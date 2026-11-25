"""Replay the exact UNIFIED2 corpus; draw fresh random-3SAT and transfer cases."""
import json,random,subprocess,sys,tempfile
from pathlib import Path
from corpus import encode,sha
root=Path(sys.argv[1]);root.mkdir(parents=True,exist_ok=True)
freeze=sys.argv[2]
previous="8ac5c62c955d04fabfd6367f83aa408a297ed2ae"
cases=[]
with tempfile.TemporaryDirectory() as td:
    for label,seed in [('replay',previous),('fresh',freeze)]:
        d=Path(td)/label
        subprocess.run([sys.executable,str(Path(__file__).with_name('unified2_corpus.py')),str(d),seed],check=True)
        manifest=json.loads((d/'manifest.json').read_text())
        selected=manifest['cases']
        if label=='fresh':
            # Twenty newly seeded transfer controls; no previous result labels.
            selected=[c for c in selected if c['group']=='fresh' and c['family'] in ('tseitin','colour','mixed','circuit','reconvergent-miter')]
            selected=sorted(selected,key=lambda c:sha((freeze+'|transfer|'+c['id']).encode()))[:20]
        for c in selected:
            raw=(d/(c['id']+'.cnf')).read_bytes()
            assert sha(raw)==c['cnf_sha256']
            cid=label+'-'+c['id']
            (root/(cid+'.cnf')).write_bytes(raw)
            cases.append(dict(c,id=cid,group=label,prior_group=c['group'],original_id=c['id'],draw_commit=seed))
# A new, independently seeded random-3SAT sweep across sizes and densities.
# No filtering by satisfiability: all draws are retained.
for k in range(30):
    n=[48,64,80,96,128][k%5]
    ratio=[4.1,4.26,4.5,4.7,5.0,5.2][k//5]
    seed=int(sha(f'{freeze}|uniform3|{k}'.encode())[:16],16)
    rng=random.Random(seed)
    cs=[[v*rng.choice((-1,1)) for v in rng.sample(range(1,n+1),3)] for _ in range(round(n*ratio))]
    raw=encode(n,cs);cid=f'fresh-uniform3-{k:02}'
    (root/(cid+'.cnf')).write_bytes(raw)
    cases.append(dict(id=cid,group='fresh',family='uniform3',seed=seed,ratio=ratio,cnf_sha256=sha(raw),variables=n,clauses=len(cs),draw_commit=freeze))
assert len(cases)==160
assert len({c['cnf_sha256'] for c in cases})==160
(root/'manifest.json').write_text(json.dumps(dict(freeze=freeze,replay_commit=previous,cases=cases),indent=2))
