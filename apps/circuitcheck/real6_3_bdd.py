#!/usr/bin/env python3
"""REAL6.3 source-gate arithmetic discovery using canonical reduced BDD.

Unlike REAL6.2, subsequent bits require only a physically present XOR-of-XOR
SUM, not a local separately exposed MAJ carry. The inferred carry input to
a SUM is proved equivalent to the prefix arithmetic carry in the ORIGINAL
source gate network over independent free bit cuts.

Original Yosys gate source + independent REAL6.1 eight-row certificate are
immutable inputs. No CDCL fallback; no project/name/HDL-specific patterns.
Proof scope: purely combinational, two-state, cut-relative, SUM modulo 2^n.
Detector findings are independently rechecked in real6_3_verify.py.
"""
from __future__ import annotations
import argparse,collections,hashlib,json
from pathlib import Path
from real6_1_carry import gate_graph,sum_seeds

MAX_DEPTH=32
MAX_SEEDS=10000
MAX_BDD_NODES=30000
MAX_PATHS=8
MAX_CHECKS=220000
MAX_ACCEPTED_NEXT_STAGE_CANDIDATES=3

class Budget(Exception):pass
class Unsupported(Exception):pass

class BDD:
    def __init__(self,source,variables):
        self.source=source
        self.rank={b:k for k,b in enumerate(variables)}
        if len(self.rank)!=len(variables):raise Unsupported("DUPLICATE_VARIABLES")
        self.nodes=[None,None];self.unique={};self.memo={};self.cone={};self.active=set()
        self.ranks=[1<<30,1<<30]
    def mk(self,v,lo,hi):
        if lo==hi:return lo
        key=(v,lo,hi)
        if key in self.unique:return self.unique[key]
        if len(self.nodes)>MAX_BDD_NODES:raise Budget("BDD_NODE_LIMIT")
        n=len(self.nodes);self.nodes.append((v,lo,hi));self.ranks.append(v)
        self.unique[key]=n;return n
    def apply(self,op,a,b):
        if op in ("A","O","X") and a>b:a,b=b,a
        key=(op,a,b)
        if key in self.memo:return self.memo[key]
        if a<=1 and b<=1:
            v={"A":a&b,"O":a|b,"X":a^b}[op]
        else:
            t=min(self.ranks[a],self.ranks[b])
            a0,a1=(self.nodes[a][1:] if self.ranks[a]==t else (a,a))
            b0,b1=(self.nodes[b][1:] if self.ranks[b]==t else (b,b))
            v=self.mk(t,self.apply(op,a0,b0),self.apply(op,a1,b1))
        self.memo[key]=v
        return v
    def AND(self,a,b):return self.apply("A",a,b)
    def OR(self,a,b):return self.apply("O",a,b)
    def XOR(self,a,b):return self.apply("X",a,b)
    def NOT(self,a):return self.XOR(a,1)
    def majority(self,a,b,c):
        return self.OR(self.AND(a,b),self.AND(c,self.OR(a,b)))
    def wire(self,bit):
        if bit=="0":return 0
        if bit=="1":return 1
        if bit in self.rank:return self.mk(self.rank[bit],0,1)
        if bit in self.cone:return self.cone[bit]
        if bit in self.active or bit not in self.source:raise Unsupported("UNBOUND_CUT_OR_CYCLE")
        if len(self.active)>1500:raise Budget("DEPTH")
        op,ins=self.source[bit]
        self.active.add(bit)
        try:v=[self.wire(x) for x in ins]
        finally:self.active.remove(bit)
        if op=="$_AND_":ans=self.AND(*v)
        elif op=="$_OR_":ans=self.OR(*v)
        elif op=="$_XOR_":ans=self.XOR(*v)
        elif op=="$_XNOR_":ans=self.NOT(self.XOR(*v))
        elif op=="$_NAND_":ans=self.NOT(self.AND(*v))
        elif op=="$_NOR_":ans=self.NOT(self.OR(*v))
        elif op=="$_NOT_":ans=self.NOT(v[0])
        elif op=="$_BUF_":ans=v[0]
        elif op=="$_MUX_":
            ans=self.OR(self.AND(v[0],self.NOT(v[2])),self.AND(v[1],v[2]))
        else:raise Unsupported("GATE")
        self.cone[bit]=ans
        return ans

def make_seeds(prod):
    seeds={};raw=0
    for out,triple in sum_seeds(prod):
        raw+=1
        if raw>MAX_SEEDS:break
        k=(out,tuple(sorted(triple)))
        seeds[k]={"sum_bit":out,"inputs":list(k[1])}
    return list(seeds.values()),raw

def verify_path(path,prod,check_output=True):
    """Full symbolic carry induction on independent original physical cuts."""
    first=path[0]
    if len(first["inputs"])!=3:raise Unsupported("BAD_FIRST")
    free=list(first["inputs"])
    for st in path[1:]:
        if len(st["operands"])!=2 or st["carry_input"] in st["operands"]:
            raise Unsupported("BAD_LATER")
        if any(v in free for v in st["operands"]):
            raise Unsupported("INPUT_OVERLAP")
        free.extend(st["operands"])
    b=BDD(prod,free)
    low=[b.wire(v) for v in first["inputs"]]
    carry=b.majority(*low)
    if check_output and b.wire(first["sum_bit"])!=b.XOR(low[0],b.XOR(low[1],low[2])):
        return False,len(b.nodes)
    for stage in path[1:]:
        actual=b.wire(stage["carry_input"])
        if actual!=carry:return False,len(b.nodes)
        a,c=(b.wire(v) for v in stage["operands"])
        if check_output and b.wire(stage["sum_bit"])!=b.XOR(a,b.XOR(c,carry)):
            return False,len(b.nodes)
        carry=b.majority(a,c,carry)
    return True,len(b.nodes)

def detect(original,base,top=None):
    src=Path(original).read_bytes()
    base_src=Path(base).read_bytes()
    cert=json.loads(base_src)
    doc=json.loads(src)
    top,prod,users,unknown=gate_graph(doc,top or cert["top"])
    original_stages=cert["stages"]
    seedlist,raw=make_seeds(prod)
    roots={s["sum_bit"]:s for s in seedlist}
    base_roots={x["sum_bit"] for x in original_stages}
    edges=[]
    for i,s in enumerate(original_stages):
        for j,t in enumerate(original_stages):
            if i==j or s["carry_bit"] not in t["inputs"]:continue
            fresh=[v for v in t["inputs"] if v!=s["carry_bit"]]
            if len(fresh)!=2 or any(v in s["inputs"] for v in fresh):continue
            if s["sum_bit"] not in roots or t["sum_bit"] not in roots:continue
            path=[{"sum_bit":s["sum_bit"],"inputs":s["inputs"],"base_carry_bit":s["carry_bit"]},
                  {"sum_bit":t["sum_bit"],"carry_input":s["carry_bit"],"operands":sorted(fresh)}]
            edges.append(path)
    paths=edges[:MAX_PATHS];checks=0;max_bdd=0;budget_hits=0;depths=[]
    winners=list(paths)
    while paths:
        next_paths=[];pmax=max(len(p) for p in paths)
        if pmax>=MAX_DEPTH:break
        for path in paths:
            introduced=set(path[0]["inputs"])
            for st in path[1:]:introduced.update(st["operands"])
            visited={st["sum_bit"] for st in path}
            # Source-lowering physical bit ID proximity only ranks the search.
            # Results rely on full BDD proof, never this heuristic.
            last=path[-1]["sum_bit"]
            options=sorted(seedlist,key=lambda s:(abs(s["sum_bit"]-last),s["sum_bit"]))
            found=[]
            for s in options:
                if s["sum_bit"] in visited:continue
                for v in s["inputs"]:
                    fresh=sorted(x for x in s["inputs"] if x!=v)
                    if len(fresh)!=2 or len(set(fresh))!=2:continue
                    if any(x in introduced for x in fresh):continue
                    if v not in prod and v not in introduced:continue
                    candidate=path+[{"sum_bit":s["sum_bit"],
                        "carry_input":v,"operands":fresh}]
                    checks+=1
                    if checks>MAX_CHECKS:
                        budget_hits+=1;break
                    try:
                        ok,nodes=verify_path(candidate,prod)
                        max_bdd=max(max_bdd,nodes)
                    except (Budget,Unsupported,RecursionError):
                        budget_hits+=1;continue
                    if ok:
                        found.append(candidate)
                        # Purely a search heuristic. Each retained path is
                        # independently proved; completeness is not claimed.
                        if len(found)>=MAX_ACCEPTED_NEXT_STAGE_CANDIDATES:break
                if checks>MAX_CHECKS or len(found)>=MAX_ACCEPTED_NEXT_STAGE_CANDIDATES:break
            found.sort(key=lambda p:(abs(p[-1]["sum_bit"]-last),p[-1]["sum_bit"]))
            next_paths.extend(found[:MAX_PATHS])
            if checks>MAX_CHECKS:break
        if not next_paths:break
        next_paths.sort(key=lambda p:(-len(p),[x["sum_bit"] for x in p]))
        # Remove duplicate physical sum sequences.
        seen=set();unique=[]
        for p in next_paths:
            seq=tuple(s["sum_bit"] for s in p)
            if seq not in seen:unique.append(p);seen.add(seq)
        paths=unique[:MAX_PATHS]
        winners.extend(paths)
        depths.append({"bits":len(paths[0]),"paths":len(paths),"checked":checks})
        print("REAL6_3_PROGRESS",depths[-1],flush=True)
        if checks>MAX_CHECKS:break
    winners.sort(key=lambda p:(-len(p),[s["sum_bit"] for s in p]))
    distinct=[];seen=set()
    for p in winners:
        key=tuple(s["sum_bit"] for s in p)
        if key not in seen:distinct.append(p);seen.add(key)
    best=distinct[:16]
    result={"protocol":"DRNAS_REAL6_3_BDD_ARITHMETIC_CARRY_DISCOVERY_V1",
            "scope":"source-only two-state exact gate-ROBDD over free cut bits; verified local SUM modulo 2^n; no full HDL time or whole SAT/UNSAT",
            "original_netlist_sha256":hashlib.sha256(src).hexdigest(),
            "source_real6_1_certificate_sha256":hashlib.sha256(base_src).hexdigest(),
            "original_top":top,"paths":best,
            "metrics":{"source_verified_1bit_full_adder_pairs":len(original_stages),
                       "xor_sum_seeds":len(seedlist),"raw_xor_seed_sightings":raw,
                       "direct_two_stage_anchors":len(edges),"longest_proposed_sum_bits":max((len(p) for p in best),default=0),
                       "candidate_checks":checks,"bdd_max_nodes":max_bdd,
                       "unverifiable_candidate_attempts":budget_hits,
                       "search_budget_reached":checks>MAX_CHECKS,
                       "heuristic_next_stage_candidates_per_path":MAX_ACCEPTED_NEXT_STAGE_CANDIDATES,
                       "search_progress":depths,
                       "not_a_new_blind_holdout":True}}
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--netlist",required=True)
    p.add_argument("--base-certificate",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    report=detect(a.netlist,a.base_certificate)
    Path(a.out).write_text(json.dumps(report,indent=2)+"\n")
    print("REAL6_3_SOURCE_DETECTION_FINAL",report["metrics"],flush=True)
if __name__=="__main__":main()
