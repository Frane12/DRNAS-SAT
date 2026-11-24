"""Retrospective fixed cohort; synthetic compact controls, real source CNFs, public originals.
Each solver process receives only bytes. No name/status passed into solve.
"""
import json,sys,time,os,subprocess,hashlib,random
from pathlib import Path
from engine import solve
def worker(path,out):
    raw=Path(path).read_bytes()
    t=time.perf_counter();r=solve(raw);r['e2e_s']=round(time.perf_counter()-t,6)
    Path(out).write_text(json.dumps(r))
def bench(out,roots):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    files=[]
    for cohort,root in zip(('REGRESSION_ATLAS22','REAL6_EZSAT','PUBLIC_ORIGINALS'),roots):
        for p in sorted(Path(root).rglob('*.cnf')):files.append((cohort,p))
    # Six compact circuit cases, new generator controls, not public originals.
    for n in (8,16,32):
        for bad in (False,True):
            # chain of AND gates with fixed input assignments and expected output
            cs=[];v=n+2
            for i in range(n):
                a=1+i;b=n+1;z=2+i
                cs.extend([[-a,-b,z],[a,-z],[b,-z]])
            cs.extend([[1],[n+1],[-(n+1)] if bad else [n+1]]) if False else None
            # separate fixed operand; last z is n+1, operand n+2
            cs=[]
            for i in range(n):
                a=i+1;b=n+2;z=i+2
                cs.extend([[-a,-b,z],[a,-z],[b,-z]])
            cs.extend([[1],[n+2],[-(n+1)] if bad else [n+1]])
            p=out/f'compact_{n}_{int(bad)}.cnf';p.write_text(f'p cnf {v} {len(cs)}\n'+''.join(' '.join(map(str,c))+' 0\n' for c in cs));files.append(('COMPACT_CONTROLS',p))
    manifest=[{'cohort':c,'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for c,p in files]
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    rows=[]
    for i,((cohort,p),m) in enumerate(zip(files,manifest)):
        cert=out/f'proof_{i:03}.json';start=time.perf_counter()
        try:
            x=subprocess.run([sys.executable,__file__,'worker',str(p),str(cert)],capture_output=True,text=True,timeout=15)
            if x.returncode:raise RuntimeError(x.stderr[-1200:])
            r=json.loads(cert.read_text());assert r['sha256']==m['sha256']
            row={k:v for k,v in r.items() if k!='proof'}
        except subprocess.TimeoutExpired:
            row={'status':'UNKNOWN','reason':'15s_cap','e2e_s':round(time.perf_counter()-start,6)}
        except RuntimeError as e:
            row={'status':'ERROR','reason':str(e)}
        if cohort=='COMPACT_CONTROLS':
            assert row['status']==('UNSAT' if p.stem.endswith('_1') else 'SAT'),(p,row)
        row.update(m);rows.append(row);print('ATLAS27_ROW',json.dumps(row),flush=True)
        (out/'rows.json').write_text(json.dumps(rows,indent=2))
    for c in sorted(set(x['cohort'] for x in rows)):
        print('ATLAS27_COHORT',c,json.dumps({s:sum(x['status']==s and x['cohort']==c for x in rows) for s in ('SAT','UNSAT','UNKNOWN','ERROR')}),flush=True)
    print('ATLAS27_COMPLETE',len(rows),flush=True)
if __name__=='__main__':
    if sys.argv[1]=='worker':worker(*sys.argv[2:])
    else:bench(sys.argv[1],sys.argv[2:])
