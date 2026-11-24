"""Prospective public cohort: frozen engine, raw CNF only, all failures reported."""
import sys,os,time,json,hashlib,urllib.request,lzma,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=json.loads((ROOT/'research/atlas289/prespec.json').read_text())
def freeze(idx,out):
    case=spec['cases'][idx]
    out.mkdir(parents=True,exist_ok=True)
    info=dict(case=idx,**case)
    try:
        req=urllib.request.Request(case['url']+'?context=cnf',headers={'User-Agent':'DRNAS-ATLAS289/1.0'})
        with urllib.request.urlopen(req,timeout=30) as r: z=r.read(20000001)
        assert len(z)<=20000000
        if z.startswith(b'\xfd7zXZ\x00'):
            raw=lzma.LZMADecompressor().decompress(z,max_length=20000001)
        else:raw=z
        assert len(raw)<=20000000
        assert hashlib.sha256(raw).hexdigest()==case['sha256'],'SHA256_MISMATCH'
        (out/'input.cnf').write_bytes(raw)
        info['freeze']='PASS'
        for line in raw.splitlines():
            if line.startswith(b'p cnf '):
                _,_,n,m=line.split();info.update(variables=int(n),clauses=int(m));break
        assert 'variables' in info
    except Exception as e:info.update(freeze='FAILED',error=str(e))
    (out/'freeze.json').write_text(json.dumps(info,indent=2))
    print('ATLAS289_FREEZE',json.dumps(info),flush=True)
    return info
def read_model(stdout,p):
    a={}
    for l in stdout.splitlines():
        if l.startswith('v '):
            for x in map(int,l[2:].split()):
                if x:
                    if abs(x) in a and a[abs(x)]!=int(x>0):return False
                    a[abs(x)]=int(x>0)
    clause=[];total=0
    for l in p.read_text().splitlines():
        if not l or l[0] in 'cp':continue
        for x in map(int,l.split()):
            if x:clause.append(x)
            else:
                if not any(abs(q) in a and a[abs(q)]==int(q>0) for q in clause):return False
                clause=[];total+=1
    return total>0 and not clause
def run(idx,out,baseline):
    info=freeze(idx,out);rows=[]
    p=(out/'input.cnf').resolve()
    # deterministic rotation balances fixed ordering across cases.
    arms=['ATLAS_GF2_ON','ATLAS_GF2_OFF','kissat','cadical']
    arms=arms[idx%4:]+arms[:idx%4]
    for arm in arms:
        d=out/arm;d.mkdir(exist_ok=True)
        t=time.monotonic();r={}
        if info['freeze']!='PASS':r=dict(status='UNAVAILABLE',audit='NO_INPUT')
        else:
            try:
                if arm.startswith('ATLAS'):
                    q=subprocess.run([sys.executable,str(ROOT/'research/atlas288/solve.py'),str(p),str(d),str(int(arm.endswith('ON')))],capture_output=True,text=True,timeout=180)
                    (d/'worker.log').write_text(q.stdout+q.stderr)
                    if q.returncode:raise RuntimeError(q.stderr[-1200:])
                    r=json.loads((d/'result.json').read_text())
                    if r['solve_s']>60:r.update(status='TIMEOUT',audit='SOLVE_CAP_EXCEEDED')
                    elif r['e2e_s']-r['solve_s']>120:r.update(audit='VERIFY_CAP_EXCEEDED')
                else:
                    proof=d/'proof.drat'
                    q=subprocess.run([str(Path(baseline).resolve()/arm),'--no-binary',str(p),str(proof)],capture_output=True,text=True,timeout=60)
                    s=time.monotonic()-t
                    (d/'solver.log').write_text(q.stdout+q.stderr)
                    status={10:'SAT',20:'UNSAT',0:'UNKNOWN'}.get(q.returncode,'ERROR')
                    r=dict(status=status,audit='NOT_VERIFIED',solve_s=s)
                    if status=='UNSAT':
                        try:
                            x=subprocess.run(['/tmp/drat-check',str(p),str(proof)],capture_output=True,text=True,timeout=120)
                            (d/'check.log').write_text(x.stdout+x.stderr)
                            r['audit']='EXTERNAL_DRAT_VERIFIED' if 's VERIFIED' in x.stdout else 'CHECK_FAILED'
                        except subprocess.TimeoutExpired:r['audit']='VERIFY_TIMEOUT'
                    elif status=='SAT':r['audit']='ORIGINAL_MODEL_VERIFIED' if read_model(q.stdout,p) else 'CHECK_FAILED'
                    r['e2e_s']=time.monotonic()-t
            except subprocess.TimeoutExpired:r=dict(status='TIMEOUT',audit='INCOMPLETE')
            except Exception as e:r=dict(status='ERROR',audit='INCOMPLETE',error=str(e))
        r.update(case=idx,family=info['family'],sha=info['sha256'],arm=arm,wall_s=time.monotonic()-t)
        rows.append(r);print('ATLAS289_ROW',json.dumps(r),flush=True)
        (out/'rows.json').write_text(json.dumps(rows,indent=2))
if __name__=='__main__':run(int(sys.argv[1]),Path(sys.argv[2]),sys.argv[3])
