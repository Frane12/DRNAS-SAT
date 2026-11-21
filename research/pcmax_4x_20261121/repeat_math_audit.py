#!/usr/bin/env python3
"""Five independent end-to-end repeats of CNF-only structural PCMAX proof+source check.
This is a Python PCMAX/Hall experimental prototype, not the native C++ module.
CPU pinned; process startup, CNF read, discovery, cert write, and independent
fresh-process checker are included in per-repetition wall times.
"""
import argparse, csv, hashlib, json, os, statistics, subprocess, sys, time
from pathlib import Path

EXPECTED_SHA = "510afeeeba1478ebaa2ce4866680447ad496e2eec30ce1c88eb5f9f07f9a4cb9"
ROOT = Path(__file__).resolve().parents[2]
DETECTOR = ROOT / "research/pcmax_4x_20261121/source_bdd_hall_detector.py"
CHECKER = ROOT / "research/pcmax_capacity/check_capacity.py"

def run_timed(argv, label, outdir, cpu, timeout=150):
    metric = outdir / (label + ".time.txt")
    log = outdir / (label + ".stdout.json")
    err = outdir / (label + ".stderr.txt")
    command = ["/usr/bin/time", "-f",
               "wall_s=%e\nuser_cpu_s=%U\nsystem_cpu_s=%S\nmax_rss_kb=%M",
               "-o", str(metric), "taskset", "-c", str(cpu)] + list(argv)
    start = time.perf_counter()
    result = subprocess.run(command, text=True, capture_output=True, timeout=timeout)
    elapsed = time.perf_counter() - start
    log.write_text(result.stdout)
    err.write_text(result.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"{label} failed rc={result.returncode}: {result.stderr[-500:]}")
    stats = {}
    for line in metric.read_text().splitlines():
        if "=" in line:
            key, val = line.split("=", 1)
            stats[key] = float(val)
    return json.loads(result.stdout), {"elapsed_host_s":elapsed, **stats}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("cnf", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--repetitions", type=int, default=5)
    args=parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    raw=args.cnf.read_bytes()
    digest=hashlib.sha256(raw).hexdigest()
    assert digest == EXPECTED_SHA, ("unexpected CNF sha", digest)
    assert raw.startswith(b"p cnf 81055 704682\n")
    cpus=sorted(os.sched_getaffinity(0))
    assert cpus
    cpu=cpus[0]
    rows=[]
    for rep in range(1,args.repetitions+1):
        cert=args.output/f"rep{rep:02}.capacity.json"
        start=time.perf_counter()
        detected,det_time=run_timed([sys.executable,str(DETECTOR),str(args.cnf),"--cert",str(cert)],
                                   f"rep{rep:02}-detector",args.output,cpu)
        checked,check_time=run_timed([sys.executable,str(CHECKER),str(args.cnf),str(cert)],
                                    f"rep{rep:02}-checker",args.output,cpu)
        pair_elapsed=time.perf_counter()-start
        assert detected["status"]=="UNSAT_CERTIFICATE_EMITTED_UNCHECKED",detected
        assert checked["status"]=="UNSAT_STRUCTURAL_CERTIFICATE_VERIFIED",checked
        assert checked["source_sha256"]==digest
        assert checked["required"]==131 and checked["capacity_sum"]==129
        assert detected["required"]==131 and detected["capacity"]==129
        cert_doc=json.loads(cert.read_text())
        assert cert_doc["source_sha256"]==digest
        row={"rep":rep,"sha256":digest,"required":131,"capacity":129,
             "detector_wall_s":round(det_time["elapsed_host_s"],6),
             "checker_wall_s":round(check_time["elapsed_host_s"],6),
             "pair_wall_s":round(pair_elapsed,6),
             "detector_rss_kb":int(det_time.get("max_rss_kb",0)),
             "checker_rss_kb":int(check_time.get("max_rss_kb",0)),
             "detector_cpu_user_s":det_time.get("user_cpu_s"),
             "checker_cpu_user_s":check_time.get("user_cpu_s"),
             "source_clauses":704682,"source_variables":81055,
             "certificate_bytes":cert.stat().st_size,"result":"VERIFIED_UNSAT"}
        rows.append(row)
        print("REPEAT "+json.dumps(row,sort_keys=True),flush=True)
    # Negative control: a forged hash must be rejected even though the math fields are unchanged.
    forged=json.loads((args.output/"rep01.capacity.json").read_text())
    forged["source_sha256"]="0"*64
    forged_path=args.output/"forged_hash.capacity.json"
    forged_path.write_text(json.dumps(forged))
    attempted=subprocess.run(["taskset","-c",str(cpu),sys.executable,str(CHECKER),
                              str(args.cnf),str(forged_path)],
                             text=True,capture_output=True,timeout=60)
    if attempted.returncode==0:raise RuntimeError("critical: tampered certificate accepted")
    (args.output/"negative_hash_test.txt").write_text(
        f"REJECTED_AS_EXPECTED rc={attempted.returncode}\n"+
        attempted.stdout+attempted.stderr)
    keys=list(rows[0].keys())
    with (args.output/"results.csv").open("w",newline="") as fd:
        wr=csv.DictWriter(fd,fieldnames=keys);wr.writeheader();wr.writerows(rows)
    pairs=[r["pair_wall_s"] for r in rows]
    summary={"result":"5_OF_5_VERIFIED_UNSAT" if len(rows)==5 else "ALL_VERIFIED_UNSAT",
             "repetitions":len(rows),"input_sha256":digest,"variables":81055,
             "clauses":704682,"formula_family":"synthetic connected BDD PCMAX-style",
             "proof_kind":"independent project structural CNF checker; NOT VeriPB",
             "method":"Python CNF-only BDD extraction, Hall min cut, CNF-bound source checker",
             "cpu_pinned":cpu,"demand":131,"capacity":129,
             "wall_pair_s_median":statistics.median(pairs),
             "wall_pair_s_min":min(pairs),"wall_pair_s_max":max(pairs),
             "negative_forged_hash_rejected":True,"repeats":rows}
    (args.output/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print("SUMMARY "+json.dumps({k:v for k,v in summary.items() if k!="repeats"},sort_keys=True),flush=True)
if __name__=="__main__":main()
