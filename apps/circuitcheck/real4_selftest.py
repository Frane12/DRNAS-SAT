#!/usr/bin/env python3
"""REAL4 isolated adversarial netlist controls (no Yosys needed).

Pass/fail verifies: nonlinear cut soundness, free FF-Q state recognition,
true global affine cones, ignored unknown gates ONLY as explicit cuts,
independent set-based checker, randomized XOR circuits, certificate tamper
rejection and x/z unknown rather than false formal claims.
"""
from __future__ import annotations
import copy,json,random,tempfile,sys
from pathlib import Path
from real4_islands import analyze
from real4_verify import proof_replay,Rejected

def cell(kind,inputs,out):
    c={"type":kind,"connections":{"Y":[out]},
       "port_directions":{"Y":"output"}}
    for k,bit in inputs.items():
        c["connections"][k]=[bit]
        c["port_directions"][k]="input"
    return c
def ffc(d,q,clk):
    return {"type":"$_DFF_P_",
            "connections":{"D":[d],"Q":[q],"C":[clk]},
            "port_directions":{"D":"input","Q":"output","C":"input"}}
def basic():
    cells={
        "xor_ab":cell("$_XOR_",{"A":2,"B":3},6),
        "and_ac":cell("$_AND_",{"A":2,"B":4},7),
        "xor_mixed":cell("$_XOR_",{"A":6,"B":7},8),
        "mux_unknown":cell("$_MUX_",{"A":2,"B":3,"S":4},9),
        "ff_state":ffc(9,10,5),
        "mystery":cell("$_SPECIAL_NOT_SUPPORTED_",{"A":6},11),
        "xor_unknown":cell("$_XOR_",{"A":6,"B":11},12),
    }
    ports={
       "alpha":{"direction":"input","bits":[2]},
       "beta":{"direction":"input","bits":[3]},
       "gamma":{"direction":"input","bits":[4]},
       "clock":{"direction":"input","bits":[5]},
       "linear":{"direction":"output","bits":[6]},
       "nonlinear":{"direction":"output","bits":[8]},
       "state":{"direction":"output","bits":[10]},
       "unsupported":{"direction":"output","bits":[12]}
    }
    return {"modules":{"unknown_top":{"ports":ports,"cells":cells}}}

def evaluate_f(x):
    return int(x["mask_hex"],16)
def one_test(net,where):
    raw=where/"netlist.json"
    raw.write_text(json.dumps(net))
    result=analyze(net,"unknown_top")
    result["netlist_sha256"]=__import__("hashlib").sha256(raw.read_bytes()).hexdigest()
    cert=where/"real4_certificate.json"
    cert.write_text(json.dumps(result))
    checked=proof_replay(where)
    assert checked["status"]=="CHECKED_LOCAL_AFFINE_GATE_IDENTITIES"
    return result,cert

def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        result,cert=one_test(basic(),root)
        rows={(x["kind"],x["name"]):x for x in result["probes"]}
        assert rows["primary_output","linear"]["status"]=="GLOBAL_AFFINE_ONE_STEP"
        assert rows["primary_output","nonlinear"]["status"]=="LOCAL_AFFINE_WITH_CUTS"
        assert rows["primary_output","unsupported"]["status"]=="LOCAL_AFFINE_WITH_CUTS"
        assert rows["primary_output","state"]["status"]=="GLOBAL_AFFINE_ONE_STEP"
        assert rows["ff_next_state","ff_state"]["status"]=="LOCAL_AFFINE_WITH_CUTS"
        assert result["metrics"]["state_Q_bits"]==1
        assert result["metrics"]["cutpoints"]>=3
        original=cert.read_bytes()
        attacks=[
            ("FALSE_GLOBAL_AFFINE",lambda x:x["probes"][0].update(status="GLOBAL_AFFINE_ONE_STEP")),
            ("CUTPOINT_FORGERY",lambda x:x["cutpoints"][0].update(yosys_bit=888)),
            ("MASK_MODIFIED",lambda x:x["probes"][0].update(mask_hex="0xdeadcafe")),
            ("FALSE_FULL_SAT_VERDICT",lambda x:x.update(status="UNSAT_VERIFIED")),
            ("MISSING_PROBE",lambda x:x["probes"].pop())
        ]
        for name,change in attacks:
            copy_obj=json.loads(original)
            change(copy_obj)
            cert.write_text(json.dumps(copy_obj))
            try:proof_replay(root)
            except (Rejected,ValueError):pass
            else:raise AssertionError("ACCEPTED_TAMPER "+name)
            print("REAL4_CORRUPTED_CERT_REJECTED",name,flush=True)
        cert.write_bytes(original)
        net=basic()
        net["modules"]["unknown_top"]["ports"]["linear"]["bits"]=["x"]
        result,cert=one_test(net,root)
        assert any(p["status"]=="UNKNOWN" for p in result["probes"])
        print("REAL4_X_UNKNOWN_NOT_PROVED",flush=True)
        rng=random.Random(20261124)
        for iteration in range(80):
            num_inputs=rng.randint(2,16)
            ins=list(range(2,num_inputs+2))
            cells={}
            current=ins[0]
            for i in range(rng.randint(1,16)):
                wire=1000+i
                rhs=rng.choice(ins)
                cells[f"xor{i}"]=cell(rng.choice(("$_XOR_","$_XNOR_")),
                                     {"A":current,"B":rhs},wire)
                current=wire
            net={"modules":{"unknown_top":{
                "ports":{
                    "din":{"direction":"input","bits":ins},
                    "out":{"direction":"output","bits":[current]}
                },"cells":cells}}}
            result,cert=one_test(net,root)
            assert result["metrics"]["global_affine_external_and_state_probes"]==1
        print("REAL4_RANDOM_UNSEEN_AFFINE_NETLISTS_PASS",80,flush=True)
    print("REAL4_ALGEBRA_TAMPER_AND_STATE_CUT_TESTS_PASS",flush=True)

if __name__=="__main__":main()
