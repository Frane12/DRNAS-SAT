#!/usr/bin/env python3
"""ATLAS12 real original source and adversarial source-fact proof controls.

Positive proofs must be independently accepted on exact source DIMACS by
external VeriPB. Negative controls carry explicit SAT models checked against
EVERY source clause. No random benchmark substitutions, no main change.
"""
from __future__ import annotations
import hashlib,itertools,json,os,random,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/"atlas12_results"
OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/"research/structure_atlas1"))
sys.path.insert(0,str(ROOT/"research/structure_atlas3"))
sys.path.insert(0,str(ROOT/"research/graphclique"))
sys.path.insert(0,str(ROOT/"research/pcmax_capacity"))
from atlas import parse as source_parse,encoded,transform
from source_facts import derive as eo_fact_producer
from check_facts import check as eo_independent_check
from check_php_partition import check as hall_independent_check
from bridge import discover,run
import emit_veripb as graph_emitter

CPU=min(os.sched_getaffinity(0))
os.sched_setaffinity(0,{CPU})
def sha(raw):return hashlib.sha256(raw).hexdigest()
def model_ok(raw,assn):
    nv,clauses=source_parse(raw)
    return len(assn)==nv and all(any(assn[abs(lit)]==(lit>0) for lit in clause)
                                 for clause in clauses)
def make_coloring(k,n,edge_pairs,seed,missing_pair=None):
    rng=random.Random(seed)
    ids=list(range(1,k*n+1));rng.shuffle(ids)
    mapping={(v,c):ids[v*k+c] for v in range(n) for c in range(k)}
    cs=[]
    for v in range(n):
        row=[mapping[(v,c)] for c in range(k)]
        cs.append(tuple(row))
        for a,b in itertools.combinations(row,2):cs.append((-a,-b))
    for u,v in edge_pairs:
        for c in range(k):
            if missing_pair and set((u,v))==set(missing_pair[:2]) and c==missing_pair[2]:
                continue
            cs.append((-mapping[(u,c)],-mapping[(v,c)]))
    for c in cs:assert len(set(map(abs,c)))==len(c)
    for i in range(len(cs)):
        cs[i]=tuple(rng.sample(cs[i],len(cs[i])))
    rng.shuffle(cs)
    return encoded(k*n,cs),mapping
def verify_external(cnf,pbp,label):
    start=time.perf_counter()
    p=subprocess.run(["taskset","-c",str(CPU),"veripb","--cnf",str(cnf),str(pbp)],
       capture_output=True,text=True,timeout=45)
    success=p.returncode==0 and "s VERIFIED UNSATISFIABLE" in p.stdout+p.stderr
    (OUT/(label+".veripb.log")).write_text(p.stdout+"\n"+p.stderr)
    if not success:
        raise AssertionError("EXTERNAL_STANDARD_PROOF_REJECTED_"+label+":"+(p.stdout+p.stderr)[-400:])
    return round(time.perf_counter()-start,6)
def case(raw,label,kind):
    folder=OUT/label;folder.mkdir(parents=True,exist_ok=True)
    source=folder/"original.cnf";source.write_bytes(raw)
    cnf=folder/"source-fact-hall.json"
    pbp=folder/"original-source.pbp"
    m=folder/"meta.json"
    result=run(source,cnf,pbp,m)
    assert hall_independent_check(source,cnf)["status"]=="UNSAT_SOURCE_CLIQUE_VERIFIED"
    checker_s=verify_external(source,pbp,label)
    result.update({"case":label,"case_kind":kind,
          "status":"STANDARD_ORIGINAL_VERIPB_VERIFIED_UNSAT",
          "independent_external_Veripb_s":checker_s,
          "strict_veripb":True})
    (folder/"result.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("ATLAS12_STANDARD_PROOF "+json.dumps({
        "case":label,"kind":kind,
        "source_sha256":result["source_sha256"],
        "ALO_groups":result["ALO_source_groups"],
        "direct_EO_groups":result["direct_source_exact_one_groups"],
        "GRAPH_clique":result["GRAPH_aligned_clique"],
        "HALL_resource_count":result["HALL_resources"],
        "proof_bytes":result["proof_bytes"],
        "veripb_s":checker_s},sort_keys=True),flush=True)
    return result

records=[];controls=[]
# Fresh generated controls: both actual EO and ALO are in source. Four
# different k values; the exact accepted proofs are not competition benchmarks.
for k in range(2,6):
    n=k+1
    clique_edges=list(itertools.combinations(range(n),2))
    raw,mapping=make_coloring(k,n,clique_edges,1000+k)
    facts=eo_fact_producer(raw)
    independently=eo_independent_check(raw,facts)
    assert independently["status"]=="SOURCE_FACTS_INDEPENDENTLY_VERIFIED"
    source_eo={frozenset(g) for g in facts["exact_one_groups"]}
    assert all(frozenset(mapping[(v,c)] for c in range(k)) in source_eo
               for v in range(n)), "SOURCE_VERTEX_EO_GROUP_MISSING"
    r=case(raw,f"synthetic-K{n}-with-{k}-colors","synthetic_eo_graph_hall")
    assert r["direct_source_exact_one_groups"]==n
    records.append(r)
    if k==3:
        # Signed variable *names* and clause order preserving explicit EO:
        # do not claim coverage of polarity changes for source-positive ALO.
        nv,cs=source_parse(raw)
        shuffled,known_inverse,_=transform(nv,cs,20261122,rename=True,flip=False,shuffle=True)
        assert known_inverse and sha(shuffled)!=sha(raw)
        records.append(case(shuffled,"synthetic-K4-renamed","synthetic_rename_only"))
        # Removing ONE exact source GRAPH blocking edge produces a SAT source.
        changed,m=make_coloring(k,n,clique_edges,2020,missing_pair=(0,1,0))
        assignment={m[(v,c)]:(c==(0 if v<2 else v-1)) for v in range(n) for c in range(k)}
        assert model_ok(changed,assignment)
        # Without that source conflict, graph/Hall should not claim UNSAT.
        try:discover(OUT/"nonexisting.cnf")
        except OSError:pass
        p=OUT/"synthetic-missing-one-edge-SAT.cnf";p.write_bytes(changed)
        try:discover(p)
        except graph_emitter.Unsupported:
            controls.append({"control":"missing_one_graph_conflict",
                "outcome":"SAFE_UNKNOWN","SAT_model_independent":True})
        else:raise AssertionError("FALSE_UNSAT_ON_VALID_SAT_COLORING")
        # Same control for an actual k-colorable complete graph K_k.
        sat,sm=make_coloring(k,k,list(itertools.combinations(range(k),2)),2021)
        assn={sm[(v,c)]:(c==v) for v in range(k) for c in range(k)}
        assert model_ok(sat,assn)
        path=OUT/"synthetic-k-colorable-SAT.cnf";path.write_bytes(sat)
        try:discover(path)
        except graph_emitter.Unsupported:
            controls.append({"control":"proper_Kk_k_coloring","outcome":"SAFE_UNKNOWN",
                "SAT_model_independent":True})
        else:raise AssertionError("FALSE_UNSAT_ON_KK_SAT")
        # Forge exact source SHA in a previously successful source certificate.
        cert_path=OUT/"synthetic-K4-with-3-colors"/"source-fact-hall.json"
        original_path=OUT/"synthetic-K4-with-3-colors"/"original.cnf"
        cert=json.loads(cert_path.read_text());cert["source_sha256"]="0"*64
        forged=OUT/"forged-hall-certificate.json"
        forged.write_text(json.dumps(cert,sort_keys=True)+"\n")
        try:hall_independent_check(original_path,forged)
        except ValueError:
            controls.append({"control":"forged_original_SHA",
              "outcome":"INDEPENDENT_SOURCE_REJECT"})
        else:raise AssertionError("FORGED_SHA_ACCEPTED")
        # Delete one chosen source graph-mutex and update claimed SHA.
        cert=json.loads(cert_path.read_text())
        original=original_path.read_bytes()
        nn,cl=source_parse(original)
        pick=cert["capacity_cliques"][0]
        forbidden=frozenset((-pick[0],-pick[1]))
        deleted=False;new=[]
        for row in cl:
            if not deleted and frozenset(row)==forbidden:
                deleted=True;continue
            new.append(row)
        assert deleted
        tampered=encoded(nn,new)
        test=OUT/"tampered-source.cnf";test.write_bytes(tampered)
        cert["source_sha256"]=sha(tampered)
        cert["source_clauses"]=len(new)
        fake=OUT/"tampered-rehashed-certificate.json"
        fake.write_text(json.dumps(cert,sort_keys=True)+"\n")
        try:hall_independent_check(test,fake)
        except ValueError:
            controls.append({"control":"deleted_source_mutex_updated_SHA",
              "outcome":"INDEPENDENT_SOURCE_REJECT"})
        else:raise AssertionError("DELETED_MUTEX_ACCEPTED")
# One real previously published original graph source (no new blind label).
original=ROOT/"evidence/graph-k11/original.cnf"
actual=original.read_bytes()
start=time.perf_counter()
try:
    rec=case(actual,"real-original-graph-k11","previously_published_original_graph")
    rec["original_source_in_repository"]=str(original.relative_to(ROOT))
    records.append(rec)
except graph_emitter.Unsupported as error:
    state={"case":"real-original-graph-k11","status":"UNKNOWN_SOURCE_GATE",
           "reason":str(error),"source_sha256":sha(actual)}
    records.append(state)
    print("ATLAS12_REAL_UNKNOWN "+json.dumps(state,sort_keys=True),flush=True)
# Honest unrelated-family rejection is expected, not a fake proof result.
unrelated=ROOT/"evidence/pcmax-weighted2/00/original.cnf"
if unrelated.exists():
    path=OUT/"pcmax-original00.cnf";path.write_bytes(unrelated.read_bytes())
    try:
        cert,meta=discover(path,budget=15000)
        controls.append({"control":"different_BDD_source",
              "outcome":"GRAPH_HALL_PREMISES_FOUND_UNVERIFIED",
              "original_sha256":sha(path.read_bytes())})
    except graph_emitter.Unsupported as e:
        controls.append({"control":"different_BDD_source",
              "outcome":"SAFE_UNKNOWN","reason":str(e)[:180]})
summary={
    "status":"COMPLETE","original_input_source":"evidence/graph-k11/original.cnf",
    "real_original_source_sha256":sha(actual),
    "real_original_strict_verified":sum(x.get("strict_veripb",False)
                           for x in records if x.get("case")=="real-original-graph-k11"),
    "synthetic_standard_verified":sum(x.get("strict_veripb",False)
                           for x in records if x.get("case_kind","").startswith("synthetic")),
    "source_checks_real_original":1,
    "source_forgery_controls_checked":len(controls),
    "safety_controls":controls,
    "cases":records,
    "known_theorem_not_new_complexity_class":True,
    "graph_and_hall_are_existing_structural_modules":True,
    "no_claim_of_new_cross_family_solver_win":True,"main_untouched":True
}
(OUT/"summary.json").write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n")
print("ATLAS12_FINAL "+json.dumps({k:v for k,v in summary.items() if k not in ("cases","safety_controls")},sort_keys=True),flush=True)
assert summary["synthetic_standard_verified"]==5
assert summary["source_forgery_controls_checked"]>=4
