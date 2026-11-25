"""YM30 independent audit of sparse positive quadratic-form certificates."""
import json,hashlib
from pathlib import Path
from fractions import Fraction as Q
from collections import defaultdict

def read_matrix(source):
    raw=Path(source).read_bytes()
    if len(raw)>2_000_000:raise ValueError('input size')
    s=json.loads(raw);n=s['n'];target=Q(s['target'])
    if type(n)!=int or not 1<=n<=4096 or target<=0 or len(s['diagonal'])!=n:raise ValueError('matrix parameters')
    diag=list(map(Q,s['diagonal']));edges={}
    for i,j,z in s['off_diagonal']:
        if type(i)!=int or type(j)!=int or not 0<=i<j<n or (i,j) in edges:raise ValueError('edge')
        w=-Q(z)
        if w<=0:raise ValueError('outside supported sign class')
        edges[i,j]=w
        diag[i]-=w;diag[j]-=w
    if min(diag)<0:raise ValueError('negative row sum')
    return raw,n,target,edges,diag

def verify(source,cert):
    raw,n,g,edges,p=read_matrix(source)
    c=json.loads(Path(cert).read_text())
    if c['source_sha256']!=hashlib.sha256(raw).hexdigest():raise ValueError('source binding')
    if c['kind']=='LOWER':
        paths=c['paths']
        if len(paths)!=n:raise ValueError('path coverage')
        load=defaultdict(Q)
        for i,path in enumerate(paths):
            if not path or path[0]!=i or len(set(path))!=len(path) or any(type(j)!=int or not 0<=j<n for j in path):raise ValueError('path')
            root=path[-1]
            if p[root]<=0:raise ValueError('unanchored path')
            used=[tuple(sorted((a,b))) for a,b in zip(path,path[1:])]
            if any(e not in edges for e in used):raise ValueError('path edge')
            R=1/p[root]+sum(1/edges[e] for e in used)
            load[('pin',root)]+=R
            for a,b in used:load[('edge',a,b)]+=R
        K=max(load.values())
        if Q(c['bound'])!=1/K or 1/K<g:raise ValueError('lower bound')
        return dict(status='LOWER_PROVED',lambda_lower=str(1/K),target=str(g),n=n,max_path=max(map(len,paths))-1)
    if c['kind']=='UPPER':
        v=list(map(Q,c['vector']))
        if len(v)!=n or not any(v):raise ValueError('witness')
        # Independent original-matrix Rayleigh form, not the solver's
        # path energy expression.
        s=json.loads(raw);den=sum(x*x for x in v)
        num=sum(Q(x)*y*y for x,y in zip(s['diagonal'],v))
        num+=2*sum(Q(z)*v[i]*v[j] for i,j,z in s['off_diagonal'])
        upper=num/den
        if Q(c['bound'])!=upper or upper>=g:raise ValueError('upper bound')
        return dict(status='UPPER_PROVED',lambda_upper=str(upper),target=str(g),n=n)
    raise ValueError('certificate kind')
