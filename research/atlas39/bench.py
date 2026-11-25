"""Fresh-seed paired experiment; reference arms never enter ATLAS."""
import sys,time,json,hashlib,subprocess,random
from pathlib import Path
import hybrid as H
A=H.A
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'atlas31'))
import bench as B
def run(raw,out,baseline,case):
 out.mkdir(parents=True,exist_ok=True);p=out/'input.cnf';p.write_bytes(raw);rows=[]
 arms=['FUSED_WIDE','DEDUCT','REPAIR','AUTO','kissat','cadical'];shift=int(hashlib.sha256(raw).hexdigest()[:8],16)%len(arms);arms=arms[shift:]+arms[:shift]
 for arm in arms:
  d=out/arm;d.mkdir();t=time.monotonic();r={}
  try:
   if arm=='FUSED_WIDE':cmd=[sys.executable,str(R/'atlas38'/'autonomous.py'),str(p),str(d),arm,'25']
   elif arm in ('DEDUCT','REPAIR','AUTO'):cmd=[sys.executable,str(Path(__file__).with_name('hybrid.py')),str(p),str(d),arm,'25']
   else:cmd=[str(baseline/arm),'--no-binary',str(p),str(d/'proof.drup')]
   q=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
   (d/'solver.log').write_text(q.stdout+q.stderr)
   if arm in ('kissat','cadical'):
    r=dict(status={10:'SAT',20:'UNSAT',0:'UNKNOWN'}.get(q.returncode,'ERROR'))
    if r['status']=='SAT':
     a={}
     for l in q.stdout.splitlines():
      if l.startswith('v '):
       for v in map(int,l[2:].split()):
        if v:a[str(abs(v))]=int(v>0)
     (d/'model.json').write_text(json.dumps(a))
   else:
    if q.returncode:raise RuntimeError(q.stderr[-1000:])
    r=json.loads((d/'result.json').read_text())
   r['process_s']=time.monotonic()-t
   r['audit']='NONE'
   if r['status']=='UNSAT' and r.get('method')=='bdd':
    # Audit in its own hard-capped process.
    z=subprocess.run([sys.executable,str(R/'atlas38'/'bench.py'),'check',str(p),str(d)],capture_output=True,text=True,timeout=65)
    (d/'check.log').write_text(z.stdout+z.stderr)
    r['audit']='CUSTOM_BDD' if z.returncode==0 and 'BDD_VERIFIED' in z.stdout else 'CHECK_FAILED'
   elif r['status'] in ('SAT','UNSAT'):r['audit']=B.audit(raw,p,d,r)
  except subprocess.TimeoutExpired:
   if 'process_s' in r:r['audit']='VERIFY_TIMEOUT'
   else:r=dict(status='TIMEOUT',audit='NONE',process_s=30)
  except Exception as e:r.update(status='ERROR',audit='NONE',error=str(e))
  r.update(arm=arm,case=case,sha=hashlib.sha256(raw).hexdigest(),e2e_s=time.monotonic()-t)
  rows.append(r);print('A39_ROW',json.dumps(r),flush=True);(out/'rows.json').write_text(json.dumps(rows,indent=2))
def selftest(out):
 rng=random.Random(36011)
 for i in range(32):
  n=rng.randrange(3,9);raw=B.random_cnf(n,min(8*(n*(n-1)*(n-2)//6),rng.randrange(4,5*n)),36011+i)
  _,cs=A.S.M.parse(raw);truth=any(all(any(((a>>(abs(l)-1))&1)==int(l>0) for l in c) for c in cs) for a in range(1<<n))
  d=out/str(i);d.mkdir(parents=True);(d/'input.cnf').write_bytes(raw)
  active,proof,checks,unsat=H.deduction(cs,n,time.monotonic()+5)
  models=[a for a in range(1<<n) if all(any(((a>>(abs(l)-1))&1)==int(l>0) for l in c) for c in cs)]
  assert not unsat or not models
  assert all(all(any(((a>>(abs(l)-1))&1)==int(l>0) for l in c) for c in proof) for a in models)
  for mode in ('DEDUCT','REPAIR','AUTO'):
   r=H.solve(raw,d/mode,mode,2)
   assert r['status']=='UNKNOWN' or r['status']==('SAT' if truth else 'UNSAT'),(mode,r)
   if r['status']=='UNSAT' and r['method']!='bdd':assert B.audit(raw,(d/'input.cnf'),d/mode,r)=='STANDARD_DRAT'
   if r['status']=='SAT':assert B.verify_model(raw,json.loads((d/mode/'model.json').read_text()))
 print('A39_SELFTEST 96 truth controls and local entailment',flush=True)
if __name__=='__main__':
 if sys.argv[1]=='check':
  assert A.check_bdd(Path(sys.argv[2]).read_bytes(),Path(sys.argv[3]),time.monotonic()+60)
  print('BDD_VERIFIED')
 elif sys.argv[1]=='selftest':selftest(Path(sys.argv[2]))
 else:
  n=int(sys.argv[1]);rho=float(sys.argv[2]);out=Path(sys.argv[3]).resolve();base=Path(sys.argv[4]).resolve()
  cohort=sys.argv[5]
  for i in range(3):
   raw=B.random_cnf(n,round(n*rho),(380000 if cohort=='replay' else 390000)+n*100+round(rho*100)*10+i)
   run(raw,out/f'case{i}',base,f'{cohort}/{n}/{rho}/{i}')
