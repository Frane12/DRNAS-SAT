"""ATLAS30 random CNF: indexed exact Davis-Putnam + bounded alternative pivots.
No CDCL, case metadata, learned policy, or external solving backend.
"""
import sys,time,json,heapq,collections,hashlib,random
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'atlas288'))
import solve as old
C=old.C
def profile(cs,n):
    widths=collections.Counter(map(len,cs))
    occ=collections.Counter(abs(l) for c in cs for l in c)
    signs=collections.Counter(l for c in cs for l in c)
    scopes=collections.Counter(tuple(sorted(map(abs,c))) for c in cs)
    # Descriptive features, NOT a proof that the generating process was random.
    return dict(n=n,m=len(cs),density=len(cs)/max(1,n),widths=dict(widths),
                mean_degree=sum(occ.values())/max(1,n),max_degree=max(occ.values(),default=0),
                repeated_scopes=sum(v-1 for v in scopes.values()),
                sign_imbalance=sum(abs(signs[v]-signs[-v]) for v in occ)/max(1,sum(occ.values())))
def solve(raw,out,adaptive=True,cap=30):
    t=time.monotonic();deadline=t+cap;n,cs=C.E.g.parse(raw)
    active={frozenset(c) for c in cs if not any(-l in c for l in c)}
    features=profile(cs,n);known=set(active);proof=[];history=[]
    ix=C.index(active);heap=[]
    def score(v):return (len(ix[v])*len(ix[-v]),len(ix[v])+len(ix[-v]),v)
    for v in set(map(abs,ix)):heapq.heappush(heap,score(v))
    reason='complete';alternate=0;peak=len(active)
    while active and frozenset() not in active:
        if time.monotonic()>=deadline:reason='time_cap';break
        if len(active)>80000 or len(proof)>150000:reason='memory_guard';break
        opts=[];seen=set();chosen=None;why='no_pivot'
        while heap and len(opts)<(8 if adaptive else 1):
            item=heapq.heappop(heap);v=item[2]
            if v in seen or item!=score(v) or item[1]==0:continue
            opts.append(item);seen.add(v)
        for j,item in enumerate(opts):
            if time.monotonic()>=deadline:why='time_cap';break
            v=item[2];res,why=C.resolve(ix,v,3000,12,deadline)
            if res is not None:
                chosen=(v,res);alternate+=int(j>0);break
        for item in opts:heapq.heappush(heap,item)
        if chosen is None:reason=why or 'no_pivot';break
        v,res=chosen;removed=ix[v]|ix[-v]
        history.append((v,removed));changed=set()
        for c in removed:
            active.remove(c)
            for l in c:ix[l].remove(c);changed.add(abs(l))
        for c in sorted(res,key=lambda q:(len(q),sorted(q))):
            if c not in known:proof.append(c);known.add(c)
            if c not in active:
                active.add(c)
                for l in c:ix[l].add(c);changed.add(abs(l))
        for x in changed:
            if ix[x] or ix[-x]:heapq.heappush(heap,score(x))
        if len(heap)>max(10000,8*len(ix)):
            heap=[score(x) for x in set(map(abs,ix)) if ix[x] or ix[-x]];heapq.heapify(heap)
        peak=max(peak,len(active))
    out.mkdir(parents=True,exist_ok=True)
    C.write_cnf(out/'core.cnf',active,n)
    def writeproof(): (out/'projection.drup').write_text(''.join(' '.join(map(str,sorted(c)))+' 0\n' for c in proof))
    writeproof()
    projection_s=time.monotonic()-t
    base=dict(features=features,projected=len(history),alternate_pivots=alternate,peak_clauses=peak,projection_s=projection_s,projection_stop=reason,core_variables=len({abs(l) for c in active for l in c}),core_clauses=len(active))
    if frozenset() in active:
        if not proof or proof[-1]:proof.append(frozenset());writeproof()
        return dict(base,status='UNSAT',audit='DRUP_PENDING_EXTERNAL',route='DP',solve_s=time.monotonic()-t)
    if not active:
        a={}
        for v,removed in reversed(history):
            for b in (0,1):
                a[v]=b
                if all(any(a.get(abs(l),0)==int(l>0) for l in c) for c in removed):break
            else:raise AssertionError('model lift')
        for v in range(1,n+1):a.setdefault(v,0)
        (out/'model.json').write_text(json.dumps(a))
        return dict(base,status='SAT',audit='MODEL_PENDING_EXTERNAL',route='DP',solve_s=time.monotonic()-t)
    # Existing symbolic core, no branching on Boolean assignments and no solver fallback.
    if time.monotonic()<deadline and base['core_variables']<=220:
        core=(out/'core.cnf').read_bytes()
        p=old.P.solve(core,True,cap=max(0,deadline-time.monotonic()))
        (out/'partition.json').write_text(json.dumps(p))
        if p['status']=='UNSAT':
            return dict(base,status='UNSAT',audit='COMPOSITE_PENDING_EXTERNAL',route='BDD',solve_s=time.monotonic()-t)
        base.update(bdd_reason=p['reason'],bdd_peak=p.get('peak_nodes'))
    return dict(base,status='UNKNOWN',audit='NO_FINAL_PROOF',route='NONE',solve_s=time.monotonic()-t)
if __name__=='__main__':
    raw=Path(sys.argv[1]).read_bytes();out=Path(sys.argv[2])
    r=solve(raw,out,bool(int(sys.argv[3])),float(sys.argv[4]))
    (out/'result.json').write_text(json.dumps(r))
