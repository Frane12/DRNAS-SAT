"""YM13: full SU(2) representation graph gap, exact small-coupling bounds."""
from fractions import Fraction as Q
from pathlib import Path
from tempfile import TemporaryDirectory
from run import run
from operator_verify import verify
import json

def grid(x,y,k):
    v=lambda i,j:j*(x+1)+i
    e=[(v(i,j),v(i+1,j)) for j in range(y+1) for i in range(x)]
    e += [(v(i,j),v(i,j+1)) for j in range(y) for i in range(x+1)]
    p=[(k,[v(i,j),v(i+1,j),v(i+1,j+1),v(i,j+1)]) for j in range(y) for i in range(x)]
    return (x+1)*(y+1),e,p
def emit(n,edges,loops,target,alpha=1):
    return f'p op gauge-gap {n} {len(edges)} {len(loops)} {alpha} {target}\n'+''.join(f'{a} {b}\n' for a,b in edges)+''.join(f'{len(v)} {k} '+ ' '.join(map(str,v))+'\n' for k,v in loops)
def main():
    cases=[
        (1,1,Q(1,2),2,Q(77,37)),
        (2,1,Q(1,4),2,Q(293,145)),
        (2,1,Q(1,2),1,Q(40,37)),
        (2,1,Q(3,4),Q(1,10),Q(3,17)),
        (2,1,Q(1),Q(1,10),None),
        (2,2,Q(1,4),1,Q(148,145)),
        (3,3,Q(1,16),1,Q(34599,18440)),
        (10,10,Q(1,100),1,Q(90004,90001)),
        (2,1,Q(0),3,Q(3)),
        (2,1,Q(-1,2),1,Q(40,37)),
        (2,1,Q(0),4,None),
    ]
    with TemporaryDirectory() as tmp:
        d=Path(tmp)
        for i,(x,y,k,target,expected) in enumerate(cases):
            src=d/f'{i}.op';cert=d/f'{i}.cert'
            src.write_text(emit(*grid(x,y,k),target))
            r=run(src,cert,10,audit_seconds=15)
            assert r['status']==('PROVED' if expected is not None else 'UNKNOWN'),(i,r)
            if expected is not None:
                assert Q(r['gap_lower'])==expected and r['all_representations'],r
                old=cert.read_text();w=old.split();w[3]='3';cert.write_text(' '.join(w))
                try:verify(src,cert)
                except ValueError:pass
                else:raise AssertionError('tampered girth accepted')
                cert.write_text(old)
            print('YM13_ROW '+json.dumps(dict(id=i,**r)),flush=True)
        src=d/'tree.op';cert=d/'tree.cert'
        src.write_text(emit(3,[(0,1),(1,2)],[],1))
        assert run(src,cert,10)['status']=='UNKNOWN'
        src=d/'triangle.op';cert=d/'triangle.cert'
        src.write_text(emit(3,[(0,1),(1,2),(2,0)],[],Q(9,4)))
        r=run(src,cert,10);assert r['status']=='PROVED' and r['electric_gap']=='9/4',r
    print('YM13_SUMMARY '+json.dumps(dict(cases=len(cases)+2,positive=10,volume_uniform=False,continuum=False)),flush=True)
if __name__=='__main__':main()
