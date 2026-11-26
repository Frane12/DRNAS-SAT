"""Larger paired CORE transfer benchmark, with independently audited CDCL references."""
import argparse
import collections
import hashlib
import itertools
import json
import os
from pathlib import Path
import random
import time
from benchmark import make, gate, random3, norm_digest, attempt
from tests import hide, write
from run import run as native
import strategy

ARMS=('default','cold','warm','kissat','cadical')
CAP=2.0
ACCEPTED={'SAT','UNSAT'}
SEED=2611202671

def create(r,family,i):
    if family=='random3-hard':
        n=80+20*i
        return hide(r,n,random3(r,list(range(1,n+1)),round(4.25*n)))
    if family=='nae-mix':
        n=36+12*i;vs=list(range(1,n+1));cs=[]
        for j in range(2*n):
            a=tuple(r.sample(vs,3));cs.extend((a,tuple(-x for x in a)))
        cs+=random3(r,vs,round(.8*n))
        return hide(r,n,cs)
    if family=='xor-mix':
        n=48+16*i;vs=list(range(1,n+1));cs=[]
        for j in range(n):
            a=r.sample(vs,3);rhs=r.randrange(2)
            cs+=gate(a,lambda x,y,z,rhs=rhs:x^y^z==rhs)
        cs+=random3(r,vs,n)
        return hide(r,n,cs)
    return make(r,family,i)

def generate(out):
    rng=random.Random(SEED);seen=set();rows=[]
    (out/'cnf').mkdir()
    for cohort,families,repeats in (
        ('train',('random3','planted3','mixed','separator'),2),
        ('holdout',('random3-hard','nae-mix','xor-mix','colour','capacity','components'),2)):
        for family in families:
            for rep in range(repeats):
                for i in range(5):
                    n,cs=create(rng,family,i)
                    h=norm_digest(n,cs)
                    if h in seen:raise ValueError('normalized duplicate')
                    seen.add(h)
                    cid=('T' if cohort=='train' else 'H')+str(len(rows)).zfill(3)
                    path=out/'cnf'/f'{cid}.cnf';write(path,n,cs)
                    rows.append(dict(id=cid,cohort=cohort,family=family,path='cnf/'+path.name,n=n,m=len(cs),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),normalized_sha256=h))
    rng.shuffle(rows)
    (out/'manifest.json').write_text(json.dumps(rows,indent=2))
    return rows

def evaluate(out,case,arm,mem,readonly=True):
    src=out/case['path'];ev=out/'evidence'/f"{case['id']}.{arm}.cert"
    assert hashlib.sha256(src.read_bytes()).hexdigest()==case['sha256']
    start=time.monotonic()
    if arm in ('kissat','cadical'):
        result=attempt(dict(case,cohort='fresh'),arm,out,CAP)
    elif arm=='warm':
        result=strategy.run(str(src),str(ev),CAP,5,mem,readonly)
    else:
        result=native(str(src),str(ev),CAP,'default' if arm=='default' else 'freedom',5)
    result.update(case,arm=arm,e2e_s=time.monotonic()-start)
    if result.get('status') in ACCEPTED:
        assert ev.is_file(),result
        result['evidence_sha256']=hashlib.sha256(ev.read_bytes()).hexdigest()
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    for d in ('evidence','logs'):(out/d).mkdir()
    cases=generate(out);mem=out/'policy.json'
    cpus=sorted(os.sched_getaffinity(0));os.sched_setaffinity(0,{cpus[0]})
    (out/'protocol.json').write_text(json.dumps(dict(seed=SEED,cap_s=CAP,audit_s=5,cpu=cpus[0],commit=os.getenv('GITHUB_SHA'),arms=ARMS,serial=True,training=40,holdout=60,repetitions=1),indent=2))
    errors=[];rows=[];paired=collections.Counter();profile_counts=collections.Counter()
    with (out/'rows.jsonl').open('w') as stream:
        def record(r):
            stream.write(json.dumps(r)+'\n');stream.flush()
            print('CORE_LARGE_ROW '+json.dumps(r),flush=True)
            if r.get('status') in ('ERROR','REJECTED') or 'strategy_error' in r:errors.append(r)
        for case in cases:
            if case['cohort']=='train':record(evaluate(out,case,'warm',mem,False))
        before=mem.read_bytes() if mem.exists() else b''
        for i,case in enumerate(c for c in cases if c['cohort']=='holdout'):
            panel={}
            for arm in ARMS[i%len(ARMS):]+ARMS[:i%len(ARMS)]:
                r=evaluate(out,case,arm,mem);record(r);rows.append(r);panel[arm]=r
            answers={r['status'] for r in panel.values() if r['status'] in ACCEPTED}
            if len(answers)>1:raise RuntimeError(f"conflicting audited answers: {case['id']}")
            a=panel['warm']['status'] in ACCEPTED;b=panel['cold']['status'] in ACCEPTED
            paired['both' if a and b else 'warm_only' if a else 'cold_only' if b else 'neither']+=1
            profile_counts[panel['warm'].get('strategy',{}).get('profile','none')]+=1
        assert (mem.read_bytes() if mem.exists() else b'')==before
    def stats(rr):
        return dict(n=len(rr),solved=sum(r['status'] in ACCEPTED for r in rr),
                    statuses=dict(collections.Counter(r['status'] for r in rr)),
                    par2_s=sum(r['solve_s'] if r['status'] in ACCEPTED else 2*CAP for r in rr)/max(1,len(rr)),
                    audit_s=sum(r.get('audit_s',0) for r in rr))
    summary=dict(overall={a:stats([r for r in rows if r['arm']==a]) for a in ARMS},
                 families={f:{a:stats([r for r in rows if r['arm']==a and r['family']==f]) for a in ARMS} for f in sorted({r['family'] for r in rows})},
                 warm_vs_cold=dict(paired),warm_profiles=dict(profile_counts),errors=len(errors))
    summary['open_frontier']=[dict(id=r['id'],family=r['family'],n=r['n'],m=r['m'],sha256=r['sha256'],status=r['status'],telemetry=r.get('telemetry')) for r in rows if r['arm']=='warm' and r['status'] not in ACCEPTED]
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print('CORE_LARGE_SUMMARY '+json.dumps(summary),flush=True)
    if errors:raise RuntimeError(f'{len(errors)} errors/rejections; see artifacts')

if __name__=='__main__':main()
