#!/usr/bin/env python3
"""Independent checker: SOURCE AND-camouflage/XOR equivalence + full SAT model.

No import of the detector or Gaussian solver. Re-reads ORIGINAL unchanged
DIMACS. For each claimed source hyperedge, exhaustively recomputes its
full 2^w forbidden-assignment truth table from virtual signed AND variables
and XOR. Requires exact equality to the ORIGINAL clause set, plus exact
quotient XOR CNF and full SAT witness check against every original clause.
Only original-source model satisfaction earns SAT. Never manufactures UNSAT.
"""
import argparse,hashlib,itertools,json
from collections import defaultdict,Counter
from pathlib import Path

class Invalid(ValueError):pass
def need(v,why):
    if not v:raise Invalid(why)
def parse(raw):
    n=m=None;out=[];pending=[]
    for line in raw.decode("ascii").splitlines():
        w=line.split()
        if not w or w[0]=="c":continue
        if w[0]=="p":
            need(n is None and len(w)==4 and w[1]=="cnf","source_header")
            n,m=map(int,w[2:])
            need(1<=n<=50000 and 0<=m<=100000,"source_limits")
            continue
        need(n is not None,"missing_header")
        for word in w:
            v=int(word)
            need(abs(v)<=n,"literal_range")
            if v:pending.append(v)
            else:
                need(len(pending)<=8 and
                     len(set(map(abs,pending)))==len(pending),"clause_width_or_duplicates")
                out.append(tuple(pending));pending=[]
    need(n is not None and not pending and len(out)==m,"dimacs_count")
    return n,out

def clause_bag(clauses):
    return Counter(tuple(sorted(c)) for c in clauses)

def verify(original_raw,quot_raw,certificate,model=None):
    need(type(certificate) is dict and
         certificate.get("format")=="DRNAS-ATLAS6-SEMANTIC-AND-XOR-v1","format")
    need(certificate.get("source_sha256")==hashlib.sha256(original_raw).hexdigest(),
         "original_SHA")
    need(certificate.get("quotient_sha256")==hashlib.sha256(quot_raw).hexdigest(),
         "quotient_SHA")
    n,clauses=parse(original_raw)
    nq,qclauses=parse(quot_raw)
    need(certificate.get("source_vars")==n and
         certificate.get("source_clauses")==len(clauses),"source_counts")
    need(certificate.get("quotient_variables")==nq and
         certificate.get("quotient_clauses")==len(qclauses),"quotient_counts")
    tokens=certificate.get("tokens")
    rows=certificate.get("rows")
    need(type(tokens) is list and type(rows) is list and
         len(tokens)==nq and len(rows)<=len(clauses),"type_or_length")
    variable_owner={};tok_by_id={}
    for j,tok in enumerate(tokens,1):
        need(type(tok) is dict and tok.get("id")==j,"token_id")
        members=tok.get("members");true_if=tok.get("true_if")
        need(type(members) is list and 1<=len(members)<=2 and
             all(type(v) is int and 1<=v<=n for v in members),"token_members")
        need(type(true_if) is list and len(true_if)==len(members) and
             all(type(x) is int and x in (0,1) for x in true_if),"token_orientations")
        for v in members:
            need(v not in variable_owner,"source_var_token_overlap")
            variable_owner[v]=j
        tok_by_id[j]=(members,true_if)
    grouped=defaultdict(Counter)
    for clause in clauses:
        supp=tuple(sorted(abs(v) for v in clause))
        mask=sum(1<<i for i,v in enumerate(supp) if -v in clause)
        grouped[supp][mask]+=1
    need(set(variable_owner)=={abs(v) for c in clauses for v in c},
         "source_variable_not_partitioned")
    need(len(rows)==len(grouped)==certificate.get("source_supports"),
         "row_count_or_missing_supports")
    seen=set()
    quotient_expected=[]
    for entry in rows:
        need(type(entry) is dict and
             set(entry)=={"support","tokens","rhs"},"row_type")
        supp=entry["support"];ids=entry["tokens"];rhs=entry["rhs"]
        need(type(supp) is list and 3<=len(supp)<=6 and
             all(type(v) is int and 1<=v<=n for v in supp)
             and supp==sorted(set(supp)),"row_support")
        key=tuple(supp)
        need(key in grouped and key not in seen,"repeated_or_unknown_source_support")
        seen.add(key)
        need(type(ids) is list and len(ids)==3 and
             ids==sorted(set(ids)) and all(type(i) is int and 1<=i<=nq for i in ids),
             "row_token_ids")
        need(type(rhs) is int and rhs in (0,1),"row_rhs")
        union={v for i in ids for v in tok_by_id[i][0]}
        need(union==set(supp),"token_source_support_mismatch")
        actual=grouped[key]
        need(all(n==1 for n in actual.values()),"source_duplicate_forbidden_assignment")
        expected=set()
        bit_index={v:i for i,v in enumerate(supp)}
        for value in range(1<<len(supp)):
            parity=0
            for i in ids:
                members,required=tok_by_id[i]
                if len(members)==1:
                    parity^=(value>>bit_index[members[0]])&1
                else:
                    flags=[(value>>bit_index[v])&1 for v in members]
                    parity^=int(flags==required)
            if parity!=rhs:expected.add(value)
        need(set(actual)==expected,"SOURCE_HYPEREDGE_TRUTH_TABLE_NOT_EQUIVALENT")
        for values in itertools.product((0,1),repeat=len(ids)):
            if sum(values)%2==rhs:continue
            quotient_expected.append(tuple((-v if bit else v)
                         for v,bit in zip(ids,values)))
    need(clause_bag(qclauses)==clause_bag(quotient_expected),
         "QUOTIENT_NOT_EXACT_GF2_CNF")
    result={
      "status":"FULL_SOURCE_AND_GF2_EQUIVALENCE_VERIFIED",
      "source_sha256":hashlib.sha256(original_raw).hexdigest(),
      "quotient_sha256":hashlib.sha256(quot_raw).hexdigest(),
      "source_variables":n,"original_clauses":len(clauses),
      "masked_pairs_verified":sum(len(t["members"])==2 for t in tokens),
      "virtual_variables":nq,"source_truth_tables_checked":len(grouped),
      "source_forbidden_assignments_checked":len(clauses),
      "quotient_clauses_checked":len(qclauses),
      "SAT_status":"NO_MODEL_CHECK_REQUESTED"}
    if model is not None:
        need(type(model) is dict and
             model.get("source_sha256")==hashlib.sha256(original_raw).hexdigest(),
             "model_source_SHA")
        A=model.get("assignment"); Q=model.get("quotient_assignment")
        need(type(A) is list and len(A)==n+1 and A[0] is None and
             all(type(v) is bool for v in A[1:]),"model_source_assignment")
        need(type(Q) is list and len(Q)==nq+1 and Q[0] is None and
             all(type(v) is bool for v in Q[1:]),"model_quotient_assignment")
        for i,(members,required) in tok_by_id.items():
            value=all(A[v]==bool(s) for v,s in zip(members,required))
            need(value==Q[i],"MASKED_AND_VALUE_NOT_EQUAL_VIRTUAL")
        for clause in qclauses:
            need(any(Q[abs(v)]==(v>0) for v in clause),
                 "QUOTIENT_GF2_MODEL_CLAUSE_FAILED")
        for index,clause in enumerate(clauses,1):
            need(any(A[abs(v)]==(v>0) for v in clause),
                 "ORIGINAL_SAT_MODEL_FAILED_CLAUSE_"+str(index))
        result.update({"SAT_status":"ORIGINAL_SAT_MODEL_INDEPENDENTLY_VERIFIED",
                       "source_model_all_clauses_checked":len(clauses)})
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True,type=Path)
    p.add_argument("--quotient",required=True,type=Path)
    p.add_argument("--certificate",required=True,type=Path)
    p.add_argument("--model",type=Path)
    a=p.parse_args()
    try:
        raw=a.source.read_bytes()
        q=a.quotient.read_bytes()
        cert=json.loads(a.certificate.read_text())
        model=json.loads(a.model.read_text()) if a.model else None
        result=verify(raw,q,cert,model)
        print("ATLAS6_INDEPENDENT_SEMANTIC "+json.dumps(result,sort_keys=True),flush=True)
    except (Invalid,ValueError,KeyError,TypeError,OSError,UnicodeError,MemoryError) as err:
        print("ATLAS6_INDEPENDENT_REJECT "+str(err),flush=True)
        raise SystemExit(1)
if __name__=="__main__":main()
