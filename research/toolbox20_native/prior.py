"""Collect explicit CNF file names and order-insensitive fingerprints before draw."""
import argparse
import json
import re
import subprocess
import zipfile
from collections import Counter
from pathlib import Path
from corpus import fingerprint, parse_source, sha

NAME = re.compile(rb"[a-z0-9][a-z0-9_.+-]{1,125}\.cnf\b",re.I)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("repo",type=Path);p.add_argument("toolboxes",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args(); hashes=set(); names=set(); counts=Counter(); packages={}
    def collect(data, name, source):
        suffix=Path(name).suffix.lower()
        names.update(s.decode("ascii").lower() for s in NAME.findall(data))
        if suffix == ".cnf":
            names.add(Path(name).name.lower())
            try: n,cs=parse_source(data)
            except ValueError: return
            hashes.add(fingerprint(n,cs));counts[source+"_dimacs"]+=1
        elif suffix == ".json":
            try: doc=json.loads(data)
            except (ValueError,UnicodeError):return
            def visit(x):
                if isinstance(x,dict):
                    n=x.get("n",x.get("nvars",x.get("variables")))
                    cs=x.get("cnf",x.get("clauses"))
                    if isinstance(n,int) and isinstance(cs,list) and all(isinstance(c,list) and all(type(l) is int and 0<abs(l)<=n for l in c) for c in cs):
                        hashes.add(fingerprint(n,cs));counts[source+"_json_cnfs"]+=1
                    for v in x.values():
                        if isinstance(v,(dict,list)): visit(v)
                elif isinstance(x,list):
                    for v in x:
                        if isinstance(v,(dict,list)):visit(v)
            visit(doc)
    for path in sorted(a.toolboxes.glob("math_closure_toolbox*.zip")):
        packages[path.name]=sha(path.read_bytes())
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if Path(name).suffix.lower() in {".cnf",".csv",".md",".py",".json",".txt"}:
                    collect(z.read(name),name,"toolbox")
    cmd=["git","-C",str(a.repo)]
    files=subprocess.check_output(cmd+["rev-list","--objects","--all"]).decode().splitlines()
    proc=subprocess.Popen(cmd+["cat-file","--batch"],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    for line in files:
        oid,sep,name=line.partition(" ")
        if not sep or Path(name).suffix.lower() not in {".cnf",".csv",".md",".py",".json",".txt",".yml",".cpp",".hpp",".tsv"}: continue
        proc.stdin.write((oid+"\n").encode());proc.stdin.flush()
        length=int(proc.stdout.readline().split()[2])
        data=proc.stdout.read(length); proc.stdout.read(1)
        collect(data,name,"git"); counts["git_blobs"]+=1
    proc.stdin.close()
    if proc.wait(): raise RuntimeError("git cat-file failed")
    counts.update({"unique_fingerprints":len(hashes),"explicit_names":len(names),"toolbox_archives":len(packages)})
    a.out.write_text(json.dumps(dict(fingerprints=sorted(hashes),names=sorted(names),counts=dict(counts),packages=packages),indent=2)+"\n")
    print(dict(counts))

if __name__=="__main__":main()
