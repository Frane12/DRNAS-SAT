#!/usr/bin/env python3
"""DRNAS ATLAS13: proof-carrying GRAPH(2SAT implication) -> HALL exchange.

Graph implication module sends *new, source-implied* binary mutex facts to
Hall. Hall's source-only direct-mutex mode and preexisting aligned-clique
GRAPH mode BOTH return UNKNOWN on the intended controlled instances.

The transfer lemmas are source-RUP derivable in two implications:
   (¬a ∨ t), (¬t ∨ ¬b)  ==>  (¬a ∨ ¬b).
Their paths are checked by an independent implementation that re-reads
the ORIGINAL DIMACS. The new Hall source certificate is checked against
the original CNF augmented by these certified derived constraints.
A final VeriPB PBP is lifted BACK to the unmodified original by inserting
one externally checked 'rup' instruction for each derived constraint
before the old Hall cutting-planes steps.

Only external VeriPB accepting that exact ORIGINAL CNF makes strict UNSAT.
This is a controlled two-module inference exchange demonstration, NOT a new
proof-complexity theorem or a claim on unseen competition formulas.
"""
import hashlib,json,os,sys,tempfile,time,itertools
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"research/structure_atlas1"))
sys.path.insert(0,str(ROOT/"research/pcmax_capacity"))
sys.path.insert(0,str(ROOT/"research/atlas12_graph_hall"))
sys.path.insert(0,str(ROOT/"research/graphclique"))
from atlas import parse,encoded
from check_php_partition import check as hall_independent
from emit_veripb_source_clique import emit as hall_proof_emitter
from bridge import discover as previous_graph_clique_discover
import emit_veripb as graph_module
from witness_checker import check_witness as independent_lemma_check
MAX_GROUPS=32
MAX_CLAUSES=200_000
MAX_DERIVED_LEMMAS=24

class Unknown(ValueError):pass
def need(v,msg):
    if not v:raise Unknown(msg)
def sha(raw):return hashlib.sha256(raw).hexdigest()

def original_facts(raw):
    nv,clauses=parse(raw)
    need(len(clauses)<=MAX_CLAUSES,"CLAUSE_BUDGET")
    positive=sorted({tuple(sorted(row)) for row in clauses
        if 3<=len(row)<=12 and all(x>0 for x in row)
        and len(set(row))==len(row)})
    need(3<=len(positive)<=MAX_GROUPS,"ALO_GROUP_COUNT_GATE")
    owner={}
    for i,group in enumerate(positive):
        for v in group:
            need(v not in owner,"OVERLAPPING_DEMAND_VARIABLES")
            owner[v]=i
    # Other variables may be auxiliary implications, NOT required to be
    # in the ALO groups. This is precisely why old Hall source parser alone
    # can be blind to source encodings with extra intermediate variables.
    idx={frozenset(c) for c in clauses}
    source_cross=set()
    graph=defaultdict(set)
    for clause in clauses:
        if len(clause)!=2 or len(set(clause))!=2:continue
        x,y=clause
        graph[-x].add(y)
        graph[-y].add(x)
        if x<0 and y<0 and -x in owner and -y in owner and owner[-x]!=owner[-y]:
            source_cross.add(tuple(sorted((-x,-y))))
    aux=set(range(1,nv+1))-set(owner)
    return nv,clauses,positive,owner,source_cross,graph,aux,idx

def derived_two_hop_graph_lemmas(raw):
    nv,clauses,groups,owner,direct,graph,aux,index=original_facts(raw)
    new={}
    for a in sorted(owner):
        for t in sorted(graph.get(a,())):
            if abs(t) not in aux:continue
            for end in sorted(graph.get(t,())):
                b=-end
                if b not in owner or b==a or owner[b]==owner[a]:continue
                pair=tuple(sorted((a,b)))
                if pair in direct:continue
                first=frozenset((-a,t))
                second=frozenset((-t,-b))
                if first not in index or second not in index:continue
                if pair not in new:
                    new[pair]={"a":pair[0],"b":pair[1],
                               "path":[a,t,-b],
                               "input_clause_1":sorted(first),
                               "input_clause_2":sorted(second)}
    need(0<len(new)<=MAX_DERIVED_LEMMAS,"NO_BOUNDED_GRAPH_IMPLICATION_LEMMAS")
    return sorted(new.values(),key=lambda x:(x["a"],x["b"]))

def hall_partition(raw,extra=()):
    # Hall module is restricted to literal original-source mutexes PLUS
    # specifically proof-carrying transferred graph lemmas (if supplied).
    nv,clauses,groups,owner,direct,_,_,_=original_facts(raw)
    pairs=set(direct)
    for lemma in extra:
        a,b=lemma["a"],lemma["b"]
        need(a in owner and b in owner and owner[a]!=owner[b],
             "GRAPH_LEMMA_NOT_CROSS_GROUP")
        pairs.add(tuple(sorted((a,b))))
    parent={v:v for v in owner}
    def find(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]]
            x=parent[x]
        return x
    for a,b in sorted(pairs):
        aa,bb=find(a),find(b)
        if aa!=bb:parent[bb]=aa
    clusters=defaultdict(list)
    for v in owner:clusters[find(v)].append(v)
    resources=sorted((sorted(vals) for vals in clusters.values()),
                       key=lambda xs:(xs[0],len(xs)))
    if any(len(resource)<2 for resource in resources):
        raise Unknown("HALL_ISOLATED_RESOURCE")
    for resource in resources:
        for a,b in itertools.combinations(resource,2):
            if (a,b) not in pairs:
                raise Unknown("HALL_RESOURCE_NOT_SOURCE_OR_DERIVED_CLIQUE")
    if len(groups)<=len(resources):
        raise Unknown("HALL_NO_CAPACITY_DEFICIT")
    # Exact literal-cover and pair-source checks are repeated externally
    # on the original+lemmas by check_php_partition.py.
    return {"format":"DRNAS-source-clique-capacity-v1",
       "source_sha256":None,"source_variables":nv,
       "source_clauses":len(clauses)+len(extra),
       "selected_groups":[list(g) for g in groups],
       "capacity_cliques":resources,
       "demand":len(groups),"capacity":len(resources)}

def baseline_status(source):
    source=Path(source)
    raw=source.read_bytes()
    graph_status="UNKNOWN"
    try:
        previous_graph_clique_discover(source,15000)
        graph_status="UNSAT_CLIQUE_PREMISES_FOUND"
    except graph_module.Unsupported:
        pass
    hall_status="UNKNOWN"
    try:
        hall_partition(raw,())
        hall_status="UNSAT_HALL_PREMISES_FOUND"
    except Unknown:pass
    # The 2SAT graph alone cannot UNSAT here: all-false assignment to
    # every original variable satisfies every source BINARY constraint.
    _,clauses=parse(raw)
    all_false_2sat=all(any(lit<0 for lit in cl) for cl in clauses if len(cl)==2)
    return {"GRAPH_CLIQUE_ONLY":graph_status,"HALL_DIRECT_ONLY":hall_status,
            "binary_implication_subsystem_has_all_false_model":all_false_2sat}

def compile_original(source,certfile,proofout,metadata):
    source=Path(source);certfile=Path(certfile);proofout=Path(proofout)
    metadata=Path(metadata)
    started=time.perf_counter()
    raw=source.read_bytes()
    basis=baseline_status(source)
    # Require that BOTH independently functioning source-only prior modes
    # are UNKNOWN, or abstain. No cherry-picked 'final proof' on easy cases.
    need(basis["GRAPH_CLIQUE_ONLY"]=="UNKNOWN","GRAPH_BASELINE_NOT_UNKNOWN")
    need(basis["HALL_DIRECT_ONLY"]=="UNKNOWN","HALL_BASELINE_NOT_UNKNOWN")
    need(basis["binary_implication_subsystem_has_all_false_model"],
         "BINARY_GRAPH_SUBSYSTEM_NOT_KNOWN_SAT")
    lemmas=derived_two_hop_graph_lemmas(raw)
    candidates={"format":"DRNAS-ATLAS13-GRAPH-IMPLICATION-v1",
        "source_sha256":sha(raw),"original_clause_count":len(parse(raw)[1]),
        "lemmas":lemmas}
    independently=independent_lemma_check(raw,candidates)
    need(independently["status"]=="GRAPH_IMPLICATION_LEMMAS_SOURCE_VERIFIED",
         "INDEPENDENT_GRAPH_LEMMAS_REJECTED")
    _,source_clauses=parse(raw)
    aug=encoded(parse(raw)[0],source_clauses+
                [(-item["a"],-item["b"]) for item in lemmas])
    cert=hall_partition(raw,lemmas)
    cert["source_sha256"]=sha(aug)
    checked_original_sha=sha(raw)
    # Source/original SHA is stored separately from augmented internal
    # representation, to prevent ever confusing quotient for original.
    candidates["augmented_sha256"]=sha(aug)
    with tempfile.TemporaryDirectory(prefix="atlas13-math-exchange-") as temp:
        td=Path(temp)
        augmented=td/"verified-lemma-augmented.cnf"
        augmented.write_bytes(aug)
        hall_cert=td/"hall-on-verified-lemmas.json"
        hall_cert.write_text(json.dumps(cert,sort_keys=True)+"\n")
        verified=hall_independent(augmented,hall_cert)
        need(verified["status"]=="UNSAT_SOURCE_CLIQUE_VERIFIED",
             "INDEPENDENT_AUGMENTED_HALL_NOT_VERIFIED")
        compiled=td/"augmented.pbp"
        proof_meta=hall_proof_emitter(augmented,hall_cert,compiled)
        need(proof_meta["status"]=="EMITTED_UNCHECKED",
             "HALL_EMITTER_REJECTED_CERT")
        lines=compiled.read_text().splitlines()
        need(lines[0]=="pseudo-Boolean proof version 3.0","PBP_HEADER")
        need(lines[1]==f"f {len(source_clauses)+len(lemmas)} ;",
             "AUGMENTED_PROOF_PREMISE_COUNT")
        p=["pseudo-Boolean proof version 3.0",f"f {len(source_clauses)} ;"]
        for l in lemmas:
            p.append(f"rup 1 ~x{l['a']} 1 ~x{l['b']} >= 1 ;")
        p.extend(lines[2:])
        original_pbp="\n".join(p)+"\n"
        need(len(original_pbp)<4_000_000,"PROOF_BUDGET")
    certfile.parent.mkdir(exist_ok=True,parents=True)
    certfile.write_text(json.dumps({**candidates,"hall_certificate_on_augmented":cert,
             "augmented_source_checker":verified["status"],
             "original_graph_checker":independently["status"]},
             sort_keys=True,indent=2)+"\n")
    proofout.write_text(original_pbp)
    result={"status":"PROOF_EMITTED_REQUIRES_EXTERNAL_VERIPB",
        "source_original_sha256":checked_original_sha,
        "source_augmented_sha256":sha(aug),"premise_count_original":len(source_clauses),
        "derived_source_RUP_lemmas":len(lemmas),"proof_sha256":sha(original_pbp.encode()),
        "proof_bytes":len(original_pbp.encode()),
        "baseline_modes":basis,
        "ALO_demand":cert["demand"],"HALL_capacity":cert["capacity"],
        "capacity_deficit":cert["demand"]-cert["capacity"],
        "independent_graph_implication_lemmas":independently["status"],
        "independent_HALL_after_exchange":verified["status"],
        "proof_compiled_via_existing_HALL_CP":True,
        "full_original_veripb_still_required":True,
        "source_math_elapsed_without_external_checker_s":round(time.perf_counter()-started,6)}
    metadata.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("ATLAS13_PROOF_EMITTED "+json.dumps(result,sort_keys=True),flush=True)
    return result

def main():
    p=__import__("argparse").ArgumentParser()
    p.add_argument("--cnf",required=True,type=Path)
    p.add_argument("--certificate",required=True,type=Path)
    p.add_argument("--proof",required=True,type=Path)
    p.add_argument("--meta",required=True,type=Path)
    a=p.parse_args()
    try:compile_original(a.cnf,a.certificate,a.proof,a.meta)
    except (Unknown,ValueError,TypeError,IndexError,OSError,
            graph_module.Unsupported,KeyError,OverflowError) as exc:
        a.certificate.unlink(missing_ok=True);a.proof.unlink(missing_ok=True)
        a.meta.unlink(missing_ok=True)
        print("ATLAS13_SAFE_UNKNOWN "+str(exc)[:450],flush=True)
        raise SystemExit(2)
if __name__=="__main__":main()
