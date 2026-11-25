"""ATLAS38: factorized existential projection and explicit capacity ablation.
No external solver, CDCL or branching search. Original input only.
"""
import sys,time,json,collections,hashlib,heapq
from pathlib import Path
import sparse_state as S
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'atlas288'))
import solve as old
class Limit(Exception):pass
class BDD:
 def __init__(self,order,deadline,node_cap=350000,op_cap=1500000):
  self.order=order;self.rank={v:i for i,v in enumerate(order)};self.nodes=[None,None];self.unique={};self.cache={};self.ops=0;self.deadline=deadline;self.node_cap=node_cap;self.op_cap=op_cap;self.weights=[1,1]
 def mk(self,v,l,h):
  if l==h:return l
  k=(v,l,h)
  if k not in self.unique:
   if len(self.nodes)>=self.node_cap:raise Limit('nodes')
   self.unique[k]=len(self.nodes);self.nodes.append(k);self.weights.append(min(10**12,1+self.weights[l]+self.weights[h]))
  return self.unique[k]
 def app(self,op,a,b):
  if a>b:a,b=b,a
  if a==b:return a
  if op==0:
   if a==0:return 0
   if a==1:return b
  else:
   if a==0:return b
   if a==1:return 1
  k=(op,a,b)
  if k in self.cache:return self.cache[k]
  self.ops+=1
  if self.ops>self.op_cap or (self.ops%512==0 and time.monotonic()>self.deadline):raise Limit('operations_or_time')
  x,l,h=self.nodes[a];y,p,q=self.nodes[b]
  if self.rank[x]<self.rank[y]:v=x;p=q=b
  elif self.rank[y]<self.rank[x]:v=y;l=h=a
  else:v=x
  z=self.mk(v,self.app(op,l,p),self.app(op,h,q));self.cache[k]=z;return z
 def clause(self,c):
  if any(-l in c for l in c):return 1
  a=0
  for l in sorted(set(c),key=lambda l:self.rank[abs(l)],reverse=True):
   a=self.mk(abs(l),a,1) if l>0 else self.mk(abs(l),1,a)
  return a
 def evaluate(self,a,m):
  while a>1:
   v,l,h=self.nodes[a];a=h if m.get(v,0) else l
  return a
def minfill(cs,vs,deadline):
 g={v:set() for v in vs}
 for c in cs:
  sc=set(map(abs,c))
  for v in sc:g[v].update(sc-{v})
 order=[]
 while g:
  if time.monotonic()>deadline:raise Limit('ordering_time')
  v=min(g,key=lambda x:(sum(1 for a in g[x] for b in g[x] if a<b and b not in g[a]),len(g[x]),x))
  ns=g.pop(v);order.append(v)
  for u in ns:g[u].discard(v);g[u].update(ns-{u})
 return order
def components(cs):
 by=collections.defaultdict(list)
 for i,c in enumerate(cs):
  for v in set(map(abs,c)):by[v].append(i)
 seen=set()
 for i in range(len(cs)):
  if i in seen:continue
  stack=[i];seen.add(i);group=[];vs=set()
  while stack:
   j=stack.pop();c=cs[j];group.append(c)
   for v in set(map(abs,c))-vs:
    vs.add(v)
    for k in by[v]:
     if k not in seen:seen.add(k);stack.append(k)
  yield group,sorted(vs)
def symbolic(cs,vs,deadline,mode='FUSED'):
 if len(vs)>180:return dict(status='UNKNOWN',reason='bdd_variable_cap')
 b=None
 try:
  order=minfill(cs,vs,deadline);wide=mode in ('WIDE','FUSED_WIDE');fused=mode in ('FUSED','FUSED_WIDE')
  b=BDD(order,deadline,1200000 if wide else 350000,5000000 if wide else 1500000);buckets={v:[] for v in order};history=[]
  def join(factors):
   roots=set(factors)
   if 0 in roots:return 0
   roots.discard(1)
   heap=[(b.weights[u],u) for u in roots];heapq.heapify(heap)
   while len(heap)>1:
    _,x=heapq.heappop(heap);_,y=heapq.heappop(heap)
    z=b.app(0,x,y)
    if not z:return 0
    heapq.heappush(heap,(b.weights[z],z))
   return heap[0][1] if heap else 1
  def push(a):
   if a>1:buckets[b.nodes[a][0]].append(a)
   return a!=0
  for c in cs:
   if not push(b.clause(c)):return dict(status='UNSAT',order=order,nodes=len(b.nodes))
  for v in order:
   if time.monotonic()>deadline:raise Limit('time')
   factors=tuple(sorted(set(buckets[v])))
   if fused:
    # Existential projection distributes over the two cofactors of the bucket.
    # Never materialize the full conjunction containing the eliminated variable.
    lo=[];hi=[]
    for u in factors:
     if u>1 and b.nodes[u][0]==v:
      _,l,h=b.nodes[u];lo.append(l);hi.append(h)
     else:lo.append(u);hi.append(u)
    l=join(lo)
    h=1 if l==1 else join(hi)
    a=b.app(1,l,h)
    # Retain original factors, not the huge intermediate conjunction.
    history.append((v,factors))
   else:
    a=1
    for u in factors:
     a=b.app(0,a,u)
     if not a:break
    history.append((v,(a,)))
    if a>1 and b.nodes[a][0]==v:
     _,l,h=b.nodes[a];a=b.app(1,l,h)
   if not push(a):return dict(status='UNSAT',order=order,nodes=len(b.nodes),ops=b.ops)
  m={}
  for v,factors in reversed(history):
   m[v]=0
   if not all(b.evaluate(u,m) for u in factors):m[v]=1
   if not all(b.evaluate(u,m) for u in factors):raise AssertionError('BDD reverse lift')
  return dict(status='SAT',model=m,nodes=len(b.nodes))
 except (Limit,RecursionError) as e:return dict(status='UNKNOWN',reason=str(e),nodes=len(b.nodes) if b else 0,ops=b.ops if b else 0)
def write_cnf(p,n,cs):
 p.write_text(f'p cnf {n} {len(cs)}\n'+''.join(' '.join(map(str,c))+' 0\n' for c in cs))
def solve(raw,out,mode,cap):
 t=time.monotonic();deadline=t+cap;n,cs=S.M.parse(raw);out.mkdir(parents=True,exist_ok=True)
 # Ablation: restart BDD at original; HANDOFF uses exact residual and reconstruction.
 d=out/'sparse';d.mkdir()
 r=S.solve(raw,d,True,max(.01,cap*.45),handoff=True,policy='EARLY')
 route=dict(sparse=r,mode=mode);base=dict(status=r['status'],route=route)
 if r['status'] in ('SAT','UNSAT'):
  import shutil
  name='model.json' if r['status']=='SAT' else 'proof.drup'
  shutil.copy(d/name,out/name)
  return dict(base,method='sparse',decision_s=time.monotonic()-t)
 if (d/'residual.json').exists():
  state=json.loads((d/'residual.json').read_text());res=state['active'];history=state['history']
 else:res=cs;history=[]
 route.update(residual_clauses=len(res),residual_vars=len({abs(l) for c in res for l in c}),eliminated=len(history),components=[])
 model={}
 for comp,vs in sorted(components(res),key=lambda x:len(x[1])):
  if time.monotonic()>deadline:return dict(base,method='time_cap',decision_s=time.monotonic()-t)
  z=symbolic(comp,vs,deadline,mode)
  route['components'].append({k:v for k,v in z.items() if k not in ('model','order')})
  if z['status']=='UNKNOWN':return dict(base,method=z['reason'],decision_s=time.monotonic()-t)
  if z['status']=='UNSAT':
   # Checkable residual subset, prefix source consequences and independent BDD order.
   write_cnf(out/'core.cnf',n,comp)
   prefix=(d/'proof.drup').read_text() if history else ''
   (out/'prefix.drup').write_text(prefix)
   (out/'bdd.json').write_text(json.dumps(dict(order=z['order'],source_sha=hashlib.sha256(raw).hexdigest())))
   return dict(base,status='UNSAT',method='bdd',decision_s=time.monotonic()-t)
  model.update(z['model'])
 for v,removed in reversed(history):
  model[v]=0
  if not all(any(model.get(abs(l),0)==int(l>0) for l in c) for c in removed):model[v]=1
  if not all(any(model.get(abs(l),0)==int(l>0) for l in c) for c in removed):raise AssertionError('sparse reverse lift')
 for v in range(1,n+1):model.setdefault(v,0)
 if not all(any(model[abs(l)]==int(l>0) for l in c) for c in cs):raise AssertionError('original witness')
 (out/'model.json').write_text(json.dumps(model))
 return dict(base,status='SAT',method='bdd_lift',decision_s=time.monotonic()-t)
def check_bdd(raw,out,deadline):
 from verify import IteBDD
 core=(out/'core.cnf').read_bytes()
 old.provenance(raw,core,(out/'prefix.drup').read_bytes())
 cert=json.loads((out/'bdd.json').read_text())
 if cert['source_sha']!=hashlib.sha256(raw).hexdigest():return False
 _,cs=S.M.parse(core);order=cert['order']
 if set(order)!={abs(l) for c in cs for l in c} or len(order)!=len(set(order)):return False
 b=IteBDD({},order);b.limit=1800000;V={v:b.wire(v) for v in order};buckets={v:[] for v in order}
 def push(a):
  if a>1:buckets[order[b.nodes[a][0]]].append(a)
  return a!=0
 for c in cs:
  a=0
  for l in c:a=b.OR(a,V[abs(l)] if l>0 else b.NOT(V[abs(l)]))
  if not push(a):return True
 for v in order:
  if time.monotonic()>deadline:return False
  a=1
  for u in sorted(set(buckets[v])):
   a=b.AND(a,u)
   if not a:break
  if a>1:
   k,l,h=b.nodes[a]
   if order[k]==v:a=b.OR(l,h)
  if not push(a):return True
 return False
if __name__=='__main__':
 p=Path(sys.argv[1]);out=Path(sys.argv[2]);r=solve(p.read_bytes(),out,sys.argv[3],float(sys.argv[4]));(out/'result.json').write_text(json.dumps(r));print(json.dumps(r))
