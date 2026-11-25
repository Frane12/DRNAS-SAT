"""YM18: ATLAS30 plans a rooted tree; compile full SU(2) loop-coordinate operator."""
from collections import deque
from fractions import Fraction as Q
from pathlib import Path
from itertools import combinations
import hashlib,json,subprocess,sys
from atlas_decimation import PIN
from tree_gauge_verify import verify_tree
from run import run

def solve(n,edges,loops,alpha,target,atlas,work,root=0):
    if subprocess.check_output(['git','-C',str(atlas),'rev-parse','HEAD'],text=True).strip()!=PIN:raise ValueError('ATLAS pin')
    if not 2<=n<=256 or not 0<=root<n or alpha<=0 or target<=0:raise ValueError('parameters')
    work.mkdir(parents=True,exist_ok=True)
    edges=sorted(tuple(sorted(e)) for e in edges)
    if len(set(edges))!=len(edges) or any(not 0<=a<b<n for a,b in edges):raise ValueError('edge')
    adj=[[] for _ in range(n)]
    for a,b in edges:adj[a].append(b);adj[b].append(a)
    dist={root:0};q=deque([root])
    while q:
        v=q.popleft()
        for u in adj[v]:
            if u not in dist:dist[u]=dist[v]+1;q.append(u)
    if len(dist)!=n:raise ValueError('disconnected')
    choices=[];clauses=[]
    for v in range(n):
        if v==root:continue
        group=[]
        for u in adj[v]:
            if dist[u]+1==dist[v]:choices.append((u,v));group.append(len(choices))
        clauses.append(group)
        clauses.extend([-a,-b] for a,b in combinations(group,2))
    cnf=work/'tree.cnf';out=work/'atlas'
    cnf.write_text(f'p cnf {len(choices)} {len(clauses)}\n'+''.join(' '.join(map(str,c))+' 0\n' for c in clauses))
    p=subprocess.run([sys.executable,str(atlas/'research/atlas30/solve.py'),str(cnf),str(out),'1','5'],capture_output=True,text=True,timeout=8)
    if p.returncode:raise RuntimeError(p.stderr[-2000:])
    res=json.loads((out/'result.json').read_text())
    if res['status']!='SAT':return dict(status='UNKNOWN',reason='ATLAS_NO_TREE')
    model=json.loads((out/'model.json').read_text())
    if set(model)!=set(map(str,range(1,len(choices)+1))) or any(type(v)!=int or v not in (0,1) for v in model.values()) or not all(any(model[str(abs(l))]==int(l>0) for l in c) for c in clauses):raise ValueError('ATLAS model')
    parents={v:u for i,(u,v) in enumerate(choices,1) if model[str(i)]}
    tree={tuple(sorted((u,v))) for v,u in parents.items()}
    chords=[e for e in edges if e not in tree]
    if not chords:return dict(status='UNKNOWN',reason='NO_LOOPS')
    index={e:i+1 for i,e in enumerate(chords)}
    def below(u,v):
        while u!=root:
            if u==v:return True
            u=parents[u]
        return False
    # Field convention: +L on source, -R on target. Tree edges are
    # oriented parent -> child, chord edges low -> high.
    fields=[]
    for e in edges:
        if e in index:row=[[index[e],'L',1]]
        else:
            child=e[0] if parents.get(e[0])==e[1] else e[1]
            row=[]
            for i,(a,b) in enumerate(chords,1):
                if below(a,child):row.append([i,'L',1])
                if below(b,child):row.append([i,'R',-1])
        fields.append(row)
    words=[]
    for k,v in loops:
        row=[]
        for a,b in zip(v,v[1:]+v[:1]):
            e=tuple(sorted((a,b)))
            if e not in edges:raise ValueError('loop edge')
            if e in index:row.append(index[e] if a<b else -index[e])
        words.append(row)
    src=work/'graph.json';cert=work/'tree.json'
    src.write_text(json.dumps(dict(n=n,edges=edges,loops=[[str(k),v] for k,v in loops],alpha=str(alpha),target=str(target),root=root),sort_keys=True))
    cert.write_text(json.dumps(dict(source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),parents=sorted([u,v] for v,u in parents.items()),chords=chords,fields=fields,words=words),sort_keys=True))
    audit=verify_tree(src,cert)
    op=work/'original.op';proof=work/'gap.cert'
    op.write_text(f'p op gauge-gap {n} {len(edges)} {len(loops)} {alpha} {target}\n'+''.join(f'{a} {b}\n' for a,b in edges)+''.join(f'{len(v)} {k} '+' '.join(map(str,v))+'\n' for k,v in loops))
    result=run(op,proof,10,audit_seconds=20)
    return dict(status=result['status'],core=result,tree=audit,atlas=dict(commit=PIN,model_verified=True,route=res.get('route')))
