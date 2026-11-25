"""CORE-OP4 / YM7: verified rule extraction, frozen holdout and finite Z2 gauge controls.
This is a transfer experiment, not a continuum Yang-Mills proof.
"""
import itertools
import json
import os
import random
import tempfile
import time
from fractions import Fraction as Q
from pathlib import Path
from run import run
from symbolic_verify import check

MEM='DRNAS_CORE_RULE_MEMORY'
def emit(n, terms, target=0, task='lower'):
    return f'p sop {task} {n} {len(terms)} {target}\n'+''.join(f'{c} {s}\n' for c,s in terms)

def mul(a,b):
    phase=0; out=[]
    for x,y in zip(a,b):
        if x=='I': out.append(y)
        elif y=='I': out.append(x)
        elif x==y: out.append('I')
        else:
            u='XYZ'.index(x); v='XYZ'.index(y)
            out.append('XYZ'[3-u-v]); phase+=(1 if (v-u)%3==1 else 3)
    return ''.join(out),phase%4

def extract(src,cert):
    # Never extract from an unverified result. Rules are hints, not axioms.
    check(src,cert)
    z=iter(cert.read_text().split())
    next(z);next(z); task=next(z)
    if task not in ('lower','lower-fixed'): return set()
    w=iter(src.read_text().split()); next(w);next(w);next(w)
    n=int(next(w));m=int(next(w));next(w)
    a={}
    for _ in range(m):
        c=Q(next(w));s=next(w);a[s]=a.get(s,Q(0))+c
    terms=sorted(s for s,c in a.items() if c and s!='I'*n)
    next(z); count=int(next(z)); rules=set()
    for _ in range(count):
        typ=next(z);size=int(next(z)); words=[terms[int(next(z))] for _ in range(size)]
        if typ=='A':
            next(z)
            if 2<=size<=10: rules.add('A'+str(size))
        elif typ=='C' and size==3:
            s,p=mul(words[0],words[1])
            if s==words[2] and p in (0,2): rules.add('C3+' if p==0 else 'C3-')
    return rules

def execute(root,label,raw,memory=None):
    src=root/(label+'.op');cert=root/(label+'.cert')
    src.write_text(raw)
    if memory is None: os.environ.pop(MEM,None)
    else: os.environ[MEM]=str(memory)
    result=run(src,cert,5,audit_seconds=15)
    return result,src,cert

def word(n, entries):
    s=['I']*n
    for i,c in entries:s[i]=c
    return ''.join(s)

def gauge(n):
    # A periodic one-dimensional Z2 link model. Gauss generators and Wilson loop.
    g=[word(n,[(i,'X'),((i+1)%n,'X')]) for i in range(n)]
    b='Z'*n
    terms=[(Q(n+1,2),'I'*n)]+[(Q(-1,2),s) for s in g+[b]]
    return g,b,terms

def main():
    old=os.environ.get(MEM)
    try:
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); memory=root/'rules.txt'
            training=[
                emit(1,[(Q(3,2),'I'),(1,'X'),(1,'Z')]),
                emit(2,[(1,'II'),(1,'XI'),(1,'IX'),(1,'XX')]),
                emit(2,[(1,'II'),(1,'XX'),(1,'YY'),(-1,'ZZ')])]
            rules=set()
            for i,raw in enumerate(training):
                r,s,c=execute(root,f'train{i}',raw)
                assert r['status']=='PROVED',r
                rules|=extract(s,c)
            assert {'A2','C3+','C3-'}<=rules,rules
            memory.write_text('drnas-rule-memory-v1\n'+'\n'.join(sorted(rules))+'\n')
            print('OP4_RULES '+json.dumps(sorted(rules)),flush=True)
            # Fixed seed, disjoint from training: dimensions, labels, coefficients
            # and local cyclic Pauli frames change; identical theorem families.
            rng=random.Random(7152026); hold=[]
            for i in range(24):
                n=8+i; u,v=rng.sample(range(n),2); c=rng.randint(2,9)
                axes=list('XYZ');shift=rng.randrange(3);axes=axes[shift:]+axes[:shift]
                if i%3==0:
                    terms=[(Q(3*c,2),'I'*n),(c,word(n,[(u,axes[0])])),(c,word(n,[(u,axes[1])]))]
                elif i%3==1:
                    x=word(n,[(u,axes[0])]);y=word(n,[(v,axes[1])]);z,_=mul(x,y)
                    terms=[(c,'I'*n),(c,x),(c,y),(c,z)]
                else:
                    x=word(n,[(u,axes[0]),(v,axes[0])]);y=word(n,[(u,axes[1]),(v,axes[1])]);z,p=mul(x,y)
                    assert p==2
                    terms=[(c,'I'*n),(c,x),(c,y),(-c,z)]
                rng.shuffle(terms)
                hold.append(emit(n,terms))
            counts={a:0 for a in ('fixed','adaptive','memory')}; hits=0
            for i,raw in enumerate(hold):
                for arm in ('fixed','adaptive','memory'):
                    inp=raw.replace('p sop lower ','p sop lower-fixed ',1) if arm=='fixed' else raw
                    r,_,_=execute(root,f'{arm}{i}',inp,memory if arm=='memory' else None)
                    counts[arm]+=r['status']=='PROVED'
                    hits+=arm=='memory' and r.get('telemetry',{}).get('memory_proved',False)
                    print('OP4_ROW '+json.dumps(dict(id=i,arm=arm,**r)),flush=True)
            assert counts['memory']==len(hold) and hits==len(hold),(counts,hits)
            # Invalid positive-bound claim cannot be certified by rule replay.
            negative=emit(1,[(1,'I'),(1,'X'),(1,'Z')])
            r,_,_=execute(root,'negative',negative,memory)
            assert r['status']=='UNKNOWN',r
            for n in (4,6,12):
                gs,b,terms=gauge(n)
                for j,g in enumerate(gs):
                    raw=f'p sop commute {n} {len(terms)} 1\n'+''.join(f'{c} {s}\n' for c,s in terms)+f'1 {g}\n'
                    r,_,_=execute(root,f'gauge{n}-{j}',raw,memory)
                    assert r['status']=='PROVED',r
                r,_,_=execute(root,f'energy{n}',emit(n,terms),memory)
                assert r['status']=='PROVED',r
            # A single Z link violates one Gauss generator.
            gs,b,terms=gauge(4)
            r,_,_=execute(root,'gauge-negative',f'p sop commute 4 1 1\n1 {gs[0]}\n1 ZIII\n',memory)
            assert r['status']=='UNKNOWN',r
            # Full finite 16-dimensional matrix: sum of commuting projectors.
            # Exact gap claim with E=0; verifier checks kernel/excited space.
            n=4; dim=1<<n
            mat=[[Q(0) for _ in range(dim)] for _ in range(dim)]
            for j in range(dim):
                mat[j][j]+=Q(n+1,2)-Q((-1)**j.bit_count(),2)
                for i in range(n):mat[j^((1<<i)|(1<<((i+1)%n)))][j]-=Q(1,2)
            raw='p op gap 16 0 1\n'+'\n'.join(' '.join(map(str,row)) for row in mat)+'\n'
            r,_,_=execute(root,'finite-gap',raw)
            assert r['status']=='PROVED',r
            print('YM7_FINITE_GAP '+json.dumps(r),flush=True)
            print('OP4_SUMMARY '+json.dumps(dict(holdout=len(hold),proved=counts,memory_hits=hits,gauge_sizes=[4,6,12],finite_gap_lower=1,continuum_claim=False)),flush=True)
    finally:
        if old is None: os.environ.pop(MEM,None)
        else: os.environ[MEM]=old
if __name__=='__main__':main()
