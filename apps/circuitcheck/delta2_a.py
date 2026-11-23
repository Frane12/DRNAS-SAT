"""Experimental transition recognition from ordered, externally supplied cuts.
No automatic cut discovery or source RTL proof is claimed.
Each stage is independently reduced to affine masks in its local input basis.
"""
import json
import sys
from delta1_engine import analyze, Unknown

def extract(netlist, top, stages):
    module = netlist["modules"][top]
    results = []
    for stage in stages:
        state, inputs, outputs = (stage[k] for k in ("state","inputs","next"))
        boundary = state + inputs
        if len(set(boundary)) != len(boundary) or not all(type(x)==int for x in boundary):
            raise Unknown("invalid boundary")
        if len(state)!=len(outputs) or not state:
            raise Unknown("state width mismatch")
        ports = {"a_state":{"direction":"input","bits":state},
                 "b_input":{"direction":"input","bits":inputs},
                 "next":{"direction":"output","bits":outputs}}
        local = {"modules":{top:{"ports":ports,"cells":module["cells"]}}}
        cert = analyze(local, {"top":top,"pairs":[{"port":"next","reference":"next","candidate":"next"}]})
        if cert["status"]!="EQUIVALENT_NETLIST":
            raise Unknown("stage not affine in supplied boundary")
        n=len(state)
        masks=[int(row["reference_mask"],16) for row in cert["checked_outputs"]]
        results.append({"A":[(m>>1)&((1<<n)-1) for m in masks],
                        "B":[m>>(n+1) for m in masks],
                        "c":[m&1 for m in masks]})
    if not results: raise Unknown("no stages")
    for a,b in zip(stages,stages[1:]):
        if a["next"]!=b["state"]: raise Unknown("disconnected stages")
    return {"status":"REPEATED_AFFINE" if all(r==results[0] for r in results) else "VARYING_AFFINE",
            "stages":results,"scope":"supplied ordered cuts; local affine identities only"}

if __name__=="__main__":
    try:
        net=json.load(open(sys.argv[1]))
        cuts=json.load(open(sys.argv[2]))
        print(json.dumps(extract(net,cuts["top"],cuts["stages"]),indent=2))
    except (Unknown,KeyError,ValueError,RecursionError) as e:
        print(json.dumps({"status":"UNKNOWN","reason":str(e)}))
        sys.exit(2)
