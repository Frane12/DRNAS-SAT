#!/usr/bin/env python3
"""ATLAS15 original-source proof transport: GRAPH/XOR -> HALL.

The original CNF is never replaced when verifying UNSAT:
1. Find source-supported GRAPH and/or XOR3+unit mutex transfer lemmas.
2. Have independent verifier independently re-derive them from raw source.
3. For HALL use an INTERNAL original+lemmas copy, with independent Hall
   source checker and existing cutting-plane emitter.
4. Lift PBP into original-CNF provenance by INSERTING externally checked
   RUP lines for each transferred lemma at precisely the source premise
   indices expected by internal Hall PBP. Only external VeriPB may accept.
No CDCL, external solver, or source filename/expected status is read here.
"""
import argparse,hashlib,json,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/"research/structure_atlas1"))
sys.path.insert(0,str(ROOT/"research/atlas13_exchange"))
sys.path.insert(0,str(ROOT/"research/pcmax_capacity"))
from atlas import encoded,parse
from facts import candidates,Unknown
from witness import verify as original_fact_check,Invalid
from check_php_partition import check as independent_hall_check
from emit_veripb_source_clique import emit as hall_emitter
import importlib.util
_oldpath=ROOT/"research/atlas13_exchange/bridge.py"
_oldspec=importlib.util.spec_from_file_location("drnas_atlas13_hall_provenance",_oldpath)
_oldmodule=importlib.util.module_from_spec(_oldspec)
_oldspec.loader.exec_module(_oldmodule)
hall_partition=_oldmodule.hall_partition
HallUnknown=_oldmodule.Unknown

def sha(raw):return hashlib.sha256(raw).hexdigest()

def compile_original(original_path,mode,claim_path,pbp_path,meta_path):
    started=time.perf_counter()
    source=Path(original_path)
    raw=source.read_bytes()
    source_nv,source_clauses=parse(raw)
    claims=candidates(raw,mode)
    checked=original_fact_check(raw,claims)
    if checked["status"]!="ATLAS15_ORIGINAL_SOURCE_LEMMAS_INDEPENDENTLY_VERIFIED":
        raise Unknown("INDEPENDENT_SOURCE_TRANSFER_REJECTED")
    facts=claims["facts"]
    if mode=="TRIPLE_HALL":
        # The real two-module exchange demonstration is required on k=5+
        # controls, while k=4 sanity may need only the XOR premise.
        pass
    if not facts:raise Unknown("NO_SOURCE_TRANSFER_FACTS")
    cert=hall_partition(raw,facts)
    # Source-only Hall returns UNKNOWN unless it has full, disjoint resource
    # partition whose every pair is original OR verified transferred lemma.
    augmented_raw=encoded(source_nv,source_clauses+
                          [(-fact["a"],-fact["b"]) for fact in facts])
    cert["source_sha256"]=sha(augmented_raw)
    with tempfile.TemporaryDirectory(prefix="drnas-atlas15-") as td:
        temporary=Path(td)
        qsource=temporary/"source-plus-proof-facts.cnf"
        qcert=temporary/"hall-source-fact-cert.json"
        qpbp=temporary/"hall-pbp-from-augmented.cnf.pbp"
        qsource.write_bytes(augmented_raw)
        qcert.write_text(json.dumps(cert,sort_keys=True)+"\n")
        hc=independent_hall_check(qsource,qcert)
        if hc["status"]!="UNSAT_SOURCE_CLIQUE_VERIFIED":
            raise Unknown("INDEPENDENT_HALL_SOURCE_CHECK_REJECT")
        pmeta=hall_emitter(qsource,qcert,qpbp)
        if pmeta["status"]!="EMITTED_UNCHECKED":
            raise Unknown("PROOF_EMITTER_UNKNOWN")
        old=qpbp.read_text().splitlines()
        need_header=f"f {len(source_clauses)+len(facts)} ;"
        if old[:2]!=["pseudo-Boolean proof version 3.0",need_header]:
            raise Unknown("AUGMENTED_PROOF_INDICES_INCONSISTENT")
        output=["pseudo-Boolean proof version 3.0",
                f"f {len(source_clauses)} ;"]
        for fact in facts:
            output.append(f"rup 1 ~x{fact['a']} 1 ~x{fact['b']} >= 1 ;")
        output.extend(old[2:])
        proof="\n".join(output)+"\n"
        if len(proof.encode())>3_000_000:raise Unknown("PROOF_LIMIT")
    claim_path=Path(claim_path);pbp_path=Path(pbp_path);meta_path=Path(meta_path)
    claim_path.parent.mkdir(exist_ok=True,parents=True)
    claim_path.write_text(json.dumps({**claims,
         "independent_source_provenance":checked,
         "auxiliary_HALL_source_sha256":sha(augmented_raw),
         "internal_independent_HALL_checker":hc["status"],
         "verification_notice":"Original-source standard VeriPB is mandatory; augmented internal CNF is NOT authority for original UNSAT"},
         sort_keys=True,indent=2)+"\n")
    pbp_path.write_text(proof)
    result={"status":"UNSAT_PROOF_EMITTED_EXTERNAL_VERIPB_REQUIRED",
      "original_sha256":sha(raw),"source_original_clauses":len(source_clauses),
      "transfer_mode":mode,
      "graph_lemmas_transferred":checked["graph_lemmas_verified"],
      "xor_lemmas_transferred":checked["xor3_unit_lemmas_verified"],
      "all_transferred_lemmas":len(facts),
      "source_original_ALO_groups":checked["original_ALO_groups"],
      "source_independent_fact_check":checked["status"],
      "hall_independent_check":hc["status"],
      "hall_required_groups":hc["required_groups"],
      "hall_capacity_cliques":hc["capacity_resources"],
      "hall_deficit":hc["deficit"],
      "original_source_PBP_sha256":sha(proof.encode()),
      "original_source_PBP_bytes":len(proof.encode()),
      "proof_emission_wall_s":round(time.perf_counter()-started,6),
      "external_original_veripb_mandatory":True}
    meta_path.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("ATLAS15_FACT_TRANSPORT "+json.dumps(result,sort_keys=True),flush=True)
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cnf",required=True,type=Path)
    p.add_argument("--mode",required=True,choices=("GRAPH_HALL","XOR_HALL","TRIPLE_HALL"))
    p.add_argument("--claims",required=True,type=Path)
    p.add_argument("--proof",required=True,type=Path)
    p.add_argument("--meta",required=True,type=Path)
    a=p.parse_args()
    try:
        compile_original(a.cnf,a.mode,a.claims,a.proof,a.meta)
    except (Unknown,HallUnknown,Invalid,ValueError,TypeError,IndexError,
            KeyError,OSError,OverflowError,MemoryError) as e:
        a.proof.unlink(missing_ok=True)
        a.claims.unlink(missing_ok=True)
        a.meta.unlink(missing_ok=True)
        print("ATLAS15_SAFE_UNKNOWN "+str(e)[:420],flush=True)
        raise SystemExit(2)
if __name__=="__main__":main()
