"""Original frozen ATLAS22 CNFs and signed/permuted controls, no manifests passed."""
import json,random,time,sys,os
from pathlib import Path
from engine import solve,parse
from verify import verify
def permute(raw,seed):
    n,cs=parse(raw);r=random.Random(seed);p=list(range(1,n+1));r.shuffle(p);s=[r.choice([-1,1]) for _ in p]
    cc=[[(1 if l>0 else -1)*p[abs(l)-1]*s[abs(l)-1] for l in c] for c in cs]
    r.shuffle(cc)
    for c in cc:r.shuffle(c)
    return ('p cnf %d %d\n'%(n,len(cc))+''.join(' '.join(map(str,c))+' 0\n' for c in cc)).encode()
def main(src,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);rows=[]
    for f in sorted(Path(src).rglob('*.cnf')):
        raw=f.read_bytes()
        for seed in (None,26001,26002,26003):
            inp=raw if seed is None else permute(raw,seed)
            name=f.stem+'_'+('original' if seed is None else str(seed))
            start=time.perf_counter();result=solve(inp);dt=time.perf_counter()-start
            try:audit=verify(inp,result)
            except Exception as e:
                audit='CHECKER_REJECTED_'+str(e);raise
            expected='UNSAT' if f.stem=='original_mismatch' else 'SAT'
            assert result['status'] in (expected,'UNKNOWN'),(name,result['status'])
            row={k:v for k,v in result.items() if k not in ('plan','model','roots','residual')}
            row.update(case=name,expected=expected,audit=audit,solve_s=round(dt,6),verified_e2e_s=round(time.perf_counter()-start,6),roots=len(result.get('roots',[])))
            rows.append(row);print('ATLAS26_ROW',json.dumps(row),flush=True)
            (out/(name+'.cnf')).write_bytes(inp)
            (out/(name+'.json')).write_text(json.dumps(result))
            (out/'summary.json').write_text(json.dumps(rows,indent=2))
    assert len(rows)==12
    print('ATLAS26_FINAL',json.dumps({s:sum(r['status']==s for r in rows) for s in ('SAT','UNSAT','UNKNOWN')}),flush=True)
if __name__=='__main__':main(*sys.argv[1:])
