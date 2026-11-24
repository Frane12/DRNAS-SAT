"""Raw DIMACS-only gate reconstruction and symbolic equivalence.
Orientation is a heuristic, not an assertion of original circuit direction.
Every accepted outcome is independently replayed against original clauses.
"""
import itertools as I, hashlib, json, collections, time, sys
from pathlib import Path
from functools import lru_cache
from collections import defaultdict
CAP=180000
class Limit(Exception):pass
def parse(raw):
    n=None; cs=[]; cur=[]
    for line in raw.decode().splitlines():
        if not line.strip() or line.lstrip().startswith('c'):continue
        if line.lstrip().startswith('p'):
            _,typ,n,m=line.split();n=int(n);m=int(m)
            if typ!='cnf':raise ValueError('header')
        else:
            for x in map(int,line.split()):
                if x:cur.append(x)
                else:cs.append(cur);cur=[]
    if n is None or cur or len(cs)!=m or any(abs(x)>n for c in cs for x in c):raise ValueError('DIMACS')
    return n,cs

def discover(cs):
    groups=defaultdict(list)
    for i,c in enumerate(cs):
        if any(-x in c for x in c):continue
        groups[tuple(sorted(set(map(abs,c))))].append(i)
    candidates=[]; residual=[]
    for sc,ids in groups.items():
        if len(sc) not in (2,3,4):
            residual.extend(ids);continue
        rows=[dict(zip(sc,b)) for b in I.product((0,1),repeat=len(sc))
              if all(any(dict(zip(sc,b))[abs(l)]==(l>0) for l in cs[i]) for i in ids)]
        choices={}
        for z in sc:
            ins=tuple(x for x in sc if x!=z); table={}
            for a in rows:
                key=tuple(a[x] for x in ins)
                if key in table and table[key]!=a[z]:break
                table[key]=a[z]
            else:
                if len(table)==2**len(ins):
                    choices[z]=(ins,sum(v<<sum(b<<j for j,b in enumerate(k)) for k,v in table.items()))
        if choices:candidates.append((sc,ids,choices))
        else:residual.extend(ids)
    return candidates,residual

def make_plan(candidates,residual,cs,n,mode):
    fixed={};pending=[];occupied=set()
    for sc,ids,opts in candidates:
        if len(opts)==1:
            z=next(iter(opts))
            if z in occupied:return None
            occupied.add(z);fixed[z]=(opts[z],ids)
        else:pending.append((sc,ids,opts))
    occurrence=collections.Counter(v for sc,_,_ in candidates for v in sc)
    targets=set(abs(v) for i in residual for v in cs[i] if len(cs[i])!=2)
    pairs=collections.Counter(tuple(ins) for (ins,t),_ in fixed.values() if len(ins)==2)
    # Target leaves, and shared input pairs of independently identified non-linear gates.
    while pending:
        options=[]
        for j,(sc,ids,opts) in enumerate(pending):
            poss=[z for z in opts if z not in occupied]
            if not poss:return None
            def score(z):
                ins,_=opts[z]
                if mode=='numeric':return (z,)
                return (int(z in targets and occurrence[z]==1),
                        int(pairs[ins]>0),pairs[ins],
                        int(occurrence[z]==1),-occurrence[z],z)
            ranking=sorted(poss,key=score,reverse=True)
            s=score(ranking[0])
            priority=(int(len(poss)==1),s[:-1] if mode!='numeric' else (),s[-1])
            options.append((priority,j,ranking[0]))
        _,j,z=max(options)
        sc,ids,opts=pending.pop(j);occupied.add(z);fixed[z]=(opts[z],ids)
    # A candidate orientation that cycles is discarded, not assumed true.
    roots=set(range(1,n+1))-set(fixed)
    known=set(roots); topo=[]; todo=dict(fixed)
    while todo:
        ready=sorted(z for z,((ins,t),ids) in todo.items() if set(ins)<=known)
        if not ready:return None
        for z in ready:
            (ins,t),ids=todo.pop(z);known.add(z);topo.append({'out':z,'ins':list(ins),'table':t,'clauses':ids})
    return topo,roots

def root_order(topo,roots):
    depth={v:0 for v in roots}; users=defaultdict(list)
    for g in topo:
        z=g['out'];ins=g['ins']
        depth[z]=1+max(depth[x] for x in ins)
        for x in ins:users[x].append(g)
    pairs=defaultdict(list)
    for g in topo:
        if len(g['ins'])==2 and set(g['ins'])<=roots:pairs[tuple(g['ins'])].append(g['out'])
    ranks=[]
    for p,outs in pairs.items():
        # Carry interaction gives an approximate significance rank.
        other=[depth[x] for z in outs for g in users[z] for x in g['ins'] if x!=z and depth[x]>0]
        ranks.append((min(other,default=0),-len(outs),p))
    order=[];used=set()
    for _,__,p in sorted(ranks):
        if not used.intersection(p):order.extend(p);used.update(p)
    return order+sorted(roots-used)

class BDD:
    def __init__(self,order):
        self.nodes=[None,None];self.unique={};self.cache={};self.order={v:i for i,v in enumerate(order)}
    def mk(self,v,a,b):
        if a==b:return a
        key=(v,a,b)
        if key not in self.unique:
            if len(self.nodes)>=CAP:raise Limit('bdd_cap')
            self.unique[key]=len(self.nodes);self.nodes.append(key)
        return self.unique[key]
    def variable(self,v):return self.mk(self.order[v],0,1)
    def op(self,t,a,b):
        if a<2 and b<2:return (t>>(a+2*b))&1
        key=(t,a,b)
        if key in self.cache:return self.cache[key]
        ra=self.nodes[a][0] if a>=2 else 10**9;rb=self.nodes[b][0] if b>=2 else 10**9
        r=min(ra,rb)
        aa=self.nodes[a][1:] if ra==r else (a,a);bb=self.nodes[b][1:] if rb==r else (b,b)
        z=self.mk(r,self.op(t,aa[0],bb[0]),self.op(t,aa[1],bb[1]))
        self.cache[key]=z;return z
    def AND(self,a,b):return self.op(8,a,b)
    def OR(self,a,b):return self.op(14,a,b)
    def NOT(self,a):return self.op(3,a,0) if False else self.op(5,a,0)
    def table(self,t,vals):
        # Sum of products over input truth table, canonical reduction.
        ans=0
        for i in range(1<<len(vals)):
            if not t>>i&1:continue
            q=1
            for j,v in enumerate(vals):
                q=self.AND(q,v if i>>j&1 else self.NOT(v))
            ans=self.OR(ans,q)
        return ans
    def witness(self,node,order):
        a={v:0 for v in order}
        while node>=2:
            r,lo,hi=self.nodes[node]
            if lo:node=lo
            else:a[order[r]]=1;node=hi
        if node!=1:raise ValueError('false root')
        return a

def solve(raw,modes=('numeric','structure')):
    n,cs=parse(raw);cand,res=discover(cs)
    base={'sha256':hashlib.sha256(raw).hexdigest(),'variables':n,'clauses':len(cs),'gate_candidates':len(cand),'residual_clauses':len(res)}
    attempts=[]
    for mode in modes:
        plan=make_plan(cand,res,cs,n,mode)
        if plan is None:attempts.append([mode,'no_dag']);continue
        topo,roots=plan; order=root_order(topo,roots)
        try:
            b=BDD(order); values={v:b.variable(v) for v in order}
            for g in topo:values[g['out']]=b.table(g['table'],[values[x] for x in g['ins']])
            prop=1; constant_zero=[];constant_one=[]
            for i in res:
                z=0
                for l in cs[i]:z=b.OR(z,values[abs(l)] if l>0 else b.NOT(values[abs(l)]))
                if not z:constant_zero.append(i)
                if z==1:constant_one.append(i)
                prop=b.AND(prop,z)
                if not prop:break
            out=dict(base,mode=mode,plan=topo,roots=order,residual=res,bdd_nodes=len(b.nodes),constant_false_clauses=constant_zero,constant_true_clauses=constant_one,attempts=attempts)
            if not prop:return dict(out,status='UNSAT')
            a=b.witness(prop,order)
            for g in topo:a[g['out']]=(g['table']>>sum(a[x]<<j for j,x in enumerate(g['ins'])))&1
            if all(any(a[abs(l)]==(l>0) for l in c) for c in cs):return dict(out,status='SAT',model=a)
            attempts.append([mode,'model_failed'])
        except (Limit,RecursionError) as e:attempts.append([mode,str(e)])
    return dict(base,status='UNKNOWN',attempts=attempts)
