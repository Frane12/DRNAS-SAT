#!/usr/bin/env python3
"""REAL6 controlled adversarial tests on actual Boolean gate descriptions.

Builds raw gate representations of CH, majority with AND/XOR and OR/MUX,
full-adder sum+carry and physically unknown input cuts. Independently checks
against the REAL5Q ANF replay and REAL6 exhaustive 3-input truth-table checker.
Includes malicious motif, wrong carry, forged source hash, relabeled cut scope.
"""
from __future__ import annotations
import copy,hashlib,json,tempfile
from pathlib import Path
from real5q_anf import analyze
from real5q_verify import check as verify_anf
from real6_motifs import generate
from real6_verify import verify as verify_motifs,Invalid

def cell(kind,a,y,b=None,s=None):
    ports={"A":[a],"Y":[y]}
    directions={"A":"input","Y":"output"}
    if b is not None:ports["B"]=[b];directions["B"]="input"
    if s is not None:ports["S"]=[s];directions["S"]="input"
    return {"type":kind,"connections":ports,"port_directions":directions}

def gate_model(with_cut=True,wrong_carry=False):
    cells={
      "xy":cell("$_AND_",2,101,3),
      "xz":cell("$_AND_",2,102,4),
      "yz":cell("$_AND_",3,103,4),
      "xy_xz":cell("$_XOR_",101,104,102),
      "maj":cell("$_XOR_",104,105,103),
      "x_xor_y":cell("$_XOR_",2,106,3),
      "sum":cell("$_XOR_",106,107,4),
      "choice_mux":cell("$_MUX_",4,108,3,s=2),
      "or_yz":cell("$_OR_",3,109,4),
      "maj_mux":cell("$_MUX_",103,110,109,s=2),
      "neg_maj":cell("$_NOT_",105,111),
    }
    output={"sum":107,"carry":105,"choice":108,"carry_alt":110,
            "not_carry":111}
    if wrong_carry:
        cells["carry_wrong"]=cell("$_XOR_",2,113,4)
        output["carry"]=113
    if with_cut:
        cells["nonlinear_unknown"]=cell("$_UNKNOWN_SOURCE_CELL_",2,200)
        cells["choice_cut"]=cell("$_MUX_",4,201,3,s=200)
        output["cut_choice"]=201
    ports={
      "a":{"direction":"input","bits":[2]},
      "b":{"direction":"input","bits":[3]},
      "c":{"direction":"input","bits":[4]}
    }
    ports.update({k:{"direction":"output","bits":[v]} for k,v in output.items()})
    return {"modules":{"black_box_design":{"ports":ports,"cells":cells}}}

def prepare(folder,model):
    raw=folder/"netlist.json";raw.write_text(json.dumps(model))
    report=analyze(model,"black_box_design")
    report["netlist_sha256"]=hashlib.sha256(raw.read_bytes()).hexdigest()
    (folder/"real5q_certificate.json").write_text(json.dumps(report,indent=2))
    assert verify_anf(folder)["status"]=="CHECKED_EXACT_BOUNDED_BOOLEAN_POLYNOMIALS"
    results=generate(folder)
    proof=folder/"real6_certificate.json"
    proof.write_text(json.dumps(results,indent=2))
    checked=verify_motifs(folder,proof)
    assert checked["status"]=="CHECKED_REAL6_MOTIF_TRUTH_TABLES"
    return results,proof

def must_reject(folder,path,tag,edit):
    old=path.read_bytes()
    obj=json.loads(old)
    edit(obj)
    path.write_text(json.dumps(obj))
    try:verify_motifs(folder,path)
    except (Invalid,ValueError,KeyError,TypeError):print("REAL6_TAMPER_REJECTED",tag,flush=True)
    else:raise AssertionError("INVALID_REAL6_PROOF_ACCEPTED "+tag)
    finally:path.write_bytes(old)

def main():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        result,path=prepare(root,gate_model())
        kind={m["motif"] for m in result["motifs"]}
        assert {"CH","MAJ","SUM3"}.issubset(kind),kind
        adders=result["full_adder_pairs"]
        assert any({x["sum_probe"]["name"],x["carry_probe"]["name"]}=={"sum","carry"}
                   for x in adders),adders
        assert any({x["sum_probe"]["name"],x["carry_probe"]["name"]}=={"sum","carry_alt"}
                   for x in adders),adders
        assert any(m["motif"]=="CH" and m["scope"]=="CONDITIONAL_CUT_SYMBOLS"
                   and m["probe"]["name"]=="cut_choice" for m in result["motifs"])
        print("REAL6_CH_MAJ_AND_TWO_DIFFERENT_ADDER_IMPLEMENTATIONS_PASS",
              len(result["motifs"]),len(adders),flush=True)
        must_reject(root,path,"MAJ_FALSE_VARIABLE",
            lambda j:next(m for m in j["motifs"] if m["motif"]=="MAJ").update(
                  variables=[0,1,77]))
        must_reject(root,path,"FALSE_CH_SELECTOR",
            lambda j:next(m for m in j["motifs"] if m["motif"]=="CH").update(
                  selector=999))
        must_reject(root,path,"LOCAL_CUT_FALSE_GLOBAL",
            lambda j:next(m for m in j["motifs"] if m["scope"]=="CONDITIONAL_CUT_SYMBOLS").update(
                  scope="GLOBAL_ONE_STEP"))
        must_reject(root,path,"FORGED_FULL_ADDER_PAIR",
            lambda j:j["full_adder_pairs"][0].update(variables=[0,1,4]))
        must_reject(root,path,"FALSE_GATE_NETLIST_SHA",
            lambda j:j.update(gate_netlist_sha256="0"*64))
        must_reject(root,path,"MISLABELED_STATUS",
            lambda j:j.update(status="FULL_DESIGN_UNSAT"))
        assert verify_motifs(root,path)["status"]=="CHECKED_REAL6_MOTIF_TRUTH_TABLES"
        incorrect,proof=prepare(root,gate_model(wrong_carry=True))
        assert all(x["carry_probe"]["name"]!="carry" for x in incorrect["full_adder_pairs"])
        print("REAL6_WRONG_CARRY_NOT_LINKED_TO_FULL_ADDER_PASS",flush=True)
        none,proof=prepare(root,gate_model(with_cut=False))
        assert not any(m["scope"]=="CONDITIONAL_CUT_SYMBOLS" for m in none["motifs"])
        print("REAL6_NO_FALSE_LOCAL_PROOF_FROM_ABSENT_CUT_PASS",flush=True)
    print("REAL6_ALL_INDEPENDENT_TRUTH_TABLE_CONTROLS_PASS",flush=True)

if __name__=="__main__":main()
