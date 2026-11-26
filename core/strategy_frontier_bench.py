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
CAP=5.0
ACCEPTED={'SAT','UNSAT'}
SEED=2611202689

SIZES=(210,400,600,800,1000)

def create(r,family,i,rep):
    n=SIZES[i];vs=list(range(1,n+1))
    planted={v:bool(r.getrandbits(1)) for v in vs}
    expected=None
    if family=='random3':
        cs=random3(r,vs,round(n*(4.0 if rep==0 else 4.5)))
    elif family=='planted3':
        cs=random3(r,vs,round(n*(4.25 if rep==0 else 5.25)),planted);expected='SAT'
    elif family=='mixed':
        cs=random3(r,vs,round(3.2*n),planted)
        for j in range(n//5):
            a=r.sample(vs,3);rhs=planted[a[0]]^planted[a[1]]^planted[a[2]]
            cs+=gate(a,lambda x,y,z,rhs=rhs:x^y^z==rhs)
        expected='SAT'
    elif family=='separator':
        sep=max(4,n//40);mid=(n-sep)//2+sep
        left=list(range(1,mid+1));right=list(range(1,sep+1))+list(range(mid+1,n+1))
        cs=random3(r,left,round(4.1*len(left)))+random3(r,right,round(4.1*len(right)))
    elif family=='random3-critical':
        cs=random3(r,vs,round(n*(4.20 if rep==0 else 4.27)))
    elif family=='nae-mix':
        cs=[]
        for j in range(round(1.95*n)):
            while True:
                a=tuple(r.sample(vs,3))
                if rep or len({planted[x] for x in a})>1:break
            cs.extend((a,tuple(-x for x in a)))
        cs+=random3(r,vs,round(.25*n),None if rep else planted)
        expected=None if rep else 'SAT'
    elif family=='xor-mix':
        cs=[]
        # Underdetermined parities, so the mixed problem is not merely a full-rank XOR system.
        for j in range(round(.55*n)):
            a=r.sample(vs,3)
            rhs=r.randrange(2) if rep else planted[a[0]]^planted[a[1]]^planted[a[2]]
            cs+=gate(a,lambda x,y,z,rhs=rhs:x^y^z==rhs)
        cs+=random3(r,vs,round(2.3*n),None if rep else planted)
        expected=None if rep else 'SAT'
    elif family=='colour':
        v=n//3;n=3*v;cs=[]
        colors=[r.randrange(3) for _ in range(v)]
        for x in range(v):
            cs.append(tuple(3*x+c+1 for c in range(3)))
            cs.extend((-(3*x+a+1),-(3*x+b+1)) for a,b in itertools.combinations(range(3),2))
        edges=set();target=round(v*(2.3 if rep==0 else 2.45))
        while len(edges)<target:
            a,b=sorted(r.sample(range(v),2))
            if rep or colors[a]!=colors[b]:edges.add((a,b))
        cs.extend((-(3*a+c+1),-(3*b+c+1)) for a,b in sorted(edges) for c in range(3))
        expected=None if rep else 'SAT'
    elif family=='capacity':
        slots=(15,19,24,28,31)[i];demands=slots+rep;n=slots*demands
        # Complete slot cliques. SAT and UNSAT are separate constructions.
        cs=[tuple(slots*j+k+1 for k in range(slots)) for j in range(demands)]
        cs.extend((-(slots*a+k+1),-(slots*b+k+1)) for k in range(slots) for a,b in itertools.combinations(range(demands),2))
        expected='UNSAT' if rep else 'SAT'
    elif family=='components':
        cs=[]
        for block in range(4):
            local=list(range(1+block*n//4,1+(block+1)*n//4))
            cs+=random3(r,local,round(4.25*len(local)),None if rep else planted)
        expected=None if rep else 'SAT'
    else:raise ValueError(family)
    n,cs=hide(r,n,cs)
    return n,cs,expected

def generate(out):
    rng=random.Random(SEED);seen=set();rows=[]
    (out/'cnf').mkdir()
    for cohort,families in (
        ('train',('random3','planted3','mixed','separator')),
        ('holdout',('random3-critical','nae-mix','xor-mix','colour','capacity','components'))):
        for family in families:
            for rep in range(2):
                for i in range(5):
                    n,cs,expected=create(rng,family,i,rep)
                    h=norm_digest(n,cs)
                    if h in seen:raise ValueError('normalized duplicate')
                    seen.add(h)
                    cid=('T' if cohort=='train' else 'H')+str(len(rows)).zfill(3)
                    path=out/'cnf'/f'{cid}.cnf';write(path,n,cs)
                    rows.append(dict(id=cid,cohort=cohort,family=family,path='cnf/'+path.name,n=n,m=len(cs),size_target=SIZES[i],rep=rep,expected=expected,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),normalized_sha256=h))
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
    else:
        ev.unlink(missing_ok=True) # keep sources and logs, not partial proof files
    if case['expected'] and result.get('status') in ACCEPTED and result['status']!=case['expected']:
        raise RuntimeError(f'validated answer conflicts with generator guarantee: {case["id"]}')
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    for d in ('evidence','logs'):(out/d).mkdir()
    cases=generate(out);mem=out/'policy.json'
    cpus=sorted(os.sched_getaffinity(0));os.sched_setaffinity(0,{cpus[0]})
    (out/'protocol.json').write_text(json.dumps(dict(seed=SEED,cap_s=CAP,audit_s=5,cpu=cpus[0],commit=os.getenv('GITHUB_SHA'),arms=ARMS,serial=True,training=40,holdout=60,repetitions=1),indent=2))
    errors=[];rows=[];paired=collections.Counter();profile_counts=collections.Counter();paired_default=collections.Counter()
    with (out/'rows.jsonl').open('w') as stream:
        def record(r):
            stream.write(json.dumps(r)+'\n');stream.flush()
            print('CORE_FRONTIER_ROW '+json.dumps(r),flush=True)
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
            d=panel['default']['status'] in ACCEPTED
            paired_default['both' if a and d else 'warm_only' if a else 'default_only' if d else 'neither']+=1
            profile_counts[panel['warm'].get('strategy',{}).get('profile','none')]+=1
        assert (mem.read_bytes() if mem.exists() else b'')==before
    def stats(rr):
        return dict(n=len(rr),solved=sum(r['status'] in ACCEPTED for r in rr),
                    statuses=dict(collections.Counter(r['status'] for r in rr)),
                    par2_s=sum(r['solve_s'] if r['status'] in ACCEPTED else 2*CAP for r in rr)/max(1,len(rr)),
                    audit_s=sum(r.get('audit_s',0) for r in rr))
    summary=dict(overall={a:stats([r for r in rows if r['arm']==a]) for a in ARMS},
                 families={f:{a:stats([r for r in rows if r['arm']==a and r['family']==f]) for a in ARMS} for f in sorted({r['family'] for r in rows})},
                 warm_vs_cold=dict(paired),warm_vs_default=dict(paired_default),by_size={str(k):{a:stats([r for r in rows if r['arm']==a and r['size_target']==k]) for a in ARMS} for k in SIZES},warm_profiles=dict(profile_counts),errors=len(errors))
    summary['open_frontier']=[dict(id=r['id'],family=r['family'],n=r['n'],m=r['m'],sha256=r['sha256'],status=r['status'],telemetry=r.get('telemetry')) for r in rows if r['arm']=='warm' and r['status'] not in ACCEPTED]
    summary['warm_only_ids']={a:sorted(r['id'] for r in rows if r['arm']=='warm' and r['status'] in ACCEPTED and not any(q['id']==r['id'] and q['arm']==a and q['status'] in ACCEPTED for q in rows)) for a in ('cold','default')}
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print('CORE_FRONTIER_SUMMARY '+json.dumps(summary),flush=True)
    if errors:raise RuntimeError(f'{len(errors)} errors/rejections; see artifacts')

if __name__=='__main__':main()
