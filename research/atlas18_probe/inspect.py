#!/usr/bin/env python3
"""ATLAS18 source-only diagnostic. No solver, no SAT labels, no proofs."""
from collections import Counter, defaultdict
from pathlib import Path
import hashlib, json
ROOT=Path(__file__).resolve().parents[2]
M=json.loads((ROOT/"atlas17_original_inputs/manifest.json").read_text())
OUT=ROOT/"atlas18_diagnostics";OUT.mkdir(exist_ok=True)
rows=[]
for item in M["sources"]:
    if item["cohort"]=="retrospective_known" and item["name"] not in ("petersen-ipg",):
        continue
    data=(ROOT/item["path"]).read_bytes()
    assert hashlib.sha256(data).hexdigest()==item["sha256"]
    n,m=item["variables"],item["clauses"]
    positives=Counter();opts=[];neg=set();unit=Counter();binaries=Counter()
    current=[]
    for line in data.splitlines():
        row=line.split()
        if not row or row[0]==b"c" or row[0]==b"p":continue
        for token in row:
            v=int(token)
            if v:current.append(v);continue
            c=current;current=[]
            if 2<=len(c)<=64 and all(x>0 for x in c) and len(set(c))==len(c):
                opts.append(tuple(sorted(c)));positives[len(c)]+=1
            if len(c)==2:
                binaries["total"]+=1
                if c[0]<0 and c[1]<0 and c[0]!=c[1]:
                    neg.add(tuple(sorted((-c[0],-c[1]))));binaries["both_neg"]+=1
                elif c[0]*c[1]<0:binaries["mixed"]+=1
            if len(c)==1:unit[len(c)]+=1
    if current:raise AssertionError("source not complete")
    options=list(dict.fromkeys(opts))
    widths=sorted(positives.items(),key=lambda x:(-x[1],-x[0]))
    trials=[]
    for key,ordering in [
        ("widest",sorted(options,key=lambda v:(-len(v),v))),
        ("narrowest",sorted(options,key=lambda v:(len(v),v))),
        ("most_frequent_width",sorted(options,key=lambda v:(-positives[len(v)],-len(v),v)))]:
        used=set();picked=[]
        for group in ordering:
            if not any(x in used for x in group):
                picked.append(group);used.update(group)
        cross=sum(a in used and b in used for a,b in neg)
        trials.append({"strategy":key,"groups":len(picked),"selected":len(used),
                       "selection_coverage":round(len(used)/n,5),
                       "widths":sorted(Counter(map(len,picked)).items()),
                       "cross_direct_pairs_in_selection":cross,
                       "groups_first":picked[:4]})
    row={"name":item["name"],"cohort":item["cohort"],"n":n,"m":m,
         "positive_alo_clauses":len(options),"widths":widths[:25],
         "negative_pair_clauses":len(neg),"binary_clauses":dict(binaries),
         "greedy":trials,
         "first_positive_groups":options[:5]}
    rows.append(row)
    print("ATLAS18_DIAGNOSTIC "+json.dumps(row,sort_keys=True),flush=True)
(OUT/"summary.json").write_text(json.dumps(rows,indent=2,sort_keys=True)+"\n")
print("ATLAS18_DIAGNOSTIC_FINAL "+json.dumps({"sources":len(rows),"status":"COMPLETE",
      "no_results_from_catalog":True,"no_solver_run":True},sort_keys=True),flush=True)
