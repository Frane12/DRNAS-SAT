#!/usr/bin/env python3
"""ATLAS3 audit: 14 ORIGINAL source CNFs, 42 controlled bijective variants,
independent exact-source fact validation, 14 source-mutation safety controls,
and real-source cross-encoding rewriters with separate projected semantics.

This is a fact-recognition benchmark, not a solver-performance or new
VeriPB/DRAT UNSAT benchmark. Source names and prior SAT statuses never enter
the recognizer. Known inverse maps prove exact clause-multiset equivalence
for bijective transforms; sequential rewrite has distinct auxiliary vars
and only existentially equivalent original-variable projections.
"""
import collections,csv,hashlib,json,itertools,os,sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"research"/"structure_atlas1"))
from atlas import parse,encoded,scan,transform
from semantic_eo import unit_conflict
from source_facts import derive,fact_summary,reencode_amo,local_sequential_equivalence,verify_local_sequential_large
from check_facts import check,Invalid

OUT=ROOT/"structure_atlas3_results"
OUT.mkdir(exist_ok=True)
INPUTS=[
 ("graph","evidence/graph-k11/original.cnf"),
 ("petersen","evidence/ipg7b-petersen/original.cnf"),
 ("xor-grid","evidence/xor234-grid5/original.cnf"),
]+[("pcmax",f"evidence/pcmax-weighted2/{x}/original.cnf")
    for x in ("00","02","03","04","05","07","08","09","10","14","15")]
assert len(INPUTS)==14
VARIANTS=[
 ("rename",31201,False),
 ("rename-polarity",31202,True),
 ("rename-polarity2",31203,True)]
original_rows=[];variant_rows=[];mutated=0;rewrite_rows=[]
started_all=time.perf_counter()

# Local projected semantics oracle of the two encoders, independent for
# every bool source selector assignment. The 12-wide test checks prefix
# witnesses and all pairwise UCP conflicts.
for n in (2,3,4,5,6):
    assert local_sequential_equivalence(n),("encodings_differ",n)
for n in (7,9,12):
    assert verify_local_sequential_large(n),("sequential_refutation_failed",n)

for idx,(family,path) in enumerate(INPUTS):
    raw=(ROOT/path).read_bytes()
    start=time.perf_counter()
    f=derive(raw)
    report=check(raw,f)
    orig_sig=scan(raw)["coarse_invariant_sha256"]
    sec=time.perf_counter()-start
    counts=fact_summary(f)
    source_sha=hashlib.sha256(raw).hexdigest()
    original_rows.append({"family":family,"source":path,"sha256":source_sha,
        "vars":f["source_variables"],"clauses":f["source_clauses"],
        "facts":counts,"coarse":orig_sig,"independent_check":report["status"],
        "wall_s":round(sec,6)})
    print("ORIGINAL "+json.dumps(original_rows[-1],sort_keys=True),flush=True)
    # The original CNF is unchanged. Save exact source-bound fact data.
    (OUT/(f"original-{idx:02}.facts.json")).write_text(json.dumps(f,indent=2,sort_keys=True)+"\n")

    for rep,(label,seed,flip) in enumerate(VARIANTS):
        nv,clauses=parse(raw)
        altered,known_equivalence,metadata=transform(nv,clauses,seed+idx*101,
                                    rename=True,flip=flip,shuffle=True)
        assert known_equivalence
        derived=derive(altered)
        verified=check(altered,derived)
        assert verified["status"]=="SOURCE_FACTS_INDEPENDENTLY_VERIFIED"
        summary=fact_summary(derived)
        assert summary["eo_count"]==counts["eo_count"],("EO_gone",path,label,summary,counts)
        assert summary["xor_counts"]==counts["xor_counts"],("XOR_gone",path,label,summary,counts)
        assert scan(altered)["coarse_invariant_sha256"]==orig_sig
        assert hashlib.sha256(altered).hexdigest()!=source_sha
        variant_rows.append({"source":path,"family":family,"variant":label,
            "seed":seed+idx*101,"sign_flip":flip,
            "source_sha256":source_sha,"variant_sha256":hashlib.sha256(altered).hexdigest(),
            "known_exact_inverse_equivalence":known_equivalence,
            "independent_fact_check":"PASS",
            "EO_count_original":counts["eo_count"],"EO_count_variant":summary["eo_count"],
            "XOR_by_width_original":str(counts["xor_counts"]),
            "XOR_by_width_variant":str(summary["xor_counts"]),
            "fingerprint_invariant":True})
        print("VARIANT "+json.dumps(variant_rows[-1],sort_keys=True),flush=True)
    # Rejection test 1: change original bytes AND maliciously update claimed
    # SHA to match a changed source, but leave original proof premises.
    if f["exact_one_groups"]:
        first=f["exact_one_groups"][0]
        target=frozenset((-first[0],-first[1]))
    elif f["complete_xor_rows"]:
        row=f["complete_xor_rows"][0]
        vs=row["vars"];rhs=row["rhs"]
        bits=next(t for t in itertools.product((0,1),repeat=len(vs)) if sum(t)%2!=rhs)
        target=frozenset((-v if bits[j] else v) for j,v in enumerate(vs))
    else:
        target=None
    if target is not None:
        nv,clauses=parse(raw)
        newer=[cl for cl in clauses if frozenset(cl)!=target]
        assert len(newer)<len(clauses)
        tampered=encoded(nv,newer)
        claim=json.loads(json.dumps(f))
        claim["source_sha256"]=hashlib.sha256(tampered).hexdigest()
        claim["source_clauses"]=len(newer)
        try:
            check(tampered,claim)
            raise AssertionError(("FALSE_ACCEPT",path))
        except Invalid:
            mutated+=1
            print("SOURCE_MUTATION_REJECT "+json.dumps({"source":path,"removed":len(clauses)-len(newer)},sort_keys=True),flush=True)
    else:
        print("SOURCE_MUTATION_NOT_APPLICABLE "+path,flush=True)

# Cross-encoding tests on selected real ORIGINAL CNFs with source-supported EO:
# replace exactly ONE source AMO group, keeping every other clause unchanged.
# Exact original-variable projection equality follows from the tested Sinz
# encoder: at most one selector true iff exists a sequential prefix witness.
TARGETS=[
 "evidence/ipg7b-petersen/original.cnf",
 "evidence/xor234-grid5/original.cnf",
 "evidence/pcmax-weighted2/05/original.cnf",
 "evidence/pcmax-weighted2/15/original.cnf"]
for idx,path in enumerate(TARGETS):
    raw=(ROOT/path).read_bytes()
    f=derive(raw)
    options=[g for g in f["exact_one_groups"] if 2<=len(g)<=12]
    if not options:
        print("CROSS_ENCODER_UNSUPPORTED "+path,flush=True)
        rewrite_rows.append({"source":path,"status":"NO_EO_WIDTH_3_TO_12"})
        continue
    chosen=min(options,key=lambda g:(len(g),[abs(x) for x in g]))
    rewritten,info=reencode_amo(raw,chosen)
    nv,source=parse(raw);new_nv,new_clauses=parse(rewritten)
    origs={frozenset(c) for c in source}
    removed={frozenset((-a,-b)) for a,b in itertools.combinations(chosen,2)}
    kept=[c for c in source if frozenset(c) not in removed]
    # Construct the new local suffix deterministically from literal list.
    extra=new_clauses[len(kept):]
    assert all(all(abs(l)<=nv or abs(l) in info["new_auxiliary_variables"] for l in c)
               for c in new_clauses)
    assert new_clauses[:len(kept)]==kept
    assert len(extra)==info["added_auxiliary_clauses"]
    # Each pair is refuted by the NEW local sequential encoding itself.
    pair_conflicts=0
    for a,b in itertools.combinations(chosen,2):
        assert unit_conflict(extra,(a,b)),("new_AMO_not_RUP",path,a,b)
        pair_conflicts+=1
    # Every feasible selector assignment with <=1 TRUE has a witness
    # for the local auxiliary chain. For other original variables,
    # the new clauses are independent and do not restrict them.
    n=len(chosen);s=info["new_auxiliary_variables"]
    for selected in [-1]+list(range(n)):
        A={abs(l):(l>0)==(j==selected) for j,l in enumerate(chosen)}
        for j,v in enumerate(s):
            A[v]=(selected>=0 and selected<=j)
        for clause in extra:
            assert any(A[abs(l)]==(l>0) for l in clause),("witness_extension_bad",path,selected,clause)
    # The old original-source direct EO fact may disappear after rewrite;
    # do NOT require original direct EO counts to stay equal.
    rewritten_facts=derive(rewritten)
    check(rewritten,rewritten_facts)
    base_summary=fact_summary(f);new_summary=fact_summary(rewritten_facts)
    # A logically equivalent alternative encoding CAN remove visible XOR2
    # or pairwise AMO motifs; preserve those differences as evidence, not failure.
    # Two sign/rename variants of this semantically reencoded original:
    variant_validated=0
    for seed in (77001+idx*100,77002+idx*100):
        t_n,t_c=parse(rewritten)
        variant,eq,_=transform(t_n,t_c,seed,rename=True,flip=True,shuffle=True)
        assert eq
        vfacts=derive(variant)
        check(variant,vfacts)
        assert fact_summary(vfacts)["xor_counts"]==new_summary["xor_counts"]
        assert fact_summary(vfacts)["eo_count"]==new_summary["eo_count"]
        variant_validated+=1
    rewrite_rows.append({"source":path,"status":"PROJECTION_EQUIVALENT_BY_VERIFIED_LOCAL_ENCODING",
         "group_size":n,"old_vars":nv,"new_vars":new_nv,
         "old_clauses":len(source),"new_clauses":len(new_clauses),
         "source_sha256":hashlib.sha256(raw).hexdigest(),
         "rewritten_sha256":hashlib.sha256(rewritten).hexdigest(),
         "local_prefix_witnesses_checked":n+1,
         "local_pairwise_RUP_checks":pair_conflicts,
         "signed_permutation_retests":variant_validated,
         "direct_EO_before":base_summary["eo_count"],
         "direct_EO_after":new_summary["eo_count"],
         "XOR_count_before":base_summary["xor_counts"],
         "XOR_count_after":new_summary["xor_counts"]})
    # Only keep the rewritten CNF on two modest-sized originals to stay
    # within evidence size; all others can be regenerated deterministically.
    if len(rewritten)<350000:
        (OUT/(f"reencoded-{idx:02}.cnf")).write_bytes(rewritten)
    print("REENCODE "+json.dumps(rewrite_rows[-1],sort_keys=True),flush=True)

with (OUT/"source-variations.csv").open("w",newline="") as h:
    writer=csv.DictWriter(h,fieldnames=list(variant_rows[0]))
    writer.writeheader();writer.writerows(variant_rows)
(OUT/"original-profiles.json").write_text(json.dumps(original_rows,indent=2,sort_keys=True)+"\n")
(OUT/"reencoding-results.json").write_text(json.dumps(rewrite_rows,indent=2,sort_keys=True)+"\n")
summary={
 "status":"PASS","source_provenance":"14 unchanged original CNFs committed previously in DRNAS-SAT",
 "original_sources":len(original_rows),
 "distinct_repository_source_domains":len(set(x["family"] for x in original_rows)),
 "known_inverse_variant_trials":len(variant_rows),
 "source_motif_certificates_independently_checked":len(original_rows)+len(variant_rows),
 "signed_EO_count_preserved":sum(x["EO_count_original"]==x["EO_count_variant"] for x in variant_rows),
 "complete_XOR_counts_preserved":sum(x["XOR_by_width_original"]==x["XOR_by_width_variant"] for x in variant_rows),
 "coarse_invariant_preserved":sum(x["fingerprint_invariant"] for x in variant_rows),
 "tamper_source_missing_premise_rejected":mutated,
 "tamper_source_trials_applicable":mutated,
 "reencoded_original_sources_supported":sum(x["status"].startswith("PROJECTION_EQUIVALENT") for x in rewrite_rows),
 "reencoded_original_sources_unsupported":sum(x["status"].startswith("NO_EO") for x in rewrite_rows),
 "reencoded_signed_variant_rechecks":sum(x.get("signed_permutation_retests",0) for x in rewrite_rows),
 "local_semantics_small_truth_table_n":[2,3,4,5,6],
 "local_semantics_larger_checked_n":[7,9,12],
 "elapsed_s":round(time.perf_counter()-started_all,5),
 "certificate_type":"source-clause facts, not external UNSAT proof",
 "benchmark_status":"DEVELOPMENT_REGRESSION_NOT_FRESH_BLIND_NOT_CDCL_SPEED",
 "no_new_SAT_UNSAT":True,
 "scope_limits":["only original repo CNFs plus controlled variants",
      "source validity of selected facts, not completeness of detector",
      "Sinz rewrite projection equivalence follows from local encoder and retained clauses",
      "no claim to identify arbitrary equivalent unannotated CNF encodings",
      "no new result on real untouched SAT Competition 2025 cross-family inputs"]}
(OUT/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
print("ATLAS3_AUDIT_PASS "+json.dumps(summary,sort_keys=True),flush=True)
