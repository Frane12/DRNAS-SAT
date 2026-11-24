#!/usr/bin/env python3
"""ATLAS22: provenance-locked Tseitin miter for ORIGINAL REAL6 ChaCha 32-bit source gate netlist.

NO synthetic replacement for source gates. Frozen Yosys gate JSON and the
independently proven REAL6.3/32 original output-bus fact specify exact
64-wire local cut and 32-output gate cone. This encoder constructs a
second, mathematically conventional 32-bit ripple adder and asks whether
any of its 32 bits differs from the unmodified source gate network.

Output formulas: original_mismatch (UNSAT if certified theorem applies),
wrong_lsb_mismatch (SAT control), correct_equal (SAT control).
The generated encoding itself is independently audited by audit.py.
No CDCL is used by the encoder or structural method.
"""
from __future__ import annotations
import argparse,hashlib,itertools,json
from pathlib import Path
PORTS={"$_AND_":("A","B"),"$_OR_":("A","B"),"$_XOR_":("A","B"),
       "$_XNOR_":("A","B"),"$_NOT_":("A",),"$_BUF_":("A",),
       "$_NAND_":("A","B"),"$_NOR_":("A","B"),"$_MUX_":("A","B","S")}
OPS={"$_AND_":"AND","$_OR_":"OR","$_XOR_":"XOR","$_XNOR_":"XNOR",
     "$_NOT_":"NOT","$_BUF_":"BUF","$_NAND_":"NAND","$_NOR_":"NOR","$_MUX_":"MUX"}
def sha(b):return hashlib.sha256(b).hexdigest()
def apply(op,v):
    a=v[0]
    if op=="NOT":return 1-a
    if op=="BUF":return a
    b=v[1]
    if op=="AND":return a&b
    if op=="OR":return a|b
    if op=="XOR":return a^b
    if op=="XNOR":return 1^(a^b)
    if op=="NAND":return 1^(a&b)
    if op=="NOR":return 1^(a|b)
    if op=="MUX":return v[2]*b+(1-v[2])*a
    raise ValueError("UNSUPPORTED_OPERATOR "+op)

class Encoder:
    def __init__(self,cut,source,top):
        self.cut=list(cut)
        assert len(cut)==64 and len(set(cut))==64
        self.nextvar=64
        self.var={v:i+1 for i,v in enumerate(cut)}
        self.clauses=[];self.gates=[];self.in_progress=set()
        self.graph={}
        for cell in source["modules"][top]["cells"].values():
            op=cell["type"];co=cell.get("connections",{})
            if op not in PORTS:continue
            if any(len(co.get(k,[]))!=1 for k in (*PORTS[op],"Y")):continue
            z=co["Y"][0]
            if not isinstance(z,int):continue
            if z in self.graph:raise ValueError("SOURCE_MULTIDRIVEN_GATE_BIT")
            self.graph[z]=(OPS[op],[co[k][0] for k in PORTS[op]])
    def fresh(self):
        self.nextvar+=1;return self.nextvar
    def emit(self,op,args,origin=None,source_bit=None):
        z=self.fresh()
        for xyz in itertools.product((0,1),repeat=len(args)):
            wanted=apply(op,xyz)
            for zv in (0,1):
                if zv==wanted:continue
                # Forbid exactly this false assignment; truth-table Tseitin.
                cs=[(-v if b else v) for v,b in zip(args,xyz)]
                cs.append(-z if zv else z)
                self.clauses.append(cs)
        self.gates.append({"op":op,"inputs":list(args),"output":z,
                           "origin":origin,"source_gate_bit":source_bit})
        return z
    def source_wire(self,bit):
        if bit in self.var:return self.var[bit]
        if bit in ("0","1"):
            z=self.fresh()
            self.clauses.append([z] if bit=="1" else [-z])
            self.var[bit]=z
            return z
        if bit in self.in_progress or bit not in self.graph:
            raise ValueError("SOURCE_CONE_UNBOUND_OR_CYCLE "+str(bit))
        self.in_progress.add(bit)
        op,inputs=self.graph[bit]
        value=self.emit(op,[self.source_wire(x) for x in inputs],
                        origin="ORIGINAL_YOSYS_GATE",source_bit=bit)
        self.in_progress.remove(bit)
        self.var[bit]=value
        return value

def derive(net,old,complete,port):
    source=json.loads(net)
    top=complete["top"]
    matches=[x for x in complete["proposals"]
             if x["output_port_name"]==port and x["complete_modular_sum_bits"]==32]
    if len(matches)!=1:raise ValueError("NOT_ONE_SOURCE_PROVED_32_BIT_OUTPUT")
    row=matches[0]
    path=old["paths"][row["previous_full_adder_path_index"]]
    assert len(path)==31
    legs=row["lsb_half_adder"]["operands"]
    first_carry=row["lsb_half_adder"]["carry_bit"]
    rem=sorted(x for x in path[0]["inputs"] if x!=first_carry)
    assert len(rem)==2
    pairs=[sorted(legs),rem]+[s["operands"] for s in path[1:]]
    assert len(pairs)==32
    free=[v for pair in pairs for v in pair]
    assert len(free)==64 and len(set(free))==64
    outputs=source["modules"][top]["ports"][port]["bits"]
    assert len(outputs)==32
    return top,source,free,pairs,outputs

def generate(netfile,basefile,priorfile,proposalfile,original32_verification,port,case,dest):
    src=Path(netfile).read_bytes()
    base_raw=Path(basefile).read_bytes()
    prior_raw=Path(priorfile).read_bytes()
    proposal_raw=Path(proposalfile).read_bytes()
    proof_raw=Path(original32_verification).read_bytes()
    old=json.loads(prior_raw);candidate=json.loads(proposal_raw)
    accepted=json.loads(proof_raw)
    if (accepted.get("status")!="REAL6_3_SOURCE_32_BIT_INDEPENDENT_BDD_PROOF_PASS"
        or port not in {x["source_output_name"] for x in accepted["fully_verified_source_32bit_output_ports"]}
        or candidate["source_gate_sha256"]!=sha(src)
        or candidate["source_previous_independent_fulladder_report_sha256"]!=sha(prior_raw)):
        raise ValueError("INDEPENDENT_32BIT_SOURCE_PROOF_REQUIRED")
    top,doc,free,pairs,outputs=derive(src,old,candidate,port)
    encoder=Encoder(free,doc,top)
    actual=[encoder.source_wire(bit) for bit in outputs]
    carry=None;expected=[]
    # Initial stage is naturally a half-adder with zero initial carry.
    for i,(a,b) in enumerate(pairs):
        x=encoder.var[a];y=encoder.var[b]
        xy=encoder.emit("XOR",[x,y],origin="REFERENCE_ARITHMETIC")
        if carry is None:
            s=xy;carry=encoder.emit("AND",[x,y],origin="REFERENCE_ARITHMETIC")
        else:
            s=encoder.emit("XOR",[xy,carry],origin="REFERENCE_ARITHMETIC")
            g=encoder.emit("AND",[x,y],origin="REFERENCE_ARITHMETIC")
            p=encoder.emit("AND",[xy,carry],origin="REFERENCE_ARITHMETIC")
            carry=encoder.emit("OR",[g,p],origin="REFERENCE_ARITHMETIC")
        expected.append(s)
    diffs=[]
    for i in range(32):
        ref=expected[i]
        if case=="wrong_lsb_mismatch" and i==0:
            ref=encoder.emit("NOT",[ref],origin="CONTROL_BROKEN_ARITHMETIC")
        diffs.append(encoder.emit("XOR",[actual[i],ref],origin="CHECK_SOURCE_VS_ARITHMETIC"))
    if case=="correct_equal":
        for v in diffs:encoder.clauses.append([-v])
    else:encoder.clauses.append(diffs)
    assert case in ("original_mismatch","wrong_lsb_mismatch","correct_equal")
    dest=Path(dest);dest.mkdir(parents=True,exist_ok=True)
    hdr=f"p cnf {encoder.nextvar} {len(encoder.clauses)}\n"
    cnf=hdr+"".join(" ".join(map(str,cl))+" 0\n" for cl in encoder.clauses)
    cnfpath=dest/(case+".cnf")
    cnfpath.write_text(cnf)
    metadata={
        "protocol":"ATLAS22_REAL6_CHA32_SOURCE_BOUND_CNF_V1","case":case,
        "source_gate_sha256":sha(src),"base_cert_sha256":sha(base_raw),
        "prior_paths_sha256":sha(prior_raw),"proposal_sha256":sha(proposal_raw),
        "independent_32bit_verification_sha256":sha(proof_raw),
        "original_top":top,"port":port,"cut_gate_bits":free,
        "source_output_gate_bits":outputs,"input_pairs":pairs,
        "source_gate_count":sum(g["origin"]=="ORIGINAL_YOSYS_GATE" for g in encoder.gates),
        "variable_count":encoder.nextvar,"clause_count":len(encoder.clauses),
        "cnf_sha256":sha(cnf.encode()),"source_is_original_unchanged":True,
        "no_CDCL_fallback":True,"known_result_for_audit_only":
            "UNSAT" if case=="original_mismatch" else "SAT",
        "all_source_gates":encoder.gates,
        "cnf_cut_mapping":{str(k):encoder.var[k] for k in free},
        "actual_var_ids":actual,"expected_var_ids":expected,"difference_var_ids":diffs
    }
    (dest/(case+"_manifest.json")).write_text(json.dumps(metadata,indent=2)+"\n")
    print("ATLAS22_CNF_EXPORTED",json.dumps({
        "case":case,"variables":encoder.nextvar,"clauses":len(encoder.clauses),
        "original_source_gates":metadata["source_gate_count"],
        "sha":metadata["cnf_sha256"]}),flush=True)
    return metadata

def main():
    p=argparse.ArgumentParser()
    for name in ("netlist","base-certificate","prior-paths","proposal","original32-verification","out"):
        p.add_argument("--"+name,required=True)
    p.add_argument("--port",default="a_prim")
    a=p.parse_args()
    for case in ("original_mismatch","wrong_lsb_mismatch","correct_equal"):
        generate(a.netlist,a.base_certificate,a.prior_paths,a.proposal,
                 a.original32_verification,a.port,case,a.out)
if __name__=="__main__":main()
