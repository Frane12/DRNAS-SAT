"""YM20: pinned ATLAS chooses local trees, CORE certifies original finite gap."""
from collections import deque,Counter
from itertools import combinations
from fractions import Fraction as Q
from pathlib import Path
import hashlib,json,subprocess,sys
from atlas_decimation import PIN
from forest_gauge_verify import grid,verify_forest
from run import run

def solve(d,L,b,alpha,k,target,atlas,work):
    if subprocess.check_output(['git','-C',str(atlas),'rev-parse','HEAD'],text=True).strip()!=PIN:raise ValueError('ATLAS pin')
    if not 2<=d<=3 or not 2<=L or not 2<=b<=4 or L**d>256 or min(alpha,target)<=0:raise ValueError('dimensions')
    work.mkdir(parents=True,exist_ok=True)
    pts,edges,loops=grid(d,L);n=len(pts)
    blocks={}
    for i,p in enumerate(pts):blocks.setdefault(tuple(x//b for x in p),[]).append(i)
    roots=sorted(min(v) for v in blocks.values());rootset=set(roots)
    adj=[[] for _ in pts]
    for u,v in edges:
        if tuple(x//b for x in pts[u])==tuple(x//b for x in pts[v]):adj[u].append(v);adj[v].append(u)
    dist={v:0 for v in roots};todo=deque(roots)
    while todo:
        u=todo.popleft()
        for v in adj[u]:
            if v not in dist:dist[v]=dist[u]+1;todo.append(v)
    choices=[];clauses=[]
    for v in range(n):
        if v in rootset:continue
        group=[]
        for u in adj[v]:
            if dist[u]+1==dist[v]:choices.append((u,v));group.append(len(choices))
        clauses.append(group);clauses.extend([-i,-j] for i,j in combinations(group,2))
    p=work/'forest.cnf';out=work/'atlas'
    p.write_text(f'p cnf {len(choices)} {len(clauses)}\n'+''.join(' '.join(map(str,c))+' 0\n' for c in clauses))
    try:r=subprocess.run([sys.executable,str(atlas/'research/atlas30/solve.py'),str(p),str(out),'1','8'],capture_output=True,text=True,timeout=10)
    except subprocess.TimeoutExpired:return dict(status='UNKNOWN',reason='ATLAS_LIMIT')
    if r.returncode:raise RuntimeError(r.stderr[-2000:])
    res=json.loads((out/'result.json').read_text())
    if res['status']!='SAT':return dict(status='UNKNOWN',reason='ATLAS_NO_FOREST')
    a=json.loads((out/'model.json').read_text())
    if set(a)!=set(map(str,range(1,len(choices)+1))) or any(type(v)!=int or v not in (0,1) for v in a.values()) or not all(any(a[str(abs(l))]==int(l>0) for l in c) for c in clauses):raise ValueError('ATLAS model')
    parents={v:u for i,(u,v) in enumerate(choices,1) if a[str(i)]}
    tree={tuple(sorted((u,v))) for v,u in parents.items()}
    chords=[e for e in edges if e not in tree];idx={e:i+1 for i,e in enumerate(chords)}
    def below(u,v):
        while u not in rootset:
            if u==v:return True
            u=parents[u]
        return False
    def root(u):
        while u not in rootset:u=parents[u]
        return u
    rows=[]
    for e in edges:
        if e in idx:row=[[idx[e],'L',1]]
        else:
            child=e[0] if parents.get(e[0])==e[1] else e[1]
            row=[]
            for j,(u,v) in enumerate(chords,1):
                if below(u,child):row.append([j,'L',1])
                if below(v,child):row.append([j,'R',-1])
        rows.append(row)
    words=[]
    for loop in loops:
        w=[]
        for u,v in zip(loop,loop[1:]+loop[:1]):
            e=tuple(sorted((u,v)))
            if e in idx:w.append(idx[e] if u<v else -idx[e])
        words.append(w)
    weights=Counter()
    for row in rows:
        for j,side,sign in row:weights[j]+=len(row)
    src=work/'grid.json';cert=work/'forest.json'
    src.write_text(json.dumps(dict(d=d,L=L,b=b,alpha=str(alpha),k=str(k),target=str(target)),sort_keys=True))
    cert.write_text(json.dumps(dict(source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),
        parents=sorted([u,v] for v,u in parents.items()),roots=roots,chords=chords,
        fields=rows,endpoints=[[root(u),root(v)] for u,v in chords],words=words,
        form_factor=max(weights.values(),default=1)),sort_keys=True))
    audit=verify_forest(src,cert)
    op=work/'original.op';proof=work/'gap.cert'
    op.write_text(f'p op gauge-gap {n} {len(edges)} {len(loops)} {alpha} {target}\n'+''.join(f'{u} {v}\n' for u,v in edges)+''.join(f'{len(v)} {k} '+' '.join(map(str,v))+'\n' for v in loops))
    core=run(op,proof,10,audit_seconds=20)
    return dict(status=core['status'],forest=audit,core=core,atlas=dict(commit=PIN,model_verified=True,route=res.get('route')))
