#!/usr/bin/env python3
"""Independent checker for parity-conditioned capacity witnesses against SOURCE CNF.
Checks only soundness of a structural UNSAT certificate, not existence of a
standard VeriPB proof. All graph edges, units and exact-one groups are checked
as clauses of the byte-exact source CNF before any dynamic programming.
"""
import argparse, hashlib, json
from itertools import combinations
from pathlib import Path

class Invalid(ValueError):
    pass

def req(cond,msg):
    if not cond: raise Invalid(msg)

def read_cnf(data):
    nvars=ncls=None
    clauses=[]
    acc=[]
    for line in data.decode('ascii').splitlines():
        tokens=line.split()
        if not tokens or tokens[0]=='c':continue
        if tokens[0]=='p':
            req(nvars is None and len(tokens)==4 and tokens[1]=='cnf',"bad DIMACS header")
            nvars,ncls=map(int,tokens[2:])
            req(nvars>0 and ncls>=0,"bad DIMACS dimensions")
            continue
        req(nvars is not None,"clauses before header")
        for s in tokens:
            v=int(s)
            if v==0:
                req(all(0<abs(x)<=nvars for x in acc),"out of range literal")
                clauses.append(frozenset(acc))
                acc=[]
            else:acc.append(v)
    req(nvars is not None and not acc and len(clauses)==ncls,"bad clause count")
    return nvars,set(clauses),ncls

def maxset(old,index,value):
    if old[index] is None or value>old[index]:
        old[index]=value

def add_optional_selector(best,var,weights,parity_vars):
    out=[None,None]
    wt=weights.get(var,0)
    pa=int(var in parity_vars)
    for p in (0,1):
        if best[p] is not None:
            maxset(out,p,best[p])
            maxset(out,p^pa,best[p]+wt)
    return out

def machine_caps(machine,clauses,nvars,weights,parity_vars):
    order=machine['variable_order']
    req(len(order)>0 and len(set(order))==len(order),"bad selector order")
    req(all(type(x)==int and 1<=x<=nvars for x in order),"selector outside CNF")
    ranks={v:i for i,v in enumerate(order)}
    nodes={}
    for row in machine['transitions']:
        req(len(row)==4 and all(type(x)==int and 1<=x<=nvars for x in row),
            "invalid BDD row")
        q,x,lo,hi=row
        req(q not in nodes and x in ranks,"duplicate BDD node or unknown selector")
        req(len({q,x,lo})==3 and len({q,x,hi})==3,"aliased state/selector")
        req(frozenset((-q,x,lo)) in clauses,"missing source false-edge clause")
        req(frozenset((-q,-x,hi)) in clauses,"missing source true-edge clause")
        nodes[q]=(x,lo,hi)
    root,t,f=(machine[k] for k in ('root','true_terminal','false_terminal'))
    req(root in nodes and t!=f and t not in nodes and f not in nodes,
        "bad root/terminal")
    req(frozenset((root,)) in clauses and frozenset((t,)) in clauses
        and frozenset((-f,)) in clauses,"source root/terminal units missing")
    states=set(nodes)|{t,f}
    req(not(states & set(order)),"state overlaps selector")
    rank_node={q:ranks[row[0]] for q,row in nodes.items()}
    rank_node[t]=rank_node[f]=len(order)
    for q,(x,lo,hi) in nodes.items():
        req(lo in states and hi in states,"unknown BDD child")
        req(rank_node[lo]>ranks[x] and rank_node[hi]>ranks[x],"non-DAG BDD")
    memo={t:[0,None],f:[None,None]}
    for q in sorted(nodes,key=lambda k:rank_node[k],reverse=True):
        x,lo,hi=nodes[q]
        r=ranks[x]
        cap=[None,None]
        for child,take in ((lo,0),(hi,1)):
            branch=memo[child][:]
            for pos in range(r+1,rank_node[child]):
                branch=add_optional_selector(branch,order[pos],weights,parity_vars)
            for parity in (0,1):
                if branch[parity] is not None:
                    np=parity^(int(x in parity_vars) if take else 0)
                    maxset(cap,np,branch[parity]+(weights.get(x,0) if take else 0))
        memo[q]=cap
    cap=memo[root][:]
    for pos in range(rank_node[root]):
        cap=add_optional_selector(cap,order[pos],weights,parity_vars)
    req(cap!=[None,None],"no accepting machine path")
    req(cap==machine['claimed_parity_capacities'],
        f"false claimed machine caps {machine['claimed_parity_capacities']} != {cap}")
    return cap,states,set(order),{q:row for q,row in nodes.items()}

def accepted(pattern,machine,groups):
    """Test any given selector assignment against the certified graph."""
    order=machine['variable_order']
    selected=set(pattern)
    enabled=set()
    for i, group in enumerate(groups):
        members=set(group)&set(order)
        req(len(members)==1,'fractional group is not uniquely mapped to machine')
        if i in selected: enabled.update(members)
    rows={q:(x,l,h) for q,x,l,h in machine['transitions']}
    q=machine['root']
    while q in rows:
        x,l,h=rows[q]
        q=h if x in enabled else l
    return q==machine['true_terminal']

def check(cnf_data,cert):
    req(cert['source_sha256']==hashlib.sha256(cnf_data).hexdigest(),
        "original CNF SHA256 does not match")
    nvars,clauses,nclauses=read_cnf(cnf_data)
    groups=cert['selected_groups']
    wts=cert['group_weights']
    req(groups and len(groups)==len(wts),"bad groups and weights")
    req(all(type(w)==int and w>0 for w in wts),"weights must be positive integers")
    weights={}
    pids=cert['parity_group_indices']
    req(len(set(pids))==len(pids) and all(type(i)==int and 0<=i<len(groups)
        for i in pids),"bad parity group indices")
    parity_vars=set()
    for i,(group,wt) in enumerate(zip(groups,wts)):
        req(group and len(set(group))==len(group)
            and all(type(v)==int and 0<v<=nvars for v in group),
            "invalid exact-one group")
        req(frozenset(group) in clauses,"missing source at-least-one clause")
        for x,y in combinations(group,2):
            req(frozenset((-x,-y)) in clauses,
                "missing source at-most-one clause")
        for v in group:
            req(v not in weights,"overlapping exact-one groups")
            weights[v]=wt
            if i in pids:parity_vars.add(v)
    machines=cert['machines']
    req(machines and len(machines)==cert['machine_count'],"machine count mismatch")
    all_sel=set()
    all_states=set()
    caps=[]
    for m in machines:
        c,states,selectors,_=machine_caps(m,clauses,nvars,weights,parity_vars)
        req(not(all_sel & selectors),"machine selectors overlap")
        req(not(all_states & states),"machine states overlap")
        all_sel|=selectors
        all_states|=states
        caps.append(c)
    req(not(all_states & all_sel),"machine states overlap other machine selectors")
    req(set(weights)<=all_sel,"selected variable lacks machine graph")
    demand=sum(wts)
    req(cert['claimed_demand']==demand,"wrong demand")
    naive=sum(max(v for v in c if v is not None) for c in caps)
    req(naive==cert['claimed_naive_capacity'],"wrong ordinary capacity")
    # The exact-one group clauses imply the XOR parity across machine
    # selectors for the chosen groups is |selected groups| mod 2.
    target=len(pids)%2
    global_dp=[0,None]
    for cap in caps:
        nxt=[None,None]
        for a in (0,1):
            for b in (0,1):
                if global_dp[a] is not None and cap[b] is not None:
                    maxset(nxt,a^b,global_dp[a]+cap[b])
        global_dp=nxt
    improved=global_dp[target]
    req(improved==cert['claimed_parity_capacity'],
        f"wrong claimed parity-conditioned upper bound: {improved}")
    # Optional rational fractional packing witness: each of the 12 local
    # configurations has prob 1/12 on each of the 6 machines.
    fractional=cert.get('fractional_half_cover',[])
    if fractional:
        req(len(machines)==6 and len(fractional)==12,
            "unexpected fractional witness shape")
        count=[0]*len(groups)
        for p in fractional:
            req(len(set(p))==len(p) and all(type(i)==int and 0<=i<len(groups)
                for i in p),"bad fractional pattern")
            for i in p:count[i]+=1
            for m in machines:
                req(accepted(p,m,groups),"fractional pattern rejected by source BDD")
        req(all(v==2 for v in count),"fractional witness fails to cover each group")
    result={
        "status":"STRUCTURAL_HYBRID_UNSAT_CHECKED"
            if improved is None or demand>improved else "INCONCLUSIVE",
        "cnf_sha256":cert['source_sha256'],
        "source_variables":nvars,"source_clauses":nclauses,
        "exact_one_groups":len(groups),
        "machines":len(machines),
        "parity_groups":pids,
        "global_parity_target":target,
        "demand":demand,"ordinary_capacity":naive,
        "parity_conditioned_capacity":improved,
        "machine_capacities":caps,
        "fractional_cover_verified":bool(fractional),
        "external_standard_proof":"NOT_EMITTED"
    }
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--cnf',required=True,type=Path)
    p.add_argument('--certificate',required=True,type=Path)
    p.add_argument('--expect',choices=('UNSAT','INCONCLUSIVE'),required=True)
    a=p.parse_args()
    try:
        result=check(a.cnf.read_bytes(),json.loads(a.certificate.read_text()))
        expected=('STRUCTURAL_HYBRID_UNSAT_CHECKED' if a.expect=='UNSAT' else 'INCONCLUSIVE')
        req(result['status']==expected,"unexpected verdict")
        print(json.dumps(result,indent=2,sort_keys=True))
    except (Invalid,ValueError,KeyError,TypeError,IndexError) as error:
        print(json.dumps({'status':'INVALID_CERTIFICATE','error':str(error)}))
        raise SystemExit(1)

if __name__=='__main__':main()
