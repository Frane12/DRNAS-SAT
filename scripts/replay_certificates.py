"""Verify the checked-in PCMAX, graph, XOR and Petersen certificates."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

EVIDENCE = Path(__file__).resolve().parents[1] / "evidence"


def certificates():
    pcmax = EVIDENCE / "pcmax-weighted2"
    for row in json.loads((pcmax / "verified_manifest.json").read_text()):
        folder = pcmax / f"{row['index']:02}"
        yield (row["source_name"], folder / "original.cnf", row["original_sha256"],
               folder / "weighted.pbp", row["proof_sha256"])
    structural = json.loads((EVIDENCE / "structural-replay.json").read_text())
    for row in structural["verified_cases"]:
        if row["mirrored_example"]:
            folder = EVIDENCE / row["mirrored_example"]
            yield (row["case"], folder / "original.cnf", row["cnf_sha256"],
                   folder / "proof.pbp", row["proof_sha256"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--veripb", default="veripb", help="path to the VeriPB executable")
    args = parser.parse_args()
    count = 0
    for name, source, source_hash, proof, proof_hash in certificates():
        for path, expected in ((source, source_hash), (proof, proof_hash)):
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError(f"SHA-256 mismatch for {path}")
        result = subprocess.run([args.veripb, "--cnf", source, proof],
                                capture_output=True, text=True)
        if result.returncode or "s VERIFIED UNSATISFIABLE" not in result.stdout.splitlines():
            raise ValueError(f"{name}: checker did not accept the proof\n"
                             f"{result.stdout}{result.stderr}")
        print(f"VERIFIED  {name}", flush=True)
        count += 1
    print(f"{count} original CNF/proof pairs accepted.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        sys.exit(str(error))
