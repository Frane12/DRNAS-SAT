"""YM18: actual ATLAS + original CORE proof + rational quaternion identity controls."""
from pathlib import Path
from tempfile import TemporaryDirectory
from itertools import product,combinations
from fractions import Fraction as Q
import json,sys,random
from atlas_tree_gauge import solve
from tree_gauge_verify import verify_tree

I=(Q(1),Q(0),Q(0),Q(0))
def mul(a,b):
    w,x,y,z=a;v,p,q,r=b
    return (w*v-x*p-y*q-z*r,w*p+x*v+y*r-z*q,w*q-x*r+y*v+z*p,w*r+x*q-y*p+z*v)
def inv(a):return (a[0],-a[1],-a[2],-a[3])
def qprod(xs):
    a=I
    for x in xs:a=mul(a,x)
    return a
def quat(axis,sign=1):
    a=list(I);a[0]=Q(3,5);a[axis]=Q(4*sign,5);return tuple(a)

def check_group_identities(src,cert):
    s=json.loads(src.read_text());c=json.loads(cert.read_text());root=s['root'];edges=list(map(tuple,s['edges']))
    tree={tuple(sorted(e)) for e in c['parents']};chords=list(map(tuple,c['chords']))
    parents={v:u for u,v in c['parents']}
    rng=random.Random(1818)
    def reduced(U):
        def link(a,b):return U[tuple(sorted((a,b)))] if a<b else inv(U[tuple(sorted((a,b)))] )
        path={root:I}
        def get(v):
            if v not in path:path[v]=mul(get(parents[v]),link(parents[v],v))
            return path[v]
        return [qprod((get(a),U[a,b],inv(get(b)))) for a,b in chords]
    U={e:quat(rng.randrange(1,4),rng.choice((-1,1))) for e in edges}
    X=reduced(U)
    for (_,v),word in zip(s['loops'],c['words']):
        original=qprod(U[tuple(sorted((a,b)))] if a<b else inv(U[tuple(sorted((a,b)))]) for a,b in zip(v,v[1:]+v[:1]))
        transformed=qprod(X[j-1] if j>0 else inv(X[-j-1]) for j in word)
        assert original[0]==transformed[0]
    # Check finite group actions at the tree-gauge section for every edge.
    U={e:I if e in tree else quat(rng.randrange(1,4),rng.choice((-1,1))) for e in edges};X=reduced(U)
    h=quat(2);oriented={tuple(sorted(e)):tuple(e) for e in c['parents']}
    for e,row in zip(edges,c['fields']):
        changed=dict(U)
        # Tree edge is varied in parent->child orientation, even if labels descend.
        changed[e]=inv(h) if e in tree and oriented[e]!=e else mul(h,U[e])
        expected=list(X)
        for j,side,sign in row:
            g=h if sign==1 else inv(h)
            expected[j-1]=mul(g,expected[j-1]) if side=='L' else mul(expected[j-1],g)
        assert reduced(changed)==expected,(e,row)
    return len(edges)+len(s['loops'])

def grid(d,L,k):
    pts=list(product(range(L),repeat=d));ids={p:i for i,p in enumerate(pts)}
    def shift(x,i):
        y=list(x);y[i]+=1;return tuple(y)
    edges=[];loops=[]
    for x in pts:
        for i in range(d):
            if x[i]+1<L:edges.append((ids[x],ids[shift(x,i)]))
        for i,j in combinations(range(d),2):
            if x[i]+1<L and x[j]+1<L:loops.append((k,[ids[y] for y in (x,shift(x,i),shift(shift(x,i),j),shift(x,j))]))
    return len(pts),edges,loops
def main(atlas):
    with TemporaryDirectory() as t:
        root=Path(t)
        cases=[('square',2,2,Q(1,16),Q(1),0,True),('cube',3,2,Q(1,32),Q(1),0,True),
               ('degree-six',3,3,Q(1,64),Q(1),13,True),('alternate-root',3,3,Q(1,64),Q(1),0,True),
               ('overshoot',3,2,Q(1,32),Q(100),0,False)]
        for name,d,L,k,g,r,ok in cases:
            n,e,p=grid(d,L,k);out=root/name;ans=solve(n,e,p,Q(1),g,atlas,out,r)
            assert ans['status']==('PROVED' if ok else 'UNKNOWN'),ans
            assert ans['tree']['loop_coordinates']==len(e)-n+1 and ans['atlas']['model_verified'],ans
            cert=out/'tree.json';src=out/'graph.json'
            checks=check_group_identities(src,cert)
            old=cert.read_text();z=json.loads(old);z['fields'][0].append([1,'L',1]);cert.write_text(json.dumps(z))
            try:verify_tree(src,cert)
            except ValueError:pass
            else:raise AssertionError('tampered electric field accepted')
            cert.write_text(old)
            print('YM18_ROW '+json.dumps(dict(id=name,group_identity_checks=checks,**ans)),flush=True)
    print('YM18_SUMMARY '+json.dumps(dict(cases=len(cases),continuum=False)),flush=True)
if __name__=='__main__':main(Path(sys.argv[1]).resolve())
