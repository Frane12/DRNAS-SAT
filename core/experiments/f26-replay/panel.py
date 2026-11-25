"""Freeze both native states, independently replay claims and cross state/order."""
import collections,hashlib,json,os,random,subprocess,sys,tempfile,time
from pathlib import Path
CORE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(CORE))
from verify import verify,parse_cnf
from table_verify import verify_tables

SRC=CORE/'regression/F26.cnf'
BIN=CORE/'bin/f26-replay'
def rows(p): return p.read_text().splitlines()
def canon(s): return frozenset(map(int,s.split()[:-1]))
def write(p,r):p.write_text(''.join(s+'\n' for s in r))

def capture(dest):
    dest.mkdir(parents=True,exist_ok=False)
    for mode in ('table-first','default'):
        d=dest/mode;d.mkdir()
        proc=subprocess.run([BIN,SRC,d/'answer.cert','5',mode],env={**os.environ,'DRNAS_CAPTURE_STATE':str(d)},
                            text=True,capture_output=True,timeout=5.5)
        assert proc.returncode in (0,10),proc.stderr
        (d/'native.log').write_text(proc.stdout)
        if proc.returncode==10: assert verify(SRC,d/'answer.cert',10)==('SAT','MODEL')

def main(states,out):
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    if not states.exists():capture(states)
    out.mkdir(parents=True,exist_ok=False)
    direct=states/'table-first';base=states/'default'
    if (direct/'answer.cert').exists():assert verify(SRC,direct/'answer.cert',10)==('SAT','MODEL')
    n,cs=parse_cnf(SRC)
    claims,_=verify_tables(SRC,cs,n,rows(direct/'messages.txt')+['suffix','0'],time.monotonic()+5)
    # verify_tables validates lemmas only. The dummy suffix is never used as a refutation.
    assert len(claims)==6
    keys={frozenset(c):i for i,c in enumerate(claims)}
    assert len(keys)==6
    a,b=[rows(p/'active.rows') for p in (direct,base)]
    strip=lambda rr:[s for s in rr if canon(s) not in keys]
    assert strip(a)==strip(b) and collections.Counter(a)==collections.Counter(b)
    assert all(sum(canon(s)==k for s in a)==1 for k in keys)
    with tempfile.TemporaryDirectory() as tmp:
        t=Path(tmp)
        write(t/'claims',[' '.join(map(str,c))+' 0' for c in claims])
        p=subprocess.run([CORE/'bin/check-rup',SRC,base/'ledger.rows','--prefix',t/'claims'],
                         capture_output=True,text=True,check=True)
        print(p.stdout.strip(),flush=True)
        # Mask subsets at their original direct-mode insertion positions.
        arms={f'mask-{m:02d}':([s for s in a if canon(s) not in keys or m>>keys[canon(s)]&1],direct)
              for m in range(64)}
        arms.update({'base-native':(b,base),'base-order-direct-ledger':(b,direct),
                     'direct-order-base-ledger':(a,base)})
        audit={'source_sha256':hashlib.sha256(SRC.read_bytes()).hexdigest(),'clauses':claims,
               'positions_direct':[next(i+1 for i,s in enumerate(a) if canon(s)==frozenset(c)) for c in claims],
               'positions_base':[next(i+1 for i,s in enumerate(b) if canon(s)==frozenset(c)) for c in claims],
               'active_count':len(a),'other_rows_identical_in_order':True,'default_rup_check':p.stdout.strip(),
               'phase_caps_ms':{'projection':150,'cooperation':90,'model_repair':2000 if os.getenv('DRNAS_FULL_REPAIR') else 145}}
        (out/'design.json').write_text(json.dumps(audit,indent=2))
        with (out/'runs.jsonl').open('x',buffering=1) as log:
            for rep in range(3):
                order=list(arms)
                random.Random(318421+rep).shuffle(order)
                for arm in order:
                    active,ledger=arms[arm]
                    write(t/'active.rows',active)
                    (t/'ledger.rows').write_bytes((ledger/'ledger.rows').read_bytes())
                    cert=t/'model'
                    cert.unlink(missing_ok=True)
                    proc=subprocess.run([BIN,SRC,cert,'5'],env={**os.environ,'DRNAS_REPLAY_STATE':str(t)},
                                        capture_output=True,text=True,timeout=5.5)
                    assert proc.returncode in (0,10),proc.stderr
                    tele=json.loads(next(s[2:] for s in proc.stdout.splitlines() if s.startswith('c ')))
                    row=dict(arm=arm,rep=rep+1,status='UNKNOWN',projected=tele['unified_projected'],
                             flips=tele['unified_repair_flips'],elapsed=tele['elapsed_s'])
                    if proc.returncode==10:
                        assert verify(SRC,cert,10)==('SAT','MODEL')
                        raw=cert.read_bytes();sha=hashlib.sha256(raw).hexdigest()
                        (out/(sha+'.model')).write_bytes(raw)
                        row.update(status='SAT',sha256=sha)
                    if os.getenv('DRNAS_FULL_REPAIR') and row['status']=='UNKNOWN':
                        assert row['flips']==36*60000,row
                    print(json.dumps(row),file=log)
                print('Completed F26 repetition',rep+1,flush=True)
if __name__=='__main__':main(Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve())
