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
    if task in ('lower','lower-fixed'): target=Q(next(w)); k=0
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
        lower=a.pop('I'*n,Q(0)); terms=sorted(a.items()); seen=set(); rules=set()
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
                if 2<=size<=10 and bound<sum(abs(c) for s,c in group): rules.add('A'+str(size))
            elif typ=='C':
                if size>10: raise ValueError('commuting block size')
                bs=[bits(s) for s,c in group]
                if any(anti(u,v) for u,v in itertools.combinations(bs,2)): raise ValueError('noncommuting group')
                # Work in the X^x Z^z basis, storing phase modulo four.
                # A pivot reduction derives each generator dependency without
                # building the native product lookup table.
                basis={}; encoded=[]; generators=[]
                for (s,c),(x,y) in zip(group,bs):
                    original=(x,y); phase=(x&y).bit_count()%4
                    mask=0; px=py=pp=0; v=x|(y<<n)
                    while v:
                        pivot=v.bit_length()-1
                        if pivot not in basis:
                            j=len(basis)
                            # Store the original word as a new independent generator,
                            # reduced binary row and its expression in original generators.
                            basis[pivot]=(v,mask^(1<<j))
                            generators.append((x,y,phase))
                            mask=1<<j
                            break
                        row,expr=basis[pivot]; v^=row;mask^=expr
                    for j,(gx,gy,gp) in enumerate(generators):
                        if mask>>j&1:
                            pp=(pp+gp+2*(py&gx).bit_count())%4
                            px^=gx;py^=gy
                    if (px,py)!=original or (pp-phase)%2: raise ValueError('dependency')
                    encoded.append((mask,c*(1 if (pp-phase)%4==0 else -1)))
                lower+=min(sum(c*(-1 if (mask&val).bit_count()%2 else 1) for mask,c in encoded) for val in range(1<<len(generators)))
            elif typ=='D':
                if any(set(s)-set('IZ') for s,c in group): raise ValueError('diagonal word')
                support=sorted({i for s,c in group for i,ch in enumerate(s) if ch=='Z'})
                if len(support)>16: raise ValueError('block size')
                masks=[sum(1<<j for j,i in enumerate(support) if s[i]=='Z') for s,c in group]
                lower+=min(sum(c*(-1 if (mask&v).bit_count()%2 else 1) for mask,(s,c) in zip(masks,group)) for v in range(1<<len(support)))
            else: raise ValueError('group type')
            if typ in ('C','D') and 3<=size<=32:
                # Extract signed triple identities from the actual checked group.
                bs={bits(s):s for s,c in group}
                for u,v in itertools.combinations(bs,2):
                    x,y=u; X,Y=v; prod=(x^X,y^Y)
                    if prod not in bs or anti(u,v): continue
                    phase=((x&y).bit_count()+(X&Y).bit_count()+2*(y&X).bit_count()-(prod[0]&prod[1]).bit_count())%4
                    if phase in (0,2): rules.add('C3+' if phase==0 else 'C3-')
        if len(seen)!=len(terms) or lower!=claimed or lower<target: raise ValueError('lower bound')
        result=dict(lower=str(lower),target=str(target),groups=count,learned_rules=sorted(rules))
    if next(z,None) is not None: raise ValueError('trailing certificate')
    return dict(status='PROVED',certificate='SYMBOLIC_OPERATOR_EXACT',task=task,**result)

if __name__=='__main__':
    try: print(json.dumps(check(sys.argv[1],sys.argv[2])))
    except Exception as e: print(json.dumps(dict(status='REJECTED',error=str(e))));sys.exit(1)
