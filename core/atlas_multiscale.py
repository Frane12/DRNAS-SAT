"""ATLAS30 planner on successive symbolic fill graphs; CORE audits exact cuts."""
from pathlib import Path
from fractions import Fraction as Q
import subprocess,json
from atlas_decimation import plan,PIN
from run import run
from operator_verify import verify

def solve(h,g,atlas,work):
    if subprocess.check_output(['git','-C',str(atlas),'rev-parse','HEAD'],text=True).strip()!=PIN:
        raise ValueError('ATLAS source not pinned')
    n=len(h);work.mkdir(parents=True,exist_ok=True)
    if not 3<=n<=24 or any(len(row)!=n for row in h) or any(h[i][j]!=h[j][i] for i in range(n) for j in range(n)):raise ValueError('matrix')
    protected=set(sorted(range(n),key=lambda i:(h[i][i],i))[:2])
    low=min(h[i][i] for i in range(n));active=list(range(n))
    adj={i:{j for j in range(n) if i!=j and h[i][j]} for i in range(n)}
    layers=[];plans=[]
    for s in range(8):
        if len(active)<=2:break
        # Restore symmetry: protected rows still participate in the graph.
        proxy=[[((low if i in protected else h[i][i]) if i==j else Q(int(j in adj[i]))) for j in active] for i in active]
        loc=work/f'layer{s}';loc.mkdir()
        got=plan(proxy,g,atlas,loc)
        if got is None:break
        ids,info=got;layer=[active[i] for i in ids]
        assert not (set(layer)&protected)
        assert all(j not in adj[i] for i in layer for j in layer if i!=j)
        layers.append(layer);plans.append(info)
        for i in layer:
            neighbors=adj.pop(i)
            for j in neighbors:adj[j].discard(i);adj[j].update(neighbors-{j})
        active=sorted(adj)
    if len(layers)<2:return dict(status='UNKNOWN',reason='NO_MULTILAYER_PLAN',layers=layers)
    source=work/'matrix.op';cert=work/'gap.cert'
    source.write_text(f'p op multiscale-gap {n} {g} {len(layers)}\n'+''.join(str(len(l))+' '+' '.join(map(str,l))+'\n' for l in layers)+'\n'.join(' '.join(map(str,row)) for row in h)+'\n')
    r=run(source,cert,10,audit_seconds=30)
    if r['status']=='PROVED':assert verify(source,cert)['status']=='PROVED'
    return dict(r,plan_layers=layers,atlas_plans=plans)
