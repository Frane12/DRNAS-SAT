"""Paired native representation ablation: frozen prior solvers and two factor modes."""
import argparse,collections as C,json,os,re,subprocess,time
from pathlib import Path
from corpus import sha
from unified6_utility import corpus,load,dump
from unified7_failure import OLD,MISS
from verify import check_model,check_unsat
CAP=5.
def run(root,row,arm,paths,checker):
    path,raw=load(root,row);d=root/"evidence"/row["id"]/arm;d.mkdir(parents=True)
    proof=d/"proof";env=dict(os.environ,DRNAS_U7_POLICY="0",DRNAS_U8_MODE="2" if arm=="hybrid" else "1")
    start=time.monotonic()
    try:
        x=subprocess.run([paths[arm],str(path),str(proof),str(CAP-.12)],env=env,capture_output=True,timeout=CAP)
        elapsed=time.monotonic()-start;out=x.stdout.decode("ascii","replace")
        status={10:"SAT",20:"UNSAT",0:"UNKNOWN"}.get(x.returncode,"ERROR")
        if {"SAT":"s SATISFIABLE","UNSAT":"s UNSATISFIABLE","UNKNOWN":"s UNKNOWN"}.get(status) not in out.splitlines():
            raise ValueError("bad solver output "+out[-300:]+x.stderr.decode(errors="replace")[-300:])
    except subprocess.TimeoutExpired as e:
        elapsed=time.monotonic()-start;out=(e.stdout or b"").decode("ascii","replace");status="TIMEOUT"
    if elapsed>CAP:status="TIMEOUT"
    (d/"solver.out").write_text(out);verified=""
    if status=="SAT":verified=check_model(raw,out)
    elif status=="UNSAT":verified=check_unsat(path,proof,checker)
    phase=re.search(r"^c phase (\S+) (.*)$",out,re.M);tele={}
    if phase:
        fields=phase[2].split()
        tele={k:int(v) for k,v in zip(fields[::2],fields[1::2]) if (k.startswith("factor_") or k.startswith("frontier_")) and v.isdigit()}
    return dict(id=row["id"],family=row["family"],group="replay" if row["id"].startswith("replay") else "fresh",arm=arm,status=status,verified=verified,elapsed=elapsed,sha256=row["sha256"],phase=phase[1] if phase else "",**tele)
def solved(r):return r["status"] in ("SAT","UNSAT")
def summary(rows,arms):
    by=C.defaultdict(dict)
    for r in rows:by[r["id"]][r["arm"]]=r
    out={}
    for a in arms:
        rr=[p[a] for p in by.values()]
        out[a]=dict(n=len(rr),solved=sum(map(solved,rr)),sat=sum(r["status"]=="SAT" for r in rr),unsat=sum(r["status"]=="UNSAT" for r in rr),par2=sum(r["elapsed"] if solved(r) else 2*CAP for r in rr)/len(rr),
            active=sum(r.get("factor_bags",0)>0 for r in rr),novel=sum(r.get("factor_novel",0) for r in rr),wide=sum(r.get("factor_wide",0) for r in rr),units=sum(r.get("factor_units",0) for r in rr),global_blocked=sum(r.get("factor_global_blocked",0) for r in rr),gains=[i for i,p in by.items() if solved(p[a]) and not solved(p["base"])],regressions=[i for i,p in by.items() if not solved(p[a]) and solved(p["base"])],gains_vs_frontier=[i for i,p in by.items() if solved(p[a]) and not solved(p["frontier"])])
    return out
def main():
    p=argparse.ArgumentParser()
    for k in ("base","frontier","factor","checker","out"):p.add_argument("--"+k,type=Path,required=True)
    p.add_argument("--freeze",required=True);a=p.parse_args()
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    root=a.out;root.mkdir();old=root/"old";old.mkdir()
    prior=corpus(old,OLD,"test",[("random3",30),("tseitin",10),("colour",10)])
    (root/"replay").mkdir();replay=[]
    for r in prior:
        if r["family"]!="random3" or int(r["id"].split("-")[-1]) not in MISS:continue
        raw=(old/"test"/(r["id"]+".cnf")).read_bytes();cid="replay-"+r["id"].split("-",1)[1]
        (root/"replay"/(cid+".cnf")).write_bytes(raw);replay.append(dict(r,id=cid))
    assert len(replay)==8
    test=corpus(root,a.freeze,"test",[("random3",30),("tseitin",6),("colour",6),("circuit",4),("mixed",4)])
    assert len({r["sha256"] for r in replay+test})==58
    dump(root/"manifest.json",dict(freeze=a.freeze,replay=replay,test=test,cap=CAP))
    arms=["base","frontier","factor","hybrid"]
    paths={k:str(getattr(a,k if k!="hybrid" else "factor").resolve()) for k in arms}
    rows=[]
    for i,row in enumerate(replay+test):
        rr=[]
        for arm in arms[i%4:]+arms[:i%4]:
            r=run(root,row,arm,paths,str(a.checker.resolve()));rr.append(r);rows.append(r)
            print("U8_ROW",json.dumps(r,sort_keys=True),flush=True)
        if len({r["status"] for r in rr if solved(r)})>1:raise ValueError("contradictory answers")
        dump(root/"results.json",rows)
    out={g:summary([r for r in rows if r["group"]==g],arms) for g in ("replay","fresh")}
    out["families"]={f:summary([r for r in rows if r["group"]=="fresh" and r["family"]==f],arms) for f in ("random3","tseitin","colour","circuit","mixed")}
    dump(root/"summary.json",out);print("U8_SUMMARY",json.dumps(out),flush=True)
if __name__=="__main__":main()
