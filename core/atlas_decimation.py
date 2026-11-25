"""YM15: actual pinned ATLAS30 proposes a block, native CORE certifies the gap."""
from fractions import Fraction as Q
from pathlib import Path
from itertools import combinations
import argparse,json,subprocess,sys
from run import run
from operator_verify import verify

PIN='283af5a80491d31b08250c62e91a8118cc8c20bc'

def plan(h,g,atlas,work):
    n=len(h)
    # Keep at least one low-diagonal state. Cap the combinatorial encoding.
    low=min(h[i][i] for i in range(n))
    candidates=sorted((i for i in range(n) if h[i][i]>low+g),key=lambda i:(-h[i][i],i))[:12]
    if not candidates:return None
    m=len(candidates)
    conflict=[(-i-1,-j-1) for i,j in combinations(range(m),2) if h[candidates[i]][candidates[j]]]
    for k in range(min(m,n-1,4),0,-1):
        clauses=conflict+[tuple(i+1 for i in a) for a in combinations(range(m),m-k+1)]
        p=work/f'plan{k}.cnf';out=work/f'plan{k}'
        p.write_text(f'p cnf {m} {len(clauses)}\n'+''.join(' '.join(map(str,c))+' 0\n' for c in clauses))
        try:
            r=subprocess.run([sys.executable,str(atlas/'research/atlas30/solve.py'),str(p),str(out),'1','2'],
                             capture_output=True,text=True,timeout=4)
        except subprocess.TimeoutExpired:continue
        if r.returncode:raise RuntimeError(r.stderr[-2000:])
        res=json.loads((out/'result.json').read_text())
        if res['status']!='SAT':continue # never rely on an unverified UNSAT
        a=json.loads((out/'model.json').read_text())
        if set(a)!=set(map(str,range(1,m+1))) or any(type(v) is not int or v not in (0,1) for v in a.values()):
            raise ValueError('invalid ATLAS model')
        if not all(any(a[str(abs(l))]==int(l>0) for l in c) for c in clauses):raise ValueError('ATLAS source model')
        drop=sorted(candidates[i] for i in range(m) if a[str(i+1)])
        if len(drop)<k or len(drop)>=n:raise ValueError('plan cardinality')
        return drop,dict(atlas_commit=PIN,model_verified=True,plan_cnf=str(p.name),atlas_route=res.get('route'),requested_count=k)
    return None

def solve(h,g,atlas,work):
    if subprocess.check_output(['git','-C',str(atlas),'rev-parse','HEAD'],text=True).strip()!=PIN:
        raise ValueError('ATLAS source not pinned')
    work.mkdir(parents=True,exist_ok=True)
    got=plan(h,g,atlas,work)
    if got is None:return dict(status='UNKNOWN',reason='NO_ATLAS_PLAN')
    drop,info=got;n=len(h)
    source=work/'matrix.op';cert=work/'gap.cert'
    source.write_text(f'p op decimation-gap {n} {g} {len(drop)} '+' '.join(map(str,drop))+'\n'+'\n'.join(' '.join(map(str,row)) for row in h)+'\n')
    r=run(source,cert,10,audit_seconds=25)
    if r['status']=='PROVED': assert verify(source,cert)['status']=='PROVED'
    return dict(r,atlas=info,drop=drop)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('atlas',type=Path);p.add_argument('matrix',type=Path);p.add_argument('output',type=Path);p.add_argument('--gap',default='1')
    a=p.parse_args();h=[[Q(v) for v in row] for row in json.loads(a.matrix.read_text())]
    print(json.dumps(solve(h,Q(a.gap),a.atlas.resolve(),a.output.resolve())))
