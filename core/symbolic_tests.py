"""Prospective symbolic checks; includes a source-derived SAT projector control."""
import pathlib
import tempfile
import itertools
from fractions import Fraction
from collections import defaultdict
from run import run
from symbolic_verify import check

def lift(n,clauses):
    a=defaultdict(Fraction)
    for clause in clauses:
        # All literals have distinct variables in these controls.
        for mask in range(1<<len(clause)):
            s=['I']*n; c=Fraction(1,1<<len(clause))
            for j,l in enumerate(clause):
                if mask>>j&1:
                    s[abs(l)-1]='Z'; c*=1 if l>0 else -1
            a[''.join(s)]+=c
    return [(str(c),s) for s,c in sorted(a.items()) if c]

def main():
    cases=[]
    def lower(n,terms,target,expected):
        cases.append((f'p sop lower {n} {len(terms)} {target}\n'+''.join(f'{c} {s}\n' for c,s in terms),expected))
    def commute(n,a,b,expected):
        cases.append((f'p sop commute {n} {len(a)} {len(b)}\n'+''.join(f'{c} {s}\n' for c,s in a+b),expected))
    lower(1,[(2,'I'),(1,'X'),(1,'Y'),(1,'Z')],0,True)
    lower(1,[(1,'I'),(1,'X'),(1,'Y')],0,False)
    lower(1,[(3,'I'),(1,'X'),(1,'Z')],1,True)
    lower(2,[(1,'ZI'),(1,'IZ'),(1,'ZZ'),(1,'II')],0,True)
    lower(2,[(1,'ZI'),(1,'IZ'),(1,'ZZ')],0,False)
    commute(1,[(1,'X')],[(1,'Y')],False)
    commute(2,[(1,'XX')],[(1,'ZZ')],True)
    commute(1,[(1,'X'),(1,'Z')],[(2,'X'),(2,'Z')],True)
    commute(1,[(1,'Y'),(1,'Y'),(-2,'Y')],[(1,'Z')],True)
    for n in [2,32,128,256]:
        # Disjoint contradictory pairs: exact energy n, no 2**n allocation.
        cs=[(l,) for i in range(1,n+1) for l in (i,-i)]
        lower(n,lift(n,cs),n,True)
        # SAT control: nonnegative but not strictly positive.
        lower(n,lift(n,[(1,)]),1,False)
    # Four clauses forbid all two-variable assignments.
    cs=list(itertools.product([1,-1],[2,-2]))
    lower(2,lift(2,cs),1,True)
    lower(2,lift(2,cs[:-1]),1,False)
    # Independent frustrated triangles: each Z_i Z_j sum >= -1.
    # Use 60 disjoint triples (180 qubits).
    n=180; terms=[(60,'I'*n)]
    for i in range(0,n,3):
        for u,v in [(i,i+1),(i+1,i+2),(i,i+2)]:
            s=['I']*n;s[u]=s[v]='Z';terms.append((1,''.join(s)))
    lower(n,terms,0,True)
    lower(n,terms,1,False)
    with tempfile.TemporaryDirectory() as d:
        p=pathlib.Path(d); src=p/'input.sop'; cert=p/'output.cert'
        for i,(raw,expected) in enumerate(cases):
            cert.unlink(missing_ok=True);src.write_text(raw)
            result=run(src,cert,5,audit_seconds=15)
            assert result['status']==('PROVED' if expected else 'UNKNOWN'),(i,result)
            if expected:
                orig=cert.read_text();cert.write_text(orig.replace('drnas-sop-v1','wrong',1))
                try:check(src,cert)
                except ValueError:pass
                else:raise AssertionError('tamper accepted')
        src.write_text('p sop lower 1 1 0\n1 X\n');cert.unlink(missing_ok=True)
        assert run(src,cert,5)['status']=='UNKNOWN'
    print(f'symbolic_cases={len(cases)+1} PASS')
if __name__=='__main__':main()
