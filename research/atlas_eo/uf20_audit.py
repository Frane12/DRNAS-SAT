"""Compare the full router and both references on the same 1,000 UF20-91 CNFs."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import monotonic

from research.atlas16_pilot import run
from research.atlas_eo.binary_cutset import candidate


def main(corpus, output):
    paths = sorted(corpus.glob("*.cnf"))
    assert len(paths) == 1000
    methods = ["ATLAS", "Kissat4.0.4", "CaDiCaL2.1.3"]
    values = {m: [] for m in methods}
    failures = {m: Counter() for m in methods}
    source_results = Counter()
    unique = set()
    output.mkdir(parents=True, exist_ok=True)
    with (output / "uf20.csv").open("w", newline="") as f, TemporaryDirectory() as temp:
        wr = csv.writer(f)
        wr.writerow(["case", "source_sha256", "dimacs_sha256", "method", "status", "seconds",
                     "route", "original_checked_model_hex"])
        for index, path in enumerate(paths):
            raw = path.read_bytes()
            n, rows = run.parse(raw)
            assert n == 20 and len(rows) == 91
            # Stock CLIs reject SATLIB's percent footer. Supply identical DIMACS to all arms.
            dimacs = run.encoded(n, rows)
            digest = run.sha(dimacs)
            assert digest not in unique
            unique.add(digest)
            src = Path(temp) / "input.cnf"
            src.write_bytes(dimacs)
            original_hash = run.sha(raw)
            raw_result = candidate(raw, monotonic()+1.0)
            if "model" in raw_result:
                run.verify_full_original_sat_model(raw, raw_result["model"])
                source_results["SAT_VERIFIED"] += 1
            else:
                source_results[raw_result["reason"]] += 1
            order = index % len(methods)
            for method in methods[order:] + methods[:order]:
                with TemporaryDirectory(dir=temp) as d:
                    folder = Path(d)
                    if method == "ATLAS":
                        result = run.auto({"source":src,"name":"case"}, run.ROOT/"build/drnas-pcmax",
                                          folder=folder)
                    else:
                        result = run.reference(method, src, folder=folder, solver_limit=run.CAP)
                    status = result["status"]
                    mask = ""
                    assert status != "UNSAT_VERIFIED"
                    if status == "SAT_VERIFIED":
                        model = json.loads((folder / "model.json").read_text())
                        assert model["source_sha256"] == digest
                        model["source_sha256"] = original_hash
                        run.verify_full_original_sat_model(raw, model)
                        mask = format(sum(1 << i for i,v in enumerate(model["assignment"][1:]) if v), "x")
                        values[method].append(result["e2e_s"])
                    else:
                        failures[method][status] += 1
                    wr.writerow([path.name, original_hash, digest, method, status, result["e2e_s"],
                                 result.get("mode"), mask])
    summary = {"distinct":len(unique), "raw_cutset":dict(source_results),
               "methods":{m:{"verified":len(values[m]), "unresolved":dict(failures[m]),
                             "median_verified_s":median(values[m]) if values[m] else None}
                          for m in methods}}
    (output / "summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    print("UF20_AUDIT", json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    main(args.corpus, args.output)
