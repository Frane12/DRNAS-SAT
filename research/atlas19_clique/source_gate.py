#!/usr/bin/env python3
"""Cheap, name-independent recognition gate for clique-versus-coloring CNFs.

This is only a source-encoding candidate fingerprint, NEVER an UNSAT
certificate. The independent clique_color_er/source_check.py rechecks all
needed source clauses, and external VeriPB must accept on the exact ORIGINAL.
"""
from collections import Counter
from pathlib import Path

MAX_INPUT_BYTES=30_000_000
MAX_INPUT_CLAUSES=400_000
MAX_INPUT_VARIABLES=200_000

def sniff(source):
    source=Path(source)
    if source.stat().st_size>MAX_INPUT_BYTES:
        return {"candidate":False,"reason":"source_bytes_gate"}
    nvars=nclauses=None
    positive=Counter()
    actual=0
    partial=[]
    for line in source.open("rb"):
        fields=line.split()
        if not fields or fields[0]==b"c":
            continue
        if fields[0]==b"p":
            if nvars is not None or len(fields)!=4 or fields[1]!=b"cnf":
                return {"candidate":False,"reason":"header"}
            try:
                nvars,nclauses=map(int,fields[2:])
            except ValueError:
                return {"candidate":False,"reason":"header_noninteger"}
            if not 0<nvars<=MAX_INPUT_VARIABLES or not 0<nclauses<=MAX_INPUT_CLAUSES:
                return {"candidate":False,"reason":"size_gate"}
            continue
        if nvars is None:
            return {"candidate":False,"reason":"missing_header"}
        for word in fields:
            try:lit=int(word)
            except ValueError:
                return {"candidate":False,"reason":"literal_noninteger"}
            if abs(lit)>nvars:
                return {"candidate":False,"reason":"literal_range"}
            if lit:
                partial.append(lit)
            else:
                actual+=1
                if len(partial)>1 and len(partial)<=150 and all(v>0 for v in partial):
                    positive[len(partial)]+=1
                    if len(positive)>2:
                        return {"candidate":False,"reason":"positive_widths_gt_2"}
                partial=[]
    if partial or nvars is None or actual!=nclauses:
        return {"candidate":False,"reason":"clause_count"}
    if len(positive)!=2:
        return {"candidate":False,"reason":"positive_widths_not_two"}
    c,n=sorted(positive)
    k=positive[n]
    candidate=(2<=c<k<=n<=150 and k==c+1 and positive[c]==n
                and nvars==n*(n-1)//2+n*(k+c))
    return {"candidate":candidate,
            "reason":"shape_candidate_not_a_proof" if candidate else "shape_mismatch",
            "positive_width_counts":dict(positive),
            "n_vertices_hypothesis":n,"clique_size_hypothesis":k,
            "colors_hypothesis":c,
            "source_variables":nvars,"source_clauses":nclauses}
if __name__=="__main__":
    import argparse,json
    a=argparse.ArgumentParser()
    a.add_argument("source",type=Path)
    p=a.parse_args()
    report=sniff(p.source)
    print("ATLAS19_SOURCE_GATE "+json.dumps(report,sort_keys=True))
    raise SystemExit(0 if report["candidate"] else 2)
