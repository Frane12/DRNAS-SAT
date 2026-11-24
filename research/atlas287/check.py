"""Independent ITE-BDD replay of exact partition elimination certificates."""
import sys,json,hashlib,collections
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'atlas286'))
from verify import verify_core,provenance,parse,IteBDD
def replay(raw,r):
    affine=dict(r,status='UNKNOWN')
    if r['reason']=='affine_inconsistent':
        return verify_core(raw,dict(r,status='UNSAT'))
    verify_core(raw,affine)
    if r['status']=='UNKNOWN':return 'AFFINE_BASIS_VERIFIED_NO_FINAL_PROOF'
    cs=parse(raw);roots=set(r['roots']);order=r['order']
    assert len(order)==len(roots) and set(order)==roots
    b=IteBDD({},order);b.limit=1500000
    V={v:b.wire(v) for v in roots}
    for p,x in r['basis'].items():
        p=int(p);q=x['rhs']
        for v in x['scope']:
            if v!=p:q=b.XOR(q,V[v])
        V[p]=q
    F={}
    for i in r['residual']:
        q=0
        for l in cs[i]:q=b.OR(q,V[abs(l)] if l>0 else b.NOT(V[abs(l)]))
        if q==0:
            assert r['status']=='UNSAT';return 'INDEPENDENT_PARTITION_UNSAT'
        if q!=1:F[i]=q
    supports={0:set(),1:set()}
    def support(x):
        if x not in supports:
            rank,l,h=b.nodes[x];supports[x]=support(l)|support(h)|{order[rank]}
        return supports[x]
    def quantify(x,v,memo):
        if x<2:return x
        if x in memo:return memo[x]
        k,l,h=b.nodes[x]
        if order[k]==v:y=b.OR(l,h)
        else:y=b.reduce(k,quantify(l,v,memo),quantify(h,v,memo))
        memo[x]=y;return y
    for event in r['trace']:
        v=event['var'];ids=event['parents'];new=event['id']
        assert len(ids)==len(set(ids)) and set(ids)=={i for i,x in F.items() if v in support(x)}
        assert new not in F and new>=len(cs)
        q=1
        for i in ids:q=b.AND(q,F[i])
        q=quantify(q,v,{})
        for i in ids:del F[i]
        if q==0:
            assert r['status']=='UNSAT';return 'INDEPENDENT_PARTITION_UNSAT'
        if q!=1:F[new]=q
    assert r['status']=='SAT_CORE_ONLY' and not F
    return 'INDEPENDENT_CORE_SAT_PROJECTION_ONLY'
if __name__=='__main__':
    root=Path(sys.argv[1]);out=Path(sys.argv[2])
    for p in sorted(root.rglob('core.cnf')):
        raw=p.read_bytes()
        steps=provenance((p.parent/'original.cnf').read_bytes(),raw,(p.parent/'proof.drup').read_bytes())
        for a in (0,1):
            f=out/(p.parent.name+'_'+str(a)+'.json');r=json.loads(f.read_text())
            t=__import__('time').monotonic()
            r['audit']=replay(raw,r);r['provenance_steps']=steps;r['replay_s']=__import__('time').monotonic()-t
            f.write_text(json.dumps(r))
            print('ATLAS287_AUDIT',json.dumps({k:v for k,v in r.items() if k not in ('rows','basis','roots','residual','order','trace')}),flush=True)
