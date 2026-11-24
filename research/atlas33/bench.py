"""Paired source-only test: archived discovery cases and fresh random seeds.
External solvers are diagnostic arms only. No artifacts or labels enter ATLAS.
"""
import sys,time,json,hashlib,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'atlas31'))
import bench as B
def one(raw,out,baseline,case):
    out.mkdir(parents=True,exist_ok=True);p=out/'input.cnf';p.write_bytes(raw);rr=[]
    arms=['MRC','UNIT','UNIT_BINARY','kissat','cadical'];shift=int(hashlib.sha256(raw).hexdigest()[:4],16)%5;arms=arms[shift:]+arms[:shift]
    for arm in arms:
        d=out/arm;d.mkdir();t=time.monotonic();r={}
        try:
            if arm=='MRC':
                cmd=[sys.executable,str(Path(B.__file__).with_name('mrc.py')),str(p),str(d),'12','25','1']
            elif arm in ('UNIT','UNIT_BINARY'):
                cmd=[sys.executable,str(Path(__file__).with_name('contract.py')),str(p),str(d),str(1 if arm=='UNIT' else 2)]
            else:cmd=[str(baseline/arm),'--no-binary',str(p),str(d/'proof.drup')]
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
                if q.returncode:raise RuntimeError(q.stderr[-1200:])
                r=json.loads((d/'result.json').read_text())
            r['process_s']=time.monotonic()-t
            r['audit']=B.audit(raw,p,d,r) if r['status'] in ('SAT','UNSAT') else 'NONE'
        except subprocess.TimeoutExpired:
            if 'process_s' in r:r['audit']='VERIFY_TIMEOUT'
            else:r=dict(status='TIMEOUT',audit='NONE',process_s=30)
        except Exception as e:r.update(status='ERROR',audit='NONE',error=str(e))
        r.update(arm=arm,case=case,sha=hashlib.sha256(raw).hexdigest(),e2e_s=time.monotonic()-t)
        rr.append(r);print('DMD2_ROW',json.dumps(r),flush=True);(out/'rows.json').write_text(json.dumps(rr,indent=2))
if __name__=='__main__':
    mode=sys.argv[1];out=Path(sys.argv[2]).resolve();base=Path(sys.argv[3]).resolve()
    if mode=='random':
        n=int(sys.argv[4]);rho=float(sys.argv[5])
        for i in range(3):one(B.random_cnf(n,round(n*rho),330000+n*100+round(rho*100)*10+i),out/f'case{i}',base,f'fresh/{n}/{rho}/{i}')
    elif mode=='archive':
        for i,p in enumerate(sorted(Path(sys.argv[4]).rglob('input.cnf'))):
            one(p.read_bytes(),out/f'case{i}',base,'archive/'+sys.argv[5]+'/'+str(i))
    elif mode=='selftest':
        for i,cs in enumerate([[(1,),(-1,)],[(1,2),(1,-2)],[(1,2),(-1,2),(1,-2),(-1,-2)],[(1,2),(-1,3),(-2,-3)]]):
            one(B.serialize(3,cs),out/f'case{i}',base,'selftest/'+str(i))
            rows=json.loads((out/f'case{i}'/'rows.json').read_text())
            assert all(r['audit'] in ('MODEL_VERIFIED','STANDARD_DRAT') for r in rows),rows
            assert len({r['status'] for r in rows})==1,rows
