"""Local congruence and unit propagation on recovered functions; proof by RUP.
No branching. Every emitted clause is independently checked by unit propagation.
"""
import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'atlas27_integrated'))
import engine as E
def up(cs,assumptions):
    a={}
    for l in assumptions:
        if -l in a:return True
        a[l]=1
    while True:
        changed=False
        for c in cs:
            if any(l in a for l in c):continue
            rem=[l for l in c if -l not in a]
            if not rem:return True
            if len(rem)==1 and rem[0] not in a:a[rem[0]]=1;changed=True
        if not changed:return False
def solve(raw):
    n,cs=E.g.parse(raw);cs=[tuple(dict.fromkeys(c)) for c in cs if not any(-l in c for l in c)]
    cand,res,added=E.compact(cs)
    plan=E.g.make_plan(cand,res,cs,n,'numeric') or E.g.make_plan(cand,res,cs,n,'structure')
    proof=[];known=set()
    def emit(c):
        c=tuple(c)
        if c in known:return True
        if not up(cs,[-l for l in c]):return False
        cs.append(c);proof.append(c);known.add(c);return True
    if emit([]):return 'UNSAT',proof,added
    if plan:
        topo,roots=plan; reps={v:v for v in roots}; signatures={}
        for g in topo:
            z=g['out'];ins=g['ins'];t=g['table']
            args=[reps[x] for x in ins]
            # Normalize input ordering, including repeated inputs.
            scope=sorted(set(args)); table=0
            for i in range(1<<len(scope)):
                ix=sum(((i>>scope.index(x))&1)<<j for j,x in enumerate(args))
                table|=((t>>ix)&1)<<i
            key=(tuple(scope),table)
            if key in signatures:
                q=signatures[key]
                # Congruence is not necessarily RUP directly. Derive conditional
                # equality for every local input row, then resolve away inputs.
                for direction in (0,1):
                    target=[-z,q] if direction==0 else [z,-q]
                    rows=[tuple(target+[(-v if i>>j&1 else v) for j,v in enumerate(scope)]) for i in range(1<<len(scope))]
                    if not all(emit(c) for c in rows):break
                    for k in range(len(scope)-1,-1,-1):
                        rows=[c[:-1] for c in rows if c[-1]==scope[k]]
                        if not all(emit(c) for c in rows):break
                    if not emit(target):break
                else:reps[z]=q;continue
            signatures[key]=z;reps[z]=z
        if emit([]):return 'UNSAT',proof,added
    return 'UNKNOWN',proof,added
def verify(raw,proof):
    _,cs=E.g.parse(raw)
    for c in proof:
        assert up(cs,[-l for l in c])
        cs.append(c)
    return bool(proof) and not proof[-1]
if __name__=='__main__':
    import time
    out=Path(sys.argv[2]);out.mkdir(exist_ok=True)
    for i,p in enumerate(sorted(Path(sys.argv[1]).rglob('*.cnf'))):
        raw=p.read_bytes();t=time.perf_counter();s,proof,g=solve(raw)
        if s=='UNSAT':assert verify(raw,proof)
        (out/f'{i}.drup').write_text(''.join(' '.join(map(str,c))+' 0\n' for c in proof))
        print('ATLAS28',json.dumps(dict(file=str(p),status=s,steps=len(proof),compact=g,seconds=time.perf_counter()-t)),flush=True)
