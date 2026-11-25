"""Fixed-seed matched-size prospective control; solver gets only the DIMACS file."""
import hashlib,json,os,random,sys
from pathlib import Path

CORE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(CORE))
from run import run


def main(out):
    out.mkdir(parents=True,exist_ok=False)
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    rng=random.Random(181926041)
    ids=list(range(8))
    manifest=[]
    for i in ids:
        hidden={v:rng.randrange(2) for v in range(1,501)}
        clauses=[]
        while len(clauses)<2130:
            c=[v*rng.choice((-1,1)) for v in rng.sample(range(1,501),3)]
            if i%2==1 or any(hidden[abs(l)]==(l>0) for l in c):
                clauses.append(c)
        path=out/f'{i}.cnf'
        path.write_text('p cnf 500 2130\n'+''.join(' '.join(map(str,c))+' 0\n' for c in clauses))
        manifest.append(dict(id=i,family='uniform' if i%2 else 'planted',sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    with (out/'runs.jsonl').open('x',buffering=1) as log:
        for rep in range(3):
            order=ids[:]
            random.Random(358993+rep).shuffle(order)
            for pos,i in enumerate(order):
                modes=['default','table-first']
                if (i+rep)%2: modes.reverse()
                for mode in modes:
                    ans=run(out/f'{i}.cnf',out/f'{i}-{rep}-{mode}.cert',5,mode,5)
                    assert ans['status'] in ('SAT','UNSAT','UNKNOWN','TIMEOUT','AUDIT_LIMIT'),ans
                    assert not (i%2==0 and ans['status']=='UNSAT'),ans
                    print(json.dumps(dict(**ans,id=i,rep=rep+1)),file=log)
if __name__=='__main__':main(Path(sys.argv[1]))
