#!/usr/bin/env python3
"""DRNAS HYBRID9: source-checked symmetry-quotient of sparse BDD products.

Identical local SOURCE-VERIFIED BDD DAGs (up to state/variable renaming,
preserving selected group indices and relative auxiliary selector indices)
are collapsed into machine classes. Each class tracks a MULTISET of
nondeterministic local BDD frontiers rather than ordered machine tuples.
The quotient is a sound existential overapproximation of the source CNF.

UNSAT is emitted on an empty product or on a proven weighted capacity gap. Surviving configurations
are UNKNOWN, never SAT. This prototype emits no external RUP/VeriPB.
"""
import argparse
import hashlib
import json
import time
from collections import Counter
from functools import lru_cache
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"pcmax_hybrid7"))
from sparse import validate, Unsupported

def canonical_graphs(raw_machines, verified):
    # Preserve each selected-group index and distinguish auxiliary
    # selectors by their relative index in machine variable order.
    # Canonical nodes are shared by structurally identical DAGs.
    dictionary={}
    canon={0:None,1:None}
    next_id=2
    classes={}
    per_machine=[]
    for j,m in enumerate(raw_machines):
        graph=verified[j]
        nodes=graph["nodes"]
        order=m["variable_order"]
        selected=graph["selected"]
        var_to_group={v:i for i,v in selected.items()}
        aux={v:i for i,v in enumerate(v for v in order
                                       if v not in var_to_group)}
        memo={}
        def conv(q):
            nonlocal next_id
            if q==graph["t"]:return 1
            if q==graph["f"]:return 0
            if q in memo:return memo[q]
            x,lo,hi=nodes[q]
            label=("g",var_to_group[x]) if x in var_to_group else ("a",aux[x])
            key=(label,conv(lo),conv(hi))
            if key not in dictionary:
                dictionary[key]=next_id
                canon[next_id]=key
                next_id+=1
            memo[q]=dictionary[key]
            return memo[q]
        root=conv(graph["root"])
        eligible=tuple(sorted(selected))
        key=(root,eligible)
        if key not in classes:
            classes[key]={"root":root,"eligible":eligible,
                          "members":[]}
        classes[key]["members"].append(j)
        per_machine.append(root)
    return list(classes.values()),canon


def weighted_bounds(canonical_classes, canon, raw_machines, checked_machines, weights):
    """Exact local BDD maximum weighted selected-variable suffix.

    Every skipped selected selector is OPTIMISTICALLY allowed to be 1.
    Other CNF constraints can only reduce actual capacity.
    Classwise frontiers are nondeterministic and their maximum is used,
    so it is sound to add these independent upper bounds.
    """
    from functools import lru_cache
    from bisect import bisect_left
    def build_one(c):
        representative=c["members"][0]
        raw=raw_machines[representative]
        check=checked_machines[representative]
        order=raw["variable_order"]
        group_var={v:g for g,v in check["selected"].items()}
        aux={v:i for i,v in enumerate(
            v for v in order if v not in group_var)}
        rank_by_label={}
        selected_positions=[]
        for rank,v in enumerate(order):
            tag=("g",group_var[v]) if v in group_var else ("a",aux[v])
            rank_by_label[tag]=rank
            if v in group_var:
                selected_positions.append((rank,group_var[v]))
        prefix=[0]
        for v in order:
            prefix.append(prefix[-1]+(weights[group_var[v]] if v in group_var else 0))
        norder=len(order)

        def node_rank(q):
            if q in (0,1):return norder
            return rank_by_label[canon[q][0]]

        @lru_cache(maxsize=None)
        def best(q):
            if q==0:return None
            if q==1:return 0
            tag,lo,hi=canon[q]
            r=node_rank(q)
            local_w=weights[tag[1]] if tag[0]=="g" else 0
            choices=[]
            for child,bit in ((lo,0),(hi,1)):
                b=best(child)
                if b is None: continue
                skipped=prefix[node_rank(child)]-prefix[r+1]
                choices.append(b+skipped+(local_w if bit else 0))
            return max(choices) if choices else None

        @lru_cache(maxsize=200000)
        def front_capacity(front,i):
            options=[]
            for q in front:
                remainder=best(q)
                if remainder is None:continue
                r=node_rank(q)
                # A jump past untested selected groups does NOT force
                # their values. Assume they can all be 1, an upper bound.
                skipped=sum(weights[g] for p,g in selected_positions
                            if p<r and g>=i)
                options.append(remainder+skipped)
            return max(options) if options else None
        return front_capacity
    return [build_one(c) for c in canonical_classes]

def quotient(source,cert,max_states=3000,max_seconds=12):
    start=time.perf_counter()
    meta=validate(source,cert)
    n=len(meta["groups"])
    machine_count=len(meta["machines"])
    classes,canon=canonical_graphs(cert["machines"],meta["machines"])
    w=cert.get("group_weights",[1]*n)
    if len(w)!=n or any(type(x)!=int or x<1 for x in w):
        raise Unsupported("invalid positive integer group weights")
    capacities=weighted_bounds(classes,canon,cert["machines"],meta["machines"],w)
    demand_suffix=[sum(w[i:]) for i in range(n+1)]
    require_limits=type(max_states)==int and max_states>0 and max_seconds>0
    if not require_limits:
        raise Unsupported("invalid state/time limits")

    @lru_cache(maxsize=None)
    def eps(q):
        if q==0:return frozenset()
        if q==1:return frozenset((1,))
        label,lo,hi=canon[q]
        if label[0]=="a":
            return eps(lo)|eps(hi)
        return frozenset((q,))

    @lru_cache(maxsize=500000)
    def move(front,i,taken):
        nxt=set()
        for q in front:
            if q==1:
                nxt.add(1)
                continue
            label,lo,hi=canon[q]
            if label[0]!="g":
                raise AssertionError("aux node survived epsilon closure")
            k=label[1]
            if k<i:
                raise AssertionError("past selected group reached")
            if k>i:
                nxt.add(q)
            else:
                nxt.add(hi if taken else lo)
        joined=set()
        for q in nxt:
            joined.update(eps(q))
        return tuple(sorted(joined))

    initial=[]
    for c in classes:
        front=tuple(sorted(eps(c["root"])))
        if not front:
            return {"status":"UNSAT_SOURCE_WEIGHTED_SYMMETRY_PRODUCT",
                    "processed_groups":0,
                    "reason":"a source-verified local BDD root has no accepted path"}
        initial.append(((front,len(c["members"])),))
    initial=tuple(initial)
    def state_capacity(state,i):
        total=0
        for class_idx,multiset in enumerate(state):
            for front,count in multiset:
                bound=capacities[class_idx](front,i)
                if bound is None:
                    return None
                total+=bound*count
        return total

    root_bound=state_capacity(initial,0)
    if root_bound is None or root_bound<demand_suffix[0]:
        return {
            "status":"UNSAT_SOURCE_WEIGHTED_ROOT_CUT",
            "processed_groups":0,
            "machine_count":machine_count,
            "structural_classes":len(classes),
            "root_capacity":root_bound,
            "required_demand":demand_suffix[0],
            "product_states":1,
            "cut_states":1,
            "source_sha256":cert["source_sha256"],
            "external_veripb_proof":"NOT_EMITTED",
        }

    frontier={initial}
    cut_states=0
    visited=1
    maximum=1
    transitions=0
    class_choices=[[] for _ in range(n)]
    for i in range(n):
        class_choices[i]=[k for k,c in enumerate(classes)
                          if i in c["eligible"]]
        if not class_choices[i]:
            raise Unsupported("group has no source-backed eligible machine")

    def canonical_multiset(counter):
        return tuple(sorted((front,count) for front,count in counter.items()
                            if count>0))

    for i in range(n):
        nxt_layer=set()
        # Memoize the zero branch for each local class frontier.
        for state in frontier:
            for chosen_class in class_choices[i]:
                counts=[Counter(dict(group)) for group in state]
                zero={}
                valid=True
                for class_idx, group in enumerate(counts):
                    zero[class_idx]={}
                    for f,count in group.items():
                        z=move(f,i,False)
                        zero[class_idx][f]=z
                for selected_front,number in counts[chosen_class].items():
                    if number<=0:continue
                    per_class=[]
                    for class_idx,group in enumerate(counts):
                        trans=Counter()
                        chosen_here=(class_idx==chosen_class)
                        for f,count in group.items():
                            z=zero[class_idx][f]
                            remaining=count-(1 if chosen_here and f==selected_front else 0)
                            if remaining:
                                if not z:
                                    valid=False
                                    break
                                trans[z]+=remaining
                            if chosen_here and f==selected_front:
                                one=move(f,i,True)
                                if not one:
                                    valid=False
                                    break
                                trans[one]+=1
                        if not valid:break
                        per_class.append(canonical_multiset(trans))
                    transitions+=1
                    if valid:
                        candidate=tuple(per_class)
                        upper=state_capacity(candidate,i+1)
                        if upper is None or upper<demand_suffix[i+1]:
                            cut_states+=1
                        else:
                            nxt_layer.add(candidate)
                    valid=True
                    if (visited+len(nxt_layer)>max_states or
                        time.perf_counter()-start>max_seconds):
                        return {
                            "status":"UNKNOWN_RESOURCE_LIMIT",
                            "processed_groups":i+1,
                            "states":visited+len(nxt_layer),
                            "machine_count":machine_count,
                            "structural_classes":len(classes),
                            "tried_transitions":transitions,
                            "max_states":max_states,
                            "cut_states":cut_states,
                            "root_capacity":root_bound,
                            "required_demand":demand_suffix[0],
                        }
        if not nxt_layer:
            return {
                "status":"UNSAT_SOURCE_WEIGHTED_SYMMETRY_PRODUCT",
                "processed_groups":i+1,
                "machine_count":machine_count,
                "structural_classes":len(classes),
                "product_states":visited,
                "max_frontier":maximum,
                "tried_transitions":transitions,
                "source_sha256":cert["source_sha256"],
                "external_veripb_proof":"NOT_EMITTED",
                "cut_states":cut_states,
                "root_capacity":root_bound,
                "required_demand":demand_suffix[0]
            }
        visited+=len(nxt_layer)
        maximum=max(maximum,len(nxt_layer))
        frontier=nxt_layer
    accepted=0
    for state in frontier:
        if all(all(1 in front for front,count in group)
               for group in state):
            accepted+=1
    status=("UNKNOWN_ABSTRACT_COMPATIBLE" if accepted else
            "UNSAT_SOURCE_WEIGHTED_SYMMETRY_PRODUCT")
    return {
        "status":status,
        "processed_groups":n,
        "machine_count":machine_count,
        "structural_classes":len(classes),
        "class_multiplicities":sorted((len(x["members"]) for x in classes),
                                      reverse=True),
        "product_states":visited,
        "max_frontier":maximum,
        "tried_transitions":transitions,
        "abstract_compatible_states":accepted,
        "source_sha256":cert["source_sha256"],
        "external_veripb_proof":"NOT_EMITTED",
        "cut_states":cut_states,
        "root_capacity":root_bound,
        "required_demand":demand_suffix[0],
    }

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--cnf",type=Path,required=True)
    p.add_argument("--certificate",type=Path,required=True)
    p.add_argument("--max-states",type=int,default=3000)
    p.add_argument("--max-seconds",type=float,default=12)
    a=p.parse_args()
    try:
        result=quotient(a.cnf.read_bytes(),
                        json.loads(a.certificate.read_text()),
                        a.max_states,a.max_seconds)
        print(json.dumps(result,sort_keys=True))
    except (Unsupported,ValueError,TypeError,KeyError,RecursionError) as error:
        print(json.dumps({"status":"UNSUPPORTED_OR_INVALID_SOURCE",
                          "reason":str(error)}))
        raise SystemExit(2)
