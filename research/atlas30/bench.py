"""Fixed random 3-SAT cohort. Seed labels never enter solver.
All arms see same exact bytes and one CPU; separate standard and custom audits.
"""
import sys,time,json,hashlib,random,subprocess,os
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'atlas288'))
import solve as old
def cnf(n,m,seed):
    rng=random.Random(seed);cs=set()
    while len(cs)<m:
        vs=sorted(rng.sample(range(1,n+1),3))
        cs.add(tuple(v if rng.randrange(2) else -v for v in vs))
    return ('p cnf %d %d\n'%(n,m)+''.join(' '.join(map(str,c))+' 0\n' for c in sorted(cs))).encode()
def audit(p,d,r):
    raw=p.read_bytes();n,cs=old.C.E.g.parse(raw)
    if r['status']=='SAT':
        a=json.loads((d/'model.json').read_text())
        return 'MODEL_VERIFIED' if set(a)==set(map(str,range(1,n+1))) and all(v in (0,1) for v in a.values()) and all(any(a[str(abs(l))]==int(l>0) for l in c) for c in cs) else 'CHECK_FAILED'
    if r['route']=='DP':
        q=subprocess.run(['/tmp/drat-check',str(p),str(d/'projection.drup')],capture_output=True,text=True,timeout=60)
        return 'STANDARD_DRAT' if 's VERIFIED' in q.stdout and q.returncode==0 else 'CHECK_FAILED'
    core=(d/'core.cnf').read_bytes()
    old.provenance(raw,core,(d/'projection.drup').read_bytes())
    return old.replay(core,json.loads((d/'partition.json').read_text()))
def worker(n,rho,out,baseline):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True);baseline=Path(baseline).resolve()
    rows=[];cap=30
    for i in range(3):
        seed=300000+n*100+int(rho*100)*10+i
        p=out/f'case{i}.cnf';p.write_bytes(cnf(n,round(n*rho),seed))
        sha=hashlib.sha256(p.read_bytes()).hexdigest()
        arms=['atlas30','atlas30_ablation','kissat','cadical'];shift=i%len(arms);arms=arms[shift:]+arms[:shift]
        for arm in arms:
            d=out/f'{i}_{arm}';d.mkdir(exist_ok=True);t=time.monotonic();r={}
            try:
                if arm.startswith('atlas'):
                    q=subprocess.run([sys.executable,str(Path(__file__).with_name('solve.py')),str(p),str(d),str(int(arm=='atlas30')),str(cap)],capture_output=True,text=True,timeout=cap)
                    (d/'solver.log').write_text(q.stdout+q.stderr)
                    if q.returncode:raise RuntimeError(q.stderr[-1000:])
                    r=json.loads((d/'result.json').read_text())
                else:
                    proof=d/'proof.drat'
                    q=subprocess.run([str(baseline/arm),'--no-binary',str(p),str(proof)],capture_output=True,text=True,timeout=cap)
                    (d/'solver.log').write_text(q.stdout+q.stderr)
                    r=dict(status={10:'SAT',20:'UNSAT',0:'UNKNOWN'}.get(q.returncode,'ERROR'),audit='PENDING',route='BASELINE')
                    if r['status']=='SAT':
                        a={}
                        for l in q.stdout.splitlines():
                            if l.startswith('v '):
                                for v in map(int,l[2:].split()):
                                    if v:a[str(abs(v))]=int(v>0)
                        (d/'model.json').write_text(json.dumps(a))
                r['decision_s']=time.monotonic()-t
                if r['decision_s']>cap:r.update(status='TIMEOUT',audit='CAP')
                elif r['status'] in ('SAT','UNSAT'):
                    if arm.startswith('atlas') or r['status']=='SAT':r['audit']=audit(p,d,r)
                    else:
                        q=subprocess.run(['/tmp/drat-check',str(p),str(d/'proof.drat')],capture_output=True,text=True,timeout=60)
                        r['audit']='STANDARD_DRAT' if q.returncode==0 and 's VERIFIED' in q.stdout else 'CHECK_FAILED'
            except subprocess.TimeoutExpired:
                if 'decision_s' in r:r['audit']='VERIFY_TIMEOUT'
                else:r=dict(status='TIMEOUT',audit='INCOMPLETE',decision_s=cap)
            except Exception as e:r.update(status='ERROR',audit='INCOMPLETE',error=str(e))
            r.update(n=n,rho=rho,seed=seed,sha=sha,arm=arm,e2e_s=time.monotonic()-t)
            rows.append(r);print('ATLAS30_ROW',json.dumps(r),flush=True);(out/'rows.json').write_text(json.dumps(rows,indent=2))
if __name__=='__main__':worker(int(sys.argv[1]),float(sys.argv[2]),*sys.argv[3:])
