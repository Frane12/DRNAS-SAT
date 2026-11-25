"""YM31: geometry-proposed soft modes, certified against incidence only."""
from fractions import Fraction as Q
from pathlib import Path
from itertools import product,combinations
import hashlib,json
from cochain_verify import read,verify

def periodic(shape,target,seed=0):
    import random
    d=len(shape);points=list(product(*[range(l) for l in shape]));n=len(points)
    def shift(x,i):
        a=list(x);a[i]=(a[i]+1)%shape[i];return tuple(a)
    rng=random.Random(seed);ids=list(range(n));rng.shuffle(ids);vid=dict(zip(points,ids))
    keys=[(x,i) for x in points for i in range(d)];rng.shuffle(keys)
    eid={key:i for i,key in enumerate(keys)}
    # Random independent edge orientations; incidence signs are preserved.
    signs={key:rng.choice((-1,1)) for key in keys}
    edges=[]
    for x,i in keys:
        a,b=vid[x],vid[shift(x,i)]
        edges.append([a,b] if signs[x,i]==1 else [b,a])
    pkeys=[(x,i,j) for x in points for i,j in combinations(range(d),2)];rng.shuffle(pkeys)
    faces=[];geometry=[]
    for x,i,j in pkeys:
        flip=rng.choice((-1,1))
        row=[((x,i),1),((shift(x,i),j),1),((shift(x,j),i),-1),((x,j),-1)]
        faces.append([[eid[key],a*signs[key]*flip] for key,a in row])
        geometry.append([list(x),i,j,flip])
    return dict(vertices=n,edges=edges,faces=faces,shape=list(shape),face_geometry=geometry,target=str(target))

def solve(source,cert):
    raw,s,target=read(source);shape=s['shape'];d=len(shape);best=None
    if not 2<=d<=4 or any(type(l)!=int or l<4 for l in shape) or len(s['face_geometry'])!=len(s['faces']):raise ValueError('geometry')
    for i,j in combinations(range(d),2):
        for axis in (i,j):
            L=shape[axis]
            # Integer triangular wave, with exact zero mean even for odd L.
            wave=[Q(min(x,L-x)) for x in range(L)];mean=sum(wave)/L
            acc=Q(0);potential=[]
            for a in wave:acc-=a-mean;potential.append(acc)
            z=[potential[x[axis]]*flip if (a,b)==(i,j) else Q(0) for x,a,b,flip in s['face_geometry']]
            v=[Q(0)]*len(s['edges'])
            for a,row in zip(z,s['faces']):
                if a:
                    for k,w in row:v[k]+=a*w
            den=sum(a*a for a in v)
            if not den:continue
            num=sum(sum(w*v[k] for k,w in row)**2 for row in s['faces'])
            upper=num/den
            if upper>0 and (best is None or upper<best[0]):best=(upper,z,v,axis)
    if best is None or best[0]>=target:return dict(status='UNKNOWN',candidate_upper=str(best[0]) if best else None)
    upper,z,v,axis=best
    c=dict(source_sha256=hashlib.sha256(raw).hexdigest(),face_potential=list(map(str,z)),edge_vector=list(map(str,v)),bound=str(upper))
    Path(cert).write_text(json.dumps(c,sort_keys=True))
    return dict(verify(source,cert),selected_axis=axis)
