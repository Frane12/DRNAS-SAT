"""YM32: independent audit of exact group-word elimination and flat witnesses."""
from fractions import Fraction as Q
from pathlib import Path
from collections import Counter
import hashlib,json

I=(Q(1),Q(0),Q(0),Q(0))
def mul(a,b):
    s,x,y,z=a;t,u,v,w=b
    return (s*t-x*u-y*v-z*w,s*u+t*x+y*w-z*v,s*v+t*y+z*u-x*w,s*w+t*z+x*v-y*u)
def inv(a):return (a[0],-a[1],-a[2],-a[3])
def prod(word,values):
    x=I
    for l in word:x=mul(x,values[abs(l)] if l>0 else inv(values[-l]))
    return x
def reduce_word(w):
    a=[]
    for l in w:
        if a and a[-1]==-l:a.pop()
        else:a.append(l)
    return a
def inverse_word(w):return [-l for l in reversed(w)]
def read(source):
    raw=Path(source).read_bytes();s=json.loads(raw);n=s['n']
    if type(n)!=int or not 2<=n<=256:raise ValueError('n')
    edges=[tuple(e) for e in s['edges']]
    if len(set(edges))!=len(edges) or any(len(e)!=2 or any(type(i)!=int for i in e) or not 0<=e[0]<e[1]<n for e in edges):raise ValueError('edges')
    faces=s['faces']
    if any(len(w)<3 or len(set(w))!=len(w) or any(type(i)!=int or not 0<=i<n for i in w) for w in faces):raise ValueError('face')
    eset=set(edges)
    if any(tuple(sorted((a,b))) not in eset for w in faces for a,b in zip(w,w[1:]+w[:1])):raise ValueError('boundary')
    return raw,n,edges,faces

def words(n,edges,faces,tree):
    if len(tree)!=n-1 or len(set(tree))!=n-1 or not set(tree)<=set(edges):raise ValueError('tree')
    adj=[[] for _ in range(n)]
    for a,b in tree:adj[a].append(b);adj[b].append(a)
    seen={0};queue=[0]
    for v in queue:
        for u in adj[v]:
            if u not in seen:seen.add(u);queue.append(u)
    if len(seen)!=n:raise ValueError('tree disconnected')
    chords=sorted(set(edges)-set(tree));idx={e:i+1 for i,e in enumerate(chords)}
    rel=[]
    for face in faces:
        row=[]
        for a,b in zip(face,face[1:]+face[:1]):
            e=tuple(sorted((a,b)))
            if e in idx:row.append(idx[e] if a<b else -idx[e])
        rel.append(reduce_word(row))
    return chords,rel

def eliminate(rel,g,at):
    if type(g)!=int or g<=0 or type(at)!=int or not 0<=at<len(rel):raise ValueError('step')
    w=rel[at];pos=[i for i,l in enumerate(w) if abs(l)==g]
    if len(pos)!=1:raise ValueError('not solvable')
    i=pos[0]
    # A g^eps B=1 -> g^eps=A^-1 B^-1.
    rhs=inverse_word(w[:i])+inverse_word(w[i+1:])
    if w[i]<0:rhs=inverse_word(rhs)
    rhs=reduce_word(rhs)
    out=[]
    for j,word in enumerate(rel):
        if j==at:continue
        v=[]
        for l in word:v.extend(rhs if l==g else inverse_word(rhs) if l==-g else [l])
        out.append(reduce_word(v))
    if sum(map(len,out))>200000:raise ValueError('word budget')
    return out,rhs

def rank(a,n):
    a=[list(map(Q,r)) for r in a];k=0
    for j in range(n):
        p=next((i for i in range(k,len(a)) if a[i][j]),None)
        if p is None:continue
        a[k],a[p]=a[p],a[k];v=a[k][j];a[k]=[x/v for x in a[k]]
        for i in range(k+1,len(a)):
            if a[i][j]:
                t=a[i][j];a[i]=[x-t*y for x,y in zip(a[i],a[k])]
        k+=1
        if k==len(a):break
    return k
def adj(q):
    cols=[mul(mul(q,tuple(Q(int(i==j)) for i in range(4))),inv(q))[1:] for j in (1,2,3)]
    return list(map(list,zip(*cols)))
def tangent(rel,values):
    # Left perturbation g -> exp(eps X)g; inverse letter contributes
    # -Ad(g^-1)X, transported by the prefix. At a flat relator this
    # is its exact differential at the identity.
    m=len(values);rows=[]
    for w in rel:
        a=[[Q(0)]*(3*m) for _ in range(3)];prefix=I
        for l in w:
            g=values[abs(l)];step=g if l>0 else inv(g)
            rot=adj(prefix if l>0 else mul(prefix,step))
            for i in range(3):
                for j in range(3):a[i][3*(abs(l)-1)+j]+=(1 if l>0 else -1)*rot[i][j]
            prefix=mul(prefix,step)
        if prefix!=I:raise ValueError('nonflat')
        rows.extend(a)
    orbit=[]
    for g in values.values():
        r=adj(g);orbit.extend([[Q(int(i==j))-r[i][j] for j in range(3)] for i in range(3)])
    r=rank(rows,3*m);o=rank(orbit,3)
    if r+o>3*m:raise ValueError('tangent rank')
    return dict(curvature_rank=r,gauge_orbit_rank=o,linearized_quotient_dimension=3*m-r-o)

def verify(source,cert):
    raw,n,edges,faces=read(source);c=json.loads(Path(cert).read_text())
    if c['sha256']!=hashlib.sha256(raw).hexdigest():raise ValueError('binding')
    chords,original=words(n,edges,faces,[tuple(e) for e in c['tree']])
    rel=original;remaining=set(range(1,len(chords)+1));history=[]
    for g,at in c['steps']:
        if g not in remaining:raise ValueError('reused generator')
        rel,rhs=eliminate(rel,g,at);remaining.remove(g);history.append((g,rhs))
    if c['remaining']!=sorted(remaining) or c['relators']!=rel:raise ValueError('residual')
    zero=tangent(original,{i:I for i in range(1,len(chords)+1)})
    result=dict(generators=len(chords),eliminated=len(history),remaining=len(remaining),
                identity_tangent=zero,continuum=False,quantum_gap_proved=False)
    if c['kind']=='TRIVIAL':
        if remaining:raise ValueError('not trivial')
        return dict(result,status='FLAT_TRIVIAL',all_flat_pure_gauge=True)
    if c['kind']=='WITNESS':
        v={int(i):tuple(map(Q,z)) for i,z in c['values'].items()}
        if set(v)!=set(range(1,len(chords)+1)) or any(len(z)!=4 or sum(t*t for t in z)!=1 for z in v.values()):raise ValueError('quaternion')
        if any(prod(w,v)!=I for w in original):raise ValueError('original curvature')
        g=c['loop_generator']
        if g not in v or v[g]==I:raise ValueError('trivial loop')
        return dict(result,status='NONTRIVIAL_FLAT',all_flat_pure_gauge=False,
                    nontrivial_wilson_trace=str(2*v[g][0]),witness_tangent=tangent(original,v))
    if c['kind']!='UNKNOWN':raise ValueError('kind')
    return dict(result,status='UNKNOWN')
