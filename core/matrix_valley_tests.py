"""Rational SU(2) identities, transverse certificates, free-coordinate controls."""
from fractions import Fraction as Q
from pathlib import Path
from tempfile import TemporaryDirectory
from itertools import product
from atlas_matrix_valley import solve
from matrix_valley_verify import verify
import random,json,sys

def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def mul(a,b):
    s,u=a[0],a[1:];t,v=b[0],b[1:];c=cross(u,v)
    return (s*t-dot(u,v),)+tuple(s*y+t*x+z for x,y,z in zip(u,v,c))
def inv(a):return (a[0],)+tuple(-x for x in a[1:])
def quaternion(v):
    t=dot(v,v);return ((1-t)/(1+t),)+tuple(2*x/(1+t) for x in v)
def identities():
    q=[quaternion(v) for v in product((Q(-1),Q(0),Q(1,2)),repeat=3)]
    for a,b in product(q,repeat=2):
        c=mul(mul(mul(a,b),inv(a)),inv(b))
        z=cross(a[1:],b[1:]);assert 1-c[0]==2*dot(z,z)
    return len(q)**2

def main(atlas):
    cases=[]
    for n in (2,3,4,8,16):
        cases.append((n,[(i,i+1,'1') for i in range(n-1)],'COERCIVE_PROVED'))
    cases.extend([(6,[(0,i,'1') for i in range(1,6)],'COERCIVE_PROVED'),
                 (4,[(0,1,'3/2'),(2,3,'1/7')],'COERCIVE_PROVED'),
                 (3,[(0,1,'1')],'FREE_COORDINATE'),
                 (5,[],'FREE_COORDINATE')])
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        for idx,(n,edges,expected) in enumerate(cases):
            p=list(range(n));random.Random(idx+31).shuffle(p)
            s=dict(n=n,kinetic=['1']*n,couplings=sorted([*sorted((p[i],p[j])),w] for i,j,w in edges))
            src=root/f'{idx}.json';c=root/f'{idx}.cert';src.write_text(json.dumps(s))
            r=solve(src,c,atlas,root/f'w{idx}');assert r['status']==expected,(idx,r)
            assert verify(src,c)['status']==expected
            if expected=='COERCIVE_PROVED':
                old=c.read_text();z=json.loads(old);z['allocations'][0][2]='100';c.write_text(json.dumps(z))
                try:verify(src,c)
                except ValueError:pass
                else:raise AssertionError('double spending accepted')
                c.write_text(old)
            print('YM31_ROW '+json.dumps(dict(id=idx,**r)),flush=True)
    print('YM31_SUMMARY '+json.dumps(dict(cases=len(cases),positive=7,free=2,quaternion_identities=identities(),continuum=False)),flush=True)
if __name__=='__main__':main(Path(sys.argv[1]).resolve())
