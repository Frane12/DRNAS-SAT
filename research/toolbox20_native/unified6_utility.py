"""Proof-macro utility learning; frozen native solver, separate train/calibration/test."""
import argparse, collections as C, itertools, json, math, os, random, time
from pathlib import Path
from corpus import encode, parse_source, sha, fresh
from unified5_memory import norm, rup_support, audit_macro, extract, instantiate, invoke, dump, selftest
from verify import check_model, check_unsat

CAP=5.0
PILOT=.24
MATCH=.24
MAX_RULES=120
def corpus(root,freeze,split,spec):
    folder=root/split;folder.mkdir()
    rows=[]
    for family,count in spec:
        for k in range(count):
            seed=int(sha(f"{freeze}|u6|{split}|{family}|{k}".encode())[:16],16)
            rng=random.Random(seed)
            if family=="random3":
                n=([48,64,80,96,112,128] if split!="test" else [64,80,96,112,128,144])[k%6]
                density=[4.1,4.26,4.5,4.8,5.0][(k//3)%5]
                cs=[[v*rng.choice((-1,1)) for v in rng.sample(range(1,n+1),3)] for _ in range(round(n*density))]
            elif family=="mixed":
                n=24+3*k;cs=[]
                for i in range(1,n-1):
                    op=rng.randrange(3)
                    for x,y,z in itertools.product((0,1),repeat=3):
                        if z!=((x^y) if op==0 else (x&y) if op==1 else (x|y)):
                            cs.append([(-v if b else v) for v,b in zip((i,i+1,i+2),(x,y,z))])
                for _ in range(4+k):
                    cs.append([v*rng.choice((-1,1)) for v in rng.sample(range(1,n+1),2)])
                order=list(range(1,n+1));rng.shuffle(order);m=[0]+[v*rng.choice((-1,1)) for v in order]
                cs=[[m[abs(l)]*(1 if l>0 else -1) for l in c] for c in cs];rng.shuffle(cs)
            else:n,cs=fresh(family,k%3,seed)
            raw=encode(n,cs);cid=f"{split}-{family}-{k:02}"
            (folder/(cid+".cnf")).write_bytes(raw)
            rows.append(dict(id=cid,family=family,seed=seed,n=n,clauses=len(cs),sha256=sha(raw)))
    return rows

def load(root,row):
    p=root/row["id"].split("-")[0]/(row["id"]+".cnf")
    raw=p.read_bytes()
    if sha(raw)!=row["sha256"]:raise ValueError("source changed")
    return p,raw

def add_catalog(cat,macros,row):
    for p,s in macros:
        key=(p,s);z=cat.setdefault(key,dict(families=set(),sources=set()))
        z["families"].add(row["family"]);z["sources"].add(row["id"])

def catalog(cat):
    ranked=sorted(cat.items(),key=lambda x:(-len(x[1]["families"]),-len(x[1]["sources"]),len(x[0][0]),-len(x[0][1]),x[0]))[:MAX_RULES]
    return [dict(id=sha(json.dumps([p,s]).encode())[:16],premises=p,steps=s,
        families=sorted(z["families"]),sources=sorted(z["sources"])) for (p,s),z in ranked]

def match(raw,rules,seconds,learned=False,scores=None):
    n,original=parse_source(raw)
    known=set(c for x in original if (c:=norm(x)) is not None)
    initial=set(known);width=C.defaultdict(list);occ=C.defaultdict(list)
    def index(c):
        width[len(c)].append(c)
        for l in c:occ[l].append(c)
    for c in sorted(known):index(c)
    deadline=time.monotonic()+seconds
    prefix=[];hits=[];tried=C.Counter();total=0;chained=0
    # Width signature is necessary under injective signed substitution.
    def viable(r):
        need=C.Counter(map(len,r["premises"]))
        return all(len(width[w])>=k for w,k in need.items())
    def priority(r):
        rarity=min(len(width[len(c)]) for c in r["premises"])
        utility=(scores or {}).get(r["id"],0.0) if learned else 0.
        return (-utility,rarity,len(r["premises"]),r["id"])
    candidates=sorted((r for r in rules if viable(r)),key=priority)
    # At most two passes; the second can match premises produced by other macros.
    for epoch in range(2):
        start=len(prefix)
        for r in candidates:
            if time.monotonic()>=deadline or len(prefix)>=100:break
            p=tuple(map(tuple,r["premises"]));s=tuple(map(tuple,r["steps"]))
            budget=500 if learned else 500
            seen=set();matches=0
            def walk(left,m,used):
                nonlocal budget,total
                if budget<=0 or time.monotonic()>=deadline:return
                if not left:
                    key=tuple(sorted(m.items()))
                    if key not in seen:
                        seen.add(key);yield m
                    return
                def choices(c):
                    shared=[m[abs(l)]*(1 if l>0 else -1) for l in c if abs(l) in m]
                    if shared:
                        smallest=min(shared,key=lambda l:len(occ[l]))
                        return [d for d in occ[smallest] if len(d)==len(c) and all(l in d for l in shared)]
                    return width[len(c)]
                anchor=min(left,key=lambda c:(-sum(abs(l) in m for l in c),len(choices(c))))
                remaining=list(left);remaining.remove(anchor)
                # Snapshot because recursive matching can add clauses to indices.
                for d in tuple(choices(anchor)):
                    for permutation in itertools.permutations(d):
                        budget-=1;total+=1;tried[r["id"]]+=1
                        if budget<0 or time.monotonic()>=deadline:return
                        mm=dict(m);occupied=set(used)
                        for l,t in zip(anchor,permutation):
                            v=abs(l);mapped=t*(1 if l>0 else -1)
                            if v in mm:
                                if mm[v]!=mapped:break
                            elif abs(mapped) in occupied:break
                            else:mm[v]=mapped;occupied.add(abs(mapped))
                        else:yield from walk(remaining,mm,occupied)
            for m in walk(list(p),{},set()):
                if len(prefix)>=100 or matches>=5 or time.monotonic()>=deadline:break
                ip=[instantiate(c,m) for c in p];steps=[instantiate(c,m) for c in s]
                if steps[-1] in known:continue
                local=list(ip)
                if not all(c in known for c in ip):raise ValueError("missing premise")
                for c in steps:
                    if rup_support(local,c) is None:raise ValueError("invalid instantiated macro")
                    local.append(c)
                is_chain=any(c not in initial for c in ip)
                new=[]
                for c in steps:
                    if c not in known:
                        known.add(c);index(c);prefix.append(c);new.append(c)
                if not new:continue
                chained+=is_chain;matches+=1
                hits.append(dict(rule=r["id"],families=r["families"],added=len(new),short=sum(len(c)<=2 for c in new),chain=is_chain,premises=ip,conclusions=new,mapping=m))
        if len(prefix)==start or time.monotonic()>=deadline:break
    return prefix,hits,dict(tried),total,chained

def prefix_bytes(n,prefix):
    return encode(n,prefix).split(b"\n",1)[1]

def verify(raw,original_path,aug,proof,out,status,prefix,checker):
    n,original=parse_source(raw)
    active=[c for q in original if (c:=norm(q)) is not None]
    for c in prefix:
        if rup_support(active,c) is None:raise ValueError("prefix audit failed")
        active.append(c)
    if status=="SAT":return check_model(raw,out)
    if status=="UNSAT":
        kind=check_unsat(aug,proof,checker)
        if prefix and kind=="DRAT":
            combined=proof.with_name("combined.drat")
            combined.write_bytes(prefix_bytes(n,prefix)+proof.read_bytes())
            return check_unsat(original_path,combined,checker)
        return ("RUP_PREFIX+" if prefix else "")+kind
    if status=="ERROR":raise ValueError("solver error")
    return ""

def attempt(root,row,mode,solver,checker,rules=(),scores=None,cap=CAP):
    source,raw=load(root,row);n,orig=parse_source(raw)
    d=root/"evidence"/row["id"]/mode;d.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();pilot_status="SKIP";prefix=[];hits=[];tried={};trials=chains=0
    if mode!="base":
        pp=d/"pilot.proof"
        pilot_status,out,_=invoke(solver,source,pp,PILOT)
        if pilot_status=="ERROR":raise ValueError("pilot error")
        if pilot_status in ("SAT","UNSAT"):
            elapsed=time.monotonic()-start
            v=verify(raw,source,source,pp,out,pilot_status,[],checker)
            (d/"solver.out").write_text(out)
            return dict(id=row["id"],family=row["family"],mode=mode,status=pilot_status,verified=v,elapsed=elapsed,pilot=pilot_status,match_s=0,added=0,hits=0,trials=0,chains=0,cross=0,hit_details=[],attempts={})
    mt=time.monotonic()
    if mode in ("static","learned","harvest"):
        prefix,hits,tried,trials,chains=match(raw,rules,MATCH,mode=="learned",scores)
    match_s=time.monotonic()-mt
    aug=d/"input.cnf";aug.write_bytes(encode(n,orig+prefix) if prefix else raw)
    proof=d/"solver.proof";status,out,_=invoke(solver,aug,proof,cap-(time.monotonic()-start))
    elapsed=time.monotonic()-start
    (d/"solver.out").write_text(out);(d/"prefix.drup").write_bytes(prefix_bytes(n,prefix))
    if elapsed>cap:status="TIMEOUT"
    v=verify(raw,source,aug,proof,out,status,prefix,checker)
    return dict(id=row["id"],family=row["family"],mode=mode,status=status,verified=v,elapsed=elapsed,pilot=pilot_status,match_s=match_s,added=len(prefix),hits=len(hits),trials=trials,chains=chains,cross=sum(row["family"] not in h["families"] for h in hits),hit_details=hits,attempts=tried)

def solved(r):return r["status"] in ("SAT","UNSAT")
def par(r):return r["elapsed"] if solved(r) else 2*CAP

def summarize(rows):
    by=C.defaultdict(dict)
    for r in rows:by[r["id"]][r["mode"]]=r
    summary={}
    for mode in ("base","staged","static","learned"):
        rr=[p[mode] for p in by.values()]
        summary[mode]=dict(cases=len(rr),solved=sum(map(solved,rr)),sat=sum(r["status"]=="SAT" for r in rr),unsat=sum(r["status"]=="UNSAT" for r in rr),par2=sum(map(par,rr))/len(rr),
            matched=sum(r["hits"]>0 for r in rr),cross_family_matched=sum(r["cross"]>0 for r in rr),chains=sum(r["chains"] for r in rr),pilot_solved=sum(r["pilot"] in ("SAT","UNSAT") for r in rr),mean_match_s=sum(r["match_s"] for r in rr)/len(rr),
            gains_vs_base=[i for i,p in by.items() if solved(p[mode]) and not solved(p["base"])],regressions_vs_base=[i for i,p in by.items() if solved(p["base"]) and not solved(p[mode])],
            gains_vs_staged=[i for i,p in by.items() if solved(p[mode]) and not solved(p["staged"])],regressions_vs_staged=[i for i,p in by.items() if solved(p["staged"]) and not solved(p[mode])])
    return summary

def log(tag,r):
    print(tag,json.dumps({k:v for k,v in r.items() if k not in ("hit_details","attempts")},sort_keys=True),flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--solver",type=Path,required=True);p.add_argument("--checker",type=Path,required=True);p.add_argument("--out",type=Path,required=True);p.add_argument("--freeze",required=True)
    a=p.parse_args();selftest();os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    root=a.out;root.mkdir();solver=str(a.solver.resolve());checker=str(a.checker.resolve())
    train=corpus(root,a.freeze,"train",[("random3",12),("circuit",10),("mixed",8)])
    cal=corpus(root,a.freeze,"cal",[("random3",18),("circuit",6),("mixed",6)])
    test=corpus(root,a.freeze,"test",[("random3",30),("tseitin",10),("colour",10)])
    assert len({r["sha256"] for r in train+cal+test})==len(train+cal+test)
    dump(root/"manifest.json",dict(freeze=a.freeze,train=train,calibration=cal,test=test,cap=CAP,pilot=PILOT,match=MATCH))
    cat={};training=[]
    for row in train:
        source,raw=load(root,row)
        d=root/"training";d.mkdir(exist_ok=True)
        proof=d/(row["id"]+".proof")
        status,out,elapsed=invoke(solver,source,proof,3.)
        if status=="SAT":check_model(raw,out)
        elif status=="UNSAT":check_unsat(source,proof,checker)
        elif status=="ERROR":raise ValueError("training error")
        macros=extract(raw,proof)
        add_catalog(cat,macros,row)
        z=dict(id=row["id"],status=status,elapsed=elapsed,macros=len(macros));training.append(z);log("U6_TRAIN",z)
    first=catalog(cat);dump(root/"memory_initial.json",first)
    # Second learning pass only on training cases; new prefix + own derivation may
    # yield reusable proof DAGs containing previously learned inference steps.
    for row in train:
        if row["family"]!="random3":continue
        result=attempt(root,row,"harvest",solver,checker,first,cap=3.)
        d=root/"evidence"/row["id"]/"harvest";proof=d/"solver.proof"
        if result["hits"] and proof.exists() and not proof.read_bytes().startswith(b"{"):
            combined=d/"harvest.drup"
            combined.write_bytes((d/"prefix.drup").read_bytes()+proof.read_bytes())
            _,raw=load(root,row);macros=extract(raw,combined)
            add_catalog(cat,macros,row)
            result["harvested"]=len(macros)
        log("U6_HARVEST",result)
    rules=catalog(cat);dump(root/"memory.json",rules);dump(root/"training.json",training)
    # Learn ordering from calibration only. Shared case reward is an association,
    # not causal per-rule attribution; static control isolates the ranking effect.
    obs=C.defaultdict(lambda:dict(trials=0,hits=0,credit=0.,short=0,chains=0))
    calibration=[]
    for i,row in enumerate(cal):
        pair={}
        for mode in (("staged","static") if i%2==0 else ("static","staged")):
            r=attempt(root,row,mode,solver,checker,rules);pair[mode]=r;calibration.append(r);log("U6_CAL",r)
        if solved(pair["staged"]) and solved(pair["static"]) and pair["staged"]["status"]!=pair["static"]["status"]:raise ValueError("contradiction")
        r=pair["static"];reward=max(-1.,min(1.,(par(pair["staged"])-par(r))/CAP))
        if solved(r) and not solved(pair["staged"]):reward=2.
        if not solved(r) and solved(pair["staged"]):reward=-2.
        for rid,t in r["attempts"].items():obs[rid]["trials"]+=t
        for h in r["hit_details"]:
            q=obs[h["rule"]];q["hits"]+=1;q["credit"]+=reward/max(1,len(r["hit_details"]));q["short"]+=h["short"];q["chains"]+=int(h["chain"])
    scores={}
    for rule in rules:
        o=obs[rule["id"]]
        scores[rule["id"]]=round(o["credit"]/(1+math.sqrt(o["hits"]))+.08*math.log1p(o["hits"])+.03*math.log1p(o["short"])+.04*math.log1p(o["chains"])-.04*math.log1p(o["trials"]/max(1,o["hits"])/100),8)
    dump(root/"calibration.json",calibration);dump(root/"utility.json",dict(scores=scores,observations=dict(obs)))
    memhash=sha((root/"memory.json").read_bytes());utilityhash=sha((root/"utility.json").read_bytes())
    print("U6_FROZEN",json.dumps(dict(rules=len(rules),initial=len(first),observed=sum(o["hits"]>0 for o in obs.values()),memory_sha256=memhash,utility_sha256=utilityhash)),flush=True)
    results=[];arms=["base","staged","static","learned"]
    for i,row in enumerate(test):
        for mode in arms[i%4:]+arms[:i%4]:
            r=attempt(root,row,mode,solver,checker,rules,scores)
            r.update(memory_sha256=memhash,utility_sha256=utilityhash)
            results.append(r);log("U6_ROW",r);dump(root/"results.json",results)
        if len({r["status"] for r in results[-4:] if solved(r)})>1:raise ValueError("contradictory answers")
        if sha((root/"memory.json").read_bytes())!=memhash or sha((root/"utility.json").read_bytes())!=utilityhash:raise ValueError("test contamination")
    summary={"all":summarize(results)}
    for fam in ("random3","tseitin","colour"):summary[fam]=summarize([r for r in results if r["family"]==fam])
    dump(root/"summary.json",summary);print("U6_SUMMARY",json.dumps(summary),flush=True)
if __name__=="__main__":main()
