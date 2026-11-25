"""Independent arithmetic audit of transverse oscillator form bounds."""
from fractions import Fraction as Q
from pathlib import Path
from collections import defaultdict
import hashlib,json

def read(source):
    raw=Path(source).read_bytes();s=json.loads(raw);n=s['n']
    if type(n)!=int or not 2<=n<=64 or len(s['kinetic'])!=n:raise ValueError('n')
    a=list(map(Q,s['kinetic']));w={}
    if min(a)<=0:raise ValueError('kinetic')
    for i,j,z in s['couplings']:
        if type(i)!=int or type(j)!=int or not 0<=i<j<n or (i,j) in w or Q(z)<=0:raise ValueError('coupling')
        w[i,j]=Q(z)
    return raw,n,a,w

def verify(source,cert):
    raw,n,a,w=read(source);c=json.loads(Path(cert).read_text())
    if c['sha256']!=hashlib.sha256(raw).hexdigest():raise ValueError('binding')
    if c['kind']=='FREE':
        i=c['vertex']
        if type(i)!=int or not 0<=i<n or any(i in e for e in w):raise ValueError('not free')
        return dict(status='FREE_COORDINATE',vertex=i,compact_resolvent=False,uniform_gap=False)
    if c['kind']!='COERCIVE':raise ValueError('kind')
    usedT=defaultdict(Q);usedV=defaultdict(Q);slope=defaultdict(Q)
    for i,j,t,v,k in c['allocations']:
        if type(i)!=int or type(j)!=int or not 0<=i<n or not 0<=j<n or i==j:raise ValueError('allocation index')
        e=tuple(sorted((i,j)));t,v,k=map(Q,(t,v,k))
        if e not in w or min(t,v,k)<=0 or k*k>4*t*v:raise ValueError('oscillator bound')
        usedT[j]+=t;usedV[e]+=v;slope[i]+=k
    if any(usedT[i]>a[i]/2 for i in range(n)) or any(usedV[e]>w[e] for e in w):raise ValueError('double counted energy')
    if min(slope[i] for i in range(n))<=0:raise ValueError('uncovered flat direction')
    if list(map(Q,c['slopes']))!=[slope[i] for i in range(n)]:raise ValueError('slopes')
    return dict(status='COERCIVE_PROVED',n=n,min_slope=str(min(slope.values())),slopes=c['slopes'],
                compact_resolvent=True,positive_finite_model_gap=True,uniform_gap=False,
                continuum=False,analytic_premise='two_dimensional_transverse_oscillator')
