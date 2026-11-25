"""Replay the exact 23 public originals used by the imported WORDLIFT23 kernel.

This is a selected, known development corpus, not a blind competition result.
Download provenance and raw SHA256s are pinned in validation/public23/manifest.json.
"""
import argparse
import bz2
import gzip
import hashlib
import json
import lzma
import os
import pathlib
import sys
import urllib.request
from run import run
from benchmark import source_hashes

ROOT=pathlib.Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['download','run'])
    parser.add_argument('--out',type=pathlib.Path,default=ROOT/'results/public23')
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    manifest=ROOT/'validation/public23/manifest.json'
    cases=json.loads(manifest.read_text());assert len(cases)==23
    (out/'cnf').mkdir(exist_ok=True)
    if args.command=='download':
        for case in cases:
            p=out/'cnf'/(case['id']+'.cnf')
            if p.exists() and hashlib.sha256(p.read_bytes()).hexdigest()==case['sha256']:continue
            with urllib.request.urlopen(case['url'],timeout=45) as stream:data=stream.read(128*1024*1024)
            assert hashlib.sha256(data).hexdigest()==case['packed_sha256'],'compressed input changed'
            if data.startswith(b'\xfd7zXZ\x00'):raw=lzma.decompress(data)
            elif data.startswith(b'\x1f\x8b'):raw=gzip.decompress(data)
            elif data.startswith(b'BZh'):raw=bz2.decompress(data)
            else:raw=data
            assert hashlib.sha256(raw).hexdigest()==case['sha256'],'source hash mismatch'
            p.write_bytes(raw)
        return
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    (out/'evidence').mkdir(exist_ok=True)
    (out/'source_hashes.json').write_text(json.dumps(source_hashes(),indent=2)+'\n')
    rows=[]
    with (out/'runs.jsonl').open('w') as log:
        for case in cases:
            source=out/'cnf'/(case['id']+'.cnf');assert hashlib.sha256(source.read_bytes()).hexdigest()==case['sha256']
            cert=out/'evidence'/(case['id']+'.cert')
            result=run(source,cert,seconds=15,audit_seconds=5)
            row=dict(case,**result)
            if result['status'] in ('SAT','UNSAT'):row['evidence_sha256']=hashlib.sha256(cert.read_bytes()).hexdigest()
            rows.append(row);log.write(json.dumps(row)+'\n');log.flush()
            print(case['id'],case['family'],result['status'],result.get('telemetry',{}).get('method'),flush=True)
    summary={'instances':len(rows),'solved':sum(r['status'] in ('SAT','UNSAT') for r in rows),
             'sat':sum(r['status']=='SAT' for r in rows),'unsat':sum(r['status']=='UNSAT' for r in rows),
             'solve_s':sum(r['solve_s'] for r in rows),'audit_s':sum(r.get('audit_s',0) for r in rows),
             'scope':'23 selected previously tested public originals; CORE only, no concurrent reference rerun',
             'cap_s':15,'audit_cap_s':5,'one_logical_cpu':True}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
    if any(r['status'] in ('ERROR','REJECTED') for r in rows):return 1
    return 0


if __name__=='__main__':sys.exit(main())
