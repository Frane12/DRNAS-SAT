#!/usr/bin/env python3
"""DRNAS MATH-HYBRID2: k-dimensional GF(2)-conditioned BDD capacity audit.

This only accepts BDDs already checked against source-CNF clauses by
research/pcmax_hybrid1/check.py. It is a structural certificate, NOT a
VeriPB or polynomial-time general SAT algorithm.

Run: python3 research/pcmax_hybrid2/analyze.py
"""
from pathlib import Path
import json, sys, tempfile
from itertools import combinations
from functools import reduce
from operator import xor

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"research"/"pcmax_hybrid1"))
from emit import emit
from check import check

DEMO_A=12142  # 10 marked jobs; this parity alone cannot separate
DEMO_B=28520  #  9 marked jobs; this parity alone cannot separate
N=15

def support_bits(n,mask):
    return tuple(i for i in range(n) if (mask>>i)&1)

def xor_signature_for_group(group_index,supports):
    return sum((1<<k) for k,s in enumerate(supports) if group_index in s)

def local_bdd_caps(machine,weights,group_index,supports):
    """Exact max-plus dynamic programming on the CNF-checked ordered BDD."""
    k=len(supports)
    if k>12: raise ValueError("k too large for this bounded audit (max 12)")
    order=machine['variable_order']
    rank={v:i for i,v in enumerate(order)}
    trans={q:(x,lo,hi) for q,x,lo,hi in machine['transitions']}
    t,f=machine['true_terminal'],machine['false_terminal']
    ranks={q:rank[x] for q,(x,_,_) in trans.items()}
    ranks[t]=ranks[f]=len(order)
    sigma={v:xor_signature_for_group(group_index[v],supports)
           if v in group_index else 0 for v in order}

    def append_optional(dist,v):
        out=dict(dist)
        for sig,score in dist.items():
            tag=sig^sigma[v]
            val=score+weights.get(v,0)
            if val>out.get(tag,-1):out[tag]=val
        return out

    best={t:{0:0},f:{}}
    for q in sorted(trans,key=lambda x:ranks[x],reverse=True):
        x,lo,hi=trans[q]
        acc={}
        for child,take in ((lo,0),(hi,1)):
            partial=best[child]
            for i in range(rank[x]+1,ranks[child]):
                partial=append_optional(partial,order[i])
            for sig,score in partial.items():
                if take:sig^=sigma[x];score+=weights.get(x,0)
                if score>acc.get(sig,-1):acc[sig]=score
        best[q]=acc
    root=machine['root']
    local=best[root]
    for i in range(ranks[root]):
        local=append_optional(local,order[i])
    return local

def combine(local_caps,supports):
    k=len(supports)
    target=sum((len(s)%2)<<i for i,s in enumerate(supports))
    dp={0:0}
    for cap in local_caps:
        nxt={}
        for a,weight in dp.items():
            for b,value in cap.items():
                sig=a^b
                if weight+value>nxt.get(sig,-1):
                    nxt[sig]=weight+value
        dp=nxt
    return dp.get(target),target

def check_source_and_bound(data,cert,supports):
    # Existing source-level checker independently verifies all source clauses
    # (selected groups, exact-one, BDD edges, units, hash and structural capacity).
    verified=check(data,cert)
    assert verified['status']=='STRUCTURAL_HYBRID_UNSAT_CHECKED'
    groups=cert['selected_groups']
    weights={v:cert['group_weights'][i] for i,g in enumerate(groups) for v in g}
    index={v:i for i,g in enumerate(groups) for v in g}
    assert all(set(s)<=set(range(len(groups))) for s in supports)
    caps=[local_bdd_caps(m,weights,index,supports) for m in cert['machines']]
    bound,target=combine(caps,supports)
    return {'bound':bound,'target':target,'local_caps_first':caps[0],
            'demand':sum(cert['group_weights']),
            'rank_dimension_k':len(supports)}

def affine_rank(vectors):
    piv={}
    for x in vectors:
        while x:
            p=x.bit_length()-1
            if p not in piv:
                piv[p]=x
                break
            x^=piv[p]
    return list(piv.values())

def affine_hull(s):
    """Return base and linear span of differences from that base."""
    base=min(s)
    piv=affine_rank(x^base for x in s)
    lin={0}
    for v in piv: lin|={x^v for x in list(lin)}
    return {x^base for x in lin},len(piv)

def xor_sumset(s,m):
    out={0}
    for _ in range(m):out={x^y for x in out for y in s}
    return out

def test_affine_saturation():
    # Exhaustive tiny-set test of the theorem: if m >= rank(S-S),
    # then mS is precisely m*s0 + span(S-s0).
    for k in (1,2,3):
        space=range(1<<k)
        for mask in range(1,1<<(1<<k)):
            s={x for x in space if (mask>>x)&1}
            hull,r=affine_hull(s)
            anchor=min(s)
            span={x^anchor for x in hull}
            for m in range(max(1,r),r+3):
                target={x^((m&1)*anchor) for x in span}
                assert xor_sumset(s,m)==target,(k,s,m)
    s={0,1,2,4}
    _,r=affine_hull(s)
    assert r==3 and 7 not in xor_sumset(s,2)
    for mask in range(1,8):
        goal=(7&mask).bit_count()%2
        assert any((x&mask).bit_count()%2==goal for x in xor_sumset(s,2))
    return {'theorem_exhaustive_k_le':3,'nonaffine_example':{
        'k':3,'machines':2,'local_signatures':sorted(s),
        'target_missing':7,'single_linear_projection_separates':False}}

def main():
    with tempfile.TemporaryDirectory() as d:
        folder=Path(d)
        emit(folder)
        data=(folder/"source_atmost.cnf").read_bytes()
        cert=json.loads((folder/"certificate.json").read_text())
        A=set(support_bits(N,DEMO_A))
        B=set(support_bits(N,DEMO_B))
        X=set(support_bits(N,DEMO_A^DEMO_B))
        one_a=check_source_and_bound(data,cert,[A])
        one_b=check_source_and_bound(data,cert,[B])
        one_xor=check_source_and_bound(data,cert,[X])
        two=check_source_and_bound(data,cert,[A,B])
        assert [one_a['bound'],one_b['bound'],one_xor['bound'],two['bound']]==[198,198,197,197]
        assert two['local_caps_first']=={0:33,1:32,2:32,3:33}
        assert two['target']==2
        # Independently enumerate all 2^15 assignments on one machine.
        jobs=cert['jobs']; pattern_caps={}
        for mask in range(1<<len(jobs)):
            load=sum(x for i,x in enumerate(jobs) if mask>>i&1)
            if load>33:continue
            sig=((mask&DEMO_A).bit_count()%2)+2*((mask&DEMO_B).bit_count()%2)
            pattern_caps[sig]=max(pattern_caps.get(sig,-1),load)
        assert pattern_caps==two['local_caps_first']
        theorem=test_affine_saturation()
        print(json.dumps({'status':'ALL_TESTS_PASS',
          'source_sha256':cert['source_sha256'],
          'cnf_source_type':'newly generated at-most BDD CNF, not archived benchmark',
          'demand':198,'single_a':one_a,'single_b':one_b,
          'single_xor':one_xor,'two_parities':two,
          'two_parities_not_independent':True,
          'xor_support_zero_based':sorted(X),
          'exhaustive_local_enumeration':'PASS',
          'theorem_test':theorem,
          'external_veripb_status':'NOT_EMITTED'},indent=2,sort_keys=True))

if __name__=='__main__':main()
