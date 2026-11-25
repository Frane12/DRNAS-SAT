"""YM30 operator-only route: actual pinned ATLAS chooses anchor paths."""
from collections import deque,defaultdict
from itertools import combinations
from fractions import Fraction as Q
from pathlib import Path
import hashlib,json,subprocess,sys
from atlas_decimation import PIN
from collective_verify import read_matrix,verify

def solve(source,cert,atlas,work):
    if subprocess.check_output(['git','-C',str(atlas),'rev-parse','HEAD'],text=True).strip()!=PIN:raise ValueError('ATLAS pin')
    raw,n,g,edges,p=read_matrix(source)
    work.mkdir(parents=True,exist_ok=True)
    adj=[[] for _ in range(n)]
    for i,j in edges:adj[i].append(j);adj[j].append(i)
    dist={i:0 for i in range(n) if p[i]>0};q=deque(dist)
    while q:
        i=q.popleft()
        for j in adj[i]:
            if j not in dist:dist[j]=dist[i]+1;q.append(j)
    bind=hashlib.sha256(raw).hexdigest()
    # Discover a soft mode independently of the lower proof. Unreachable
    # components have an exact zero mode; elsewhere distance gives a ramp.
    if len(dist)<n:v=[Q(int(i not in dist)) for i in range(n)]
    else:v=[Q(dist[i]) for i in range(n)]
    if not any(v):v=[Q(1)]*n
    den=sum(x*x for x in v)
    upper=(sum(w*(v[i]-v[j])**2 for (i,j),w in edges.items())+sum(a*x*x for a,x in zip(p,v)))/den
    if upper<g:
        c=dict(source_sha256=bind,kind='UPPER',vector=list(map(str,v)),bound=str(upper))
        Path(cert).write_text(json.dumps(c,sort_keys=True))
        return dict(verify(source,cert),route='collective_distance_witness',atlas_used=False)
    if len(dist)<n:return dict(status='UNKNOWN',reason='uncovered')
    choices=[];clauses=[]
    for i in range(n):
        if not dist[i]:continue
        group=[]
        for j in sorted(adj[i]):
            if dist[j]+1==dist[i]:choices.append((i,j));group.append(len(choices))
        clauses.append(group);clauses.extend([-a,-b] for a,b in combinations(group,2))
    parents={}
    if choices:
        cnf=work/'paths.cnf';out=work/'atlas'
        cnf.write_text(f'p cnf {len(choices)} {len(clauses)}\n'+''.join(' '.join(map(str,c))+' 0\n' for c in clauses))
        try:r=subprocess.run([sys.executable,str(atlas/'research/atlas30/solve.py'),str(cnf),str(out),'1','8'],capture_output=True,text=True,timeout=10)
        except subprocess.TimeoutExpired:return dict(status='UNKNOWN',reason='ATLAS_LIMIT')
        if r.returncode:raise RuntimeError(r.stderr[-2000:])
        result=json.loads((out/'result.json').read_text())
        if result['status']!='SAT':return dict(status='UNKNOWN',reason='NO_ATLAS_PATH')
        a=json.loads((out/'model.json').read_text())
        if set(a)!=set(map(str,range(1,len(choices)+1))) or any(type(v)!=int or v not in (0,1) for v in a.values()) or not all(any(a[str(abs(l))]==int(l>0) for l in c) for c in clauses):raise ValueError('ATLAS model')
        parents={i:j for k,(i,j) in enumerate(choices,1) if a[str(k)]}
    paths=[];load=defaultdict(Q)
    for i in range(n):
        path=[i]
        while dist[path[-1]]:path.append(parents[path[-1]])
        paths.append(path);root=path[-1]
        used=[tuple(sorted((a,b))) for a,b in zip(path,path[1:])]
        R=1/p[root]+sum(1/edges[e] for e in used)
        load[('pin',root)]+=R
        for a,b in used:load[('edge',a,b)]+=R
    lower=1/max(load.values())
    if lower<g:return dict(status='UNKNOWN',candidate_lower=str(lower),candidate_upper=str(upper))
    c=dict(source_sha256=bind,kind='LOWER',paths=paths,bound=str(lower))
    Path(cert).write_text(json.dumps(c,sort_keys=True))
    return dict(verify(source,cert),route='anchor_path_congestion',atlas_used=bool(choices),atlas_commit=PIN if choices else None)
