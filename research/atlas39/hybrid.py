"""ATLAS39: source-only RUP closure and independent constructive witness search.
No CDCL, reference answers or conflict-driven branching. Repair is a SAT-only
heuristic; only a checked original model or a proof may decide the formula.
"""
import sys,time,json,hashlib,random,collections,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'atlas38'))
import autonomous as A

def propagate(cs,assumptions=()):
    values={}
    def put(l):
        v=abs(l);b=l>0
        if v in values:return values[v]==b
        values[v]=b;return True
    for l in assumptions:
        if not put(l):return None
    while True:
        changed=False
        for c in cs:
            free=[]
            for l in c:
                v=abs(l)
                if v not in values:free.append(l)
                elif values[v]==(l>0):break
            else:
                if not free:return None
                if len(free)==1:
                    if not put(free[0]):return None
                    changed=True
        if not changed:return values

def deduction(cs,n,deadline):
    active=list(dict.fromkeys(tuple(sorted(set(c))) for c in cs if not any(-l in c for l in c)))
    known=set(active);proof=[];checks=0
    def add(c):
        c=tuple(sorted(c))
        if c not in known:known.add(c);active.append(c);proof.append(c)
    pairs=collections.Counter()
    for c in active:
        vs=sorted(set(map(abs,c)))
        for i,v in enumerate(vs):
            for w in vs[i+1:]:pairs[v,w]+=1
    order=sorted(pairs,key=lambda p:(-pairs[p],p))
    for epoch in range(3):
        if time.monotonic()>deadline:break
        before=len(proof)
        if propagate(active) is None:
            add(());return active,proof,checks,True
        for v in range(1,n+1):
            for l in (v,-v):
                if time.monotonic()>deadline:break
                if (l,) in known:continue
                checks+=1
                if propagate(active,(-l,)) is None:add((l,))
            if time.monotonic()>deadline:break
        if propagate(active) is None:
            add(());return active,proof,checks,True
        for v,w in order[:min(len(order),400)]:
            if time.monotonic()>deadline or len(proof)>=600:break
            for l,k in ((v,w),(v,-w),(-v,w),(-v,-w)):
                c=tuple(sorted((l,k)))
                if c in known or (l,) in known or (k,) in known:continue
                checks+=1
                if propagate(active,(-l,-k)) is None:add(c)
                if time.monotonic()>deadline:break
        if propagate(active) is None:
            add(());return active,proof,checks,True
        if len(proof)==before:break
    return active,proof,checks,False

def repair(cs,n,deadline,seed):
    rng=random.Random(seed);steps=0
    if any(not c for c in cs):return None,steps
    forced=propagate(cs)
    if forced is None:return None,steps
    occurrences=collections.defaultdict(list)
    for i,c in enumerate(cs):
        for l in c:occurrences[abs(l)].append(i)
    for restart in range(32):
        if time.monotonic()>deadline:break
        m={v:bool(rng.getrandbits(1)) for v in range(1,n+1)};m.update(forced)
        counts=[sum(m[abs(l)]==(l>0) for l in c) for c in cs]
        bad={i for i,k in enumerate(counts) if not k}
        for _ in range(max(300,80*n)):
            if not bad:return m,steps
            if time.monotonic()>deadline:return None,steps
            i=rng.choice(sorted(bad));vs=sorted({abs(l) for l in cs[i]}-forced.keys())
            if not vs:break
            def score(v):
                gain=loss=0
                for j in occurrences[v]:
                    k=counts[j]
                    delta=sum(1 if m[v]!=(l>0) else -1 for l in cs[j] if abs(l)==v)
                    gain+=k==0 and k+delta>0
                    loss+=k>0 and k+delta==0
                return gain-loss
            if rng.random()<.20:v=rng.choice(vs)
            else:
                scores=[(score(v),v) for v in vs];best=max(s for s,v in scores)
                v=rng.choice([v for s,v in scores if s==best])
            m[v]=not m[v]
            for j in occurrences[v]:
                counts[j]=sum(m[abs(l)]==(l>0) for l in cs[j])
                if counts[j]:bad.discard(j)
                else:bad.add(j)
            steps+=1
    return None,steps

def proof_text(proof):
    return ''.join(' '.join(map(str,c))+' 0\n' for c in proof)
def solve(raw,out,mode,cap):
    t=time.monotonic();deadline=t+cap;n,cs=A.S.M.parse(raw);out.mkdir(parents=True,exist_ok=True)
    route={};active=cs;proof=[]
    if mode in ('DEDUCT','AUTO'):
        active,proof,checks,unsat=deduction(cs,n,min(deadline,t+cap*.28))
        route.update(rup_checks=checks,rup_clauses=len(proof),rup_units=sum(len(c)==1 for c in proof))
        (out/'deduction.drup').write_text(proof_text(proof))
        if unsat:
            (out/'proof.drup').write_text(proof_text(proof))
            return dict(status='UNSAT',method='rup_closure',route=route)
    if mode in ('REPAIR','AUTO'):
        m,steps=repair(active,n,min(deadline,time.monotonic()+cap*(1 if mode=='REPAIR' else .26)),int(hashlib.sha256(raw).hexdigest()[:16],16))
        route['repair_steps']=steps
        if m is not None:
            assert all(any(m[abs(l)]==(l>0) for l in c) for c in cs)
            (out/'model.json').write_text(json.dumps({v:int(b) for v,b in m.items()}))
            return dict(status='SAT',method='constructive_repair',route=route)
        if mode=='REPAIR':return dict(status='UNKNOWN',method='repair_exhausted',route=route)
    if time.monotonic()>=deadline:return dict(status='UNKNOWN',method='time_cap',route=route)
    d=out/'symbolic';d.mkdir()
    A.write_cnf(out/'augmented.cnf',n,active)
    aug=(out/'augmented.cnf').read_bytes()
    r=A.solve(aug,d,'FUSED_WIDE',max(.01,deadline-time.monotonic()))
    route['symbolic']=r
    if r['status']=='SAT':
        m={int(v):b for v,b in json.loads((d/'model.json').read_text()).items()}
        assert all(any(m[abs(l)]==int(l>0) for l in c) for c in cs)
        shutil.copy(d/'model.json',out/'model.json')
    elif r['status']=='UNSAT':
        if r['method']=='bdd':
            shutil.copy(d/'core.cnf',out/'core.cnf')
            (out/'prefix.drup').write_text(proof_text(proof)+(d/'prefix.drup').read_text())
            cert=json.loads((d/'bdd.json').read_text());cert['source_sha']=hashlib.sha256(raw).hexdigest()
            (out/'bdd.json').write_text(json.dumps(cert))
        else:
            (out/'proof.drup').write_text(proof_text(proof)+(d/'proof.drup').read_text())
    return dict(status=r['status'],method=r['method'],route=route)
if __name__=='__main__':
    p=Path(sys.argv[1]);d=Path(sys.argv[2]);r=solve(p.read_bytes(),d,sys.argv[3],float(sys.argv[4]));(d/'result.json').write_text(json.dumps(r));print(json.dumps(r))
