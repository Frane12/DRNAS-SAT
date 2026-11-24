"""Independent replay of affine certificates and original-to-core RUP provenance."""
import sys,itertools,collections,hashlib,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'apps/circuitcheck'))
from real6_3_verify import IteBDD
def parse(raw):
    clauses=[];pending=[];n=None
    for line in raw.decode().splitlines():
        line=line.strip()
        if not line or line[0]=='c':continue
        if line[0]=='p':
            _,typ,n,m=line.split();n=int(n);m=int(m);assert typ=='cnf';continue
        for l in map(int,line.split()):
            if l:pending.append(l)
            else:clauses.append(tuple(pending));pending=[]
    assert not pending and n is not None and len(clauses)==m
    return clauses
def verify_core(raw,r):
    assert hashlib.sha256(raw).hexdigest()==r['sha256']
    cs=parse(raw);used=set();orig=[]
    for row in r['rows']:
        sc=row['scope'];rhs=row['rhs'];ids=row['ids']
        assert sc==sorted(set(sc)) and rhs in (0,1)
        assert all(0<=i<len(cs) and set(map(abs,cs[i]))==set(sc) for i in ids)
        forbidden={tuple(int(-v in cs[i]) for v in sc) for i in ids}
        assert forbidden=={b for b in itertools.product((0,1),repeat=len(sc)) if sum(b)%2!=rhs}
        orig.append((set(sc),rhs));used.update(ids)
    assert sorted(set(range(len(cs)))-used)==r['residual']
    # Independent row-space equality using bit-packed elimination in numeric order.
    def reduce(rows):
        piv={}
        for sc,b in rows:
            x=sum(1<<v for v in sc)|b
            while x>1:
                p=x.bit_length()-1
                if p not in piv:piv[p]=x;break
                x^=piv[p]
            else:
                if x:return None
        for p in sorted(piv):
            for q in sorted(piv):
                if q>p and (piv[q]>>p)&1:piv[q]^=piv[p]
        return piv
    a=reduce(orig)
    if a is None:
        assert r['status']=='UNSAT' and r['reason']=='affine_inconsistent';return 'AFFINE_CONTRADICTION_VERIFIED'
    B={int(p):(set(x['scope']),x['rhs']) for p,x in r['basis'].items()}
    assert reduce(B.values())==a and len(B)==len(a)
    roots=set(r['roots']);vs={abs(l) for c in cs for l in c}
    assert roots|set(B)==vs and not roots&set(B)
    assert all(p in sc and sc-{p}<=roots for p,(sc,b) in B.items())
    if r['status']=='UNKNOWN':return 'AFFINE_ROWS_AND_BASIS_VERIFIED'
    if r['status']=='SAT_CORE':
        model={int(k):v for k,v in r['model'].items()}
        assert all(any(model[abs(l)]==(l>0) for l in c) for c in cs)
        return 'CORE_SAT_ONLY'
    assert r['status']=='UNSAT'
    b=IteBDD({},r['bdd_order']);b.limit=600000
    V={v:b.wire(v) for v in roots}
    for p,(sc,rhs) in B.items():
        q=rhs
        for v in sorted(sc-{p}):q=b.XOR(q,V[v])
        V[p]=q
    prop=1
    for i in sorted(r['residual'],key=lambda i:(len(cs[i]),i)):
        q=0
        for l in cs[i]:q=b.OR(q,V[abs(l)] if l>0 else b.NOT(V[abs(l)]))
        prop=b.AND(prop,q)
        if not prop:return 'CORE_UNSAT_INDEPENDENT_ITE_VERIFIED'
    raise AssertionError('no contradiction')

def provenance(original,core,proof):
    # Independently check each RUP step until all core clauses are justified.
    cs=[];idx=collections.defaultdict(list);units=[];known=set()
    def add(c):
        c=frozenset(c);j=len(cs);cs.append(c);known.add(c)
        if len(c)==1:units.append(next(iter(c)))
        for l in c:idx[l].append(j)
    for c in parse(original):add(c)
    need=set(map(frozenset,parse(core)))-known
    def rup(c):
        a=set();q=collections.deque()
        def assign(l):
            if -l in a:return False
            if l not in a:a.add(l);q.append(l)
            return True
        for l in itertools.chain(units,(-l for l in c)):
            if not assign(l):return True
        if frozenset() in known:return True
        while q:
            l=q.popleft()
            for j in idx[-l]:
                d=cs[j]
                if d&a:continue
                rest=[x for x in d if -x not in a]
                if not rest:return True
                if len(rest)==1 and not assign(rest[0]):return True
        return False
    steps=0
    for line in proof.decode().splitlines():
        if not need:break
        c=frozenset(int(l) for l in line.split() if int(l))
        assert rup(c),('non RUP',steps)
        add(c);need.discard(c);steps+=1
    assert not need,('unproved core',len(need))
    return steps

if __name__=='__main__':
    root=Path(sys.argv[1]);out=Path(sys.argv[2])
    for p in sorted(root.rglob('core.cnf')):
        r=json.loads((out/(p.parent.name+'.json')).read_text())
        audit=verify_core(p.read_bytes(),r)
        steps=provenance((p.parent/'original.cnf').read_bytes(),p.read_bytes(),(p.parent/'proof.drup').read_bytes())
        r.update(audit=audit,original_to_core_rup_steps=steps)
        (out/(p.parent.name+'.json')).write_text(json.dumps(r))
        print('ATLAS286_AUDIT',json.dumps({k:v for k,v in r.items() if k not in ('rows','basis','roots','residual','model','bdd_order')}),flush=True)
