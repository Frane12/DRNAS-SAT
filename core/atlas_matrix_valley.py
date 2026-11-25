"""ATLAS plans oscillator energy allocation; no perturbative expansion."""
from fractions import Fraction as Q
from collections import Counter
from itertools import combinations
from pathlib import Path
from math import isqrt
import json,hashlib,sys,subprocess
from atlas_decimation import PIN
from matrix_valley_verify import read,verify

def solve(source,cert,atlas,work):
    raw,n,a,w=read(source);bind=hashlib.sha256(raw).hexdigest()
    if subprocess.check_output(['git','-C',str(atlas),'rev-parse','HEAD'],text=True).strip()!=PIN:raise ValueError('ATLAS pin')
    adj=[[] for _ in range(n)]
    for i,j in w:adj[i].append(j);adj[j].append(i)
    for i,x in enumerate(adj):
        if not x:
            Path(cert).write_text(json.dumps(dict(sha256=bind,kind='FREE',vertex=i)))
            return dict(verify(source,cert),atlas_used=False)
    choices=[];groups=[];incoming=[[] for _ in range(n)]
    for i in range(n):
        g=[]
        for j in sorted(adj[i]):
            choices.append((i,j));g.append(len(choices));incoming[j].append(len(choices))
        groups.append(g)
    base=[]
    for g in groups:
        base.append(g);base.extend([-i,-j] for i,j in combinations(g,2))
    work.mkdir(parents=True,exist_ok=True)
    model=None
    for cap in range(1,max(map(len,incoming))+1):
        # Limit combinatorial expansion, then use uncapped exact coverage.
        if cap>3 and cap<max(map(len,incoming)):continue
        clauses=base+[[-i for i in c] for group in incoming for c in combinations(group,cap+1)]
        cnf=work/f'plan{cap}.cnf';out=work/f'atlas{cap}'
        cnf.write_text(f'p cnf {len(choices)} {len(clauses)}\n'+''.join(' '.join(map(str,c))+' 0\n' for c in clauses))
        try:r=subprocess.run([sys.executable,str(atlas/'research/atlas30/solve.py'),str(cnf),str(out),'1','8'],capture_output=True,text=True,timeout=10)
        except subprocess.TimeoutExpired:continue
        if r.returncode:raise RuntimeError(r.stderr[-2000:])
        result=json.loads((out/'result.json').read_text())
        if result['status']!='SAT':continue
        m=json.loads((out/'model.json').read_text())
        if set(m)!=set(map(str,range(1,len(choices)+1))) or any(type(x)!=int or x not in (0,1) for x in m.values()) or not all(any(m[str(abs(l))]==int(l>0) for l in c) for c in clauses):raise ValueError('model')
        model=[p for k,p in enumerate(choices,1) if m[str(k)]]
        break
    if model is None:return dict(status='UNKNOWN',reason='ATLAS_LIMIT')
    load=Counter(j for i,j in model);alloc=[];slopes=[Q(0)]*n
    for i,j in model:
        e=tuple(sorted((i,j)));t=a[j]/(2*load[j]);v=w[e]/2
        # rational underestimate of 2 sqrt(t*v)
        z=4*t*v;scale=10**6;k=Q(isqrt((z.numerator*scale**2)//z.denominator),scale)
        if k<=0:return dict(status='UNKNOWN',reason='RATIONAL_PRECISION')
        alloc.append([i,j,str(t),str(v),str(k)]);slopes[i]+=k
    c=dict(sha256=bind,kind='COERCIVE',allocations=alloc,slopes=list(map(str,slopes)))
    Path(cert).write_text(json.dumps(c,sort_keys=True))
    return dict(verify(source,cert),atlas_used=True,atlas_commit=PIN,chosen_load=max(load.values()))
