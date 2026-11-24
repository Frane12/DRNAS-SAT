#!/usr/bin/env python3
"""Independent universal parity relation SAT/CaDiCaL controls.

This generates a *small standalone symbolic* Verilog theorem:
for every word X and every mask M, XOR(X & M) equals
conditional XOR for set mask bits. Both the correct relation (UNSAT)
and deliberately complemented relation (SAT) are tested.

These CNFs are NOT the original third-party HDL miter CNFs. The actual
third-party module uses lfsr_mask(j) internally; REAL2 source proof
relies on the exact unchanged common mask function and recognized code
styles. The theorem checks the universal algebraic lemma separately.
"""
from __future__ import annotations
import argparse,hashlib,json,os,pathlib,sys
from stress_run import run,dimacs_meta,result_status,verify_sat

WIDTHS=(8,16,32,64,128)
REPS=2
CAP=12.
EXPORT=90.

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def generate(width:int,fault:bool)->str:
    return f"""
module miter(input wire [{width-1}:0] data, input wire [{width-1}:0] mask, output wire mismatch);
  reg loop_parity;
  integer i;
  always @* begin
    loop_parity = 1'b0;
    for(i = 0; i < {width}; i=i+1) begin
      if (mask[i]) begin
         loop_parity = loop_parity ^ data[i];
      end
    end
  end
  wire reduction_parity = ^(data & mask);
  assign mismatch = loop_parity ^ reduction_parity {"^ 1'b1" if fault else ""};
endmodule
"""

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=pathlib.Path,required=True)
    p.add_argument("--kissat",type=pathlib.Path,required=True)
    p.add_argument("--cadical",type=pathlib.Path,required=True)
    x=p.parse_args()
    root=x.out.resolve();root.mkdir(exist_ok=True,parents=True)
    exe={"Kissat":x.kissat.resolve(),"CaDiCaL":x.cadical.resolve()}
    cpu=min(os.sched_getaffinity(0))
    data={"protocol":"REAL2_PARITY_SYMBOLIC_MASK_SAT_CONTROLS",
          "statement":"forall X,M: reduction-XOR(X&M) == conditional per-bit XOR(X,M)",
          "CNF_scope":"symbolic universal parity lemma, NOT original public IP source formula",
          "one_cpu":cpu,"wall_cap_seconds":CAP,
          "binary_sha256":{k:sha(v) for k,v in exe.items()},
          "cases":[]}
    def write():
        (root/"sat_controls.json").write_text(json.dumps(data,indent=2)+"\n")
    for n in WIDTHS:
        for broken in (False,True):
            label=f"parity_{n}_"+("fault" if broken else "equal")
            folder=root/label;folder.mkdir(exist_ok=True)
            source=folder/"theorem.v"
            source.write_text(generate(n,broken))
            cnf=folder/"theorem.cnf"
            script=("read_verilog -sv "+str(source)+"; hierarchy -check -top miter; "
                    "proc; flatten; opt; sat -timeout 1 -set mismatch 1 -dump_cnf "+str(cnf))
            export=run(["yosys","-p",script],cpu,EXPORT,folder/"yosys.log")
            case={"name":label,"width":n,"fault":broken,"source_sha256":sha(source),
                  "expected":"SAT" if broken else "UNSAT","cnf":None,
                  "cnf_export_seconds":export["seconds"],"cnf_export_timeout":export["timeout"],
                  "trials":[]}
            data["cases"].append(case)
            if export["return_code"]==0 and not export["timeout"] and cnf.exists():
                case["cnf"]=dimacs_meta(cnf)
            write()
            print("REAL2_THEOREM_CNF",label,case["cnf"],flush=True)
            for rep in range(REPS):
                order=("Kissat","CaDiCaL") if rep==0 else ("CaDiCaL","Kissat")
                for arm in order:
                    if case["cnf"] is None:
                        result={"arm":arm,"repeat":rep,"status":"CNF_EXPORT_FAILED",
                                "seconds":0,"sat_witness_checked":None}
                    else:
                        t=run([exe[arm],cnf],cpu,CAP,folder/f"{arm}_{rep}.log")
                        status=result_status(t["stdout"],t["return_code"],t["timeout"])
                        witness=verify_sat(cnf,t["stdout"]) if status=="SAT" else None
                        if status in ("SAT","UNSAT") and status!=case["expected"]:
                            raise RuntimeError("INCORRECT_PARITY_THEOREM_VERDICT "+label+" "+arm)
                        if status=="SAT" and witness is not True:
                            raise RuntimeError("INVALID_SAT_THEOREM_WITNESS "+label+" "+arm)
                        result={"arm":arm,"repeat":rep,"status":status,"seconds":t["seconds"],
                                "max_rss_kb":t["max_rss_kb"],
                                "sat_witness_checked":witness,
                                "unsat_drat_lrat_proof_checked":False}
                    case["trials"].append(result)
                    write()
                    print("REAL2_THEOREM_TRIAL",label,arm,rep,result["status"],
                          round(result["seconds"],4),"s",flush=True)
    if len(data["cases"])!=len(WIDTHS)*2:
        raise RuntimeError("MISSING_CASES")
    assert all(len(c["trials"])==REPS*2 for c in data["cases"])
    lines=["# REAL2 universal parity theorem — Kissat and CaDiCaL fresh run",
           "", "These small CNFs express the generic identity for arbitrary **data and mask**.",
           "**They are NOT original third-party source CNFs**. Yosys CNF export measured separately.",
           "One CPU per solver, two repeats, 12-second solver wall cap.",
           "",
           "| Data/mask width | Case | CNF variables | Kissat (2×) | CaDiCaL (2×) |",
           "|---|---|---:|---|---|"]
    for case in data["cases"]:
        arms={}
        for arm in exe:
            ts=sorted([v for v in case["trials"] if v["arm"]==arm],key=lambda v:v["repeat"])
            arms[arm]=" / ".join(v["status"]+" "+str(round(v["seconds"],3))+"s" for v in ts)
        lines.append("| "+str(case["width"])+" | "+("fault" if case["fault"] else "equal")+
            " | "+str(case["cnf"]["vars"] if case["cnf"] else "—")+
            " | "+arms["Kissat"]+" | "+arms["CaDiCaL"]+" |")
    lines+=["","No standard DRAT/LRAT verification of solver-reported UNSAT was performed.",""]
    (root/"SAT_CONTROLS.md").write_text("\n".join(lines))
    print("REAL2_PARITY_THEOREM_CONTROLS_COMPLETE",flush=True)

if __name__=="__main__":main()
