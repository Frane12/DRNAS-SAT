"""YM17B: finite open SU(2) ladder, all representations, fixed-coupling scaling."""
from fractions import Fraction as Q
from pathlib import Path
from run import run
from operator_verify import verify
import tempfile,json
def main():
    cases=[]
    for g2 in (8,4,2,1,Q(1,2),Q(1,8)):
        for m in (2,4,8,16,64,256):
            # Frozen sweep, not a guarantee of a positive proof for every case.
            cases.append((f'g{g2}-m{m}',m,48,Q(1),Q(g2),Q(1,10),None))
    # Explicit strong-coupling and impossible-target controls.
    cases += [('strong-control',256,48,Q(1),Q(8),Q(1),True),
              ('overshoot',2,32,Q(1),Q(1),Q(10000),False)]
    positive=unknown=0;by={}
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)
        for i,(label,m,n,a,g2,g,expected) in enumerate(cases):
            s=p/f'{i}.op';c=p/f'{i}.cert';s.write_text(f'p op ks-ladder-gap {m} {n} {a} {g2} {g}\n')
            r=run(s,c,20,audit_seconds=25)
            assert r['status'] in ('PROVED','UNKNOWN','TIMEOUT','AUDIT_LIMIT'),(label,r)
            if expected is True:assert r['status']=='PROVED',(label,r)
            if expected is False:assert r['status']=='UNKNOWN',(label,r)
            if r['status']=='PROVED':
                positive+=1;assert Q(r['gap_lower'])>=g and r['plaquettes']==m
                old=c.read_text();z=old.split();z[-2]=str(Q(z[-2])+1000000);c.write_text(' '.join(z)+'\n')
                try:verify(s,c)
                except ValueError:pass
                else:raise AssertionError('tampered spectral cut accepted')
                c.write_text(old)
            else:unknown+=1
            if expected is None:by.setdefault(str(g2),{})[str(m)]=r['status']
            print('YM17B_ROW '+json.dumps(dict(id=label,**r)),flush=True)
    print('YM17B_SUMMARY '+json.dumps(dict(positive=positive,unknown=unknown,cases=len(cases),by_coupling=by,all_representations=True,volume_uniform=False,continuum=False)),flush=True)
if __name__=='__main__':main()
