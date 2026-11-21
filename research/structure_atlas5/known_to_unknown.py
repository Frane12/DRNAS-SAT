#!/usr/bin/env python3
"""ATLAS5: proof-carrying rule chain from known structural facts to GF(2) UNSAT.

Fact producer: source_facts.derive on original CNF -> external independent
check_facts.check. Reusable known theorem: Gaussian elimination of full
source XOR equations over GF(2), carrying exact source-row indices.
Proof bridge: check_math5.verify and xorlin1/emit_veripb.py; final authority
is *external standard VeriPB on the EXACT original/variant CNF*.

This is retrospective: previously frozen ten SAT Competition 2025 originals,
and ID6 Tseitin has a documented prior standard proof. No general SAT claim,
and no new solution claims for formulas previously proved by other branches.
"""
from __future__ import annotations
import hashlib,itertools,json,os,sys,time,subprocess,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"atlas5_results"
OUT.mkdir(exist_ok=True,parents=True)
sys.path.insert(0,str(ROOT/"research/structure_atlas1"))
sys.path.insert(0,str(ROOT/"research/structure_atlas3"))
sys.path.insert(0,str(ROOT/"research/xorlin1"))
sys.path.insert(0,str(ROOT/"research/math5"))
from atlas import parse,encoded,transform
from source_facts import derive as source_derive
from check_facts import check as source_check, Invalid
from extract import gaussian
from check_math5 import verify as xor_certificate_check
CPU=min(os.sched_getaffinity(0))
os.sched_setaffinity(0,{CPU})
LIMITS={"bytes":12_000_000,"variables":6000,"clauses":100_000,
        "xor_rows":1500,"pbp_bytes":8_000_000}
MAN=json.loads((ROOT/"atlas4_real10/manifest.json").read_text())
HIST=json.loads((ROOT/"evidence/ci/graph-disjoint10.json").read_text())
PROOF=ROOT/"research/xorlin1/emit_veripb.py"

def sha(raw):return hashlib.sha256(raw).hexdigest()
def run(args,limit=30):
    start=time.perf_counter()
    try:
        r=subprocess.run(["taskset","-c",str(CPU)]+list(map(str,args)),
            capture_output=True,text=True,timeout=limit)
        return {"rc":r.returncode,"stdout":r.stdout,"stderr":r.stderr,
                "wall_s":round(time.perf_counter()-start,6),"timeout":False}
    except subprocess.TimeoutExpired as e:
        return {"rc":None,"stdout":"","stderr":"","wall_s":round(time.perf_counter()-start,6),
                "timeout":True}
def report_stage(f,name,rec):
    (OUT/(name+".json")).write_text(json.dumps(rec,sort_keys=True,indent=2)+"\n")

def check_one(raw,full_path,tag,source_expected):
    start=time.perf_counter()
    row={"tag":tag,"input_sha256":sha(raw),"original_sha256":source_expected,
         "status":"UNKNOWN","strict_unsat_verified":False,
         "source_fact_count":0,"selected_xor_rows":0,"verified_source_facts":False,
         "verify_kind":"NONE","proof_sha256":None}
    # No filename/family metadata enters detector. Only source bytes.
    if len(raw)>LIMITS["bytes"]:
        row["reason"]="BYTES_POLICY";return row
    try:
        nv,cls=parse(raw)
        if nv>LIMITS["variables"] or len(cls)>LIMITS["clauses"]:
            row["reason"]="CNF_HEADER_POLICY";return row
        source=source_derive(raw)
        counted=source_check(raw,source)
        if counted["status"]!="SOURCE_FACTS_INDEPENDENTLY_VERIFIED":
            raise AssertionError("SOURCE_FACT_CHECK_NOT_VERIFIED")
        row["verified_source_facts"]=True
        row["source_fact_count"]=len(source["exact_one_groups"])+len(source["complete_xor_rows"])
        xorrows=source["complete_xor_rows"]
        row["xor_rows_detected"]=len(xorrows)
        if len(xorrows)>LIMITS["xor_rows"]:
            row["reason"]="XOR_ROWS_POLICY";return row
        if not xorrows:
            row["reason"]="NO_COMPLETE_SOURCE_XOR_ROWS";return row
        # Distinct module: GF(2) selector receives only source-checked facts,
        # not raw source, status or family labels.
        rows=[{"vars":x["vars"],"forbidden_parity":1-x["rhs"]} for x in xorrows]
        indices=gaussian(rows)
        if indices is None:
            row["reason"]="NO_SOURCE_GF2_CONTRADICTION";return row
        selected=[rows[i] for i in indices]
        row["selected_xor_rows"]=len(selected)
        certificate={
            "format":"drnas-math5-eo-xor-unit-v1",
            "source_sha256":sha(raw),
            "xor_rows":selected,"exact_one_groups":[],"root_units":[]
        }
        # Independent checker reads exact original and selected theorem premises.
        evidence=xor_certificate_check(raw,certificate)
        if evidence["status"]!="UNSAT_MATH5_CERTIFICATE_VERIFIED":
            raise AssertionError("INVALID_GF2_CONTRADICTION_SOURCE")
        row["source_theorem_verified"]=True
        certpath=OUT/(tag+".xor-source-certificate.json")
        certpath.write_text(json.dumps(certificate,indent=2,sort_keys=True)+"\n")
        pbpath=OUT/(tag+".pbp")
        metapath=OUT/(tag+".pbmeta.json")
        emitted=run([sys.executable,PROOF,"--cnf",full_path,
            "--certificate",certpath,"--output",pbpath,"--meta",metapath],limit=40)
        row["proof_emitter_wall_s"]=emitted["wall_s"]
        if emitted["timeout"] or emitted["rc"]==2:
            row["reason"]="EMITTER_BUDGET_OR_UNSUPPORTED";return row
        if emitted["rc"]!=0 or not pbpath.exists() or not metapath.exists():
            row["status"]="CRITICAL_BAD_PROOF_EMITTER"
            row["reason"]=(emitted["stderr"]+emitted["stdout"])[-450:]
            return row
        meta=json.loads(metapath.read_text())
        if meta.get("source_sha256")!=sha(raw):
            row["status"]="CRITICAL_PROOF_SHA_MISMATCH";return row
        if pbpath.stat().st_size>LIMITS["pbp_bytes"]:
            row["reason"]="PROOF_BYTE_BUDGET";return row
        result=run(["veripb","--cnf",full_path,pbpath],limit=40)
        row["veripb_wall_s"]=result["wall_s"]
        if result["timeout"]:
            row["reason"]="VERIPB_CHECKER_TIMEOUT";return row
        if result["rc"]!=0 or "s VERIFIED UNSATISFIABLE" not in result["stdout"]+result["stderr"]:
            row["status"]="CRITICAL_EXTERNAL_PROOF_REJECTED"
            row["reason"]=(result["stderr"]+result["stdout"])[-450:];return row
        row["status"]="STANDARD_VERIPB_VERIFIED_UNSAT"
        row["strict_unsat_verified"]=True
        row["verify_kind"]="VERIPB_RED_RUP_CP"
        row["proof_bytes"]=pbpath.stat().st_size
        row["proof_sha256"]=sha(pbpath.read_bytes())
        return row
    except (ValueError,TypeError,KeyError,IndexError,OverflowError,
            UnicodeError,MemoryError,RecursionError) as error:
        row["reason"]="SOURCE_UNSUPPORTED_"+str(error)[:180]
        return row
    finally:
        row["e2e_s"]=round(time.perf_counter()-start,6)

def main():
    assert MAN["status"]=="FROZEN_ALL_10_EXISTING_ORIGINALS"
    assert len(MAN["sources"])==10 and len(HIST["provenance"])==10
    results=[]
    for item in sorted(MAN["sources"],key=lambda x:x["id"]):
        idx=item["id"]
        old=HIST["provenance"][idx]
        assert item["gbd_hash"]==old["gbd_hash"]
        path=ROOT/item["path"]
        raw=path.read_bytes()
        assert sha(raw)==item["original_source_sha256"]==old["source_sha256"]
        # Original source; only metadata added AFTER detector and proof.
        result=check_one(raw,path,f"id{idx:02d}-orig",item["original_source_sha256"])
        result["id"]=idx
        result["family_for_reporting_only"]=item["family"]
        result["bytes"]=len(raw)
        results.append(result)
        print("ATLAS5_ORIGINAL "+json.dumps(result,sort_keys=True),flush=True)
        report_stage(OUT,f"id{idx:02d}-result",result)
        # Freeze first original result before beginning the variant replays.
    pilot=next(x for x in results if x["id"]==6)
    if pilot["strict_unsat_verified"]:
        # Exact original ID6 is a previously documented 2026-11-17 solution;
        # transforming its CNF demonstrates robustness, NOT fresh novelty.
        original=next(x for x in MAN["sources"] if x["id"]==6)
        raw=(ROOT/original["path"]).read_bytes()
        n,c=parse(raw)
        for seed in (101,202,303):
            changed,eq,method=transform(n,c,seed,rename=True,flip=(seed!=101),shuffle=True)
            assert eq
            variant=OUT/(f"id06-var{seed}.cnf")
            variant.write_bytes(changed)
            attempt=check_one(changed,variant,f"id06-var{seed}",original["original_source_sha256"])
            attempt.update({"id":6,"known_equivalence_from_inverse_clause_map":eq,
                            "variant_seed":seed,"family_for_reporting_only":"tseitin-formulas"})
            results.append(attempt)
            print("ATLAS5_REPLAY "+json.dumps(attempt,sort_keys=True),flush=True)
            report_stage(OUT,f"id06-variant-{seed}-result",attempt)
    # Original safe control: if a source premise from a selected XOR table
    # is absent (and the claimed SHA is UPDATED), the independent checker
    # must reject that purported fact. This is not a SAT proof.
    tamper_checks=0
    if pilot["strict_unsat_verified"]:
        raw=(ROOT/next(x["path"] for x in MAN["sources"] if x["id"]==6)).read_bytes()
        fact=source_derive(raw)
        row=fact["complete_xor_rows"][0]
        vars=row["vars"];rhs=row["rhs"]
        bits=next(bits for bits in itertools.product((0,1),repeat=len(vars))
                  if sum(bits)%2!=rhs)
        clause=frozenset(-v if bit else v for v,bit in zip(vars,bits))
        n,cs=parse(raw)
        tampered=encoded(n,[c for c in cs if frozenset(c)!=clause])
        assert tampered!=raw
        fact["source_sha256"]=sha(tampered)
        fact["source_clauses"]=len(parse(tampered)[1])
        try:source_check(tampered,fact)
        except Invalid:tamper_checks+=1
        else:raise AssertionError("TAMPER_CLAUSE_NOT_REJECTED")
        print("ATLAS5_TAMPER_SOURCE_PREMISE_REJECTED",flush=True)
    all_orig=[x for x in results if "variant_seed" not in x]
    replays=[x for x in results if "variant_seed" in x]
    summary={
      "status":"COMPLETE",
      "originals":len(all_orig),"catalog_families":len({r["family_for_reporting_only"] for r in all_orig}),
      "source_fact_checks_pass":sum(r["verified_source_facts"] for r in all_orig),
      "standard_veripb_original_proofs":sum(r["strict_unsat_verified"] for r in all_orig),
      "original_verified_ids":[r["id"] for r in all_orig if r["strict_unsat_verified"]],
      "unknown_originals":sum(not r["strict_unsat_verified"] for r in all_orig),
      "permuted_known_formula_replays":len(replays),
      "permuted_standard_verified":sum(r["strict_unsat_verified"] for r in replays),
      "source_premise_tamper_rejections":tamper_checks,
      "critical":[{"id":r["id"],"status":r["status"],"reason":r.get("reason")}
           for r in results if r["status"].startswith("CRITICAL")],
      "fact_modules":"ATLAS3 source XOR fact producer + independent clause checker -> GF2 Gaussian source-row selector -> independent MATH5 checker -> standard VeriPB",
      "scope":"RETROSPECTIVE original CNFs previously evaluated, not new blind sample",
      "known_prior_ID6_proof":"research/MATH5_XOR3_CARRY_VERIPB_RESULTS.md, 2026-11-17",
      "unknown_does_not_mean_sat":True,
      "newly_solved_unseen_families_claimed":0
    }
    (OUT/"summary.json").write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n")
    print("ATLAS5_FINAL "+json.dumps(summary,sort_keys=True),flush=True)
    assert len(all_orig)==10 and not summary["critical"]
    assert tamper_checks==int(bool(pilot["strict_unsat_verified"]))

if __name__=="__main__":
    main()
