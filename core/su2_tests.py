"""YM12: finite spin-1/2 SU(2) representation and Casimir controls.
Not a lattice gauge field or continuum Yang-Mills proof.
"""
from collections import defaultdict
from fractions import Fraction as Q
from pathlib import Path
from math import comb
import itertools,random,tempfile,json
from run import run
from symbolic_verify import check

def word(n,entries):
    w=['I']*n
    for i,c in entries:w[i]=c
    return ''.join(w)
def generators(n,block):
    return [{word(n,[(i,axis)]):Q(1,2) for i in block} for axis in 'XYZ']
def build(sizes,seed):
    n=sum(sizes);rng=random.Random(seed);perm=list(range(n));rng.shuffle(perm)
    a=defaultdict(Q);blocks=[];off=0;gap=None;dim=1
    for m in sizes:
        block=perm[off:off+m];off+=m;blocks.append(block)
        weight=Q(rng.randrange(1,5),2)
        a['I'*n]+=3*weight*m/4
        for i,j in itertools.combinations(block,2):
            for axis in 'XYZ':a[word(n,[(i,axis),(j,axis)])]+=weight/2
        gap=2*weight if gap is None else min(gap,2*weight)
        dim*=comb(m,m//2)-comb(m,m//2-1)
    return n,dict(a),blocks,gap,dim
def rows(a):return ''.join(f'{c} {s}\n' for s,c in a.items())
def cas(n,a,g):return f'p sop casimir-gap {n} {len(a)} {g}\n'+rows(a)
def lie(n,a,b,c):return f'p sop lie {n} {len(a)} {len(b)} {len(c)}\n'+rows(a)+rows(b)+rows(c)
def commute(n,a,b):return f'p sop commute {n} {len(a)} {len(b)}\n'+rows(a)+rows(b)
def main():
    with tempfile.TemporaryDirectory() as d:
        p=Path(d);idx=0;positive=negative=0
        def test(label,raw,expected=True):
            nonlocal idx,positive,negative
            idx+=1;s=p/f'{idx}.sop';c=p/f'{idx}.cert';s.write_text(raw)
            r=run(s,c,10,audit_seconds=25)
            assert r['status']==('PROVED' if expected else 'UNKNOWN'),(label,r)
            if expected:positive+=1
            else:negative+=1
            print('YM12_ROW '+json.dumps(dict(id=label,**r)),flush=True)
            return r,s,c
        for sizes in ([2],[4],[6],[8],[4]*12,[6]*20,[8]*30):
            n,a,blocks,gap,dim=build(sizes,1234+sum(sizes))
            r,s,c=test(f'casimir-{n}',cas(n,a,gap))
            assert r['gap_lower']==str(gap) and r['ground_dimension']==str(dim) and r['blocks']==len(blocks),r
            old=c.read_text();lines=old.splitlines();lines[-1]=f'{len(blocks)} {gap+1}';c.write_text('\n'.join(lines)+'\n')
            try:check(s,c)
            except ValueError:pass
            else:raise AssertionError('tamper accepted')
            c.write_text(old)
            x,y,z=generators(n,blocks[0])
            for i,(u,v,w) in enumerate(((x,y,z),(y,z,x),(z,x,y))):test(f'lie-{n}-{i}',lie(n,u,v,w))
            for i,u in enumerate((x,y,z)):test(f'symmetry-{n}-{i}',commute(n,a,u))
        n,a,blocks,gap,dim=build([4,4],77)
        x,y,z=generators(n,blocks[0]);u,v,w=generators(n,blocks[1])
        test('independent-local-algebras',commute(n,x,v))
        test('wrong-lie-sign',lie(n,x,y,{s:-c for s,c in z.items()}),False)
        test('overshoot',cas(n,a,gap+1),False)
        test('shift',cas(n,{**a,'I'*n:a['I'*n]+1},gap),False)
        bad=dict(a);key=next(s for s in a if 'X' in s);bad[key]+=1
        test('anisotropic',cas(n,bad,gap),False)
        test('broken-symmetry',commute(n,bad,dict(y)|dict(v)),False)
        test('odd-spin-block',cas(3,{'III':Q(9,4),**{word(3,[(i,t),(j,t)]):Q(1,2) for i,j in itertools.combinations(range(3),2) for t in 'XYZ'}},1),False)
        print('YM12_SUMMARY '+json.dumps(dict(positive=positive,negative=negative,max_qubits=240,finite_spin_only=True,continuum_claim=False)),flush=True)
if __name__=='__main__':main()
