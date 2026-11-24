#!/usr/bin/env python3
"""Independent mathematical contract and Yosys miter for REAL3 fixtures.

Independent contract is defined by UART parity / parity-checker semantics
and frozen before comparing to source-derived REAL3 algebra. No expressions
are obtained from REAL3 classifier or any existing source recognizer.
"""
import hashlib
from pathlib import Path

def sha(data):return hashlib.sha256(data).hexdigest()

def configuration(case):
    if case["kind"]=="uart":
        return {"BITS_NUM":case["width"],"ODD_PARITY":case["odd"]}
    if case["kind"]=="chunk":
        return {"WIDTH":case["width"],"CHUNKS":case["chunks"]}
    return {}

def expected_masks(case):
    w=case["width"]
    if case["kind"] in ("even","uart"):
        return [(((1<<w)-1)<<1) | (case.get("odd") or 0)]
    count=case["chunks"];size=w//count
    data_masks=[]
    error_masks=[]
    for j in range(count):
        low=j*size
        high=(j+1)*size-1 if j<count-1 else w-1
        data=( ((1<<(high-low+1))-1)<<low )
        const=1
        ctl=(1<<(w+count+1))
        row=(data<<1)|ctl|const
        data_masks.append(row)
        error_masks.append(row^(1<<(w+j+1)))
    return data_masks+error_masks

def generated_harness(case):
    w=case["width"]
    typ=case["kind"]
    if typ=="uart":
        o=case["odd"]
        spec=(f"module external_spec(input wire [{w-1}:0] data,output wire parity_bit);\n"
              f" assign parity_bit=(^data) ^ 1'b{o};\nendmodule\n")
        check=(f"module miter(input wire [{w-1}:0] data,output wire mismatch);\n"
               "wire got,wanted;\n"
               f"parity_gen #(.BITS_NUM({w}),.ODD_PARITY({o})) dut"
               "(.data(data),.parity_bit(got));\n"
               "external_spec spec(.data(data),.parity_bit(wanted));\n"
               "assign mismatch=(got ^ wanted)")
    elif typ=="even":
        spec=("module external_spec(input wire [7:0] data_in,output wire parity);\n"
              " assign parity=(^data_in);\nendmodule\n")
        check=("module miter(input wire [7:0] data_in,output wire mismatch);\n"
               "wire got,wanted;\n"
               "even_parity_generator dut(.data_in(data_in),.parity(got));\n"
               "external_spec spec(.data_in(data_in),.parity(wanted));\n"
               "assign mismatch=(got ^ wanted)")
    elif typ=="chunk":
        n=case["chunks"]
        header=(f"input wire [{w-1}:0] data_in,input wire [{n-1}:0] parity_in,"
                "input wire parity_type")
        spec=(f"module external_spec({header},"
              f"output wire [{n-1}:0] parity,output wire [{n-1}:0] parity_err);\n")
        for j in range(n):
            low=j*(w//n)
            high=(j+1)*(w//n)-1 if j<n-1 else w-1
            spec+=f" assign parity[{j}]=(^data_in[{high}:{low}]) ^ (~parity_type);\n"
            spec+=f" assign parity_err[{j}]=parity[{j}] ^ parity_in[{j}];\n"
        spec+="endmodule\n"
        check=(f"module miter({header},output wire mismatch);\n"
               f"wire [{n-1}:0] got,expected,got_err,expected_err;\n"
               f"dataint_parity #(.WIDTH({w}),.CHUNKS({n})) dut"
               "(.data_in(data_in),.parity_in(parity_in),.parity_type(parity_type),"
               ".parity(got),.parity_err(got_err));\n"
               "external_spec spec(.data_in(data_in),.parity_in(parity_in),"
               ".parity_type(parity_type),.parity(expected),.parity_err(expected_err));\n"
               "assign mismatch=((|(got ^ expected)) | (|(got_err ^ expected_err)))")
    else:raise ValueError("UNKNOWN_CASE_KIND")
    if case["fault"]:
        check+=" ^ 1'b1"
    return spec+"\n"+check+";\nendmodule\n"

def prepare_source(root:Path,case):
    text=generated_harness(case)
    folder=root/case["name"]
    folder.mkdir(parents=True,exist_ok=True)
    file=folder/"miter.v"
    file.write_text(text)
    return file
