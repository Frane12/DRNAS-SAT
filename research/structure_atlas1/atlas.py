#!/usr/bin/env python3
"""DRNAS STRUCTURE ATLAS 1: source-only, permutation/sign-invariant CNF fingerprint.

This is NON-PROOF recognition and NOT an SAT solver. It studies raw original
DIMACS inputs and preserves SHA-256 of all exact source bytes. Feature hash
is a coarse structural invariant, NOT a canonical formula or SAT equivalence
certificate. For known invertible transformations, a separate exact inverse-
mapping check proves equivalence of the transformed source to its original.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from hashlib import sha256
import json,random
from pathlib import Path

def parse(raw:bytes):
    nv=nc=None;cs=[];partial=[]
    lines=iter(raw.decode("ascii").splitlines())
    for line in lines:
        words=line.split()
        if not words or words[0]=="c":continue
        if words==["%"]:
            trailer=[fields for tail in lines if (fields:=tail.split()) and fields[0]!="c"]
            if trailer not in ([],[["0"]]):raise ValueError("invalid SATLIB trailer")
            break
        if words[0]=="p":
            if nv is not None or len(words)!=4 or words[1]!="cnf":raise ValueError("bad header")
            nv,nc=int(words[2]),int(words[3])
            if not(1<=nv<=1000000 and 0<=nc<=3000000):raise ValueError("header budget")
            continue
        if nv is None:raise ValueError("header missing")
        for word in words:
            x=int(word)
            if abs(x)>nv:raise ValueError("literal exceeds header")
            if x:partial.append(x)
            else:
                if len(partial)>10000:raise ValueError("clause width budget")
                cs.append(tuple(partial));partial=[]
    if nv is None or partial or len(cs)!=nc:raise ValueError("clause-count mismatch")
    return nv,cs

def encoded(nv,clauses):
    return (f"p cnf {nv} {len(clauses)}\n" +
            "".join(" ".join(map(str,c))+" 0\n" for c in clauses)).encode("ascii")

def exact_multiset(clauses):
    return Counter(tuple(sorted(c)) for c in clauses)

def signature(nv,clauses):
    """Coarse invariant under any bijective variable rename, sign flips,
    clause reorder and literal order; multiplicities kept. No labels used."""
    hist=Counter();per=defaultdict(lambda:[Counter(),Counter()])
    units=0;empty=0;binary=0
    for c in clauses:
        n=len(c);hist[n]+=1
        if n==0:empty+=1
        if n==1:units+=1
        if n==2:binary+=1
        for lit in c:
            per[abs(lit)][0 if lit>0 else 1][n]+=1
    varhist=Counter()
    # Include zero-occurrence vars, stable under arbitrary renaming.
    for v in range(1,nv+1):
        pos,neg=per[v]
        sides=sorted((tuple(sorted(pos.items())),tuple(sorted(neg.items()))))
        varhist[tuple(sides)]+=1
    payload={
        "num_vars":nv,"num_clauses":len(clauses),
        "clause_widths":sorted(hist.items()),
        "sign_invariant_literal_neighborhoods":[
            [ [[list(item) for item in side] for side in key],amount]
            for key,amount in sorted(varhist.items())
        ],
    }
    digest=sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return {"fingerprint_version":"ATLAS1-COARSE-LITERAL-INCIDENCE-v1",
            "coarse_invariant_sha256":digest,
            "variable_count":nv,"clause_count":len(clauses),
            "clause_width_histogram":dict(sorted(hist.items())),
            "unit_clauses":units,"binary_clauses":binary,
            "empty_clauses":empty,
            "distinct_variable_patterns":len(varhist),
            "NOTE":"Equal fingerprints do not prove formula isomorphism or equivalent SAT status"}

def motifs(nv,clauses):
    """Recognition candidates only. Source-support counted; no UNSAT verdict.
    Sign orientation matters. Conservative budgets are explicit."""
    source={frozenset(c) for c in clauses}
    groups=[]
    for c in clauses:
        if 2<=len(c)<=32 and all(x>0 for x in c) and len(set(c))==len(c):
            groups.append(c)
    eo=[]
    if len(groups)<=25000:
        for g in groups:
            if all(frozenset((-a,-b)) in source for i,a in enumerate(g) for b in g[i+1:]):
                eo.append(g)
    # Recover complete XOR3/4 truth-table encodings by literal SETS, not names.
    xor_candidates=defaultdict(set)
    width3_4=0
    for c in clauses:
        if len(c) not in (3,4) or len({abs(l) for l in c})!=len(c):continue
        width3_4+=1
        if width3_4>160000:break
        vs=tuple(sorted(abs(l) for l in c))
        mask=sum((1<<i) for i,v in enumerate(vs) if -v in c)
        xor_candidates[vs].add(mask)
    x3=x4=0
    for vs,masks in xor_candidates.items():
        if len(masks)<(1<<(len(vs)-1)):continue
        for parity in (0,1):
            valid={a for a in range(1<<len(vs)) if a.bit_count()%2==parity}
            if valid<=masks:
                if len(vs)==3:x3+=1
                else:x4+=1
                break
    return {"source_supported_exact_one_groups":len(eo),
            "positive_ALO_candidates":len(groups),
            "source_XOR3_table_candidates":x3,
            "source_XOR4_table_candidates":x4,
            "xor_table_scan_limited":width3_4>160000,
            "alo_mutex_scan_limited":len(groups)>25000,
            "note":"Motifs are syntactic source-backed candidates, not SAT/UNSAT proofs"}

def transform(nv,clauses,seed,rename=True,flip=False,shuffle=True):
    """Return generated source AND exact inverse-literal map (not given scanner)."""
    rng=random.Random(seed)
    new=list(range(1,nv+1))
    if rename:rng.shuffle(new)
    rename_map=[0]+new
    signs=[1]*(nv+1)
    if flip:
        signs=[1]+[(-1 if rng.randrange(2) else 1) for _ in range(nv)]
        # ensure nontrivial sign change, even for very small source
        if all(s>0 for s in signs[1:]):signs[1]=-1
    inverse={}
    for old in range(1,nv+1):
        inverse[rename_map[old]]=old*signs[old]
    newclauses=[]
    for c in clauses:
        out=[(1 if lit>0 else -1)*signs[abs(lit)]*rename_map[abs(lit)] for lit in c]
        if shuffle:rng.shuffle(out)
        newclauses.append(tuple(out))
    if shuffle:rng.shuffle(newclauses)
    # Inverse literal map for independent source equivalence audit
    def inv(lit):
        v=inverse[abs(lit)]
        return v if lit>0 else -v
    recovered=[tuple(inv(l) for l in c) for c in newclauses]
    exact=(exact_multiset(recovered)==exact_multiset(clauses))
    return encoded(nv,newclauses),exact,{
        "rename":rename,"sign_flip":flip,"shuffle_clauses_and_literals":shuffle,
        "seed":seed,"flipped_vars":sum(s<0 for s in signs[1:])
    }

def scan(raw):
    nv,clauses=parse(raw)
    return {"raw_source_sha256":sha256(raw).hexdigest(),**signature(nv,clauses),
            "motifs":motifs(nv,clauses)}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("input",type=Path)
    ap.add_argument("--output",type=Path)
    a=ap.parse_args()
    result=scan(a.input.read_bytes())
    s=json.dumps(result,indent=2,sort_keys=True)
    if a.output:a.output.write_text(s+"\n")
    print(s)
if __name__=="__main__":main()
