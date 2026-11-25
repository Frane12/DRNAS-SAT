"""Independent audit of local gauge forests and uniform electric form bounds."""
from pathlib import Path
from collections import Counter,deque
from itertools import product,combinations
import json,hashlib
from fractions import Fraction as Q

def grid(d,L):
    pts=list(product(range(L),repeat=d)); ids={v:i for i,v in enumerate(pts)}
    def step(v,i):
        w=list(v);w[i]+=1;return tuple(w)
    edges=[];loops=[]
    for x in pts:
        for i in range(d):
            if x[i]<L-1:edges.append((ids[x],ids[step(x,i)]))
        for i,j in combinations(range(d),2):
            if max(x[i],x[j])<L-1:loops.append([ids[v] for v in (x,step(x,i),step(step(x,i),j),step(x,j))])
    return pts,sorted(edges),loops

def verify_forest(source,cert):
    raw=Path(source).read_bytes();s=json.loads(raw);c=json.loads(Path(cert).read_text())
    if c['source_sha256']!=hashlib.sha256(raw).hexdigest():raise ValueError('binding')
    d,L,b=(s[k] for k in ('d','L','b'))
    if any(type(x) is not int for x in (d,L,b)) or not 2<=d<=3 or not 2<=L or not 2<=b<=4 or L**d>256:raise ValueError('dimensions')
    alpha,k,target=(Q(s[x]) for x in ('alpha','k','target'))
    if min(alpha,target)<=0:raise ValueError('parameters')
    pts,edges,loops=grid(d,L);n=len(pts)
    cells={i:tuple(x//b for x in p) for i,p in enumerate(pts)}
    blocks={}
    for i,v in cells.items():blocks.setdefault(v,[]).append(i)
    roots={min(v) for v in blocks.values()}
    children=[[] for _ in pts];tree=set();seen=set()
    for u,v in c['parents']:
        e=tuple(sorted((u,v)))
        if e not in edges or cells[u]!=cells[v] or v in roots or v in seen or e in tree:raise ValueError('forest')
        seen.add(v);tree.add(e);children[u].append(v)
    if seen!=set(range(n))-roots:raise ValueError('parent coverage')
    paths={v:() for v in roots};owner={v:v for v in roots};todo=deque(roots)
    while todo:
        u=todo.popleft()
        for v in children[u]:
            if v in paths:raise ValueError('forest cycle')
            paths[v]=paths[u]+(tuple(sorted((u,v))),);owner[v]=owner[u];todo.append(v)
    if len(paths)!=n:raise ValueError('forest connectivity')
    chords=[e for e in edges if e not in tree]
    if c['chords']!=[list(e) for e in chords] or c['roots']!=sorted(roots):raise ValueError('retained edges')
    idx={e:i+1 for i,e in enumerate(chords)}
    rows=[]
    for e in edges:
        if e in idx:row=[[idx[e],'L',1]]
        else:
            row=[]
            for j,(u,v) in enumerate(chords,1):
                if e in paths[u]:row.append([j,'L',1])
                if e in paths[v]:row.append([j,'R',-1])
        rows.append(row)
    if rows!=c['fields']:raise ValueError('electric rows')
    if c['endpoints']!=[[owner[u],owner[v]] for u,v in chords]:raise ValueError('residual action')
    words=[]
    for loop in loops:
        w=[]
        for u,v in zip(loop,loop[1:]+loop[:1]):
            e=tuple(sorted((u,v)))
            if e in idx:w.append(idx[e] if u<v else -idx[e])
        words.append(w)
    if words!=c['words']:raise ValueError('magnetic words')
    # ||sum D_i psi||^2 <= len(row) sum ||D_i psi||^2.
    # Each L/R Casimir form equals the same retained link Casimir.
    weights=Counter()
    for row in rows:
        for j,side,sign in row:weights[j]+=len(row)
    coefficient=max(weights.values(),default=1)
    B=b**d;uniform=1+2*(B-1)*2*d*(B-1)
    if coefficient>uniform or max(map(len,rows))>2*d*(B-1):raise ValueError('uniform bound')
    if c['form_factor']!=coefficient:raise ValueError('form coefficient')
    return dict(status='FOREST_FORM_CHECKED',vertices=n,edges=len(edges),blocks=len(roots),
        retained=len(chords),removed=n-len(roots),max_row=max(map(len,rows)),
        cross_pairs=sum(len(r)*(len(r)-1)//2 for r in rows),
        form_factor=coefficient,uniform_form_factor=uniform,uniform_row_bound=2*d*(B-1),
        residual_root_gauge=True,all_representations=True,magnetic_gap_uniform=False,continuum=False)
