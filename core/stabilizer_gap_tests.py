"""YM10: exact comparison to entangled stabilizer reference spaces."""
from collections import defaultdict
from fractions import Fraction as Q
from pathlib import Path
import tempfile,json
from run import run
from symbolic_verify import check

def word(n,entries):
    w=['I']*n
    for i,c in entries:w[i]=c
    return ''.join(w)

def mul(a,b):
    w=[];p=0
    for x,y in zip(a,b):
        if x=='I':w.append(y)
        elif y=='I':w.append(x)
        elif x==y:w.append('I')
        else:
            u='XYZ'.index(x);v='XYZ'.index(y);w.append('XYZ'[3-u-v]);p+=1 if (v-u)%3==1 else 3
    assert p%2==0
    return ''.join(w),1 if p%4==0 else -1

def build(n,kind,negative_sign=False,degenerate=False):
    if kind=='bell':
        s=[(word(n,[(i,'X'),(i+1,'X')]),-1 if negative_sign and i%4==0 else 1) for i in range(0,n,2)]
        z=[(word(n,[(i,'Z'),(i+1,'Z')]),1) for i in range(0,n,2)]
        t=[word(n,[((i+2)%n,'Z')]) for i in range(0,n,2)]
        generators=s+([] if degenerate else z)
    else:
        s=[(word(n,[(i,'X'),((i-1)%n,'Z'),((i+1)%n,'Z')]),-1 if negative_sign and i%2==0 else 1) for i in range(n)]
        t=[word(n,[((i+1)%n,'Z')]) for i in range(n)]
        generators=s
    a=defaultdict(Q);id='I'*n
    for p,sign in generators:a[id]+=Q(1,2);a[p]-=Q(sign,2)
    # H = D + sum of positive products. Local terms commute internally,
    # but the complete interacting Hamiltonian contains noncommuting terms.
    for (p,sign),q in zip(s,t):
        r,phase=mul(p,q)
        a[id]+=Q(1,4);a[p]-=Q(sign,4);a[q]-=Q(1,4);a[r]+=Q(sign*phase,4)
    return {p:c for p,c in a.items() if c},dict(generators)

def emit(n,a,s,gamma):
    return f'p sop stabilizer-gap {n} {len(a)} {gamma} {len(s)}\n'+''.join(f'{c} {p}\n' for p,c in sorted(a.items()))+''.join(f'{c} {p}\n' for p,c in sorted(s.items()))

def main():
    cases=[]
    for n in (4,12,48,120,240):
        a,s=build(n,'bell');cases.append((f'bell-{n}',n,a,s,1,n))
    for n in (5,12,48,120,240):
        a,s=build(n,'graph',True);cases.append((f'graph-{n}',n,a,s,1,n))
    a,s=build(12,'bell',True,True);cases.append(('degenerate',12,a,s,1,6))
    a,s=build(4,'bell',True);cases.append(('signed',4,a,s,1,4))
    # Signed Y phases and dependent but consistent stabilizers.
    s={'XX':1,'ZZ':1,'YY':-1};a={'II':Q(3,2),'XX':-Q(1,2),'ZZ':-Q(1,2),'YY':Q(1,2)}
    cases.append(('phase-dependent',2,a,s,1,2))
    cases.append(('inconsistent',2,a,{**s,'YY':1},1,None))
    cases.append(('noncommuting-reference',2,a,{'XI':1,'ZI':1},1,None))
    a,s=build(4,'bell');cases.append(('bad-ground',4,{**a,'ZIII':Q(1)},s,1,None))
    cases.append(('overshoot',4,a,s,100,None))
    # H = -D has the right kernel but fails positivity.
    cases.append(('negative-H',2,{'II':Q(-1,2),'XX':Q(1,2)},{'XX':1},1,None))
    with tempfile.TemporaryDirectory() as d:
        root=Path(d)
        for i,(label,n,a,s,gamma,rank) in enumerate(cases):
            src=root/f'{i}.sop';cert=root/f'{i}.cert';src.write_text(emit(n,a,s,gamma))
            r=run(src,cert,10,audit_seconds=25)
            assert r['status']==('PROVED' if rank is not None else 'UNKNOWN'),(label,r)
            if rank is not None:
                assert r['rank']==rank and r['ground_dimension']==str(1<<(n-rank)),(label,r)
                old=cert.read_text();lines=old.splitlines();lines[3]=str(rank+1);cert.write_text('\n'.join(lines)+'\n')
                try:check(src,cert)
                except ValueError:pass
                else:raise AssertionError('rank tamper accepted')
                cert.write_text(old)
            print('YM10_ROW '+json.dumps(dict(id=label,**r)),flush=True)
    print('YM10_SUMMARY '+json.dumps(dict(cases=len(cases),positive=sum(x[-1] is not None for x in cases),max_qubits=240,reference_supplied=True,continuum_claim=False)),flush=True)
if __name__=='__main__':main()
