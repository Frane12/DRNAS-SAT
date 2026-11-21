#!/usr/bin/env python3
"""SAT from a source-verified AND quotient and recovered GF(2) rows.

NOT a generic SAT solver. Gaussian GF(2) is valid only for exact original-
source XOR equations. Reconstruct SAT model for quotient then reverse every
AND-substitution pair, *independently verify all exact original CNF clauses*
before reporting SAT. If XOR elimination is consistent but quotient model
fails any residual source constraint, result is safely UNKNOWN.
"""
import argparse,collections,hashlib,itertools,json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"research/structure_atlas1"))
sys.path.insert(0,str(ROOT/"research/structure_atlas3"))
from atlas import parse as parse_source
from source_facts import derive as source_facts
from check_facts import check as fact_check
from check_roundtrip import check as quotient_check,check_sat,Invalid

def parity_solution(rows,nv):
    basis={}
    for equation in rows:
        vs=equation["vars"];rhs=equation["rhs"]
        mask=sum(1<<(v-1) for v in vs)
        while mask:
            pivot=mask.bit_length()-1
            if pivot not in basis:
                basis[pivot]=(mask,rhs);break
            oldmask,oldrhs=basis[pivot]
            mask^=oldmask;rhs^=oldrhs
        else:
            if rhs:return None
    m=0
    for pivot in sorted(basis):
        mask,rhs=basis[pivot]
        knownlower=mask^(1<<pivot)
        bit=rhs^(knownlower&m).bit_count()%2
        if bit:m|=(1<<pivot)
    A=[None]+[bool(m&(1<<(v-1))) for v in range(1,nv+1)]
    for eq in rows:
        if sum(A[v] for v in eq["vars"])%2!=eq["rhs"]:
            raise AssertionError("GF2_POSTSOLVE_INCORRECT")
    return A

def satisfies(clauses,assignment):
    return all(any(assignment[abs(l)]==(l>0) for l in clause) for clause in clauses)

def solve(raw,quotient_raw,certificate):
    started=time.perf_counter()
    source_equivalence=quotient_check(raw,quotient_raw,certificate)
    nv,quotient=parse_source(quotient_raw)
    facts=source_facts(quotient_raw)
    fact_validation=fact_check(quotient_raw,facts)
    xorrows=facts["complete_xor_rows"]
    record={
      "status":"UNKNOWN",
      "source_sha256":hashlib.sha256(raw).hexdigest(),
      "quotient_sha256":hashlib.sha256(quotient_raw).hexdigest(),
      "certified_masking_steps":source_equivalence["checked_exact_AND_reexpansion_steps"],
      "quotient_clauses":len(quotient),
      "source_xor_rows":len(xorrows),
      "independent_source_facts":fact_validation["status"],
      "source_equivalence":source_equivalence["status"],
      "math_method":"Gaussian GF(2) exact source XOR rows",
      "original_model_independently_checked":False}
    if not xorrows:
        record["reason"]="NO_COMPLETE_XOR_ROWS_IN_QUOTIENT";return record,None
    sol=parity_solution(xorrows,nv)
    if sol is None:
        record["reason"]="XOR_ROWS_CONTRADICT; UNSAT needs separate external proof"
        return record,None
    if not satisfies(quotient,sol):
        record["reason"]="GF2_MODEL_DOES_NOT_SATISFY_NON_XOR_QUOTIENT_CLAUSES"
        return record,None
    # For original quotient equality q=(a AND b), choose both a and b equal
    # to the value of q. Reverse steps in order for nested substitutions.
    for step in reversed(certificate["pair_steps"]):
        a,b=step["a"],step["b"]
        aval=(sol[abs(a)] if a>0 else not sol[abs(a)])
        sol[abs(b)]=(aval if b>0 else not aval)
    checked=check_sat(raw,{"assignment":sol})
    record.update({
       "status":"SAT_MODEL_ORIGINAL_VERIFIED",
       "source_variables":nv,
       "original_clauses_checked":checked["clauses_checked"],
       "original_model_independently_checked":True,
       "math_used_free_bits_as_zero":True,
       "elapsed_s":round(time.perf_counter()-started,6)
    })
    return record,{"source_sha256":hashlib.sha256(raw).hexdigest(),
                   "assignment":sol}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--quotient",type=Path,required=True)
    p.add_argument("--certificate",type=Path,required=True)
    p.add_argument("--model",type=Path,required=True)
    p.add_argument("--meta",type=Path,required=True)
    a=p.parse_args()
    try:
        raw=a.source.read_bytes()
        meta=json.loads(a.certificate.read_text())
        result,model=solve(raw,a.quotient.read_bytes(),meta)
        a.meta.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
        if model:
            a.model.write_text(json.dumps(model,sort_keys=True)+"\n")
        else:
            a.model.unlink(missing_ok=True)
        print("ATLAS6_GF2 "+json.dumps(result,sort_keys=True),flush=True)
        return 0 if model else 2
    except (Invalid,ValueError,TypeError,UnicodeError,MemoryError,OSError,OverflowError) as error:
        a.model.unlink(missing_ok=True)
        a.meta.write_text(json.dumps({"status":"UNKNOWN","reason":str(error)[:250]},sort_keys=True)+"\n")
        print("ATLAS6_GF2_UNKNOWN "+str(error),flush=True)
        return 2
if __name__=="__main__":raise SystemExit(main())
