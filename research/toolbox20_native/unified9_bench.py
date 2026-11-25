"""Paired adaptive-representation test, with replay and public diagnostics separated."""
import argparse,collections as C,io,json,os,re,subprocess,tarfile,time
from pathlib import Path
from corpus import sha,download,parse_source,encode
from unified6_utility import corpus,load,dump
from unified7_failure import OLD,MISS
from verify import check_model,check_unsat
CAP=5.
U8="66a47e0c868e93c9de619f6cac81feddc8f5ca05"
U8_REPLAY={4,10,11,16,22,23}
HASHES={4:"1160914944ccb1073d3fc7243479f00df70578c57c0cef8591787dab09e6efb8",10:"2acfd07c01959b8b3f3cb660ef947185a853b8ef1996f16229d16d6e0bc141fd",11:"66e188e62a18d175fb34379a9d912a5572febf33a29e716f07566dc70c918551",16:"7fa87f4caeae646875f58bb0ef5632420ad945951fa3b12e73b93196bd2395b1",22:"ffcb5317fb646eb2ecc1f4253a8ecb843715c0c554b518c8abcd3a2227c6936b",23:"c96a37aaf7732c908110185ee1cd4e311312b0d0dff96da9995a05e2133a815a"}
def run(root,row,arm,paths,checker):
    path,raw=load(root,row);d=root/"evidence"/row["id"]/arm;d.mkdir(parents=True)
    proof=d/"proof";env=dict(os.environ,DRNAS_U8_MODE="2",DRNAS_U9_MODE="0" if arm=="fixed" else "1")
    cmd=[paths[arm],str(path),str(proof)] if arm in ("kissat","cadical") else [paths[arm],str(path),str(proof),str(CAP-.12)]
    start=time.monotonic()
    try:
        x=subprocess.run(cmd,env=env,capture_output=True,timeout=CAP)
        elapsed=time.monotonic()-start;out=x.stdout.decode("ascii","replace")
        status={10:"SAT",20:"UNSAT",0:"UNKNOWN"}.get(x.returncode,"ERROR")
        if {"SAT":"s SATISFIABLE","UNSAT":"s UNSATISFIABLE","UNKNOWN":"s UNKNOWN"}.get(status) not in out.splitlines():
            raise ValueError("bad solver output "+out[-300:]+x.stderr.decode(errors="replace")[-300:])
    except subprocess.TimeoutExpired as e:
        elapsed=time.monotonic()-start;out=(e.stdout or b"").decode("ascii","replace");status="TIMEOUT"
    if elapsed>CAP:status="TIMEOUT"
    (d/"solver.out").write_text(out);verified=""
    if status=="SAT":verified=check_model(raw,out)
    elif status=="UNSAT":verified=check_unsat(path,proof,checker)
    phase=re.search(r"^c phase (\S+) (.*)$",out,re.M);tele={}
    if phase:
        fields=phase[2].split()
        tele={k:int(v) for k,v in zip(fields[::2],fields[1::2]) if k.startswith(("meta_","factor_")) and v.isdigit()}
    return dict(id=row["id"],family=row["family"],group=row["group"],arm=arm,status=status,verified=verified,elapsed=elapsed,sha256=row["sha256"],phase=phase[1] if phase else "",**tele)
def solved(r):return r["status"] in ("SAT","UNSAT")
def summarize(rows,arms):
    by=C.defaultdict(dict)
    for r in rows:by[r["id"]][r["arm"]]=r
    out={}
    for a in arms:
        rr=[p[a] for p in by.values()]
        out[a]=dict(n=len(rr),solved=sum(map(solved,rr)),sat=sum(r["status"]=="SAT" for r in rr),unsat=sum(r["status"]=="UNSAT" for r in rr),par2=sum(r["elapsed"] if solved(r) else 2*CAP for r in rr)/len(rr),
            changed=sum(r.get("meta_changes",0)>0 for r in rr),joins=sum(r.get("meta_joins",0) for r in rr),join_facts=sum(r.get("meta_join_facts",0) for r in rr),affine=sum(r.get("meta_affine",0) for r in rr),affine_facts=sum(r.get("meta_affine_facts",0) for r in rr),novel=sum(r.get("meta_novel",0) for r in rr),gains=[i for i,p in by.items() if solved(p[a]) and not solved(p["u8"])],regressions=[i for i,p in by.items() if not solved(p[a]) and solved(p["u8"])])
    return out
def main():
    p=argparse.ArgumentParser()
    for k in ("u8","u9","kissat","cadical","checker","out"):p.add_argument("--"+k,type=Path,required=True)
    p.add_argument("--freeze",required=True);a=p.parse_args()
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    root=a.out;root.mkdir();(root/"replay").mkdir()
    replay=[]
    for label,freeze,ids,spec in [("u6",OLD,MISS,[("random3",30),("tseitin",10),("colour",10)]),("u8",U8,U8_REPLAY,[("random3",30),("tseitin",6),("colour",6),("circuit",4),("mixed",4)])]:
        old=root/label;old.mkdir()
        prior=corpus(old,freeze,"test",spec)
        for r in prior:
            if r["family"]!="random3" or int(r["id"].split("-")[-1]) not in ids:continue
            raw=(old/"test"/(r["id"]+".cnf")).read_bytes()
            if label=="u8":assert sha(raw)==HASHES[int(r["id"].split("-")[-1])]
            cid="replay-"+label+"-"+r["id"].split("-",1)[1]
            (root/"replay"/(cid+".cnf")).write_bytes(raw);replay.append(dict(r,id=cid,group="replay"))
    assert len(replay)==14
    fresh=[dict(r,group="fresh") for r in corpus(root,a.freeze,"test",[("random3",30),("tseitin",6),("colour",6),("circuit",4),("mixed",4)])]
    # Public source-pinned SATLIB replay, not a blind public holdout.
    public=[];folder=root/"public";folder.mkdir();cache=folder/"archives";cache.mkdir()
    manifest=json.loads((Path(__file__).parent/"results/manifest.json").read_text())
    for fam,meta in manifest["archives"].items():
        chosen=min((c for c in manifest["cases"] if c["group"]=="public" and c["family"]==fam),key=lambda c:(c["n"],c["id"]))
        try:
            data=download(cache,fam,meta["sha256"])
            with tarfile.open(fileobj=io.BytesIO(data),mode="r:gz") as tar:raw=tar.extractfile(chosen["member"]).read()
            assert sha(raw)==chosen["original_sha256"]
            n,cs=parse_source(raw);canonical=encode(n,cs);assert sha(canonical)==chosen["cnf_sha256"]
            cid="public-"+chosen["id"]
            (folder/(cid+".cnf")).write_bytes(canonical)
            public.append(dict(chosen,id=cid,group="public",sha256=sha(canonical)))
        except Exception as e:
            print("U9_PUBLIC_UNAVAILABLE",fam,repr(e),flush=True)
    rows=[];arms=["u8","fixed","adaptive","kissat","cadical"]
    paths={k:str(getattr(a,"u9" if k in ("fixed","adaptive") else k).resolve()) for k in arms}
    assert len({r["sha256"] for r in replay+fresh+public})==len(replay+fresh+public)
    dump(root/"manifest.json",dict(freeze=a.freeze,replay=replay,test=fresh,public=public,cap=CAP))
    for i,row in enumerate(replay+fresh+public):
        rr=[]
        for arm in arms[i%5:]+arms[:i%5]:
            r=run(root,row,arm,paths,str(a.checker.resolve()));rr.append(r);rows.append(r)
            print("U9_ROW",json.dumps(r,sort_keys=True),flush=True)
        if len({r["status"] for r in rr if solved(r)})>1:raise ValueError("contradictory accepted answers")
        dump(root/"results.json",rows)
    out={g:summarize([r for r in rows if r["group"]==g],arms) for g in ("replay","fresh","public") if any(r["group"]==g for r in rows)}
    dump(root/"summary.json",out);print("U9_SUMMARY",json.dumps(out),flush=True)
if __name__=="__main__":main()
