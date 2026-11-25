"""YM20: verify fixed-block volume sweep, tamper control and actual ATLAS/CORE."""
from pathlib import Path
from tempfile import TemporaryDirectory
from fractions import Fraction as Q
import json,sys
from atlas_forest_gauge import solve
from forest_gauge_verify import verify_forest

def main(atlas):
    cases=[(2,4,2,Q(1),True),(3,2,2,Q(1),True),(3,3,2,Q(1),True),
           (3,4,2,Q(1),True),(3,5,2,Q(1),True),(3,6,2,Q(1),True),
           (3,4,3,Q(1),True),(3,3,2,Q(100),False)]
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        for i,(d,L,b,g,ok) in enumerate(cases):
            out=root/str(i)
            r=solve(d,L,b,Q(1),Q(1,1024),g,atlas,out)
            assert r['status']==('PROVED' if ok else 'UNKNOWN'),r
            a=r['forest'];assert a['removed']==L**d-a['blocks'] and a['max_row']<=a['uniform_row_bound']
            assert a['form_factor']<=a['uniform_form_factor'] and r['atlas']['model_verified']
            cert=out/'forest.json';src=out/'grid.json';old=cert.read_text()
            z=json.loads(old);z['form_factor']-=1;cert.write_text(json.dumps(z))
            try:verify_forest(src,cert)
            except ValueError:pass
            else:raise AssertionError('false form coefficient')
            cert.write_text(old)
            print('YM20_ROW '+json.dumps(dict(d=d,L=L,b=b,**r)),flush=True)
    print('YM20_SUMMARY '+json.dumps(dict(cases=len(cases),positive=7,negative=1,uniform_electric_form=True,uniform_magnetic_gap=False,continuum=False)),flush=True)
if __name__=='__main__':main(Path(sys.argv[1]).resolve())
