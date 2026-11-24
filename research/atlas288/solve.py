"""ATLAS28.8 original CNF -> exact DP projection -> partitioned BDD.
SAT is returned only with an original-CNF witness. No CDCL fallback.
"""
import sys,time,json,hashlib,collections
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'atlas287'))
import partition as P
from check import replay,provenance
sys.path.insert(0,str(R/'atlas285'))
import core as C
def solve(raw,out,affine,cap=60):
    t=time.monotonic();deadline=t+cap
    n,cs=C.E.g.parse(raw)
    active={frozenset(c) for c in cs if not any(-l in c for l in c)}
    known=set(active);proof=[];history=[];reason='complete'
    while active and frozenset() not in active:
        ix=C.index(active);vs=set(map(abs,ix))
        v=min(vs,key=lambda v:(len(ix[v])*len(ix[-v]),len(ix[v])+len(ix[-v]),v))
        res,why=C.resolve(ix,v,3000,12,deadline)
        if res is None:reason=why;break
        removed=ix[v]|ix[-v]
        history.append((v,removed))
        for c in sorted(res,key=lambda c:(len(c),sorted(c))):
            if c not in known:proof.append(c);known.add(c)
        active=(active-removed)|res
    out.mkdir(parents=True,exist_ok=True)
    C.write_cnf(out/'core.cnf',active,n)
    (out/'projection.drup').write_text(''.join(' '.join(map(str,sorted(c)))+' 0\n' for c in proof))
    core=(out/'core.cnf').read_bytes()
    projection_s=time.monotonic()-t
    if not active:
        # Reconstruct DP-eliminated variables in reverse order.
        a={}
        for v,removed in reversed(history):
            for bit in (0,1):
                a[v]=bit
                if all(any(a.get(abs(l),0)==(l>0) for l in c) for c in removed):break
            else:raise AssertionError('witness reconstruction')
        for v in range(1,n+1):a.setdefault(v,0)
        assert all(any(a[abs(l)]==(l>0) for l in c) for c in cs)
        (out/'model.json').write_text(json.dumps(a))
        s=time.monotonic()-t
        # separate literal-by-literal replay of saved witness
        a=json.loads((out/'model.json').read_text())
        assert set(map(int,a))==set(range(1,n+1))
        assert all(sum(a[str(abs(l))]==int(l>0) for l in c)>0 for c in cs)
        return dict(status='SAT',audit='ORIGINAL_MODEL_VERIFIED',projection_s=projection_s,solve_s=s,e2e_s=time.monotonic()-t,projected=len(history))
    p=P.solve(core,affine,cap=max(0,deadline-time.monotonic()))
    (out/'partition.json').write_text(json.dumps(p))
    solve_s=time.monotonic()-t
    audit=replay(core,p)
    steps=provenance(raw,core,(out/'projection.drup').read_bytes())
    status=p['status'] if p['status'] in ('UNSAT','UNKNOWN') else 'UNKNOWN'
    return dict(status=status,audit=audit,projection_s=projection_s,partition_s=p['seconds'],solve_s=solve_s,e2e_s=time.monotonic()-t,projected=len(history),core_variables=len({abs(l) for c in active for l in c}),core_clauses=len(active),rank=p['rank'],peak_nodes=p.get('peak_nodes'),reason=p['reason'],projection_stop=reason,provenance_steps=steps)
if __name__=='__main__':
    f=Path(sys.argv[1]);out=Path(sys.argv[2]);r=solve(f.read_bytes(),out,bool(int(sys.argv[3])))
    (out/'result.json').write_text(json.dumps(r))
    print('ATLAS288_WORKER',json.dumps(r),flush=True)
