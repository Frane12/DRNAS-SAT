"""Aggregate all repetitions; report each input and each subset with no selection."""
import collections,json,sys
from pathlib import Path


def read(path):return [json.loads(s) for s in path.read_text().splitlines()]
def count(rows):return sum(x['status']=='SAT' for x in rows)

def report(root):
    result={}
    for label in ('ablation','full'):
        records=read(root/f'f26-{label}/runs.jsonl')
        assert len({(r['arm'],r['rep']) for r in records})==len(records)==201
        grouped={}
        for arm in sorted({r['arm'] for r in records}):
            rs=[r for r in records if r['arm']==arm]
            grouped[arm]={'sat_of_3':count(rs),'flips':[r['flips'] for r in rs],
                          'projected':[r['projected'] for r in rs]}
        wins=[m for m in range(64) if grouped[f'mask-{m:02d}']['sat_of_3']==3]
        minimal=[m for m in wins if not any(k!=m and k&m==k for k in wins)]
        result[label]=dict(arms=grouped,stable_subsets=wins,minimal_stable=minimal)
    records=read(root/'f26-fresh/runs.jsonl')
    assert len({(r['mode'],r['rep'],r['id']) for r in records})==len(records)==48
    result['fresh']={arm:{i:[r['status'] for r in records if r['mode']==arm and r['id']==i]
                          for i in range(8)} for arm in ('default','table-first')}
    records=read(root/'f26-order/runs.jsonl')
    result['fresh_order']={}
    for i in range(8):
        rr=[r for r in records if r['id']==i]
        if len(rr)==1 and 'skip' in rr[0]:
            result['fresh_order'][i]=rr[0]['skip']
        else:
            assert len({(r['arm'],r['rep']) for r in rr})==len(rr)==6
            result['fresh_order'][i]={arm:[r['status'] for r in rr if r['arm']==arm]
                                       for arm in ('native-order','moved-last')}
    return result

if __name__=='__main__':print(json.dumps(report(Path(sys.argv[1])),indent=2))
