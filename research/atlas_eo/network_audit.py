"""Audit direct capacity cuts and full models across signed network encodings."""
import json
import subprocess

from research.atlas_eo.benchmark import OUT, ROOT, assignment_problem, dump, encoded, parse, run


def verify_case(raw, name, expected, folder):
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / "original.cnf"
    source.write_bytes(raw)
    result = run.auto({"source": source, "name": name}, ROOT / "build/drnas-pcmax",
                      folder=folder, eo_only=True)
    assert result["status"] == expected + "_VERIFIED", (name, result)
    return result


def main():
    base = OUT / "network-audit"
    records = []
    for size in (4, 5, 6):
        jobs = [tuple(i for i in range(size) if i != missing) for missing in range(size)]
        for enc in ("seqcounter", "cardnetwrk", "sortnetwrk", "totalizer", "mtotalizer"):
            for seed in (71, 99, 233):
                for deficit in (False, True):
                    options = jobs + [jobs[0]] if deficit else jobs
                    name = f"{enc}-{size}-{seed}-{len(options)}"
                    raw = assignment_problem(options, enc, seed)
                    status = "UNSAT" if deficit else "SAT"
                    result = verify_case(raw, name, status, base / name)
                    if deficit:
                        assert (result["mode"], result["demand"], result["capacity"]) == (
                            "EO_HALL", size + 1, size), (name, result)
                    records.append({"name": name, "status": result["status"],
                                    "mode": result["mode"], "sha256": result["source_sha256"]})
    original = OUT / "runs/deficit-cardnetwrk/0/ATLAS"
    demand = json.loads((original / "result.json").read_text())["demand_literals"][0]
    nv, rows = parse((OUT / "inputs/deficit-cardnetwrk.cnf").read_bytes())
    idx = next(i for i, row in enumerate(rows) if set(row) == set(demand))
    first, *rest = rows[idx]
    rows[idx] = (-first, *rest)
    twin = base / "one-sign-flip"
    verify_case(encoded(nv, rows), twin.name, "SAT", twin)
    rejected = subprocess.run(["veripb", "--cnf", str(twin/"original.cnf"), str(original/"eo.pbp")],
                              capture_output=True, text=True, timeout=15)
    assert rejected.returncode != 0 and "s VERIFIED UNSATISFIABLE" not in rejected.stdout
    (twin / "proof-check.log").write_text(rejected.stdout + rejected.stderr)
    dump(base / "summary.json", records)
    print("NETWORK_AUDIT", len(records), "cases, 45 direct Hall proofs, 45 verified models; signed twin SAT, old proof rejected")


if __name__ == "__main__":
    main()
