#!/usr/bin/env python3
"""REAL6.3 diagnosis of original 64 full-adder sites, without source mutation."""
import argparse,collections,json
from pathlib import Path
from real6_1_carry import gate_graph,eval_local,CARRY_MASK

def diagnose(net,cert):
    doc=json.loads(Path(net).read_text());p=json.loads(Path(cert).read_text())
    top,prod,users,ignored=gate_graph(doc,p["top"])
    stage=p["stages"]
    indep=collections.Counter();candidate=[]
    for i,a in enumerate(stage):
        leaves=tuple(a["inputs"])
        for j,b in enumerate(stage):
            if i==j or a["carry_bit"] in b["inputs"]:continue
            for bit in b["inputs"]:
                if bit in leaves or bit==a["sum_bit"]:continue
                try:
                    if eval_local(bit,leaves,prod)==CARRY_MASK:
                        candidate.append((i,j,bit,a["carry_bit"]))
                        indep["hidden_equivalent_carry"]+=1
                except ValueError:indep["out_of_3_cut"]+=1
    links=p["links"]
    print("REAL6_3_DIAG",p["top"],"stage_pairs",len(stage),"direct_edges",len(links),
          "hidden_edges",len(candidate),flush=True)
    print("REAL6_3_COUNTS",dict(indep),flush=True)
    for i,a in enumerate(stage[:24]):
        print("STAGE",i,"leaves",a["inputs"],"sum",a["sum_bit"],"carry",a["carry_bit"],
              "carry_fanout",len(users.get(a["carry_bit"],[])),
              "user_gates",[(v,prod[v][0]) for v in users.get(a["carry_bit"],[])[:6]],flush=True)
    for x in candidate[:30]:print("HIDDEN_CARRY_LINK",*x,flush=True)
    return {"original_stages":len(stage),"direct_links":len(links),
            "hidden_candidates":len(candidate),"candidate_edges":candidate}

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--netlist",required=True)
    a.add_argument("--certificate",required=True)
    a.add_argument("--out",required=True)
    v=a.parse_args()
    out=diagnose(v.netlist,v.certificate)
    Path(v.out).write_text(json.dumps(out,indent=2))
if __name__=="__main__":main()
