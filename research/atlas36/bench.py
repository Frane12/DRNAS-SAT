"""Fresh-seed paired experiment; reference arms never enter ATLAS."""
import sys,time,json,hashlib,subprocess,random
from pathlib import Path
import autonomous as A
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'atlas31'))
import bench as B
def run(raw,out,baseline,case):
 out.mkdir(parents=True,exist_ok=True);p=out/'input.cnf';p.write_bytes(raw);rows=[]
 arms=['SPARSE','RESTART','HANDOFF','kissat','cadical'];shift=int(hashlib.sha256(raw).hexdigest()[:8],16)%len(arms);arms=arms[shift:]+arms[:shift]
 for arm in arms:
  d=out/arm;d.mkdir();t=time.monotonic();r={}
  try:
   if arm=='SPARSE':cmd=[sys.executable,str(R/'atlas34/sparse.py'),str(p),str(d),'1']
   elif arm in ('HANDOFF','RESTART'):cmd=[sys.executable,str(Path(__file__).with_name('autonomous.py')),str(p),str(d),arm,'9']
   else:cmd=[str(baseline/arm),'--no-binary',str(p),str(d/'proof.drup')]
   q=subprocess.run(cmd,capture_output=True,text=True,timeout=10)
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
    z=subprocess.run([sys.executable,str(Path(__file__).resolve()),'check',str(p),str(d)],capture_output=True,text=True,timeout=20)
    (d/'check.log').write_text(z.stdout+z.stderr)
    r['audit']='CUSTOM_BDD' if z.returncode==0 and 'BDD_VERIFIED' in z.stdout else 'CHECK_FAILED'
   elif r['status'] in ('SAT','UNSAT'):r['audit']=B.audit(raw,p,d,r)
  except subprocess.TimeoutExpired:
   if 'process_s' in r:r['audit']='VERIFY_TIMEOUT'
   else:r=dict(status='TIMEOUT',audit='NONE',process_s=10)
  except Exception as e:r.update(status='ERROR',audit='NONE',error=str(e))
  r.update(arm=arm,case=case,sha=hashlib.sha256(raw).hexdigest(),e2e_s=time.monotonic()-t)
  rows.append(r);print('A36_ROW',json.dumps(r),flush=True);(out/'rows.json').write_text(json.dumps(rows,indent=2))
def selftest(out):
 rng=random.Random(36011)
 for i in range(32):
  n=rng.randrange(3,9);raw=B.random_cnf(n,min(8*(n*(n-1)*(n-2)//6),rng.randrange(4,5*n)),36011+i)
  _,cs=A.S.M.parse(raw);truth=any(all(any(((a>>(abs(l)-1))&1)==int(l>0) for l in c) for c in cs) for a in range(1<<n))
  d=out/str(i);d.mkdir(parents=True);z=A.symbolic(cs,list(range(1,n+1)),time.monotonic()+5)
  assert z['status']==('SAT' if truth else 'UNSAT'),z
  if truth:assert all(any(z['model'][abs(l)]==int(l>0) for l in c) for c in cs)
 print('A36_SELFTEST 32/32 symbolic truth enumeration',flush=True)
if __name__=='__main__':
 if sys.argv[1]=='check':
  assert A.check_bdd(Path(sys.argv[2]).read_bytes(),Path(sys.argv[3]),time.monotonic()+18)
  print('BDD_VERIFIED')
 elif sys.argv[1]=='selftest':selftest(Path(sys.argv[2]))
 else:
  n=int(sys.argv[1]);rho=float(sys.argv[2]);out=Path(sys.argv[3]).resolve();base=Path(sys.argv[4]).resolve()
  for i in range(3):
   raw=B.random_cnf(n,round(n*rho),360000+n*100+round(rho*100)*10+i)
   run(raw,out/f'case{i}',base,f'{n}/{rho}/{i}')
