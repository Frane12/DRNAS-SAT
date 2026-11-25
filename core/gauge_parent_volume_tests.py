"""YM21: exact reference gap and local residual; original finite bound separate."""
from fractions import Fraction as Q
from pathlib import Path
from tempfile import TemporaryDirectory
from atlas_forest_gauge import solve as forest
from run import run
from operator_verify import verify
import json,sys

def main(atlas):
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        cases=[(3,L,Q(1),Q(1,64),Q(1,4),True) for L in (2,4,8,16,32,64)]
        cases += [(2,8,Q(1),Q(-1,32),Q(1,4),True),(3,4,Q(2),Q(0),Q(1),True),
                  (3,4,Q(1),Q(1,4),Q(1,4),False),(3,4,Q(1),Q(1,64),Q(1),False)]
        for i,(d,L,a,k,g,ok) in enumerate(cases):
            src=root/f'{i}.op';cert=root/f'{i}.cert'
            src.write_text(f'p op gauge-parent-volume {d} {L} {a} {k} {g}\n')
            r=run(src,cert,5)
            assert r['status']==('PROVED' if ok else 'UNKNOWN'),r
            if ok:
                assert r['uniform_reference_gap'] and not r['uniform_original_gap'],r
                if i<6:assert Q(r['gap_lower'])==Q(5,12) and Q(r['local_residual_upper'])==Q(1,2304),r
                if i==0:assert r['original_positive_bound'],r
                if i==5:assert not r['original_positive_bound'],r
                old=cert.read_text();z=old.split();z[-2]='0';cert.write_text(' '.join(z))
                if Q(r['total_residual_upper']):
                    try:verify(src,cert)
                    except ValueError:pass
                    else:raise AssertionError('false residual accepted')
                cert.write_text(old)
            print('YM21_ROW '+json.dumps(dict(id=i,**r)),flush=True)
        # Actual ATLAS forest is exercised at the same physical parameters.
        # Its original finite gap is a separate result, not a parent proof.
        for L in (2,4):
            r=forest(3,L,2,Q(1),Q(1,64),Q(1,4),atlas,root/f'forest{L}')
            assert r['atlas']['model_verified'] and r['forest']['residual_root_gauge'],r
            assert r['status'] in ('PROVED','UNKNOWN'),r
            print('YM21_FOREST '+json.dumps(dict(L=L,**r)),flush=True)
    print('YM21_SUMMARY '+json.dumps(dict(cases=len(cases),positive=8,negative=2,atlas_forest_controls=2,uniform_reference_gap=True,uniform_original_gap=False,continuum=False)),flush=True)
if __name__=='__main__':main(Path(sys.argv[1]).resolve())
