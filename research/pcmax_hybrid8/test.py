#!/usr/bin/env python3
"""HYBRID8 symmetry-multiset correctness, distinct-source and original-CNF audit."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from quotient import quotient
from sparse import sparse_product, Unsupported

ROOT=Path(__file__).resolve().parents[2]

def run(script,*args):
    subprocess.run([sys.executable,str(script),*map(str,args)],
                   check=True,stdout=subprocess.DEVNULL)

def generate_capacity(folder,n,m,k):
    """At-most-k per-machine BDDs; exact-one choice for each job group."""
    folder.mkdir(parents=True,exist_ok=True)
    clauses=[]
    groups=[[j*n+i+1 for j in range(m)] for i in range(n)]
    for g in groups:
        clauses.append(tuple(g))
        for j in range(m):
            for t in range(j+1,m):
                clauses.append((-g[j],-g[t]))
    nextv=n*m+1
    machines=[]
    for j in range(m):
        nodes={}
        for i in range(n):
            for rem in range(k+1):
                nodes[(i,rem)]=nextv
                nextv+=1
        t,f=nextv,nextv+1
        nextv+=2
        root=nodes[(0,k)]
        clauses.extend(((root,),(t,),(-f,)))
        tr=[]
        for (i,rem),q in sorted(nodes.items()):
            x=groups[i][j]
            lo=t if i==n-1 else nodes[(i+1,rem)]
            hi=f if rem==0 else (t if i==n-1 else nodes[(i+1,rem-1)])
            clauses.append((-q,x,lo))
            clauses.append((-q,-x,hi))
            tr.append([q,x,lo,hi])
        machines.append({
            "root":root,"true_terminal":t,"false_terminal":f,
            "variable_order":[groups[i][j] for i in range(n)],
            "transitions":tr,
        })
    text=f"c HYBRID8 constructed capacity-{k} exact cover; not real PCMAX\n"
    text+=f"p cnf {nextv-1} {len(clauses)}\n"
    text+=''.join(' '.join(map(str,c))+' 0\n' for c in clauses)
    data=text.encode()
    cert={"selected_groups":groups,
          "machines":machines,
          "source_sha256":hashlib.sha256(data).hexdigest()}
    (folder/"source.cnf").write_bytes(data)
    (folder/"certificate.json").write_text(json.dumps(cert,indent=2)+"\n")
    return data,cert

with TemporaryDirectory() as tmp:
    tmp=Path(tmp)
    for n,expected in ((11,"UNSAT_SOURCE_SYMMETRY_PRODUCT"),
                       (10,"UNKNOWN_ABSTRACT_COMPATIBLE")):
        data,cert=generate_capacity(tmp/f"ten_machines_{n}",n,10,1)
        out=quotient(data,cert,max_states=500,max_seconds=10)
        assert out["status"]==expected,(n,out)
        assert out["structural_classes"]==1,(n,out)
        assert out["product_states"]<=n+1,(n,out)
        print("TEN_SYMMETRIC_MACHINES_PASS",n,out["status"],
              "states",out["product_states"],
              "classes",out["structural_classes"])
        if n==11:
            plain=sparse_product(data,cert,max_states=500,max_seconds=10)
            assert plain["status"]=="UNKNOWN_RESOURCE_LIMIT",plain
            print("UNQUOTIENTED_EXPLOSION_CONFIRMED",plain["product_states"])

    for name,emitter,args,expected in (
        ("hybrid5_unsat",ROOT/"research/pcmax_hybrid5/emit.py",(),
         "UNSAT_SOURCE_SYMMETRY_PRODUCT"),
        ("hybrid5_sat",ROOT/"research/pcmax_hybrid5/emit.py",("--control",),
         "UNKNOWN_ABSTRACT_COMPATIBLE"),
        ("fano_unsat",ROOT/"research/pcmax_hybrid3/emit.py",("--kind","fano"),
         "UNSAT_SOURCE_SYMMETRY_PRODUCT"),
        ("fano_sat",ROOT/"research/pcmax_hybrid3/emit.py",("--kind","sat-control"),
         "UNKNOWN_ABSTRACT_COMPATIBLE"),
    ):
        path=tmp/name
        run(emitter,"--out",path,*args)
        data=(path/"source.cnf").read_bytes()
        cert=json.loads((path/"certificate.json").read_text())
        out=quotient(data,cert,max_states=2500,max_seconds=8)
        assert out["status"]==expected,(name,out)
        assert out["structural_classes"]<=3,out
        print("CROSS_FAMILY_SYMMETRY_PASS",name,
              out["status"],out["product_states"],
              out["structural_classes"])
        if name=="hybrid5_sat":
            altered=dict(cert)
            altered["source_sha256"]="0"*64
            try:quotient(data,altered)
            except Unsupported: print("BAD_SOURCE_SHA_REJECTED")
            else:raise AssertionError("bad sha accepted")
            mutated=json.loads(json.dumps(cert))
            mutated["machines"][0]["transitions"][0][2]=(
                mutated["machines"][0]["false_terminal"])
            try:quotient(data,mutated)
            except Unsupported: print("BAD_SOURCE_EDGE_REJECTED")
            else:raise AssertionError("bad edge accepted")

    results=[]
    for id in ("00","05","09","10","14","15"):
        folder=ROOT/"evidence"/"pcmax-weighted2"/id
        data=(folder/"original.cnf").read_bytes()
        cert=json.loads((folder/"capacity.json").read_text())
        out=quotient(data,cert,max_states=3000,max_seconds=6)
        assert out["status"] in (
            "UNSAT_SOURCE_SYMMETRY_PRODUCT",
            "UNKNOWN_ABSTRACT_COMPATIBLE",
            "UNKNOWN_RESOURCE_LIMIT"),(id,out)
        record={
            "case":id,
            "status":out["status"],
            "machines":len(cert["machines"]),
            "classes":out["structural_classes"],
            "states":out.get("product_states",out.get("states")),
            "processed_groups":out.get("processed_groups"),
        }
        print("ORIGINAL_SYMMETRY_TRANSFER",json.dumps(record,sort_keys=True))
        results.append(record)
    Path("hybrid8-transfer.json").write_text(json.dumps(results,indent=2)+"\n")
    print("ALL_SYMMETRY_TESTS_PASS")
