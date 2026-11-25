"""Exact 210-input UNIFIED4 replay, independent 50-case draw."""
import json,random,subprocess,sys,tempfile
from pathlib import Path
from corpus import encode,sha
root=Path(sys.argv[1]);root.mkdir(parents=True,exist_ok=True)
freeze=sys.argv[2]
previous="66b1449c370b4cb35a9493a76cdcd1edb6d5695f"
cases=[]
with tempfile.TemporaryDirectory() as td:
    for label,seed in [('replay',previous),('fresh',freeze)]:
        d=Path(td)/label
        subprocess.run([sys.executable,str(Path(__file__).with_name('unified4_corpus.py')),str(d),seed],check=True)
        manifest=json.loads((d/'manifest.json').read_text())
        selected=manifest['cases']
        if label=='fresh':
            selected=[c for c in selected if c['group']=='fresh' and c['family']!='larger3']
            assert len(selected)==10
        for c in selected:
            raw=(d/(c['id']+'.cnf')).read_bytes()
            assert sha(raw)==c['cnf_sha256']
            cid=label+'-'+c['id']
            (root/(cid+'.cnf')).write_bytes(raw)
            cases.append(dict(c,id=cid,group=label,prior_group=c['group'],original_id=c['id'],draw_commit=seed))
for k in range(40):
    n=[64,96,128,192,256][k%5]
    ratio=[3.9,4.1,4.26,4.4,4.6,4.8,5.0,5.2][k//5]
    seed=int(sha(f'{freeze}|compression-uniform3|{k}'.encode())[:16],16)
    rng=random.Random(seed)
    cs=[[v*rng.choice((-1,1)) for v in rng.sample(range(1,n+1),3)] for _ in range(round(n*ratio))]
    raw=encode(n,cs);cid=f'fresh-compression3-{k:02}'
    (root/(cid+'.cnf')).write_bytes(raw)
    cases.append(dict(id=cid,group='fresh',family='compression3',seed=seed,ratio=ratio,cnf_sha256=sha(raw),variables=n,clauses=len(cs),draw_commit=freeze))
assert len(cases)==260
assert len({c['cnf_sha256'] for c in cases})==260
(root/'manifest.json').write_text(json.dumps(dict(freeze=freeze,replay_commit=previous,cases=cases),indent=2))
