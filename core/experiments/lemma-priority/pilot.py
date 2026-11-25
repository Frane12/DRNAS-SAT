"""Precommitted paired experiment. Inputs are generated only after source hashes are frozen."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import platform

HERE=Path(__file__).resolve().parent
CORE=HERE.parents[1]
sys.path.insert(0,str(CORE))
from run import run

MODES=('default','table-first','table-pick-first','table-rank')
FAMILIES=('uniform','planted','balanced-planted')
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def generate(out):
    out.mkdir(parents=True,exist_ok=False)
    files=[CORE/'core.cpp',CORE/'lemma_priority.hpp',CORE/'run.py',CORE/'bin/drnas-core',
           HERE/'order.cpp',HERE/'pilot.py',HERE/'fixed.py']
    (out/'freeze.json').write_text(json.dumps(dict(files={str(x.relative_to(CORE)):digest(x) for x in files},
      rule='max product of Laplace-smoothed opposite-sign frequencies on original clauses',
      tie='first active candidate',seed=503181417,cap=5,audit=5,repetitions=3,modes=MODES,
      platform=platform.platform()),indent=2))
    rng=random.Random(503181417)
    manifest={}
    for i in range(12):
        family=FAMILIES[i%3]
        hidden=[rng.randrange(2) for _ in range(501)]
        cs=[]
        for _ in range(2130):
            vs=rng.sample(range(1,501),3)
            if family=='uniform':
                clause=[v*rng.choice((-1,1)) for v in vs]
            else:
                if family=='balanced-planted':
                    k=rng.choices((1,2,3),weights=(6,3,1))[0]
                    bits=[0,0,0]
                    for j in rng.sample(range(3),k):bits[j]=1
                else:
                    mask=rng.randrange(1,8)
                    bits=[(mask>>j)&1 for j in range(3)]
                clause=[v if hidden[v]==b else -v for v,b in zip(vs,bits)]
                assert any((lit>0)==hidden[abs(lit)] for lit in clause)
            cs.append(clause)
        path=out/f'H{i:02}.cnf'
        path.write_text('p cnf 500 2130\n'+''.join(' '.join(map(str,c))+' 0\n' for c in cs))
        manifest[path.stem]=dict(family=family,sha256=digest(path))
    manifest['F26']=dict(family='retrospective',sha256=digest(CORE/'regression/F26.cnf'))
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    return manifest

def lane(args):
    out,cpu,cases,manifest=args
    os.sched_setaffinity(0,{cpu})
    records=out/f'lane-{cpu}.jsonl'
    with records.open('x',buffering=1) as log:
        for rep in range(3):
            order=cases[:]
            random.Random(179211+rep).shuffle(order)
            for ident in order:
                src=CORE/'regression/F26.cnf' if ident=='F26' else out/(ident+'.cnf')
                assert digest(src)==manifest[ident]['sha256']
                base=12 if ident=='F26' else int(ident[1:])
                start=(base+rep)%len(MODES)
                for mode in MODES[start:]+MODES[:start]:
                    cert=out/f'{ident}-{rep+1}-{mode}.cert'
                    a=run(src,cert,5,mode,5)
                    assert a['status'] in ('SAT','UNSAT','UNKNOWN','TIMEOUT','AUDIT_LIMIT'),a
                    if manifest[ident]['family']!='uniform':assert a['status']!='UNSAT',a
                    log.write(json.dumps(dict(**a,id=ident,rep=rep+1,cpu=cpu))+'\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('out',type=Path)
    parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args()
    out=args.out.resolve();m=generate(out)
    cpus=sorted(os.sched_getaffinity(0))[:max(1,args.workers)]
    ids=list(m)
    with concurrent.futures.ProcessPoolExecutor(max_workers=len(cpus)) as pool:
        list(pool.map(lane,[(out,c,ids[i::len(cpus)],m) for i,c in enumerate(cpus)]))
    rows=[json.loads(s) for p in out.glob('lane-*.jsonl') for s in p.read_text().splitlines()]
    assert len({(r['id'],r['mode'],r['rep']) for r in rows})==len(rows)==156
    for ident in ids:
        assert len({r['status'] for r in rows if r['id']==ident and r['status'] in ('SAT','UNSAT')})<=1
