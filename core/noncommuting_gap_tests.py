"""YM9: source-bound gap via comparison, including interacting gauge-invariant controls."""
from collections import defaultdict
from fractions import Fraction as Q
from pathlib import Path
import tempfile
import json
from run import run
from symbolic_verify import check

def model(n,encoded=False,axis='X'):
    a=defaultdict(Q);ident='I'*n
    def word(entries):
        p=['I']*n
        for i,c in entries:p[i]=c
        return ''.join(p)
    a[ident]+=Q(n,2)
    for i in range(n):a[word([(i,'Z')])]-=Q(1,2)
    stride=2 if encoded else 1
    for i in range(0,n,stride):
        j=(i+stride)%n
        flip=[(j,axis)]+([(j+1,axis)] if encoded else [])
        # P_i Q_j, positive because supports are disjoint, but different
        # local terms of the full H do not commute.
        a[ident]+=Q(1,4)
        a[word([(i,'Z')])]-=Q(1,4)
        a[word(flip)]-=Q(1,4)
        a[word([(i,'Z')]+flip)]+=Q(1,4)
    return {s:c for s,c in a.items() if c}

def emit(n,a,gamma):
    return f'p sop product-gap {n} {len(a)} {gamma}\n'+''.join(f'{c} {s}\n' for s,c in sorted(a.items()))

def main():
    cases=[]
    for n in (3,12,48,120,240):
        cases.append((f'ring-{n}',n,model(n),1,True))
    for n in (6,24,96,240):
        cases.append((f'gauge-{n}',n,model(n,True),1,True))
    cases += [('complex-phase',6,model(6,False,'Y'),1,True),
              ('overshoot',6,model(6),2,False),
              ('bad-ground',2,{'II':Q(1),'XI':Q(1)},1,False),
              ('bad-positivity',2,{'II':Q(-1),'ZI':Q(1)},1,False),
              ('zero-gap',3,model(3),0,False)]
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)
        for i,(label,n,a,gamma,expected) in enumerate(cases):
            s=p/f'{i}.sop';c=p/f'{i}.cert';s.write_text(emit(n,a,gamma))
            r=run(s,c,10,audit_seconds=25)
            assert r['status']==('PROVED' if expected else 'UNKNOWN'),(label,r)
            if expected:
                assert r['gap_lower']==str(gamma) and r['ground_dimension']=='1',r
                old=c.read_text();lines=old.splitlines();lines[3]='999';c.write_text('\n'.join(lines)+'\n')
                try:check(s,c)
                except ValueError:pass
                else:raise AssertionError('tampered residual bound accepted')
                c.write_text(old)
            print('YM9_ROW '+json.dumps(dict(id=label,**r)),flush=True)
        # Gauge invariance of full interacting H under local Z2 parity generators.
        n=24;a=model(n,True)
        for j in range(0,n,2):
            g='I'*j+'ZZ'+'I'*(n-j-2)
            s=p/f'commute{j}.sop';c=p/f'commute{j}.cert'
            s.write_text(f'p sop commute {n} {len(a)} 1\n'+''.join(f'{v} {k}\n' for k,v in a.items())+f'1 {g}\n')
            assert run(s,c,10,audit_seconds=25)['status']=='PROVED'
        # Z on an individual target link fails to commute with the logical-X interaction.
        s=p/'noncommuting.sop';c=p/'noncommuting.cert'
        s.write_text(f'p sop commute {n} {len(a)} 1\n'+''.join(f'{v} {k}\n' for k,v in a.items())+'1 Z'+'I'*(n-1)+'\n')
        assert run(s,c,10,audit_seconds=25)['status']=='UNKNOWN'
        print('YM9_SUMMARY '+json.dumps(dict(cases=len(cases),positive=sum(x[-1] for x in cases),gauge_checks=n//2,max_qubits=240,continuum_claim=False)),flush=True)
if __name__=='__main__':main()
