"""Independent exact verifier: characteristic coefficients, not native congruence."""
from fractions import Fraction as Q
from pathlib import Path
import hashlib
import re
import sys
import json

def q(s):
    if not re.fullmatch(r'-?[0-9]{1,17}(?:/[0-9]{1,17})?',s):
        raise ValueError('invalid rational')
    return Q(s)

def matmul(a,b):
    n=len(a)
    return [[sum((a[i][k]*b[k][j] for k in range(n) if a[i][k] and b[k][j]),Q(0))
             for j in range(n)] for i in range(n)]

def shift(a,e):
    return [[x-(e if i==j else 0) for j,x in enumerate(row)] for i,row in enumerate(a)]

def characteristic_plus(a):
    # Newton identities for det(I+t A), i.e. elementary symmetric eigenvalue sums.
    n=len(a); power=a; traces=[Q(0)]
    for i in range(1,n+1):
        traces.append(sum(power[j][j] for j in range(n)))
        if i<n: power=matmul(power,a)
    c=[Q(1)]
    for k in range(1,n+1):
        c.append(sum(((-1)**(j-1)*c[k-j]*traces[j] for j in range(1,k+1)),Q(0))/k)
    return c


def rotor_verify(words,raw,cert):
    from itertools import product
    d,n=int(words[3]),int(words[4])
    if d not in (1,2) or not 2<=n<=4 or len(words)!=8: raise ValueError('rotor parameters')
    g,k,c=map(q,words[5:8])
    if g<=0 or (d==1 and c): raise ValueError('rotor parameters')
    lines=Path(cert).read_text().split()
    if len(lines)!=6 or lines[:3]!=['drnas-op-v1',hashlib.sha256(raw).hexdigest(),'rotor-gap']:
        raise ValueError('rotor binding')
    upper,requested,lower=map(Q,lines[3:])
    tail=Q(n*(n+2))-2*(d*abs(k)+abs(c))
    if requested!=g or lower-upper<g or lower>=tail: raise ValueError('rotor gap bound')
    # Independently enumerate coordinate differences, not native edge walk.
    points=list(product(range(n),repeat=d))
    outside=[z for z in product(range(n+1),repeat=d) if max(z)==n]
    steps={tuple(int(i==j) for i in range(d)):k for j in range(d)}
    if d==2: steps[(1,1)]=c
    def entry(x,y):
        if x==y:return Q(sum(j*(j+2) for j in x))
        diff=tuple(a-b for a,b in zip(x,y))
        return -steps.get(diff,steps.get(tuple(-v for v in diff),Q(0)))
    a=[[entry(x,y) for y in points] for x in points]
    boundary=[[entry(x,z) for z in outside] for x in points]
    gram=[[sum(u*v for u,v in zip(x,y)) for y in boundary] for x in boundary]
    def counts(m):
        co=characteristic_plus(m)
        nz=[x for x in co if x]
        return sum((x<0)!=(y<0) for x,y in zip(nz,nz[1:])),len(m)-max(i for i,x in enumerate(co) if x)
    neg,zero=counts(shift(a,upper))
    if neg+zero<1:raise ValueError('Rayleigh upper bound')
    b=shift(a,lower)
    b=[[v-gram[i][j]/(tail-lower) for j,v in enumerate(row)] for i,row in enumerate(b)]
    if counts(b)[0]>1:raise ValueError('Schur negative index')
    return dict(status='PROVED',certificate='OPERATOR_EXACT',task='rotor-gap',
                ground_upper=str(upper),excited_lower=str(lower),gap_lower=str(lower-upper),
                tail_lower=str(tail),rotors=d,cutoff=n,infinite_representation=True)

def verify(source,cert):
    raw=Path(source).read_bytes()
    if len(raw)>65536: raise ValueError('size')
    words=raw.decode('ascii').split()
    if words[:2]!=['p','op']: raise ValueError('header')
    kind=words[2]; n=int(words[3])
    if not 1<=n<=24: raise ValueError('dimension')
    if kind=='rotor-gap':return rotor_verify(words,raw,cert)
    i=4; e=Q(0); g=Q(0)
    if kind=='gap': e=q(words[i]); i+=1
    if kind in ('gap','auto-gap','interval-gap'):
        g=q(words[i]); i+=1
        if g<=0: raise ValueError('gap')
    elif kind not in ('psd','pd','commute'): raise ValueError('task')
    def matrix():
        nonlocal i
        a=[[q(words[i+r*n+c]) for c in range(n)] for r in range(n)]; i+=n*n
        if any(a[r][c]!=a[c][r] for r in range(n) for c in range(n)): raise ValueError('symmetry')
        return a
    a=matrix(); b=matrix() if kind=='commute' else None
    if i!=len(words): raise ValueError('trailing input')
    lines=Path(cert).read_text().split()
    if len(lines)!=(6 if kind=='interval-gap' else 5) or lines[:3]!=['drnas-op-v1',hashlib.sha256(raw).hexdigest(),kind]:
        raise ValueError('evidence binding')
    ce,cg=Q(lines[3]),Q(lines[4])
    if kind=='interval-gap':
        # Independent inertia via signs of coefficients of det(I+tA).
        # This polynomial has only real roots, all nonzero; the positive
        # roots count negative eigenvalues. Descartes is exact here.
        def counts(t):
            c=characteristic_plus(shift(a,t))
            nonzero=[x for x in c if x]
            neg=sum((x<0)!=(y<0) for x,y in zip(nonzero,nonzero[1:]))
            degree=max(i for i,x in enumerate(c) if x)
            return neg,n-degree
        lower=Q(lines[5])
        if n<2 or cg!=g or lower-ce<g: raise ValueError('interval gap claim')
        neg,z=counts(ce)
        neg2,z2=counts(lower)
        if neg+z<1 or neg2>1: raise ValueError('spectral count')
        return dict(status='PROVED',certificate='OPERATOR_EXACT',task=kind,
                    ground_upper=str(ce),excited_lower=str(lower),gap_lower=str(lower-ce),
                    requested_gap=str(g),ground_dimension='1')
    if cg!=g or (kind!='auto-gap' and ce!=e): raise ValueError('claim mismatch')
    if kind=='commute': ok=matmul(a,b)==matmul(b,a)
    elif kind in ('psd','pd'):
        c=characteristic_plus(a); ok=all(x>=0 for x in c) and (kind=='psd' or c[-1]>0)
    else:
        a=shift(a,ce); c=characteristic_plus(a)
        # Symmetric real matrix: all elementary symmetric sums nonnegative iff PSD.
        # Zero determinant and nonzero trace ensure both ground and excited states.
        ok=all(x>=0 for x in c) and c[-1]==0 and c[1]>0
        b=matmul(a,a); b=[[x-g*a[i][j] for j,x in enumerate(row)] for i,row in enumerate(b)]
        ok=ok and all(x>=0 for x in characteristic_plus(b))
    if not ok: raise ValueError('operator claim false')
    return dict(status='PROVED',certificate='OPERATOR_EXACT',task=kind,ground=str(ce),gap_lower=str(g))

if __name__=='__main__':
    try: print(json.dumps(verify(sys.argv[1],sys.argv[2])))
    except Exception as e: print(json.dumps(dict(status='REJECTED',error=str(e)))); sys.exit(1)
