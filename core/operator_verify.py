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


def gauge_verify(words,raw,cert):
    from collections import deque
    n,m,p=map(int,words[3:6]); alpha,target=map(q,words[6:8])
    if not 1<=n<=256 or not 0<=m<=1024 or not 0<=p<=512 or min(alpha,target)<=0: raise ValueError('gauge parameters')
    i=8; edges=set(); adj=[set() for _ in range(n)]
    for _ in range(m):
        a,b=map(int,words[i:i+2]);i+=2
        e=tuple(sorted((a,b)))
        if a==b or not (0<=a<n and 0<=b<n) or e in edges:raise ValueError('edge')
        edges.add(e);adj[a].add(b);adj[b].add(a)
    magnetic=Q(0);upper=Q(0);loops=set()
    for _ in range(p):
        length=int(words[i]);k=q(words[i+1]);i+=2
        if not 3<=length<=n:raise ValueError('loop length')
        v=list(map(int,words[i:i+length]));i+=length
        if len(v)!=length or len(set(v))!=length or any(not 0<=a<n for a in v):raise ValueError('loop vertices')
        boundary=frozenset(tuple(sorted((a,b))) for a,b in zip(v,v[1:]+v[:1]))
        if not boundary<=edges or boundary in loops:raise ValueError('loop boundary')
        loops.add(boundary)
        magnetic+=2*abs(k)
        e=alpha*3*length/4
        upper=min(upper,-k*k*e/(e*e+k*k))
    if i!=len(words):raise ValueError('trailing input')
    # Independently compute girth by deleting each edge and finding
    # a shortest alternate path between its endpoints.
    girth=n+1
    for a,b in edges:
        todo=deque([(a,0)]);seen={a}
        while todo:
            u,d=todo.popleft()
            if u==b:girth=min(girth,d+1);break
            for v in adj[u]:
                if (u==a and v==b) or (u==b and v==a) or v in seen:continue
                seen.add(v);todo.append((v,d+1))
    if girth>n:raise ValueError('no nontrivial physical sector')
    lower=alpha*3*girth/4-magnetic
    lines=Path(cert).read_text().split()
    if len(lines)!=6 or lines[:3]!=['drnas-op-v1',hashlib.sha256(raw).hexdigest(),'gauge-gap']:raise ValueError('gauge binding')
    if int(lines[3])!=girth or Q(lines[4])!=upper or Q(lines[5])!=lower or lower-upper<target:raise ValueError('gauge bound')
    return dict(status='PROVED',certificate='OPERATOR_EXACT',task='gauge-gap',
        electric_gap=str(alpha*3*girth/4),girth=girth,ground_upper=str(upper),
        excited_lower=str(lower),gap_lower=str(lower-upper),requested_gap=str(target),
        vertices=n,edges=m,loops=p,all_representations=True,volume_uniform=False)


def gauge_stability_verify(words,raw,cert):
    # This checks the normalization of a particular analytic theorem
    # application, not an arbitrary numerical assertion about its constants.
    if len(words)!=5:raise ValueError('stability header')
    d=int(words[3]);alpha=q(words[4])
    if not 2<=d<=4 or alpha<=0:raise ValueError('stability parameters')
    import math
    stencil=1+d
    local_gap=alpha*Q(3,4)/stencil
    beta_factor=2*math.comb(d,2)/local_gap
    w=Path(cert).read_text().split()
    if len(w)!=6 or w[:3]!=['drnas-op-v1',hashlib.sha256(raw).hexdigest(),'gauge-stability']:
        raise ValueError('stability binding')
    if int(w[3])!=stencil or Q(w[4])!=local_gap or Q(w[5])!=beta_factor:
        raise ValueError('stability normalization')
    return dict(status='THEOREM_APPLIED',certificate='THEOREM_APPLICATION',
        task='gauge-stability',theorem='Yarotsky 2004 arXiv:math-ph/0412040 Theorem 1',
        spatial_dimension=d,stencil_size=stencil,local_electric_gap=str(local_gap),
        beta_per_abs_k=str(beta_factor),volume_uniform_for_sufficiently_small_coupling=True,
        numerical_threshold_known=False,numerical_gap_known=False,continuum=False)


def decimation_verify(words,raw,cert):
    n=int(words[3]);g=q(words[4]);k=int(words[5])
    if not 2<=n<=24 or g<=0 or not 1<=k<n or len(words)!=6+k+n*n: raise ValueError('decimation dimensions')
    drop=list(map(int,words[6:6+k]))
    if len(set(drop))!=k or any(not 0<=i<n for i in drop): raise ValueError('decimation indices')
    v=list(map(q,words[6+k:]));h=[v[i*n:(i+1)*n] for i in range(n)]
    if any(h[i][j]!=h[j][i] for i in range(n) for j in range(n)):raise ValueError('symmetry')
    if any(h[i][j] for i in drop for j in drop if i!=j):raise ValueError('diagonal block')
    lines=Path(cert).read_text().split()
    if len(lines)!=6 or lines[:3]!=['drnas-op-v1',hashlib.sha256(raw).hexdigest(),'decimation-gap']:raise ValueError('decimation binding')
    u,requested,l=map(Q,lines[3:])
    if requested!=g or l-u<g or any(h[i][i]<=l for i in drop):raise ValueError('cut or bound')
    # Independent check uses the original full matrix, not the Schur reduction.
    def counts(t):
        c=characteristic_plus(shift(h,t))
        nz=[x for x in c if x]
        neg=sum((x<0)!=(y<0) for x,y in zip(nz,nz[1:]))
        return neg,n-max(i for i,x in enumerate(c) if x)
    a,b=counts(u)
    if a+b<1 or counts(l)[0]>1:raise ValueError('spectral count')
    return dict(status='PROVED',certificate='OPERATOR_EXACT',task='decimation-gap',
                ground_upper=str(u),excited_lower=str(l),gap_lower=str(l-u),
                eliminated=k,remaining=n-k,finite_only=True)

def ks_loop_verify(words,raw,cert):
    if len(words)!=8:raise ValueError('ks loop header')
    length,cutoff=map(int,words[3:5]);a,g2,target=map(q,words[5:8])
    if not 3<=length<=24 or not 2<=cutoff<=128 or min(a,g2,target)<=0:raise ValueError('ks loop parameters')
    e=length*g2/(8*a);k=2/(a*g2);tail=e*cutoff*(cutoff+2)-2*k
    z=Path(cert).read_text().split()
    if len(z)!=5 or z[:3]!=['drnas-op-v1',hashlib.sha256(raw).hexdigest(),'ks-loop-gap']:raise ValueError('ks binding')
    upper,lower=map(Q,z[3:])
    if lower>=tail or lower-upper<target:raise ValueError('ks gap bound')
    # Independent LDL congruence on the tridiagonal head. A zero pivot
    # and its nonzero neighbor form an invertible 2x2 block of inertia (1,1).
    def negative(cut,correction):
        d=[e*j*(j+2)-cut for j in range(cutoff)]
        d[-1]-=correction
        count=0;i=0
        while i<len(d):
            pivot=d[i]
            if not pivot:
                if i+1<len(d):count+=1;i+=2
                else:i+=1
                continue
            count+=pivot<0
            if i+1<len(d):d[i+1]-=k*k/pivot
            i+=1
        return count
    if upper>0 or (upper!=0 and negative(upper,Q(0))<1):raise ValueError('Rayleigh upper')
    if negative(lower,k*k/(tail-lower))>1:raise ValueError('Schur lower')
    # YM14 normalized perturbation factor for d=3, not a threshold.
    alpha=g2/(2*a);beta=32*k/alpha
    return dict(status='PROVED',certificate='OPERATOR_EXACT',task='ks-loop-gap',
        ground_upper=str(upper),excited_lower=str(lower),gap_lower=str(lower-upper),
        requested_gap=str(target),tail_lower=str(tail),lattice_spacing=str(a),
        coupling_squared=str(g2),magnetic_electric_ratio=str(k/alpha),ym14_beta=str(beta),
        cutoff=cutoff,all_representations=True,physical_single_cycle=True,volume_uniform=False,continuum=False)

def multiscale_verify(words,raw,cert):
    n=int(words[3]);g=q(words[4]);s=int(words[5]);i=6
    if not 2<=n<=24 or g<=0 or not 2<=s<n:raise ValueError('dimensions')
    layers=[];drop=set()
    for _ in range(s):
        k=int(words[i]);i+=1
        layer=list(map(int,words[i:i+k]));i+=k
        if not 1<=k<n or len(layer)!=k or len(set(layer))!=k or any(j in drop or not 0<=j<n for j in layer):raise ValueError('layer')
        drop.update(layer);layers.append(layer)
    if len(drop)>=n or len(words)!=i+n*n:raise ValueError('matrix size')
    vals=list(map(q,words[i:]));h=[vals[j*n:(j+1)*n] for j in range(n)]
    if any(h[i][j]!=h[j][i] for i in range(n) for j in range(n)):raise ValueError('symmetry')
    z=Path(cert).read_text().split()
    if len(z)!=6 or z[:3]!=['drnas-op-v1',hashlib.sha256(raw).hexdigest(),'multiscale-gap']:raise ValueError('binding')
    u,r,l=map(Q,z[3:])
    if r!=g or l-u<g:raise ValueError('gap')
    # Independent original-matrix spectrum, not a replay of native elimination.
    def counts(a):
        c=characteristic_plus(a);nz=[x for x in c if x]
        return sum((x<0)!=(y<0) for x,y in zip(nz,nz[1:])),len(a)-max(i for i,x in enumerate(c) if x)
    neg,zero=counts(shift(h,u))
    if neg+zero<1 or counts(shift(h,l))[0]>1:raise ValueError('spectral count')
    d=sorted(drop);block=[[h[i][j]-(l if i==j else 0) for j in d] for i in d]
    if not all(x>0 for x in characteristic_plus(block)):raise ValueError('eliminated block not positive')
    # Independently check the conservative symbolic fill graph.
    adj={i:{j for j in range(n) if j!=i and h[i][j]} for i in range(n)}
    dims=[n]
    for layer in layers:
        if any(j in adj[i] for i in layer for j in layer if i!=j):raise ValueError('layer conflict')
        for i in layer:
            neighbors=adj.pop(i)
            for j in neighbors:adj[j].discard(i);adj[j].update(neighbors-{j})
        dims.append(len(adj))
    return dict(status='PROVED',certificate='OPERATOR_EXACT',task='multiscale-gap',
                ground_upper=str(u),excited_lower=str(l),gap_lower=str(l-u),
                layers=s,dimensions=dims,eliminated=len(drop),remaining=n-len(drop),finite_only=True)

def ks_pair_verify(words,raw,cert):
    if len(words)!=8:raise ValueError('pair header')
    length,n=map(int,words[3:5]);a,g2,target=map(q,words[5:8])
    if not 3<=length<=24 or not 3<=n<=128 or min(a,g2,target)<=0:raise ValueError('pair parameters')
    e=(length-1)*g2/(8*a);f=length*g2/(8*a);k=2/(a*g2);tau=e*n*(n+2)-2*k
    z=Path(cert).read_text().split()
    if len(z)!=7 or z[:3]!=['drnas-op-v1',hashlib.sha256(raw).hexdigest(),'ks-pair-gap']:raise ValueError('pair binding')
    u,l0,l1,la=map(Q,z[3:])
    if max(l0,l1,la)>=tau:raise ValueError('tail cut')
    # Independent rational LDL inertia. Squared off-diagonals are sufficient.
    def hop(j,l):return k*k*(1-Q(l*(l+1),(j+1)*(j+2)))
    def count(l,scale,cut,correct):
        d=[scale*j*(j+2)-cut for j in range(l,n)]
        if correct:d[-1]-=hop(n-1,l)/(tau-cut)
        neg=0;i=0
        while i<len(d):
            if d[i]==0:
                if i+1<len(d):neg+=1;i+=2
                else:i+=1
                continue
            neg+=d[i]<0
            if i+1<len(d):d[i+1]-=hop(l+i,l)/d[i]
            i+=1
        return neg
    if u>0 or (u!=0 and count(0,f,u,False)<1):raise ValueError('upper trial')
    if count(0,e,l0,True)>0 or count(0,e,l1,True)>1 or count(1,e,la,True)>0:raise ValueError('lower comparison')
    lower=min(l0+l1,2*la);gap=lower-2*u
    if gap<target:raise ValueError('pair gap')
    return dict(status='PROVED',certificate='OPERATOR_EXACT',task='ks-pair-gap',ground_upper=str(2*u),excited_lower=str(lower),gap_lower=str(gap),radial_lower=str(l0+l1),angular_lower=str(2*la),tail_lower=str(tau),magnetic_electric_ratio=str(4/g2**2),cutoff=n,shared_edges=1,all_representations=True,volume_uniform=False,continuum=False)

def ks_ladder_verify(words,raw,cert):
    if len(words)!=8:raise ValueError('ladder header')
    m,n=map(int,words[3:5]);a,g2,target=map(q,words[5:8])
    if not 2<=m<=256 or not 3<=n<=128 or min(a,g2,target)<=0:raise ValueError('ladder parameters')
    e=g2/(4*a);f=g2/(2*a);k=2/(a*g2);tau=e*n*(n+2)-2*k
    z=Path(cert).read_text().split()
    if len(z)!=7 or z[:3]!=['drnas-op-v1',hashlib.sha256(raw).hexdigest(),'ks-ladder-gap']:raise ValueError('ladder binding')
    u,l0,l1,la=map(Q,z[3:])
    if max(l0,l1,la)>=tau:raise ValueError('tail cut')
    # Independent LDL count; 2x2 pivot at a zero diagonal has inertia (1,1).
    def hop(j,l):return k*k*(1-Q(l*(l+1),(j+1)*(j+2)))
    def count(l,scale,cut,correct):
        d=[scale*j*(j+2)-cut for j in range(l,n)]
        if correct:d[-1]-=hop(n-1,l)/(tau-cut)
        neg=0;i=0
        while i<len(d):
            if not d[i]:
                if i+1<len(d):neg+=1;i+=2
                else:i+=1
                continue
            neg+=d[i]<0
            if i+1<len(d):d[i+1]-=hop(l+i,l)/d[i]
            i+=1
        return neg
    if u>0 or (u and count(0,f,u,False)<1):raise ValueError('upper trial')
    if count(0,e,l0,True)>0 or count(0,e,l1,True)>1 or count(1,e,la,True)>0:raise ValueError('lower comparison')
    radial=(m-1)*l0+l1;angular=(m-2)*l0+2*la
    lower=min(radial,angular);gap=lower-m*u
    if gap<target:raise ValueError('ladder gap')
    return dict(status='PROVED',certificate='OPERATOR_EXACT',task='ks-ladder-gap',
        plaquettes=m,vertices=2*(m+1),edges=3*m+1,ground_upper=str(m*u),
        excited_lower=str(lower),gap_lower=str(gap),radial_lower=str(radial),
        angular_lower=str(angular),reference_ground_lower=str(m*l0),
        per_plaquette_bracket_width=str(u-l0),cutoff=n,all_representations=True,
        volume_uniform=False,continuum=False,magnetic_electric_ratio=str(4/g2**2))

def ks_bouquet_verify(words,raw,cert):
    if len(words)!=8:raise ValueError('bouquet header')
    length,n=map(int,words[3:5]);a,g2,target=map(q,words[5:8])
    if not 3<=length<=24 or not 3<=n<=128 or min(a,g2,target)<=0:raise ValueError('bouquet parameters')
    e=length*g2/(8*a);k=2/(a*g2);tau=e*n*(n+2)-2*k
    z=Path(cert).read_text().split()
    if len(z)!=6 or z[:3]!=['drnas-op-v1',hashlib.sha256(raw).hexdigest(),'ks-bouquet-gap']:raise ValueError('bouquet binding')
    u,l1,la=map(Q,z[3:])
    if max(l1,la)>=tau:raise ValueError('tail cut')
    def hop(j,l):return k*k*(1-Q(l*(l+1),(j+1)*(j+2)))
    def count(l,cut,correct):
        d=[e*j*(j+2)-cut for j in range(l,n)]
        if correct:d[-1]-=hop(n-1,l)/(tau-cut)
        neg=0;i=0
        while i<len(d):
            if not d[i]:
                if i+1<len(d):neg+=1;i+=2
                else:i+=1
                continue
            neg+=d[i]<0
            if i+1<len(d):d[i+1]-=hop(l+i,l)/d[i]
            i+=1
        return neg
    if u>0 or (u and count(0,u,False)<1):raise ValueError('upper trial')
    if count(0,l1,True)>1 or count(1,la,True)>0:raise ValueError('lower comparison')
    radial=l1-u;angular=2*(la-u);gap=min(radial,angular)
    if gap<target:raise ValueError('bouquet gap')
    return dict(status='PROVED',certificate='OPERATOR_EXACT',task='ks-bouquet-gap',
        gap_lower=str(gap),radial_gap_lower=str(radial),angular_pair_gap_lower=str(angular),
        single_ground_upper=str(u),tail_lower=str(tau),cutoff=n,
        applies_to_all_finite_bouquets_m_ge_2=True,volume_uniform=True,
        topology='edge_disjoint_cycles_common_vertex',shared_edges=False,
        all_representations=True,continuum=False,magnetic_electric_ratio=str(4/g2**2))


def gauge_parent_verify(words,raw,cert):
    if len(words)!=7:raise ValueError('parent header')
    d=int(words[3]);alpha,k,target=map(q,words[4:])
    if not 2<=d<=4 or min(alpha,target)<=0:raise ValueError('parent parameters')
    t=k/(3*alpha)
    # Each edge has at most two plaquettes per perpendicular direction.
    # Each plaquette has Hessian norm at most 4/2 on its four edges.
    degree=2*(d-1)
    curvature=Q(1,2)-4*degree*abs(t)
    gap=alpha*curvature
    residual=alpha*(degree*abs(t))**2
    z=Path(cert).read_text().split()
    if len(z)!=7 or z[:3]!=['drnas-op-v1',hashlib.sha256(raw).hexdigest(),'gauge-parent-gap']:raise ValueError('parent binding')
    if list(map(Q,z[3:]))!=[t,curvature,gap,residual] or gap<target:raise ValueError('parent bound')
    return dict(status='PROVED',certificate='OPERATOR_EXACT',task='gauge-parent-gap',
                model='interacting_gauge_parent_not_KS',ground='0',ground_dimension='1',
                gap_lower=str(gap),curvature_lower=str(curvature),vacuum_exponent=str(t),
                residual_per_edge_upper=str(residual),volume_uniform=True,all_representations=True,
                original_KS_uniform_gap=False,continuum=False,analytic_premise='Bakry-Emery ground-state transform')

def gauge_parent_volume_verify(words,raw,cert):
    from math import comb
    if len(words)!=8:raise ValueError('parent header')
    d,L=map(int,words[3:5]);alpha,k,target=map(q,words[5:8])
    if d not in (2,3) or not 2<=L<=64 or min(alpha,target)<=0:raise ValueError('parent parameters')
    lam=k/(3*alpha);degree=2*(d-1)
    # Independent combinatorial count: s boundary transverse coordinates
    # each contribute one instead of two neighboring plaquettes.
    total=d*(L-1)*sum(comb(d-1,s)*2**s*(L-2)**(d-1-s)*(degree-s)**2 for s in range(d))
    gap=alpha/2-4*degree*abs(k)/3
    local=alpha*lam**2*degree**2;residual=alpha*lam**2*total
    z=Path(cert).read_text().split()
    if len(z)!=8 or z[:3]!=['drnas-op-v1',hashlib.sha256(raw).hexdigest(),'gauge-parent-volume']:raise ValueError('parent binding')
    if list(map(Q,z[3:]))!=[lam,gap,local,residual,gap-residual] or gap<target:raise ValueError('parent bound')
    return dict(status='PROVED',certificate='OPERATOR_EXACT',task='gauge-parent-volume',
        reference_hamiltonian=True,gap_lower=str(gap),local_residual_upper=str(local),
        total_residual_upper=str(residual),original_finite_gap_lower=str(gap-residual),
        original_positive_bound=gap-residual>0,uniform_reference_gap=True,
        uniform_original_gap=False,all_representations=True,continuum=False,
        dimension=d,L=L,lambda_value=str(lam),analytic_theorem='Bakry-Emery curvature criterion')

def verify(source,cert):
    raw=Path(source).read_bytes()
    if len(raw)>65536: raise ValueError('size')
    words=raw.decode('ascii').split()
    if words[:2]!=['p','op']: raise ValueError('header')
    kind=words[2]; n=int(words[3])
    if kind=='ks-bouquet-gap':return ks_bouquet_verify(words,raw,cert)
    if kind=='ks-ladder-gap':return ks_ladder_verify(words,raw,cert)
    if kind=='ks-pair-gap':return ks_pair_verify(words,raw,cert)
    if kind=='ks-loop-gap':return ks_loop_verify(words,raw,cert)
    if kind=='gauge-gap':return gauge_verify(words,raw,cert)
    if kind=='gauge-stability':return gauge_stability_verify(words,raw,cert)
    if kind=='gauge-parent-gap':return gauge_parent_verify(words,raw,cert)
    if kind=='gauge-parent-volume':return gauge_parent_volume_verify(words,raw,cert)
    if not 1<=n<=24: raise ValueError('dimension')
    if kind=='rotor-gap':return rotor_verify(words,raw,cert)
    if kind=='decimation-gap':return decimation_verify(words,raw,cert)
    if kind=='multiscale-gap':return multiscale_verify(words,raw,cert)
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
