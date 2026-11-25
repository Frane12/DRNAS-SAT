"""Paired replay of the same native state; additionally measure an oracle over single priorities."""
import collections,concurrent.futures,hashlib,json,math,os,random,subprocess,sys,tempfile,time
from pathlib import Path
from pilot import CORE,digest
from verify import parse_cnf,verify
from table_verify import verify_tables
BIN=CORE/'bin/f26-replay'
def read_rows(p):
    return [tuple(sorted(set(map(int,s.split()[:-1])),key=abs)) for s in p.read_text().splitlines()]

def strings(rows):
    return ''.join(' '.join(map(str,c))+' 0\n' for c in rows)

def batch(args):
    out,corpus,ids,cpu=args
    os.sched_setaffinity(0,{cpu})
    manifest=json.loads((corpus/'manifest.json').read_text())
    for ident in ids:
        d=out/ident;d.mkdir()
        src=CORE/'regression/F26.cnf' if ident=='F26' else corpus/(ident+'.cnf')
        assert digest(src)==manifest[ident]['sha256']
        p=subprocess.run([BIN,src,d/'native.cert','5','table-first'],capture_output=True,text=True,
                         env={**os.environ,'DRNAS_CAPTURE_STATE':str(d)},timeout=5.6)
        assert p.returncode in (0,10,20),p.stderr
        if p.returncode:verify(src,d/'native.cert',p.returncode)
        (d/'native.log').write_text(p.stdout)
        if not (d/'active.rows').exists():
            (d/'skip.txt').write_text('solver finished before model discovery');continue
        lines=(d/'messages.txt').read_text().splitlines()
        if len(lines)<2:
            (d/'skip.txt').write_text('no certified table claims');continue
        n,cs=parse_cnf(src)
        claims,_=verify_tables(src,cs,n,lines+['suffix','0'],time.monotonic()+5)
        active=read_rows(d/'active.rows')
        keys={frozenset(c) for c in claims}
        original=active[:len(cs)];suffix=active[len(cs):]
        candidates=[c for c in suffix if frozenset(c) in keys]
        others=[c for c in suffix if frozenset(c) not in keys]
        assert len(candidates)==len(keys)
        counts=collections.Counter(l for c in original for l in c)
        scores=[math.prod((1+counts[-l])/(2+counts[-l]+counts[l]) for l in c) for c in candidates]
        best=max(range(len(scores)),key=scores.__getitem__)
        def ordering(j):return original+[candidates[j]]+others+candidates[:j]+candidates[j+1:]
        with tempfile.TemporaryDirectory() as tmp:
            t=Path(tmp);inputs={}
            for arm in ('table-first','table-pick-first','table-rank'):
                ordered=t/arm
                res=subprocess.check_output([CORE/'bin/priority-order',src,d/'active.rows',d/'messages.txt',arm,ordered],text=True)
                expected=active if arm=='table-first' else ordering(0 if arm=='table-pick-first' else best)
                assert read_rows(ordered)==expected
                if arm=='table-rank':assert int(res.split()[0])==best+1
                inputs[arm]=ordered.read_bytes()
            for j in range(len(candidates)):
                inputs[f'ordinal-{j+1}']=strings(ordering(j)).encode()
            (d/'selection.json').write_text(json.dumps(dict(chosen=best+1,candidates=candidates,scores=scores),indent=2))
            # Identical orderings share the same three physical runs, recorded as aliases.
            aliases=collections.defaultdict(list)
            for arm,data in inputs.items():aliases[data].append(arm)
            (t/'ledger.rows').write_bytes((d/'ledger.rows').read_bytes())
            with (d/'runs.jsonl').open('x',buffering=1) as log:
                for rep in range(3):
                    order=list(aliases);random.Random(31895+rep).shuffle(order)
                    for data in order:
                        arms=aliases[data];(t/'active.rows').write_bytes(data)
                        cert=t/'model';cert.unlink(missing_ok=True)
                        p=subprocess.run([BIN,src,cert,'5'],capture_output=True,text=True,timeout=5.6,
                          env={**os.environ,'DRNAS_FULL_REPAIR':'1','DRNAS_REPLAY_STATE':str(t)})
                        assert p.returncode in (0,10),p.stderr
                        tel=json.loads(next(s[2:] for s in p.stdout.splitlines() if s.startswith('c ')))
                        row=dict(arms=arms,id=ident,rep=rep+1,status='SAT' if p.returncode else 'UNKNOWN',
                                 flips=tel['unified_repair_flips'],projected=tel['unified_projected'])
                        if p.returncode:
                            assert verify(src,cert,10)==('SAT','MODEL')
                            raw=cert.read_bytes();sha=hashlib.sha256(raw).hexdigest()
                            (d/(sha+'.model')).write_bytes(raw);row['model']=sha
                        print(json.dumps(row),file=log)

if __name__=='__main__':
    corpus,out=map(lambda p:Path(p).resolve(),sys.argv[1:3])
    out.mkdir(parents=True,exist_ok=False)
    ids=list(json.loads((corpus/'manifest.json').read_text()))
    cpus=sorted(os.sched_getaffinity(0))[:3]
    with concurrent.futures.ProcessPoolExecutor(max_workers=len(cpus)) as pool:
        list(pool.map(batch,[(out,corpus,ids[i::len(cpus)],c) for i,c in enumerate(cpus)]))
