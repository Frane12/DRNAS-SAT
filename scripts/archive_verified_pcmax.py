#!/usr/bin/env python3
"""Archive the 11 independently accepted PCMAX VeriPB proofs from their original Actions artifact.

Requires a GitHub Actions token that can fetch the public source run and the
pinned external VeriPB 3.0.2 checker. Rejects all missing or invalid evidence.
Does not change the original source repository.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZipFile

ARTIFACT_ID = 14164325633
URL = "https://api.github.com/repos/Frane12/AndroidGameTest/actions/artifacts/" + str(ARTIFACT_ID) + "/zip"
RUN_URL = "https://github.com/Frane12/AndroidGameTest/actions/runs/43719601339"
M14_SHA = "a540b7d1aa098217bde5145b56f1f8e4898e9fedd73ea1ad99259ed43fa1e275"

def command(args, timeout=180):
    p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError(f"command failed rc={p.returncode}: {args[0]} {p.stderr[-400:]}")
    return p.stdout + "\n" + p.stderr

def main():
    root = Path(__file__).resolve().parent.parent
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("GH_TOKEN missing; source proof archive NOT transferred")
    checker = os.environ.get("VERIPB_BIN", "veripb")
    with tempfile.TemporaryDirectory() as td:
        temp = Path(td)
        archive = temp / "old-actions.zip"
        command(["curl", "--fail", "--silent", "--show-error", "--location",
                 "--retry", "2",
                 "--header", "Accept: application/vnd.github+json",
                 "--header", "Authorization: Bearer " + token,
                 "--output", str(archive), URL], timeout=180)
        with ZipFile(archive) as z:
            names = set(z.namelist())
            manifest = "results/weighted2/summary.json"
            if manifest not in names:
                raise RuntimeError("original verified summary absent")
            records = json.loads(z.read(manifest))
            if len(records) != 20 or sum(bool(r.get("accepted")) for r in records) != 11:
                raise RuntimeError("expected original 20/11 verified coverage was not found")
            dest = root / "evidence" / "pcmax-weighted2"
            evidence = []
            for r in records:
                if not r["accepted"]:
                    continue
                ix = int(r["index"])
                prefix = "results/weighted2/" + f"{ix:02d}" + "/"
                proof_name = prefix + "weighted.pbp"
                source_name = "results/weighted2/originals/" + r["name"]
                log_name = prefix + "veripb.log"
                cap_name = prefix + "capacity.json"
                for n in (proof_name, source_name, log_name, cap_name):
                    if n not in names:
                        raise RuntimeError("missing accepted case artifact: " + n)
                original = z.read(source_name)
                proof = z.read(proof_name)
                stored_log = z.read(log_name).decode("utf-8")
                source_sha = hashlib.sha256(original).hexdigest()
                if source_sha != r["sha256"]:
                    raise RuntimeError("original CNF SHA mismatch: " + str(ix))
                if len(proof) != r["proof_bytes"]:
                    raise RuntimeError("proof length mismatch: " + str(ix))
                if "s VERIFIED UNSATISFIABLE" not in stored_log:
                    raise RuntimeError("old checker log not accepted: " + str(ix))
                work = temp / f"{ix:02d}"
                work.mkdir()
                cnf = work / "original.cnf"
                pbp = work / "weighted.pbp"
                cnf.write_bytes(original)
                pbp.write_bytes(proof)
                log = command([checker, "--cnf", str(cnf), str(pbp)], timeout=120)
                if "s VERIFIED UNSATISFIABLE" not in log:
                    raise RuntimeError("new pinned VeriPB checker rejected: " + str(ix))
                out = dest / f"{ix:02d}"
                out.mkdir(parents=True, exist_ok=True)
                (out / "original.cnf").write_bytes(original)
                (out / "weighted.pbp").write_bytes(proof)
                (out / "veripb.log").write_text(log)
                (out / "capacity.json").write_bytes(z.read(cap_name))
                item = {
                    "index": ix, "source_name": r["name"], "original_sha256": source_sha,
                    "proof_sha256": hashlib.sha256(proof).hexdigest(),
                    "proof_bytes": len(proof), "demand": r.get("demand"),
                    "capacity": r.get("capacity"), "veripb_3_0_2": "VERIFIED_UNSAT",
                }
                if ix == 5 and source_sha != M14_SHA:
                    raise RuntimeError("m14 exact source identity mismatch")
                evidence.append(item)
                print("TRANSFER_VERIFIED", json.dumps(item, sort_keys=True), flush=True)
            (dest / "summary.json").write_bytes(z.read(manifest))
            (dest / "verified_manifest.json").write_text(json.dumps(evidence, indent=2) + "\n")
            (dest / "README.md").write_text(
                "# DRNAS PCMAX Weighted VeriPB2 original evidence\n\n"
                "11 standard VeriPB 3.0.2 UNSAT proofs, each independently rechecked "
                "against an unchanged SHA-256-pinned original CNF in the new repository.\n\n"
                "The full retrospective source set has 20 instances; the other 9 "
                "returned UNKNOWN and do not have UNSAT proofs.\n\n"
                "Original run: " + RUN_URL + "\n\n"
                "Reproduce each accepted example: "
                "veripb --cnf 05/original.cnf 05/weighted.pbp\n\n"
                "This is a restricted SAT benchmark family and is not evidence of "
                "a general SAT complexity breakthrough.\n"
            )
            p = root / "evidence" / "pcmax-m14-3640-14524" / "README.md"
            p.write_text(p.read_text() +
                         "\nThe exact original and standard proof are now mirrored in "
                         "../pcmax-weighted2/05/ and independently rechecked.\n")
            print("PCMAX_ALL_11_STANDARD_VERIPB_PROOFS_MIRRORED", flush=True)

if __name__ == "__main__":
    main()
