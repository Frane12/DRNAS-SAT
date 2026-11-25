"""YM23: exact automatic log-vacuum series on a single SU(2) cycle."""
from fractions import Fraction as Q
from collections import defaultdict
from pathlib import Path
import hashlib,json,sys

def multiply(a,b):
    out=defaultdict(Q)
    for i,x in a.items():
        for j,y in b.items():out[i+j]+=x*y
    return dict(out)

def inverse_derivative(g):
    # Invert -D on nonconstant coefficients, where
    # D=(1-x^2)d^2/dx^2-3x d/dx; then differentiate.
    g=defaultdict(Q,g);v={}
    for m in range(max(g,default=0),0,-1):
        a=g[m]/(m*(m+2))
        if a:v[m-1]=m*a
        if m>=2:g[m-2]+=m*(m-1)*a
    return v

def series(N):
    v=[{}, {0:Q(2,3)}]
    for n in range(2,N+1):
        g=defaultdict(Q)
        for i in range(1,n):
            for j,c in multiply(v[i],v[n-i]).items():
                g[j]+=c;g[j+2]-=c
        v.append(inverse_derivative(g))
    return v[1:]

def solve(source,cert):
    raw=Path(source).read_bytes();s=json.loads(raw)
    e,lam,target=map(Q,(s['electric'],s['ratio'],s['target']))
    N=s['order']
    if e<=0 or target<=0 or type(N)!=int or not 1<=N<=24:raise ValueError('parameters')
    if abs(lam)>Q(19,64) or target>5*e/4:return dict(status='UNKNOWN',reason='conservative convergence or gap bound')
    v=series(N);q=Q(20,9)*abs(lam)
    tail=Q(2,3)*abs(lam)*q**N/(1-q)
    c=dict(source_sha256=hashlib.sha256(raw).hexdigest(),coefficients=[{str(i):str(a) for i,a in sorted(p.items())} for p in v],
        tail=str(tail),gap_lower=str(5*e/4))
    Path(cert).write_text(json.dumps(c,sort_keys=True))
    from vacuum_series_verify import verify
    return verify(source,cert)

if __name__=='__main__':print(json.dumps(solve(sys.argv[1],sys.argv[2])))
