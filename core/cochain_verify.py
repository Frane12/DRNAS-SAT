"""YM31: independent exact audit of a transverse coexact soft-mode witness."""
from fractions import Fraction as Q
from pathlib import Path
from collections import defaultdict
import hashlib,json

def read(source):
    raw=Path(source).read_bytes();s=json.loads(raw)
    n=s['vertices'];edges=s['edges'];faces=s['faces'];target=Q(s['target'])
    if type(n)!=int or not 1<=n<=100000 or not edges or not faces or target<=0:raise ValueError('parameters')
    if any(len(e)!=2 or any(type(i)!=int or not 0<=i<n for i in e) or e[0]==e[1] for e in edges):raise ValueError('edge')
    for row in faces:
        if not row or len({i for i,a in row})!=len(row):raise ValueError('face')
        boundary=defaultdict(int)
        for i,a in row:
            if type(i)!=int or not 0<=i<len(edges) or type(a)!=int or a not in (-1,1):raise ValueError('incidence')
            u,v=edges[i];boundary[u]-=a;boundary[v]+=a
        if any(boundary.values()):raise ValueError('C G != 0')
    return raw,s,target

def verify(source,cert):
    raw,s,target=read(source);c=json.loads(Path(cert).read_text())
    if c['source_sha256']!=hashlib.sha256(raw).hexdigest():raise ValueError('binding')
    z=list(map(Q,c['face_potential']));v=list(map(Q,c['edge_vector']))
    if len(z)!=len(s['faces']) or len(v)!=len(s['edges']) or not any(v):raise ValueError('size')
    # Verify coexactness, hence orthogonality to the entire ker(C),
    # not only to gradients. No assumed topology or harmonic dimension.
    w=[Q(0)]*len(v)
    for a,row in zip(z,s['faces']):
        for i,k in row:w[i]+=a*k
    if w!=v:raise ValueError('not C^T z')
    div=[Q(0)]*s['vertices']
    for a,(i,j) in zip(v,s['edges']):div[i]-=a;div[j]+=a
    if any(div):raise ValueError('not transverse')
    # Recompute the quotient by sparse original C, not a dispersion formula.
    den=sum(x*x for x in v)
    num=sum(sum(k*v[i] for i,k in row)**2 for row in s['faces'])
    upper=num/den
    if not 0<upper<target or Q(c['bound'])!=upper:raise ValueError('Rayleigh')
    return dict(status='SOFT_MODE_PROVED',lambda_positive_upper=str(upper),target=str(target),
        edges=len(v),faces=len(z),coexact=True,transverse=True,
        orthogonal_to_all_flat_modes=True,model='quadratic_free_gauge',interacting_quantum_gap=False)
