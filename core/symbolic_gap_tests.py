"""YM8: matrix-free exact gaps for commuting Pauli projector Hamiltonians."""
import json
import tempfile
from pathlib import Path
from fractions import Fraction as Q
from run import run
from symbolic_verify import check

def word(n,ix,axis):
    a=['I']*n
    for i in ix:a[i]=axis
    return ''.join(a)

def toric(L):
    n=2*L*L
    def e(x,y,d):return 2*((y%L)*L+(x%L))+d
    stars=[]; faces=[]
    for y in range(L):
        for x in range(L):
            stars.append(word(n,[e(x,y,0),e(x-1,y,0),e(x,y,1),e(x,y-1,1)],'X'))
            faces.append(word(n,[e(x,y,0),e(x,y+1,0),e(x,y,1),e(x+1,y,1)],'Z'))
    return n,[(Q(-1,2),s) for s in stars+faces]

def emit(n,terms,target=1,constant=None):
    if constant is None:constant=sum(abs(c) for c,s in terms)
    return f'p sop projector-gap {n} {len(terms)+1} {target}\n{constant} '+ 'I'*n+'\n'+''.join(f'{c} {s}\n' for c,s in terms)

def main():
    cases=[]
    for L in (3,5,8,11):
        n,terms=toric(L)
        cases.append((f'toric-{L}',emit(n,terms),True,n-2))
    cases += [
        ('negative-phase-valid',emit(2,[(-1,'XX'),(-1,'YY'),(1,'ZZ')],2),True,2),
        ('negative-phase-invalid',emit(2,[(-1,'XX'),(-1,'YY'),(-1,'ZZ')],2),False,None),
        ('positive-phase-invalid',emit(2,[(-1,'ZI'),(-1,'IZ'),(1,'ZZ')],2),False,None),
        ('noncommuting',emit(1,[(-1,'X'),(-1,'Z')]),False,None),
        ('wrong-shift',emit(1,[(-1,'Z')],constant=0),False,None),
        ('too-large-bound',emit(1,[(-1,'Z')],3),False,None),
        ('zero-excited-space',emit(1,[],1),False,None),
        ('weighted',emit(2,[(-Q(3,2),'ZI'),(Q(5,2),'IZ')],3),True,2),
    ]
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)
        for i,(name,raw,expected,rank) in enumerate(cases):
            s=p/f'{i}.sop';c=p/f'{i}.cert';s.write_text(raw)
            r=run(s,c,10,audit_seconds=25)
            assert r['status']==('PROVED' if expected else 'UNKNOWN'),(name,r)
            if expected:
                assert r['rank']==rank,(name,r)
                old=c.read_text();lines=old.splitlines();lines[-1]=f'{rank+1} {r["gap_lower"]}'
                c.write_text('\n'.join(lines)+'\n')
                try:check(s,c)
                except ValueError:pass
                else:raise AssertionError('tampered rank accepted')
                c.write_text(old)
            print('YM8_ROW '+json.dumps(dict(id=name,**r)),flush=True)
    print('YM8_SUMMARY '+json.dumps(dict(cases=len(cases),positive=sum(c[2] for c in cases),max_qubits=242,continuum_claim=False)),flush=True)
if __name__=='__main__':main()
