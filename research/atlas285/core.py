"""ATLAS28.5: exact residual diagnostics and bounded adaptive Davis-Putnam.
Every new clause is a resolvent of active clauses; proof is DRUP.
No branching, CDCL or solver fallback. Original input kept unchanged.
"""
import sys,time,json,collections,itertools,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'atlas281_cuts'))
from cuts import E,RUP
def index(active):
    ix=collections.defaultdict(set)
    for c in active:
        for l in c:ix[l].add(c)
    return ix
def metrics(active):
    ix=index(active);vs=set(map(abs,ix));w=collections.Counter(map(len,active))
    groups=collections.defaultdict(set)
    for c in active:groups[tuple(sorted(map(abs,c)))].add(tuple(sorted(l for l in c if l<0)))
    parity=collections.Counter()
    for sc,rows in groups.items():
        if 2<=len(sc)<=16 and len(rows)==2**(len(sc)-1) and len({len(r)%2 for r in rows})==1:parity[len(sc)]+=1
    best=sorted((len(ix[v])*len(ix[-v]),len(ix[v])+len(ix[-v]),v) for v in vs)
    return dict(variables=len(vs),clauses=len(active),widths=dict(sorted(w.items())),parity_scopes=dict(parity),min_pivot=best[0] if best else None,top_pivots=best[:8])
def write_cnf(path,active,n):
    path.write_text(f'p cnf {n} {len(active)}\n'+''.join(' '.join(map(str,sorted(c)))+' 0\n' for c in sorted(active,key=lambda c:(len(c),sorted(c)))))
def resolve(ix,v,paircap,widthcap,deadline):
    p,q=ix[v],ix[-v]
    if len(p)*len(q)>paircap:return None,'pair_cap'
    new=set()
    for a in p:
        if time.monotonic()>deadline:return None,'time_cap'
        for b in q:
            c=(a-{v})|(b-{-v})
            if any(-l in c for l in c):continue
            if len(c)>widthcap:return None,'width_cap'
            new.add(c)
    return new,None
def prune(clauses):
    # Exact subsumption. A stronger clause makes supersets redundant.
    ix=collections.defaultdict(set);accepted=set()
    for c in sorted(clauses,key=lambda c:(len(c),sorted(c))):
        if frozenset() in accepted:return {frozenset()}
        if any(d<=c for l in c for d in ix[l]):continue
        accepted.add(c)
        for l in c:ix[l].add(c)
    return accepted
def run(raw,out,cap=60):
    t=time.monotonic();deadline=t+cap;n,cs=E.g.parse(raw)
    active={frozenset(c) for c in cs if not any(-l in c for l in c)}
    known=set(active);proof=[];projected=0;phase2=0
    def apply(v,res,ix):
        nonlocal active,projected
        for c in sorted(res,key=lambda c:(len(c),sorted(c))):
            if c not in known:proof.append(c);known.add(c)
        active=(active-ix[v]-ix[-v])|res;projected+=1
    def finish(status,reason,core):
        if status=='UNSAT' and (not proof or proof[-1]):proof.append(frozenset())
        (out/'proof.drup').write_text(''.join(' '.join(map(str,sorted(c)))+' 0\n' for c in proof))
        write_cnf(out/'final.cnf',active,n)
        return dict(status=status,reason=reason,initial_variables=n,initial_clauses=len(cs),core=core,final=metrics(active),projected=projected,adaptive_projected=phase2,proof_steps=len(proof),seconds=time.monotonic()-t)
    reason='none'
    while active and frozenset() not in active:
        ix=index(active);vs=set(map(abs,ix))
        v=min(vs,key=lambda v:(len(ix[v])*len(ix[-v]),len(ix[v])+len(ix[-v]),v))
        res,reason=resolve(ix,v,3000,12,deadline)
        if res is None:break
        apply(v,res,ix)
    core=metrics(active);core.update(stop_reason=reason,projected=projected,seconds=time.monotonic()-t)
    write_cnf(out/'core.cnf',active,n)
    print('ATLAS285_CORE',json.dumps(core),flush=True)
    if frozenset() in active:return finish('UNSAT','empty_before_adaptive',core)
    # Width limit is not a theorem; try alternatives and exact subsumption.
    active=prune(active)
    while active and time.monotonic()<deadline and len(proof)<120000:
        if frozenset() in active:return finish('UNSAT','empty_after_adaptive',core)
        ix=index(active);vs=set(map(abs,ix))
        ranking=sorted(vs,key=lambda v:(len(ix[v])*len(ix[-v]),len(ix[v])+len(ix[-v]),v))
        candidates=[]
        for v in ranking[:12]:
            res,why=resolve(ix,v,12000,24,deadline)
            if res is None:continue
            # remove redundant resolvents against all surviving clauses.
            remain=active-ix[v]-ix[-v]
            rr=prune(remain|res)-remain
            candidates.append((len(rr)-len(ix[v])-len(ix[-v]),max(map(len,rr),default=0),v,rr))
            if time.monotonic()>=deadline:break
        if not candidates:reason='adaptive_no_pivot';break
        _,_,v,rr=min(candidates,key=lambda x:x[:3])
        apply(v,rr,ix);phase2+=1;active=prune(active)
        if len(active)>40000:reason='active_clause_cap';break
        if phase2%5==0:print('ATLAS285_PROGRESS',json.dumps(dict(step=phase2,clauses=len(active),variables=len({abs(l) for c in active for l in c}))),flush=True)
    if frozenset() in active:return finish('UNSAT','empty_after_adaptive',core)
    return finish('UNKNOWN','time_cap' if time.monotonic()>=deadline else reason,core)
if __name__=='__main__':
    root=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True);seen=set();rows=[]
    for p in sorted(root.rglob('*.cnf')):
        raw=p.read_bytes();h=hashlib.sha256(raw).hexdigest()
        if h in seen:continue
        seen.add(h);d=out/h[:12];d.mkdir(exist_ok=True);(d/'original.cnf').write_bytes(raw)
        r=run(raw,d);r.update(sha=h,file=str(p));rows.append(r)
        (d/'summary.json').write_text(json.dumps(r,indent=2))
        print('ATLAS285_ROW',json.dumps(r),flush=True)
    (out/'summary.json').write_text(json.dumps(rows,indent=2))
