import sys
from pathlib import Path
from corpus import parse_source
from unified5_memory import norm,rup_support
root=Path(sys.argv[1]);cases=0;lines=0
for p in sorted(root.glob("*.cnf")):
    _,cs=parse_source(p.read_bytes());active=[norm(c) for c in cs]
    for line in p.with_suffix(".drup").read_text().splitlines():
        vals=list(map(int,line.split()));assert vals[-1]==0
        c=norm(vals[:-1]);assert c is not None and rup_support(active,c) is not None,(p,line)
        active.append(c);lines+=1
    cases+=1
assert cases==81
print("U8_INDEPENDENT_RUP",cases,lines,flush=True)
