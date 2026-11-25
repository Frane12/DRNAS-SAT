"""Frozen paired pilot. Fresh instances use known family generators, not unseen families."""
import argparse
import collections
import csv
import hashlib
import itertools
import json
import os
import pathlib
import random
import secrets
import subprocess
import sys
import time
from tests import write, hide, gf3
from verify import parse_cnf, check_model, verify

ROOT=pathlib.Path(__file__).resolve().parent
ARMS=['core','fusion1','general14','unified3','kissat','cadical']


def digest(data):return hashlib.sha256(data).hexdigest()


def norm_digest(n,cs):
    return digest(repr((n,sorted({tuple(sorted(set(c))) for c in cs if not any(-l in c for l in c)}))).encode())


def gate(vs,predicate):
    return [tuple(-v if b else v for v,b in zip(vs,bits))
            for bits in itertools.product([0,1],repeat=len(vs)) if not predicate(*bits)]


def random3(rng,vs,count,planted=None):
    out=[]
    while len(out)<count:
        c=tuple(v*rng.choice([-1,1]) for v in rng.sample(vs,3))
        if planted is None or any(planted[abs(l)]==(l>0) for l in c):out.append(c)
    return out


def make(rng,family,i):
    size=[24,32,40,56,80][i]
    if family in ('random3','planted3'):
        n=size if family=='random3' else 2*size
        planted={v:bool(rng.getrandbits(1)) for v in range(1,n+1)} if family=='planted3' else None
        return hide(rng,n,random3(rng,list(range(1,n+1)),round(n*(4.25 if planted is None else 5)),planted))
    if family=='gf3':return gf3(rng,5+3*i)
    if family=='xor-cycle':
        n=32+16*i;rhs=[rng.randrange(2) for _ in range(n)];rhs[-1]=sum(rhs[:-1])%2+(i%2);rhs[-1]%=2
        cs=[]
        for j in range(n):cs+=gate([j+1,(j+1)%n+1],lambda a,b,r=rhs[j]:a^b==r)
        return hide(rng,n,cs)
    if family=='capacity':
        slots=4+i;demands=slots+1;n=slots*demands
        cs=[tuple(slots*j+k+1 for k in range(slots)) for j in range(demands)]
        cs += [(-(slots*a+k+1),-(slots*b+k+1)) for k in range(slots) for a,b in itertools.combinations(range(demands),2)]
        return hide(rng,n,cs)
    if family=='colour':
        vertices=12+4*i;n=vertices*3;cs=[]
        for v in range(vertices):
            cs.append(tuple(3*v+c+1 for c in range(3)))
            cs += [(-(3*v+a+1),-(3*v+b+1)) for a,b in itertools.combinations(range(3),2)]
        colors=[rng.randrange(3) for _ in range(vertices)]
        edges={(a,b) for a,b in itertools.combinations(range(vertices),2) if colors[a]!=colors[b] and rng.random()<.4}
        if i%2:edges.update(itertools.combinations(range(4),2))
        cs += [(-(3*a+c+1),-(3*b+c+1)) for a,b in sorted(edges) for c in range(3)]
        return hide(rng,n,cs)
    if family=='circuit':
        n=10+i*2;values={v:rng.randrange(2) for v in range(1,n+1)};cs=[]
        for j in range(32+i*12):
            a,b=rng.sample(range(1,n+1),2);n+=1
            fun=(lambda x,y:x^y) if j%2 else (lambda x,y:x&y)
            values[n]=fun(values[a],values[b]);cs+=gate([a,b,n],lambda x,y,z,fun=fun:z==fun(x,y))
        cs += [(v if values[v] else -v,) for v in range(n-3,n+1)]
        return (n,cs) if i%2==0 else hide(rng,n,cs)
    if family=='components':
        k=20+8*i;cs=[]
        for block in range(3):cs+=random3(rng,list(range(1+block*k,1+(block+1)*k)),round(k*4.25))
        return hide(rng,3*k,cs)
    if family=='separator':
        sep=2+i%3;k=16+4*i;n=sep+2*k
        left=list(range(1,sep+k+1));right=list(range(1,sep+1))+list(range(sep+k+1,n+1))
        return hide(rng,n,random3(rng,left,round(len(left)*4.2))+random3(rng,right,round(len(right)*4.2)))
    if family=='mixed':
        n=size;cs=random3(rng,list(range(1,n+1)),round(n*4.1))
        for j in range(16):
            a,b=rng.sample(range(1,n+1),2);n+=1;cs+=gate([a,b,n],lambda x,y,z:z==(x^y if j%2 else x&y))
        return hide(rng,n,cs)
    raise ValueError(family)


def source_hashes():
    files=list((ROOT/'vendor').rglob('*.hpp'))+list((ROOT/'vendor').rglob('*.cpp'))+list((ROOT/'vendor').rglob('*.py'))
    files += [ROOT/p for p in ['core.cpp','build.sh','verify.py','run.py','tests.py','benchmark.py','prepare_references.sh']]
    return {str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in sorted(files)}


def generate(out):
    if (out/'manifest.json').exists():raise ValueError('panel already frozen')
    out.mkdir(exist_ok=True,parents=True);(out/'cnf').mkdir(exist_ok=True)
    freeze={'sources':source_hashes(),'seed':secrets.randbits(64),'arms':ARMS,'cap_s':1.0,'repetitions':1,
            'design':'50 prospective instances from 10 prespecified known families; normalized deduplication; archived regression panel separately',
            'audit_s':5,'wall_tolerance_s':.05,'external_kill_tolerance_s':.1}
    (out/'freeze.json').write_text(json.dumps(freeze,indent=2)+'\n')
    rng=random.Random(freeze['seed']);cases=[];seen=set()
    for x in json.loads((ROOT/'regression/manifest.json').read_text()):
        n,cs=parse_cnf(ROOT/x['file']);h=norm_digest(n,cs)
        if h in seen:continue
        seen.add(h);cases.append(dict(x,path=x['file'],normalized_sha256=h))
    fresh_index=0
    for family in ['random3','planted3','gf3','xor-cycle','capacity','colour','circuit','components','separator','mixed']:
        for i in range(5):
            n,cs=make(rng,family,i);h=norm_digest(n,cs)
            if h in seen:raise ValueError('duplicate prospective formula')
            seen.add(h);cid=f'N{fresh_index:02}';fresh_index+=1;p=out/'cnf'/f'{cid}.cnf';write(p,n,cs)
            cases.append(dict(id=cid,cohort='fresh',family=family,path='cnf/'+p.name,sha256=digest(p.read_bytes()),normalized_sha256=h))
    (out/'manifest.json').write_text(json.dumps(cases,indent=2)+'\n')
    print(json.dumps({'frozen':len(cases),'seed':freeze['seed']}),flush=True)


def model_from_output(text):
    return 'v '+' '.join(l[2:].strip() for l in text.splitlines() if l.startswith('v '))+'\n'


def attempt(case,arm,out,cap):
    source=(ROOT if case['cohort']=='replay' else out)/case['path'];prefix=out/'evidence'/f"{case['id']}.{arm}";cert=prefix.with_suffix(prefix.suffix+'.cert')
    n,cs=parse_cnf(source);tele={};rc=0
    if arm=='core':cmd=[ROOT/'bin/drnas-core',source,cert,str(cap)]
    elif arm=='general14':cmd=[ROOT/'bin/general14',source,cert,str(round(cap*1000)),'contract']
    elif arm=='fusion1':cmd=[ROOT/'bin/fusion1',source,str(cap),'fuse',prefix]
    elif arm=='unified3':cmd=[ROOT/'bin/unified3',source,cert,str(cap)]
    else:cmd=[ROOT/'bin'/arm,'--no-binary',source,cert]
    row={k:case[k] for k in ['id','cohort','family','sha256']};row.update(arm=arm,n=n,m=len(cs),status='UNKNOWN',certificate='NONE',audit_s=0,error='')
    started=time.monotonic()
    try:
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=cap+.1);rc=p.returncode;stdout=p.stdout;stderr=p.stderr
    except subprocess.TimeoutExpired:
        row.update(status='TIMEOUT',solve_s=time.monotonic()-started);return row
    row['solve_s']=time.monotonic()-started
    (out/'logs'/f"{case['id']}.{arm}.txt").write_text(stdout+'\n'+stderr)
    if row['solve_s']>cap+.05:row['status']='TIMEOUT';return row
    if arm=='fusion1':
        if rc!=0:row.update(status='ERROR',error=stderr);return row
        tele=json.loads(stdout);s=tele['status'];rc=10 if s=='SAT_VERIFIED' else 20 if s=='UNSAT_CHECKED' else 0
        if rc==10:cert=pathlib.Path(str(prefix)+'.model')
        elif rc==20:
            if tele['certificate']=='capacity':cert.write_text('drnas-capacity-v1\n'+pathlib.Path(str(prefix)+'.capacity').read_text())
            else:cert=pathlib.Path(str(prefix)+'.drat')
    elif arm=='core':
        for line in stdout.splitlines():
            if line.startswith('c {'):tele=json.loads(line[2:])
    row['telemetry']=json.dumps(tele)
    if rc not in (0,10,20):row.update(status='ERROR',error=stderr);return row
    if not rc:return row
    started=time.monotonic()
    try:
        if rc==10 and arm in ('kissat','cadical','unified3'):
            text=model_from_output(stdout);check_model(n,cs,text);cert.write_text(text);status,kind='SAT','MODEL'
        elif rc==20 and arm in ('kissat','cadical','unified3'):
            if arm=='unified3' and cert.read_text().startswith('{'):
                sys.path.insert(0,str(ROOT/'results/references/unified3/research/pcmax_capacity'))
                sys.path.insert(0,str(ROOT/'results/references/unified3/research/math4'))
                from check_clause_hall import check as check_hall
                from check_xor_units import verify as check_xor
                obj=json.loads(cert.read_text());kind='GF2' if obj.get('format')=='drnas-math4-xor-unit-v1' else 'HALL'
                (check_xor if kind=='GF2' else check_hall)(source.read_bytes(),obj)
            else:
                p=subprocess.run([ROOT/'bin/drat-trim',source,cert],capture_output=True,timeout=5)
                if p.returncode or b's VERIFIED' not in p.stdout.splitlines():raise ValueError('external DRAT checker rejected')
                kind='DRAT'
            status='UNSAT'
        else:
            p=subprocess.run([sys.executable,ROOT/'verify.py',source,cert,str(rc)],capture_output=True,text=True,timeout=5.1)
            checked=json.loads(p.stdout);status=checked['status'];kind=checked.get('certificate','NONE')
            if status=='REJECTED':row['error']=checked.get('error','')
        row.update(status=status,certificate=kind)
        if status in ('SAT','UNSAT'):row['evidence_sha256']=digest(cert.read_bytes())
    except subprocess.TimeoutExpired:row['status']='AUDIT_LIMIT'
    except Exception as error:row.update(status='REJECTED',error=str(error))
    row['audit_s']=time.monotonic()-started
    return row


def summarize(rows,out):
    summary={}
    for cohort in ['fresh','replay','all']:
        selected=[r for r in rows if cohort=='all' or r['cohort']==cohort];summary[cohort]={}
        for arm in ARMS:
            rr=[r for r in selected if r['arm']==arm];solved=[r for r in rr if r['status'] in ('SAT','UNSAT')]
            summary[cohort][arm]={'n':len(rr),'solved':len(solved),'statuses':dict(collections.Counter(r['status'] for r in rr)),
                'par2_s':sum(r['solve_s'] if r in solved else 2 for r in rr)/max(1,len(rr)),
                'certificates':dict(collections.Counter(r['certificate'] for r in solved))}
    summary['paired']={}
    for arm in ARMS[1:]:
        a={r['id'] for r in rows if r['arm']=='core' and r['status'] in ('SAT','UNSAT')}
        b={r['id'] for r in rows if r['arm']==arm and r['status'] in ('SAT','UNSAT')}
        summary['paired'][arm]={'core_only':sorted(a-b),'baseline_only':sorted(b-a)}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary),flush=True)


def benchmark(out):
    freeze=json.loads((out/'freeze.json').read_text());assert source_hashes()==freeze['sources'],'sources changed after freeze'
    cases=json.loads((out/'manifest.json').read_text());rows=[]
    for d in ['evidence','logs']:(out/d).mkdir(exist_ok=True)
    cpus=sorted(os.sched_getaffinity(0));os.sched_setaffinity(0,{cpus[0]})
    (out/'environment.json').write_text(json.dumps({'cpu':cpus[0],'platform':os.uname()._asdict() if hasattr(os.uname(),'_asdict') else list(os.uname()),'cap_s':freeze['cap_s'],'logical_cpus_per_solver':1,'serial':True},indent=2))
    stream=(out/'runs.jsonl').open('w')
    for i,case in enumerate(cases):
        assert digest(((ROOT if case['cohort']=='replay' else out)/case['path']).read_bytes())==case['sha256']
        panel=[]
        for arm in ARMS[i%len(ARMS):]+ARMS[:i%len(ARMS)]:
            row=attempt(case,arm,out,freeze['cap_s']);rows.append(row);panel.append(row);stream.write(json.dumps(row)+'\n');stream.flush()
        answers={r['status'] for r in panel if r['status'] in ('SAT','UNSAT')}
        assert len(answers)<=1,(case,answers)
        print(case['id'],' '.join(r['arm']+':'+r['status'] for r in panel),flush=True)
    stream.close()
    fields=sorted(set().union(*(r.keys() for r in rows)))
    with (out/'runs.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    summarize(rows,out)
    failures=[r for r in rows if r['status'] in ('ERROR','REJECTED')]
    if failures:raise RuntimeError(f'{len(failures)} errors or rejected results; inspect runs.csv')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['generate','run']);p.add_argument('--out',type=pathlib.Path,default=ROOT/'results/pilot');a=p.parse_args()
    (generate if a.command=='generate' else benchmark)(a.out.resolve())
