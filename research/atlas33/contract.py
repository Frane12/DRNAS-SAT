"""ATLAS33: source-only implication contraction, no CDCL / external clauses.
Probe hypotheses are discharged immediately; only RUP consequences persist.
"""
import sys,time,json,collections,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'atlas31'))
import mrc as M
def serialize(n,cs):
    return ('p cnf %d %d\n'%(n,len(cs))+''.join(' '.join(map(str,sorted(c)))+' 0\n' for c in cs)).encode()
def contract(raw,out,mode,cap=25):
    t=time.monotonic();deadline=t+cap;n,original=M.parse(raw)
    cs=[frozenset(c) for c in original if not any(-l in c for l in c)]
    known=set(cs);cs=list(dict.fromkeys(cs));ix=collections.defaultdict(list);units=[];proof=[]
    def index(c,i):
        for l in c:ix[l].append(i)
        if len(c)==1:units.append(next(iter(c)))
    for i,c in enumerate(cs):index(c,i)
    def add(c):
        c=frozenset(c)
        if c not in known:
            known.add(c);proof.append(c);cs.append(c);index(c,len(cs)-1)
    end=min(deadline,t+5)
    def propagate(extra=(),limit=120000):
        a=set();q=collections.deque();work=0
        def push(l):
            if -l in a:return False
            if l not in a:a.add(l);q.append(l)
            return True
        if frozenset() in known:return False,a
        for l in list(units)+list(extra):
            if not push(l):return False,a
        while q:
            if work>limit or time.monotonic()>end:return None,a
            l=q.popleft()
            for i in ix[-l]:
                c=cs[i];work+=1
                if any(x in a for x in c):continue
                rem=[x for x in c if -x not in a]
                if not rem:return False,a
                if len(rem)==1 and not push(rem[0]):return False,a
        return True,a
    probes=0;failed=0;binary=0;root=set();conflict=False
    if mode:
        for sweep in range(3):
            ok,a=propagate()
            if ok is False:conflict=True;break
            if ok is None:break
            root=a
            for l in sorted(root):add([l])
            if len(proof)>12000:break
            changed=False
            vs=sorted({abs(l) for l in ix},key=lambda v:(-len(ix[v])-len(ix[-v]),v))
            for v in vs[:300]:
                if time.monotonic()>end or len(proof)>12000:break
                if v in root or -v in root:continue
                for l in (v,-v):
                    ok,a=propagate([l]);probes+=1
                    if ok is False:
                        add([-l]);failed+=1;changed=True;break
                    if ok is True and mode==2:
                        # Keep source-local pairs to avoid dense arbitrary implication graphs.
                        neighbors={abs(x) for k in (l,-l) for i in ix[k] for x in cs[i]}
                        for b in sorted(a-root-{l}):
                            if abs(b) in neighbors and frozenset((-l,b)) not in known and binary<1200:
                                add([-l,b]);binary+=1;changed=True
            if not changed:break
        ok,a=propagate()
        if ok is False:conflict=True
        if ok is True:root=a
        # Even if final propagation was capped, all prior root literals are certified.
        for l in sorted(root):add([l])
    if conflict:
        proof.append(frozenset());r=dict(status='UNSAT',reason='source_implication_contradiction')
    else:
        # Remove satisfied clauses, shorten by certified units, and subsume supersets.
        residual=set()
        for c in list(cs):
            if c&root:continue
            d=frozenset(l for l in c if -l not in root)
            add(d);residual.add(d)
        bins={c for c in residual if len(c)<=2}
        residual={c for c in residual if len(c)<=2 or not any(frozenset(pair) in bins for pair in __import__('itertools').combinations(c,2))}
        reduced=serialize(n,sorted(residual,key=lambda c:(len(c),sorted(c))))
        (out/'reduced.cnf').write_bytes(reduced)
        d=out/'mrc';d.mkdir(exist_ok=True)
        if time.monotonic()>=deadline:r=dict(status='UNKNOWN',reason='preprocess_cap')
        else:r=M.solve(reduced,d,width=12,cap=max(0,deadline-time.monotonic()))
        if r['status']=='SAT':
            a=json.loads((d/'model.json').read_text())
            for l in root:a[str(abs(l))]=int(l>0)
            if not all(any(a[str(abs(l))]==int(l>0) for l in c) for c in original):raise AssertionError('original model invalid')
            (out/'model.json').write_text(json.dumps(a))
        if r['status']=='UNSAT':
            p=d/'proof.drup'
            if p.exists() and r.get('audit')!='PROOF_INCOMPLETE':
                (out/'proof.drup').write_text(''.join(' '.join(map(str,sorted(c)))+' 0\n' for c in proof)+p.read_text())
            else:r['audit']='PROOF_INCOMPLETE'
        r['residual_clauses']=len(residual);r['residual_vars']=len({abs(l) for c in residual for l in c})
    if conflict:(out/'proof.drup').write_text(''.join(' '.join(map(str,sorted(c)))+' 0\n' for c in proof))
    r.update(mode=mode,probes=probes,failed_literals=failed,binary_consequences=binary,root_units=len(root),source_rup_steps=len(proof),total_s=time.monotonic()-t)
    return r
if __name__=='__main__':
    out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
    r=contract(Path(sys.argv[1]).read_bytes(),out,int(sys.argv[3]))
    (out/'result.json').write_text(json.dumps(r));print('DMD2_RESULT',json.dumps(r),flush=True)
