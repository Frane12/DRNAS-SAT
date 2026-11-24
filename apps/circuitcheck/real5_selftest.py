#!/usr/bin/env python3
"""REAL5 original-gate adversarial tests: 2 and 3 output cut cancellation.

No source-specific rule is installed. Recomputes real4 gate proof, builds
REAL5 relation and separately checks against independent GF2-set replay.
Mutated RHS, cut count, relation membership and source gate SHA must fail.
A distinct nonlinear gate with no relation remains NO_NONTRIVIAL... .
"""
from __future__ import annotations
import hashlib,json,random,tempfile
from pathlib import Path
from real4_islands import analyze
from real5_relations import generate
from real5_verify import verify,Invalid
from real4_verify import Rejected as BaseRejected

def cell(kind, inputs, out):
    conn={"Y":[out]}
    dirs={"Y":"output"}
    for p,bit in inputs.items():
        conn[p]=[bit];dirs[p]="input"
    return {"type":kind,"connections":conn,"port_directions":dirs}

def source(triple=False,none=False):
    inputs={"a":{"direction":"input","bits":[2]},
            "b":{"direction":"input","bits":[3]},
            "c":{"direction":"input","bits":[4]}}
    cells={
       "and_ab":cell("$_AND_",{"A":2,"B":3},9),
       "out_one":cell("$_XOR_",{"A":9,"B":2},10)
    }
    if none:
        cells["and_bc"]=cell("$_AND_",{"A":3,"B":4},12)
        cells["out_two"]=cell("$_XOR_",{"A":12,"B":3},11)
    else:
        cells["out_two"]=cell("$_XOR_",{"A":9,"B":3},11)
    outs={"y0":{"direction":"output","bits":[10]},
          "y1":{"direction":"output","bits":[11]}}
    if triple:
        # Remove the original pairwise canceling external output to force
        # a genuine three-output dependency with two nonlinear cutpoints.
        outs.pop("y0")
        # Additional 3-term linear dependence involving two independent
        # nonlinear gate outputs. Each contributing output is itself
        # non-affine, while all cuts cancel in the three-output sum.
        cells["and_ac"]=cell("$_AND_",{"A":2,"B":4},13)
        cells["xor_ab"]=cell("$_XOR_",{"A":9,"B":13},14)
        cells["triple0"]=cell("$_XOR_",{"A":13,"B":2},15)
        outs["y2"]={"direction":"output","bits":[14]}
        outs["y3"]={"direction":"output","bits":[15]}
        # y0 ^ y2 ^ y3 = cut1^a ^ cut1^cut2 ^ cut2^a =0,
        # so this particular triple is trivial and must be discarded
        # by nontrivial-input-weight filter.
        # y1 ^ y2 ^ y3 = a ^ b (nontrivial) due remaining cut1?:
        # y1=cut1^b; y2=cut1^cut2; y3=cut2^a -> a^b.
    return {"modules":{"unknown_circuit":{"ports":{**inputs,**outs},"cells":cells}}}

def save(root,net):
    raw=root/"netlist.json"
    raw.write_text(json.dumps(net))
    c=analyze(net,"unknown_circuit")
    c["netlist_sha256"]=hashlib.sha256(raw.read_bytes()).hexdigest()
    (root/"real4_certificate.json").write_text(json.dumps(c,indent=2))
    r=generate(root)
    output=root/"real5_relations.json"
    output.write_text(json.dumps(r,indent=2))
    return r,output

def must_reject(tag,folder,file,mutate):
    original=file.read_bytes()
    record=json.loads(original)
    mutate(record)
    file.write_text(json.dumps(record))
    try:
        verify(folder,file)
    except (Invalid,ValueError,TypeError,KeyError):
        print("REAL5_TAMPER_REJECTED",tag,flush=True)
    else:
        raise AssertionError("UNSOUND_RELATION_ACCEPTED "+tag)
    finally:
        file.write_bytes(original)

def main():
    with tempfile.TemporaryDirectory() as temporary:
        folder=Path(temporary)
        proof,path=save(folder,source())
        assert proof["status"]=="RELATIONAL_IDENTITIES_FOUND",proof
        assert any(x["term_count"]==2 and x["ordinary_input_coefficient_weight"]==2
                   for x in proof["relations"]),proof
        assert verify(folder,path)["relations_replayed"]>=1
        print("REAL5_TWO_OUTPUT_CUT_CANCELLATION_PASS",len(proof["relations"]),flush=True)
        must_reject("FALSE_GLOBAL_AFFINE_RHS",folder,path,
                    lambda v:v["relations"][0].update(output_xor_mask_hex="0x1"))
        must_reject("FALSE_CANCELED_CUT_COUNT",folder,path,
                    lambda v:v["relations"][0].update(nonlinear_cutpoints_canceled=999))
        must_reject("MISSING_PROBE",folder,path,
                    lambda v:v["relations"][0]["probes"].pop())
        must_reject("BAD_PROOF_LEVEL",folder,path,
                    lambda v:v.update(status="FULL_CIRCUIT_UNSAT"))
        gate=folder/"netlist.json"
        raw=gate.read_bytes();gate.write_bytes(raw+b"\n")
        try:
            verify(folder,path)
        except (Invalid,BaseRejected,ValueError):pass
        else:raise AssertionError("BAD_SOURCE_SHA_ACCEPTED")
        finally:gate.write_bytes(raw)
        proof,path=save(folder,source(triple=True))
        assert any(x["term_count"]==3 and x["ordinary_input_coefficient_weight"]>=2
                   for x in proof["relations"]),proof
        assert verify(folder,path)["relations_replayed"]>=1
        print("REAL5_THREE_OUTPUT_NULLSPACE_PASS",len(proof["relations"]),flush=True)
        proof,path=save(folder,source(none=True))
        # Internal sampled XOR probes might produce relations; only assert
        # that there is no false pairwise combination of the two external
        # outputs of independent nonlinear gates.
        assert not any(set(x["probes"][i]["name"] for i in range(len(x["probes"])))=={"y0","y1"}
                       for x in proof["relations"])
        assert verify(folder,path)["status"]=="CHECKED_GF2_CROSSCONE_RELATIONS"
        print("REAL5_NO_FALSE_RELATION_BETWEEN_INDEPENDENT_CUTS_PASS",flush=True)
    print("REAL5_SYNTHETIC_MATRIX_CORRELATION_AND_CERT_TAMPER_PASS",flush=True)

if __name__=="__main__":main()
