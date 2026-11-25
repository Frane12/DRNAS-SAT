"""YM11: no reference generators in the source; relabelled signed holdout."""
from collections import defaultdict
from fractions import Fraction as Q
from pathlib import Path
import tempfile,json,random
from run import run
from symbolic_verify import check
from stabilizer_gap_tests import build

def emit(n,a,gamma):
    return f'p sop auto-stabilizer-gap {n} {len(a)} {gamma}\n'+''.join(f'{c} {p}\n' for p,c in a.items())

def relabel(a,n,seed):
    # Independent local cyclic Clifford frames and wire permutations.
    # All are unitaries, so spectrum and degeneracy are preserved.
    rng=random.Random(seed);perm=list(range(n));rng.shuffle(perm)
    frames=[rng.randrange(3) for _ in range(n)]
    def transform(p):
        out=['I']*n
        for i,c in enumerate(p):out[perm[i]]='I' if c=='I' else 'XYZ'[('XYZ'.index(c)+frames[i])%3]
        return ''.join(out)
    rows=[(transform(p),c) for p,c in a.items()];rng.shuffle(rows)
    return dict(rows)

def weighted(n,kind,seed,degenerate=False):
    a,s=build(n,kind,True,degenerate)
    # Keep a certified lower bound 1 while changing coefficients of D and
    # the positive interactions. No generator list is sent to the solver.
    rng=random.Random(seed)
    for p,sign in s.items():
        delta=Q(rng.randrange(3),2)
        a['I'*n]=a.get('I'*n,Q(0))+delta/2
        a[p]=a.get(p,Q(0))-sign*delta/2
    return relabel({p:c for p,c in a.items() if c},n,seed)

def main():
    cases=[]
    for n in (4,12,48,120,240):
        cases.append((f'bell-{n}',n,weighted(n,'bell',117+n),1,n))
    for n in (5,12,48,120,240):
        cases.append((f'graph-{n}',n,weighted(n,'graph',217+n),1,n))
    cases.append(('degenerate',12,weighted(12,'bell',317,True),1,6))
    # Unweighted independent generators with a dependent signed relation.
    cases.append(('signed-phase',2,{'II':Q(3,2),'XX':-Q(1,2),'ZZ':-Q(1,2),'YY':Q(1,2)},1,2))
    a=weighted(12,'bell',417)
    cases += [('overshoot',12,a,100,None),('wrong-shift',12,{**a,'I'*12:a['I'*12]+1},1,None),
              ('inconsistent',2,{'II':Q(3,2),'XX':-Q(1,2),'YY':-Q(1,2),'ZZ':-Q(1,2)},1,None),
              ('negative-H',1,{'I':-Q(1,2),'Z':Q(1,2)},1,None),
              ('zero',1,{'I':Q(0)},1,None)]
    positives=negatives=0
    with tempfile.TemporaryDirectory() as d:
        root=Path(d)
        for i,(label,n,a,gamma,rank) in enumerate(cases):
            src=root/f'{i}.sop';cert=root/f'{i}.cert';src.write_text(emit(n,a,gamma))
            r=run(src,cert,10,audit_seconds=25)
            if rank is not None and r['status']=='PROVED':
                assert r['rank']==rank and r['ground_dimension']==str(1<<(n-rank)),(label,r)
                positives+=1
                old=cert.read_text();lines=old.splitlines()
                sign,word=lines[4].split();lines[4]=f'{-int(sign)} {word}'
                cert.write_text('\n'.join(lines)+'\n')
                try:check(src,cert)
                except ValueError:pass
                else:raise AssertionError('tampered stabilizer accepted')
                cert.write_text(old)
            elif rank is None:
                assert r['status']=='UNKNOWN',(label,r)
                negatives+=1
            else:
                assert r['status']=='UNKNOWN',(label,r)
            print('YM11_ROW '+json.dumps(dict(id=label,**r)),flush=True)
    print('YM11_SUMMARY '+json.dumps(dict(cases=len(cases),positive=positives,positive_total=sum(x[-1] is not None for x in cases),negative_controls=negatives,max_qubits=240,reference_supplied=False,continuum_claim=False)),flush=True)
    assert positives>0,'no positive discovery'
if __name__=='__main__':main()
