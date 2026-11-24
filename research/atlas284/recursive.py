import sys,time,collections,itertools
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'atlas281_cuts'))
from cuts import RUP,E
def solve(raw,cap=60,recursive=True):
 n,cs=E.g.parse(raw);p=RUP(cs);proof=[];known={frozenset(c) for c in cs};active={frozenset(c) for c in cs if not any(-l in c for l in c)};deadline=time.monotonic()+cap
 stats=dict(rounds=0,substitutions=0,projected=0)
 def emit(c):
  c=frozenset(c)
  if c in known:return True
  if time.monotonic()>=deadline or len(proof)>=100000:return False
  if not p.check([-l for l in c]):return False
  p.add(c);known.add(c);proof.append(sorted(c));return True
 while active and time.monotonic()<deadline:
  if emit([]):return 'UNSAT',proof,stats
  if recursive:
   stats['rounds']+=1
   # Detect certified binary equivalences and units in the current residual.
   parent={v:v for v in range(n+1)};pol={v:0 for v in parent}
   def find(x):
    if parent[x]==x:return x,0
    y,b=find(parent[x]);pol[x]^=b;parent[x]=y;return y,pol[x]
   def union(x,y,b):
    x,a=find(x);y,c=find(y)
    if x!=y:
     if x<y:x,y=y,x
     parent[x]=y;pol[x]=a^b^c
   for c in active:
    if len(c)==1:
     l=next(iter(c));union(abs(l),0,int(l>0))
    elif len(c)==2 and frozenset(-l for l in c) in active:
     a,b=sorted(c);union(abs(a),abs(b),int((a>0)==(b>0)))
   changed=sum(find(v)[0]!=v for v in set(abs(l) for c in active for l in c))
   if changed:
    new=set()
    for c in active:
     d=set();sat=False
     for l in c:
      v,b=find(abs(l));pos=(l>0)^bool(b)
      if v==0:
       if not pos:sat=True;break
      else:d.add(v if pos else -v)
     if sat or any(-l in d for l in d):continue
     if not emit(d):return 'UNKNOWN',proof,stats
     new.add(frozenset(d))
    active=new;stats['substitutions']+=changed
    if not active:break
  ix=collections.defaultdict(set)
  for c in active:
   for l in c:ix[l].add(c)
  vs=set(map(abs,ix))
  if not vs:break
  v=min(vs,key=lambda v:(len(ix[v])*len(ix[-v]),len(ix[v])+len(ix[-v]),v))
  pos,neg=ix[v],ix[-v]
  if len(pos)*len(neg)>3000:break
  res=set()
  for x in pos:
   for y in neg:
    c=(x-{v})|(y-{-v})
    if any(-l in c for l in c):continue
    if len(c)>12:return 'UNKNOWN',proof,stats
    res.add(c)
  for c in sorted(res,key=lambda c:(len(c),sorted(c))):
   if not emit(c):return 'UNKNOWN',proof,stats
   if not c:return 'UNSAT',proof,stats
  active-=pos|neg;active|=res;stats['projected']+=1
 return 'UNKNOWN',proof,stats
