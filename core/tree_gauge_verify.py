"""Independent source-bound tree-coordinate audit, no assumption of commuting fields."""
import hashlib,json
from pathlib import Path
from collections import deque
from fractions import Fraction as Q

def verify_tree(source,certificate):
    raw=Path(source).read_bytes();s=json.loads(raw);c=json.loads(Path(certificate).read_text())
    if c['source_sha256']!=hashlib.sha256(raw).hexdigest():raise ValueError('source hash')
    n=s['n'];root=s['root'];edges=[tuple(e) for e in s['edges']]
    if not 2<=n<=256 or not 0<=root<n or min(Q(s['alpha']),Q(s['target']))<=0:raise ValueError('parameters')
    if edges!=sorted(set(edges)) or any(not 0<=a<b<n for a,b in edges):raise ValueError('edges')
    tree=[tuple(x) for x in c['parents']]
    if len(tree)!=n-1 or len({v for u,v in tree})!=n-1 or root in {v for u,v in tree}:raise ValueError('tree count')
    children=[[] for _ in range(n)]
    tree_edges=set()
    for u,v in tree:
        e=tuple(sorted((u,v)))
        if e not in edges or e in tree_edges:raise ValueError('tree edge')
        tree_edges.add(e);children[u].append(v)
    # Independently reconstruct all root paths in parent-to-child orientation.
    paths={root:()};queue=deque([root])
    while queue:
        u=queue.popleft()
        for v in children[u]:
            if v in paths:raise ValueError('cycle')
            paths[v]=paths[u]+((u,v),);queue.append(v)
    if len(paths)!=n:raise ValueError('tree not spanning')
    chords=[e for e in edges if e not in tree_edges]
    if not chords or c['chords']!=[list(e) for e in chords]:raise ValueError('chords')
    index={e:i+1 for i,e in enumerate(chords)};oriented={tuple(sorted(e)):e for e in tree}
    expected=[]
    for e in edges:
        if e in index:row=[[index[e],'L',1]]
        else:
            t=oriented[e];row=[]
            for i,(a,b) in enumerate(chords,1):
                if t in paths[a]:row.append([i,'L',1])
                if t in paths[b]:row.append([i,'R',-1])
        expected.append(row)
    if c['fields']!=expected:raise ValueError('electric fields')
    words=[];seen=set()
    for k,v in s['loops']:
        Q(k)
        if len(v)<3 or len(v)!=len(set(v)) or any(not 0<=a<n for a in v):raise ValueError('loop')
        signed=[(tuple(sorted((a,b))),1 if a<b else -1) for a,b in zip(v,v[1:]+v[:1])]
        boundary=frozenset(e for e,sign in signed)
        if not boundary<=set(edges) or boundary in seen:raise ValueError('loop boundary')
        seen.add(boundary);words.append([sign*index[e] for e,sign in signed if e in index])
    if c['words']!=words:raise ValueError('Wilson words')
    # Return structural diagnostics; a wide row creates cross-derivatives
    # in its square, including distinct left/right actions on one chord.
    mixed=sum(len(row)>1 for row in expected)
    pairs=sum(len(row)*(len(row)-1)//2 for row in expected)
    return dict(status='TREE_COORDINATES_CHECKED',vertices=n,edges=len(edges),loop_coordinates=len(chords),
        removed_gauge_coordinates=n-1,magnetic_words=len(words),mixed_electric_rows=mixed,
        electric_cross_pairs=pairs,max_row=max(map(len,expected)),residual_global_conjugation=True,
        all_representations=True,continuum=False)
