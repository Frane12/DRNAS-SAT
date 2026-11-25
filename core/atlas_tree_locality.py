"""YM19: actual ATLAS tree proposals and exact complement optimization."""
import hashlib,json
from pathlib import Path
from atlas_tree_gauge import solve as tree_solve
from tree_locality_verify import verify_locality

def optimize(source,tree,out):
    t=json.loads(Path(tree).read_text());s=json.loads(Path(source).read_text())
    tree_edges={tuple(sorted(e)) for e in t['parents']}
    global_row={(j,side):sign for j in range(1,len(t['chords'])+1) for side,sign in [('L',1),('R',-1)]}
    rows=[];flags=[]
    for e,row in zip(s['edges'],t['fields']):
        present={(j,side) for j,side,sgn in row}
        flip=tuple(e) in tree_edges and len(row)>len(global_row)-len(row)
        rows.append([[j,side,-sign] for (j,side),sign in global_row.items() if (j,side) not in present] if flip else row)
        flags.append(flip)
    c=dict(source_sha256=hashlib.sha256(Path(source).read_bytes()).hexdigest(),
        tree_sha256=hashlib.sha256(Path(tree).read_bytes()).hexdigest(),rows=rows,complement=flags)
    Path(out).write_text(json.dumps(c,sort_keys=True))
    return verify_locality(source,tree,out)

def solve(n,edges,loops,alpha,target,atlas,work,roots):
    work.mkdir(parents=True,exist_ok=True)
    results=[]
    for root in dict.fromkeys(roots):
        d=work/f'root{root}'
        r=tree_solve(n,edges,loops,alpha,target,atlas,d,root)
        if 'tree' not in r:continue
        a=optimize(d/'graph.json',d/'tree.json',d/'locality.json')
        results.append(dict(root=root,locality=a,core=r['core'],atlas=r['atlas']))
    if not results:return dict(status='UNKNOWN',reason='NO_AUDITED_TREE')
    best=min(results,key=lambda r:(r['locality']['reduced']['max_row'],r['locality']['reduced']['cross_pairs'],r['locality']['reduced']['terms']))
    return dict(status=best['core']['status'],best=best,candidates=results)
