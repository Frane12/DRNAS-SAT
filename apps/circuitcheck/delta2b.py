#!/usr/bin/env python3
"""DELTA2-B: discover RTL loop -> prove ONE step -> compose N steps without
synthesizing the unfolded reference -> independently replay all certificates.

Use --full-rtl-audit to additionally prove original reference vs generated
parallel model with DELTA1. Without it, results are conditional on the
STRICT_RTL_LOOP extraction's semantic fidelity, not certified original RTL.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

from delta2_auto import (DiscoveryFailure, discover, strict_module,
                         exact_affine_rows, finish_outputs, render_model, fail)
from delta2b_math import fast_compose

HERE=Path(__file__).resolve().parent


def sha(p:Path)->str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_external(cmd, timeout:int, work:Path, logfile:str):
    p=subprocess.run([str(x) for x in cmd],cwd=work,
                     capture_output=True,text=True,timeout=timeout,check=False)
    (work/logfile).write_text(p.stdout+"\n"+p.stderr)
    if p.returncode:
        fail("subprocess failed; inspect "+logfile)
    return p


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--rtl",required=True,type=Path)
    parser.add_argument("--reference",default="reference")
    parser.add_argument("--candidate",default="candidate")
    parser.add_argument("--out",required=True,type=Path)
    parser.add_argument("--full-rtl-audit",action="store_true")
    args=parser.parse_args()
    t0=time.perf_counter()
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    report={"engine":"DRNAS-DELTA2-B-v0.1","status":"UNKNOWN",
            "source_validation":"STRICT_RTL_EXTRACTION_ONLY",
            "source_audit":"NOT_RUN","timings_s":{},
            "proof_limit":"synthesized 2-state gate netlists; original RTL guarded separately"}
    stage=time.perf_counter()
    try:
        original=args.rtl.resolve()
        source=original.read_text()
        schema=discover(source,args.reference)
        report["source_sha256"]=sha(original)
        report["width"]=schema["state_bits"]
        report["input_bits"]=schema["input_bits"]
        report["cutpoints_discovered"]=schema["iterations"]+1
        report["timings_s"]["cut_discovery"]=round(time.perf_counter()-stage,6)

        stage=time.perf_counter()
        step,step_meta=exact_affine_rows(out,schema["transition_rtl"],
                 "drnas_delta2_step","drnas_state_out",
                 [("a_state_in",schema["state_bits"]),("b_input_bit",1)])
        finish,finish_meta=exact_affine_rows(out,schema["finish_rtl"],
                 "drnas_delta2_finish","drnas_output",
                 [("a_state_in",schema["state_bits"])])
        report["timings_s"]["one_step_plus_finish_proofs"]=round(time.perf_counter()-stage,6)

        width=schema["state_bits"];n=schema["input_bits"]
        A=[(m>>1)&((1<<width)-1) for m in step]
        B=[m>>(width+1) for m in step]
        c=[m&1 for m in step]
        if any(x not in (0,1) for x in B):
            fail("stage input is not scalar affine")
        stage=time.perf_counter()
        state,stats=fast_compose(A,B,c,schema["initial_state"],n)
        outputs=finish_outputs(state,finish,width)
        if len(outputs)!=schema["output_bits"]:
            fail("incomplete output vector")
        model=render_model(schema,outputs)
        (out/"drnas_delta2_model.v").write_text(model)
        report["timings_s"]["matrix_composition"]=round(time.perf_counter()-stage,6)

        stage=time.perf_counter()
        head,body=strict_module(source,args.candidate)
        candidate_rtl="module "+args.candidate+"("+head+");"+body+"endmodule\n"
        candidate,can_meta=exact_affine_rows(out,candidate_rtl,args.candidate,
                      schema["output_name"],[(schema["input_name"],n)])
        report["timings_s"]["candidate_synthesis_proof"]=round(time.perf_counter()-stage,6)
        if len(candidate)!=len(outputs):
            fail("candidate width mismatch")
        delta=[x^y for x,y in zip(outputs,candidate)]
        differing=[i for i,m in enumerate(delta) if m]
        verdict="DIFFERENT_EXTRACTED_MODEL" if differing else "EQUIVALENT_EXTRACTED_MODEL"

        stage=time.perf_counter()
        composition={
            "candidate_name":args.candidate,
            "schema":{"input_name":schema["input_name"],
                      "output_name":schema["output_name"],
                      "input_bits":n,"state_bits":width,
                      "output_bits":schema["output_bits"],"iterations":schema["iterations"],
                      "initial_state":schema["initial_state"]},
            "A_rows_hex":[hex(x) for x in A],"B_bits":B,"c_bits":c,
            "step_masks_hex":[hex(x) for x in step],
            "finish_masks_hex":[hex(x) for x in finish],
            "final_model_masks_hex":[hex(x) for x in outputs],
            "candidate_masks_hex":[hex(x) for x in candidate],
            "difference_masks_hex":[hex(x) for x in delta],
            "first_difference_bit":differing[0] if differing else None,
            "verdict":verdict,
            "original_sha256":sha(original),
            "derived_model_sha256":sha(out/"drnas_delta2_model.v"),
            "step_meta":step_meta,"finish_meta":finish_meta,
            "candidate_meta":can_meta,
            "stats":stats,
            "trust_boundary":"RTL loop cuts from strict source parser, gate-level stage/candidate proofs"
        }
        (out/"delta2b_composition.json").write_text(json.dumps(composition,indent=2)+"\n")
        run_external([sys.executable,HERE/"delta2b_verify.py",out,original],
                     120,out,"composition_replay.log")
        report["timings_s"]["independent_composition_replay"]=round(time.perf_counter()-stage,6)
        verified=json.loads((out/"delta2b_verification.json").read_text())
        if verified.get("status")!="CHECKED_COMPOSITIONAL":
            fail("independent composition checker did not accept all proofs")
        report["status"]=verdict
        report["independently_verified"]=True
        report["first_difference_bit"]=composition["first_difference_bit"]
        report["input_bits"]=n
        report["model_sha256"]=composition["derived_model_sha256"]
        report["extracted_polynomial_hex"]=None
        if all(c[j]==0 and A[j]==(((1<<(j+1)) if j+1<width else 0)^B[j])
               for j in range(width)):
            report["structure"]="SHIFT_RIGHT_FEEDBACK"
            report["extracted_polynomial_hex"]=hex(sum(v<<j for j,v in enumerate(B)))
        else:
            report["structure"]="GENERAL_AFFINE"
        report["matrix_power_stats"]=stats

        if args.full_rtl_audit:
            stage=time.perf_counter()
            proof=out/"full_original_audit"
            run_external([sys.executable,HERE/"delta1.py","--rtl",
                    original,out/"drnas_delta2_model.v",
                    "--reference",args.reference,"--candidate",
                    "drnas_delta2_model","--out",proof],180,
                    out,"full_reference_check.log")
            run_external([sys.executable,HERE/"delta1_verify.py",proof],
                         180,out,"full_reference_replay.log")
            verified_full=json.loads((proof/"delta1_verification.json").read_text())
            if verified_full["status"]!="CHECKED_EQUIVALENT_NETLIST":
                fail("full-original model not checked equivalent")
            report["source_audit"]="CHECKED_ORIGINAL_NETLIST"
            report["source_validation"]="INDEPENDENT_REPLAY_OF_ORIGINAL_RTL_VS_MODEL_NETLIST"
            report["timings_s"]["full_original_audit"]=round(time.perf_counter()-stage,6)
    except (DiscoveryFailure,KeyError,ValueError,TypeError,
            IndexError,OverflowError,MemoryError,RecursionError,
            FileNotFoundError,subprocess.TimeoutExpired) as ex:
        report["status"]="UNKNOWN"
        report["reason"]=str(ex)
        report["independently_verified"]=False
    report["seconds"]=round(time.perf_counter()-t0,6)
    (out/"delta2b_report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2),flush=True)
    return 0 if report["status"]!="UNKNOWN" else 2


if __name__=="__main__":
    sys.exit(main())
