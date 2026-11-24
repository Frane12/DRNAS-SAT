#!/usr/bin/env python3
"""Independent completeness audit of REAL3 18 third-party RTL cases.

No retuning/dropping unknown cases; no SAT oracle assumptions. Kissat and
CaDiCaL run on exactly the same Yosys DIMACS source in each case. Report
separate source-rule proof and independent Yosys SAT confirmations.
"""
import argparse,hashlib,json
from pathlib import Path

ARMS=("Kissat","CaDiCaL")
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--manifest",required=True,type=Path)
    a.add_argument("--combined",required=True,type=Path)
    a.add_argument("--output",required=True,type=Path)
    a.add_argument("--report",required=True,type=Path)
    a.add_argument("--shards",type=int,default=3)
    x=a.parse_args()
    manifest=json.loads(x.manifest.read_text())
    rows={}
    for shard in range(x.shards):
        p=x.combined/f"real3-shard-{shard}"/"results/rows.json"
        if not p.is_file():p=x.combined/f"real3-shard-{shard}"/"rows.json"
        if not p.is_file():raise RuntimeError("SHARD_MISSING "+str(shard))
        d=json.loads(p.read_text())
        if d["manifest_sha256"]!=sha(x.manifest) or d["shard"]!=shard:
            raise RuntimeError("CHANGED_FROZEN_SOURCE_MANIFEST")
        for case in d["cases"]:
            if case["id"] in rows:raise RuntimeError("DUPLICATE_CASE")
            rows[case["id"]]=case
    expected={s["name"]:s for s in manifest["cases"]}
    if set(expected)!=set(rows):
        raise RuntimeError("NOT_ALL_CASES_INCLUDED")
    stats={"REAL3":{"recognized":0,"unknown":0,"replayed":0},
           "Kissat":{"attempts":0,"solved":0,"timeouts":0,"cnf_missing":0},
           "CaDiCaL":{"attempts":0,"solved":0,"timeouts":0,"cnf_missing":0},
           "Yosys":{"full_equal_formal_verified":0,"equal_cases":0,"cnf_exports":0}}
    lines=[
      "# DRNAS REAL3 — name-independent RTL parity holdout",
      "",
      "**Original third-party sources**: code002-nova UART parity, Supreethm2004",
      "even parity generator, RTLDesignSherpa multi-chunk parity/error checker.",
      "These 3 codebases are unrelated to the previous REAL2 pinned LFSR.",
      "One additional original clocked UART RTL source intentionally stays UNKNOWN.",
      "",
      "**Source recognizer** has no known source SHA, module names or signal names.",
      "It only accepts two full-module grammars: scalar parity and a chunked",
      "parity/error checker. Therefore this is narrow grammar generalization,",
      "not a universal Verilog parser or novel universal SAT complexity result.",
      "",
      "Each independent spec is declared separately from the original source.",
      "Yosys proves the equality on synthesized original RTL (equal controls).",
      "SAT controls inject a *conditional input-dependent mismatch* into",
      "the external miter wrapper while keeping the original RTL unchanged.",
      "Kissat/CaDiCaL receive identical Yosys CNF, 2 repeats each, 1 CPU, 15s cap.",
      "CNF export is a separate stage and excluded from solver-only times.",
      "SAT models are independently checked against DIMACS. UNSAT solver",
      "reports do not have separately checked standard DRAT/LRAT certificates.",
      "",
      "| Real module configuration | Inputs | REAL3 detect & replay | Independent Yosys full-source equal proof | CNF vars | Kissat (2×) | CaDiCaL (2×) |",
      "|---|---:|---|---|---:|---|---|"]
    for case in manifest["cases"]:
        row=rows[case["name"]]
        pin=next(s for s in manifest["sources"] if s["name"]==case["src"])
        if row["source_sha256"]!=pin["sha256"]:
            raise RuntimeError("ORIGINAL_SOURCE_CHANGED "+case["name"])
        if row["id"]!=case["name"]:
            raise RuntimeError("ID_CHANGED")
        proof=row["proof"]
        recognized=proof["status"]=="RECOGNIZED_AND_REPLAYED"
        stats["REAL3"]["recognized"]+=int(recognized)
        stats["REAL3"]["unknown"]+=int(not recognized)
        stats["REAL3"]["replayed"]+=int(proof.get("replayed") is True)
        if row["cnf"] is not None:
            stats["Yosys"]["cnf_exports"]+=1
        if not case["fault"]:
            stats["Yosys"]["equal_cases"]+=1
            stats["Yosys"]["full_equal_formal_verified"]+=int(row["external_yosys"]["status"]=="VERIFIED_EQUAL")
        strings={}
        for arm in ARMS:
            ts=sorted([v for v in row["trials"] if v["arm"]==arm],key=lambda v:v["repeat"])
            if len(ts)!=2 or [v["repeat"] for v in ts]!=[0,1]:
                raise RuntimeError("INCOMPLETE_SAT_PAIR "+case["name"]+" "+arm)
            for t in ts:
                stats[arm]["attempts"]+=1
                expect="SAT" if case["fault"] else "UNSAT"
                if t["status"] in ("SAT","UNSAT") and t["status"]!=expect:
                    raise RuntimeError("WRONG_SAT_VERDICT "+case["name"]+" "+arm)
                if t["status"]=="SAT" and t["sat_witness_checked"] is not True:
                    raise RuntimeError("SAT_WITNESS_UNCHECKED")
                if t["status"]==expect:
                    stats[arm]["solved"]+=1
                if t["status"]=="TIMEOUT":stats[arm]["timeouts"]+=1
                if t["status"]=="CNF_EXPORT_FAILED":stats[arm]["cnf_missing"]+=1
            strings[arm]=" / ".join(v["status"]+" "+str(round(v["seconds"],3))+"s" for v in ts)
        desc=(case["name"]+" ("+case["kind"]+")")
        lines.append("| "+desc+" | "+str(proof.get("input_bits","—"))+
            " | "+(f"PASS {proof['seconds']:.4f}s" if recognized else proof["status"])+
            " | "+row["external_yosys"]["status"]+
            " | "+str(row["cnf"]["vars"] if row["cnf"] else "—")+
            " | "+strings["Kissat"]+" | "+strings["CaDiCaL"]+" |")
    lines+=["","## Total results","",
            "| Outcome | Count |","|---|---:|",
            "| REAL3 recognized with independent coefficient replay | "+str(stats["REAL3"]["recognized"])+"/18 |",
            "| Yosys original RTL independently proved equivalent | "+str(stats["Yosys"]["full_equal_formal_verified"])+"/9 |",
            "| CNF exports completed | "+str(stats["Yosys"]["cnf_exports"])+"/18 |",
            "| Kissat completed correct cases | "+str(stats["Kissat"]["solved"])+"/36 |",
            "| CaDiCaL completed correct cases | "+str(stats["CaDiCaL"]["solved"])+"/36 |",
            "",
            "## Scientific boundary",
            "",
            "The real DUTs are independent public sources; the expected reference",
            "functional specification was handcrafted independently for this",
            "specific industrially relevant parity class. The recognizer",
            "accepts narrow source syntax; no claim for arbitrary RTL or",
            "unverified third-party specifications beyond these original sources.",
            "No source file was modified; fault injection occurs only in miter.",
            "The real clocked UART control is UNKNOWN by design.",
            "No physical FPGA PPA or performance signoff.",""]
    out={"protocol":manifest["protocol"],"manifest_sha256":sha(x.manifest),
         "stats":stats,"cases":rows,
         "source":manifest["sources"],
         "negative_controls":manifest["negative_controls"]}
    x.output.write_text(json.dumps(out,indent=2)+"\n")
    x.report.write_text("\n".join(lines))
    print(x.report.read_text(),flush=True)
    print("REAL3_STRICT_18_CASE_AUDIT_PASS",flush=True)

if __name__=="__main__":main()
