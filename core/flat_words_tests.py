"""YM32 synthetic cell complexes with relabelled vertices and reversed faces."""
from pathlib import Path
from tempfile import TemporaryDirectory
from atlas_flat_words import solve
from flat_words_verify import verify,mul,inv,I
from fractions import Fraction as Q
import json,random,sys

def grid(L,H,px=False,py=False,hole=None):
    n=L*H;faces=[];edges=set()
    def v(x,y):return (x%L)*H+y%H
    for x in range(L):
        for y in range(H):
            if px or x+1<L:edges.add(tuple(sorted((v(x,y),v(x+1,y)))))
            if py or y+1<H:edges.add(tuple(sorted((v(x,y),v(x,y+1)))))
            if (px or x+1<L) and (py or y+1<H) and (x,y)!=hole:
                faces.append([v(x,y),v(x+1,y),v(x+1,y+1),v(x,y+1)])
    return dict(n=n,edges=sorted(edges),faces=faces)
def permute(s,seed):
    p=list(range(s['n']));r=random.Random(seed);r.shuffle(p)
    faces=[[p[i] for i in w] for w in s['faces']]
    faces=[w[::-1] if r.randrange(2) else w for w in faces];r.shuffle(faces)
    return dict(n=s['n'],edges=sorted(tuple(sorted((p[a],p[b]))) for a,b in s['edges']),faces=faces)
def main(atlas):
    cases=[(grid(3,3),'disk','FLAT_TRIVIAL',0,0),
           (grid(4,4),'disk','FLAT_TRIVIAL',0,0),
           (grid(5,4),'disk','FLAT_TRIVIAL',0,0),
           (grid(4,4,hole=(1,1)),'puncture','NONTRIVIAL_FLAT',3,1),
           (grid(4,3,px=True),'cylinder','NONTRIVIAL_FLAT',3,1),
           (grid(4,4,px=True,py=True),'torus','NONTRIVIAL_FLAT',6,2),
           (grid(5,4,px=True,py=True),'torus','NONTRIVIAL_FLAT',6,2)]
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        for i,(s,family,status,t0,t1) in enumerate(cases):
            src=root/f'{i}.json';c=root/f'{i}.cert';src.write_text(json.dumps(permute(s,i+320)))
            r=solve(src,c,atlas,root/f'w{i}');assert r['status']==status,(i,r)
            assert r['identity_tangent']['linearized_quotient_dimension']==t0,(i,r)
            if t1:assert r['witness_tangent']['linearized_quotient_dimension']==t1,(i,r)
            assert verify(src,c)['status']==status
            old=c.read_text();z=json.loads(old);z['sha256']='0';c.write_text(json.dumps(z))
            try:verify(src,c)
            except ValueError:pass
            else:raise AssertionError('tampered binding')
            c.write_text(old)
            print('YM32_ROW '+json.dumps(dict(id=i,family=family,**r)),flush=True)
    # At identity the first variation of a commutator vanishes, yet
    # nonparallel infinitesimal generators need not integrate to flats.
    a=(Q(3,5),Q(4,5),Q(0),Q(0));b=(Q(3,5),Q(0),Q(4,5),Q(0))
    assert mul(mul(mul(a,b),inv(a)),inv(b))!=I
    print('YM32_SUMMARY '+json.dumps(dict(cases=len(cases),trivial=3,nontrivial=4,continuum=False)),flush=True)
if __name__=='__main__':main(Path(sys.argv[1]).resolve())
