"""Independent PySAT encoders, source-only ablation and matched baselines."""
import csv
from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path
from statistics import median
import subprocess
import time

from pysat.card import CardEnc, EncType
from pysat.solvers import Solver

from research.atlas16_pilot import run
from research.atlas_eo import check, decode
from research.atlas_eo.test_eo import rename
from research.structure_atlas1.atlas import encoded, parse
from research.structure_atlas3.source_facts import signed_exact_one

ROOT = run.ROOT
OUT = ROOT / "atlas_eo_results"
ENCODINGS = ("pairwise","seqcounter","sortnetwrk","cardnetwrk","bitwise","ladder",
             "totalizer","mtotalizer","kmtotalizer")


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def tabulate(name, rows):
    with (OUT / name).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def projected_oracle(rows, literals):
    with Solver(name="g3", bootstrap_with=rows) as oracle:
        for bits in product((False,True), repeat=len(literals)):
            fixed = [x if bit else -x for x,bit in zip(literals,bits)]
            assert oracle.solve(assumptions=fixed) == (sum(bits)==1)


def recognition():
    records, negatives = [], []
    for kind in ENCODINGS:
        for k in (2,3,5,8,16):
            xs = list(range(1,k+1))
            z = CardEnc.equals(xs, bound=1, encoding=getattr(EncType,kind))
            for variant in ("original","signed-shuffled"):
                if variant == "original":
                    raw, target = encoded(z.nv,z.clauses), xs
                else:
                    raw, mapped = rename(z.nv,z.clauses,k+1009)
                    target = [mapped(x) for x in xs]
                _, rows = parse(raw)
                if k <= 5:
                    projected_oracle(rows,target)
                before = sorted(target,key=lambda x:(abs(x),x<0)) in [
                    list(g) for g in signed_exact_one({frozenset(c) for c in rows})]
                t = time.perf_counter()
                _, _, facts = decode.decode(raw)
                check.verify(raw,facts)
                found = sorted(target) in facts["groups"]
                if kind in ("pairwise","seqcounter","cardnetwrk"):
                    assert found, (kind,k,variant,"target not recovered")
                records.append(dict(encoding=kind,k=k,variant=variant,target_found=found,
                                    literal_pairwise_baseline=before,groups=len(facts["groups"]),
                                    scan=facts["scan"]["stop"],sha256=sha256(raw).hexdigest(),
                                    decoder_and_replay_s=round(time.perf_counter()-t,6)))
            if k != 5:
                continue
            fixed = [1,2,-3,-4,-5]
            damaged = list(z.clauses)
            # Fix selector bits, then use a model of the AMO-free problem to
            # pick one reproducible extension. Keeping every clause it satisfies
            # guarantees an explicit two-choice countermodel.
            with Solver(name="g3", bootstrap_with=[(x,) for x in fixed]) as oracle:
                assert oracle.solve()
                bits = set(oracle.get_model())
            bits.update(-v for v in range(6,z.nv+1))
            damaged = [r for r in damaged if any(x in bits for x in r)]
            with Solver(name="g3",bootstrap_with=damaged) as oracle:
                assert oracle.solve(assumptions=fixed)
            raw, mapped = rename(z.nv,damaged,4903)
            _, _, facts = decode.decode(raw)
            check.verify(raw,facts)
            assert sorted(mapped(x) for x in xs) not in facts["groups"]
            negatives.append(dict(encoding=kind,removed=len(z.clauses)-len(damaged),
                                  sha256=sha256(raw).hexdigest(),rejected_target=True))
    tabulate("encodings.csv",records)
    dump(OUT / "mutations.json",negatives)
    return records, negatives


def assignment_problem(options, kind, seed):
    nv = sum(map(len,options))
    selectors = iter(range(1,nv+1))
    columns, rows = {}, []
    for opts in options:
        xs = []
        for slot in opts:
            x = next(selectors)
            xs.append(x)
            columns.setdefault(slot,[]).append(x)
        z = CardEnc.equals(xs,bound=1,top_id=nv,encoding=getattr(EncType,kind))
        nv = max(nv,z.nv)
        rows += z.clauses
    for xs in columns.values():
        if len(xs)>1:
            z = CardEnc.atmost(xs,bound=1,top_id=nv,encoding=getattr(EncType,kind))
            nv = max(nv,z.nv)
            rows += z.clauses
    return rename(nv,rows,seed)[0]


def sudoku():
    n = 4
    def v(r,c,d): return 1 + (r*n+c)*n+d
    domains = [[v(r,c,d) for d in range(n)] for r in range(n) for c in range(n)]
    domains += [[v(r,c,d) for c in range(n)] for r in range(n) for d in range(n)]
    domains += [[v(r,c,d) for r in range(n)] for c in range(n) for d in range(n)]
    domains += [[v(rr+r,cc+c,d) for r in range(2) for c in range(2)]
                for rr in (0,2) for cc in (0,2) for d in range(n)]
    nv, rows = n**3, []
    for xs in domains:
        z = CardEnc.equals(xs,bound=1,top_id=nv,encoding=EncType.seqcounter)
        nv, rows = max(nv,z.nv), rows+z.clauses
    return rename(nv,rows,3106)[0]


def reencode_petersen(raw):
    nv, rows = parse(raw)
    groups = [c for c in rows if len(c)==3 and all(x>0 for x in c)]
    assert len(groups)==15 and len({x for g in groups for x in g})==45
    pairs = {frozenset((-a,-b)) for g in groups for a,b in combinations(g,2)}
    assert pairs <= {frozenset(c) for c in rows}
    kept = [c for c in rows if frozenset(c) not in pairs]
    for group in groups:
        z=CardEnc.atmost(group,bound=1,top_id=nv,encoding=EncType.seqcounter)
        nv=max(nv,z.nv)
        kept.extend(z.clauses)
    return rename(nv,kept,2307)[0]


def build_cases():
    cases = []
    def add(name, kind, raw, truth):
        f = OUT / "inputs" / (name+".cnf")
        f.parent.mkdir(exist_ok=True,parents=True)
        f.write_bytes(raw)
        cases.append(dict(name=name,type=kind,path=f,truth=truth,sha256=sha256(raw).hexdigest()))
    base=[(0,1,2),(0,1,3),(0,2,3),(1,2,3)]
    for kind in ("pairwise","seqcounter","cardnetwrk"):
        add("deficit-"+kind,"constructed",assignment_problem(base+[base[0]],kind,71),"UNSAT")
        add("feasible-"+kind,"constructed",assignment_problem(base,kind,81),"SAT")
    add("clique-five-four","constructed",assignment_problem([tuple(range(4))]*5,"seqcounter",107),"UNSAT")
    z=CardEnc.equals([1,2,3,4],bound=1,encoding=EncType.seqcounter)
    even=[[-x if bit else x for x,bit in zip(range(1,5),bits)]
          for bits in product((0,1),repeat=4) if sum(bits)%2==1]
    add("eo-plus-even","constructed",rename(z.nv,z.clauses+even,295)[0],"UNSAT")
    softened = [list(row) for row in even]
    softened[softened.index([-1,2,3,4])][0] = 1
    twin = rename(z.nv,z.clauses+softened,295)[0]
    # Same header, variable IDs and clause order. Exactly one sign changes.
    _, ca = parse(cases[-1]["path"].read_bytes())
    _, cb = parse(twin)
    assert sum(x != y for a,b in zip(ca,cb) for x,y in zip(a,b)) == 1
    add("eo-plus-even-one-flip","constructed",twin,"SAT")
    add("sudoku-four","constructed",sudoku(),"SAT")
    for name,path,truth,pin in [
        ("graph-k11","evidence/graph-k11/original.cnf","UNSAT","69d4e0ad868e920920d214acaf0c37f52870655ecc8a6807fd1ee3e4dcaa91e0"),
        ("pcmax-m00","evidence/pcmax-weighted2/00/original.cnf","UNSAT","c55ab8fe2c9e10f0579f806802bc32d04913f12cd6ce28e6662b8d59d114c174"),
        ("petersen","evidence/ipg7b-petersen/original.cnf","UNSAT","c2fefeffc1f9644ffd6f85728106a21c82dfc01d0d021f32d4d73569cc2bfb70"),
        ("uf20-01","research/structure1_corpus/uf20-01.cnf","SAT",None)]:
        raw=(ROOT/path).read_bytes()
        if pin: assert sha256(raw).hexdigest()==pin
        add(name,"archived",raw,truth)
        if name=="petersen": add("petersen-sequential","reencoded archived",reencode_petersen(raw),truth)
    return cases


def main():
    OUT.mkdir(exist_ok=True)
    records, negatives = recognition()
    print("EO_ENCODINGS", {k:sum(r["target_found"] for r in records if r["encoding"]==k)
                           for k in ENCODINGS},flush=True)
    cases=build_cases()
    dump(OUT/"inputs.json",[{k:str(v) for k,v in c.items()} for c in cases])
    rows=[]
    for case in cases:
        path=case["path"]
        for rep in range(3):
            methods=["ATLAS","ATLAS16","EO","Kissat4.0.4","CaDiCaL2.1.3"]
            for method in methods[rep:] + methods[:rep]:
                assert sha256(path.read_bytes()).hexdigest()==case["sha256"]
                where=OUT/"runs"/case["name"]/str(rep)/method
                where.mkdir(parents=True,exist_ok=True)
                if method in ("ATLAS","ATLAS16","EO"):
                    rec=run.auto({"source":path,"name":case["name"]},ROOT/"build/drnas-pcmax",
                                 folder=where,eo_only=method=="EO",enable_eo=method!="ATLAS16")
                else:
                    rec=run.reference(method,path,folder=where,solver_limit=run.CAP)
                status=rec["status"]
                if status in ("SAT_VERIFIED","UNSAT_VERIFIED"):
                    assert status==case["truth"]+"_VERIFIED", (case,method,rec)
                rows.append(dict(source=case["name"],kind=case["type"],sha256=case["sha256"],
                                 truth=case["truth"],rep=rep,method=method,status=status,
                                 route=rec.get("mode"),e2e_s=rec["e2e_s"]))
                dump(where/"result.json",rec)
        print("EO_CASE",case["name"],[(r["method"],r["status"],r["route"]) for r in rows
                                    if r["source"]==case["name"] and r["rep"]==0],flush=True)
    tabulate("trials.csv",rows)
    summary=[]
    for c in cases:
        for method in methods:
            rs=[r for r in rows if r["source"]==c["name"] and r["method"]==method]
            summary.append(dict(source=c["name"],type=c["type"],method=method,
                                verified=sum(r["status"] in ("SAT_VERIFIED","UNSAT_VERIFIED") for r in rs),
                                repeats=len(rs),median_e2e_s=round(median(r["e2e_s"] for r in rs),6),
                                routes="/".join(sorted({r["route"] or "-" for r in rs}))))
    tabulate("summary.csv",summary)
    for case in cases:
        print("EO_SOURCE_SUMMARY "+json.dumps([r for r in summary if r["source"]==case["name"]],
                                              separators=(",",":")),flush=True)
    for kind in ENCODINGS:
        rr=[r for r in records if r["encoding"]==kind]
        print("EO_ENCODING_SUMMARY "+json.dumps({"encoding":kind,"recognized":sum(r["target_found"] for r in rr),
                 "baseline":sum(r["literal_pairwise_baseline"] for r in rr),"n":len(rr)}),flush=True)
    p=OUT/"runs/eo-plus-even/0/EO/eo.pbp"
    twin=OUT/"inputs/eo-plus-even-one-flip.cnf"
    bad=subprocess.run(["veripb","--cnf",str(twin),str(p)],capture_output=True,text=True,timeout=10)
    assert bad.returncode!=0 and "s VERIFIED UNSATISFIABLE" not in bad.stdout
    print("EO_PROOF_REJECTED_ON_SIGN_FLIPPED_SAT_TWIN")
    assert all(r["verified"]==3 for r in summary if r["type"]=="constructed" and r["method"]=="EO"), summary
    assert any(r["routes"]=="EO_HALL" for r in summary) and any(r["routes"]=="EO_GRAPH" for r in summary)
    assert any(r["routes"]=="EO_XOR" for r in summary)
    assert all(r["verified"]==3 for r in summary if r["source"]=="sudoku-four" and r["method"]=="ATLAS")
    print("EO_VERIFIED_SUMMARY",json.dumps({"sources":len(cases),"attempts":len(rows),
          "recognized":sum(r["target_found"] for r in records),"recognition_tests":len(records),
          "baseline_recognized":sum(r["literal_pairwise_baseline"] for r in records),
          "negative_controls":len(negatives),
          "constructed":sum(c["type"]=="constructed" for c in cases),
          "archived":sum(c["type"]=="archived" for c in cases)},sort_keys=True),flush=True)


if __name__=="__main__":
    main()
