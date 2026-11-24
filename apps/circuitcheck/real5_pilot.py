#!/usr/bin/env python3
"""REAL5 *development* replay on previously evaluated REAL4 public RTL.

Not blind: the first six-project REAL4 corpus was visible before REAL5 was
written. This experiment is solely a pilot, not generalization evidence.
No cherry picking: 5 synthesized original netlists must be replayed; HDMI
is recorded explicitly as frontend-unsupported in the fixed original run.
"""
from pathlib import Path
import argparse,hashlib,json

from real5_relations import generate
from real5_verify import verify

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--originals",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    seen={}
    for index in (0,1,2):
        base=args.originals/f"real4-shard-{index}"/"results"
        if not base.is_dir():raise RuntimeError("ORIGINAL_SHARD_MISSING "+str(base))
        for folder in sorted(base.iterdir()):
            if not (folder/"netlist.json").is_file():
                # HDMI may be unsupported and there is no gate proof.
                continue
            if folder.name in seen:raise RuntimeError("DUPLICATE_FROZEN_CASE")
            evidence=generate(folder)
            target=args.out/(folder.name+".json")
            target.write_text(json.dumps(evidence,indent=2)+"\n")
            checked=verify(folder,target)
            assert checked["status"]=="CHECKED_GF2_CROSSCONE_RELATIONS"
            assert evidence["stats"]["verified_nontrivial_relations"]>=len(evidence["relations"])
            seen[folder.name]={
                "status":evidence["status"],
                "source_netlist_sha256":sha(folder/"netlist.json"),
                "relations":len(evidence["relations"]),
                "external_relations":evidence["stats"]["external_relations_reported"],
                "internal_relations":evidence["stats"]["internally_sampled_relations_reported"],
                "cut_dependent_probes":evidence["stats"]["eligible_cut_dependent_probes"],
                "all_candidates":evidence["stats"]["candidate_pair_or_nullspace_relations"],
                "independent_replay":checked["status"]
            }
            print("REAL5_ORIGINAL_DEVELOPMENT_PILOT",folder.name,
                  "cutdependent",seen[folder.name]["cut_dependent_probes"],
                  "relations",seen[folder.name]["relations"],flush=True)
    expected={"aes_sbox","uart_tx","axis_fifo","picorv32","sha256_w_mem"}
    if set(seen)!=expected:raise RuntimeError("FIVE_ORIGINAL_NETLISTS_NOT_REPLAYED "+repr(set(seen)))
    summary={"protocol":"REAL5_PRIOR_REAL4_DEVELOPMENT_NOT_BLIND",
             "source_run":45341226748,
             "cases":seen,
             "hdmi":"FRONTEND_UNSUPPORTED_ORIGINAL_REAL4",
             "total_relations":sum(x["relations"] for x in seen.values())}
    (args.out/"pilot_summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    lines=["# REAL5 — retrospective five-project development pilot",
           "",
           "**NOT BLIND**. The original REAL4 external corpus was available before",
           "the REAL5 algorithm was designed; this is a gap-finding experiment.",
           "",
           "| Original RTL | Cut-dependent probes | Candidate algebraic dependencies | Proven nontrivial GF2 relations |",
           "|---|---:|---:|---:|"]
    for name,x in seen.items():
        lines.append(f"| {name} | {x['cut_dependent_probes']} | {x['all_candidates']} | {x['relations']} |")
    lines+=["","Original HDMI module remained frontend-unsupported (not dropped as success).",
            "Each original REAL4 proof and every candidate REAL5 relation is independently replayed.",
            "Zero is a scientifically meaningful outcome: treating every nonlinear",
            "gate output as an independent cut variable can prevent uncovering",
            "higher-order dependencies. No same-CNF solver speedup is claimed."]
    (args.out/"PILOT.md").write_text("\n".join(lines)+"\n")
    print("REAL5_DEVELOPMENT_PILOT_FIVE_FROZEN_CASES_COMPLETE",
          summary["total_relations"],flush=True)

if __name__=="__main__":main()
