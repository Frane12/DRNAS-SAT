"""Draw after a published code freeze; restore a manifest without redrawing."""
import argparse
import hashlib
import io
import itertools
import json
import random
import tarfile
import urllib.request
from pathlib import Path

BASE = "https://www.cs.ubc.ca/~hoos/SATLIB/Benchmarks/SAT/"
PUBLIC = {
    "blocks": "PLANNING/BlocksWorld/blocksworld.tar.gz",
    "bridge": "DIMACS/BF/bf.tar.gz",
    "stuck": "DIMACS/SSA/ssa.tar.gz",
    "induction": "DIMACS/II/inductive-inference.tar.gz",
    "quasigroup": "QG/QG.tar.gz",
    "interval": "AIS/ais.tar.gz",
    "dubois": "DIMACS/DUBOIS/dubois.tar.gz",
    "colour75": "GCP/flat75-180.tar.gz",
}
TRANSFER = {
    "aim": "DIMACS/AIM/aim.tar.gz",
    "jnh": "DIMACS/JNH/jnh.tar.gz",
    "parity": "DIMACS/PARITY/parity.tar.gz",
    "bmc": "BMC/bmc.tar.gz",
    "quasigroup": PUBLIC["quasigroup"],
    "colour75": PUBLIC["colour75"],
}
FRESH = ("tseitin", "random3", "colour", "circuit")
def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(n, cs):
    return (f"p cnf {n} {len(cs)}\n" +
            "".join(" ".join(map(str,c)) + (" " if c else "") + "0\n" for c in cs)).encode()


def parse_source(raw):
    n = declared = None
    clauses, pending = [], []
    for line in raw.decode("latin-1").splitlines():
        tokens = line.split()
        if not tokens or tokens[0].startswith("c"):
            continue
        if tokens[0].startswith("%"):
            break
        if tokens[0] == "p":
            if n is not None or len(tokens) != 4 or tokens[1].lower() != "cnf":
                raise ValueError("invalid header")
            n, declared = map(int,tokens[2:])
            if n < 0 or declared < 0:
                raise ValueError("negative header")
            continue
        if n is None:
            raise ValueError("missing header")
        for lit in map(int,tokens):
            if abs(lit) > n:
                raise ValueError("out-of-range literal")
            if lit:
                pending.append(lit)
            else:
                clauses.append(pending); pending = []
    if n is None or pending or len(clauses) != declared:
        raise ValueError("header/clause count mismatch")
    return n, clauses


def fingerprint(n, cs):
    unique = set()
    for c in cs:
        s = frozenset(c)
        if not any(-l in s for l in s):
            unique.add(tuple(sorted(s)))
    return sha(encode(n,sorted(unique)))


def fresh(family, index, seed):
    rng = random.Random(seed)
    def parity(variables, rhs):
        return [[-v if b else v for v,b in zip(variables,bits)]
                for bits in itertools.product((0,1),repeat=len(variables)) if sum(bits)%2 != rhs]
    clauses = []
    if family == "tseitin":
        vertices = [34,46,58][index]
        perm = list(range(vertices)); rng.shuffle(perm)
        edges = [(i,(i+1)%vertices) for i in range(vertices)]
        edges += list(zip(perm[::2],perm[1::2]))
        inc = [[] for _ in range(vertices)]
        for e,(u,v) in enumerate(edges,1):
            inc[u].append(e); inc[v].append(e)
        n = len(edges)
        charges = [rng.randrange(2) for _ in range(vertices-1)]
        charges.append((sum(charges) + (index != 1)) % 2)
        for vs,rhs in zip(inc,charges):
            clauses.extend(parity(vs,rhs))
    elif family == "random3":
        n = [87,111,139][index]
        for _ in range(round(n*4.26)):
            clauses.append([v*rng.choice((-1,1)) for v in rng.sample(range(1,n+1),3)])
    elif family == "colour":
        vertices = [30,42,54][index]; n = vertices*3
        classes = [i%3 for i in range(vertices)]; rng.shuffle(classes)
        edges = set()
        while len(edges) < 2*vertices:
            a,b = sorted(rng.sample(range(vertices),2))
            if classes[a]!=classes[b]: edges.add((a,b))
        if index == 1: edges.update(itertools.combinations(rng.sample(range(vertices),4),2))
        for i in range(vertices):
            vs = list(range(3*i+1,3*i+4)); clauses.append(vs)
            clauses.extend([[-a,-b] for a,b in itertools.combinations(vs,2)])
        for a,b in sorted(edges):
            for colour in range(1,4): clauses.append([-(3*a+colour),-(3*b+colour)])
    else:
        inputs, gates = 12, [34,48,68][index]
        left = list(range(1,inputs+1)); right = left[:]; n = inputs
        def gate(a,b,y,op):
            if op == "xor": return parity([a,b,y],0)
            if op == "and": return [[-a,-b,y],[a,-y],[b,-y]]
            return [[a,b,-y],[-a,y],[-b,y]]
        for j in range(gates):
            ia = len(left)-1 if j else rng.randrange(inputs)
            ib = rng.randrange(len(left)-1)
            op = rng.choice(("and","or","xor"))
            n += 2
            clauses.extend(gate(left[ia],left[ib],n-1,op))
            clauses.extend(gate(right[ib],right[ia],n,op))
            left.append(n-1); right.append(n)
        clauses.extend(parity([left[-1],right[-1]],int(index != 1)))
    # Blind variable identities, literal signs, clause and literal order.
    variables = list(range(1,n+1)); rng.shuffle(variables)
    rename = [0]+[v*rng.choice((-1,1)) for v in variables]
    masked = [[rename[abs(l)]*(1 if l>0 else -1) for l in c] for c in clauses]
    for c in masked: rng.shuffle(c)
    rng.shuffle(masked)
    return n, masked


def download(cache, group, expected=None, sources=PUBLIC):
    path = cache/(group+".tar.gz")
    if not path.exists():
        with urllib.request.urlopen(BASE+sources[group],timeout=60) as response:
            data = response.read()
        path.write_bytes(data)
    raw = path.read_bytes()
    if expected and sha(raw) != expected:
        raise ValueError(f"archive digest changed for {group}")
    return raw


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,required=True)
    select=p.add_mutually_exclusive_group(required=True)
    select.add_argument("--draw",metavar="FREEZE_COMMIT")
    select.add_argument("--restore",type=Path,metavar="MANIFEST")
    p.add_argument("--prior",type=Path,help="development fingerprints/names for original draw")
    p.add_argument("--transfer",action="store_true",help="draw four originals from each postprojection transfer collection")
    a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    cache=a.out/"archives"; cache.mkdir(exist_ok=True)
    if a.restore:
        manifest=json.loads(a.restore.read_text()); freeze=manifest["freeze"]
    else:
        if a.prior is None: p.error("--draw requires --prior")
        freeze=a.draw; manifest={"freeze":freeze,"archives":{},"excluded":[],"cases":[]}
    if not a.restore and a.transfer:
        manifest["cohort"]="postprojection-transfer"
    transfer=manifest.get("cohort")=="postprojection-transfer"
    sources=TRANSFER if transfer else PUBLIC
    per_family=4 if transfer else 3
    if len(freeze)!=40 or any(c not in "0123456789abcdef" for c in freeze):
        raise ValueError("expected immutable git commit SHA")
    previous=json.loads(a.prior.read_text()) if a.prior else {}
    seen=set(previous.get("fingerprints",[]))
    blocked_names=set(previous.get("names",[]))
    index={r["id"]:r for r in manifest["cases"]}
    def save(case_id, group, family, n, cs, **origin):
        data=encode(n,cs); normalized=fingerprint(n,cs)
        if normalized in seen: raise ValueError("duplicate selected formula")
        seen.add(normalized)
        row=dict(id=case_id,group=group,family=family,n=n,clauses=len(cs),
                 cnf_sha256=sha(data),fingerprint=normalized,**origin)
        if a.restore and row != index[case_id]: raise ValueError(f"manifest mismatch: {case_id}")
        if not a.restore: manifest["cases"].append(row)
        (a.out/(case_id+".cnf")).write_bytes(data)
    for fam in sources:
        archive=download(cache,fam,manifest["archives"].get(fam,{}).get("sha256"),sources)
        manifest["archives"][fam]={"url":BASE+sources[fam],"sha256":sha(archive)}
        with tarfile.open(fileobj=io.BytesIO(archive),mode="r:gz") as tar:
            members=[m for m in tar.getmembers() if m.isfile() and m.name.lower().endswith(".cnf")
                     and not Path(m.name).name.startswith(".")]
            if a.restore:
                ordered=[tar.getmember(r["member"]) for r in manifest["cases"] if r["family"]==fam and r["group"]=="public"]
            else:
                ordered=sorted(members,key=lambda m:sha(f"{freeze}|{fam}|{m.name}".encode()))
            selected=0
            for member in ordered:
                raw=tar.extractfile(member).read()
                try:
                    n,cs=parse_source(raw)
                except ValueError as exc:
                    if a.restore: raise
                    manifest["excluded"].append([fam,member.name,str(exc)]); continue
                if not a.restore and (Path(member.name).name.lower() in blocked_names or fingerprint(n,cs) in seen):
                    manifest["excluded"].append([fam,member.name,"development overlap or duplicate"]); continue
                save(f"p-{fam}-{selected+1}","public",fam,n,cs,member=member.name,original_sha256=sha(raw))
                selected+=1
                if selected==per_family: break
            if selected!=per_family: raise ValueError(f"{fam}: insufficient eligible members ({selected})")
    for fam in (() if transfer else FRESH):
        for i in range(3):
            seed=int(sha(f"{freeze}|fresh|{fam}|{i}".encode())[:16],16)
            n,cs=fresh(fam,i,seed)
            save(f"g-{fam}-{i+1}","fresh",fam,n,cs,seed=seed)
    if not a.restore:
        manifest["audit_counts"]=previous.get("counts",{})
        (a.out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(f"{len(manifest['cases'])} canonical inputs; freeze {freeze}")

if __name__=="__main__": main()
