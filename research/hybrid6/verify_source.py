#!/usr/bin/env python3
"""Independent source-clause checker for HYBRID-6 witnesses.
Uses original GitHub CNFs, does not import or trust the producer.
This checks restricted mathematical UNSAT certificates, NOT DRAT proofs.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]

def load(path):
    clauses=[]; current=[]; n=m=None
    for raw in path.read_text().splitlines():
        line=raw.strip()
        if not line or line.startswith('c'): continue
        if line.startswith('p '):
            p=line.split()
            assert len(p)==4 and p[:2]==['p','cnf']
            n,m=map(int,p[2:]);continue
        for item in line.split():
            lit=int(item)
            if lit: current.append(lit)
            else:
                clauses.append(tuple(current));current=[]
    assert n is not None and not current and m==len(clauses)
    assert all(1<=abs(l)<=n for c in clauses for l in c)
    return clauses

def row(clauses, witness):
    vs=witness['vars']; rhs=witness['rhs']; inds=witness['clauses']
    k=len(vs)
    assert 2<=k<=4 and len(set(vs))==k and rhs in (0,1)
    assert len(inds)==(1<<(k-1)) and len(set(inds))==len(inds)
    forbidden=set()
    for idx in inds:
        c=clauses[idx]
        assert len(c)==k and set(abs(l) for l in c)==set(vs)
        bits=tuple(int(next(l for l in c if abs(l)==v)<0) for v in vs)
        assert sum(bits)%2 != rhs
        forbidden.add(bits)
    assert len(forbidden)==(1<<(k-1))
    mask=0
    for v in vs: mask^=1<<(v-1)
    return mask,rhs

def check_xor(clauses, rows):
    mask=rhs=0
    for w in rows:
        m,r=row(clauses,w);mask^=m;rhs^=r
    assert mask==0 and rhs==1, 'XOR witness does not derive 0=1'

def check_clique(clauses, info):
    k=info['colors'];verts=info['clique']
    assert len(verts)==k+1
    groups=[];seen=set()
    for w in verts:
        c=clauses[w['clause']]
        assert tuple(w['vars'])==c and len(c)==k and all(v>0 for v in c)
        assert not seen.intersection(c)
        seen.update(c);groups.append(c)
    forbidden=set(clauses)
    for i,a in enumerate(groups):
        for b in groups[i+1:]:
            for t in range(k):
                assert (-a[t],-b[t]) in forbidden or (-b[t],-a[t]) in forbidden

def check_hybrid(clauses, info):
    onehot=tuple(info['onehot_vars'])
    assert clauses[info['onehot_clause']]==onehot and len(onehot)>=2
    assert len(set(onehot))==len(onehot) and all(v>0 for v in onehot)
    source=set(clauses)
    for i,v in enumerate(onehot):
        for u in onehot[i+1:]:
            assert (-v,-u) in source or (-u,-v) in source
    mask=rhs=0
    for w in info['rows']:
        m,r=row(clauses,w);mask^=m;rhs^=r
    wanted=0
    for x in onehot:wanted^=1<<(x-1)
    assert mask==wanted and rhs==0, 'parity does not contradict one-hot'

def main():
    report=json.loads((HERE/'research/hybrid6/witnesses.json').read_text())
    xor=load(HERE/report['xor_grid']['source'])
    graph=load(HERE/report['graph_k11']['source'])
    mixed=load(HERE/report['hybrid_mixed8']['source'])
    check_xor(xor,report['xor_grid']['rows'])
    print('SOURCE VERIFIED: XOR grid contradiction')
    check_clique(graph,report['graph_k11'])
    print('SOURCE VERIFIED: graph K11 clique')
    check_hybrid(mixed,report['hybrid_mixed8'])
    print('SOURCE VERIFIED: one-hot + XOR mixed contradiction')
    # Deliberate source mutations: every previously valid witness must fail.
    bad_xor=xor.copy()
    witness=report['xor_grid']['rows'][0]
    k=witness['clauses'][0];c=list(bad_xor[k]);c[0]*=-1;bad_xor[k]=tuple(c)
    try:check_xor(bad_xor,report['xor_grid']['rows'])
    except AssertionError:print('REJECTED: mutated XOR source')
    else:raise AssertionError('XOR mutation wrongly accepted')
    bad_graph=graph.copy()
    a,b=report['graph_k11']['clique'][:2]
    target=(-a['vars'][0],-b['vars'][0])
    j=next(i for i,c in enumerate(graph) if c==target or c==target[::-1])
    bad_graph[j]=(a['vars'][0],-b['vars'][0])
    try:check_clique(bad_graph,report['graph_k11'])
    except AssertionError:print('REJECTED: mutated graph source')
    else:raise AssertionError('graph mutation wrongly accepted')
    bad_mixed=mixed.copy()
    j=next(i for i,c in enumerate(mixed) if c in [(-1,-2),(-2,-1)])
    bad_mixed[j]=(1,-2)
    try:check_hybrid(bad_mixed,report['hybrid_mixed8'])
    except AssertionError:print('REJECTED: removed source capacity')
    else:raise AssertionError('mixed mutation wrongly accepted')
    sat=load(HERE/'research/hybrid6/mixed8-sat-control.cnf')
    try:check_hybrid(sat,report['hybrid_mixed8'])
    except AssertionError:print('REJECTED: SAT-control mixed witness')
    else:raise AssertionError('SAT control wrongly accepted')
    print('HYBRID6_SOURCE_AUDIT_PASS')

if __name__=='__main__':main()
