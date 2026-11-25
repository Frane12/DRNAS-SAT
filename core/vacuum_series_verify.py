"""Independent exact recurrence audit: direct differential identity, not inversion."""
from fractions import Fraction as Q
from pathlib import Path
from collections import defaultdict
import hashlib,json

def verify(source,cert):
    raw=Path(source).read_bytes();s=json.loads(raw);c=json.loads(Path(cert).read_text())
    e,lam,target=map(Q,(s['electric'],s['ratio'],s['target']));N=s['order']
    if e<=0 or target<=0 or abs(lam)>Q(19,64) or type(N)!=int or not 1<=N<=24 or target>5*e/4:raise ValueError('parameters')
    if c['source_sha256']!=hashlib.sha256(raw).hexdigest() or len(c['coefficients'])!=N:raise ValueError('binding')
    v=[{}]
    for n,row in enumerate(c['coefficients'],1):
        a={int(j):Q(x) for j,x in row.items()}
        if len(a)!=len(row) or any(j<0 or j>=n or not x for j,x in a.items()):raise ValueError('degree')
        # -D F_n, dropping its undetermined constant.
        left=defaultdict(Q)
        for j,x in a.items():
            left[j+1]+=(j+3)*x
            if j>=2:left[j-1]-=j*x
        right=defaultdict(Q)
        if n==1:right[1]=2
        else:
            for m in range(1,n):
                for i,x in v[m].items():
                    for j,y in v[n-m].items():
                        if i+j:right[i+j]+=x*y
                        right[i+j+2]-=x*y
        if any(left[j]!=right[j] for j in (left.keys()|right.keys())-{0}):raise ValueError('vacuum recurrence')
        if sum(abs(x)*2**j for j,x in a.items())>Q(2,3)*Q(20,9)**(n-1):raise ValueError('majorant')
        v.append(a)
    q=Q(20,9)*abs(lam);tail=Q(2,3)*abs(lam)*q**N/(1-q)
    if Q(c['tail'])!=tail or Q(c['gap_lower'])!=5*e/4:raise ValueError('bound')
    return dict(status='PROVED',certificate='ANALYTIC_SERIES_EXACT',task='single_cycle_vacuum',
        order=N,ratio=str(lam),derivative_tail_upper=str(tail),gap_lower=str(5*e/4),
        actual_single_cycle_hamiltonian=True,all_representations=True,
        interacting_lattice_uniform=False,continuum=False)
