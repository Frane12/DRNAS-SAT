#!/usr/bin/env python3
"""Retrospective original20 paired comparison. No CDCL fallback, no oracle schedules."""
import argparse, hashlib, json, os, random, resource, subprocess, sys, time
from pathlib import Path
from benchmark import materialize

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CAP=30.0
CHECK_CAP=60.0
MAX_FILE=128*1024*1024
MAX_AS=5*1024**3
def limits():
    resource.setrlimit(resource.RLIMIT_FSIZE,(MAX_FILE,MAX_FILE))
    resource.setrlimit(resource.RLIMIT_AS,(MAX_AS,MAX_AS))
def run(cmd,budget,log):
    if budget<=0:
        return 124,0.0,""
    start=time.monotonic()
    with log.open("wb") as f:
        try:
            p=subprocess.run([str(x) for x in cmd],stdout=f,stderr=subprocess.STDOUT,timeout=budget,preexec_fn=limits)
            rc=p.returncode
        except subprocess.TimeoutExpired: rc=124
    elapsed=time.monotonic()-start
    with log.open("rb") as f:
        f.seek(max(0,log.stat().st_size-65536)); msg=f.read().decode(errors="replace")
    return rc,elapsed,msg
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--pgpbs",type=Path,required=True)
    ap.add_argument("--veripb",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    pg=a.pgpbs.resolve(); veri=a.veripb.resolve(); out=a.out.resolve()
    out.mkdir(parents=True,exist_ok=False)
    (out/"inputs").mkdir()
    cpu=min(os.sched_getaffinity(0));os.sched_setaffinity(0,{cpu})
    manifest=json.loads((HERE/"sources20.json").read_text())["entries"]
    assert len(manifest)==20 and len({e["sha256"] for e in manifest})==20
    # Input acquisition is outside timing. Prefer exact archived bytes where present.
    files=[]
    for i,e in enumerate(manifest):
        archived=ROOT/"evidence/pcmax-weighted2"/f"{i:02}"/"original.cnf"
        if archived.is_file():
            src=archived
        else:
            src=materialize(e,out/"inputs",True)
        assert hashlib.sha256(src.read_bytes()).hexdigest()==e["sha256"]
        # Blind filename: neither tool receives status labels through its filename.
        dest=out/"inputs"/f"case-{i:02}.cnf";dest.write_bytes(src.read_bytes());files.append(dest)
    rows=[]
    for i,e in enumerate(manifest):
        src=files[i]
        expected="SAT" if e["expected_status"]=="SAT" else "UNSAT"
        arms=["drnas","pgpbs"];random.Random(20261125+i).shuffle(arms)
        for arm in arms:
            d=out/f"{i:02}"/arm;d.mkdir(parents=True)
            r=dict(id=i,arm=arm,sha256=e["sha256"],expected=expected,certified=False,cap_s=CAP,check_cap_s=CHECK_CAP)
            if arm=="pgpbs":
                schedule=d/"input.schedule";proof=d/"proof.lrat"
                rc,t,msg=run([sys.executable,pg/"src/constraint_extractor.py","-v","2","-i",src,"-o",schedule],CAP,d/"extract.log")
                r.update(extract_rc=rc,extract_s=t,produce_s=t,status="UNKNOWN")
                if rc==124:r["status"]="TIMEOUT"
                elif rc!=0 or not schedule.is_file() or not schedule.stat().st_size:
                    r["status"]="UNSUPPORTED" if "Could not classify" in msg or "Could not be classified" in msg else "EXTRACT_ERROR"
                else:
                    rc2,t2,msg2=run([sys.executable,pg/"src/pgpbs.py","-v","1","-r","123456","-i",src,"-s",schedule,"-o",proof],CAP-t,d/"solve.log")
                    r.update(solver_rc=rc2,solve_s=t2,produce_s=t+t2,status="TIMEOUT" if rc2==124 else "UNKNOWN" if rc2==0 else "SOLVER_ERROR")
                    if proof.is_file() and proof.stat().st_size and rc2==0 and t+t2<=CAP:
                        cr,ct,cm=run([pg/"lrat/lrat-check",src,proof],CHECK_CAP,d/"check.log")
                        accepted=cr==0 and any(l.strip()=="c VERIFIED" for l in cm.splitlines())
                        r.update(check_rc=cr,check_s=ct,proof_bytes=proof.stat().st_size,proof_type="LRAT",certified=accepted)
                        if accepted:r["status"]="UNSAT_VERIFIED"
                        elif "proved formula UNSAT" in msg2 or any(l.strip()=="UNSAT" for l in msg2.splitlines()):r["status"]="UNSAT_UNVERIFIED"
            else:
                cert=d/"capacity.json";proof=d/"proof.pbp"
                rc,t,msg=run([ROOT/"build/drnas-pcmax",src,"--mode","core","--time","7","--pcmax-only","--pcmax-capacity","--pcmax-budget-ms","5000","--pcmax-certificate",cert],CAP,d/"native.log")
                r.update(native_rc=rc,native_s=t,produce_s=t,status="TIMEOUT" if rc==124 else "UNKNOWN" if rc==0 else "NATIVE_ERROR")
                if rc==20 and cert.is_file():
                    rc2,t2,msg2=run([sys.executable,HERE/"emit_veripb_capacity_weighted2.py","--cnf",src,"--certificate",cert,"--output",proof],CAP-t,d/"emit.log")
                    r.update(emit_rc=rc2,emit_s=t2,produce_s=t+t2,status="TIMEOUT" if rc2==124 else "UNSAT_UNVERIFIED")
                    if rc2==0 and proof.is_file() and proof.stat().st_size and t+t2<=CAP:
                        cr,ct,cm=run([veri,"--cnf",src,proof],CHECK_CAP,d/"check.log")
                        accepted=cr==0 and any(l.strip()=="s VERIFIED UNSATISFIABLE" for l in cm.splitlines())
                        r.update(check_rc=cr,check_s=ct,proof_bytes=proof.stat().st_size,proof_type="VeriPB",certified=accepted)
                        if accepted:r["status"]="UNSAT_VERIFIED"
            r["verified_total_s"]=r["produce_s"]+r.get("check_s",0)
            r["within_produce_cap"]=r["produce_s"]<=CAP
            rows.append(r)
            with (out/"rows.jsonl").open("a") as f:f.write(json.dumps(r,sort_keys=True)+"\n")
            print("PGPBS_PCMax_ROW",json.dumps(r,sort_keys=True),flush=True)
            # Keep proof hashes, sizes and checker logs; avoid filling runner disk.
            if proof.exists():
                h=hashlib.sha256()
                with proof.open("rb") as f:
                    for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
                (d/"proof.sha256").write_text(h.hexdigest()+"\n")
                if not r["certified"] or proof.stat().st_size>16*1024*1024:proof.unlink()
    summary={}
    for arm in ["drnas","pgpbs"]:
        rr=[r for r in rows if r["arm"]==arm];solved=[r for r in rr if r["certified"] and r["within_produce_cap"]]
        summary[arm]={"n":len(rr),"verified":len(solved),"statuses":{s:sum(r["status"]==s for r in rr) for s in sorted({r["status"] for r in rr})},"unsat_cohort":sum(r["expected"]=="UNSAT" for r in solved),"sat_control_conflicts":sum(r["expected"]=="SAT" for r in solved),"certified_production_par2":sum(r["produce_s"] if r in solved else 2*CAP for r in rr)/len(rr)}
    (out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print("PGPBS_PCMAX_FINAL",json.dumps(summary),flush=True)
    if any(r["certified"] and r["expected"]=="SAT" for r in rows):raise SystemExit("SAT control contradiction")
if __name__=="__main__":main()
