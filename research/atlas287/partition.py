"""ATLAS28.7: partitioned BDD elimination with bounded live symbolic state.
Each bucket existentially projects one variable only after collecting every
factor containing it. No global conjunction, CDCL, or unbounded search.
"""
import sys,time,json,collections,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'atlas286'))
import affine as A
E=A.E
class Budget(Exception):pass

class Manager:
    def __init__(self,order,limit=500000):
        self.order=order;self.rank={v:i for i,v in enumerate(order)}
        self.b=E.g.BDD(order);E.g.CAP=limit
        self.limit=limit;self.qcache={};self.scache={0:frozenset(),1:frozenset()}
    def support(self,x):
        if x not in self.scache:
            r,l,h=self.b.nodes[x]
            self.scache[x]=self.support(l)|self.support(h)|{self.order[r]}
        return self.scache[x]
    def exists(self,x,v):
        if x<2:return x
        key=(x,v)
        if key in self.qcache:return self.qcache[key]
        r,l,h=self.b.nodes[x];target=self.rank[v]
        if r>target:return x
        if r==target:y=self.b.OR(l,h)
        else:y=self.b.mk(r,self.exists(l,v),self.exists(h,v))
        self.qcache[key]=y;return y
    def compact(self,factors):
        old=self.b;new=E.g.BDD(self.order);cache={0:0,1:1}
        def copy(x):
            if x not in cache:
                r,l,h=old.nodes[x];cache[x]=new.mk(r,copy(l),copy(h))
            return cache[x]
        result={i:copy(x) for i,x in factors.items()}
        self.b=new;self.qcache={};self.scache={0:frozenset(),1:frozenset()}
        return result

def minfill(scopes,variables):
    adj={v:set() for v in variables}
    for sc in scopes:
        for v in sc:adj[v].update(set(sc)-{v})
    order=[]
    while adj:
        v=min(adj,key=lambda x:(sum(1 for a in adj[x] for b in adj[x] if a<b and b not in adj[a]),len(adj[x]),x))
        ns=adj.pop(v);order.append(v)
        for u in ns:adj[u].discard(v);adj[u].update(ns-{u})
    return order

def setup(raw,affine):
    n,cs=E.g.parse(raw);vs=sorted({abs(l) for c in cs for l in c})
    rows,res=A.extract(cs) if affine else ([],list(range(len(cs))))
    counts=collections.Counter(abs(l) for i in res for l in cs[i])
    B,contr=A.basis(rows,sorted(vs,key=lambda v:(counts[v],v)))
    roots=[v for v in vs if v not in B]
    scopes=[set().union(*(B[abs(l)][0]-{abs(l)} if abs(l) in B else {abs(l)} for l in cs[i])) for i in res]
    return cs,rows,res,B,roots,contr,scopes

def solve(raw,affine,limit=500000,cap=25):
    t=time.monotonic();deadline=t+cap
    cs,rows,res,B,roots,contr,scopes=setup(raw,affine)
    base=dict(sha256=hashlib.sha256(raw).hexdigest(),affine=affine,rank=len(B),free=len(roots),initial_factors=len(res),rows=[dict(scope=list(s),rhs=b,ids=ids) for s,b,ids in rows],basis={str(p):dict(scope=sorted(s),rhs=b) for p,(s,b) in B.items()},roots=roots,residual=res)
    if contr:return dict(base,status='UNSAT',reason='affine_inconsistent',seconds=time.monotonic()-t)
    order=minfill(scopes,roots)
    M=Manager(list(reversed(order)),limit);F={};trace=[];peak=0;max_width=0;next_id=len(cs);reason='none'
    def finish(status,reason):
        return dict(base,status=status,reason=reason,order=M.order,trace=trace,peak_nodes=max(peak,len(M.b.nodes)),max_bucket_support=max_width,remaining_factors=len(F),remaining_variables=len(set().union(*(M.support(x) for x in F.values()))),seconds=time.monotonic()-t)
    try:
        V={v:M.b.variable(v) for v in roots}
        for p,(s,rhs) in B.items():
            q=rhs
            for v in sorted(s-{p}):q=M.b.op(6,q,V[v])
            V[p]=q
        for i in res:
            q=0
            for l in cs[i]:q=M.b.OR(q,V[abs(l)] if l>0 else M.b.NOT(V[abs(l)]))
            if q==0:return dict(finish('UNSAT','false_initial_factor'),false_id=i)
            if q!=1:F[i]=q
        peak=max(peak,len(M.b.nodes))
        F=M.compact(F)
        for v in order:
            if time.monotonic()>deadline:raise Budget('time_cap')
            ids=sorted(i for i,x in F.items() if v in M.support(x))
            if not ids:continue
            scope=set().union(*(M.support(F[i]) for i in ids))
            max_width=max(max_width,len(scope))
            # Greedy small-factor conjunction, existentially project immediately.
            ids.sort(key=lambda i:(len(M.support(F[i])),i))
            q=1
            for i in ids:
                if time.monotonic()>deadline:raise Budget('time_cap')
                q=M.b.AND(q,F[i])
                if not q:break
            q=M.exists(q,v)
            trace.append(dict(var=v,parents=ids,id=next_id,scope_before=len(scope),scope_after=len(M.support(q)),constant=q if q<2 else None))
            for i in ids:del F[i]
            if q!=1:F[next_id]=q
            next_id+=1
            peak=max(peak,len(M.b.nodes))
            if not q:return finish('UNSAT','partition_contradiction')
            F=M.compact(F)
        # A true projection proves core satisfiability only, not original SAT witness.
        return finish('SAT_CORE_ONLY','all_projected')
    except (Budget,E.g.Limit,RecursionError) as ex:
        return finish('UNKNOWN',str(ex))

if __name__=='__main__':
    root=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
    for p in sorted(root.rglob('core.cnf')):
        raw=p.read_bytes()
        for a in (False,True):
            r=solve(raw,a)
            (out/(p.parent.name+'_'+str(int(a))+'.json')).write_text(json.dumps(r))
            print('ATLAS287',json.dumps({k:v for k,v in r.items() if k not in ('rows','basis','roots','residual','order','trace')},sort_keys=True),flush=True)
