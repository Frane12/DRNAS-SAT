"""Failure-directed native reasoning; train policy on replay misses, freeze, blind test."""
import argparse, collections as C, json, os, random, re, subprocess, time
from pathlib import Path
from corpus import sha, parse_source
from unified6_utility import corpus, load, dump
from verify import check_model, check_unsat
CAP=5.0
OLD="b142f6ae7d064157c3a9c43ac1b84e1c28323292"
MISS={3,4,5,11,17,22,23,29}
def run(root,row,arm,policy,solver,base,checker):
    path,raw=load(root,row)
    d=root/"evidence"/row["id"]/arm;d.mkdir(parents=True)
    proof=d/"solver.proof"
    env=dict(os.environ,DRNAS_U7_POLICY=str(policy))
    start=time.monotonic()
    try:
        x=subprocess.run([base if arm=="base" else solver,str(path),str(proof),str(CAP-.12)],capture_output=True,timeout=CAP,env=env)
        elapsed=time.monotonic()-start;out=x.stdout.decode("ascii","replace")
        verdict={10:"SAT",20:"UNSAT",0:"UNKNOWN"}.get(x.returncode,"ERROR")
        wanted={"SAT":"s SATISFIABLE","UNSAT":"s UNSATISFIABLE","UNKNOWN":"s UNKNOWN"}.get(verdict)
        if wanted not in out.splitlines():raise ValueError("bad solver output: "+out[-300:]+x.stderr.decode(errors="replace")[-300:])
    except subprocess.TimeoutExpired as e:
        elapsed=time.monotonic()-start;out=(e.stdout or b"").decode("ascii","replace");verdict="TIMEOUT"
    if elapsed>CAP:verdict="TIMEOUT"
    (d/"solver.out").write_text(out)
    verified=""
    if verdict=="SAT":verified=check_model(raw,out)
    elif verdict=="UNSAT":verified=check_unsat(path,proof,checker)
    telemetry={}
    m=re.search(r"^c phase (\S+) (.*)$",out,re.M)
    if m:
        fields=m[2].split()
        telemetry={k:int(v) for k,v in zip(fields[::2],fields[1::2]) if k.startswith("frontier_") and v.isdigit()}
    return dict(id=row["id"],family=row["family"],arm=arm,policy=policy,status=verdict,verified=verified,elapsed=elapsed,phase=m[1] if m else "",sha256=row["sha256"],**telemetry)
def solved(r):return r["status"] in ("SAT","UNSAT")
def progress(r):
    # Primary target: verified decisions. Root propagation is a tie-breaker,
    # not a substitute for a solved formula. Raw clause volume is not reward.
    return max(0,r.get("frontier_root_after",0)-r.get("frontier_root_before",0))
def cost(r):return r["elapsed"] if solved(r) else CAP*2
def evaluate(rr):
    return dict(n=len(rr),solved=sum(map(solved,rr)),sat=sum(r["status"]=="SAT" for r in rr),unsat=sum(r["status"]=="UNSAT" for r in rr),
        par2=sum(map(cost,rr))/len(rr),progress=sum(map(progress,rr)),
        frontier_active=sum(r.get("frontier_rounds",0)>0 for r in rr),
        frontier_decisions=sum(r["phase"] in ("frontier-rup","frontier-root-rup") and solved(r) for r in rr),
        novel=sum(r.get("frontier_novel",0) for r in rr),units=sum(r.get("frontier_units",0) for r in rr))
def emit(tag,row):print(tag,json.dumps(row,sort_keys=True),flush=True)
def check_pair(rr):
    if len({r["status"] for r in rr if solved(r)})>1:raise ValueError("contradictory audited answers")
def main():
    p=argparse.ArgumentParser()
    for k in ("solver","base","checker","out"):p.add_argument("--"+k,type=Path,required=True)
    p.add_argument("--freeze",required=True);a=p.parse_args()
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    root=a.out;root.mkdir();solver=str(a.solver.resolve());base=str(a.base.resolve());checker=str(a.checker.resolve())
    # Reconstruct the exact prior test split using the previous frozen commit.
    # Keep only the eight logged misses as development; never count as holdout.
    old=root/"old";old.mkdir()
    prior=corpus(old,OLD,"test",[("random3",30),("tseitin",10),("colour",10)])
    (root/"replay").mkdir()
    replay=[]
    for r in prior:
        if r["family"]!="random3" or int(r["id"].split("-")[-1]) not in MISS:continue
        raw=(old/"test"/(r["id"]+".cnf")).read_bytes()
        cid="replay-"+r["id"].split("-",1)[1]
        (root/"replay"/(cid+".cnf")).write_bytes(raw)
        replay.append(dict(r,id=cid,original_id=r["id"]))
    assert len(replay)==8
    cal=corpus(root,a.freeze,"cal",[("random3",12)])
    test=corpus(root,a.freeze,"test",[("random3",30),("tseitin",10),("colour",10),("circuit",6),("mixed",4)])
    assert len({r["sha256"] for r in replay+cal+test})==len(replay+cal+test)
    dump(root/"manifest.json",dict(freeze=a.freeze,previous=OLD,replay=replay,calibration=cal,test=test,cap=CAP))
    train=[];policies=[0,1,2]
    for i,row in enumerate(replay+cal):
        rr=[]
        for policy in policies[i%3:]+policies[:i%3]:
            r=run(root,row,"policy"+str(policy),policy,solver,base,checker);rr.append(r);train.append(r);emit("U7_TRAIN",r)
        check_pair(rr)
    # Learn policy priority exclusively from the training/calibration cohort.
    # Lexicographic: more solved, stronger root progress, then lower PAR2.
    stats={str(p):evaluate([r for r in train if r["policy"]==p]) for p in policies}
    selected=min(policies,key=lambda p:(-stats[str(p)]["solved"],-stats[str(p)]["progress"],stats[str(p)]["par2"],p))
    dump(root/"policy.json",dict(selected=selected,training=stats))
    dump(root/"training.json",train)
    digest=sha((root/"policy.json").read_bytes())
    emit("U7_POLICY",dict(selected=selected,stats=stats,policy_sha256=digest))
    rows=[];arms=["base","neutral","learned"]
    # Replays are reported separately and never pooled into prospective holdout.
    for i,row in enumerate(replay+test):
        rr=[]
        for arm in arms[i%3:]+arms[:i%3]:
            policy=selected if arm=="learned" else 0
            r=run(root,row,arm,policy,solver,base,checker)
            r.update(group="replay" if row["id"].startswith("replay") else "fresh",policy_sha256=digest)
            rows.append(r);rr.append(r);emit("U7_ROW",r)
        check_pair(rr)
        dump(root/"results.json",rows)
        if sha((root/"policy.json").read_bytes())!=digest:raise ValueError("frozen policy changed")
    summary={}
    for group in ("replay","fresh"):
        group_rows=[r for r in rows if r["group"]==group]
        by=C.defaultdict(dict)
        for r in group_rows:by[r["id"]][r["arm"]]=r
        summary[group]={}
        for arm in arms:
            z=evaluate([p[arm] for p in by.values()])
            z["gains"]=[i for i,p in by.items() if solved(p[arm]) and not solved(p["base"])]
            z["regressions"]=[i for i,p in by.items() if solved(p["base"]) and not solved(p[arm])]
            summary[group][arm]=z
    dump(root/"summary.json",summary);emit("U7_SUMMARY",summary)
if __name__=="__main__":main()
