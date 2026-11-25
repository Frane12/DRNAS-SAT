"""Exact UNIFIED1 replay plus prospective fresh draw and a new reconvergent miter generator."""
import itertools,json,random,subprocess,sys,tempfile
from pathlib import Path
from corpus import encode,sha
root=Path(sys.argv[1]);root.mkdir(parents=True,exist_ok=True)
freeze=sys.argv[2]
previous="90c61f9b40df982607bc79bc667316146ff4b989"
cases=[]
with tempfile.TemporaryDirectory() as td:
    for label,seed in [('replay',previous),('fresh',freeze)]:
        d=Path(td)/label
        subprocess.run([sys.executable,str(Path(__file__).with_name('unified_corpus.py')),str(d),seed],check=True)
        manifest=json.loads((d/'manifest.json').read_text())
        for c in manifest['cases']:
            raw=(d/(c['id']+'.cnf')).read_bytes()
            assert sha(raw)==c['cnf_sha256']
            cid=label+'-'+c['id']
            (root/(cid+'.cnf')).write_bytes(raw)
            cases.append(dict(c,id=cid,group=label,original_id=c['id'],draw_commit=seed))
def miter(seed,k):
    rng=random.Random(seed);n=12;left=list(range(1,n+1));right=left[:];cs=[]
    def gate(a,b,y,truth):
        for x,z,t in itertools.product((0,1),repeat=3):
            if t!=((truth>>(x|(z<<1)))&1):
                cs.append([(-v if bit else v) for v,bit in zip((a,b,y),(x,z,t))])
    for j in range(36+5*k):
        a,b=rng.sample(range(len(left)),2)
        if j and j%3==0:a=len(left)-1
        if a==b:b=(b+1)%len(left)
        truth=rng.choice([1,6,7,8,9,14,2,4,11,13])
        swap=((truth&1)|((truth&2)<<1)|((truth&4)>>1)|(truth&8))
        n+=2;gate(left[a],left[b],n-1,truth);gate(right[b],right[a],n,swap)
        left.append(n-1);right.append(n)
    a,b=left[-1],right[-1]
    cs.extend([[a,b],[-a,-b]] if k%3 else [[a,-b],[-a,b]])
    order=list(range(1,n+1));rng.shuffle(order);rename=[0]+[v*rng.choice((-1,1)) for v in order]
    cs=[[rename[abs(l)]*(1 if l>0 else -1) for l in c] for c in cs]
    for c in cs:rng.shuffle(c)
    rng.shuffle(cs);return n,cs
for k in range(10):
    seed=int(sha(f'{freeze}|reconvergent-miter|{k}'.encode())[:16],16)
    n,cs=miter(seed,k);raw=encode(n,cs);cid=f'fresh-miter-{k:02}'
    (root/(cid+'.cnf')).write_bytes(raw)
    cases.append(dict(id=cid,group='fresh',family='reconvergent-miter',seed=seed,cnf_sha256=sha(raw),variables=n,clauses=len(cs),draw_commit=freeze))
assert len(cases)==110
assert len({c['cnf_sha256'] for c in cases})==110
(root/'manifest.json').write_text(json.dumps(dict(freeze=freeze,replay_commit=previous,cases=cases),indent=2))
