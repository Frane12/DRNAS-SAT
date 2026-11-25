"""Replay the previous 36 inputs and six documented BF/SSA controls, outside transfer."""
import argparse
import csv
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
from bench import run_one
from corpus import download, encode, parse_source, sha

CONTROLS = {
    "bridge": ["bf1355-075.cnf"],
    "stuck": ["ssa0432-003.cnf", "ssa6288-047.cnf", "ssa7552-038.cnf",
              "ssa7552-158.cnf", "ssa7552-160.cnf"],
}


def main():
    parser = argparse.ArgumentParser()
    for name in ("previous", "corpus", "drnas", "checker", "out"):
        parser.add_argument("--"+name,type=Path,required=True)
    a=parser.parse_args()
    a.out.mkdir(parents=True,exist_ok=False)
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    manifest=json.loads(a.previous.read_text())
    cases=[(row["id"],"previous36",a.corpus/(row["id"]+".cnf"),row["cnf_sha256"])
           for row in manifest["cases"]]
    saved=set()
    with tempfile.TemporaryDirectory() as tmp:
        tmp=Path(tmp)
        for family,names in CONTROLS.items():
            data=download(a.corpus/"archives",family,manifest["archives"][family]["sha256"])
            with tarfile.open(fileobj=io.BytesIO(data),mode="r:gz") as archive:
                for name in names:
                    member=next(m for m in archive if Path(m.name).name==name)
                    raw=encode(*parse_source(archive.extractfile(member).read()))
                    path=tmp/name
                    path.write_bytes(raw)
                    cases.append((path.stem,"fault6",path,sha(raw)))
        neutral=tmp/"input.cnf";proof=tmp/"proof"
        fields=["id","group","cnf_sha256","rep","status","phase","wall_s","check_s","method",
                "detail","telemetry","evidence","evidence_sha256"]
        with (a.out/"runs.csv").open("w",newline="") as stream:
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
            for rep in range(1,4):
                for case,group,path,digest in cases:
                    data=path.read_bytes()
                    if sha(data)!=digest: raise ValueError("input digest mismatch")
                    neutral.write_bytes(data)
                    row=run_one("DRNAS",[a.drnas.resolve(),neutral,proof,"3"],neutral,proof,
                                a.checker.resolve(),3,a.out/"evidence"/case,saved)
                    writer.writerow(dict(id=case,group=group,cnf_sha256=digest,rep=rep,**row));stream.flush()
                    if row["status"] in ("ERROR","AUDIT_FAILED"):
                        raise ValueError(row["detail"])
                print(f"replay repetition {rep}/3",flush=True)


if __name__=="__main__": main()
