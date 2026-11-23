#!/usr/bin/env python3
"""Pre-registered holdout runner: unchanged original Yosys DIMACS, two repeats.

Runs SELECTIVE-MIX3 / clean Kissat / clean CaDiCaL sequentially on the SAME
logical CPU, wall-time budgets 12s; four independent shards. Every error,
UNKNOWN, missing proof, regression and timeout remains in the report.
Synthetic new circuit families do NOT constitute independent third-party RTL.
"""
from __future__ import annotations
import argparse, hashlib, json, os, platform, re, subprocess, sys, time
from pathlib import Path
from pilot import one_command, sat_status, check_sat_model, dimacs_meta, textsha

ARMS = ("SELECTIVE-MIX3","Kissat","CaDiCaL")
CAP = 12.0
REPEATS = 2

def provenance_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def assert_frozen_case(case):
    rtl=Path(case['rtl'])
    if not rtl.is_file() or textsha(rtl)!=case['rtl_sha256']:
        raise RuntimeError("Frozen RTL file hash does not match: "+str(rtl))
    assert case['expected'] in ('SAT','UNSAT')
    assert case['family'] in ('gray','lfsr','adder')

def run_shard(args):
    cpu=sorted(os.sched_getaffinity(0))[0]
    args.out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(args.manifest.read_text())
    assert manifest["protocol"]=="MIX3_HOLDOUT_FROZEN_20261123"
    cases=manifest['cases']
    assert len(cases)==16
    for c in cases: assert_frozen_case(c)
    subset=[c for i,c in enumerate(cases) if i%args.shards==args.shard]
    data={"method":"same-CNF independent runner single-core repeated 12s",
          "shard":args.shard,"shards":args.shards,"cpu":cpu,
          "cap":CAP,"repeats":REPEATS,
          "metadata":{"platform":platform.platform(),"frozen_manifest_sha256":textsha(args.manifest),
                      "mix3_source_sha256":textsha(args.mix3),
                      "mix2_binary_sha256":textsha(args.mix2),
                      "kissat_binary_sha256":textsha(args.kissat),
                      "cadical_binary_sha256":textsha(args.cadical)},
          "cases":[]}
    for case in subset:
        name=case['case']
        cnf=args.out/f"{name}.cnf"
        ys=f"read_verilog {case['rtl']}; hierarchy -check -top miter; proc; flatten; opt; sat -timeout 1 -set mismatch 1 -dump_cnf {cnf}"
        synth=one_command(['yosys','-p',ys],cpu,90)
        (args.out/f"{name}.yosys.log").write_text(synth['output'])
        record={k:case[k] for k in ('case','family','width','fault','expected','rtl_sha256')}
        record["yosys_seconds"]=round(synth["seconds"],6)
        record["trials"]=[]
        record["dimacs"]=None
        if not cnf.is_file() or not cnf.stat().st_size:
            record["error"]="CNF_EXPORT_FAILED"
            data["cases"].append(record)
            (args.out/"shard.json").write_text(json.dumps(data,indent=2))
            continue
        record["dimacs"]={**dimacs_meta(cnf),"sha256":textsha(cnf),"size_bytes":cnf.stat().st_size}
        print("HOLDOUT_SOURCE",name,record['dimacs']['vars'],record['dimacs']['clauses'],record['dimacs']['sha256'],flush=True)
        for repeat in range(REPEATS):
            # Order rotation mitigates systematic CPU heating/cache carryover.
            order=list(ARMS)
            if repeat%2:order.reverse()
            for arm in order:
                if arm=='SELECTIVE-MIX3':
                    cmd=['python3',args.mix3,cnf,'--kissat',args.kissat,
                         '--mix2',args.mix2,'--total-cap','11.8',
                         '--probe','0.25','--mix-budget','6.5']
                elif arm=='Kissat':cmd=[args.kissat,cnf]
                else:cmd=[args.cadical,cnf]
                trial=one_command(cmd,cpu,CAP)
                status=sat_status(trial['output'],trial['return_code'],trial['timeout'])
                route_m=re.search(r'(?m)^c DRNAS_MIX3_ROUTE via=([^ ]+)',trial['output'])
                route=route_m.group(1) if route_m else None
                witness=check_sat_model(cnf,trial['output']) if status=='SAT' else None
                project=False
                if arm=='SELECTIVE-MIX3' and status=='UNSAT' and route=='mix2_project_check_required':
                    verify=one_command(['python3',args.checker,cnf,'--expected','UNSAT'],cpu,120)
                    (args.out/f"{name}.{arm}.{repeat}.source-check.json").write_text(verify['output'])
                    project=verify['return_code']==0 and not verify['timeout']
                # Validation must not relabel an unsupported claim as a verified solve.
                audited=(status=='SAT' and witness is True) or \
                        (status=='UNSAT' and arm=='SELECTIVE-MIX3' and
                         route=='mix2_project_check_required' and project)
                if status in ('SAT','UNSAT') and status!=case['expected']:
                    raise RuntimeError(f"INCORRECT_VERDICT {name} {arm} {status} expected {case['expected']}")
                if status=='SAT' and witness is not True:
                    raise RuntimeError(f"UNCHECKED_SAT {name} {arm} model={witness}")
                if status=='UNSAT' and arm=='SELECTIVE-MIX3' and route=='mix2_project_check_required' and not project:
                    raise RuntimeError(f"MIX3_UNCHECKED_UNSAT {name}")
                result={
                    "arm":arm,"repeat":repeat,"status":status,
                    "seconds":round(trial['seconds'],6),"timed_out":trial['timeout'],
                    "route":route,"return_code":trial['return_code'],
                    "sat_model_checked":witness,"project_source_checked":project,
                    "independent_standard_unsat_certificate":False,
                    "passed_available_checks":audited or status=='UNSAT'
                }
                record["trials"].append(result)
                (args.out/f"{name}.{arm}.{repeat}.log").write_text(trial['output'])
                print("HOLDOUT_TRIAL",name,arm,repeat,status,result['seconds'],route,
                      "SAT_verified" if witness else "", "PROJECT_UNSAT_CHECK" if project else "",flush=True)
                # Persist after each trial; on failure the artifact remains auditable.
                if record not in data["cases"]:data["cases"].append(record)
                (args.out/"shard.json").write_text(json.dumps(data,indent=2))
    print("HOLDOUT_SHARD_DONE",args.shard,len(subset),flush=True)

def aggregate(args):
    manifests=json.loads(args.manifest.read_text())
    cases=manifests['cases']
    rows={}
    for shard in range(args.shards):
        f=args.combined/f"shard-{shard}"/"shard.json"
        if not f.exists():raise RuntimeError("Missing shard "+str(shard))
        piece=json.loads(f.read_text())
        assert piece['shard']==shard and piece['shards']==args.shards
        assert piece['metadata']['frozen_manifest_sha256']==textsha(args.manifest)
        for c in piece["cases"]:
            assert c["case"] not in rows
            rows[c["case"]]=c
    assert set(rows)==set(x["case"] for x in cases), "missing or duplicated formulas"
    summary={"protocol":"prospective_family_disjoint_synthetic_holdout",
             "source_manifest_sha256":textsha(args.manifest),
             "cap":CAP,"repeats":REPEATS,"cases":rows,
             "scores":{}}
    lines=["# DRNAS SELECTIVE-MIX3 — prospective unseen synthetic-circuit holdout",
           "",
           "**Frozen before results:** GRAY round-trip, LFSR scrambler and ripple-carry adder.",
           "Not independent third-party hardware and not peer-reviewed.",
           "Every case has equal (UNSAT) and injected-fault (SAT) control.",
           "Matched original Yosys DIMACS, one CPU per arm, 12 s cap, two repetitions.",
           "**Strict UNSAT proofs absent:** Kissat/CaDiCaL UNSAT verdicts are not external standard certificates;",
           "MIX3 structural UNSAT outcomes require the separate project source checker.",
           "",
           "| Family | Width | Expected | MIX3 | Kissat | CaDiCaL |",
           "|---|---:|---|---|---|---|"]
    totals={arm:{"par2_seconds":0.0,"solved":0,"timeouts":0,"attempts":0,
                 "sat_checked":0,"mix2_project_unsat_checked":0,
                 "standard_unsat_verified":0} for arm in ARMS}
    family_totals={fam:{arm:0.0 for arm in ARMS} for fam in ('gray','lfsr','adder')}
    for entry in cases:
        row=rows[entry["case"]]
        actual=row.get('trials',[])
        if len(actual)!=REPEATS*len(ARMS):
            raise RuntimeError(f"Incomplete outcomes: {entry['case']}: {len(actual)}")
        score={}
        for arm in ARMS:
            trials=sorted((x for x in actual if x['arm']==arm),key=lambda x:x['repeat'])
            assert len(trials)==REPEATS and [x['repeat'] for x in trials]==list(range(REPEATS))
            total=0
            for t in trials:
                if t['status'] in ('SAT','UNSAT') and t['seconds']<=CAP:
                    if t['status']!=entry['expected']:raise RuntimeError("invalid expected status")
                    if t['status']=='SAT' and t['sat_model_checked'] is not True:raise RuntimeError("unchecked SAT")
                    if arm=='SELECTIVE-MIX3' and t['status']=='UNSAT' and t['route']=='mix2_project_check_required' and not t['project_source_checked']:
                        raise RuntimeError("unchecked MIX3")
                    total+=t['seconds'];totals[arm]['solved']+=1
                else:
                    total+=CAP*2
                    if t['status']=='TIMEOUT':totals[arm]['timeouts']+=1
                totals[arm]['attempts']+=1
                if t['sat_model_checked'] is True:totals[arm]['sat_checked']+=1
                if t['project_source_checked']:totals[arm]['mix2_project_unsat_checked']+=1
                if t['independent_standard_unsat_certificate']:totals[arm]['standard_unsat_verified']+=1
            totals[arm]['par2_seconds']+=total
            family_totals[entry['family']][arm]+=total
            score[arm]=f"{trials[0]['status']} {trials[0]['seconds']:.3f}s / {trials[1]['status']} {trials[1]['seconds']:.3f}s"
        lines.append("| "+entry['family']+" | "+str(entry['width'])+" | "+entry['expected']+
                     " | "+score['SELECTIVE-MIX3']+" | "+score['Kissat']+
                     " | "+score['CaDiCaL']+" |")
    lines.extend(["","## Aggregate PAR-2 (timeout = 24 s per trial)","",
                  "| Solver | Solved / 32 | Timeouts | PAR-2 seconds | SAT models checked | MIX2 project UNSAT checked |",
                  "|---|---:|---:|---:|---:|---:|"])
    for arm in ARMS:
        x=totals[arm]
        lines.append(f"| {arm} | {x['solved']}/32 | {x['timeouts']} | {x['par2_seconds']:.3f} | {x['sat_checked']} | {x['mix2_project_unsat_checked']} |")
    lines.extend(["","## PAR-2 by family","","| Family | MIX3 | Kissat | CaDiCaL |","|---|---:|---:|---:|"])
    for fam,v in family_totals.items():
        lines.append(f"| {fam} | {v['SELECTIVE-MIX3']:.3f} | {v['Kissat']:.3f} | {v['CaDiCaL']:.3f} |")
    if totals['SELECTIVE-MIX3']['par2_seconds']:
        ratio=totals['Kissat']['par2_seconds']/totals['SELECTIVE-MIX3']['par2_seconds']
        lines.extend(["",f"**Kissat PAR-2 / MIX3 PAR-2 = {ratio:.3f}×** on this frozen synthetic cohort."])
    lines.extend(["","Zero universal solver superiority claims. Missing standard UNSAT proofs are an explicit validation gap.",
                  "Report regressions and UNKNOWNs, no retuning to these cases."])
    summary["scores"]=totals;summary["family_scores"]=family_totals
    args.report.write_text("\n".join(lines)+"\n")
    args.output.write_text(json.dumps(summary,indent=2)+"\n")
    print(args.report.read_text())

def main():
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest='mode',required=True)
    p=sub.add_parser('shard')
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--shard',type=int,required=True)
    p.add_argument('--shards',type=int,default=4)
    for name in ('mix3','mix2','kissat','cadical','checker'):
        p.add_argument('--'+name,type=Path,required=True)
    p=sub.add_parser('aggregate')
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--combined',type=Path,required=True)
    p.add_argument('--shards',type=int,default=4)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if args.mode=='shard':run_shard(args)
    else:aggregate(args)

if __name__=='__main__':
    main()
