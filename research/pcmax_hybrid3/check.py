#!/usr/bin/env python3
"""Independent source-CNF checker of DRNAS MODQ1 / Fano experiment.

Validates source DIMACS, selected exact-one clauses, asserted root and
terminal clauses, every BDD edge and DAG rank, distinct states/selectors,
the FULL BDD-accepted language, and modular DP over accepted BDD paths.

The checker cannot certify the separate VeriPB proof; that file MUST be
run against the unchanged CNF with an external VeriPB 3.x checker.
"""
import argparse, hashlib, itertools, json
from pathlib import Path

class InvalidCertificate(ValueError):
    pass

def need(cond,why):
    if not cond:raise InvalidCertificate(why)

def parse_dimacs(data):
    vars_=declared=None
    clauses=[]
    current=[]
    for line in data.decode('ascii').splitlines():
        fields=line.split()
        if not fields or fields[0]=='c':continue
        if fields[0]=='p':
            need(vars_ is None and len(fields)==4 and fields[1]=='cnf',
                 "invalid DIMACS header")
            vars_,declared=map(int,fields[2:])
            need(vars_>=1 and declared>=0,"invalid dimensions")
            continue
        need(vars_ is not None,"clause before header")
        for token in fields:
            v=int(token)
            if v:
                need(1<=abs(v)<=vars_,"literal exceeds header")
                current.append(v)
            else:
                clauses.append(frozenset(current))
                current=[]
    need(vars_ is not None and not current and declared==len(clauses),
         "invalid final clause count")
    return vars_,set(clauses),len(clauses)

def expected_patterns(n,kind):
    if kind=='fano':
        need(n==7,"Fano test requires seven job groups")
        lines={tuple(sorted((a-1,b-1,(a^b)-1)))
               for a in range(1,8) for b in range(a+1,8)}
        need(len(lines)==7,"bad Fano design")
        return {0}|{sum(1<<v for v in row) for row in lines}
    if kind=='sat-control':
        need(n==6,"control requires six job groups")
        return {0}|{sum(1<<v for v in pair)
                     for pair in itertools.combinations(range(n),2)}
    raise InvalidCertificate("unknown family")

def inspect_machine(machine,clauses,nvars,group_map,n):
    order=machine['variable_order']
    need(len(order)==n and len(set(order))==n,"bad selector order")
    need(all(v in group_map for v in order),"BDD contains ungrouped selector")
    need(len({group_map[v] for v in order})==n,"BDD omits a job group")
    rank={v:i for i,v in enumerate(order)}
    root=machine['root']
    t=machine['true_terminal']
    f=machine['false_terminal']
    need(len({root,t,f})==3,"bad root/terminal names")
    need(frozenset((root,)) in clauses
         and frozenset((t,)) in clauses
         and frozenset((-f,)) in clauses,"missing BDD root/terminal source units")
    nodes={}
    for q,x,low,high in machine['transitions']:
        need(q not in nodes and x in rank,"duplicate state/unknown selector")
        need(all(type(z)==int and 1<=z<=nvars for z in (q,x,low,high)),
             "BDD variable outside CNF")
        need(q not in {x,low,high} and x not in {low,high},
             "aliased BDD state")
        need(frozenset((-q,x,low)) in clauses,
             "missing false branch source clause")
        need(frozenset((-q,-x,high)) in clauses,
             "missing true branch source clause")
        nodes[q]=(x,low,high)
    need(root in nodes and t not in nodes and f not in nodes,
         "invalid BDD root and terminals")
    states=set(nodes)|{t,f}
    need(not (states & set(order)),"state and selector variable alias")
    nr={q:rank[entry[0]] for q,entry in nodes.items()}
    nr[t]=nr[f]=len(order)
    for q,(x,l,h) in nodes.items():
        need(l in states and h in states,"unlisted BDD child")
        need(nr[l]>rank[x] and nr[h]>rank[x],"cyclic/unordered BDD graph")

    def accepts(mask):
        q=root
        steps=0
        while q in nodes:
            steps+=1
            need(steps<=len(nodes),"BDD cycle at runtime")
            x,l,h=nodes[q]
            q=h if ((mask>>group_map[x])&1) else l
        return q==t

    # The full set of accepted job subsets is independently checked,
    # not merely sampled or trusted from the JSON.
    accepted={m for m in range(1<<n) if accepts(m)}

    def residue_dp(modulus):
        dp={t:{0},f:set()}
        for q in sorted(nodes,key=lambda q:nr[q],reverse=True):
            x,l,h=nodes[q]
            vals=set()
            for child,take in ((l,0),(h,1)):
                valset=set(dp[child])
                # Every skipped selector is unconstrained by this edge.
                for i in range(rank[x]+1,nr[child]):
                    add=1%modulus
                    valset|={(v+add)%modulus for v in list(valset)}
                vals|={(v+take)%modulus for v in valset}
            dp[q]=vals
        vals=set(dp[root])
        for _ in range(nr[root]):
            vals|={(v+1)%modulus for v in list(vals)}
        return vals

    return {
        "accepted":accepted,
        "states":states,
        "selectors":set(order),
        "residues_mod2":residue_dp(2),
        "residues_mod3":residue_dp(3),
        "accepts":accepts,
    }

def check(data,cert):
    need(hashlib.sha256(data).hexdigest()==cert["source_sha256"],
         "CNF hash differs from source certificate")
    nvars,clauses,nclauses=parse_dimacs(data)
    groups=cert["groups"]
    n=len(groups)
    need(n>0,"no groups")
    need(cert["required"]==n,"incorrect job count")
    need(len(cert["machines"])==3,"requires three independent machine BDDs")
    group_map={}
    for i,group in enumerate(groups):
        need(len(group)==3 and len(set(group))==3,
             "invalid exact-one job group")
        need(frozenset(group) in clauses,"missing source at-least-one clause")
        for x,y in itertools.combinations(group,2):
            need(frozenset((-x,-y)) in clauses,
                 "missing source at-most-one clause")
        for v in group:
            need(1<=v<=nvars and v not in group_map,"group variable invalid/duplicated")
            group_map[v]=i

    machines=[]
    all_states=set()
    all_sel=set()
    for m in cert["machines"]:
        info=inspect_machine(m,clauses,nvars,group_map,n)
        need(not all_states.intersection(info["states"]),
             "machines reuse BDD state variables")
        need(not all_sel.intersection(info["selectors"]),
             "machines reuse selectors")
        all_states|=info["states"]
        all_sel|=info["selectors"]
        machines.append(info)
    need(all_sel==set(group_map),"BDD machines do not cover job groups")
    need(not all_states.intersection(all_sel),
         "machine state also used as a selector")
    expected=expected_patterns(n,cert["kind"])
    need(set(cert["claimed_local_patterns"])==expected,
         "claimed local patterns inconsistent with named family")
    for i,info in enumerate(machines):
        need(info["accepted"]==expected,
             f"BDD machine {i} accepts unexpected local patterns")
    modulus=cert["modulus"]
    need(type(modulus)==int and 2<=modulus<=13,
         "modulus must be a small exact integer")
    # General MODQ DP operates on machine residue sets.
    def global_residues(key):
        acc={0}
        for m in machines:
            acc={(x+y)%modulus for x in acc for y in m[key]}
        return acc
    local_mod=[{m.bit_count()%modulus for m in z["accepted"]} for z in machines]
    global_mod={0}
    for choices in local_mod:
        global_mod={(x+y)%modulus for x in global_mod for y in choices}
    target=n%modulus
    status="UNSAT_MODULAR_STRUCTURAL_CERTIFICATE_VERIFIED" if target not in global_mod else "INCONCLUSIVE"
    out={
        "status":status,"kind":cert["kind"],
        "source_sha256":cert["source_sha256"],
        "source_vars":nvars,"source_clauses":nclauses,
        "jobs":n,"machines":len(machines),
        "accepted_local_configs":len(expected),
        "modulus":modulus,"global_residues":sorted(global_mod),
        "required_residue":target,
        "per_machine_mod2":[sorted(m["residues_mod2"]) for m in machines],
        "per_machine_mod3":[sorted(m["residues_mod3"]) for m in machines],
    }
    if cert["kind"]=="fano":
        need(n==7 and modulus==3,"wrong Fano modulus")
        patterns=expected-{0}
        witness=[]
        for pivot in range(n):
            through=[p for p in patterns if (p>>pivot)&1]
            need(len(through)==3,"Fano point has wrong incidence")
            chosen_xor=0
            counts=[0]*n
            for p in through:
                chosen_xor^=p
                for i in range(n):
                    counts[i]+=(p>>i)&1
            need(chosen_xor==(1<<n)-1,"3-line GF2 witness fails")
            need(all(counts[i]==(3 if i==pivot else 1)
                     for i in range(n)),"GF2 witness multiplicities wrong")
            need(all(machines[j]["accepts"](through[j])
                     for j in range(3)),"GF2 witness not accepted by BDD")
            witness.append([int(p) for p in through])
        out["all_positive_weight_GF2_obstruction"]="VERIFIED_BY_7_THREE_LINE_WITNESSES"
        out["fractional_cover"]="EACH_MACHINE_EMPTY_2/9_AND_EACH_OF_7_LINES_1/9"
        out["three_line_witnesses"]=witness
    return out

def verify_explicit_model(data,cert,assignment):
    """Independently check every DIMACS clause for a SAT control model."""
    nvars,clauses,_=parse_dimacs(data)
    n=len(cert["groups"])
    need(len(assignment)==n,"bad assignment length")
    true_vars=set()
    for i,j in enumerate(assignment):
        need(j in range(3),"bad machine assignment")
        true_vars.add(cert["groups"][i][j])
    for j,machine in enumerate(cert["machines"]):
        true_vars.add(machine["true_terminal"])
        nodes={q:(x,l,h) for q,x,l,h in machine["transitions"]}
        q=machine["root"]
        while q in nodes:
            true_vars.add(q)
            x,l,h=nodes[q]
            q=h if x in true_vars else l
        need(q==machine["true_terminal"],"proposed model rejected")
    need(all(any(((abs(lit) in true_vars)==(lit>0))
                 for lit in clause) for clause in clauses),
         "SAT model fails source clause")
    return {"status":"SAT_SOURCE_MODEL_VERIFIED",
            "true_variables":len(true_vars),"source_vars":nvars,
            "source_clauses":len(clauses)}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--cnf",type=Path,required=True)
    p.add_argument("--certificate",type=Path,required=True)
    a=p.parse_args()
    try:
        print(json.dumps(check(a.cnf.read_bytes(),
                               json.loads(a.certificate.read_text())),
                         sort_keys=True,indent=2))
    except (InvalidCertificate,KeyError,TypeError,ValueError) as ex:
        print(json.dumps({"status":"INVALID_CERTIFICATE","reason":str(ex)}))
        raise SystemExit(1)
