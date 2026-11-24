"""ATLAS28.6: raw core -> exact parity rows -> affine substitution into nonlinear relations.
No CDCL. BDD proof of reduced conjunction is independently replayed with ITE.
Bounded symbolic search, not a polynomial-time claim.
"""
import sys,time,json,itertools,collections,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'atlas27_integrated'))
import engine as E
def extract(cs):
    groups=collections.defaultdict(list)
    for i,c in enumerate(cs):
        if not any(-l in c for l in c):groups[tuple(sorted(set(map(abs,c))))].append((i,c))
    rows=[];used=set()
    for sc,items in sorted(groups.items()):
        k=len(sc)
        if not 1<=k<=16:continue
        # A clause forbids the assignment where precisely its negative literals are 1.
        masks={sum(1<<j for j,v in enumerate(sc) if -v in c) for _,c in items}
        for b in (0,1):
            bad={i for i in range(1<<k) if i.bit_count()%2!=b}
            if bad<=masks:
                ids=[i for i,c in items if sum(1<<j for j,v in enumerate(sc) if -v in c) in bad]
                rows.append((sc,b,ids));used.update(ids)
    return rows,[i for i in range(len(cs)) if i not in used]
def basis(rows,order):
    # choose a pivot in the requested deterministic order; eliminate above and below.
    pos={v:i for i,v in enumerate(order)};B={}
    for sc,b,ids in rows:
        s=set(sc)
        while s:
            p=min(s,key=pos.get)
            if p not in B:B[p]=(s,b);break
            t,c=B[p];s^=t;b^=c
        else:
            if b:return B,True
    for p in sorted(B,key=pos.get,reverse=True):
        s,b=B[p]
        for q in list(B):
            if q!=p and p in B[q][0]:
                t,c=B[q];B[q]=(t^s,c^b)
    return B,False
def run(raw,cap=60):
    start=time.monotonic();n,cs=E.g.parse(raw);vs=sorted({abs(l) for c in cs for l in c})
    rows,res=extract(cs)
    counts=collections.Counter(abs(l) for i in res for l in cs[i])
    order=sorted(vs,key=lambda v:(counts[v],v))
    B,contradiction=basis(rows,order)
    roots=[v for v in vs if v not in B]
    out=dict(sha256=hashlib.sha256(raw).hexdigest(),variables=len(vs),clauses=len(cs),xor_rows=len(rows),xor_clauses=len(cs)-len(res),rank=len(B),free_variables=len(roots),nonlinear_clauses=len(res),rows=[dict(scope=s,rhs=b,ids=ids) for s,b,ids in rows],basis={str(p):dict(scope=sorted(s),rhs=b) for p,(s,b) in B.items()},roots=roots,residual=res)
    if contradiction:return dict(out,status='UNSAT',reason='affine_inconsistent',seconds=time.monotonic()-start)
    # For each residual clause, substitute the exact affine expression for every variable.
    # Incremental canonical conjunction, capped; try both natural and occurrence order.
    attempts=[]
    for root_order in (roots,sorted(roots,key=lambda v:(-counts[v],v))):
        if time.monotonic()-start>=cap:break
        try:
            E.g.CAP=300000
            b=E.g.BDD(root_order);V={v:b.variable(v) for v in root_order}
            for p,(s,rhs) in B.items():
                q=rhs
                for v in sorted(s-{p}):q=b.op(6,q,V[v])
                V[p]=q
            prop=1;processed=0
            for i in sorted(res,key=lambda i:(len(cs[i]),i)):
                if time.monotonic()-start>=cap:raise E.g.Limit('time_cap')
                q=0
                for l in cs[i]:q=b.OR(q,V[abs(l)] if l>0 else b.NOT(V[abs(l)]))
                prop=b.AND(prop,q);processed+=1
                if not prop:return dict(out,status='UNSAT',reason='affine_nonlinear_bdd',bdd_order=root_order,processed=processed,bdd_nodes=len(b.nodes),seconds=time.monotonic()-start,attempts=attempts)
            a=b.witness(prop,root_order)
            for p,(s,rhs) in B.items():a[p]=rhs^ (sum(a[v] for v in s-{p})%2)
            assert all(any(a[abs(l)]==(l>0) for l in c) for c in cs)
            return dict(out,status='SAT_CORE',model=a,bdd_order=root_order,processed=processed,bdd_nodes=len(b.nodes),seconds=time.monotonic()-start,attempts=attempts)
        except (E.g.Limit,RecursionError) as ex:attempts.append(dict(reason=str(ex),processed=locals().get('processed',0),nodes=len(b.nodes)))
    return dict(out,status='UNKNOWN',attempts=attempts,seconds=time.monotonic()-start)
if __name__=='__main__':
    root=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
    for p in sorted(root.rglob('core.cnf')):
        raw=p.read_bytes();r=run(raw);(out/(p.parent.name+'.json')).write_text(json.dumps(r))
        print('ATLAS286',json.dumps({k:v for k,v in r.items() if k not in ('rows','basis','roots','residual','model','bdd_order')}),flush=True)
