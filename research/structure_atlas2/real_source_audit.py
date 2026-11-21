#!/usr/bin/env python3
"""ATLAS2: source-only fact co-occurrence + separately preserved domain taxonomy.

Reads 5 *original* DIMACS files in repository. Labels and SAT family metadata
are used only AFTER source-only probing for reporting. Previously frozen GBD
2025 manifest is indexed as metadata-only; no claim to have downloaded or
scanned its original bytes in this run.

A source fact's presence is NOT a proof of SAT/UNSAT, nor evidence that two
modules can derive a contradiction. The interoperability table records
eligible proof interfaces only, not solved instances.
"""
import csv,hashlib,json,os,statistics,subprocess,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/"research"/"structure_atlas1"))
from atlas import scan,parse,transform
OUT=ROOT/"structure_atlas2_audit";OUT.mkdir(exist_ok=True)
REG=json.loads((HERE/"domain_registry.json").read_text())
GBD=json.loads((ROOT/"research/graph_family_disjoint25/prespec.json").read_text())
assert REG["format"]=="DRNAS-ATLAS2-DOMAIN-CATALOG-v1"
expected={
 "evidence/graph-k11/original.cnf",
 "evidence/ipg7b-petersen/original.cnf",
 "evidence/xor234-grid5/original.cnf",
 "evidence/pcmax-weighted2/05/original.cnf",
 "evidence/pcmax-weighted2/15/original.cnf"}
records=[]
def paths(entry):
    return ([entry["source_path"]] if "source_path" in entry else
            entry.get("source_paths",[]))
paths_seen={p for e in REG["entries"] for p in paths(e)}
assert paths_seen==expected,(paths_seen,expected)
assert len(GBD["records"])==10
known_families={e.get("gbd_family") for e in REG["entries"] if e.get("gbd_family")}
assert known_families=={e["family"] for e in GBD["records"]}

# A report row below is labeled with provenance only AFTER the blind-to-label
# source scanner runs. It does not classify source semantic domain.
for entry in REG["entries"]:
    for p in paths(entry):
        raw=(ROOT/p).read_bytes()
        start=time.perf_counter()
        profile=scan(raw)
        secs=time.perf_counter()-start
        m=profile["motifs"]
        def present(x):return m.get(x,0)>0
        fact_modules=[]
        if present("positive_ALO_candidates"):fact_modules.append("ALO_CANDIDATES")
        if present("source_supported_exact_one_groups"):fact_modules.append("SOURCE_EXACT_ONE")
        if present("source_XOR3_table_candidates"):fact_modules.append("SOURCE_XOR3")
        if present("source_XOR4_table_candidates"):fact_modules.append("SOURCE_XOR4")
        # ENCOURAGE proof exchanges only if independently source-derived facts
        # coexist: not merely because catalog predicts a module.
        exchanges=[]
        if present("source_supported_exact_one_groups") and (
                present("source_XOR3_table_candidates") or present("source_XOR4_table_candidates")):
            exchanges.append("EO_to_XOR_THEORY_CANDIDATE_REQUIRES_SOURCE_PROOF")
        # GRAPH, HALL and BDD capabilities are not proven by this shallow scan.
        unsupported=["HALL_SUBSET_CAPACITY_NOT_CHECKED","GRAPH_CLIQUE_NOT_CHECKED",
                     "BDD_LAYOUT_NOT_CHECKED"]
        records.append({"domain_key":entry["key"],"source_path":p,
            "source_sha256":profile["raw_source_sha256"],
            "variable_count":profile["variable_count"],
            "clause_count":profile["clause_count"],
            "coarse_fingerprint":profile["coarse_invariant_sha256"],
            "motifs":m,"source_fact_modules":fact_modules,
            "possible_fact_exchanges":exchanges,"not_yet_checked":unsupported,
            "scan_seconds":round(secs,6),
            "source_verdict":"FACT_CENSUS_NO_SAT_VERDICT",
            "family_complexity_label_from_registry_only":entry["complexity"]})
        print("REAL_CNF "+json.dumps({
            "path":p,"vars":profile["variable_count"],"clauses":profile["clause_count"],
            "facts":fact_modules,"candidate_exchanges":exchanges,
            "sha256":profile["raw_source_sha256"]},sort_keys=True),flush=True)

# Signed-variant tests, constructed only by bijective renaming/negation and
# independently exact inverse clause multiset audit. Semantic EO via source
# RUP checks may be unsupported and must be reported as such.
cases=[("evidence/ipg7b-petersen/original.cnf",61021),
       ("evidence/xor234-grid5/original.cnf",61022)]
variant_records=[]
from semantic_eo import recover
for path,seed in cases:
    raw=(ROOT/path).read_bytes();nv,clauses=parse(raw)
    changed,eq,t=transform(nv,clauses,seed,rename=True,flip=True,shuffle=True)
    assert eq
    assert scan(raw)["coarse_invariant_sha256"]==scan(changed)["coarse_invariant_sha256"]
    started=time.perf_counter()
    before=recover(raw,max_candidates=1200,max_pairs=4000)
    after=recover(changed,max_candidates=1200,max_pairs=4000)
    elapsed=time.perf_counter()-started
    res={"source_path":path,"source_sha256":hashlib.sha256(raw).hexdigest(),
         "variant_sha256":hashlib.sha256(changed).hexdigest(),
         "known_transform_inverse_equivalent":eq,
         "semantic_before":before["status"],"semantic_after":after["status"],
         "eo_groups_before":len(before["source_supported_exactly_one"]),
         "eo_groups_after":len(after["source_supported_exactly_one"]),
         "run_seconds":round(elapsed,6),
         "no_sat_verdict":True}
    variant_records.append(res)
    print("ORIGINAL_POLARITY_VARIANT "+json.dumps(res,sort_keys=True),flush=True)

gbd_manifest=[]
for x in GBD["records"]:
    tax=next(e for e in REG["entries"] if e.get("gbd_family")==x["family"])
    gbd_manifest.append({"gbd_family":x["family"],"gbd_hash":x["gbd_hash"],
        "isohash":x["isohash"],"original_filename_from_catalog":x["filename"],
        "formal_problem":tax["formal_decision"],
        "complexity_is_originating_problem_not_decoded_cnf":tax["complexity"],
        "candidate_modules_by_domain_not_validated":tax["module_candidates"],
        "source_probe_status":"NOT_SCANNED_ORIGINAL_CNF_BYTES_UNAVAILABLE_IN_THIS_ATLAS2_RUN"})
# guard against accidentally implying these public instances are original-source scanned.
assert all("NOT_SCANNED" in x["source_probe_status"] for x in gbd_manifest)
(OUT/"gbd-2025-index-only.json").write_text(json.dumps(gbd_manifest,sort_keys=True,indent=2)+"\n")
(OUT/"real-original-source-profiles.json").write_text(json.dumps(records,sort_keys=True,indent=2)+"\n")
(OUT/"signed-variant-source-facts.json").write_text(json.dumps(variant_records,sort_keys=True,indent=2)+"\n")
with (OUT/"source-fact-matrix.csv").open("w",newline="") as f:
    fields=["domain_key","source_path","source_sha256","variable_count","clause_count",
            "source_fact_modules","possible_fact_exchanges","scan_seconds","source_verdict"]
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    for row in records:w.writerow({k:json.dumps(row[k],ensure_ascii=False)
                                  if isinstance(row[k],list) else row[k] for k in fields})
summary={"status":"PASS","original_repo_cnfs_scanned":len(records),
         "original_sources_exact_sha256":{r["source_path"]:r["source_sha256"] for r in records},
         "source_covered_domains":len({r["domain_key"] for r in records}),
         "formal_domain_taxonomy_entries":len(REG["entries"]),
         "gbd_2025_source_metadata_rows_not_scanned":len(gbd_manifest),
         "gbd_2025_distinct_catalog_families":len(known_families),
         "source_exact_one_cooccurs_xor_count":sum(bool(r["possible_fact_exchanges"]) for r in records),
         "signed_original_variants_exact_inverse_equivalent":sum(x["known_transform_inverse_equivalent"] for x in variant_records),
         "signed_variants":variant_records,
         "false_solver_claims":0,
         "scope":"source-only fact census and real-world class index; no newly solved SAT or standard proof",
         "not_proven":["domain labels cannot be inferred uniquely from DIMACS",
                       "no new standard VeriPB/DRAT proof in this census",
                       "cooccurring source facts do not imply an UNSAT solution",
                       "cross-encoding semantics of real originals remain open",
                       "GBD catalog rows not scanned here"]}
(OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
print("ATLAS2_FINAL "+json.dumps({k:v for k,v in summary.items() if k not in ("original_sources_exact_sha256","signed_variants")},sort_keys=True),flush=True)
