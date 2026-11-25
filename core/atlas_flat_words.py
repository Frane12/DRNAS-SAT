"""YM32 exact flat SU(2) geometry; ATLAS plans a tree, word elimination is separate."""
from collections import deque,Counter
from fractions import Fraction as Q
from itertools import combinations
from pathlib import Path
import hashlib,json,subprocess,sys
from atlas_decimation import PIN
from flat_words_verify import read,words,eliminate,prod,I,verify

def solve(source,cert,atlas,work):
    raw,n,edges,faces=read(source)
    if subprocess.check_output(['git','-C',str(atlas),'rev-parse','HEAD'],text=True).strip()!=PIN:raise ValueError('ATLAS pin')
    adj=[[] for _ in range(n)]
    for a,b in edges:adj[a].append(b);adj[b].append(a)
    dist={0:0};q=deque([0])
    while q:
        a=q.popleft()
        for b in adj[a]:
            if b not in dist:dist[b]=dist[a]+1;q.append(b)
    if len(dist)!=n:return dict(status='UNKNOWN',reason='disconnected')
    choices=[];clauses=[]
    for i in range(1,n):
        g=[]
        for j in sorted(adj[i]):
            if dist[j]+1==dist[i]:choices.append((i,j));g.append(len(choices))
        clauses.append(g);clauses.extend([-a,-b] for a,b in combinations(g,2))
    work.mkdir(parents=True,exist_ok=True);cnf=work/'tree.cnf';out=work/'atlas'
    cnf.write_text(f'p cnf {len(choices)} {len(clauses)}\n'+''.join(' '.join(map(str,c))+' 0\n' for c in clauses))
    try:r=subprocess.run([sys.executable,str(atlas/'research/atlas30/solve.py'),str(cnf),str(out),'1','8'],capture_output=True,text=True,timeout=10)
    except subprocess.TimeoutExpired:return dict(status='UNKNOWN',reason='ATLAS_LIMIT')
    if r.returncode:raise RuntimeError(r.stderr[-2000:])
    if json.loads((out/'result.json').read_text())['status']!='SAT':return dict(status='UNKNOWN',reason='ATLAS_NO_TREE')
    m=json.loads((out/'model.json').read_text())
    if set(m)!=set(map(str,range(1,len(choices)+1))) or any(type(v)!=int or v not in (0,1) for v in m.values()) or not all(any(m[str(abs(l))]==int(l>0) for l in c) for c in clauses):raise ValueError('ATLAS model')
    tree=sorted(tuple(sorted(e)) for i,e in enumerate(choices,1) if m[str(i)])
    chords,rel=words(n,edges,faces,tree);remaining=set(range(1,len(chords)+1));steps=[];history=[]
    while remaining:
        candidates=[]
        for at,w in enumerate(rel):
            for g,k in Counter(map(abs,w)).items():
                if k==1:candidates.append((len(w),sum(x.count(g)+x.count(-g) for x in rel),g,at))
        if not candidates:break
        _,_,g,at=min(candidates)
        try:new,rhs=eliminate(rel,g,at)
        except ValueError:break
        rel=new;steps.append([g,at]);remaining.remove(g);history.append((g,rhs))
    c=dict(sha256=hashlib.sha256(raw).hexdigest(),tree=tree,steps=steps,
           remaining=sorted(remaining),relators=rel,kind='UNKNOWN')
    if not remaining:c['kind']='TRIVIAL'
    else:
        # Search commuting assignments on the reduced group presentation.
        # A single nontrivial generator with zero exponent sum in each
        # relator suffices. No claim that every flat assignment is found.
        for g in sorted(remaining):
            if any(w.count(g)!=w.count(-g) for w in rel):continue
            v={i:I for i in remaining};v[g]=(Q(3,5),Q(4,5),Q(0),Q(0))
            if any(prod(w,v)!=I for w in rel):continue
            for i,rhs in reversed(history):v[i]=prod(rhs,v)
            c.update(kind='WITNESS',values={str(i):list(map(str,z)) for i,z in v.items()},loop_generator=g)
            break
    Path(cert).write_text(json.dumps(c,sort_keys=True))
    return dict(verify(source,cert),atlas_used=True,atlas_commit=PIN)
