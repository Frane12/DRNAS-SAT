"""Move only certified table lemmas within each fresh formula's frozen active set."""
from pathlib import Path
import collections,hashlib,json,os,subprocess,sys,tempfile,time
from panel import BIN,canon,rows,write
from verify import verify,parse_cnf
from table_verify import verify_tables


def main(corpus,out):
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    out.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory() as tmp,(out/'runs.jsonl').open('x',buffering=1) as log:
        t=Path(tmp)
        for item in json.loads((corpus/'manifest.json').read_text()):
            i=item['id'];src=corpus/f'{i}.cnf'
            assert hashlib.sha256(src.read_bytes()).hexdigest()==item['sha256']
            d=out/str(i);d.mkdir()
            p=subprocess.run([BIN,src,d/'native.cert','5','table-first'],capture_output=True,text=True,
                    env={**os.environ,'DRNAS_CAPTURE_STATE':str(d)},timeout=5.5)
            assert p.returncode in (0,10,20),p.stderr
            if p.returncode:verify(src,d/'native.cert',p.returncode)
            (d/'native.log').write_text(p.stdout)
            if not (d/'active.rows').exists():
                print(json.dumps(dict(id=i,skip='did not reach projection/model stage')),file=log);continue
            lines=rows(d/'messages.txt')
            if len(lines)==1:
                print(json.dumps(dict(id=i,skip='no direct messages')),file=log);continue
            n,cs=parse_cnf(src)
            claims,_=verify_tables(src,cs,n,lines+['suffix','0'],time.monotonic()+5)
            keys={frozenset(c) for c in claims}
            active=rows(d/'active.rows')
            affected=[s for s in active if canon(s) in keys]
            assert len(affected)==len(keys)
            moved=[s for s in active if canon(s) not in keys]+affected
            assert collections.Counter(active)==collections.Counter(moved)
            (t/'ledger.rows').write_bytes((d/'ledger.rows').read_bytes())
            for rep in range(3):
                arms=[('native-order',active),('moved-last',moved)]
                if (rep+i)%2:arms.reverse()
                for arm,state in arms:
                    write(t/'active.rows',state)
                    cert=d/f'{arm}-{rep+1}.cert'
                    p=subprocess.run([BIN,src,cert,'5'],capture_output=True,text=True,
                      env={**os.environ,'DRNAS_FULL_REPAIR':'1','DRNAS_REPLAY_STATE':str(t)},timeout=5.5)
                    assert p.returncode in (0,10),p.stderr
                    tele=json.loads(next(s[2:] for s in p.stdout.splitlines() if s.startswith('c ')))
                    if p.returncode:verify(src,cert,10)
                    print(json.dumps(dict(id=i,rep=rep+1,arm=arm,claims=len(claims),
                      status='SAT' if p.returncode else 'UNKNOWN',flips=tele['unified_repair_flips'],
                      projected=tele['unified_projected'])),file=log)
if __name__=='__main__':main(Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve())
