#!/usr/bin/env python3
"""Standard VeriPB 3.0 source-bound mixed XOR2/XOR3/XOR4 parity proof.

For XOR4(x,y,z,w)=b, introduce fresh q=x XOR y with four RED
definition clauses. Via three independently RUP-checked steps for
each forbidden 3-XOR assignment, derive XOR3(q,z,w)=b from the
*original* XOR4 source and the fresh definition. Emit two 3-XOR rows:
XOR3(x,y,q)=0 and XOR3(q,z,w)=b. Fresh q occurs exactly twice.

XOR2(b=1) uses its two original clauses; XOR2(b=0) introduces
a fresh AND carry with RED and derives its reverse implications
using RUP. All XOR3 rows use the previously VeriPB-accepted
carry RED/RUP/CP procedure. Every source and fresh variable must
occur exactly twice across the transformed rows, and all RHS
values sum to odd parity. Final CP division produces 0>=1.

This source is not trusted by itself: only external VeriPB 3.0.2
acceptance on the original unchanged CNF earns strict UNSAT.
"""
import argparse
from collections import Counter
from itertools import product
from pathlib import Path
import hashlib,json,sys,time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"research"/"math5"))

class Unsupported(ValueError):pass

def need(ok,message):
    if not ok:raise Unsupported(message)

def ordered_dimacs(raw):
    need(len(raw)<=12_000_000,"original CNF size limit")
    nv=nc=None;clauses=[];pending=[]
    for line in raw.decode("ascii").splitlines():
        fields=line.split()
        if not fields or fields[0]=="c":continue
        if fields[0]=="p":
            need(nv is None and len(fields)==4 and fields[1]=="cnf","bad source header")
            nv,nc=map(int,fields[2:])
            need(0<nv<=6000 and 0<=nc<=100000,"source variable/clause budget")
            continue
        need(nv is not None,"missing DIMACS header")
        for token in fields:
            lit=int(token)
            need(abs(lit)<=nv,"source literal beyond DIMACS header")
            if lit:pending.append(lit)
            else:
                clauses.append(tuple(pending));pending=[]
    need(nv and not pending and len(clauses)==nc,"source clause count mismatch")
    return nv,clauses

class Proof:
    def __init__(self,source_clauses):
        self.lines=["pseudo-Boolean proof version 3.0",
                    f"f {len(source_clauses)} ;"]
        self.ids={}
        for idx,clause in enumerate(source_clauses,1):
            self.ids.setdefault(frozenset(clause),idx)
        self.last=len(source_clauses)
        self.count=Counter()
    @staticmethod
    def clause(lits):
        return " ".join("1 "+("~" if lit<0 else "")+"x"+str(abs(lit))
                        for lit in lits)+" >= 1"
    def red(self,lits,var,val):
        self.lines.append("red "+self.clause(lits)+f" : x{var} -> {val} ;")
        self.last+=1;self.count["RED"]+=1
        self.ids.setdefault(frozenset(lits),self.last)
        return self.last
    def rup(self,lits):
        self.lines.append("rup "+self.clause(lits)+" ;")
        self.last+=1;self.count["RUP"]+=1
        self.ids.setdefault(frozenset(lits),self.last)
        return self.last
    def pol(self,ops):
        self.lines.append("pol "+" ".join(map(str,ops))+" ;")
        self.last+=1;self.count["CP"]+=1
        return self.last
    def summation(self,ids):
        need(bool(ids),"empty proof sum")
        ops=[str(ids[0])]
        for line_id in ids[1:]:ops.extend((str(line_id),"+"))
        return self.pol(ops)


def discover(original,nv,external_links=None):
    """Source-only structural recovery of indirect XOR3/4 gates.
    This is an incomplete sufficient-condition detector: unsupported => UNKNOWN.
    """
    from collections import defaultdict,deque
    ids={frozenset(c) for c in original}
    candidates=[]
    for c in original:
        if 4<=len(c)<=64 and all(v>0 for v in c) and len(set(c))==len(c):
            if all(frozenset((-u,-v)) in ids
                   for i,u in enumerate(c) for v in c[i+1:]):
                candidates.append(tuple(c))
    need(bool(candidates),"no exact source one-hot capacity premise")

    # A source XOR3 or XOR4 gate is accepted ONLY with the entire complete
    # forbidden-assignment clause family; variable/sign order is ignored.
    group_map=defaultdict(set)
    for c in original:
        vars=tuple(sorted(abs(v) for v in c))
        if len(vars) not in (3,4) or len(set(vars))!=len(vars):continue
        bits=tuple(int(next(l for l in c if abs(l)==v)<0) for v in vars)
        group_map[vars].add(bits)
    graph_rows=[]
    for vars,patterns in group_map.items():
        for forbidden_parity in (0,1):
            target={bits for bits in product((0,1),repeat=len(vars))
                    if sum(bits)%2==forbidden_parity}
            if target<=patterns:
                graph_rows.append((vars,1-forbidden_parity))
    need(bool(graph_rows),"no complete source XOR3/4 gates")

    G=defaultdict(list)
    for c in original:
        if len(c)==2:
            a,b=c
            G[-a].append(b);G[-b].append(a)
    def reachable(a,b):
        seen={a};todo=deque([a])
        while todo:
            v=todo.popleft()
            if v==b:return True
            for w in G[v]:
                if w not in seen:seen.add(w);todo.append(w)
        return False

    graphvars={v for vars,_ in graph_rows for v in vars}
    index_by_var=defaultdict(set)
    for idx,(vars,rhs) in enumerate(graph_rows):
        for v in vars:index_by_var[v].add(idx)
    for onehot in candidates:
        chosen=[];seen_y=set()
        if external_links is not None:
            if list(onehot)!=external_links.get("onehot"):continue
            claims=external_links.get("links",[])
            need(len(claims)==len(onehot),"exchange link count mismatch")
            for x,claim in zip(onehot,claims):
                need(type(claim) is dict and claim.get("x")==x,
                     "exchange job-to-link order mismatch")
                y=claim.get("y");d=claim.get("xor_bit")
                need(type(y) is int and y in graphvars and y not in onehot
                     and d in (0,1) and y not in seen_y,"exchange invalid signed link")
                target=y if d==0 else -y
                for key,a,b in (("path_xy",x,target),("path_yx",target,x)):
                    path=claim.get(key)
                    need(type(path) is list and len(path)>=2 and
                         len(path)<=len(original)+1 and path[0]==a and path[-1]==b and
                         all(type(v) is int and v!=0 and abs(v)<=nv for v in path),
                         "exchange invalid source path")
                    for u,v in zip(path,path[1:]):
                        need(frozenset((-u,v)) in ids,
                             "exchange path step is not an original binary source clause")
                chosen.append((x,y,d));seen_y.add(y)
        else:
            for x in onehot:
                possible=[]
                for y in sorted(graphvars-set(onehot)):
                    positive=reachable(x,y) and reachable(y,x)
                    negative=reachable(x,-y) and reachable(-y,x)
                    if positive:possible.append((x,y,0))
                    if negative:possible.append((x,y,1))
                if len(possible)!=1:break
                if possible[0][1] in seen_y:break
                seen_y.add(possible[0][1]);chosen.append(possible[0])
        if len(chosen)!=len(onehot):continue

        # Discover the gate component reachable from matched y variables.
        # This automatically includes chains of hidden XOR3 carry variables.
        used=set();todo=deque(sorted(seen_y))
        visited_vars=set()
        while todo:
            var=todo.popleft()
            if var in visited_vars:continue
            visited_vars.add(var)
            for j in sorted(index_by_var[var]):
                if j in used:continue
                used.add(j)
                for v in graph_rows[j][0]:
                    if v not in visited_vars:todo.append(v)
        selected=[graph_rows[j] for j in sorted(used)]
        degrees=Counter(v for vars,_ in selected for v in vars)
        if any(degrees[y]!=1 for y in seen_y):continue
        if any(degrees[v]!=2 for v in degrees if v not in seen_y):continue
        if any(v in onehot for v in degrees):continue
        # Summed graph parity and signed 2-SAT links must be EVEN, while
        # exactly-one capacity has odd parity, giving the contradiction.
        if (sum(rhs for _,rhs in selected)+sum(d for _,_,d in chosen))%2!=0:continue
        return onehot,chosen,selected
    raise Unsupported("no closed source XOR3/4 network linked to exact-one through 2-SAT")

def compile_source(raw,exchange=None):
    started=time.perf_counter()
    nv,original=ordered_dimacs(raw)
    if exchange is not None:
        need(type(exchange) is dict and
             exchange.get("format")=="DRNAS-2SAT-SIGNED-LINKS-v1" and
             exchange.get("verdict")=="FACTS_ONLY_UNCHECKED" and
             exchange.get("source_sha256")==hashlib.sha256(raw).hexdigest(),
             "exchange source hash or format mismatch")
    onehot, links, graph_rows=discover(original,nv,exchange)
    p=Proof(original)
    # Source implications entail these two equivalence clauses by RUP,
    # because both directions are paths of length >=1 in the 2-CNF graph.
    for x,y,d in links:
        if d==0:
            p.rup((-x,y))
            p.rup((x,-y))
        else:
            p.rup((-x,-y))
            p.rup((x,y))
    rows=[{"vars":vars,"forbidden_parity":1-rhs} for vars,rhs in graph_rows]
    rows += [{"vars":(x,y),"forbidden_parity":1-d}
             for x,y,d in links] # XOR2(x,y)=d, source-proved by SCC paths
    next_var=nv
    transformed=[]
    widths=Counter()
    def forbidding_clause(variables,bits):
        return tuple(-v if bit else v for v,bit in zip(variables,bits))
    for row in rows:
        vars=tuple(row["vars"])
        width=len(vars)
        rhs=1-row["forbidden_parity"]
        widths[width]+=1
        need(len(set(vars))==width,"source XOR duplicate variable")
        for bits in product((0,1),repeat=width):
            if sum(bits)%2!=rhs:
                need(frozenset(forbidding_clause(vars,bits)) in p.ids,
                     "original XOR clause missing")
        if width<=3:
            transformed.append((vars,rhs))
            continue
        x,y,z,w=vars
        next_var+=1;q=next_var
        # Introduce fresh q=x XOR y using four VeriPB RED clauses.
        for bx,by in product((0,1),repeat=2):
            value=bx^by
            invalid=forbidding_clause((x,y,q),(bx,by,1-value))
            p.red(invalid,q,value)
        transformed.append(((x,y,q),0))
        # Source plus definition entails XOR3(q,z,w)=rhs.
        # Prove each of its four clauses via bounded RUP resolution on x.
        for bq,bz,bw in product((0,1),repeat=3):
            if (bq+bz+bw)%2==rhs:continue
            guarded=forbidding_clause((q,z,w),(bq,bz,bw))
            p.rup(guarded+(x,))
            p.rup(guarded+(-x,))
            p.rup(guarded)
        transformed.append(((q,z,w),rhs))
    counts=Counter(var for variables,_ in transformed for var in variables)
    need(all(counts[v]+int(v in onehot)==2 for v in counts) and all(v in counts for v in onehot),
         "not all variables have exactly two occurrences with the capacity row")
    need(sum(rhs for _,rhs in transformed)%2==0,
         "global XOR parity does not conflict with one-hot capacity")
    lowers=[];uppers=[]
    for vars,rhs in transformed:
        if len(vars)==2:
            x,y=vars
            if rhs==1:
                lowers.append(p.ids[frozenset((x,y))])
                uppers.append(p.ids[frozenset((-x,-y))])
                continue
            next_var+=1;t=next_var
            first=p.red((-t,x),t,0)
            second=p.red((-t,y),t,0)
            p.red((t,-x,-y),t,1)
            lowers.append(p.pol((first,second,"+")))
            first=p.rup((-x,t))
            second=p.rup((-y,t))
            uppers.append(p.pol((first,second,"+")))
            continue
        x,y,z=vars
        next_var+=1;t=next_var
        if rhs==1:
            defs=[p.red((-t,v),t,0) for v in vars]
            p.red((t,-x,-y,-z),t,1)
            alo=p.ids[frozenset(vars)]
            summed=p.summation(defs)
            lower=p.pol((summed,2,"*",alo,"+",3,"d"))
            opposite=[p.rup((-a,-b,t))
                      for a,b in ((x,y),(x,z),(y,z))]
            summed=p.summation(opposite)
            upper=p.pol((summed,2,"d"))
        else:
            pairs=((x,y),(x,z),(y,z))
            defs=[p.red((-t,a,b),t,0) for a,b in pairs]
            for a,b in pairs:
                p.red((t,-a,-b),t,1)
            summed=p.summation(defs)
            lower=p.pol((summed,2,"d"))
            opposite=[p.rup((-v,t)) for v in vars]
            summed=p.summation(opposite)
            minus_all=p.ids[frozenset((-x,-y,-z))]
            upper=p.pol((summed,2,"*",minus_all,"+",3,"d"))
        lowers.append(lower)
        uppers.append(upper)

    # Build one-hot upper PB bound in polynomially many CP lines
    # from original binary exclusion clauses.
    capacity_upper=p.ids[frozenset((-onehot[0],-onehot[1]))]
    for j in range(3,len(onehot)+1):
        ops=[str(capacity_upper),str(j-2),"*"]
        for i in range(j-1):
            cid=p.ids[frozenset((-onehot[i],-onehot[j-1]))]
            ops.extend([str(cid),"+"])
        ops.extend([str(j-1),"d"])
        capacity_upper=p.pol(ops)
    capacity_lower=p.ids[frozenset(onehot)]
    # The capacity row sum(x)=1 joins the parity rows:
    # x appears once in the 2-SAT equality and once in one-hot;
    # y appears in XOR4 and equality; each edge in two XOR4 rows;
    # splitting/carry bits have even multiplicity.
    lower=p.summation(lowers+[capacity_lower])
    upper=p.summation(uppers+[capacity_upper])
    cutlower=p.pol((lower,2,"d"))
    cutupper=p.pol((upper,2,"d"))
    p.pol((cutlower,cutupper,"+"))
    p.lines.extend(("output NONE ;","conclusion UNSAT ;",
                    "end pseudo-Boolean proof ;"))
    need(sum(p.count.values())<=120000,"proof step budget")
    output="\n".join(p.lines)+"\n"
    need(len(output.encode("ascii"))<=6_000_000,"proof bytes budget")
    return output,{
        "status":"EMITTED_UNCHECKED",
        "source_sha256":hashlib.sha256(raw).hexdigest(),
        "source_vars":nv,"source_clauses":len(original),
        "one_hot_size":len(onehot),"matched_equivalences":len(links),
        "source_xor3_rows":sum(len(v)==3 for v,_ in graph_rows),
        "source_xor4_rows":sum(len(v)==4 for v,_ in graph_rows),
        "negative_links":sum(d for _,_,d in links),
        "fresh_variables":next_var-nv,
        "steps":dict(p.count),
        "proof_bytes":len(output.encode("ascii")),
        "generator_s":round(time.perf_counter()-started,6),
        "external_verifier_required":True,
        "source_verified_exchange_used":exchange is not None,
        "received_links":len(links) if exchange is not None else 0,
        "scope":"source-CNF one-hot + signed 2-SAT SCC + closed indirect XOR3/XOR4 network"}

def main():
    arg=argparse.ArgumentParser()
    arg.add_argument("--cnf",required=True,type=Path)
    arg.add_argument("--output",required=True,type=Path)
    arg.add_argument("--meta",type=Path)
    arg.add_argument("--exchange",type=Path,help="Source SHA-bound 2-SAT fact handoff")
    arg.add_argument("--require-exchange",action="store_true",help="Experimental split-module transport ablation")
    a=arg.parse_args()
    try:
        if a.require_exchange:
            need(a.exchange is not None,"bridge OFF: no signed 2-SAT facts, dispatch UNKNOWN")
        exchange=json.loads(a.exchange.read_text()) if a.exchange else None
        pb,meta=compile_source(a.cnf.read_bytes(),exchange)
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(pb)
        if a.meta:a.meta.write_text(json.dumps(meta,indent=2,sort_keys=True)+"\n")
        print("HYBRID11 "+json.dumps(meta,sort_keys=True),flush=True)
        return 0
    except (Unsupported,ValueError,TypeError,KeyError,IndexError,
            UnicodeError,OverflowError,OSError,AssertionError) as err:
        a.output.unlink(missing_ok=True)
        if a.meta:a.meta.unlink(missing_ok=True)
        print("HYBRID11_UNKNOWN "+str(err),flush=True)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
