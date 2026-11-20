#!/usr/bin/env python3
"""MATH-HYBRID7: real archive transfer audit and cross-family safety checks."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from sparse import sparse_product, Unsupported
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"research"/"pcmax_capacity"))
from check_capacity import check as check_old_capacity

VERIFIED_IDS=("00","02","03","04","05","07","08","09","10","14","15")
VALID_STATUSES={
    "UNSAT_SOURCE_SPARSE_PRODUCT",
    "UNKNOWN_RESOURCE_LIMIT",
    "UNKNOWN_ABSTRACT_COMPATIBLE",
}
def run(script,*args):
    subprocess.run([sys.executable,str(script),*map(str,args)],
                   stdout=subprocess.DEVNULL,check=True)

def test_synthetic_auxiliary(folder,full=False):
    # Every group is exactly-one across two machines.
    # Both local BDDs contain an extra unconstrained selector variable.
    # In full=False mode, both machines reject any selected job: UNSAT.
    # In full=True mode, they accept any selector selection: non-UNSAT.
    groups=[[1,3],[2,4]]
    clauses=[(1,3),(-1,-3),(2,4),(-2,-4)]
    nextvar=7
    machines=[]
    def add(*row):
        clauses.append(tuple(row))
    for j in range(2):
        root=nextvar
        a=nextvar+1
        b=nextvar+2
        t=nextvar+3
        f=nextvar+4
        nextvar+=5
        aux=5+j
        x0=groups[0][j]
        x1=groups[1][j]
        transitions=[
            [root,aux,a,a],
            [a,x0,b,t if full else f],
            [b,x1,t,t if full else f],
        ]
        add(root);add(t);add(-f)
        for q,x,lo,hi in transitions:
            add(-q,x,lo)
            add(-q,-x,hi)
        machines.append({"root":root,"true_terminal":t,"false_terminal":f,
                         "variable_order":[aux,x0,x1],
                         "transitions":transitions})
    source=(f'p cnf {nextvar-1} {len(clauses)}\n'
            +''.join(' '.join(map(str,c))+' 0\n' for c in clauses)).encode("ascii")
    cert={"source_sha256":hashlib.sha256(source).hexdigest(),
          "selected_groups":groups,"machines":machines}
    folder.mkdir(parents=True,exist_ok=True)
    (folder/"source.cnf").write_bytes(source)
    (folder/"capacity.json").write_text(json.dumps(cert,indent=2)+"\n")
    return source,cert

with TemporaryDirectory() as t:
    temp=Path(t)
    for name,full,expected in (
        ("auxiliary_unsat",False,"UNSAT_SOURCE_SPARSE_PRODUCT"),
        ("auxiliary_control",True,"UNKNOWN_ABSTRACT_COMPATIBLE"),
    ):
        data,cert=test_synthetic_auxiliary(temp/name,full)
        out=sparse_product(data,cert,max_states=1000,max_seconds=3)
        assert out["status"]==expected,(name,out)
        assert out["aux_selectors"]==2,out
        print("AUXILIARY_BDD_PASS",name,out["status"],
              out["product_states"])
    sys.path.insert(0,str(ROOT/"research"/"pcmax_hybrid5"))
    for name,emitter,extra,expected in (
        ("hybrid5_unsat",ROOT/"research/pcmax_hybrid5/emit.py",(),
         "UNSAT_SOURCE_SPARSE_PRODUCT"),
        ("hybrid5_control",ROOT/"research/pcmax_hybrid5/emit.py",
         ("--control",),"UNKNOWN_ABSTRACT_COMPATIBLE"),
        ("fano_unsat",ROOT/"research/pcmax_hybrid3/emit.py",
         ("--kind","fano"),"UNSAT_SOURCE_SPARSE_PRODUCT"),
        ("fano_control",ROOT/"research/pcmax_hybrid3/emit.py",
         ("--kind","sat-control"),"UNKNOWN_ABSTRACT_COMPATIBLE"),
    ):
        folder=temp/name
        run(emitter,"--out",folder,*extra)
        data=(folder/"source.cnf").read_bytes()
        cert=json.loads((folder/"certificate.json").read_text())
        outcome=sparse_product(data,cert,max_states=4000,max_seconds=4)
        assert outcome["status"]==expected,(name,outcome)
        print("CROSS_FAMILY_SPARSE_PASS",name,outcome["status"],
              outcome["product_states"])
        if name=="hybrid5_control":
            # A SHA-valid extra contradictory source clause must NOT
            # yield SAT, and a tampered original SHA must fail outright.
            modified=data.decode()
            head=[l for l in modified.splitlines() if l.startswith('p cnf ')][0]
            header=head.split()
            replacement=' '.join(header[:3]+[str(int(header[3])+1)])
            changed=(modified.replace(head,replacement,1)+"0\n").encode()
            cert2=dict(cert)
            cert2["source_sha256"]=hashlib.sha256(changed).hexdigest()
            status=sparse_product(changed,cert2,max_states=4000)
            assert status["status"]=="UNKNOWN_ABSTRACT_COMPATIBLE",status
            print("EXTRA_CLAUSE_NO_FALSE_SAT_PASS")
            try:
                sparse_product(data,cert2,max_states=4000)
            except Unsupported:
                print("SHA_TAMPER_REJECTED")
            else:
                raise AssertionError("tampered SHA accepted")

archive=ROOT/"evidence"/"pcmax-weighted2"
results=[]
for name in VERIFIED_IDS:
    case=archive/name
    cnf=(case/"original.cnf").read_bytes()
    cert=json.loads((case/"capacity.json").read_text())
    old=check_old_capacity(cnf,cert)
    assert old["status"]=="UNSAT_STRUCTURAL_CERTIFICATE_VERIFIED",name
    result=sparse_product(cnf,cert,max_states=1000,max_seconds=3)
    status=result["status"]
    assert status in VALID_STATUSES,(name,result)
    obj={"case":name,"source_sha256":cert["source_sha256"],
         "old_capacity_gap":old["required"]-old["capacity_sum"],
         "sparse_status":status,
         "processed_groups":result.get("processed_groups"),
         "product_states":result.get("product_states"),
         "groups":len(cert["selected_groups"]),
         "machines":len(cert["machines"]),
         "aux_selectors":sum(len(m["variable_order"]) for m in cert["machines"])
                         -sum(len(g) for g in cert["selected_groups"])}
    results.append(obj)
    print("ORIGINAL_PCMAX_TRANSFER",json.dumps(obj,sort_keys=True))

report={
    "status":"ALL_SAFETY_TESTS_PASS",
    "dataset":"11 unchanged source-CNF originals from archived PCMAX weighted2",
    "original_count":len(results),
    "archive_known_veripb_verified":11,
    "new_sparse_product_structural_unsat":
        sum(x["sparse_status"]=="UNSAT_SOURCE_SPARSE_PRODUCT" for x in results),
    "new_sparse_product_unknown":
        sum(x["sparse_status"]!="UNSAT_SOURCE_SPARSE_PRODUCT" for x in results),
    "external_new_proof":"NOT_EMITTED",
    "cases":results
}
Path("hybrid7-transfer.json").write_text(json.dumps(report,indent=2)+"\n")
print("ALL_SAFETY_TESTS_PASS")
