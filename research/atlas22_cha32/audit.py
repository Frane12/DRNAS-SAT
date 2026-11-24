#!/usr/bin/env python3
"""Independent ATLAS22 clause-by-clause original ChaCha CNF miter audit.

Does NOT import encode.py. Replays immutable original source 32-bit BDD
theorem, checks the original source Yosys bit->Tseitin variable mapping,
independently reconstructs reference ripple adder topology, and checks EVERY
CNF clause as a one-gate truth table (including mismatch/equality units).

This is an independent *source-bound structural proof certificate*, not a
standard VeriPB/DRAT/LRAT UNSAT certificate and not a raw CNF-only theorem.
"""
from __future__ import annotations
import argparse,collections,hashlib,itertools,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"apps/circuitcheck"))
from real6_3_32_lsb_verify import verify as verify_source_32

GATE_TYPES={"$_AND_":"AND","$_OR_":"OR","$_XOR_":"XOR",
            "$_XNOR_":"XNOR","$_NOT_":"NOT","$_BUF_":"BUF",
            "$_NAND_":"NAND","$_NOR_":"NOR","$_MUX_":"MUX"}
GATE_INPUTS={"AND":("A","B"),"OR":("A","B"),"XOR":("A","B"),"XNOR":("A","B"),
             "NOT":("A",),"BUF":("A",),"NAND":("A","B"),"NOR":("A","B"),
             "MUX":("A","B","S")}
def fail(msg):raise ValueError(msg)
def sha(b):return hashlib.sha256(b).hexdigest()

def boolean(op,x):
    if op=="NOT":return 1-x[0]
    if op=="BUF":return x[0]
    if op=="AND":return min(x)
    if op=="OR":return max(x)
    if op=="XOR":return x[0]^x[1]
    if op=="XNOR":return 1^(x[0]^x[1])
    if op=="NAND":return 1-min(x)
    if op=="NOR":return 1-max(x)
    if op=="MUX":return x[1] if x[2] else x[0]
    fail("OPERATOR_NOT_IN_CHECKER")

def cls(op,xs,y):
    output=[]
    for values in itertools.product((0,1),repeat=len(xs)):
        correct=boolean(op,values)
        # Exactly one forbidden y row for each tuple of inputs.
        line=tuple([-x if v else x for x,v in zip(xs,values)]+
                   [-y if correct==0 else y])
        output.append(frozenset(line))
    return output

def cnf_parse(path):
    rows=[];header=None
    for s in Path(path).read_text().splitlines():
        s=s.strip()
        if not s or s.startswith("c"):continue
        if s.startswith("p "):
            if header is not None:fail("DUPLICATE_HEADER")
            p=s.split()
            if len(p)!=4 or p[1]!="cnf":fail("BAD_HEADER")
            header=(int(p[2]),int(p[3]))
            continue
        nums=[int(v) for v in s.split()]
        if not nums or nums[-1]!=0 or nums.count(0)!=1:fail("BAD_CLAUSE_TERMINATION")
        cl=nums[:-1]
        if not cl or any(abs(v)>header[0] or v==0 for v in cl):
            fail("BAD_OR_EMPTY_CLAUSE")
        if len(set(cl))!=len(cl) or any(-v in cl for v in cl):
            fail("DUPLICATE_OR_TAUTOLOGICAL_CLAUSE")
        rows.append(frozenset(cl))
    if header is None or header[1]!=len(rows):fail("CNF_HEADER_COUNT_MISMATCH")
    return header,collections.Counter(rows)

def source_graph(doc,top):
    original={}
    for cell in doc["modules"][top]["cells"].values():
        typ=cell["type"]
        if typ not in GATE_TYPES:continue
        op=GATE_TYPES[typ];p=cell.get("connections",{})
        ps=GATE_INPUTS[op]
        if any(len(p.get(port,[]))!=1 for port in (*ps,"Y")):continue
        z=p["Y"][0]
        if z in original:fail("MULTIDRIVEN_YOSYS_GATE")
        original[z]=(op,[p[port][0] for port in ps])
    return original

def validate(net,base,previous,proposed,proof,cnffile,manifestfile):
    src=Path(net).read_bytes()
    cert=Path(base).read_bytes()
    old=Path(previous).read_bytes()
    cand=Path(proposed).read_bytes()
    accepted=Path(proof).read_bytes()
    result=verify_source_32(net,base,previous,proposed)
    if result["status"]!="REAL6_3_SOURCE_32_BIT_INDEPENDENT_BDD_PROOF_PASS":
        fail("INDEPENDENT_SOURCE_32BIT_PROOF_FAILED")
    manifest=json.loads(Path(manifestfile).read_text())
    if manifest.get("protocol")!="ATLAS22_REAL6_CHA32_SOURCE_BOUND_CNF_V1":
        fail("NOT_AN_ATLAS22_PROOF_BRIDGE")
    expected_shas={
        "source_gate_sha256":sha(src),"base_cert_sha256":sha(cert),
        "prior_paths_sha256":sha(old),"proposal_sha256":sha(cand),
        "independent_32bit_verification_sha256":sha(accepted),
        "cnf_sha256":sha(Path(cnffile).read_bytes())}
    for key,value in expected_shas.items():
        if manifest.get(key)!=value:fail("SOURCE_BINDING_FAILED "+key)
    case=manifest["case"]
    if case not in ("original_mismatch","wrong_lsb_mismatch","correct_equal"):
        fail("UNKNOWN_CASE")
    doc=json.loads(src)
    source=source_graph(doc,manifest["original_top"])
    port=manifest["port"]
    if port not in {r["source_output_name"] for r in result["fully_verified_source_32bit_output_ports"]}:
        fail("SOURCE_PROOF_DOES_NOT_NAME_OUTPUT_PORT")
    physical_output=doc["modules"][manifest["original_top"]]["ports"][port]["bits"]
    if physical_output!=manifest["source_output_gate_bits"]:
        fail("ORIGINAL_PHYSICAL_OUTPUT_MAP_BAD")
    rows=[r for r in json.loads(cand)["proposals"] if r["output_port_name"]==port]
    if len(rows)!=1:fail("SOURCE_PROPOSAL_AMBIGUOUS")
    r=rows[0];path=json.loads(old)["paths"][r["previous_full_adder_path_index"]]
    legs=r["lsb_half_adder"]["operands"]
    carry=r["lsb_half_adder"]["carry_bit"]
    f=sorted(x for x in path[0]["inputs"] if x!=carry)
    pairs=[sorted(legs),f]+[stage["operands"] for stage in path[1:]]
    free=[v for ab in pairs for v in ab]
    if len(free)!=64 or len(set(free))!=64:fail("NONINDEPENDENT_CUT")
    if manifest["cut_gate_bits"]!=free or manifest["input_pairs"]!=pairs:
        fail("FREE_64_BIT_CUT_OR_ORDER_CHANGED")
    mapping={int(k):int(v) for k,v in manifest["cnf_cut_mapping"].items()}
    if mapping!={b:i+1 for i,b in enumerate(free)}:
        fail("TSEITIN_FREE_BIT_MAP_CHANGED")

    header,actual=cnf_parse(cnffile)
    number,rows_count=header
    if (number!=manifest["variable_count"] or rows_count!=manifest["clause_count"]):
        fail("DIMACS_COUNTS_DIFFER_MANIFEST")
    gates=manifest["all_source_gates"]
    all_ids=set(range(1,65))
    connected={}
    aux={}
    expected=collections.Counter()
    by_output={}
    for cell in gates:
        op=cell["op"];inputs=cell["inputs"];out=cell["output"]
        origin=cell["origin"]
        if op not in GATE_INPUTS or not isinstance(inputs,list):
            fail("UNKNOWN_TSEITIN_GATE")
        if len(inputs)!=len(GATE_INPUTS[op]) or out in all_ids or not all(x in all_ids for x in inputs):
            fail("UNBOUND_NONTOPOLOGICAL_CNF_GATE")
        if not isinstance(out,int) or out!=len(all_ids)+1:fail("NONCANONICAL_CNF_GATE_INDEX")
        if origin=="ORIGINAL_YOSYS_GATE":
            bit=cell["source_gate_bit"]
            if bit not in source or source[bit][0]!=op:fail("YOSYS_SOURCE_GATES_CHANGED")
            source_inputs=source[bit][1]
            def physical_to_dimacs(v):
                if v in mapping:return mapping[v]
                if v in connected:return connected[v]
                fail("MISSING_OR_UNTRUSTED_ORIGINAL_GATE")
            if inputs!=[physical_to_dimacs(v) for v in source_inputs]:
                fail("ORIGINAL_GATE_INPUT_WIRING_CHANGED")
            if bit in connected:fail("SOURCE_GATE_REPEATED")
            connected[bit]=out
        else:
            if cell["source_gate_bit"] is not None:fail("REFERENCE_GATE_WITH_SOURCE_BIT")
            if origin not in ("REFERENCE_ARITHMETIC","CONTROL_BROKEN_ARITHMETIC","CHECK_SOURCE_VS_ARITHMETIC"):
                fail("FOREIGN_GATE_ORIGIN")
            aux[out]=cell
        for cl in cls(op,inputs,out):expected[cl]+=1
        by_output[out]=cell
        all_ids.add(out)
    if all_ids!=set(range(1,number+1)):fail("UNDEFINED_OR_UNUSED_CNF_ID")
    # Independent reference-circuit check: exact 32-bit ripple structure.
    def only(op,inputs,origin):
        result=[c["output"] for c in gates if
                c["op"]==op and c["inputs"]==list(inputs) and c["origin"]==origin]
        if len(result)!=1:fail("REFERENCE_32BIT_ADDER_MISSING_OR_AMBIGUOUS")
        return result[0]
    expected_bits=[];carry_ref=None
    for i,ab in enumerate(pairs):
        xa,xb=(mapping[v] for v in ab)
        xor=only("XOR",[xa,xb],"REFERENCE_ARITHMETIC")
        if i==0:
            expected_bits.append(xor)
            carry_ref=only("AND",[xa,xb],"REFERENCE_ARITHMETIC")
        else:
            expected_bits.append(only("XOR",[xor,carry_ref],"REFERENCE_ARITHMETIC"))
            g=only("AND",[xa,xb],"REFERENCE_ARITHMETIC")
            p=only("AND",[xor,carry_ref],"REFERENCE_ARITHMETIC")
            carry_ref=only("OR",[g,p],"REFERENCE_ARITHMETIC")
    if manifest["expected_var_ids"]!=expected_bits:fail("REFERENCE_OUTPUTS_WRONG")
    real=[mapping[v] if v in mapping else connected.get(v) for v in physical_output]
    if None in real or real!=manifest["actual_var_ids"]:
        fail("SOME_ORIGINAL_GATE_OUTPUT_UNACCOUNTED")
    if set(connected)!=set(manifest["source_output_gate_bits"])-set(mapping) and not connected:
        fail("ORIGINAL_SOURCE_CONE_EMPTY")
    diffs=[]
    for i in range(32):
        e=expected_bits[i]
        if case=="wrong_lsb_mismatch" and i==0:
            e=only("NOT",[e],"CONTROL_BROKEN_ARITHMETIC")
        diffs.append(only("XOR",[real[i],e],"CHECK_SOURCE_VS_ARITHMETIC"))
    if diffs!=manifest["difference_var_ids"]:
        fail("MISLABELLED_BAD_PROPERTY")
    if case=="correct_equal":
        for d in diffs:expected[frozenset([-d])]+=1
    else:
        expected[frozenset(diffs)]+=1
    if expected!=actual:fail("CNF_NOT_EXACT_SOURCE_PLUS_REFERENCE")
    return {"status":"ATLAS22_SOURCE_BOUND_CNF_INDEPENDENT_AUDIT_PASS",
            "case":case,"source_sha256":sha(src),"cnf_sha256":sha(Path(cnffile).read_bytes()),
            "original_32bit_local_source_BDD_theorem_verified":True,
            "all_CNF_gate_truth_tables_exact":True,
            "original_source_gate_count":len(connected),
            "CNF_variables":number,"CNF_clauses":rows_count,
            "source_output_port":port,
            "scope":"source-bound CNF miter with independently checked original gate + arithmetic proof, not generic raw CNF or standard DRAT/LRAT"}

def main():
    p=argparse.ArgumentParser()
    for a in ("netlist","base-certificate","prior-paths","proposal","original32-verification","cnf","manifest","out"):
        p.add_argument("--"+a,required=True)
    a=p.parse_args()
    result=validate(a.netlist,a.base_certificate,a.prior_paths,a.proposal,
                    a.original32_verification,a.cnf,a.manifest)
    Path(a.out).write_text(json.dumps(result,indent=2)+"\n")
    print("ATLAS22_INDEPENDENT_CNF_AUDIT",json.dumps(result),flush=True)

if __name__=="__main__":main()
