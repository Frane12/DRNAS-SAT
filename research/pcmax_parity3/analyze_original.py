#!/usr/bin/env python3
"""Polynomial-time affine-parity audit of the archived PCMAX BDD overapproximation.
The analysis uses exactly the CNF-checked structure from capacity.json.
NO attempt is made to infer completeness for arbitrary CNFs or BDD families.
"""
from pathlib import Path
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[2]
CASE=ROOT/'evidence'/'pcmax-weighted2'/'05'
sys.path.insert(0,str(ROOT/'research'/'pcmax_capacity'))
from check_capacity import check

source=(CASE/'original.cnf').read_bytes()
cert=json.loads((CASE/'capacity.json').read_text())
checked=check(source,cert)
assert checked['status']=='UNSAT_STRUCTURAL_CERTIFICATE_VERIFIED'
assert hashlib.sha256(source).hexdigest()==cert['source_sha256']
groups=cert['selected_groups']
N=len(groups)
gid={v:i for i,g in enumerate(groups) for v in g}

class GF2Basis:
    def __init__(self): self.piv={}
    def add(self,v):
        while v:
            p=v.bit_length()-1
            if p not in self.piv:
                self.piv[p]=v
                return True
            v ^= self.piv[p]
        return False
    def reduce(self,v):
        while v:
            p=v.bit_length()-1
            if p not in self.piv: return v
            v ^= self.piv[p]
        return 0
    def vectors(self):return list(self.piv.values())

def affine_machine(m):
    order=m['variable_order']
    rank={v:i for i,v in enumerate(order)}
    trans={q:(x,lo,hi) for q,x,lo,hi in m['transitions']}
    t,f=m['true_terminal'],m['false_terminal']
    ranks={q:rank[x] for q,(x,_,_) in trans.items()}
    ranks[t]=ranks[f]=len(order)
    memo={}
    def bit(v):
        g=gid.get(v)
        return 0 if g is None else 1<<g
    def rec(q):
        if q==f:return None
        if q==t:return (0,[])
        if q in memo:return memo[q]
        x,lo,hi=trans[q]
        i=rank[x]
        arms=[]
        for child,high in ((lo,False),(hi,True)):
            res=rec(child)
            if res is None:continue
            anchor,vecs=res
            b=GF2Basis()
            for v in vecs:b.add(v)
            for p in range(i+1,ranks[child]):
                b.add(bit(order[p]))
            arms.append((anchor ^ (bit(x) if high else 0),b))
        if not arms:
            memo[q]=None
            return None
        base=arms[0][0]
        b=GF2Basis()
        for anchor,local in arms:
            for v in local.vectors():b.add(v)
            b.add(base^anchor)
        memo[q]=(base,b.vectors())
        return memo[q]
    result=rec(m['root'])
    if result is None:
        return None
    anchor,vecs=result
    b=GF2Basis()
    for v in vecs:b.add(v)
    for p in range(ranks[m['root']]):b.add(bit(order[p]))
    return anchor,b.vectors()

all_basis=GF2Basis()
anchor_sum=0
machine_ranks=[]
for index,m in enumerate(cert['machines']):
    result=affine_machine(m)
    if result is None:
        raise RuntimeError('machine has no accepting BDD path')
    anchor,vecs=result
    anchor_sum ^= anchor
    for v in vecs:all_basis.add(v)
    machine_ranks.append(len(vecs))
target=((1<<N)-1)^anchor_sum
residue=all_basis.reduce(target)
out={'status':'NO_GLOBAL_PARITY_WITNESS_IN_SELECTED_GROUP_FAMILY' if residue==0 else 'PARITY_WITNESS_EXISTS',
    'source_sha256':cert['source_sha256'],
    'input_type':'unchanged archived PCMAX original CNF',
    'groups':N,'machines':len(cert['machines']),
    'span_rank':len(all_basis.vectors()),
    'machine_affine_ranks':machine_ranks,
    'target_residue_hex':hex(residue),
    'meaning':'This tests whether one shared GF(2) coefficient per selected group can force a contradiction using the independently checked machine BDD overapproximations. It does not test all possible parities or SAT proofs.'
}
print(json.dumps(out,indent=2,ensure_ascii=False))
