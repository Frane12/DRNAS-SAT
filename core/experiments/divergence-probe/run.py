"""Run the pre-specified mean selector and diagnostic forced-choice controls."""
from pathlib import Path
import hashlib,json,os,random,subprocess,sys,tempfile,time
CORE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(CORE))
from verify import parse_cnf,verify
from table_verify import verify_tables

def main(root,out):
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    out.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((root/'priority-fresh/manifest.json').read_text())
    keys=['F26','H09']
    with (out/'runs.jsonl').open('x',buffering=1) as log, tempfile.TemporaryDirectory() as tmp:
        tmp=Path(tmp)
        for rep in range(3):
            for ident in keys:
                src=CORE/'regression/F26.cnf' if ident=='F26' else root/'priority-fresh/H09.cnf'
                assert hashlib.sha256(src.read_bytes()).hexdigest()==manifest[ident]['sha256']
                d=root/'priority-fixed'/ident
                n,cs=parse_cnf(src)
                lines=(d/'messages.txt').read_text().splitlines()
                verify_tables(src,cs,n,lines+['suffix','0'],time.monotonic()+5)
                modes=['table-first','table-rank']
                for mode in modes:
                    subprocess.run([CORE/'bin/priority-order',src,d/'active.rows',d/'messages.txt',mode,tmp/mode],
                                   stdout=subprocess.DEVNULL,check=True)
                policies=['mean','force-first','force-rank']
                random.Random(rep+419).shuffle(policies)
                for policy in policies:
                    model=out/f'{ident}-{rep+1}-{policy}.model'
                    proc=subprocess.run([CORE/'bin/divergence-trial',str(n),tmp/modes[0],tmp/modes[1],
                                         tmp/'trace',policy,model],text=True,capture_output=True,check=True,timeout=20)
                    row=json.loads(proc.stdout)
                    assert row['charged']==sum(row['lane_flips'])<=2160000
                    if row['status']=='SAT':
                        assert verify(src,model,10)==('SAT','MODEL')
                        row['model_sha256']=hashlib.sha256(model.read_bytes()).hexdigest()
                    else:assert not model.exists()
                    print(json.dumps(dict(id=ident,rep=rep+1,policy=policy,**row)),file=log)
if __name__=='__main__':main(Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve())
