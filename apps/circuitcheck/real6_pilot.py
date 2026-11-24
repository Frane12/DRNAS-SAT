#!/usr/bin/env python3
"""REAL6 retrospective original FPGA hardware gate-corpus audit (NOT BLIND).

Five original frozen REAL5-Q ANF certificates are replayed without changing
netlists; all reported motif matches are independently checked with complete
8-assignment Boolean truth tables. No new RTL synthesis or solver runs here;
the original local Kissat and CaDiCaL controls are linked separately.
A zero motif count is a legitimate negative outcome.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from real6_motifs import generate
from real6_verify import verify

CASES=("aes_sbox","uart_tx","axis_fifo","picorv32","sha256_w_mem")
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    known=json.loads((a.source/"pilot.json").read_text())
    if set(known["cases"])!=set(CASES):
        raise RuntimeError("ORIGINAL_REAL5Q_FIVE_CASES_MISSING")
    all_cases={}
    for name in CASES:
        folder=a.source/name
        base=json.loads((folder/"real5q_certificate.json").read_text())
        if base["netlist_sha256"]!=sha(folder/"netlist.json"):
            raise RuntimeError("ORIGINAL_GATE_NETLIST_SHA_MISMATCH "+name)
        if (known["cases"][name]["original_gate_sha256"]!=base["netlist_sha256"]):
            raise RuntimeError("ORIGINAL_DEV_CORPUS_NETLIST_PIN_CHANGED")
        result=generate(folder)
        path=a.out/(name+"_real6.json")
        path.write_text(json.dumps(result,indent=2)+"\n")
        replay=verify(folder,path)
        assert replay["status"]=="CHECKED_REAL6_MOTIF_TRUTH_TABLES"
        all_cases[name]={
            "original_netlist_sha256":base["netlist_sha256"],
            "status":result["status"],"motif_counts":result["counts"],
            "independent_truth_table_checker":replay["status"],
            "CH_MAJ_SUM_samples":result["motifs"][:20],
            "full_adder_pair_examples":result["full_adder_pairs"][:12]
        }
        print("REAL6_REAL_HW",name,result["status"],result["counts"],flush=True)
    summary={"protocol":"REAL6_DEV_PREVIOUSLY_SEEN_EXTERNAL_YOSYS_NETLISTS",
             "original_hardware_run":45344738069,
             "engine_prelock_run":45347547028,
             "not_blind":True,
             "cases":all_cases}
    (a.out/"REAL6_HARDWARE_RESULTS.json").write_text(json.dumps(summary,indent=2)+"\n")
    table=["# REAL6 / CH · MAJ · FULL ADDER on previous real FPGA netlists",
           "",
           "**Development-only, NOT blind.** These original five RTL gate networks",
           "have already been examined during REAL4 and REAL5-Q.",
           "Each polynomial and motif certificate is independently replayed",
           "using an exhaustive 3-variable truth-table checker.",
           "",
           "| Original FPGA module | CH | MAJ | SUM3 | Complete sum/carry links | Globally proven motifs | Conditional-on-cut motifs |",
           "|---|---:|---:|---:|---:|---:|---:|"]
    for name in CASES:
        c=all_cases[name]["motif_counts"]
        table.append(f"| {name} | {c['chs']} | {c['majs']} | {c['three_input_xor_sums']} | "
                     f"{c['paired_full_adders_before_limit']} | "
                     f"{c['globally_proven_motifs']} | {c['conditional_cut_motifs']} |")
    table+=["","Original gate network is Yosys 0.9 two-state lowered logic.",
            "FF Q treated as free current-state variables. Unsupported",
            "nonlinear cutpoints are free variables; matching conditional",
            "patterns do not prove whole-circuit polynomial degree.",
            "No new Kissat/CaDiCaL comparison is inferred from the motif",
            "counts; existing independently checked REAL5-Q source-cone",
            "SAT controls are in GitHub run 45345192400.",
            "Unmatched patterns MUST NOT be called solved SAT problems.",""]
    (a.out/"REAL6_HARDWARE_REPORT.md").write_text("\n".join(table))
    print("REAL6_FIVE_ORIGINAL_REAL_HARDWARE_MOTIF_AUDIT_PASS",flush=True)
if __name__=="__main__":main()
