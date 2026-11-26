"""Paired REGIONAL2 validation: exact old frontier replays and fresh larger CNFs."""
import argparse
import collections
import hashlib
import itertools
import json
import os
from pathlib import Path
import random
import time
from benchmark import attempt, gate, random3, norm_digest
from strategy_frontier_bench import generate
from tests import write, hide, truth
from run import run

CAP=5.0
ARMS=('default','freedom-wide','regional','regional2','kissat','cadical')
OK={'SAT','UNSAT'}
REPLAY={
 'H064':'958ce9e60f3993e63b7dc60b7fcc40001ef09485dae316b831b98a18c448a0bd',
 'H069':'21dfb8c47ec997c4ec136fe3552cf77a3915549575d61d0ad1f9bd1daad91690',
}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def mixed(r,n,planted,local):
    vs=list(range(1,n+1))
    value={v:bool(r.getrandbits(1)) for v in vs};cs=[]
    groups=[vs] if not local else [vs[i:i+100] for i in range(0,n,100)]
    for group in groups:
        for _ in range(round(.55*len(group))):
            a=r.sample(group,3)
            rhs=value[a[0]]^value[a[1]]^value[a[2]] if planted else r.randrange(2)
            cs+=gate(a,lambda x,y,z,rhs=rhs:x^y^z==rhs)
        cs+=random3(r,group,round(2.3*len(group)),value if planted else None)
    # Couple adjacent local systems by planted clauses, no parity constraints lost.
    if local:
        for i in range(1,len(groups)):
            cs+=random3(r,groups[i-1][-5:]+groups[i][:5],2,value if planted else None)
    return hide(r,n,cs)

def panel(out):
    replay=out/'replay';replay.mkdir()
    old=generate(replay);cases=[]
    for c in old:
        if c['id'] not in REPLAY:continue
        path=replay/c['path'];assert sha(path)==REPLAY[c['id']],c
        dest=out/'cnf'/path.name;dest.write_bytes(path.read_bytes())
        cases.append(dict(c,cohort='replay',path='cnf/'+dest.name))
    assert len(cases)==2
    r=random.Random(2611202642)
    def add(cid,family,n,cs,expected):
        path=out/'cnf'/f'{cid}.cnf';write(path,n,cs)
        cases.append(dict(id=cid,cohort='fresh',family=family,n=n,m=len(cs),path='cnf/'+path.name,
            expected=expected,sha256=sha(path),normalized_sha256=norm_digest(n,cs)))
    for n in (1000,2000,5000,10000):
        for planted in (True,False):
            nn,cs=mixed(r,n,planted,False)
            add(f'X{n}-{int(planted)}','global-xor-mix',nn,cs,'SAT' if planted else None)
    for n in (10000,25000,50000,100000):
        nn,cs=mixed(r,n,True,True)
        add(f'L{n}','local-xor-mix',nn,cs,'SAT')
    # Small exact ground truth; full XOR plus non-parity clause, signed permutation.
    for j in range(4):
        n=8;cs=gate([1,2,3],lambda a,b,c:a^b^c==1)
        cs+=gate([3,4,5],lambda a,b,c:a^b^c==0)
        cs+=random3(r,list(range(1,n+1)),16)
        nn,cs=hide(r,n,cs);add(f'C{j}','truth-control',nn,cs,'SAT' if truth(nn,cs) else 'UNSAT')
    (out/'manifest.json').write_text(json.dumps(cases,indent=2))
    return cases

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    for d in ('cnf','evidence','logs'):(out/d).mkdir()
    cpus=sorted(os.sched_getaffinity(0));os.sched_setaffinity(0,{cpus[0]})
    (out/'protocol.json').write_text(json.dumps(dict(commit=os.getenv('GITHUB_SHA'),cap_s=CAP,audit_s=5,cpu=cpus[0],arms=ARMS,serial=True,seed=2611202642),indent=2))
    cases=panel(out);rows=[];errors=[]
    with (out/'rows.jsonl').open('w') as stream:
        for i,c in enumerate(cases):
            src=out/c['path'];assert sha(src)==c['sha256'];answers=set()
            for arm in ARMS[i%len(ARMS):]+ARMS[:i%len(ARMS)]:
                ev=out/'evidence'/f"{c['id']}.{arm}.cert";t=time.monotonic()
                if arm in ('kissat','cadical'):
                    ans=attempt(dict(c,cohort='fresh'),arm,out,CAP)
                else:
                    ans=run(str(src),str(ev),CAP,'freedom' if arm=='freedom-wide' else arm,5,strategy_profile='wide' if arm=='freedom-wide' else None)
                ans.update(c,arm=arm,e2e_s=time.monotonic()-t)
                if ans['status'] in OK:
                    assert ev.exists(),ans
                    ans['evidence_sha256']=sha(ev);answers.add(ans['status'])
                    if c.get('expected') and ans['status']!=c['expected']:errors.append(ans)
                else:ev.unlink(missing_ok=True)
                if ans['status'] in ('ERROR','REJECTED'):errors.append(ans)
                rows.append(ans);stream.write(json.dumps(ans)+'\n');stream.flush()
                print('REGIONAL2_ROW '+json.dumps(ans),flush=True)
            assert len(answers)<=1,(c,answers)
    def stats(rr):
        return dict(solved=sum(r['status'] in OK for r in rr),n=len(rr),statuses=dict(collections.Counter(r['status'] for r in rr)),
          par2_s=sum(r.get('solve_s',2*CAP) if r['status'] in OK else 2*CAP for r in rr)/max(1,len(rr)))
    summary=dict(overall={a:stats([r for r in rows if r['arm']==a]) for a in ARMS},
        families={f:{a:stats([r for r in rows if r['arm']==a and r['family']==f]) for a in ARMS} for f in sorted({r['family'] for r in rows})},
        replay=[r for r in rows if r['cohort']=='replay'],errors=len(errors))
    solved={a:{r['id'] for r in rows if r['arm']==a and r['status'] in OK} for a in ARMS}
    summary['regional2_only_vs']={a:sorted(solved['regional2']-solved[a]) for a in ARMS if a!='regional2'}
    summary['regional2_regressions_vs']={a:sorted(solved[a]-solved['regional2']) for a in ARMS if a!='regional2'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print('REGIONAL2_SUMMARY '+json.dumps(summary),flush=True)
    if errors:raise RuntimeError('benchmark errors; inspect artifacts')

if __name__=='__main__':main()
