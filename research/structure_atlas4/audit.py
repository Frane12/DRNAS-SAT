#!/usr/bin/env python3
"""ATLAS4 genuine original-CNF seven-family source-first evaluation.

Every frozen source is accounted for, including resource-gated UNKNOWNs.
Probe never receives family labels. Two fixed bijective variants per eligible
original are compared against same-CNF source facts. Strict SAT/UNSAT credit
only from external standard proofs, never inference from a fact-only record.
"""
import collections,hashlib,json,os,pathlib,subprocess,sys,time,statistics
ROOT=pathlib.Path(__file__).resolve().parents[2]
HERE=pathlib.Path(__file__).resolve().parent
INPUT=ROOT/"atlas4_real10"
OUT=ROOT/"atlas4_results"
OUT.mkdir(exist_ok=True)
MAN=json.loads((INPUT/"manifest.json").read_text())
PRE=json.loads((ROOT/"research/graph_family_disjoint25/prespec.json").read_text())
HIST=json.loads((ROOT/"evidence/ci/graph-disjoint10.json").read_text())
assert MAN["status"]=="FROZEN_ALL_10_EXISTING_ORIGINALS"
assert len(MAN["sources"])==len(PRE["records"])==len(HIST["provenance"])==10
MAX_STRICT_PROBE_BYTES=23_000_000
MAX_STRICT_PROBE_CLAUSES=300_000
MAX_STRICT_PROBE_VARS=600_000
CAP_S=22
CPU=min(os.sched_getaffinity(0))
os.sched_setaffinity(0,{CPU})

def sha(file):return hashlib.sha256(file.read_bytes()).hexdigest()

def run(label,args,timeout=CAP_S,ok=(0,)):
    began=time.perf_counter()
    try:
        r=subprocess.run(["taskset","-c",str(CPU)]+list(map(str,args)),
          text=True,capture_output=True,timeout=timeout)
        status=("RETURNED" if r.returncode in ok else "UNSUPPORTED_OR_ERROR_RC_"+str(r.returncode))
        (OUT/(label+".log")).write_text(
            f"exit={r.returncode}\nwall_s={time.perf_counter()-began:.6f}\n"+
            r.stdout[-20000:]+"\n"+r.stderr[-6000:])
        return {"status":status,"rc":r.returncode,"elapsed_s":time.perf_counter()-began,
                "stdout":r.stdout,"stderr":r.stderr}
    except subprocess.TimeoutExpired as e:
        (OUT/(label+".log")).write_text("TIMEOUT_"+str(timeout))
        return {"status":"UNKNOWN_TIMEOUT","elapsed_s":time.perf_counter()-began}

def sketch(file):
    """Source-only streaming clause-width census; no family label or status."""
    hist=collections.Counter();maxw=0;current=0
    pos=neg=0;numclause=0
    with file.open("rb") as f:
        for line in f:
            if not line.strip() or line.lstrip().startswith((b"c ",b"p ")):continue
            for word in line.split():
                x=int(word)
                if x==0:
                    hist[current]+=1;numclause+=1;maxw=max(maxw,current);current=0
                else:
                    current+=1
                    if x>0:pos+=1
                    else:neg+=1
    assert current==0
    return {"clause_count":numclause,
            "width_histogram":{str(k):v for k,v in sorted(hist.items())},
            "max_clause_width":maxw,"positive_literals":pos,"negative_literals":neg}

rows=[]
for s in sorted(MAN["sources"],key=lambda v:v["id"]):
    i=s["id"];fn=ROOT/s["path"]
    old=HIST["provenance"][i]
    assert old["gbd_hash"]==s["gbd_hash"] and old["source_sha256"]==s["original_source_sha256"]
    assert sha(fn)==s["original_source_sha256"]
    start=time.perf_counter()
    basic=sketch(fn)
    assert basic["clause_count"]==s["clauses"]
    eligible=(s["source_bytes"]<=MAX_STRICT_PROBE_BYTES and
              s["clauses"]<=MAX_STRICT_PROBE_CLAUSES and
              s["variables"]<=MAX_STRICT_PROBE_VARS)
    entry={"id":i,"family_for_report_only":s["family"],
      "gbd_hash":s["gbd_hash"],"original_sha256":s["original_source_sha256"],
      "source_bytes":s["source_bytes"],"variables":s["variables"],
      "clauses":s["clauses"],"basic_source_sketch":basic,
      "not_new_blind":True,"fact_probe":"UNKNOWN_RESOURCE_GATE" if not eligible else "NOT_RUN",
      "variant_probes":[],"candidate_exchanges":0,
      "graph_strict_proof":"NOT_ATTEMPTED","hall_source_cert":"NOT_ATTEMPTED"}
    if eligible:
        probe=OUT/(f"id{i:02}.facts.json")
        res=run(f"id{i:02}-source-facts",[sys.executable,HERE/"probe_one.py",fn,"--output",probe],20)
        if res["status"]=="RETURNED" and probe.exists():
            fact=json.loads(probe.read_text())
            assert fact["input_sha256"]==s["original_source_sha256"]
            assert fact["independent_checker"]=="SOURCE_FACTS_INDEPENDENTLY_VERIFIED"
            entry["fact_probe"]="SOURCE_FACTS_VERIFIED"
            entry["eo_facts"]=fact["module_EO_facts"]
            entry["xor_facts"]=fact["module_XOR_facts"]
            entry["candidate_exchanges"]=fact["module_exchange_candidates_EO_XOR"]
            for variant in (1,2):
                out=OUT/(f"id{i:02}.variant{variant}.json")
                q=run(f"id{i:02}-variant{variant}",[sys.executable,
                  HERE/"probe_one.py",fn,"--output",out,
                  "--variant",variant],20)
                if q["status"]=="RETURNED" and out.exists():
                    f2=json.loads(out.read_text())
                    assert f2["inverse_clause_multiset_equivalent"] is True
                    assert f2["independent_checker"]=="SOURCE_FACTS_INDEPENDENTLY_VERIFIED"
                    assert f2["module_EO_facts"]==fact["module_EO_facts"]
                    assert f2["module_XOR_facts"]==fact["module_XOR_facts"]
                    entry["variant_probes"].append({"variant":variant,"status":"PASS",
                          "source_sha256":f2["current_source_sha256"]})
                else:
                    entry["variant_probes"].append({"variant":variant,"status":"UNKNOWN_RESOURCE_OR_TIME"})
            # Source-level graph proof first, then FULL external VeriPB only
            # after an emitter produces a proof. All verdicts on original bytes.
            pb=OUT/(f"id{i:02}.graph.pbp")
            meta=OUT/(f"id{i:02}.graph.meta.json")
            graph=run(f"id{i:02}-graph-only",[sys.executable,
              ROOT/"research/graphclique/emit_veripb.py",
              "--cnf",fn,"--pbp",pb,"--meta",meta,
              "--max-search-nodes","2000"],5,ok=(0,2))
            if graph.get("rc")==0 and pb.exists():
                ver=run(f"id{i:02}-graph-VeriPB",
                  ["veripb","--cnf",fn,pb],8)
                if ver.get("rc")==0 and "s VERIFIED UNSATISFIABLE" in ver.get("stdout",""):
                    entry["graph_strict_proof"]="STANDARD_VERIPB_VERIFIED_UNSAT"
                    entry["graph_proof_sha256"]=sha(pb)
                else:entry["graph_strict_proof"]="PROOF_NOT_EXTERNALLY_VERIFIED"
            else:
                entry["graph_strict_proof"]="UNKNOWN_NO_COMPLETE_GRAPH_PROOF"
            pb.unlink(missing_ok=True)
            # Hall via source-only capacity as a separated, NONSTANDARD track.
            if s["source_bytes"]<=6_000_000 and s["clauses"]<=100_000:
                cert=OUT/(f"id{i:02}.hall.json")
                h=run(f"id{i:02}-hall",[sys.executable,
                     ROOT/"research/match3_flow_hall.py",fn,
                     "--certificate",cert],4)
                if h.get("rc")==0 and cert.exists():
                    j=json.loads(cert.read_text())
                    if j.get("status")=="UNSAT_UNCHECKED":
                        v=run(f"id{i:02}-hall-source-check",[sys.executable,
                            ROOT/"research/match3_flow_hall_checker.py",fn,cert],5)
                        entry["hall_source_cert"]=("CUSTOM_SOURCE_CERTIFICATE_VERIFIED_NOT_VERIPB"
                                                  if v.get("rc")==0 else "INVALID_CUSTOM_CERT")
                    else:entry["hall_source_cert"]="UNKNOWN"
                else:entry["hall_source_cert"]="UNKNOWN_RESOURCE_OR_ERROR"
            else:entry["hall_source_cert"]="UNKNOWN_RESOURCE_GATE"
        else:
            entry["fact_probe"]=("UNKNOWN_RESOURCE_OR_TIMEOUT" if res["status"]=="UNKNOWN_TIMEOUT"
                                  else "UNKNOWN_PROBE_ERROR")
    entry["elapsed_total_s"]=round(time.perf_counter()-start,6)
    rows.append(entry)
    print("ATLAS4_SOURCE "+json.dumps({
      "id":i,"bytes":entry["source_bytes"],"clauses":entry["clauses"],
      "facts":entry["fact_probe"],"variants":entry["variant_probes"],
      "EO_XOR_candidates":entry["candidate_exchanges"],
      "graph_standard":entry["graph_strict_proof"],
      "hall_custom":entry["hall_source_cert"]},sort_keys=True),flush=True)

# Tampered source-bound fact messages must be independently rejected.
# Test a bounded selection; an invalid premise NEVER earns success.
sys.path.insert(0,str(ROOT/"research/structure_atlas1"))
sys.path.insert(0,str(ROOT/"research/structure_atlas3"))
from source_facts import derive
from check_facts import check,Invalid
verified_ids=[r for r in rows if r["fact_probe"]=="SOURCE_FACTS_VERIFIED"]
tamper_rejected=0
for rec in verified_ids[:2]:
    raw=(ROOT/MAN["sources"][rec["id"]]["path"]).read_bytes()
    claim=derive(raw)
    claim["source_sha256"]="0"*64
    try:
        check(raw,claim)
    except Invalid:
        tamper_rejected+=1
    else:
        raise AssertionError("SOURCE_HASH_FORGERY_NOT_REJECTED")
# Record precommitted source selections and labels separately from detector.
(OUT/"trial_records.json").write_text(json.dumps(rows,indent=2,sort_keys=True)+"\n")
summary={
 "status":"COMPLETE_FACT_CENSUS",
 "original_sources":len(rows),
 "different_catalog_families":len({r["family_for_report_only"] for r in rows}),
 "eligible_source_fact_probes":sum(r["fact_probe"]=="SOURCE_FACTS_VERIFIED" for r in rows),
 "unknown_or_resource_sources":sum(r["fact_probe"]!="SOURCE_FACTS_VERIFIED" for r in rows),
 "source_hash_forgeries_rejected":tamper_rejected,
 "known_bijection_variant_passes":sum(x["status"]=="PASS" for r in rows for x in r["variant_probes"]),
 "known_bijection_variant_unknown":sum(x["status"]!="PASS" for r in rows for x in r["variant_probes"]),
 "eo_xor_overlap_candidates_only":sum(r["candidate_exchanges"] for r in rows),
 "graph_standard_verified_unsat":sum(r["graph_strict_proof"]=="STANDARD_VERIPB_VERIFIED_UNSAT" for r in rows),
 "hall_custom_verified_not_strict":sum(r["hall_source_cert"]=="CUSTOM_SOURCE_CERTIFICATE_VERIFIED_NOT_VERIPB" for r in rows),
 "proof_system_note":"Only external VeriPB on exact original can count as strict UNSAT",
 "no_claim_of_joint_solver_new_solution":True,
 "cohort_scope":"Previously selected and previously evaluated 10 GBD 2025 originals; 7 source-disjoint families relative to older 77 set, NOT newly blind today",
 "limits":["Some inputs resource-gated and counted UNKNOWN",
           "Overlapping math facts alone do not prove UNSAT",
           "Any failed/unknown proof cannot earn strict credit",
           "No final speed comparison to Kissat in this source-first exploratory audit"]
}
assert summary["original_sources"]==10
assert summary["different_catalog_families"]==7
(OUT/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
print("ATLAS4_AUDIT_COMPLETE "+json.dumps(summary,sort_keys=True),flush=True)
