"""Recompute per-input outcomes and compare the frozen choice with other eligible choices."""
from pathlib import Path
import collections,json,sys
from pilot import MODES,digest

def rows(p):return [json.loads(s) for s in p.read_text().splitlines()]
def report(panel,fixed):
    manifest=json.loads((panel/'manifest.json').read_text())
    measured=[x for p in panel.glob('lane-*.jsonl') for x in rows(p)]
    assert len({(r['id'],r['rep'],r['mode']) for r in measured})==len(measured)==156
    solved={'SAT','UNSAT'}
    e2e={}
    stable={}
    for mode in MODES:
        selected=sorted((r for r in measured if r['mode']==mode),key=lambda r:(r['id'],r['rep']))
        inputs={}
        for ident in manifest:
            aa=[r for r in selected if r['id']==ident]
            inputs[ident]=dict(status=[r['status'] for r in aa],
                choice=[r.get('telemetry',{}).get('priority_ordinal') for r in aa],
                certificate=[r.get('certificate') for r in aa])
        stable[mode]={i for i,a in inputs.items() if i!='F26' and all(s in solved for s in a['status'])}
        e2e[mode]=dict(per_input=inputs,all_three=sorted(stable[mode]),
          solved_per_rep=[sum(r['status'] in solved for r in selected if r['id']!='F26' and r['rep']==rep) for rep in (1,2,3)])
    f={}
    for ident in manifest:
        d=fixed/ident
        if (d/'skip.txt').exists():
            f[ident]={'skipped':(d/'skip.txt').read_text()};continue
        select=json.loads((d/'selection.json').read_text());run=rows(d/'runs.jsonl')
        keys=['table-first','table-pick-first','table-rank']+[f'ordinal-{i+1}' for i in range(len(select['scores']))]
        result={}
        for key in keys:
            rr=sorted((r for r in run if key in r['arms']),key=lambda r:r['rep'])
            assert [r['rep'] for r in rr]==[1,2,3]
            result[key]={'status':[r['status'] for r in rr],'flips':[r['flips'] for r in rr]}
        f[ident]=dict(choice=select['chosen'],clause=select['candidates'][select['chosen']-1],
                      candidates=len(select['scores']),outcomes=result,
                      stable_singletons=[i for i in range(1,len(select['scores'])+1) if result[f'ordinal-{i}']['status']==['SAT']*3])
    return dict(fresh_inputs=12,repetitions=3,e2e=e2e,fixed=f,
        priority_gains_vs_all=sorted(stable['table-rank']-stable['table-first']),
        priority_losses_vs_all=sorted(stable['table-first']-stable['table-rank']))
if __name__=='__main__':print(json.dumps(report(*map(Path,sys.argv[1:3])),indent=2))
