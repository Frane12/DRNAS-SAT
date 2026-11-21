#!/usr/bin/env python3
"""ATLAS6 — semantic AND-camouflage recovery from ONLY source DIMACS clauses.

Every pair of hidden AND-input variables has the same *absolute* clause
incidence, though their signed occurrence sets may differ (sign shuffling).
Each original XOR row's clauses are a complete forbidden-assignment table of
the resulting signed-AND / singleton-token parity function. Supports 3..6
original variables per source clause; requires exact truth table equality.

No catalog labels, filenames, predicted result, source templates or variable
role hints are used. Independent checker MUST validate all source premises,
the quotient CNF and (if SAT) every original clause before acceptance.
"""
from pathlib import Path
from collections import defaultdict,Counter
from itertools import product
import argparse,hashlib,json,os,time,sys

class Unsupported(ValueError):pass
def need(condition,why):
    if not condition:raise Unsupported(why)
def parse(raw):
    nv=nc=None;clauses=[];pending=[]
    for line in raw.decode("ascii").splitlines():
        words=line.split()
        if not words or words[0]=="c":continue
        if words[0]=="p":
            need(nv is None and len(words)==4 and words[1]=="cnf","invalid_header")
            nv,nc=map(int,words[2:])
            need(1<=nv<=50000 and 0<=nc<=100000,"source_budget")
            continue
        need(nv is not None,"missing_header")
        for word in words:
            x=int(word)
            need(abs(x)<=nv,"literal_out_of_range")
            if x:pending.append(x)
            else:
                need(len(pending)<=8 and len(set(map(abs,pending)))==len(pending),
                     "source_width_or_duplicate_variable")
                clauses.append(tuple(pending));pending=[]
    need(nv is not None and not pending and len(clauses)==nc,"source_count")
    return nv,clauses

def encode(n,rows):
    return (f"p cnf {n} {len(rows)}\n"+
            "".join(" ".join(map(str,c))+" 0\n" for c in rows)).encode("ascii")

def source_tokens(n,clauses):
    occurrences=defaultdict(list)
    for ci,c in enumerate(clauses):
        for v in c:occurrences[abs(v)].append(ci)
    patterns=defaultdict(list)
    for v,indices in occurrences.items():patterns[tuple(indices)].append(v)
    need(all(1<=len(v)<=2 for v in patterns.values()),
         "ambiguous_absolute_incidence_class_gt_2")
    tokens=sorted((tuple(sorted(v)) for v in patterns.values()))
    need(sum(len(tok) for tok in tokens)==len(occurrences),"token_partition")
    return tokens

def extract(raw):
    started=time.perf_counter()
    n,clauses=parse(raw)
    tokens=source_tokens(n,clauses)
    by_v={v:token for token in tokens for v in token}
    original_groups=defaultdict(set)
    for c in clauses:
        support=tuple(sorted(abs(l) for l in c))
        mask=sum(1<<j for j,v in enumerate(support) if -v in c)
        need(mask not in original_groups[support],"duplicate_full_assignment_clause")
        original_groups[support].add(mask)
    signs={}
    rows=[]
    for support,forbidden in sorted(original_groups.items()):
        need(3<=len(support)<=6,"unsupported_source_support_width")
        position={v:i for i,v in enumerate(support)}
        row_tokens=sorted({by_v[v] for v in support})
        need(len(row_tokens)==3 and all(set(t).issubset(support) for t in row_tokens),
             "cannot_partition_support_into_3_tokens")
        pairs=[tok for tok in row_tokens if len(tok)==2]
        possible=[]
        for orientation in product((0,1),repeat=2*len(pairs)):
            oriented={tok:[orientation[2*j],orientation[2*j+1]]
                      for j,tok in enumerate(pairs)}
            if any(tok in signs and signs[tok]!=sign for tok,sign in oriented.items()):
                continue
            outputs=[]
            for bits in range(1<<len(support)):
                output=0
                for tok in row_tokens:
                    if len(tok)==1:
                        output^=(bits>>position[tok[0]])&1
                    else:
                        a,b=tok
                        va=(bits>>position[a])&1
                        vb=(bits>>position[b])&1
                        output^=int([va,vb]==oriented[tok])
                outputs.append(output)
            for rhs in (0,1):
                bad={bits for bits,value in enumerate(outputs) if value!=rhs}
                if bad==forbidden:possible.append((oriented,rhs))
        need(len(possible)==1,"ambiguous_or_unsupported_local_truth_table")
        oriented,rhs=possible[0]
        signs.update(oriented)
        rows.append({"support":list(support),
                     "tokens":[tokens.index(tok)+1 for tok in row_tokens],
                     "rhs":rhs})
    qvars=len(tokens)
    quotient_clauses=[]
    for row in rows:
        v=row["tokens"]
        for bits in product((0,1),repeat=len(v)):
            if sum(bits)%2==row["rhs"]:continue
            quotient_clauses.append(tuple(-x if bit else x for x,bit in zip(v,bits)))
    quotient=encode(qvars,quotient_clauses)
    token_claims=[{"id":i,"members":list(tok),
                   "true_if":signs[tok] if len(tok)==2 else [1]}
                  for i,tok in enumerate(tokens,1)]
    cert={"format":"DRNAS-ATLAS6-SEMANTIC-AND-XOR-v1",
          "source_sha256":hashlib.sha256(raw).hexdigest(),
          "quotient_sha256":hashlib.sha256(quotient).hexdigest(),
          "source_vars":n,"source_clauses":len(clauses),
          "quotient_variables":qvars,"quotient_clauses":len(quotient_clauses),
          "tokens":token_claims,"rows":rows,
          "source_supports":len(original_groups),
          "camouflaged_AND_pairs":sum(len(tok)==2 for tok in tokens),
          "no_source_family_used":True,
          "proof_kind":"FULL_TRUTH_TABLE_EQUIVALENCE_NOT_STANDARD_UNSAT",
          "source_processing_s":round(time.perf_counter()-started,6)}
    return quotient,cert

def gauss_model(rows,n):
    basis={}
    for row in rows:
        rhs=row["rhs"]
        mask=sum(1<<(vid-1) for vid in row["tokens"])
        while mask:
            pivot=mask.bit_length()-1
            if pivot not in basis:
                basis[pivot]=(mask,rhs)
                break
            other,b=basis[pivot]
            mask^=other;rhs^=b
        else:
            if rhs:return None
    assignment=0
    for pivot in sorted(basis):
        mask,rhs=basis[pivot]
        value=rhs ^ (((mask^(1<<pivot))&assignment).bit_count()%2)
        if value:assignment|=(1<<pivot)
    result=[None]+[bool(assignment & (1<<(j-1))) for j in range(1,n+1)]
    need(all(sum(result[v] for v in row["tokens"])%2==row["rhs"] for row in rows),
         "gaussian_solution_not_satisfying_rows")
    return result

def lift_model(cert,virtual):
    full=[None]+[False]*cert["source_vars"]
    for tok in cert["tokens"]:
        output=bool(virtual[tok["id"]])
        for v,required in zip(tok["members"],tok["true_if"]):
            full[v]=(output==bool(required))
    return full

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cnf",type=Path,required=True)
    p.add_argument("--quotient",type=Path,required=True)
    p.add_argument("--certificate",type=Path,required=True)
    p.add_argument("--model",type=Path,required=True)
    a=p.parse_args()
    try:
        raw=a.cnf.read_bytes()
        q,cert=extract(raw)
        virtual=gauss_model(cert["rows"],cert["quotient_variables"])
        if virtual is None:
            cert["status"]="UNKNOWN_GF2_CONTRADICTION_NEEDS_STANDARD_UNSAT_PROOF"
            a.model.unlink(missing_ok=True)
        else:
            cert["status"]="MODEL_EMITTED_PENDING_INDEPENDENT_SOURCE_CHECK"
            a.model.write_text(json.dumps({
               "source_sha256":hashlib.sha256(raw).hexdigest(),
               "assignment":lift_model(cert,virtual),
               "quotient_assignment":virtual},sort_keys=True)+"\n")
        a.quotient.parent.mkdir(parents=True,exist_ok=True)
        a.quotient.write_bytes(q)
        a.certificate.write_text(json.dumps(cert,indent=2,sort_keys=True)+"\n")
        print("ATLAS6_SEMANTIC "+json.dumps({
           "status":cert["status"],"tokens":len(cert["tokens"]),
           "camouflaged_pairs":cert["camouflaged_AND_pairs"],
           "original_supports":cert["source_supports"],
           "equations":len(cert["rows"]),"source_clauses":cert["source_clauses"],
           "quotient_clauses":cert["quotient_clauses"],
           "source_processing_s":cert["source_processing_s"]},sort_keys=True),flush=True)
        return 0 if virtual is not None else 2
    except (Unsupported,ValueError,TypeError,IndexError,UnicodeError,OverflowError,MemoryError) as exc:
        a.quotient.unlink(missing_ok=True)
        a.certificate.unlink(missing_ok=True)
        a.model.unlink(missing_ok=True)
        print("ATLAS6_UNSUPPORTED "+str(exc),flush=True)
        return 2
if __name__=="__main__":sys.exit(main())
