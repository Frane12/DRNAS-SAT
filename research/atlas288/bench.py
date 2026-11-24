"""Single CPU paired original-CNF run. Unique SHA cases, one repeat pilot.
Baselines generate proof and independently verify it; ATLAS uses composite proof.
"""
import sys,json,time,hashlib,subprocess,os
from pathlib import Path
def main(real,extra,baseline,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    files=[];seen=set()
    for cohort,root in [('REGRESSION_REAL6',real),('ADDITIONAL_ATLAS22',extra)]:
        for p in sorted(Path(root).rglob('*.cnf')):
            h=hashlib.sha256(p.read_bytes()).hexdigest()
            if h in seen:continue
            seen.add(h);files.append((cohort,p,h))
    # additional novel constructed controls: signed/distributed constraints, no training.
    for n in (12,24):
        for bad in (0,1):
            cs=[]
            for i in range(1,n):
                cs.extend([[-i,i+1],[i,-(i+1)]])
            cs.extend([[1],[-n] if bad else [n]])
            p=out/f'new_chain_{n}_{bad}.cnf'
            p.write_text(f'p cnf {n} {len(cs)}\n'+''.join(' '.join(map(str,c))+' 0\n' for c in cs))
            h=hashlib.sha256(p.read_bytes()).hexdigest();files.append(('NEW_CONSTRUCTED',p,h))
    (out/'manifest.json').write_text(json.dumps([dict(cohort=c,path=str(p),sha=h) for c,p,h in files],indent=2))
    rows=[]
    for j,(cohort,p,h) in enumerate(files):
        for arm in ('ATLAS_GF2_OFF','ATLAS_GF2_ON','kissat','cadical'):
            d=out/f'{j:02}_{arm}';d.mkdir(exist_ok=True)
            t=time.monotonic()
            try:
                if arm.startswith('ATLAS'):
                    q=subprocess.run([sys.executable,str(Path(__file__).with_name('solve.py')),str(p),str(d),str(int(arm.endswith('ON')))],capture_output=True,text=True,timeout=60)
                    if q.returncode:raise RuntimeError(q.stderr[-1800:])
                    r=json.loads((d/'result.json').read_text())
                    r['process_e2e_s']=time.monotonic()-t
                else:
                    proof=d/'proof.drat'
                    q=subprocess.run([str(Path(baseline)/arm),'--no-binary',str(p),str(proof)],capture_output=True,text=True,timeout=60)
                    solve_s=time.monotonic()-t
                    (d/'solver.log').write_text(q.stdout+q.stderr)
                    status={10:'SAT',20:'UNSAT',0:'UNKNOWN'}.get(q.returncode,'ERROR')
                    audit='NOT_VERIFIED'
                    if status=='UNSAT':
                        x=subprocess.run(['/tmp/drat-check',str(p),str(proof)],capture_output=True,text=True,timeout=120)
                        (d/'check.log').write_text(x.stdout+x.stderr)
                        audit='EXTERNAL_DRAT_VERIFIED' if 's VERIFIED' in x.stdout else 'CHECK_FAILED'
                    elif status=='SAT':
                        a={}
                        for line in q.stdout.splitlines():
                            if line.startswith('v '):
                                for l in map(int,line[2:].split()):
                                    if l:a[abs(l)]=int(l>0)
                        from solve import C
                        n,cs=C.E.g.parse(p.read_bytes())
                        audit='ORIGINAL_MODEL_VERIFIED' if all(any(abs(l) in a and a[abs(l)]==(l>0) for l in c) for c in cs) else 'CHECK_FAILED'
                    r=dict(status=status,audit=audit,solve_s=solve_s,e2e_s=time.monotonic()-t,process_e2e_s=time.monotonic()-t)
            except subprocess.TimeoutExpired:
                r=dict(status='TIMEOUT',audit='INCOMPLETE',process_e2e_s=time.monotonic()-t)
            except Exception as e:r=dict(status='ERROR',audit='INCOMPLETE',error=str(e),process_e2e_s=time.monotonic()-t)
            r.update(cohort=cohort,file=p.name,path=str(p),sha=h,arm=arm)
            rows.append(r);print('ATLAS288_ROW',json.dumps(r),flush=True)
            (out/'rows.json').write_text(json.dumps(rows,indent=2))
    print('ATLAS288_COMPLETE',len(rows),flush=True)
if __name__=='__main__':main(*sys.argv[1:])
