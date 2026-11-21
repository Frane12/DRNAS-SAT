#!/usr/bin/env python3
"""ATLAS8: controlled original-source masked GF(2) UNSAT proof, not a blind benchmark.

Construct two-way masked XOR from 3-regular graphs with a fixed perfect
matching of AND-masked edges, so every local source row has four original
variables. After source-only ATLAS6 semantic discovery, independently
validate complete source truth tables and compile a *standard original-CNF
VeriPB* RED/RUP/CP proof. The external VeriPB 3.0.2 checker is sole authority.

No known original UNSAT benchmark claimed; these are deterministic constructed
safety/proof-transport controls for next prospective *real* source study.
"""
import hashlib,json,itertools,random,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"research/atlas6_camouflage"))
sys.path.insert(0,str(ROOT/"research/xorlin1"))
from semantic_and_xor import extract,gauss_model
from check_semantic import verify as independent_source_verify
from emit_veripb import Proof

def h(x):return hashlib.sha256(x).hexdigest()
def dimacs(n,clauses):
    return (f"p cnf {n} {len(clauses)}\n"+
            "".join(" ".join(map(str,c))+" 0\n" for c in clauses)).encode("ascii")

GRAPH={
    "k4":{"edges":[(0,1),(0,2),(0,3),(1,2),(1,3),(2,3)],
          "matching":[(0,1),(2,3)],"n":4},
    "prism":{"edges":[(0,1),(1,2),(0,2),(3,4),(4,5),(3,5),(0,3),(1,4),(2,5)],
             "matching":[(0,3),(1,4),(2,5)],"n":6},
    "k33":{"edges":[(i,j) for i in range(3) for j in range(3,6)],
           "matching":[(0,3),(1,4),(2,5)],"n":6}
}

def generate(kind,seed,unsat):
    cfg=GRAPH[kind]
    r=random.Random(seed)
    edges=cfg["edges"]
    mask={tuple(sorted(e)) for e in cfg["matching"]}
    token={}
    nextvar=0
    for e in edges:
        nextvar+=1
        if tuple(sorted(e)) in mask:
            nextvar+=1
            token[e]=([nextvar-1,nextvar],[r.randrange(2),r.randrange(2)])
        else:
            token[e]=([nextvar],[1])
    used=[[] for _ in range(cfg["n"])]
    for e in edges:
        for node in e:used[node].append(e)
    assert all(len(u)==3 for u in used)
    rhs=[int(unsat and i==0) for i in range(cfg["n"])]
    clauses=[]
    for node,row in enumerate(used):
        members=[token[e] for e in row]
        support=sorted(v for vs,ss in members for v in vs)
        assert len(support)==4
        index={v:j for j,v in enumerate(support)}
        for values in range(1<<len(support)):
            q=[]
            for vars,required in members:
                q.append(int(all(((values>>index[v])&1)==s for v,s in zip(vars,required))))
            if sum(q)%2 != rhs[node]:
                clauses.append(tuple(-v if (values>>index[v])&1 else v for v in support))
    r.shuffle(clauses)
    raw=dimacs(nextvar,clauses)
    return raw,{"kind":kind,"seed":seed,"unsat_by_graph_parity":unsat,
                "source_sha256":h(raw),"source_vars":nextvar,
                "source_clauses":len(clauses),"math_known":"every virtual edge occurs in exactly two XOR equations; source RHS xor is 1 if UNSAT"}

def build_standard_original_proof(original,quotient,certificate):
    """Proof starts with original source; no quotient clause is trusted.
    RED definitions for q=literal_a AND literal_b, then original-source RUP
    derive each virtual XOR3 forbidden clause. Finishes with old externally
    audited XORLIN extended cutting-planes machinery.
    """
    import collections
    source_result=independent_source_verify(original,quotient,certificate)
    if source_result["status"]!="FULL_SOURCE_AND_GF2_EQUIVALENCE_VERIFIED":
        raise ValueError("independent_source_rejection")
    n,clauses=__import__("check_semantic").parse(original)
    p=Proof(clauses)
    var=certificate["source_vars"]
    token_map={}
    masked_gate_inputs={}
    for tok in certificate["tokens"]:
        members=tok["members"];true_if=tok["true_if"]
        if len(members)==1:
            if true_if!=[1]:raise ValueError("unsupported_signed_singleton")
            token_map[tok["id"]]=members[0]
        else:
            var+=1;q=var
            a=members[0] if true_if[0] else -members[0]
            b=members[1] if true_if[1] else -members[1]
            p.red((-q,a),q,0)
            p.red((-q,b),q,0)
            p.red((q,-a,-b),q,1)
            token_map[tok["id"]]=q
            masked_gate_inputs[q]=(a,b)
    width=collections.Counter()
    mapped_rows=[]
    for row in certificate["rows"]:
        ids=row["tokens"];rhs=row["rhs"]
        assert len(ids)==3
        terms=tuple(token_map[k] for k in ids)
        mapped_rows.append((terms,rhs))
        width[3]+=1
        for bits in itertools.product((0,1),repeat=3):
            if sum(bits)%2==rhs:continue
            clause=tuple(-x if bit else x for x,bit in zip(terms,bits))
            # An AND-mask set to false does not directly unit-propagate
            # its input literals. The SOURCE truth-table row first proves
            # each required gate input via two short RUP lemmas, which
            # then combine with q = a AND b for a full RUP XOR clause.
            # The external VeriPB checker must accept every step.
            for q,(a,b) in masked_gate_inputs.items():
                if q in clause:
                    guard=tuple(lit for lit in clause if lit!=q)
                    p.rup(guard+(a,))
                    p.rup(guard+(b,))
            p.rup(clause)
    incidence=collections.Counter(v for vars,rhs in mapped_rows for v in vars)
    if any(cnt%2 for cnt in incidence.values()) or sum(rhs for vars,rhs in mapped_rows)%2!=1:
        raise ValueError("no_odd_Gauss_contradiction")
    low=[];high=[]
    for terms,rhs in mapped_rows:
        x,y,z=terms
        var+=1;t=var
        if rhs==1:
            forward=[p.red((-t,v),t,0) for v in terms]
            p.red((t,-x,-y,-z),t,1)
            alo=p.index[frozenset(terms)]
            total=p.add(forward)
            lo=p.pol((total,2,"*",alo,"+",3,"d"))
            pairs=[p.rup((-a,-b,t)) for a,b in ((x,y),(x,z),(y,z))]
            hi=p.pol((p.add(pairs),2,"d"))
        else:
            pairs=((x,y),(x,z),(y,z))
            forward=[p.red((-t,a,b),t,0) for a,b in pairs]
            for a,b in pairs:p.red((t,-a,-b),t,1)
            lo=p.pol((p.add(forward),2,"d"))
            singles=[p.rup((-v,t)) for v in terms]
            no111=p.index[frozenset((-x,-y,-z))]
            hi=p.pol((p.add(singles),2,"*",no111,"+",3,"d"))
        low.append(lo);high.append(hi)
    total_lower=p.add(low)
    total_upper=p.add(high)
    low_cut=p.pol((total_lower,2,"d"))
    high_cut=p.pol((total_upper,2,"d"))
    p.pol((low_cut,high_cut,"+"))
    p.lines.extend(("output NONE ;","conclusion UNSAT ;","end pseudo-Boolean proof ;"))
    proof="\n".join(p.lines)+"\n"
    return proof,{"status":"EMITTED_EXTERNAL_VERIPB_REQUIRED",
                  "source_sha256":h(original),
                  "proof_sha256":h(proof.encode()),"proof_bytes":len(proof.encode()),
                  "masked_AND_definition_variables":sum(len(t["members"])==2 for t in certificate["tokens"]),
                  "original_source_RUP_quotient_clauses":sum(2**(len(r["tokens"])-1) for r in certificate["rows"]),
                  "xor_rows":len(mapped_rows),"proof_steps":dict(p.steps)}

def make_case(kind,seed,unsat):
    raw,meta=generate(kind,seed,unsat)
    q,cert=extract(raw)
    checked=independent_source_verify(raw,q,cert)
    assert checked["status"]=="FULL_SOURCE_AND_GF2_EQUIVALENCE_VERIFIED"
    solution=gauss_model(cert["rows"],cert["quotient_variables"])
    if unsat:
        assert solution is None
        proof,proofmeta=build_standard_original_proof(raw,q,cert)
        return raw,q,cert,meta,proof,proofmeta
    assert solution is not None
    from semantic_and_xor import lift_model
    model={"source_sha256":h(raw),"quotient_assignment":solution,
           "assignment":lift_model(cert,solution)}
    verdict=independent_source_verify(raw,q,cert,model)
    assert verdict["SAT_status"]=="ORIGINAL_SAT_MODEL_INDEPENDENTLY_VERIFIED"
    return raw,q,cert,meta,None,{"status":"SAT_ORIGINAL_MODEL_VERIFIED","model":model}

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--kind",choices=sorted(GRAPH),required=True)
    p.add_argument("--seed",type=int,required=True)
    p.add_argument("--mode",choices=["sat","unsat"],required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    raw,q,cert,meta,proof,pmeta=make_case(a.kind,a.seed,a.mode=="unsat")
    a.out.mkdir(exist_ok=True,parents=True)
    (a.out/"source.cnf").write_bytes(raw)
    (a.out/"quotient.cnf").write_bytes(q)
    (a.out/"semantic.json").write_text(json.dumps(cert,sort_keys=True,indent=2)+"\n")
    (a.out/"meta.json").write_text(json.dumps({**meta,**{k:v for k,v in pmeta.items() if k!="model"}},sort_keys=True,indent=2)+"\n")
    if proof is not None:(a.out/"original.pbp").write_text(proof)
    if "model" in pmeta:(a.out/"model.json").write_text(json.dumps(pmeta["model"],sort_keys=True)+"\n")
    print("ATLAS8_GENERATED "+json.dumps({**meta,
             "proof_status":pmeta["status"],"proof_bytes":pmeta.get("proof_bytes")},sort_keys=True))
