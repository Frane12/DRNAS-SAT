"""REGIONAL4: exact replay of all 18 REGIONAL2 inputs, eight paired arms."""
import argparse
import collections
import json
import os
from pathlib import Path
import time
from benchmark import attempt
from regional2_bench import panel, sha, CAP, OK
from run import run

ARMS=('default','freedom-wide','regional','regional2','regional3','regional4','kissat','cadical')

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
                print('REGIONAL4_ROW '+json.dumps(ans),flush=True)
            assert len(answers)<=1,(c,answers)
    def stats(rr):
        return dict(solved=sum(r['status'] in OK for r in rr),n=len(rr),statuses=dict(collections.Counter(r['status'] for r in rr)),
          par2_s=sum(r.get('solve_s',2*CAP) if r['status'] in OK else 2*CAP for r in rr)/max(1,len(rr)))
    summary=dict(overall={a:stats([r for r in rows if r['arm']==a]) for a in ARMS},
        families={f:{a:stats([r for r in rows if r['arm']==a and r['family']==f]) for a in ARMS} for f in sorted({r['family'] for r in rows})},
        replay=[r for r in rows if r['cohort']=='replay'],errors=len(errors))
    solved={a:{r['id'] for r in rows if r['arm']==a and r['status'] in OK} for a in ARMS}
    summary['regional4_only_vs']={a:sorted(solved['regional4']-solved[a]) for a in ARMS if a!='regional4'}
    summary['regional4_regressions_vs']={a:sorted(solved[a]-solved['regional4']) for a in ARMS if a!='regional4'}
    summary['communities']=[dict(id=r['id'],n=r['n'],status=r['status'],telemetry=r.get('telemetry')) for r in rows if r['arm']=='regional4']
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print('REGIONAL4_SUMMARY '+json.dumps(summary),flush=True)
    if errors:raise RuntimeError('benchmark errors; inspect artifacts')

if __name__=='__main__':main()
