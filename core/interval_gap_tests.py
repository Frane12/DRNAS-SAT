"""YM11: unknown ground-state energy, exact interval gap certificates."""
from fractions import Fraction as Q
from pathlib import Path
from tempfile import TemporaryDirectory
from run import run
from operator_verify import verify
import json

def chain(n,k):
    return [[i*(i+2) if i==j else -k if abs(i-j)==1 else 0 for j in range(n)] for i in range(n)]

def spin(t):
    # -Z1-Z2-t X1 X2; eigenvalues +/- sqrt(4+t^2), +/- t.
    return [[-2,0,0,-t],[0,0,-t,0],[0,-t,0,0],[-t,0,0,2]]

def main():
    cases=[
        ('irrational-ground',[[0,1],[1,1]],2,True),
        ('irrational-overshoot',[[0,1],[1,1]],3,False),
        ('zero-diagonal',[[0,1],[1,0]],Q(3,2),True),
        ('degenerate-ground',[[0,0,0],[0,0,0],[0,0,3]],1,False),
        ('single-state',[[4]],1,False),
        ('entangled-spin-1',spin(1),1,True),
        ('entangled-spin-2',spin(2),Q(3,4),True),
        ('entangled-spin-overshoot',spin(2),1,False),
        ('su2-cutoff-4',chain(4,1),3,True),
        ('su2-cutoff-8',chain(8,1),3,True),
        ('su2-cutoff-12',chain(12,1),3,True),
        ('su2-cutoff-overshoot',chain(8,1),4,False),
        ('fractional',[[Q(1,3),Q(2,5)],[Q(2,5),Q(7,3)]],2,True),
        ('rational-multiplicity',[[0,0,0],[0,2,0],[0,0,2]],Q(3,2),True),
    ]
    with TemporaryDirectory() as tmp:
        p=Path(tmp)
        for i,(label,a,g,expected) in enumerate(cases):
            src=p/f'{i}.op'; cert=p/f'{i}.cert'
            src.write_text(f'p op interval-gap {len(a)} {g}\n'+'\n'.join(' '.join(map(str,row)) for row in a)+'\n')
            r=run(src,cert,10,audit_seconds=25)
            assert r['status']==('PROVED' if expected else 'UNKNOWN'),(label,r)
            if expected:
                assert Q(r['gap_lower'])>=g and Q(r['excited_lower'])-Q(r['ground_upper'])==Q(r['gap_lower'])
                old=cert.read_text(); words=old.split()
                words[5]=str(Q(words[5])+1000);cert.write_text('\n'.join(words)+'\n')
                try:verify(src,cert)
                except ValueError:pass
                else:raise AssertionError('invalid spectral count accepted')
                cert.write_text(old)
            print('YM11_ROW '+json.dumps(dict(id=label,**r)),flush=True)
    print('YM11_SUMMARY '+json.dumps(dict(cases=len(cases),positive=sum(x[-1] for x in cases),unknown_vacuum=True,finite_only=True)),flush=True)
if __name__=='__main__':main()
