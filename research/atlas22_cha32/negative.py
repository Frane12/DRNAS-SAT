#!/usr/bin/env python3
"""Adversarial ATLAS22 controls: modified original CNF, forged source SHA."""
import json,tempfile
from pathlib import Path
from audit import validate
SRC=Path("evidence/real6-original/results/chacha_qr/netlist.json")
BASE=Path("evidence/real61/chacha_qr/certificate.json")
PRIOR=Path("evidence/real632-prior/cha_candidate_paths.json")
PROPOSAL=Path("evidence/real632-complete/proposed.json")
VERIFIED=Path("evidence/real632-complete/independent.json")
ROOT=Path("atlas22_artifacts/cnf")
CASE="original_mismatch"

def reject(label,cnf,manifest):
    try:validate(SRC,BASE,PRIOR,PROPOSAL,VERIFIED,cnf,manifest)
    except (ValueError,AssertionError,KeyError,IndexError):
        print("ATLAS22_TAMPER_REJECTED",label,flush=True)
    else:raise AssertionError("UNSOUND_ATLAS22_ACCEPTANCE_"+label)

def main():
    with tempfile.TemporaryDirectory() as tmp:
        t=Path(tmp)
        cnf=ROOT/(CASE+".cnf")
        manifest=ROOT/(CASE+"_manifest.json")
        txt=cnf.read_text().splitlines()
        for i,s in enumerate(txt):
            if s.startswith(("p","c")) or not s.strip():continue
            lits=s.split()
            lits[0]=str(-int(lits[0]))
            txt[i]=" ".join(lits)
            break
        bad=t/"tampered.cnf"
        bad.write_text("\n".join(txt)+"\n")
        reject("MODIFIED_ORIGINAL_CNF_CLAUSE",bad,manifest)
        meta=json.loads(manifest.read_text())
        meta["source_gate_sha256"]="0"*64
        forged=t/"forged.json"
        forged.write_text(json.dumps(meta))
        reject("FORGED_ORIGINAL_SOURCE_SHA",cnf,forged)
        meta=json.loads(manifest.read_text())
        meta["actual_var_ids"][0]=meta["expected_var_ids"][0]
        forged.write_text(json.dumps(meta))
        reject("FORGED_CNF_SOURCE_OUTPUT_MAP",cnf,forged)
    print("ATLAS22_ALL_SOURCE_AND_CNF_NEGATIVE_CONTROLS_PASS",flush=True)
if __name__=="__main__":main()
