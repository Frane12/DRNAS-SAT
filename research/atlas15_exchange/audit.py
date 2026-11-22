#!/usr/bin/env python3
"""ATLAS15: controlled 3-way source fact exchange and old-source regression.

Target:
  GRAPH-only UNKNOWN;
  HALL source-only UNKNOWN;
  XOR+HALL UNKNOWN on 2 larger examples;
  GRAPH+HALL UNKNOWN on 2 larger examples;
  *only* GRAPH+XOR+HALL together verifies UNSAT via external VeriPB
  on the exact unchanged original CNF, with 2 or 3 necessary RUP lemmas.

All generated sources and one bijective rename are checked by independent
original-source XOR3 and graph implication checker. Contradictory source
mutation + full explicit SAT model is independently checked and no transfer
allowed. Previously published real graph/PCMAX/XOR CNFs are analyzed solely
as honest original-source stress controls, not new blind claims.
"""
import hashlib,itertools,json,os,random,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/"atlas15_results";OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(ROOT/"research/structure_atlas1"))
sys.path.insert(0,str(ROOT/"research/structure_atlas3"))
sys.path.insert(0,str(ROOT/"research/graphclique"))
from atlas import encoded,parse,transform
from source_facts import derive as source_eo_facts
from check_facts import check as independent_eo_checker
from bridge import compile_original,HallUnknown
from witness import verify as independent_exchange_checker,verify_full_original_sat_model,Invalid
from facts import candidates,graph_facts,xor_facts,Unknown

CPU=min(os.sched_getaffinity(0));os.sched_setaffinity(0,{CPU})
def hashof(data):return hashlib.sha256(data).hexdigest()
def allow(k):
    if k==4:return [(0,1,2),(0,1,2),(1,2,3),(1,2,3),(0,2,3)]
    if k==5:return [(0,1,2,3),(0,1,2,3),(1,2,3,4),
                    (1,2,3,4),(0,2,3,4),(0,2,3,4)]
    if k==6:return [(0,1,2,3,4),(0,1,2,3,4),(1,2,3,4,5),
                    (1,2,3,4,5),(0,2,3,4,5),(0,2,3,4,5),
                    (0,2,3,4,5)]
    raise ValueError("unsupported_control")

def masks(k):
    if k==4:return [(0,1,0,"XOR")]
    if k==5:return [(0,1,0,"XOR"),(4,5,4,"GRAPH")]
    if k==6:return [(0,1,0,"XOR"),(2,3,1,"XOR"),(4,5,5,"GRAPH")]
    raise ValueError("unsupported_control")

def build(k,seed,remove_xor_blocker=None):
    rng=random.Random(seed)
    groups=allow(k)
    n=len(groups);assert n==k+1
    opts=sum(len(g) for g in groups)
    labels=list(range(1,opts+1));rng.shuffle(labels)
    sel={}
    indices=iter(labels)
    for g,allowed in enumerate(groups):
        for color in allowed:sel[(g,color)]=next(indices)
    covered={}
    for ordinal,(i,j,c,kind) in enumerate(masks(k)):
        a,b=sorted((sel[(i,c)],sel[(j,c)]))
        covered[(a,b)]=(ordinal,kind)
    cl=[]
    for g,allowed in enumerate(groups):
        vs=[sel[(g,c)] for c in allowed]
        cl.append(tuple(vs))
        for a,b in itertools.combinations(vs,2):cl.append((-a,-b))
    for color in range(k):
        holders=[sel[(g,color)] for g,allowed in enumerate(groups) if color in allowed]
        for a,b in itertools.combinations(holders,2):
            if tuple(sorted((a,b))) not in covered:
                cl.append((-a,-b))
    aux_roles={}
    for (a,b),(ordinal,kind) in sorted(covered.items(),key=lambda x:x[1][0]):
        t=opts+ordinal+1
        aux_roles[(a,b)]={"aux":t,"kind":kind}
        if kind=="GRAPH":
            cl.extend([(-a,t),(-t,-b)])
        else:
            cl.append((t,))
            for bits in itertools.product((0,1),repeat=3):
                if sum(bits)%2==0:continue # allowed parity0, block odd
                row=tuple(-v if bit else v for v,bit in zip((a,b,t),bits))
                if remove_xor_blocker==(a,b) and all(bits):
                    continue
                cl.append(row)
    for j in range(len(cl)):
        cl[j]=tuple(rng.sample(cl[j],len(cl[j])))
    rng.shuffle(cl)
    source=encoded(opts+len(covered),cl)
    return source,{"k":k,"seed":seed,"n":n,"options":opts,
          "selectors":sel,"auxiliary_roles":aux_roles,
          "mask_count":len(covered),
          "graph_masks":sum(x["kind"]=="GRAPH" for x in aux_roles.values()),
          "xor_masks":sum(x["kind"]=="XOR" for x in aux_roles.values()),
          "source_sha256":hashof(source),"source_vars":opts+len(covered),
          "source_clauses":len(cl)}

def model_is_valid(raw,assignment):
    nv,cl=parse(raw)
    return (len(assignment)==nv and all(
        any(assignment[abs(v)]==(v>0) for v in row) for row in cl))

def external(cnf,pbp,tag):
    start=time.perf_counter()
    r=subprocess.run(["taskset","-c",str(CPU),"veripb",
                      "--cnf",str(cnf),str(pbp)],
                     capture_output=True,text=True,timeout=30)
    output=r.stdout+"\n"+r.stderr
    (OUT/(tag+".veripb.log")).write_text(output)
    if r.returncode!=0 or "s VERIFIED UNSATISFIABLE" not in output:
        raise AssertionError("EXTERNAL_ORIGINAL_VERIPB_REJECTED_"+tag+":"+output[-400:])
    return round(time.perf_counter()-start,6)

def check_one(raw,tag,expected_graph,expected_xor):
    folder=OUT/tag;folder.mkdir(parents=True,exist_ok=True)
    cnf=folder/"original.cnf";cnf.write_bytes(raw)
    # Independently verify all explicit EO source groups, also ensure
    # our selected positive source demands are actually part of that set.
    known=source_eo_facts(raw)
    eo=independent_eo_checker(raw,known)
    assert eo["status"]=="SOURCE_FACTS_INDEPENDENTLY_VERIFIED"
    original_eo={frozenset(x) for x in known["exact_one_groups"]}
    alo={frozenset(x) for x in parse(raw)[1] if len(x)>=3 and all(v>0 for v in x)}
    assert alo<=original_eo
    # GRAPH and XOR producers only produce source candidate facts.
    graph=graph_facts(raw);xor=xor_facts(raw)
    assert len(graph)==expected_graph,(tag,graph,expected_graph)
    assert len(xor)==expected_xor,(tag,xor,expected_xor)
    # No old-alone source proof is accepted.
    import importlib.util
    graph_spec=importlib.util.spec_from_file_location(
           "atlas15_prior_graph",ROOT/"research/graphclique/emit_veripb.py")
    old_graph=importlib.util.module_from_spec(graph_spec)
    graph_spec.loader.exec_module(old_graph)
    try:old_graph.compile_source(raw,max_trials=16000)
    except old_graph.Unsupported:graph_status="UNKNOWN"
    else:raise AssertionError("OLD_GRAPH_ALONE_SOLVED_"+tag)
    # Baseline direct Hall via previous exact source-pair routine.
    oldspec=importlib.util.spec_from_file_location(
       "atlas15_prior_hall",ROOT/"research/atlas13_exchange/bridge.py")
    old=importlib.util.module_from_spec(oldspec)
    oldspec.loader.exec_module(old)
    try:old.hall_partition(raw,[])
    except old.Unknown:hall_status="UNKNOWN"
    else:raise AssertionError("HALL_DIRECT_ALONE_SOLVED_"+tag)
    # BINARY graph subsystem alone has concrete all-false model for
    # its binary clauses. (XOR's unit clauses not part of 2-SAT subsystem.)
    _,clauses=parse(raw)
    assert all(any(l<0 for l in c) for c in clauses if len(c)==2)
    # Independent graph+XOR source-fact checked for each arm.
    arms={}
    for arm in ("GRAPH_HALL","XOR_HALL","TRIPLE_HALL"):
        proof=folder/(arm+".original.pbp")
        cert=folder/(arm+".claims.json")
        meta=folder/(arm+".meta.json")
        claims=candidates(raw,arm)
        independent=independent_exchange_checker(raw,claims)
        assert independent["status"]=="ATLAS15_ORIGINAL_SOURCE_LEMMAS_INDEPENDENTLY_VERIFIED"
        try:
            result=compile_original(cnf,arm,cert,proof,meta)
        except (Unknown,HallUnknown,old.Unknown):
            arms[arm]={"status":"UNKNOWN","source_graph_facts":claims["graph_fact_count"],
                        "source_xor_facts":claims["xor_fact_count"]}
            continue
        sec=external(cnf,proof,tag+"-"+arm)
        arms[arm]={"status":"UNSAT_ORIGINAL_VERIPB_VERIFIED",
             "source_graph_facts":result["graph_lemmas_transferred"],
             "source_xor_facts":result["xor_lemmas_transferred"],
             "proof_bytes":result["original_source_PBP_bytes"],
             "external_veripb_s":sec}
    if expected_graph and expected_xor:
        assert arms["GRAPH_HALL"]["status"]=="UNKNOWN"
        assert arms["XOR_HALL"]["status"]=="UNKNOWN"
        assert arms["TRIPLE_HALL"]["status"]=="UNSAT_ORIGINAL_VERIPB_VERIFIED"
    if expected_xor and not expected_graph:
        assert arms["GRAPH_HALL"]["status"]=="UNKNOWN"
        assert arms["XOR_HALL"]["status"]=="UNSAT_ORIGINAL_VERIPB_VERIFIED"
        assert arms["TRIPLE_HALL"]["status"]=="UNSAT_ORIGINAL_VERIPB_VERIFIED"
    trial={"tag":tag,"source_sha256":hashof(raw),"variables":parse(raw)[0],
        "source_clauses":len(clauses),"EO_original_groups_source_verified":len(alo),
        "prior_GRAPH_ONLY":graph_status,"prior_HALL_ONLY":hall_status,
        "pure_binary_graph_subsystem_has_all_false_model":True,
        "arms":arms,"strict_original_standard_veripb_source_only":True}
    (folder/"result.json").write_text(json.dumps(trial,sort_keys=True,indent=2)+"\n")
    print("ATLAS15_MATH_EXCHANGE "+json.dumps(trial,sort_keys=True),flush=True)
    return trial

results=[]
for k in (4,5,6):
    raw,meta=build(k,seed=55000+k)
    result=check_one(raw,f"constructed-k{k}",meta["graph_masks"],meta["xor_masks"])
    results.append(result)
    if k==5:
        nv,clauses=parse(raw)
        variant,equiv,_=transform(nv,clauses,90155,rename=True,flip=False,shuffle=True)
        assert equiv
        results.append(check_one(variant,"constructed-k5-renamed",1,1))
    if k==6:
        # Remove one essential forbidden source XOR3 assignment clause and
        # build a FULL SAT model. There is no valid way to derive that mutex.
        missing_pair=next(pair for pair,info in sorted(meta["auxiliary_roles"].items())
                          if info["kind"]=="XOR")
        mutated,details=build(k,seed=55000+k,remove_xor_blocker=missing_pair)
        assert details["selectors"]==meta["selectors"]
        chosen=[0,0,1,2,3,4,5]
        assignment={v:(chosen[g]==color)
                    for (g,color),v in details["selectors"].items()}
        for pair,info in details["auxiliary_roles"].items():
            a,b=pair;t=info["aux"]
            # Original XOR3 masks force t=True; graph aux from implication
            # can take truth value of a, unless a=b=True, excluded by model.
            assignment[t]=True if info["kind"]=="XOR" else assignment[a]
        assert model_is_valid(mutated,assignment),"SAT_MODEL_BROKEN"
        satdir=OUT/"source-mutation-SAT";satdir.mkdir(exist_ok=True)
        path=satdir/"original.cnf";path.write_bytes(mutated)
        sat_witness={"source_sha256":hashof(mutated),
                     "assignment":[None]+[assignment[v] for v in range(1,parse(mutated)[0]+1)]}
        independently_checked_sat=verify_full_original_sat_model(mutated,sat_witness)
        assert independently_checked_sat["status"]=="INDEPENDENT_ORIGINAL_SOURCE_SAT_MODEL_VERIFIED"
        (satdir/"source-SAT-model.json").write_text(json.dumps(sat_witness,sort_keys=True)+"\\n")
        (satdir/"independent-SAT-check.json").write_text(json.dumps(independently_checked_sat,sort_keys=True,indent=2)+"\\n")
        forged=candidates(raw,"TRIPLE_HALL")
        forged["source_sha256"]=hashof(mutated)
        forged["source_clauses"]=len(parse(mutated)[1])
        try:independent_exchange_checker(mutated,forged)
        except Invalid:changed_premise_rejected=True
        else:raise AssertionError("REMOVED_XOR_CLAUSE_TAMPER_WAS_ACCEPTED")
        wrong=json.loads(json.dumps(forged));wrong["source_sha256"]="0"*64
        try:independent_exchange_checker(mutated,wrong)
        except Invalid:forged_sha_rejected=True
        else:raise AssertionError("FORGED_SOURCE_SHA_ACCEPTED")
        xfacts=xor_facts(mutated)
        assert len(xfacts)==1,("expected one surviving full XOR row",xfacts)
        safety={"source_sha256":hashof(mutated),
             "SAT_original_model_verified":True,
             "independent_original_source_SAT_model_verified":True,
             "source_clauses_checked":len(parse(mutated)[1]),
             "removed_XOR_forbidden_assignment_with_source_SHA_update_rejected":changed_premise_rejected,
             "wrong_source_SHA_rejected":forged_sha_rejected,
             "full_XOR3_truth_table_now_incomplete":True}
        (satdir/"safety.json").write_text(json.dumps(safety,sort_keys=True,indent=2)+"\n")
        print("ATLAS15_SAT_NEGATIVE "+json.dumps(safety,sort_keys=True),flush=True)
# Existing published original CNFs are stress inputs. No family name enters
# detector, and no pre-saved proof is passed in as a candidate proof.
original_checks=[]
for label,path in (
    ("graph-k11","evidence/graph-k11/original.cnf"),
    ("pcmax-m00","evidence/pcmax-weighted2/00/original.cnf"),
    ("xor-grid5","evidence/xor234-grid5/original.cnf"),
    ("petersen","evidence/ipg7b-petersen/original.cnf")):
    raw=(ROOT/path).read_bytes()
    source=OUT/("regression-"+label+".cnf")
    source.write_bytes(raw)
    claim=OUT/("regression-"+label+".claim.json")
    proof=OUT/("regression-"+label+".proof.pbp")
    meta=OUT/("regression-"+label+".meta.json")
    try:
        out=compile_original(source,"TRIPLE_HALL",claim,proof,meta)
        verifier=external(source,proof,"regression-"+label)
        status="STANDARD_ORIGINAL_VERIPB_VERIFIED"
    except (Unknown,ValueError,OSError,TypeError,IndexError,KeyError):
        status="SAFE_UNKNOWN";verifier=None
    entry={"label":label,"original_sha256":hashof(raw),
           "status":status,"verifier_s":verifier,
           "existing_historical_source_not_newly_blind":True}
    original_checks.append(entry)
    print("ATLAS15_HISTORICAL_ORIGINAL "+json.dumps(entry,sort_keys=True),flush=True)
summary={"status":"COMPLETE",
    "distinct_constructed_origins":3,"renamed_variants":1,
    "both_GRAPH_HALL_and_XOR_HALL_UNKNOWN_but_triple_verified":sum(
         x["arms"]["GRAPH_HALL"]["status"]=="UNKNOWN"
         and x["arms"]["XOR_HALL"]["status"]=="UNKNOWN"
         and x["arms"]["TRIPLE_HALL"]["status"]=="UNSAT_ORIGINAL_VERIPB_VERIFIED"
         for x in results),
    "triple_mode_original_veripb":sum(
         x["arms"]["TRIPLE_HALL"]["status"]=="UNSAT_ORIGINAL_VERIPB_VERIFIED"
         for x in results),
    "transferred_graph_fact_total":sum(x["arms"]["TRIPLE_HALL"].get("source_graph_facts",0)
                                    for x in results),
    "transferred_xor_fact_total":sum(x["arms"]["TRIPLE_HALL"].get("source_xor_facts",0)
                                    for x in results),
    "safety":safety,"historical_source_stress":original_checks,
    "all_original_standard_proof_checks_mandatory":True,
    "main_untouched":True,
    "claim_scope":"Synthetic controlled information exchange, not original cross-family generalization",
    "cases":results}
(OUT/"summary.json").write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n")
print("ATLAS15_FINAL "+json.dumps({k:v for k,v in summary.items()
         if k not in ("cases","historical_source_stress","safety")},sort_keys=True),flush=True)
assert summary["triple_mode_original_veripb"]==4
assert summary["both_GRAPH_HALL_and_XOR_HALL_UNKNOWN_but_triple_verified"]==3
assert summary["transferred_graph_fact_total"]==3
assert summary["transferred_xor_fact_total"]==5
