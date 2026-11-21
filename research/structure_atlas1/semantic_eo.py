#!/usr/bin/env python3
"""ATLAS1 semantic pilot: recover EXACTLY-ONE across distinct CNF encodings.

Recognizes an ALO source clause plus independently UCP-refuted pairs.
Works with arbitrary selector polarities, variable renaming and order.
The pairwise RUP criterion is sound; it is NOT a complete classifier
and makes no general SAT claim or standard UNSAT claim.
"""
from pathlib import Path
import argparse,json,random
from atlas import parse,encoded,transform

def unit_conflict(clauses,assumptions):
    """Simple source-unit-propagation refutation (RUP) for a pair."""
    values={}
    for lit in assumptions:
        v=abs(lit);b=(lit>0)
        if v in values and values[v]!=b:return True
        values[v]=b
    while True:
        changed=False
        for clause in clauses:
            satisfied=False;missing=0;unit=0
            for lit in clause:
                v=abs(lit)
                if v in values:
                    if values[v]==(lit>0):
                        satisfied=True;break
                else:missing+=1;unit=lit
            if satisfied:continue
            if missing==0:return True
            if missing==1:
                v=abs(unit);b=(unit>0)
                if v in values:
                    if values[v]!=b:return True
                else:
                    values[v]=b;changed=True
        if not changed:return False

def recover(raw,max_candidates=1000,max_width=12,max_pairs=4000):
    nv,clauses=parse(raw)
    candidates=[c for c in clauses if 3<=len(c)<=max_width and
                len({abs(x) for x in c})==len(c)]
    out={"status":"UNKNOWN","tested_alo_candidates":0,"tested_pairs":0,
         "source_supported_exactly_one":[],"method":"ALO_SOURCE + PAIRWISE_RUP_VIA_UCP",
         "source_syntactic_label_free":True}
    if len(candidates)>max_candidates:
        out["reason"]="candidate_budget";return out
    for clause in candidates:
        if out["tested_pairs"]+(len(clause)*(len(clause)-1)//2)>max_pairs:
            out["reason"]="pair_budget";return out
        out["tested_alo_candidates"]+=1
        valid=True
        for i,a in enumerate(clause):
            for b in clause[i+1:]:
                out["tested_pairs"]+=1
                if not unit_conflict(clauses,(a,b)):
                    valid=False;break
            if not valid:break
        if valid:
            out["source_supported_exactly_one"].append({
                "literals":list(clause),"selector_count":len(clause),
                "proof_rule":"every pair entails a RUP blocking clause"})
    if out["source_supported_exactly_one"]:
        out["status"]="EXACTLY_ONE_SOURCE_PROVEN_PAIR_RUP"
    else:out["reason"]="no_supported_exactly_one_under_budget"
    return out

def construct(n,kind,broken=False):
    assert kind in ("pairwise","sequential") and 4<=n<=9
    xs=list(range(1,n+1))
    clauses=[tuple(xs)]
    if kind=="pairwise":
        for i,a in enumerate(xs):
            for b in xs[i+1:]:
                if broken and a==1 and b==2:continue
                clauses.append((-a,-b))
        nv=n
    else:
        # Sinz sequential AMO with n-1 fresh prefix variables.
        s=[n+i for i in range(1,n)]
        clauses.append((-xs[0],s[0]))
        for i in range(1,n-1):
            clauses.extend(((-xs[i],s[i]),(-s[i-1],s[i]),(-xs[i],-s[i-1])))
        if not broken:clauses.append((-xs[-1],-s[-1]))
        nv=2*n-1
    return nv,clauses

def projection_exactly_one(n,nv,clauses):
    """Independent exact brute-force existential-aux model check (small n)."""
    for mask in range(1<<n):
        expected=(mask.bit_count()==1)
        found=False
        for rest in range(1<<(nv-n)):
            m=mask|(rest<<n)
            if all(any(bool(m&(1<<(abs(l)-1)))==(l>0) for l in c) for c in clauses):
                found=True;break
        if found!=expected:return False
    return True

def main():
    p=argparse.ArgumentParser()
    p.add_argument("input",type=Path)
    a=p.parse_args()
    print(json.dumps(recover(a.input.read_bytes()),sort_keys=True))
if __name__=="__main__":main()
