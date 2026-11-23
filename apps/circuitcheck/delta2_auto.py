#!/usr/bin/env python3
"""DELTA2-A: automatically discover affine state-transition boundaries from RTL loops.

The detector is intentionally *strict*: exactly one fixed-count, forward
unrolled combinational for-loop, one updated multi-bit state register, one
single-bit input data[i] per step, and one final output assignment. No
hardcoded CRC name, feedback polynomial, or state-register name is used.
Reject constructs whose semantics are not explicitly covered.

Boundary discovery is currently at the RTL-loop level, NOT arbitrary optimized
gate-netlist graph topology. The automatically extracted one-step Verilog is
synthesized with Yosys. DELTA1 verifies exact affine equations on step, finish
and candidate netlists (and a separate checker replays each certificate).
Composition is exact GF(2) arithmetic conditional on the frontend extraction.
Optional --full-rtl-audit independently checks the derived parallel model
against the *unchanged original reference* on a synthesized combined netlist.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import time

from delta1_engine import write_certificate

HERE = pathlib.Path(__file__).resolve().parent
IDENT = r"[A-Za-z_][A-Za-z_0-9]*"
MAX_BITS = 65536


class DiscoveryFailure(Exception):
    pass


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(message):
    raise DiscoveryFailure(message)


def literal_value(token: str, width: int) -> int:
    m = re.fullmatch(r"(\d+)'([hHdDbB])([0-9a-fA-F_]+)", token.strip())
    if not m:
        fail("initial state is not a fixed binary literal")
    bits, base, digits = int(m[1]), m[2].lower(), m[3].replace("_", "")
    if bits != width:
        fail("initial state literal width differs")
    if any(c in digits.lower() for c in "xz?"):
        fail("unknown initial state bits")
    number = int(digits, {"h":16,"d":10,"b":2}[base])
    if number >= 1 << width:
        fail("initial state literal overflow")
    return number


def strict_module(source: str, name: str) -> tuple[str,str]:
    modules = list(re.finditer(r"\bmodule\s+("+IDENT+r")\s*\((.*?)\)\s*;(.*?)\bendmodule\b",
                               source, re.S))
    found = [m for m in modules if m[1] == name]
    if len(found) != 1:
        fail("reference module must occur exactly once")
    return found[0][2], found[0][3]


def discover(source: str, name="reference") -> dict:
    # Generated stress RTL is deliberately free of comments in its main
    # behavioral modules. Reject comments in the strict scope to avoid a
    # textual parser mistaking commented-out expressions for real hardware.
    header, body = strict_module(source, name)
    if "//" in header+body or "/*" in header+body:
        fail("RTL comments in the extraction scope are unsupported")
    input_ports = re.findall(r"\binput\s+wire\s+\[\s*(\d+)\s*:\s*0\s*\]\s*("+IDENT+r")", header)
    output_ports = re.findall(r"\boutput\s+(?:wire|reg)\s+\[\s*(\d+)\s*:\s*0\s*\]\s*("+IDENT+r")", header)
    if len(input_ports)!=1 or len(output_ports)!=1:
        fail("restricted detector needs one vector input and one vector output")
    raw_width, input_name = input_ports[0]
    out_width, out_name = output_ports[0]
    input_width=int(raw_width)+1
    output_width=int(out_width)+1
    if input_width > MAX_BITS or input_width<2 or output_width<1:
        fail("invalid or excessive declared dimensions")
    loop_regex = (r"\bfor\s*\(\s*("+IDENT+r")\s*=\s*0\s*;\s*\1\s*<\s*(\d+)\s*;"
                  r"\s*\1\s*=\s*\1\s*\+\s*1\s*\)\s*begin\b")
    loops=list(re.finditer(loop_regex,body))
    if len(loops)!=1:
        fail("expected one fixed-bound ascending for-loop")
    loop=loops[0]; ivar=loop[1]
    steps=int(loop[2])
    if steps!=input_width:
        fail("loop bound does not match vector input width")
    start=loop.end()
    closing=re.search(r"\bend\b",body[start:])
    if closing is None:fail("unterminated loop body")
    stop=start+closing.start()
    inner=body[start:stop]
    prefix=body[:loop.start()]
    suffix=body[start+closing.end():]
    if re.search(r"\b(?:begin|end|for|while|if|case|function|task)\b",inner):
        fail("conditional or nested stage behavior unsupported")
    if re.search(r"\b(?:for|while|if|case|function|task)\b",prefix+suffix):
        fail("unsupported additional control flow")
    if re.search(r"\b"+re.escape(ivar)+r"\b",prefix+suffix):
        # integer declaration is expected; ignore it below
        residue=re.sub(r"\binteger\s+"+re.escape(ivar)+r"\s*;","",prefix+suffix)
        if re.search(r"\b"+re.escape(ivar)+r"\b",residue):
            fail("loop index referenced outside loop")
    vector_regs = re.findall(r"\breg\s+\[\s*(\d+)\s*:\s*0\s*\]\s*("+IDENT+r")\s*;",body)
    state_candidates=[]
    assignments=re.findall(r"\b("+IDENT+r")\s*=\s*([^;]+);",inner)
    assigned=[key for key,_ in assignments]
    for maxbit,reg in vector_regs:
        if assigned.count(reg)==1 and any(
            lhs==reg and re.search(r"\b"+re.escape(reg)+r"\b",rhs)
            for lhs,rhs in assignments):
            state_candidates.append((reg,int(maxbit)+1))
    if len(state_candidates)!=1:
        fail("cannot unambiguously infer single feedback state register")
    state_name,state_width=state_candidates[0]
    if state_width!=output_width:
        fail("state and output width differ in supported scope")
    prefix_assignments=re.findall(r"\b("+IDENT+r")\s*=\s*([^;]+);",prefix)
    initials=[v for k,v in prefix_assignments if k==state_name]
    if len(initials)!=1:
        fail("exactly one initial state assignment required")
    init=literal_value(initials[0],state_width)
    final_assignments=re.findall(r"\b("+IDENT+r")\s*=\s*([^;]+);",suffix)
    finals=[v for k,v in final_assignments if k==out_name]
    if len(finals)!=1:
        fail("exactly one final output assignment required")
    for key,_ in final_assignments:
        if key!=out_name:
            fail("extra statement after stage loop")
    if re.search(r"\b"+re.escape(ivar)+r"\b",finals[0]):
        fail("final expression depends on loop index")
    input_reference=re.compile(r"\b"+re.escape(input_name)+r"\s*\[\s*"+re.escape(ivar)+r"\s*\]")
    if len(input_reference.findall(inner)) != 1:
        fail("expected exactly one scalar input reference per step")
    inner_replaced=input_reference.sub("b_input_bit",inner)
    if re.search(r"\b"+re.escape(input_name)+r"\b",inner_replaced) or re.search(
            r"\b"+re.escape(ivar)+r"\b",inner_replaced):
        fail("dynamic loop input/index not completely abstracted")
    # Only the state register may be read from the preceding iteration. All
    # helper scalars must be overwritten before their first use in the body.
    helper_regs=re.findall(r"\breg\s+("+IDENT+r")\s*;",body)
    for helper in helper_regs:
        if helper==state_name:continue
        first=re.search(r"\b"+re.escape(helper)+r"\b",inner)
        first_assign=re.search(r"\b"+re.escape(helper)+r"\s*=",inner)
        if not first or not first_assign or first.start()!=first_assign.start():
            fail("loop-carried scalar helper dependency cannot be ruled out: "+helper)
        if assigned.count(helper)!=1:
            fail("helper must be assigned exactly once per iteration")
    # Any variable read from source before its first write is not admitted
    # except the state and current scalar input.
    allowed={state_name,"b_input_bit"}|set(helper_regs)
    for reg_width,reg in vector_regs:
        if reg!=state_name and re.search(r"\b"+re.escape(reg)+r"\b",inner):
            fail("extra vector state register not supported")
    unexpected_assignments=set(assigned)-({state_name}|set(helper_regs))
    if unexpected_assignments:
        fail("unmodelled stage assignments "+str(sorted(unexpected_assignments)))
    helpers="\n".join("  reg "+name+";" for name in helper_regs if name!=state_name)
    step=("\nmodule drnas_delta2_step(input wire ["+str(state_width-1)+":0] a_state_in,"
          " input wire b_input_bit, output reg ["+str(state_width-1)+":0] drnas_state_out);\n"
          "  reg ["+str(state_width-1)+":0] "+state_name+";\n"
          +helpers+"\n  always @* begin\n  "+state_name+" = a_state_in;\n"
          +inner_replaced+"\n  drnas_state_out = "+state_name+";\n  end\nendmodule\n")
    finish=("\nmodule drnas_delta2_finish(input wire ["+str(state_width-1)+":0] a_state_in,"
            " output reg ["+str(output_width-1)+":0] drnas_output);\n"
            " reg ["+str(state_width-1)+":0] "+state_name+";\n"
            " always @* begin\n "+state_name+" = a_state_in;\n"
            " drnas_output = "+finals[0].strip()+";\n end\nendmodule\n")
    return {"module":name,"input_name":input_name,"output_name":out_name,
            "input_bits":input_width,"output_bits":output_width,
            "state_bits":state_width,"iterations":steps,"initial_state":init,
            "loop_body":inner.strip(),"transition_rtl":step,"finish_rtl":finish,
            "cut_discovery":"automatic RTL combinational for-loop state assignment; "
                            "no netlist-only cut inference"}


def yosys_json(folder:pathlib.Path, source_file:pathlib.Path, top:str)->pathlib.Path:
    p=folder/(top+".ys")
    p.write_text("read_verilog -sv "+source_file.name+
                 "; hierarchy -check -top "+top+
                 "; proc; flatten; opt; techmap; opt; write_json "+top+".json\n")
    t=subprocess.run(["yosys","-s",p.name],cwd=folder,capture_output=True,
                     text=True,timeout=150,check=False)
    (folder/(top+".log")).write_text(t.stdout+"\n"+t.stderr)
    if t.returncode!=0:
        fail("Yosys rejected transition module "+top)
    return folder/(top+".json")


def exact_affine_rows(folder:pathlib.Path, rtl:str,top:str,
                      output:str, input_ports:list[tuple[str,int]]):
    src=folder/(top+".v")
    src.write_text(rtl)
    netfile=yosys_json(folder,src,top)
    module=json.loads(netfile.read_text())["modules"][top]
    ins=module["ports"]
    if any(len(ins[name]["bits"])!=width for name,width in input_ports):
        fail("gate synthesis interface width mismatch")
    iface={"top":top,"pairs":[{"port":output,"reference":output,"candidate":output}]}
    certdir=folder/("cert_"+top);certdir.mkdir(exist_ok=True)
    shutil.copyfile(netfile,certdir/"netlist.json")
    (certdir/"interface.json").write_text(json.dumps(iface,indent=2)+"\n")
    cert=write_certificate(certdir/"netlist.json",certdir/"interface.json",
                           certdir/"delta1_certificate.json")
    if cert["status"]!="EQUIVALENT_NETLIST" or cert["unknown_outputs"]:
        fail("non-affine or unsupported extracted stage: "+str(cert["unknown_outputs"][:2]))
    verifier=subprocess.run([sys.executable,str(HERE/"delta1_verify.py"),str(certdir)],
                            capture_output=True,text=True,timeout=150,check=False)
    (certdir/"verifier.log").write_text(verifier.stdout+"\n"+verifier.stderr)
    if verifier.returncode:
        fail("independent affine certificate replay failed for "+top)
    verified=json.loads((certdir/"delta1_verification.json").read_text())
    if verified["status"]!="CHECKED_EQUIVALENT_NETLIST":
        fail("unverified gate model")
    expected_bits=sum(width for _,width in input_ports)
    basis=[(v["port"],v["position"]) for v in cert["input_basis"]]
    logical_basis=[(name,i) for name,_ in sorted(input_ports) for i in
                   range(dict(input_ports)[name])]
    if expected_bits!=len(basis) or basis!=logical_basis:
        fail("input mapping ambiguous in stage netlist")
    return [int(r["reference_mask"],16) for r in cert["checked_outputs"]], {
        "netlist_sha256":digest(netfile),"certificate_sha256":digest(certdir/"delta1_certificate.json"),
        "independent_replay":verified["status"],"gate_cells":len(module.get("cells",{}))}


def compose(A:list[int],B:list[int],c:list[int],initial:int,bits:int,steps:int):
    width=len(A)
    state=[(initial>>j)&1 for j in range(width)]
    for k in range(steps):
        nxt=[]
        for j in range(width):
            row=A[j];value=c[j]
            while row:
                one=row&-row
                value ^= state[one.bit_length()-1]
                row-=one
            if B[j]:value ^= 1<<(k+1)
            nxt.append(value)
        state=nxt
    return state


def finish_outputs(rows:list[int],finish_masks:list[int],width:int):
    result=[]
    for mask in finish_masks:
        value=mask&1
        bits=(mask>>1)&((1<<width)-1)
        if mask>>(width+1):
            fail("finish expression has an unexpected input dimension")
        while bits:
            one=bits&-bits;value^=rows[one.bit_length()-1];bits-=one
        result.append(value)
    return result


def render_model(schema:dict,rows:list[int])->str:
    n=schema["input_bits"];out=schema["output_bits"]
    lines=[f"module drnas_delta2_model(input wire [{n-1}:0] {schema['input_name']}, "
           f"output wire [{out-1}:0] {schema['output_name']});"]
    for j,mask in enumerate(rows):
        variables=mask>>1
        const=mask&1
        if variables:
            expr=f"(^( {schema['input_name']} & {n}'h{variables:x} ))"
            if const:expr+=" ^ 1'b1"
        else:expr="1'b1" if const else "1'b0"
        lines.append(f"  assign {schema['output_name']}[{j}] = {expr};")
    lines.append("endmodule")
    return "\n".join(lines)+"\n"


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--rtl",required=True,type=pathlib.Path)
    p.add_argument("--reference",default="reference")
    p.add_argument("--candidate",default="candidate")
    p.add_argument("--out",required=True,type=pathlib.Path)
    p.add_argument("--full-rtl-audit",action="store_true")
    args=p.parse_args()
    start=time.perf_counter()
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    report={"engine":"DRNAS-DELTA2-A-AUTO-LOOP","status":"UNKNOWN",
            "source_sha256":digest(args.rtl),"proof_scope":"strict extracted RTL stage; "
            "Yosys gate proofs; original source mapping trusted unless full RTL audit passes"}
    try:
        original=args.rtl.read_text()
        schema=discover(original,args.reference)
        (out/"drnas_delta2_step.v").write_text(schema["transition_rtl"])
        (out/"drnas_delta2_finish.v").write_text(schema["finish_rtl"])
        w=schema["state_bits"];n=schema["input_bits"]
        step,meta_step=exact_affine_rows(out,schema["transition_rtl"],
            "drnas_delta2_step","drnas_state_out",
            [("a_state_in",w),("b_input_bit",1)])
        init=schema["initial_state"]
        A=[(m>>1)&((1<<w)-1) for m in step]
        B=[(m>>(w+1)) for m in step]
        c=[m&1 for m in step]
        if any(b not in (0,1) for b in B):fail("unexpected multi-bit stage input")
        finish,meta_finish=exact_affine_rows(out,schema["finish_rtl"],
             "drnas_delta2_finish","drnas_output",[("a_state_in",w)])
        state=compose(A,B,c,init,n,n)
        outputs=finish_outputs(state,finish,w)
        if len(outputs)!=schema["output_bits"]:fail("incomplete final output")
        model=render_model(schema,outputs)
        (out/"drnas_delta2_model.v").write_text(model)
        # Independently read the user-provided candidate RTL and compare to
        # the derived model. Candidate can contain deliberate injected fault.
        header, body=strict_module(original,args.candidate)
        candidate_source="module "+args.candidate+"("+header+");"+body+"endmodule\n"
        candidate,meta_candidate=exact_affine_rows(out,candidate_source,
            args.candidate,schema["output_name"],[(schema["input_name"],n)])
        if len(candidate)!=len(outputs):fail("candidate output width mismatch")
        differences=[a^b for a,b in zip(outputs,candidate)]
        first=next((j for j,v in enumerate(differences) if v),None)
        status="EQUIVALENT_EXTRACTED_MODEL" if first is None else "DIFFERENT_EXTRACTED_MODEL"
        step_type="GENERAL_AFFINE"
        if all(cj==0 and aj==((1<<(j+1)) if j+1<w else 0) ^ bj
               for j,(aj,bj,cj) in enumerate(zip(A,B,c))):
            step_type="SHIFT_RIGHT_FEEDBACK"
        discovered_taps=sum(b<<j for j,b in enumerate(B))
        report.update({
            "status":status,"transition_kind":step_type,"iterations":n,"state_bits":w,
            "source_cut_count":n+1,"extracted_polynomial_hex":hex(discovered_taps)
              if step_type=="SHIFT_RIGHT_FEEDBACK" else None,
            "first_difference_output":first,
            "difference_mask":hex(differences[first]) if first is not None else "0x0",
            "matrix_A":[hex(x) for x in A],
            "matrix_B":[hex(x) for x in B],
            "matrix_c":c,
            "initial_state":hex(init),
            "model_coefficients":[hex(x) for x in outputs],
            "candidate_coefficients":[hex(x) for x in candidate],
            "step_proof":meta_step,"finish_proof":meta_finish,
            "candidate_proof":meta_candidate,"source_extraction":"STRICT_RTL_LOOP",
            "full_original_rtl_audit":"NOT_RUN"})
        if args.full_rtl_audit:
            # A complete original-reference vs model check gates the stronger
            # claim, rather than relying on parser correctness alone.
            proof=out/"full_original_audit"
            code=subprocess.run([sys.executable,str(HERE/"delta1.py"),"--rtl",
                      str(args.rtl.resolve()),str((out/"drnas_delta2_model.v").resolve()),
                      "--reference",args.reference,"--candidate","drnas_delta2_model",
                      "--out",str(proof)],capture_output=True,text=True,timeout=180,check=False)
            (out/"full_audit_stdout.log").write_text(code.stdout+"\n"+code.stderr)
            if code.returncode!=0:
                fail("FULL_RTL_MODEL_EQUIVALENCE_FAILED")
            verify=subprocess.run([sys.executable,str(HERE/"delta1_verify.py"),
                                   str(proof)],capture_output=True,text=True,
                                   timeout=180,check=False)
            (out/"full_audit_verifier.log").write_text(verify.stdout+"\n"+verify.stderr)
            if verify.returncode!=0:
                fail("FULL_RTL_MODEL_CERTIFICATE_REPLAY_FAILED")
            report["full_original_rtl_audit"]="CHECKED_EQUIVALENT_NETLIST"
            report["full_original_netlist_sha256"]=digest(proof/"netlist.json")
        # This certificate only binds extracted one-step equations; the
        # original-RTL audit above binds the derived model to full source.
        (out/"delta2_model.json").write_text(json.dumps(report,indent=2)+"\n")
    except (DiscoveryFailure,ValueError,KeyError,TypeError,IndexError,
            RecursionError,OverflowError,MemoryError,FileNotFoundError,
            subprocess.TimeoutExpired) as ex:
        report.update(status="UNKNOWN",reason=str(ex))
    report["seconds"]=round(time.perf_counter()-start,6)
    (out/"delta2_report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k not in (
        "matrix_A","matrix_B","matrix_c","model_coefficients","candidate_coefficients"
    )},indent=2),flush=True)
    return 0 if report["status"]!="UNKNOWN" else 2


if __name__=="__main__":
    sys.exit(main())
