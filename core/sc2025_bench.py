"""SC2025 Main Track: fixed first 24 distinct families in hash order, original CNF bytes."""
import argparse
import collections
import hashlib
import json
import lzma
import os
from pathlib import Path
import time
import urllib.request
from benchmark import attempt
from strategy_frontier_bench import create
from tests import write
from run import run as native
import strategy
import random

# https://benchmark-database.de/?context=cnf&track=main_2025
# Fixed from the public catalog in hash order; ignore result column.
PANEL=[
('00d5a43a481477fa4d56a2ce152a6cfb','argumentation'),
('00fd8ac9acd186a7a78a2c4d92f90de1','md5-equivalence-checking'),
('0205e2dffaef93a90c239df31755f2e1','belpyramid-puzzle'),
('032941f5f28c9ac53fa1c80d35f3206f','graceful-production'),
('03e852aa864cfe6eb49c264b462b8157','multiplier-verification'),
('04648cef5bed430ab6429991fa9e107d','ramsey-numbers'),
('04f43bb4a4f2c193a18e7195a4fd8e41','risc-instruction-removal-golcrest'),
('053e06424279f5cfec8bb14dfa9af23c','risc-instruction-removal-subrv'),
('062f58e44eb73f9274b57af5092cad90','rooks'),
('06d2ca2ee0b47f00d93090495f7fd4f4','clique-coloring'),
('07cea7a64248a60d509368d09d3057c2','hardware-model-checking'),
('081f111af59344b61346367a930e24f6','scheduling'),
('0876c518e5653369e20fb1ee0bb8db40','crafted-cec'),
('08d56c03e6561f6b9bec2e3f344ea3de','coloring'),
('0a8a4c28d27228e954354ea0a6e7f16c','sat-x'),
('0aa22564d00e9716519918d84b25c4a7','sudoku'),
('0ae917c2e0c1d39cbe411c29b2f5ff08','discrete-logarithm'),
('0c0430a68f147be18ab3fded07f30fdb','oddball-weighing'),
('0c9bcbc815cf0f109b7aeef3fbffc42d','minimal-disagreement-parity'),
('0ccb0f855352783a972be45188bf3164','set-covering'),
('0ed8c06438673f179985a79b9d6a9fe4','graph-isomorphism'),
('115fa7f61704bc12b2373aa471bc434f','circuit-multiplier'),
('16c999d046885c8e51f196e60c34d966','planning'),
('16ff47a05b769ed6a04c7175cfc6da55','circuit-equivalence-checking'),
]
ARMS=('default','cold','warm','kissat','cadical')
CAP=10.0
AUDIT=5.0
RAW_LIMIT=128*1024*1024
ZIP_LIMIT=64*1024*1024
OK={'SAT','UNSAT'}

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def download(case,out):
    target=out/case['path'];compressed=target.with_suffix('.xz')
    start=time.monotonic()
    try:
        with urllib.request.urlopen(case['url'],timeout=30) as inp,compressed.open('wb') as dst:
            size=0
            while True:
                if time.monotonic()-start>120:raise TimeoutError('download deadline')
                chunk=inp.read(1024*1024)
                if not chunk:break
                size+=len(chunk)
                if size>ZIP_LIMIT:raise ValueError('compressed size limit')
                dst.write(chunk)
        total=0
        with lzma.open(compressed,'rb') as inp,target.open('wb') as dst:
            for chunk in iter(lambda:inp.read(1024*1024),b''):
                total+=len(chunk)
                if total>RAW_LIMIT:raise ValueError('CNF size limit')
                dst.write(chunk)
        with target.open('rb') as f:
            for line in f:
                if line.startswith(b'p cnf '):
                    _,_,n,m=line.split();case.update(n=int(n),m=int(m));break
            else:raise ValueError('no DIMACS header')
        case.update(sha256=sha(target),bytes=total,download='OK')
    except Exception as e:
        target.unlink(missing_ok=True)
        case.update(download='UNAVAILABLE',download_error=str(e))
    finally:compressed.unlink(missing_ok=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    for d in ('cnf','evidence','logs'):(out/d).mkdir()
    cpus=sorted(os.sched_getaffinity(0));os.sched_setaffinity(0,{cpus[0]})
    panel=[dict(id=f'SC{i:02}',family=f,gbd_hash=h,path=f'cnf/SC{i:02}.cnf',
                url=f'https://benchmark-database.de/file/{h}?context=cnf') for i,(h,f) in enumerate(PANEL)]
    (out/'selection.json').write_text(json.dumps(panel,indent=2))
    (out/'protocol.json').write_text(json.dumps(dict(commit=os.getenv('GITHUB_SHA'),cap_s=CAP,audit_s=AUDIT,
        cpu=cpus[0],arms=ARMS,selection='first 24 distinct families in catalog hash order',training='synthetic only',
        max_raw=RAW_LIMIT,max_compressed=ZIP_LIMIT,training_seed=2611202697),indent=2))
    for case in panel:
        download(case,out)
        print('SC2025_SOURCE '+json.dumps(case),flush=True)
    (out/'manifest.json').write_text(json.dumps(panel,indent=2))
    # Synthetic training never reads the competition instances or their labels.
    rng=random.Random(2611202697);mem=out/'policy.json';train=[]
    for i in range(40):
        fam=('random3','planted3','mixed','separator')[i//10]
        n,cs,expected=create(rng,fam,i%5,(i//5)%2)
        src=out/'cnf'/f'train{i:02}.cnf';write(src,n,cs)
        r=strategy.run(str(src),str(out/'evidence'/f'train{i:02}.cert'),2.0,AUDIT,mem,False)
        if expected and r['status'] in OK and r['status']!=expected:raise RuntimeError('training contradiction')
        train.append(dict(id=i,family=fam,**r))
        print('SC2025_TRAIN '+json.dumps(train[-1]),flush=True)
    (out/'training.json').write_text(json.dumps(train,indent=2))
    frozen=mem.read_bytes() if mem.exists() else b''
    rows=[];paired=collections.Counter();errors=0
    with (out/'rows.jsonl').open('w') as stream:
        for i,case in enumerate(panel):
            src=out/case['path'];results={}
            if case['download']=='OK':assert sha(src)==case['sha256']
            for arm in ARMS[i%5:]+ARMS[:i%5]:
                cert=out/'evidence'/f"{case['id']}.{arm}.cert";started=time.monotonic()
                try:
                    if case['download']!='OK':r=dict(status='INPUT_UNAVAILABLE',error=case['download_error'])
                    elif arm in ('kissat','cadical'):r=attempt(dict(case,cohort='fresh'),arm,out,CAP)
                    elif arm=='warm':r=strategy.run(str(src),str(cert),CAP,AUDIT,mem,True)
                    else:r=native(str(src),str(cert),CAP,'default' if arm=='default' else 'freedom',AUDIT)
                except (OSError,ValueError,MemoryError,RuntimeError) as e:r=dict(status='ERROR',error=str(e))
                r.update(case,arm=arm,e2e_s=time.monotonic()-started)
                if r['status'] in OK:
                    if not cert.is_file():raise RuntimeError('missing evidence')
                    r['evidence_sha256']=sha(cert)
                else:cert.unlink(missing_ok=True)
                if r['status'] in ('ERROR','REJECTED') or 'strategy_error' in r:errors+=1
                results[arm]=r;rows.append(r)
                stream.write(json.dumps(r)+'\n');stream.flush()
                print('SC2025_ROW '+json.dumps(r),flush=True)
            answers={r['status'] for r in results.values() if r['status'] in OK}
            if len(answers)>1:raise RuntimeError('conflicting verified answers')
            if case['download']=='OK':
                for other in ('default','cold','kissat','cadical'):
                    x=results['warm']['status'] in OK;y=results[other]['status'] in OK
                    paired[other+':'+('both' if x and y else 'warm_only' if x else 'other_only' if y else 'neither')]+=1
    assert (mem.read_bytes() if mem.exists() else b'')==frozen
    summary=dict(selected=len(panel),available=sum(c['download']=='OK' for c in panel),errors=errors,paired=dict(paired))
    for arm in ARMS:
        rr=[r for r in rows if r['arm']==arm];valid=[r for r in rr if r['download']=='OK']
        summary[arm]=dict(statuses=dict(collections.Counter(r['status'] for r in rr)),
            solved=sum(r['status'] in OK for r in rr),
            par2_s=sum(r.get('solve_s',2*CAP) if r['status'] in OK else 2*CAP for r in valid)/len(valid) if valid else None)
    summary['open_frontier']=[dict(id=r['id'],family=r['family'],gbd_hash=r['gbd_hash'],status=r['status'],telemetry=r.get('telemetry')) for r in rows if r['arm']=='warm' and r['status'] not in OK]
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print('SC2025_SUMMARY '+json.dumps(summary),flush=True)
    if errors or not summary['available']:raise RuntimeError('benchmark errors or no available sources')

if __name__=='__main__':main()
