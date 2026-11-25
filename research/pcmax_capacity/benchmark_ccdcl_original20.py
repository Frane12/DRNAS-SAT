#!/usr/bin/env python3
"""Original20 comparison with published cardinality-CDCL core and extractor.
Uses actual extracted KNF (not the upstream CCDCL shell script's prop.cnf typo).
No source labels or oracle schedules passed to solvers. Verify on original CNF.
"""
import argparse, hashlib, json, os, random, subprocess, sys, time
from pathlib import Path
from benchmark_pgpbs_original20 import run, CAP, CHECK_CAP, ROOT, HERE, limits
from benchmark import materialize

def stage(cmd, budget, log, output=None):
    if budget<=0:return 124,0.0,""
    if output is None:return run(cmd,budget,log)
    start=time.monotonic()
    with output.open("wb") as out,log.open("wb") as err:
        try:rc=subprocess.run([str(x) for x in cmd],stdout=out,stderr=err,timeout=budget,preexec_fn=limits).returncode
        except subprocess.TimeoutExpired:rc=124
    return rc,time.monotonic()-start,log.read_text(errors="replace")[-65536:]

def parse_cnf(path):
    nv=None;clauses=[];current=[]
    for line in path.read_text().splitlines():
        s=line.split()
        if not s or s[0]=="c":continue
        if s[0]=="p":nv=int(s[2]);continue
        for v in map(int,s):
            if v==0:clauses.append(current);current=[]
            else:current.append(v)
    assert nv is not None and not current
    return nv,clauses

def model(log,n):
    vals={}
    for line in log.read_text(errors="replace").splitlines():
        if line.startswith("v "):
            for x in map(int,line[2:].split()):
                if x and abs(x)<=n:
                    if abs(x) in vals and vals[abs(x)]!=(x>0):return {}
                    vals[abs(x)]=x>0
    return vals

def satisfies(vals,cs):
    return all(any(abs(x) in vals and vals[abs(x)]==(x>0) for x in c) for c in cs)

def sat_check(r,src,d,plain,knf,solve_log):
    start=time.monotonic();nv,cs=parse_cnf(src);vals=model(solve_log,nv)
    if satisfies(vals,cs):
        r.update(certified=True,status="SAT_VERIFIED",check_s=time.monotonic()-start,check_type="original-clause model")
        return
    # Reconstruction, following upstream extension approach: remove extracted
    # encoding variables, then extend retained assignment on the original CNF.
    eliminated=set()
    if knf.exists():
        for l in knf.read_text(errors="replace").splitlines():
            if l.startswith("c Eliminated variables IDs:"):
                eliminated.update(int(x) for x in l.split(":")[-1].split() if x.isdigit())
    # Discard assignments to variables absent from the retained KNF constraints:
    # preprocessing can remove fixed or auxiliary variables.
    retained=set()
    if knf.exists():
        for l in knf.read_text(errors="replace").splitlines():
            w=l.split()
            if not w or w[0] in ("p","c"):continue
            if w[0]=="k":w=w[2:]
            retained.update(abs(int(x)) for x in w if x!="0")
    vals={k:v for k,v in vals.items() if k not in eliminated and k in retained}
    if not vals:
        r.update(check_s=time.monotonic()-start,check_type="no retained model");return
    ext=d/"extension.cnf"
    with ext.open("w") as f:
        f.write(f"p cnf {nv} {len(cs)+len(vals)}\n")
        for c in cs:f.write(" ".join(map(str,c))+" 0\n")
        for k,v in vals.items():f.write(f"{k if v else -k} 0\n")
    rc,_,_=run([plain,ext],max(0,CHECK_CAP-(time.monotonic()-start)),d/"extension.log")
    full=model(d/"extension.log",nv) if (d/"extension.log").exists() else {}
    accepted=rc==10 and satisfies(full,cs) and all(full.get(k)==v for k,v in vals.items())
    r.update(certified=accepted,status="SAT_VERIFIED" if accepted else "SAT_UNVERIFIED",
             check_s=time.monotonic()-start,check_type="source-model extension via pinned CaDiCaL then clause validation",
             extension_rc=rc,retained_assignments=len(vals))

def drnas(r,src,d,veri):
    cert=d/"capacity.json";proof=d/"proof.pbp"
    rc,t,msg=run([ROOT/"build/drnas-pcmax",src,"--mode","core","--time","7","--pcmax-only","--pcmax-capacity","--pcmax-budget-ms","5000","--pcmax-certificate",cert],CAP,d/"native.log")
    r.update(native_rc=rc,native_s=t,produce_s=t,status="TIMEOUT" if rc==124 else "UNKNOWN" if rc==0 else "NATIVE_ERROR")
    if rc==20 and cert.is_file():
        rc2,t2,_=run([sys.executable,HERE/"emit_veripb_capacity_weighted2.py","--cnf",src,"--certificate",cert,"--output",proof],CAP-t,d/"emit.log")
        r.update(emit_rc=rc2,emit_s=t2,produce_s=t+t2,status="TIMEOUT" if rc2==124 else "UNSAT_UNVERIFIED")
        if rc2==0 and proof.is_file() and proof.stat().st_size and t+t2<=CAP:
            cr,ct,cm=run([veri,"--cnf",src,proof],CHECK_CAP,d/"check.log")
            accepted=cr==0 and any(l.strip()=="s VERIFIED UNSATISFIABLE" for l in cm.splitlines())
            r.update(check_rc=cr,check_s=ct,proof_bytes=proof.stat().st_size,proof_type="VeriPB",certified=accepted)
            if accepted:r["status"]="UNSAT_VERIFIED"

def ccdcl(r,src,d,up,hybrid):
    plain=up/"Tools/cadical/build/cadical"; solver=up/"cardinality-cadical/build/cadical"
    extractor=up/"Extractor/cnf2knf/src/cnf2knf"; checker=up/"Tools/drat-trim/drat-trim"
    prop=d/"prop.cnf";knf=d/"extracted.knf";proof=d/"solve.drat";combined=d/"proof.drat"
    def step(name,cmd,output=None):
        rc,t,msg=stage(cmd,CAP-r["produce_s"],d/(name+".log"),output)
        r[name+"_rc"]=rc;r[name+"_s"]=t;r["produce_s"]+=t
        if rc==124:r["status"]="TIMEOUT"
        return rc,msg
    r.update(produce_s=0.,status="PREPROCESS_ERROR")
    # Request preprocessing proof too; original input is always checker target.
    pp=d/"preprocess.drat"
    rc,_=step("preprocess",[plain,src,pp,"-c","0","-f","-o",prop,"--no-binary"])
    if rc==20:
        r["status"]="UNSAT_UNVERIFIED"
        if pp.exists():
            cr,ct,cm=run([checker,src,pp],CHECK_CAP,d/"check.log")
            ok=cr==0 and any(l.strip()=="s VERIFIED" for l in cm.splitlines())
            r.update(certified=ok,check_s=ct,check_rc=cr,proof_type="DRAT",proof_bytes=pp.stat().st_size)
            if ok:r["status"]="UNSAT_VERIFIED"
        return
    if rc not in (0,10) or not prop.is_file():return
    r["status"]="EXTRACT_ERROR"
    rc,_=step("extract",[extractor,prop],knf)
    if rc!=0:return
    lines=knf.read_text(errors="replace").splitlines()
    heads=[l.split() for l in lines if l.startswith("p knf ")]
    if len(heads)!=1:return
    r["cardinality_constraints"]=sum(l.startswith("k ") for l in lines)
    r["knf_vars"]=int(heads[0][2]);r["knf_constraints"]=int(heads[0][3])
    inp=knf
    if hybrid:
        encoded=d/"encode.cnf"
        r["status"]="REENCODE_ERROR"
        rc,_=step("reencode",[up/"Tools/konly",knf],encoded)
        if rc!=0:return
        el=encoded.read_text().splitlines();eh=[l.split() for l in el if l.startswith("p cnf ")]
        if len(eh)!=1:return
        body=[l for l in lines+el if l.strip() and not l.startswith(("p ","c "))]
        inp=d/"full.knf"
        inp.write_text(f"p knf {max(int(eh[0][2]),r['knf_vars'])} {len(body)}\n"+"\n".join(body)+"\n")
    r["status"]="SOLVER_ERROR"
    rc,msg=step("solve",[solver,inp,proof,"--no-binary",f"--ccdclMode={1 if hybrid else 0}"])
    if rc==10:
        r["status"]="SAT_UNVERIFIED"
        sat_check(r,src,d,plain,knf,d/"solve.log")
    elif rc==20:
        r["status"]="UNSAT_UNVERIFIED"
        if not proof.is_file():return
        deriv=d/"deriv.drat"
        rc2,_=step("derive",[up/"Tools/derivation",knf],deriv)
        if rc2!=0:return
        with combined.open("wb") as f:
            for p in (pp,deriv,proof):
                if p.is_file():
                    with p.open("rb") as g:
                        for chunk in iter(lambda:g.read(1024*1024),b""):f.write(chunk)
        cr,ct,cm=run([checker,src,combined],CHECK_CAP,d/"check.log")
        ok=cr==0 and any(l.strip()=="s VERIFIED" for l in cm.splitlines())
        r.update(certified=ok,check_s=ct,check_rc=cr,proof_type="DRAT",proof_bytes=combined.stat().st_size)
        if ok:r["status"]="UNSAT_VERIFIED"
    elif rc==0:r["status"]="UNKNOWN"

def main():
    p=argparse.ArgumentParser();p.add_argument("--upstream",type=Path,required=True);p.add_argument("--veripb",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
    up=a.upstream.resolve();veri=a.veripb.resolve();out=a.out.resolve();out.mkdir();(out/"inputs").mkdir()
    cpu=min(os.sched_getaffinity(0));os.sched_setaffinity(0,{cpu})
    manifest=json.loads((HERE/"sources20.json").read_text())["entries"];assert len(manifest)==20
    files=[]
    for i,e in enumerate(manifest):
        archived=ROOT/"evidence/pcmax-weighted2"/f"{i:02}"/"original.cnf"
        src=archived if archived.exists() else materialize(e,out/"inputs",True)
        assert hashlib.sha256(src.read_bytes()).hexdigest()==e["sha256"]
        dest=out/"inputs"/f"case-{i:02}.cnf";dest.write_bytes(src.read_bytes());files.append(dest)
    rows=[]
    for i,e in enumerate(manifest):
        arms=["drnas","ccdcl","ccdcl_plus"];random.Random(20261125+i).shuffle(arms)
        for arm in arms:
            d=out/f"{i:02}"/arm;d.mkdir(parents=True)
            r=dict(id=i,arm=arm,expected="SAT" if e["expected_status"]=="SAT" else "UNSAT",sha256=e["sha256"],certified=False,cap_s=CAP,check_cap_s=CHECK_CAP,produce_s=0.)
            try:
                if arm=="drnas":drnas(r,files[i],d,veri)
                else:ccdcl(r,files[i],d,up,arm=="ccdcl_plus")
            except Exception as exc:r.update(status="HARNESS_ERROR",error=str(exc)[:500],certified=False)
            r["verified_total_s"]=r["produce_s"]+r.get("check_s",0)
            r["within_produce_cap"]=r["produce_s"]<=CAP
            rows.append(r)
            with (out/"rows.jsonl").open("a") as f:f.write(json.dumps(r,sort_keys=True)+"\n")
            print("CCDCL_PCMAX_ROW",json.dumps(r,sort_keys=True),flush=True)
            for q in d.glob("*.drat"):
                h=hashlib.sha256()
                with q.open("rb") as f:
                    for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
                q.with_suffix(q.suffix+".sha256").write_text(h.hexdigest()+"\n")
                if q.stat().st_size>16*1024*1024 or not r["certified"]:q.unlink()
    summary={}
    for arm in ("drnas","ccdcl","ccdcl_plus"):
        rr=[r for r in rows if r["arm"]==arm]
        solved=[r for r in rr if r["certified"] and r["within_produce_cap"] and r["status"]==r["expected"]+"_VERIFIED"]
        summary[arm]=dict(n=len(rr),verified=len(solved),unsat=sum(r["expected"]=="UNSAT" for r in solved),sat=sum(r["expected"]=="SAT" for r in solved),statuses={s:sum(r["status"]==s for r in rr) for s in sorted({r["status"] for r in rr})},certified_production_par2=sum(r["produce_s"] if r in solved else 2*CAP for r in rr)/len(rr))
    (out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print("CCDCL_PCMAX_FINAL",json.dumps(summary),flush=True)
    if any(r["certified"] and r["status"]!=r["expected"]+"_VERIFIED" for r in rows):raise SystemExit("verified label disagreement")
    if any(r["status"]=="HARNESS_ERROR" for r in rows):raise SystemExit("harness errors; inspect logs")
if __name__=="__main__":main()
