"""UNIFIED5: learn bounded, proof-carrying inference macros from a frozen solver."""
import argparse, collections, hashlib, itertools, json, os, random, subprocess, sys, time
from pathlib import Path
from corpus import encode, parse_source, sha
from verify import check_model, check_unsat

def norm(c):
    s=set(c)
    return None if any(-l in s for l in s) else tuple(sorted(s))

def rup_support(cs, goal):
    # Independent naive propagation, with a dependency DAG for the conflict.
    a={abs(l): -l for l in goal}; why={}
    while True:
        change=False
        for i,c in enumerate(cs):
            if any(a.get(abs(l))==l for l in c): continue
            free=[l for l in c if abs(l) not in a]
            if not free:
                seen=set(); stack=[i]
                while stack:
                    j=stack.pop()
                    if j in seen: continue
                    seen.add(j)
                    for l in cs[j]:
                        if a.get(abs(l))==-l and abs(l) in why:
                            stack.append(why[abs(l)])
                return sorted(seen)
            if len(free)==1:
                l=free[0];a[abs(l)]=l;why[abs(l)]=i;change=True
        if not change:return None

def audit_macro(premises,steps):
    cs=list(premises)
    for c in steps:
        if rup_support(cs,c) is None: raise ValueError("non-RUP macro step")
        cs.append(c)
    n=max((abs(l) for c in cs for l in c),default=0)
    for bits in range(1<<n):
        sat=lambda c:any(bool(bits&(1<<(abs(l)-1)))==(l>0) for l in c)
        if all(map(sat,premises)) and not all(map(sat,steps)):
            raise ValueError("semantic macro audit failed")

def abstract(premises,steps):
    # Signed variable renaming: the original variable identities are discarded.
    mapping={}
    def rename(c):
        out=[]
        for l in c:
            v=abs(l)
            if v not in mapping:mapping[v]=(len(mapping)+1)*(1 if l>0 else -1)
            out.append(mapping[v]*(1 if l>0 else -1))
        return tuple(sorted(out))
    p=tuple(rename(c) for c in premises)
    s=tuple(rename(c) for c in steps)
    return p,s,len(mapping)

def extract(raw, proof, limit=350):
    n,original=parse_source(raw)
    cs=list(dict.fromkeys(c for x in original if (c:=norm(x)) is not None))
    source=len(cs);deps={};known=set(cs);out=[]
    if not proof.exists():return out
    data=proof.read_bytes()
    if data.startswith(b"{"):return out
    try:lines=data.decode("ascii").splitlines()
    except UnicodeDecodeError:return out
    for line in lines[:limit]:
        f=line.split()
        if not f or f[0] in ("d","c"):continue
        try:
            nums=list(map(int,f))
            if not nums or nums[-1]!=0 or any(x==0 or abs(x)>n for x in nums[:-1]):continue
            c=norm(nums[:-1])
        except ValueError:continue
        if c is None or c in known:continue
        if not c:break
        support=rup_support(cs,c)
        if support is None:continue # never learn from unverified proof additions
        i=len(cs);cs.append(c);known.add(c);deps[i]=support
        if len(c)>3:continue
        stack=[i];leaves=set();derived=set()
        while stack and len(leaves)<=8 and len(derived)<=6:
            j=stack.pop()
            if j<source:leaves.add(j)
            elif j not in derived:
                derived.add(j);stack.extend(deps[j])
        if stack or not 2<=len(leaves)<=8 or not 2<=len(derived)<=6:continue
        p,s,v=abstract([cs[j] for j in sorted(leaves)],[cs[j] for j in sorted(derived)])
        if v>8 or any(len(x)>4 for x in p):continue
        # Require connected support so the pattern is a local relation.
        reached={abs(l) for l in p[0]};left=list(p[1:])
        while left:
            hit=next((c for c in left if reached.intersection(map(abs,c))),None)
            if hit is None:break
            reached.update(map(abs,hit));left.remove(hit)
        if left:continue
        audit_macro(p,s);out.append((p,s))
    return out

def instantiate(c,m):
    return tuple(sorted(m[abs(l)]*(1 if l>0 else -1) for l in c))

def apply_memory(raw,memory,seconds=.55):
    n,original=parse_source(raw)
    cs=list(dict.fromkeys(c for x in original if (c:=norm(x)) is not None))
    known=set(cs);width=collections.defaultdict(list);occ=collections.defaultdict(list)
    def index(c):
        width[len(c)].append(c)
        for l in c:occ[l].append(c)
    for c in cs:index(c)
    deadline=time.monotonic()+seconds;prefix=[];hits=[];trials=0
    for item in memory:
        if time.monotonic()>=deadline or len(prefix)>=120:break
        p=tuple(map(tuple,item["premises"]));s=tuple(map(tuple,item["steps"]))
        # Bounded signed subgraph matching; no assignment search or solver calls.
        budget=[1800]; seen_maps=set()
        def walk(left,m,used):
            nonlocal trials
            if budget[0]<=0 or time.monotonic()>=deadline:return
            if not left:
                key=tuple(sorted(m.items()))
                if key not in seen_maps:
                    seen_maps.add(key);yield m
                return
            def candidates(c):
                shared=[m[abs(l)]*(1 if l>0 else -1) for l in c if abs(l) in m]
                if shared:
                    smallest=min(shared,key=lambda l:len(occ[l]))
                    return [d for d in occ[smallest] if len(d)==len(c) and all(l in d for l in shared)]
                return width[len(c)]
            # Prefer already mapped variables, then a small candidate population.
            anchor=min(left,key=lambda c:(-sum(abs(l) in m for l in c),len(candidates(c))))
            rest=list(left);rest.remove(anchor)
            for d in candidates(anchor):
                for permutation in itertools.permutations(d):
                    budget[0]-=1;trials+=1
                    if budget[0]<0 or time.monotonic()>=deadline:return
                    mm=dict(m);occupied=set(used);ok=True
                    for l,t in zip(anchor,permutation):
                        v=abs(l);mapped=t*(1 if l>0 else -1)
                        if v in mm:
                            if mm[v]!=mapped:ok=False;break
                        elif abs(mapped) in occupied:ok=False;break
                        else:mm[v]=mapped;occupied.add(abs(mapped))
                    if ok:yield from walk(rest,mm,occupied)
        count=0
        for m in walk(list(p),{},set()):
            if time.monotonic()>=deadline or len(prefix)>=120 or count>=12:break
            ip=[instantiate(c,m) for c in p];steps=[instantiate(c,m) for c in s]
            if steps[-1] in known:continue
            # Check the concrete instantiated proof against its exact premises.
            local=list(ip)
            for c in steps:
                if rup_support(local,c) is None:raise ValueError("instantiated proof invalid")
                local.append(c)
            if not all(c in known for c in ip):raise ValueError("missing matched premise")
            added=[]
            for c in steps:
                if c not in known:
                    known.add(c);prefix.append(c);index(c);added.append(c)
            hits.append(dict(rule=item["id"],source_families=item["families"],mapping=m,added=added))
            count+=1
    return prefix,hits,trials

def selftest():
    p=[(1,2),(-2,3),(-3,4)]
    s=[(1,3),(1,4)]
    p,s,v=abstract(p,s);audit_macro(p,s)
    item=dict(id="test",premises=p,steps=s,families=["control"])
    raw=encode(5,[[-5,2],[-2,-1],[1,4],[3]])
    prefix,hits,_=apply_memory(raw,[item],.5)
    if not hits or not prefix:raise ValueError("signed transfer control failed")
    n,orig=parse_source(raw);cs=list(map(norm,orig))
    for c in prefix:
        if rup_support(cs,c) is None:raise ValueError("full prefix rejected")
        cs.append(c)
    print("SELFTEST signed relabelled two-step macro OK",flush=True)

def dump(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True)+"\n")
def invoke(binpath,path,proof,seconds):
    if seconds<=.10:return "TIMEOUT","",0
    t=time.monotonic()
    try:
        x=subprocess.run([binpath,str(path),str(proof),str(max(.05,seconds-.09))],capture_output=True,timeout=seconds)
    except subprocess.TimeoutExpired:return "TIMEOUT","",time.monotonic()-t
    out=x.stdout.decode("ascii","replace")
    expected={10:"s SATISFIABLE",20:"s UNSATISFIABLE",0:"s UNKNOWN"}
    verdict={10:"SAT",20:"UNSAT",0:"UNKNOWN"}
    status=verdict.get(x.returncode,"ERROR") if expected.get(x.returncode) in out.splitlines() else "ERROR"
    return status,out,time.monotonic()-t

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--solver",type=Path,required=True);a.add_argument("--checker",type=Path,required=True)
    a.add_argument("--out",type=Path,required=True);a.add_argument("--freeze",required=True)
    a=a.parse_args();selftest()
    solver=str(a.solver.resolve());checker=str(a.checker.resolve())
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    root=a.out;root.mkdir(parents=True,exist_ok=False)
    for name in ("train","holdout"):
        subprocess.run([sys.executable,str(Path(__file__).with_name("unified_corpus.py")),str(root/name),sha((a.freeze+"|"+name).encode())[:40]],check=True)
    train=[c for c in json.loads((root/"train/manifest.json").read_text())["cases"] if c["family"] in ("random3","circuit","mixed")]
    hold=[c for c in json.loads((root/"holdout/manifest.json").read_text())["cases"] if c["family"] in ("tseitin","colour","random3")]
    assert not set(c["cnf_sha256"] for c in train)&set(c["cnf_sha256"] for c in hold)
    dump(root/"selection.json",dict(train=train,holdout=hold,freeze=a.freeze))
    catalog={};training=[]
    for c in train:
        path=root/"train"/(c["id"]+".cnf");proof=path.with_suffix(".proof")
        raw=path.read_bytes();assert sha(raw)==c["cnf_sha256"]
        status,out,elapsed=invoke(solver,path,proof,3.0)
        path.with_suffix(".out").write_text(out)
        if status=="SAT":check_model(raw,out)
        elif status=="UNSAT":check_unsat(path,proof,checker)
        elif status=="ERROR":raise ValueError("training solver error")
        # Even partial traces may contain independently valid reusable deductions.
        macros=extract(raw,proof)
        for p,s in macros:
            z=catalog.setdefault((p,s),{"families":set(),"sources":set()})
            z["families"].add(c["family"]);z["sources"].add(c["id"])
        training.append(dict(id=c["id"],family=c["family"],status=status,elapsed=elapsed,extracted=len(macros)))
        print("U5_TRAIN",json.dumps(training[-1]),flush=True)
    ranked=sorted(catalog.items(),key=lambda x:(-len(x[1]["families"]),-len(x[1]["sources"]),-len(x[0][1]),len(x[0][0]),x[0]))[:120]
    memory=[dict(id=sha(json.dumps([p,s]).encode())[:16],premises=p,steps=s,families=sorted(z["families"]),sources=sorted(z["sources"])) for (p,s),z in ranked]
    dump(root/"training.json",training);dump(root/"memory.json",memory)
    memhash=sha((root/"memory.json").read_bytes());print("U5_MEMORY",len(memory),memhash,flush=True)
    # Freeze memory before evaluation. No feedback from held-out cases.
    results=[];cap=5.0
    for i,c in enumerate(hold):
        orig=root/"holdout"/(c["id"]+".cnf");raw=orig.read_bytes();assert sha(raw)==c["cnf_sha256"]
        n,original=parse_source(raw)
        for mode in (("base","memory") if i%2==0 else ("memory","base")):
            d=root/"evidence"/c["id"]/mode;d.mkdir(parents=True)
            start=time.monotonic();prefix=[];hits=[];trials=0
            if mode=="memory":prefix,hits,trials=apply_memory(raw,memory)
            prefix_s=time.monotonic()-start
            p=d/"input.cnf";p.write_bytes(encode(n,original+prefix) if prefix else raw)
            proof=d/"solver.proof";status,out,_=invoke(solver,p,proof,cap-(time.monotonic()-start))
            elapsed=time.monotonic()-start
            (d/"solver.out").write_text(out);dump(d/"matches.json",hits)
            (d/"prefix.drup").write_bytes(encode(n,prefix).split(b"\n",1)[1])
            # Independently validate the entire learned prefix against original CNF.
            active=[norm(q) for q in original];active=[q for q in active if q is not None]
            for q in prefix:
                if rup_support(active,q) is None:raise ValueError("independent prefix audit rejected")
                active.append(q)
            verified=""
            if elapsed>cap:status="TIMEOUT"
            if status=="SAT":verified=check_model(raw,out)
            elif status=="UNSAT":
                verified=check_unsat(p,proof,checker)
                if prefix and verified=="DRAT":
                    combined=d/"combined.drat"
                    combined.write_bytes((d/"prefix.drup").read_bytes()+proof.read_bytes())
                    verified=check_unsat(orig,combined,checker)
                elif prefix:verified="RUP_PREFIX+"+verified
            elif status=="ERROR":raise ValueError("evaluation solver error")
            row=dict(id=c["id"],family=c["family"],mode=mode,status=status,verified=verified,
                     elapsed=elapsed,prefix_s=prefix_s,added=len(prefix),hits=len(hits),trials=trials,
                     cross_family_hits=sum(c["family"] not in h["source_families"] for h in hits),
                     memory_sha256=memhash,source_sha256=c["cnf_sha256"])
            results.append(row);print("U5_ROW",json.dumps(row),flush=True)
            dump(root/"results.json",results)
        pair=results[-2:]
        if {r["status"] for r in pair}=={"SAT","UNSAT"}:raise ValueError("contradictory accepted results")
    summary={}
    for family in ("all","tseitin","colour","random3"):
        rr=[r for r in results if family=="all" or r["family"]==family]
        pairs=collections.defaultdict(dict)
        for r in rr:pairs[r["id"]][r["mode"]]=r
        solved=lambda r:r["status"] in ("SAT","UNSAT")
        summary[family]=dict(cases=len(pairs),base=sum(solved(p["base"]) for p in pairs.values()),
          memory=sum(solved(p["memory"]) for p in pairs.values()),
          gains=[i for i,p in pairs.items() if solved(p["memory"]) and not solved(p["base"])],
          regressions=[i for i,p in pairs.items() if solved(p["base"]) and not solved(p["memory"])],
          matched=sum(p["memory"]["hits"]>0 for p in pairs.values()),
          cross_family_matched=sum(p["memory"]["cross_family_hits"]>0 for p in pairs.values()),
          base_par2=sum(p["base"]["elapsed"] if solved(p["base"]) else cap*2 for p in pairs.values())/len(pairs),
          memory_par2=sum(p["memory"]["elapsed"] if solved(p["memory"]) else cap*2 for p in pairs.values())/len(pairs))
    dump(root/"summary.json",summary);print("U5_SUMMARY",json.dumps(summary),flush=True)
if __name__=="__main__":main()
