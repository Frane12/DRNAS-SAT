"""Frozen MRC pilot: generated 3SAT + signed permutations + archived public originals.
No label, seed or expected answer is passed into the solver.
"""
import sys,time,json,hashlib,random,subprocess,os,itertools
from pathlib import Path
import mrc
def serialize(n,cs):
    return ('p cnf %d %d\n'%(n,len(cs))+''.join(' '.join(map(str,c))+' 0\n' for c in cs)).encode()
def random_cnf(n,m,seed):
    rng=random.Random(seed);cs=set()
    while len(cs)<m:
        vs=sorted(rng.sample(range(1,n+1),3))
        cs.add(tuple(v if rng.randrange(2) else -v for v in vs))
    return serialize(n,sorted(cs))
def permute(raw,seed):
    n,cs=mrc.parse(raw);rng=random.Random(seed);p=list(range(1,n+1));rng.shuffle(p)
    signs=[rng.choice((-1,1)) for _ in p];out=[]
    for c in cs:
        d=[(1 if l>0 else -1)*p[abs(l)-1]*signs[abs(l)-1] for l in c]
        rng.shuffle(d);out.append(d)
    rng.shuffle(out);return serialize(n,out)
def verify_model(raw,a):
    # separate DIMACS token stream, no relation engine in validation
    tokens=[]
    for l in raw.decode().splitlines():
        if l.strip() and l.lstrip()[0] not in 'cp':tokens.extend(map(int,l.split()))
    if any(v not in (0,1) for v in a.values()):return False
    clause=[]
    for v in tokens:
        if v:clause.append(v)
        else:
            if not any(str(abs(l)) in a and a[str(abs(l))]==int(l>0) for l in clause):return False
            clause=[]
    return not clause
def audit(raw,p,d,r):
    if r['status']=='SAT':
        return 'MODEL_VERIFIED' if verify_model(raw,json.loads((d/'model.json').read_text())) else 'CHECK_FAILED'
    f=d/'proof.drup'
    if not f.exists() or r.get('audit')=='PROOF_INCOMPLETE':return 'NO_PROOF'
    q=subprocess.run(['/tmp/drat-check',str(p),str(f)],capture_output=True,text=True,timeout=30)
    (d/'checker.log').write_text(q.stdout+q.stderr)
    return 'STANDARD_DRAT' if q.returncode==0 and 's VERIFIED' in q.stdout else 'CHECK_FAILED'
def one(raw,out,baseline,label):
    out.mkdir(parents=True,exist_ok=True);p=out/'input.cnf';p.write_bytes(raw);rows=[]
    arms=['MRC','MRC_FIXED','kissat','cadical'];offset=int(hashlib.sha256(raw).hexdigest()[:4],16)%4;arms=arms[offset:]+arms[:offset]
    for arm in arms:
        d=out/arm;d.mkdir();t=time.monotonic();r={}
        try:
            if arm.startswith('MRC'):
                q=subprocess.run([sys.executable,str(Path(__file__).with_name('mrc.py')),str(p),str(d),'12','25',str(int(arm=='MRC'))],capture_output=True,text=True,timeout=30)
                (d/'solver.log').write_text(q.stdout+q.stderr)
                if q.returncode:raise RuntimeError(q.stderr[-1500:])
                r=json.loads((d/'result.json').read_text())
            else:
                q=subprocess.run([str(baseline/arm),'--no-binary',str(p),str(d/'proof.drup')],capture_output=True,text=True,timeout=30)
                (d/'solver.log').write_text(q.stdout+q.stderr)
                r=dict(status={10:'SAT',20:'UNSAT',0:'UNKNOWN'}.get(q.returncode,'ERROR'))
                if r['status']=='SAT':
                    a={}
                    for line in q.stdout.splitlines():
                        if line.startswith('v '):
                            for v in map(int,line[2:].split()):
                                if v:a[str(abs(v))]=int(v>0)
                    (d/'model.json').write_text(json.dumps(a))
            r['process_s']=time.monotonic()-t
            r['audit']=audit(raw,p,d,r) if r['status'] in ('SAT','UNSAT') else 'NONE'
        except subprocess.TimeoutExpired:
            if 'process_s' in r:r['audit']='VERIFY_TIMEOUT'
            else:r=dict(status='TIMEOUT',audit='NONE',process_s=30)
        except Exception as e:r.update(status='ERROR',audit='NONE',error=str(e))
        r.update(arm=arm,case=label,sha=hashlib.sha256(raw).hexdigest(),e2e_s=time.monotonic()-t)
        print('MRC_ROW',json.dumps(r),flush=True);rows.append(r)
        (out/'rows.json').write_text(json.dumps(rows,indent=2))
    return rows
def selftest(out):
    out.mkdir(parents=True,exist_ok=True);rng=random.Random(31001)
    for i in range(80):
        n=rng.randint(3,8);m=rng.randint(2,6*n)
        raw=random_cnf(n,m,i+31001) if m<=8*(n*(n-1)*(n-2)//6) else random_cnf(n,8,i+31001)
        nn,cs=mrc.parse(raw);expected=any(all(any(((a>>(abs(l)-1))&1)==int(l>0) for l in c) for c in cs) for a in range(1<<n))
        for j,b in enumerate((raw,permute(raw,i))):
            d=out/f'{i}_{j}';d.mkdir();p=d/'test.cnf';p.write_bytes(b)
            assert mrc.histogram(mrc.extract(cs))==mrc.histogram(mrc.extract(mrc.parse(b)[1]))
            r=mrc.solve(b,d,width=12,cap=10)
            assert r['status']==('SAT' if expected else 'UNSAT'),(i,j,r)
            assert audit(b,p,d,r) in ('MODEL_VERIFIED','STANDARD_DRAT'),(i,j,r)
    print('MRC_SELFTEST 160/160 exact brute-force and independent checks',flush=True)
if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='selftest':selftest(Path(sys.argv[2]))
    elif mode=='random':
        n=int(sys.argv[2]);rho=float(sys.argv[3]);out=Path(sys.argv[4]).resolve();base=Path(sys.argv[5]).resolve()
        for i in range(3):
            raw=random_cnf(n,round(n*rho),310000+n*100+round(rho*100)*10+i)
            a=one(raw,out/f'case{i}',base,f'random/{n}/{rho}/{i}')
            if i==0:
                b=one(permute(raw,31000+n),out/'permuted',base,f'random/{n}/{rho}/{i}/signed')
                x=next(r for r in a if r['arm']=='MRC');y=next(r for r in b if r['arm']=='MRC')
                if 'initial_motifs' in x and 'initial_motifs' in y:assert x['initial_motifs']==y['initial_motifs']
    elif mode=='public':
        p=Path(sys.argv[2]);out=Path(sys.argv[3]).resolve();base=Path(sys.argv[4]).resolve();label=sys.argv[5]
        one(p.read_bytes(),out,base,label)
