#!/usr/bin/env python3
"""ATLAS23 independent semantic checker; does not import closure solver."""
import argparse,copy,hashlib,itertools,json
from pathlib import Path
V=("x","y0","y1","z0","z1")
SCOPES={"GF2":("x","y0"),"PCMAX":("x","z0"),"ARITH2":("y0","y1","z0","z1")}
ORDER=("GF2","ARITH2","PCMAX")

def holds(m,a,cap,inc):
    if m=="GF2": return (a["x"]+a["y0"])%2==0
    if m=="PCMAX": return sum(a[n] for n in ("x","z0"))<=cap
    if m=="ARITH2": return (a["y0"]+2*a["y1"]+inc-a["z0"]-2*a["z1"])%4==0
    raise AssertionError("unknown module")

def assignments():
    return [dict(zip(V,b)) for b in itertools.product((0,1),repeat=5)]

def sat_cnf(a,clauses):
    return all(any(a[V[abs(l)-1]]==int(l>0) for l in c) for c in clauses)

def check(source,cert):
    assert cert["version"]=="ATLAS23-v1" and cert["type"]=="synthetic-structured"
    assert cert["variables"]==list(V) and cert["module_order"]==list(ORDER)
    assert {k:tuple(v) for k,v in cert["scopes"].items()}==SCOPES
    cap,inc=cert["capacity"],cert["increment"]
    assert cap in range(3) and inc in range(4)
    assert hashlib.sha256(source).hexdigest()==cert["cnf_sha256"]
    header=None;clauses=[]
    for s in source.decode().splitlines():
        if s.startswith("c") or not s.strip():continue
        parts=s.split()
        if parts[0]=="p":
            assert header is None and parts[:2]==["p","cnf"] and len(parts)==4
            header=(int(parts[2]),int(parts[3]))
        else:
            nums=list(map(int,parts))
            assert nums and nums[-1]==0 and 0 not in nums[:-1]
            assert all(1<=abs(l)<=5 for l in nums[:-1])
            clauses.append(nums[:-1])
    assert header==(5,len(clauses)) and cert["clause_count"]==len(clauses)
    space=assignments()
    assert all(sat_cnf(a,clauses)==all(holds(m,a,cap,inc) for m in ORDER) for a in space)
    subset_sat={}
    for k in (1,2,3):
        for subset in itertools.combinations(ORDER,k):
            subset_sat["+".join(subset)]=any(all(holds(m,a,cap,inc) for m in subset) for a in space)
    facts={};conflicts=0
    for i,e in enumerate(cert["events"]):
        m=e["module"];assert m in ORDER
        premises={n:facts[n] for n in SCOPES[m] if n in facts}
        assert premises==e["premises"]
        local=[a for a in space if holds(m,a,cap,inc)
               and all(a[n]==v for n,v in premises.items())]
        if e["kind"]=="infer":
            n,v=e["variable"],e["value"]
            assert n in SCOPES[m] and n not in facts and v in (0,1)
            assert local and all(a[n]==v for a in local)
            facts[n]=v
        elif e["kind"]=="contradiction":
            assert not local and i==len(cert["events"])-1
            conflicts+=1
        else:raise AssertionError("unexpected trace event")
    assert facts==cert["facts"]
    status=cert["status"]
    if status=="UNSAT_STRUCTURAL_TRACE":
        assert conflicts==1 and not subset_sat["+".join(ORDER)]
    elif status=="SAT_MODEL_CHECKED":
        a=cert["sat_model"]
        assert conflicts==0 and isinstance(a,dict) and set(a)==set(V)
        assert all(v in (0,1) for v in a.values()) and sat_cnf(a,clauses)
    elif status=="UNKNOWN":
        assert conflicts==0 and cert["sat_model"] is None
    else:raise AssertionError("unknown status")
    assert cert["no_cdcl_fallback"] and not cert["standard_drat_lrat_veripb_proof"]
    return {"audit":"PASS","status":status,"proper_subsets_all_sat":
            all(v for k,v in subset_sat.items() if k.count("+")<2),
            "full_three_way_sat":subset_sat["+".join(ORDER)],
            "subset_sat":subset_sat,"checked_assignments":len(space),
            "verified_inferences":sum(e["kind"]=="infer" for e in cert["events"]),
            "verified_conflicts":conflicts,"standard_unsat_proof":False}

def selftest():
    from closure import run
    cnf,cert=run(0,1)
    result=check(cnf.encode(),cert)
    assert result["status"]=="UNSAT_STRUCTURAL_TRACE"
    assert result["proper_subsets_all_sat"] and not result["full_three_way_sat"]
    for cap in range(3):
        for inc in range(4):
            c,proof=run(cap,inc)
            audit=check(c.encode(),proof)
            assert proof["status"]==("UNSAT_STRUCTURAL_TRACE" if cap==0 and inc%2 else "SAT_MODEL_CHECKED")
    c,proof=run(1,1,budget=0)
    assert check(c.encode(),proof)["status"]=="UNKNOWN"
    for change in ("source","literal","premises","module","model"):
        src=cnf.encode();bad=copy.deepcopy(cert)
        if change=="source":src+=b"c changed\n"
        elif change=="literal":
            next(e for e in bad["events"] if e["kind"]=="infer")["value"]^=1
        elif change=="premises":bad["events"][-1]["premises"]={}
        elif change=="module":bad["events"][-1]["module"]="GF2"
        else:
            c,p=run(1,1);src=c.encode();bad=p;bad["sat_model"]["z0"]^=1
        try:check(src,bad)
        except AssertionError:pass
        else:raise AssertionError("tampered proof incorrectly accepted: "+change)
    assert all(len(line.split())>=3 for line in cnf.splitlines() if not line.startswith(("c","p")))
    result.update({"grid_cases_checked":12,"negative_controls_rejected":5,
                   "source_initial_unit_clauses":0,"unknown_cap_control":"PASS"})
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--cnf",type=Path)
    p.add_argument("--trace",type=Path)
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--out",type=Path)
    a=p.parse_args()
    if a.selftest:result=selftest()
    else:
        assert a.cnf and a.trace
        result=check(a.cnf.read_bytes(),json.loads(a.trace.read_text()))
    if a.out:
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,sort_keys=True))
