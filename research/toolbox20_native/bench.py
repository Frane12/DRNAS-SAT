"""Paired, serial, single-CPU wall-clock benchmark with independent verification."""
import argparse
import csv
import gzip
import json
import os
import platform
import re
import statistics
import subprocess
import tempfile
import time
from pathlib import Path
from corpus import sha
from verify import check_model, check_unsat

MAIN = ("DRNAS","Kissat","CaDiCaL")


def run_one(name, cmd, path, proof, checker, cap, destination, saved):
    if proof.exists(): proof.unlink()
    begin=time.perf_counter()
    try:
        job=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=cap)
    except subprocess.TimeoutExpired:
        return dict(status="TIMEOUT",wall_s=time.perf_counter()-begin,check_s=0,method="",phase="",detail="external cap")
    wall=time.perf_counter()-begin
    out=job.stdout.decode("ascii","replace")
    status_lines=[line for line in out.splitlines() if line.startswith("s ")]
    phase=re.search(r"^c phase (.+)$",out,re.M)
    row=dict(status="ERROR",wall_s=wall,check_s=0,method="",phase=phase[1].split()[0] if phase else "",detail="")
    if phase:
        fields=phase[1].split()[1:]
        row["telemetry"]=" ".join(fields)
    if wall>cap:
        row.update(status="TIMEOUT",detail="external cap")
        return row
    check_start=time.perf_counter()
    try:
        if job.returncode==10 and status_lines==["s SATISFIABLE"]:
            row["method"]=check_model(path.read_bytes(),out)
            data=job.stdout; suffix=".out"
            row["status"]="SAT"
        elif job.returncode==20 and status_lines==["s UNSATISFIABLE"]:
            row["method"]=check_unsat(path,proof,checker)
            data=proof.read_bytes(); suffix=".proof"
            row["status"]="UNSAT"
        elif job.returncode==0 and status_lines==["s UNKNOWN"]:
            row["status"]="UNKNOWN"; return row
        else:
            row["detail"]=f"exit {job.returncode} {status_lines} {job.stderr[-180:].decode(errors='replace')}"
            return row
        row["check_s"]=time.perf_counter()-check_start
        row["evidence_sha256"]=sha(data)
        key=(destination.name,name,row["status"],row["method"])
        if key not in saved:
            destination.mkdir(parents=True,exist_ok=True)
            target=destination/(name+suffix+".gz")
            target.write_bytes(gzip.compress(data,compresslevel=6,mtime=0))
            saved.add(key)
            row["evidence"]=str(target.relative_to(destination.parent.parent))
    except (ValueError,OSError,subprocess.TimeoutExpired,KeyError) as e:
        row.update(status="AUDIT_FAILED",detail=str(e),check_s=time.perf_counter()-check_start)
    return row


def summaries(rows):
    groups=["public","fresh","all"]; out=[]
    for group in groups:
        for name in dict.fromkeys(r["solver"] for r in rows):
            selected=[r for r in rows if r["solver"]==name and (group=="all" or r["group"]==group)]
            if not selected: continue
            ids=sorted({r["id"] for r in selected}); sat=unsat=unstable=0
            for case in ids:
                statuses={r["status"] for r in selected if r["id"]==case}
                sat+=statuses=={"SAT"}; unsat+=statuses=={"UNSAT"}; unstable+=len(statuses)>1
            out.append(dict(group=group,solver=name,instances=len(ids),sat_all_reps=sat,unsat_all_reps=unsat,
                            solved_all_reps=sat+unsat,unstable=unstable,runs=len(selected),
                            unknown=sum(r["status"]=="UNKNOWN" for r in selected),
                            timeouts=sum(r["status"]=="TIMEOUT" for r in selected),
                            errors=sum(r["status"] in ("ERROR","AUDIT_FAILED") for r in selected),
                            par2_s=statistics.mean(r["par2_s"] for r in selected),
                            mean_check_s_verified=statistics.mean(r["check_s"] for r in selected if r["status"] in ("SAT","UNSAT")) if sat+unsat else None))
    return out


def main():
    p=argparse.ArgumentParser()
    for arg in ["manifest","corpus","out","drnas","kissat","cadical","checker"]:
        p.add_argument("--"+arg,type=Path,required=True)
    p.add_argument("--cap",type=float,default=3.0);p.add_argument("--reps",type=int,default=3)
    p.add_argument("--prior",type=Path,help="optional frozen DRNAS reference")
    p.add_argument("--ablation",action="store_true",help="only the paired --no-repair diagnostic")
    a=p.parse_args()
    if a.cap<=0 or a.reps<=0:p.error("positive cap and repetitions required")
    a.out.mkdir(parents=True,exist_ok=False)
    cpu=min(os.sched_getaffinity(0));os.sched_setaffinity(0,{cpu})
    manifest=json.loads(a.manifest.read_bytes())
    files={k:getattr(a,k).resolve() for k in ("drnas","kissat","cadical","checker")}
    if a.prior: files["prior"]=a.prior.resolve()
    arms=("DRNAS-no-repair",) if a.ablation else (("DRNAS","DRNAS-prior","Kissat","CaDiCaL") if a.prior else MAIN)
    meta=dict(freeze=manifest["freeze"],cap_s=a.cap,repetitions=a.reps,cpu=cpu,
              cpu_model=next((line.split(":",1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines() if line.startswith("model name")),"unknown"),
              platform=platform.platform(),python=platform.python_version(),manifest_sha256=sha(a.manifest.read_bytes()),
              binaries={k:sha(v.read_bytes()) for k,v in files.items()},arms=arms,
              versions={k:subprocess.check_output([files[k],"--version"],text=True).strip().splitlines()[0] for k in ("kissat","cadical")})
    (a.out/"environment.json").write_text(json.dumps(meta,indent=2)+"\n")
    cases=sorted(manifest["cases"],key=lambda c:sha(f"{manifest['freeze']}|order|{c['id']}".encode()))
    rows=[]; saved=set()
    with tempfile.TemporaryDirectory() as td, (a.out/"runs.csv").open("w",newline="") as stream:
        path=Path(td)/"input.cnf"; proof=Path(td)/"evidence"
        fields=("id","group","family","rep","order","solver","status","wall_s","check_s","par2_s","method","phase","telemetry","evidence_sha256","evidence","detail")
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for rep in range(a.reps):
            for i,case in enumerate(cases):
                data=(a.corpus/(case["id"]+".cnf")).read_bytes()
                if sha(data)!=case["cnf_sha256"]:raise ValueError("holdout hash mismatch")
                path.write_bytes(data)
                start=(i+rep)%len(arms)
                for order,name in enumerate(arms[start:]+arms[:start]):
                    if name.startswith("DRNAS"):
                        cmd=[files["prior" if name=="DRNAS-prior" else "drnas"],path,proof,str(a.cap)]
                        if a.ablation:cmd+=["--no-repair"]
                    else:
                        cmd=[files[name.lower()],"-q",path,proof]
                    result=run_one(name,cmd,path,proof,files["checker"],a.cap,a.out/"evidence"/case["id"],saved)
                    row={k:case[k] for k in ("id","group","family")}
                    row.update(rep=rep+1,order=order+1,solver=name,**result)
                    row["par2_s"]=row["wall_s"] if row["status"] in ("SAT","UNSAT") else 2*a.cap
                    rows.append(row); writer.writerow(row); stream.flush()
            print(f"completed repetition {rep+1}/{a.reps}",flush=True)
    for case in cases:
        answers={r["status"] for r in rows if r["id"]==case["id"] and r["status"] in ("SAT","UNSAT")}
        if len(answers)>1:raise RuntimeError("contradictory accepted answers: "+case["id"])
    summary=summaries(rows);(a.out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    if any(r["status"] in ("ERROR","AUDIT_FAILED") for r in rows):raise SystemExit("solver or validation error in runs.csv")

if __name__=="__main__": main()
