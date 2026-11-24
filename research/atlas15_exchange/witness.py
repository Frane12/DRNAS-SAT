#!/usr/bin/env python3
"""Independent source verifier for GRAPH/XOR3 mutex facts.

NO import of ATLAS15 producer, Hall engine or CP compiler. Re-reads exact
original CNF and proves every transferred clause [-a,-b] is source-implied
both by a separately interpreted structural witness and by independent
unit-propagation under assumptions (a,b) (RUP). The verifier returns no
SAT/UNSAT result; only standard external VeriPB may accept original UNSAT.
"""
import hashlib,itertools,json
from pathlib import Path

class Invalid(ValueError):pass
def require(x,why):
    if not x:raise Invalid(why)
def parse(raw, *, strict_premises=True):
    n=m=None;pending=[];rows=[]
    for line in raw.decode("ascii").splitlines():
        words=line.split()
        if not words or words[0]=="c":continue
        if words[0]=="p":
            require(n is None and len(words)==4 and words[1]=="cnf","DIMACS_HEADER")
            n,m=map(int,words[2:])
            require(1<=n<=200000 and 0<=m<=300000,"DIMACS_BOUNDS")
            continue
        require(n is not None,"DIMACS_NO_HEADER")
        for w in words:
            lit=int(w)
            require(abs(lit)<=n,"DIMACS_LITERAL_RANGE")
            if lit:pending.append(lit)
            else:
                if strict_premises:
                    require(len(pending)==len(set(pending)) and
                            not any(-x in pending for x in pending),
                            "DIMACS_REPEATED_OR_TAUTOLOGICAL")
                rows.append(tuple(pending));pending=[]
    require(n is not None and not pending and len(rows)==m,"DIMACS_CLAUSE_COUNT")
    return n,rows

def rup_mutex(clauses,a,b):
    """Original CNF UCP under a=b=True refutes [-a,-b]."""
    true_literals={a,b}
    for iteration in range(30000):
        changed=False
        for row in clauses:
            if any(lit in true_literals for lit in row):continue
            left=[lit for lit in row if -lit not in true_literals]
            if not left:return True
            if len(left)==1:
                lit=left[0]
                if -lit in true_literals:return True
                if lit not in true_literals:
                    true_literals.add(lit)
                    changed=True
        if not changed:return False
    raise Invalid("RUP_ITERATION_LIMIT")

def verify(raw,claim):
    require(type(claim) is dict and
            claim.get("format")=="DRNAS-ATLAS15-FACT-TRANSFER-v1","FACT_FORMAT")
    require(claim.get("source_sha256")==hashlib.sha256(raw).hexdigest(),
            "SOURCE_HASH")
    n,clauses=parse(raw)
    require(claim.get("source_variables")==n and
            claim.get("source_clauses")==len(clauses),"SOURCE_DIMENSIONS")
    index={frozenset(c) for c in clauses}
    alo=sorted({tuple(sorted(c)) for c in clauses
           if 3<=len(c)<=8 and all(x>0 for x in c)
           and len(set(c))==len(c)})
    require(3<=len(alo)<=32,"SOURCE_GROUP_COUNT")
    owners={}
    for g,row in enumerate(alo):
        for v in row:
            require(v not in owners,"OVERLAPPING_ALO")
            owners[v]=g
    auxiliaries=set(range(1,n+1))-set(owners)
    mode=claim.get("mode")
    require(mode in ("XOR_HALL","GRAPH_HALL","TRIPLE_HALL"),"MODE")
    claims=claim.get("facts")
    require(type(claims) is list and len(claims)<=16,"FACT_COUNT")
    kinds={"XOR3_UNIT_MUTEX":0,"GRAPH_PATH_MUTEX":0}
    seen=set()
    for fact in claims:
        require(type(fact) is dict and fact.get("kind") in kinds,"FACT_KIND")
        kind=fact["kind"];a=fact.get("a");b=fact.get("b")
        require(type(a) is int and type(b) is int and
                1<=a<b<=n and a in owners and b in owners and
                owners[a]!=owners[b],"CLAIM_SELECTOR_CROSS_GROUP")
        require((a,b) not in seen,"DUPLICATE_FACT")
        seen.add((a,b))
        require(frozenset((-a,-b)) not in index,"CLAIM_ALREADY_SOURCE_MUTEX")
        if kind=="GRAPH_PATH_MUTEX":
            require(mode!="XOR_HALL","MISLABELED_GRAPH_MODE")
            path=fact.get("path")
            require(type(path) is list and len(path)==3 and
                    all(type(v) is int and v!=0 and abs(v)<=n for v in path),
                    "GRAPH_PATH_STRUCTURE")
            first,t,end=path
            require({first,-end}=={a,b} and first>0 and end<0,
                    "GRAPH_PATH_ENDPOINT")
            require(abs(t) in auxiliaries,"GRAPH_AUX_NOT_AUX")
            expected=[frozenset((-first,t)),frozenset((-t,end))]
            require(all(row in index for row in expected),
                    "GRAPH_SOURCE_IMPLICATION_MISSING")
            stored=fact.get("source_clauses")
            require(type(stored) is list and stored==
                [sorted(x) for x in expected],"GRAPH_PROVENANCE_WRONG")
        else:
            require(mode!="GRAPH_HALL","MISLABELED_XOR_MODE")
            t=fact.get("aux")
            require(type(t) is int and t in auxiliaries and
                    fact.get("rhs")==0 and fact.get("unit")==t,
                    "XOR_AUX_UNIT_PARITY")
            require(frozenset((t,)) in index,"SOURCE_XOR_UNIT_MISSING")
            expected=[
                frozenset(-v if bit else v
                   for v,bit in zip((a,b,t),bits))
                for bits in itertools.product((0,1),repeat=3)
                if sum(bits)%2==1]
            require(all(row in index for row in expected),
                    "SOURCE_XOR_TRUTH_TABLE_INCOMPLETE")
            stored=fact.get("source_xor_clauses")
            require(type(stored) is list and
                    sorted(map(tuple,stored))==sorted(tuple(sorted(x)) for x in expected),
                    "XOR_SOURCE_CLAUSE_IDS_WRONG")
        require(rup_mutex(clauses,a,b),
                "CLAIMED_MUTEX_NOT_SOURCE_RUP")
        kinds[kind]+=1
    require(kinds["XOR3_UNIT_MUTEX"]==claim.get("xor_fact_count") and
            kinds["GRAPH_PATH_MUTEX"]==claim.get("graph_fact_count"),
            "FACT_COUNT_BY_KIND")
    return {"status":"ATLAS15_ORIGINAL_SOURCE_LEMMAS_INDEPENDENTLY_VERIFIED",
      "source_sha256":hashlib.sha256(raw).hexdigest(),
      "original_clauses_verified":len(clauses),
      "original_ALO_groups":len(alo),
      "transferred_source_RUP_lemmas":len(claims),
      "graph_lemmas_verified":kinds["GRAPH_PATH_MUTEX"],
      "xor3_unit_lemmas_verified":kinds["XOR3_UNIT_MUTEX"],
      "SAT_UNSAT_VERDICT":"NONE",
      "standard_original_Veripb_still_required":True}


def verify_full_original_sat_model(raw,model):
    """Standalone full original-source SAT witness checker.

    This uses only the independently parsed ORIGINAL CNF and the complete
    model, never the generator, discovery algorithm or a saved status.
    """
    n,rows=parse(raw,strict_premises=False)
    require(type(model) is dict and
            model.get("source_sha256")==hashlib.sha256(raw).hexdigest(),
            "SAT_WITNESS_ORIGINAL_SHA")
    bits=model.get("assignment")
    require(type(bits) is list and len(bits)==n+1 and bits[0] is None,
            "SAT_WITNESS_ASSIGNMENT_SIZE")
    require(all(type(v) is bool for v in bits[1:]),
            "SAT_WITNESS_NONBOOLEAN")
    for i,row in enumerate(rows,1):
        require(any(bits[abs(l)]==(l>0) for l in row),
                "SAT_WITNESS_FALSE_CLAUSE_"+str(i))
    return {"status":"INDEPENDENT_ORIGINAL_SOURCE_SAT_MODEL_VERIFIED",
            "source_sha256":hashlib.sha256(raw).hexdigest(),
            "original_variables":n,"source_clauses_checked":len(rows)}

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True,type=Path)
    p.add_argument("--claims",required=True,type=Path)
    a=p.parse_args()
    try:
        result=verify(a.source.read_bytes(),json.loads(a.claims.read_text()))
        print("ATLAS15_SOURCE_FACTS_VERIFIED "+json.dumps(result,sort_keys=True))
    except (Invalid,ValueError,TypeError,KeyError,OSError) as e:
        print("ATLAS15_SOURCE_FACTS_REJECTED "+str(e)[:250])
        raise SystemExit(1)
if __name__=="__main__":main()
