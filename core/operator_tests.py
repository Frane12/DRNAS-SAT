"""Native CORE operator smoke/negative tests, including small Boolean projector lift."""
import itertools
import pathlib
import tempfile
from run import run
from operator_verify import verify
ROOT=pathlib.Path(__file__).resolve().parent
def main():
    cases=[
        ('psd',[[1,-1],[-1,1]],'',True),
        ('psd',[[0,1],[1,0]],'',False),
        ('pd',[[2,1],[1,2]],'',True),
        ('pd',[[1,-1],[-1,1]],'',False),
        ('gap',[[1,-1],[-1,1]],'0 2',True),
        ('gap',[[1,-1],[-1,1]],'0 3',False),
        ('gap',[[1,-1],[-1,1]],'-1 1',False),
        ('gap',[[0,0],[0,0]],'0 1',False),
        ('auto-gap',[[3,-1],[-1,3]],'2',True),
        ('auto-gap',[[2,1],[1,2]],'3',False),
        ('psd',[['1/2','-1/2'],['-1/2','1/2']],'',True),
    ]
    # An UNSAT Boolean formula: x AND not x. Diagonal energies [1,1].
    # SAT control: x. Diagonal energies [1,0]. This is a small explicit lift,
    # not a scalable CNF solver or a standard CNF proof.
    for clauses, expected in [([(1,),(-1,)],True), ([(1,)],False)]:
        es=[sum(not any((bits[abs(l)-1]==1)==(l>0) for l in c) for c in clauses)
            for bits in itertools.product([0,1],repeat=1)]
        cases.append(('pd',[[es[0],0],[0,es[1]]],'',expected))
    with tempfile.TemporaryDirectory() as tmp:
        d=pathlib.Path(tmp); source=d/'in.op'; cert=d/'out.cert'
        for kind,a,args,expected in cases:
            cert.unlink(missing_ok=True)
            source.write_text(f'p op {kind} {len(a)} {args}\n'+'\n'.join(' '.join(map(str,r)) for r in a)+'\n')
            result=run(source,cert,5,audit_seconds=15)
            assert result['status']==('PROVED' if expected else 'UNKNOWN'),(kind,result)
            if expected:
                old=cert.read_text(); cert.write_text(old.replace('drnas-op-v1','bad',1))
                try: verify(source,cert)
                except ValueError: pass
                else: raise AssertionError('tamper accepted')
        for b,expected in [('1 0 0 -1',False),('2 3 3 2',True)]:
            cert.unlink(missing_ok=True);source.write_text('p op commute 2\n0 1 1 0\n'+b+'\n')
            assert run(source,cert,5)['status']==('PROVED' if expected else 'UNKNOWN')
    print(f'operator_cases={len(cases)+2} PASS')
if __name__=='__main__': main()
