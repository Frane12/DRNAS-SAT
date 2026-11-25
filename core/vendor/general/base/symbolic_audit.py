"""Independent semantic replay: no solver DAG or claimed outcome trusted.
The witness is an elimination permutation. Reconstruct exact Boolean factors
from the original CNF, eliminate with a separate Python ROBDD implementation.
This is NOT a DRAT/LRAT proof. Exhausting auditor budget rejects the certificate.
"""
import functools,time
class AuditLimit(Exception):pass

def verify_symbolic(n,cs,cert,seconds=12,max_nodes=1500000):
 lines=cert.read_text().splitlines();assert len(lines)==2 and lines[0]=='symbolic-elimination-v1'
 xs=list(map(int,lines[1].split()));assert xs[-1]==0;order=xs[:-1];assert len(order)==n and set(order)==set(range(1,n+1))
 rank={v:i for i,v in enumerate(order)}; nodes=[(n,0,0),(n,1,1)]; unique={};deadline=time.monotonic()+seconds;calls=0
 def guard():
  if len(nodes)>=max_nodes or time.monotonic()>deadline:raise AuditLimit('symbolic replay exceeded budget')
 def mk(v,l,h):
  if l==h:return l
  k=(v,l,h);z=unique.get(k)
  if z is None:
   z=len(nodes);nodes.append(k);unique[k]=z
   if z%1024==0:guard()
  return z
 @functools.lru_cache(maxsize=400000)
 def conj(a,b):
  nonlocal calls
  calls+=1
  if calls%4096==0:guard()
  if not a or not b:return 0
  if a==1 or a==b:return b
  if b==1:return a
  x,l,h=nodes[a];y,m,k=nodes[b];v=min(x,y)
  return mk(v,conj(*(sorted((l if x==v else a,m if y==v else b)))),conj(*(sorted((h if x==v else a,k if y==v else b)))))
 @functools.lru_cache(maxsize=400000)
 def neg(a):
  if a<2:return 1-a
  v,l,h=nodes[a];return mk(v,neg(l),neg(h))
 # Build clauses by Shannon restriction from source, not native node IDs.
 buckets=[[] for _ in order]
 try:
  for c in cs:
   c=set(c)
   if not c:return True
   if any(-x in c for x in c):continue
   f=0
   for l in sorted(c,key=lambda l:rank[abs(l)],reverse=True):f=mk(rank[abs(l)],f,1) if l>0 else mk(rank[abs(l)],1,f)
   if f>1:buckets[nodes[f][0]].append(f)
  for v,fs in enumerate(buckets):
   guard()
   if not fs:continue
   fs=list(dict.fromkeys(fs));conj.cache_clear()
   while len(fs)>1:
    nxt=[]
    for i in range(0,len(fs),2):
     z=conj(*sorted((fs[i],fs[i+1]))) if i+1<len(fs) else fs[i]
     if z==0:return True
     nxt.append(z)
    fs=nxt
   f=fs[0]
   if f>1 and nodes[f][0]==v:
    _,l,h=nodes[f];f=neg(conj(*sorted((neg(l),neg(h)))))
   if not f:return True
   if f>1:
    k=nodes[f][0];assert k>v;buckets[k].append(f)
  return False
 finally:
  conj.cache_clear();neg.cache_clear()
