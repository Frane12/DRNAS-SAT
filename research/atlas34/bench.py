"""Paired DMD3 diagnostic; reference solvers never supply data to ATLAS."""
import sys,time,json,hashlib,subprocess,random
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'atlas31'))
import bench as B
def one(raw,out,base,case,arms=('MRC','SPARSE_FIXED','SPARSE_ADAPT','kissat','cadical')):
    out.mkdir(parents=True,exist_ok=True);p=out/'input.cnf';p.write_bytes(raw);rr=[]
    shift=int(hashlib.sha256(raw).hexdigest()[:4],16)%len(arms);arms=arms[shift:]+arms[:shift]
    for arm in arms:
        d=out/arm;d.mkdir();t=time.monotonic();r={}
        try:
            if arm=='MRC':cmd=[sys.executable,str(Path(B.__file__).with_name('mrc.py')),str(p),str(d),'12','25','1']
            elif arm.startswith('SPARSE'):cmd=[sys.executable,str(Path(__file__).with_name('sparse.py')),str(p),str(d),str(int(arm=='SPARSE_ADAPT'))]
            else:cmd=[str(base/arm),'--no-binary',str(p),str(d/'proof.drup')]
            q=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
            (d/'solver.log').write_text(q.stdout+q.stderr)
            if arm in ('kissat','cadical'):
                r=dict(status={10:'SAT',20:'UNSAT',0:'UNKNOWN'}.get(q.returncode,'ERROR'))
                if r['status']=='SAT':
                    a={}
                    for line in q.stdout.splitlines():
                        if line.startswith('v '):
                            for v in map(int,line[2:].split()):
                                if v:a[str(abs(v))]=int(v>0)
                    (d/'model.json').write_text(json.dumps(a))
            else:
                if q.returncode:raise RuntimeError(q.stderr[-1000:])
                r=json.loads((d/'result.json').read_text())
            r['process_s']=time.monotonic()-t
            r['audit']=B.audit(raw,p,d,r) if r['status'] in ('SAT','UNSAT') else 'NONE'
        except subprocess.TimeoutExpired:
            if 'process_s' in r:r['audit']='VERIFY_TIMEOUT'
            else:r=dict(status='TIMEOUT',audit='NONE',process_s=30)
        except Exception as e:r.update(status='ERROR',audit='NONE',error=str(e))
        r.update(arm=arm,case=case,sha=hashlib.sha256(raw).hexdigest(),e2e_s=time.monotonic()-t)
        rr.append(r);print('DMD3_ROW',json.dumps(r),flush=True);(out/'rows.json').write_text(json.dumps(rr,indent=2))
    return rr
def selftest(out):
    import sparse as S
    rng=random.Random(34001)
    for i in range(64):
        n=rng.randint(2,8);cs=[]
        for j in range(rng.randint(1,6*n)):
            cs.append(tuple(v*rng.choice((-1,1)) for v in rng.sample(range(1,n+1),rng.randint(1,min(n,4)))))
        raw=B.serialize(n,cs)
        expected='SAT' if any(all(any(((a>>(abs(l)-1))&1)==int(l>0) for l in c) for c in cs) for a in range(1<<n)) else 'UNSAT'
        for mode in (False,True):
            d=out/f'{i}_{int(mode)}';d.mkdir(parents=True);p=d/'input.cnf';p.write_bytes(raw)
            r=S.solve(raw,d,mode,5)
            assert r['status']==expected,(i,mode,r)
            assert B.audit(raw,p,d,r) in ('MODEL_VERIFIED','STANDARD_DRAT'),(i,mode,r)
    print('DMD3_SELFTEST 128/128 brute force and independent checks',flush=True)
if __name__=='__main__':
    mode=sys.argv[1];out=Path(sys.argv[2]).resolve()
    if mode=='selftest':selftest(out)
    else:
        base=Path(sys.argv[3]).resolve();n=int(sys.argv[4]);rho=float(sys.argv[5])
        for i in range(3):
            seed=(340000 if mode=='fresh' else 330000)+n*100+round(rho*100)*10+i
            raw=B.random_cnf(n,round(n*rho),seed)
            one(raw,out/f'case{i}',base,f'{mode}/{n}/{rho}/{i}')
