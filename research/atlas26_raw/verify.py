"""Independent replay using REAL6.3 Shannon ITE BDD, not detector binary apply."""
import itertools,hashlib,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'apps/circuitcheck'))
from real6_3_verify import IteBDD

def verify(raw,r):
    assert hashlib.sha256(raw).hexdigest()==r['sha256']
    n=None;cs=[];cur=[]
    for line in raw.decode().splitlines():
        line=line.strip()
        if not line or line[0]=='c':continue
        if line[0]=='p':
            assert n is None
            _,typ,a,m=line.split();assert typ=='cnf';n=int(a);m=int(m)
        else:
            for l in map(int,line.split()):
                if l:cur.append(l)
                else:cs.append(cur);cur=[]
    assert not cur and n==r['variables'] and m==len(cs)==r['clauses']
    if r['status']=='UNKNOWN':return 'UNKNOWN'
    if r['status']=='SAT':
        a={int(k):v for k,v in r['model'].items()}
        assert set(a)==set(range(1,n+1)) and all(v in (0,1) for v in a.values())
        assert all(any(a[abs(l)]==int(l>0) for l in c) for c in cs)
        return 'SAT_MODEL_VERIFIED'
    assert r['status']=='UNSAT'
    roots=r['roots'];assert len(set(roots))==len(roots) and all(1<=x<=n for x in roots)
    b=IteBDD({},roots);b.limit=300000
    values={v:b.wire(v) for v in roots}
    used=set()
    for g in r['plan']:
        o=g['out'];ins=g['ins'];t=g['table'];ids=g['clauses']
        assert o not in values and 1<=o<=n and len(ins)<=3 and len(set(ins))==len(ins) and all(x in values for x in ins)
        assert ids and len(set(ids))==len(ids) and all(0<=i<len(cs) and i not in used for i in ids)
        scope=set(ins+[o])
        assert all(set(map(abs,cs[i]))<=scope for i in ids)
        for inp in itertools.product((0,1),repeat=len(ins)):
            ix=sum(x*2**j for j,x in enumerate(inp))
            for z in (0,1):
                a=dict(zip(ins,inp));a[o]=z
                sat=all(any(a[abs(l)]==(l>0) for l in cs[i]) for i in ids)
                assert sat==(z==((t>>ix)&1))
        # Independently construct truth function by Shannon decomposition of input list.
        def f(j,ix):
            if j==len(ins):return (t>>ix)&1
            return b.ite(values[ins[j]],f(j+1,ix+2**j),f(j+1,ix))
        values[o]=f(0,0);used.update(ids)
    assert set(values)==set(range(1,n+1))
    prop=1
    for i in r['residual']:
        assert 0<=i<len(cs) and i not in used
        c=0
        for l in cs[i]:c=b.OR(c,values[abs(l)] if l>0 else b.NOT(values[abs(l)]))
        prop=b.AND(prop,c);used.add(i)
        if prop==0:return 'UNSAT_INDEPENDENT_ITE_BDD_VERIFIED'
    raise AssertionError('no verified contradiction')
