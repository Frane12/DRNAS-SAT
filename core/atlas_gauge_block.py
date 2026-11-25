"""YM17: ATLAS plans degree-two suppression; CORE certifies the original gap."""
import hashlib,json,subprocess
from pathlib import Path
from fractions import Fraction as Q
from atlas_decimation import plan,PIN
from gauge_block_verify import verify_block
from run import run

def key(a,b):return tuple(sorted((a,b)))

def parse_graph(n,edges,loops):
    adj={i:set() for i in range(n)}
    weights={}
    for a,b in edges:
        if not (0<=a<n and 0<=b<n and a!=b) or key(a,b) in weights:raise ValueError('edge')
        adj[a].add(b);adj[b].add(a);weights[key(a,b)]=1
    seen=set()
    for k,v in loops:
        if len(v)<3 or len(set(v))!=len(v) or any(a not in adj for a in v):raise ValueError('loop')
        boundary=frozenset(key(a,b) for a,b in zip(v,v[1:]+v[:1]))
        if not boundary<=weights.keys() or boundary in seen:raise ValueError('loop edges')
        seen.add(boundary)
    return adj,weights

def solve(n,edges,loops,alpha,target,atlas,work):
    if subprocess.check_output(['git','-C',str(atlas),'rev-parse','HEAD'],text=True).strip()!=PIN:raise ValueError('ATLAS pin')
    if not 1<=n<=256 or alpha<=0 or target<=0:raise ValueError('parameters')
    work.mkdir(parents=True,exist_ok=True)
    adj,w=parse_graph(n,edges,loops)
    source=dict(n=n,edges=[list(e) for e in sorted(w)],loops=[[str(k),v] for k,v in loops],alpha=str(alpha),target=str(target))
    src=work/'graph.json';src.write_text(json.dumps(source,sort_keys=True))
    removed=[];plans=[];cycles=[list(v) for k,v in loops]
    for step in range(32):
        active=sorted(adj)
        def eligible(v):
            if len(adj[v])!=2:return False
            a,b=adj[v]
            return b not in adj[a]
        candidates={v for v in active if eligible(v)}
        if not candidates:break
        # Also exclude pairs sharing both neighbors, since suppressing both
        # could create parallel edges. A plan never licenses an invalid move.
        proxy=[[Q(2 if i in candidates else 0) if i==j else Q(int(j in adj[i] or (i in candidates and j in candidates and adj[i]==adj[j]))) for j in active] for i in active]
        loc=work/f'layer{step}';loc.mkdir()
        got=plan(proxy,Q(1),atlas,loc)
        if got is None:break
        ids,info=got;chosen=[active[i] for i in ids]
        layer=[]
        for v in chosen:
            if not eligible(v):continue
            a,b=sorted(adj[v])
            w[key(a,b)]=w.pop(key(a,v))+w.pop(key(v,b))
            adj[a].remove(v);adj[b].remove(v);adj[a].add(b);adj[b].add(a);del adj[v]
            cycles=[[x for x in c if x!=v] for c in cycles]
            if any(len(c)<3 for c in cycles):raise AssertionError('loop collapse')
            removed.append(v);layer.append(v)
        if not layer:break
        plans.append(dict(info,vertices=layer))
    if not removed:return dict(status='UNKNOWN',reason='NO_BLOCKING')
    cert=dict(source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),removed=removed,
        edges=[[a,b,length] for (a,b),length in sorted(w.items())],loops=cycles)
    cp=work/'block.json';cp.write_text(json.dumps(cert,sort_keys=True))
    audited=verify_block(src,cp)
    # Native CORE independently proves the same requested gap on the
    # original all-representation graph; no reduced graph is treated as a
    # different physical theory or passed off as a uniform-weight model.
    op=work/'original.op';proof=work/'gap.cert'
    op.write_text(f'p op gauge-gap {n} {len(edges)} {len(loops)} {alpha} {target}\n'+''.join(f'{a} {b}\n' for a,b in edges)+''.join(f'{len(v)} {k} '+' '.join(map(str,v))+'\n' for k,v in loops))
    result=run(op,proof,10,audit_seconds=20)
    if result['status']=='PROVED':
        if Q(result['gap_lower'])!=Q(audited['gap_lower']):raise ValueError('bound disagreement')
    return dict(status=result['status'],core=result,blocking=audited,atlas_plans=plans)
