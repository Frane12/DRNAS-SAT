"""Independent sparse Pauli certificate auditor (exact rationals, no dense matrix)."""
from fractions import Fraction as Q
from pathlib import Path
from collections import defaultdict
import hashlib
import itertools
import json
import sys

def check(source,cert):
    raw=Path(source).read_bytes()
    if len(raw)>2_000_000: raise ValueError('input limit')
    w=iter(raw.decode('ascii').split())
    if (next(w),next(w))!=('p','sop'): raise ValueError('header')
    task=next(w); n=int(next(w)); m=int(next(w))
    if not 1<=n<=256: raise ValueError('dimension')
    if task=='lower': target=Q(next(w)); k=0
    elif task=='commute': k=int(next(w)); target=0
    else: raise ValueError('task')
    def read(m):
        if not 0<=m<=4096: raise ValueError('term limit')
        a=defaultdict(Q)
        for _ in range(m):
            c=Q(next(w)); s=next(w)
            if len(s)!=n or set(s)-set('IXYZ'): raise ValueError('word')
            a[s]+=c
        return {s:c for s,c in a.items() if c}
    a=read(m); b=read(k)
    if next(w,None) is not None: raise ValueError('trailing data')
    z=iter(Path(cert).read_text().split())
    if (next(z),next(z),next(z))!=('drnas-sop-v1',hashlib.sha256(raw).hexdigest(),task): raise ValueError('binding')
    # Independent symplectic representation P=i^(x.z) X^x Z^z.
    def bits(s):
        x=sum(1<<i for i,c in enumerate(s) if c in 'XY')
        y=sum(1<<i for i,c in enumerate(s) if c in 'YZ')
        return x,y
    def anti(u,v):
        x,y=u; X,Y=v
        return ((x&Y).bit_count()+(y&X).bit_count())%2
    if task=='commute':
        accum=defaultdict(Q)
        for s,c in a.items():
            x,y=bits(s)
            for t,d in b.items():
                X,Y=bits(t)
                if anti((x,y),(X,Y)):
                    phase=((x&y).bit_count()+(X&Y).bit_count()+2*(y&X).bit_count())%4
                    # Common X^x Z^z basis; keep real and imaginary parts separately.
                    accum[(x^X,y^Y,phase%2)]+=c*d*(1 if phase<2 else -1)
        if any(accum.values()): raise ValueError('nonzero commutator')
        result={}
    else:
        claimed=Q(next(z)); count=int(next(z))
        lower=a.pop('I'*n,Q(0)); terms=sorted(a.items()); seen=set()
        if not 0<=count<=len(terms): raise ValueError('group count')
        for _ in range(count):
            typ=next(z); size=int(next(z))
            if not 1<=size<=len(terms): raise ValueError('group size')
            ids=[int(next(z)) for _ in range(size)]
            if any(not 0<=i<len(terms) or i in seen for i in ids) or len(set(ids))!=size: raise ValueError('partition')
            seen.update(ids); group=[terms[i] for i in ids]
            if typ=='A':
                bound=Q(next(z))
                if bound<0 or bound*bound<sum(c*c for s,c in group): raise ValueError('norm bound')
                if any(not anti(bits(s),bits(t)) for (s,c),(t,d) in itertools.combinations(group,2)): raise ValueError('anticommutation')
                lower-=bound
            elif typ=='D':
                if any(set(s)-set('IZ') for s,c in group): raise ValueError('diagonal word')
                support=sorted({i for s,c in group for i,ch in enumerate(s) if ch=='Z'})
                if len(support)>16: raise ValueError('block size')
                masks=[sum(1<<j for j,i in enumerate(support) if s[i]=='Z') for s,c in group]
                lower+=min(sum(c*(-1 if (mask&v).bit_count()%2 else 1) for mask,(s,c) in zip(masks,group)) for v in range(1<<len(support)))
            else: raise ValueError('group type')
        if len(seen)!=len(terms) or lower!=claimed or lower<target: raise ValueError('lower bound')
        result=dict(lower=str(lower),target=str(target),groups=count)
    if next(z,None) is not None: raise ValueError('trailing certificate')
    return dict(status='PROVED',certificate='SYMBOLIC_OPERATOR_EXACT',task=task,**result)

if __name__=='__main__':
    try: print(json.dumps(check(sys.argv[1],sys.argv[2])))
    except Exception as e: print(json.dumps(dict(status='REJECTED',error=str(e))));sys.exit(1)
