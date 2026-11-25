"""YM31: exact scale sweep and orientation/permutation controls."""
from pathlib import Path
from tempfile import TemporaryDirectory
from fractions import Fraction as Q
from cochain_soft import periodic,solve
from cochain_verify import verify
import json

def main():
    cases=[((L,4,4),Q(3),True) for L in (4,8,12,16,24,32)]
    cases += [((8,8),Q(1),True),((12,4),Q(1),True),((8,4,4),Q(1,2),False),
              ((7,4,4),Q(2),True),((8,4,4),Q(1),True)]
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        for i,(shape,target,ok) in enumerate(cases):
            s=root/f'{i}.json';c=root/f'{i}.cert'
            inp=periodic(shape,target,seed=3100+i);s.write_text(json.dumps(inp,sort_keys=True))
            r=solve(s,c)
            assert r['status']==('SOFT_MODE_PROVED' if ok else 'UNKNOWN'),(i,r)
            if ok:
                assert verify(s,c)['lambda_positive_upper']==r['lambda_positive_upper']
                L=max(shape)
                if L%4==0:assert Q(r['lambda_positive_upper'])==Q(48,L*L+8),(i,r)
                old=c.read_text();bad=json.loads(old);bad['edge_vector'][0]=str(Q(bad['edge_vector'][0])+1);c.write_text(json.dumps(bad))
                try:verify(s,c)
                except ValueError:pass
                else:raise AssertionError('tampered coexact witness')
                c.write_text(old)
                badinp=dict(inp);badinp['faces']=[list(row) for row in inp['faces']]
                badinp['faces'][0]=[list(x) for x in inp['faces'][0]]
                badinp['faces'][0][0][1]*=-1
                s.write_text(json.dumps(badinp,sort_keys=True))
                try:verify(s,c)
                except ValueError:pass
                else:raise AssertionError('broken boundary')
                s.write_text(json.dumps(inp,sort_keys=True))
            print('YM31_ROW '+json.dumps(dict(id=i,shape=shape,**r)),flush=True)
    print('YM31_SUMMARY '+json.dumps(dict(cases=len(cases),positive=10,negative=1,interacting_quantum_gap=False,continuum=False)),flush=True)
if __name__=='__main__':main()
