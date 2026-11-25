"""Audit exact use of residual global gauge symmetry; no numerical gap claim."""
import hashlib,json
from pathlib import Path
from collections import Counter
from tree_gauge_verify import verify_tree

def obstruction(d,L):
    # Centroid component of a bounded-degree spanning tree, plus
    # coordinate-ordered path congestion in the open Cartesian grid.
    if d not in (2,3,4) or L<2:raise ValueError('grid')
    n=L**d
    s=(n-1+2*d-1)//(2*d)
    denominator=L**(d+1)
    boundary=(2*s*(n-s)+denominator-1)//denominator
    return max(0,boundary-1)

def verify_locality(source,tree,certificate):
    audit=verify_tree(source,tree)
    raw=Path(tree).read_bytes();s=json.loads(Path(source).read_text())
    t=json.loads(raw);c=json.loads(Path(certificate).read_text())
    if c['tree_sha256']!=hashlib.sha256(raw).hexdigest():raise ValueError('tree binding')
    if c['source_sha256']!=hashlib.sha256(Path(source).read_bytes()).hexdigest():raise ValueError('source binding')
    if len(c['rows'])!=len(t['fields']) or len(c['complement'])!=len(t['fields']):raise ValueError('row count')
    global_row=Counter({(j,side):sgn for j in range(1,len(t['chords'])+1) for side,sgn in [('L',1),('R',-1)]})
    tree_edges={tuple(sorted(e)) for e in t['parents']}
    original=t['fields']
    for i,(row,new,flip) in enumerate(zip(original,c['rows'],c['complement'])):
        if type(flip) is not bool:raise ValueError('flag')
        def coefficients(xs):
            ans=Counter()
            for j,side,sign in xs:
                if type(j) is not int or not 1<=j<=len(t['chords']) or side not in ('L','R') or sign not in (-1,1):raise ValueError('field')
                if (j,side) in ans:raise ValueError('duplicate field')
                ans[j,side]=sign
            return ans
        a,b=coefficients(row),coefficients(new)
        edge=tuple(s['edges'][i])
        if flip and edge not in tree_edges:raise ValueError('chord changed')
        # D_new=D_old-G for the opposite side, not an arbitrary drop.
        keys=set(a)|set(b)|set(global_row)
        if any(b[x]!=a[x]-(global_row[x] if flip else 0) for x in keys):raise ValueError('operator mismatch')
        if len(new)>len(row):raise ValueError('locality regression')
        if edge in tree_edges and len(new)!=min(len(row),2*len(t['chords'])-len(row)):raise ValueError('nonminimal choice')
    def metrics(rows):
        return dict(max_row=max(map(len,rows)),terms=sum(map(len,rows)),
            cross_pairs=sum(len(r)*(len(r)-1)//2 for r in rows))
    return dict(status='LOCALITY_EQUIVALENCE_CHECKED',original=metrics(original),
        reduced=metrics(c['rows']),complemented=sum(c['complement']),
        loop_coordinates=audit['loop_coordinates'],spectrum_preserved=True,
        continuum=False)
