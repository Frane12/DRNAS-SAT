"""ATLAS34 sparse Boolean relation projection (exact Davis-Putnam).
Bit-packed forbidden subcubes, subsumption and cost-aware pivots.
No decisions on assignments, CDCL, reference data or solver fallback.
"""
import sys,time,json,collections,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'atlas31'))
import mrc as M
def encode(c):
    p=q=0
    for l in c:
        if l>0:p|=1<<(l-1)
        else:q|=1<<(-l-1)
    return p,q
def bits(x):
    while x:
        b=x&-x;yield b;x^=b
def lits(c):
    return [b.bit_length() for b in bits(c[0])]+[-b.bit_length() for b in bits(c[1])]
def length(c):return c[0].bit_count()+c[1].bit_count()
def subset(a,b):return (a[0]&b[0])==a[0] and (a[1]&b[1])==a[1]
def solve(raw,out,adaptive,cap=25,handoff=False):
    t=time.monotonic();deadline=t+cap;n,cs=M.parse(raw);out.mkdir(parents=True,exist_ok=True)
    vs=sorted({abs(l) for c in cs for l in c})
    # Explicit pilot guard; large public inputs require another representation.
    if len(vs)>512:return dict(status='UNKNOWN',reason='active_variable_cap',decision_s=time.monotonic()-t)
    active=set();known=set();ix=collections.defaultdict(set);anchors=collections.defaultdict(set)
    def keys(c):return [(b,0) for b in bits(c[0])]+[(b,1) for b in bits(c[1])]
    def anchor(c):return next(iter(keys(c)),None)
    def put(c):
        if c in active:return
        active.add(c);anchors[anchor(c)].add(c)
        for k in keys(c):ix[k].add(c)
    def drop(c):
        active.remove(c);anchors[anchor(c)].remove(c)
        for k in keys(c):ix[k].remove(c)
    for c in cs:
        a=encode(c)
        if not a[0]&a[1]:known.add(a);put(a)
    history=[];proof=[];steps=0;peak=len(active);peak_width=0;pair_total=0;subsumed=0;blocked=0
    def finish(status,reason):
        if status=='UNKNOWN' and handoff:
            (out/'residual.json').write_text(json.dumps(dict(active=[lits(c) for c in sorted(active)],history=[(v.bit_length(),[lits(c) for c in sorted(removed)]) for v,removed in history])))
            writeproof()
        return dict(status=status,reason=reason,decision_s=time.monotonic()-t,steps=steps,peak_clauses=peak,peak_scope=peak_width,pair_checks=pair_total,subsumed=subsumed,blocked_candidates=blocked,remaining_clauses=len(active),remaining_vars=len({b for c in active for b in bits(c[0]|c[1])}),proof_steps=len(proof))
    def writeproof():
        with (out/'proof.drup').open('w') as f:
            for c in proof:f.write(' '.join(map(str,lits(c)))+' 0\n')
    def contradiction(reason):
        if not proof or proof[-1]!=(0,0):proof.append((0,0))
        r=finish('UNSAT',reason);writeproof();return r
    def evaluate(v,p,q):
        nonlocal pair_total
        removed=p|q
        if len(p)*len(q)>4000:return None
        rr=set()
        for a in p:
            if time.monotonic()>deadline:return None
            for b in q:
                pair_total+=1
                c=((a[0]|b[0])&~v,(a[1]|b[1])&~v)
                if c[0]&c[1]:continue
                if c==(0,0):return removed,{c},set()
                if c not in active or c in removed:rr.add(c)
        # Retain only minimal resolvents modulo all surviving clauses.
        new=collections.defaultdict(set);keep=set();deletions=set()
        for c in sorted(rr,key=lambda x:(length(x),x)):
            if time.monotonic()>deadline:return None
            ks=keys(c)
            if any(subset(d,c) for k in ks for d in anchors[k] if d not in removed):continue
            if any(subset(d,c) for k in ks for d in new[k]):continue
            keep.add(c);new[anchor(c)].add(c)
            # Exact subsumption: remove surviving supersets of retained resolvents.
            k=min(ks,key=lambda k:len(ix[k]))
            deletions.update(d for d in ix[k] if d not in removed and subset(c,d))
        return removed,keep,deletions
    if (0,0) in active:return contradiction('original_empty')
    while active:
        if time.monotonic()>deadline:return finish('UNKNOWN','time_cap')
        if handoff and steps>=4 and len(active)>max(1000,8*len(cs)):return finish('UNKNOWN','growth_handoff')
        if len(active)>20000 or len(proof)>100000:return finish('UNKNOWN','memory_cap')
        vars_=set(b for b,s in ix if ix[b,s])
        if not vars_:raise AssertionError('empty index')
        order=sorted(vars_,key=lambda v:(len(ix[v,0])*len(ix[v,1]),len(ix[v,0])+len(ix[v,1]),v))
        opts=[]
        for v in order[:(8 if adaptive else 1)]:
            p,q=ix[v,0],ix[v,1]
            if not p or not q:
                opts=[((-len(p)-len(q),0,v),v,(p|q,set(),set()))];break
            r=evaluate(v,p,q)
            if r is None:blocked+=1;continue
            removed,keep,deletions=r
            if (0,0) in keep:
                if (0,0) not in known:proof.append((0,0))
                return contradiction('sparse_resolution_contradiction')
            net=len(keep)-len(removed)-len(deletions)
            # Cap growth, not scope: narrow and wide clauses share same sparse format.
            if len(active)+net>20000 or len(proof)+len(keep)>100000:blocked+=1;continue
            opts.append(((net,sum(map(length,keep)),v),v,r))
        if not opts:return finish('UNKNOWN','time_cap' if time.monotonic()>deadline else 'pair_or_growth_cap')
        _,v,(removed,keep,deletions)=min(opts,key=lambda x:x[0])
        scope=0
        for c in removed:scope|=c[0]|c[1]
        peak_width=max(peak_width,scope.bit_count())
        history.append((v,removed))
        for c in removed|deletions:drop(c)
        subsumed+=len(deletions)
        for c in sorted(keep,key=lambda x:(length(x),x)):
            if c not in known:known.add(c);proof.append(c)
            put(c)
        steps+=1;peak=max(peak,len(active))
    # Reverse exact existential projection.
    a=0
    def satisfied(c,a):return bool(c[0]&a or c[1]&~a)
    for v,removed in reversed(history):
        if all(satisfied(c,a) for c in removed):continue
        a|=v
        if not all(satisfied(c,a) for c in removed):raise AssertionError('reverse lift')
    model={i:int(bool(a&(1<<(i-1)))) for i in range(1,n+1)}
    if not all(any(model[abs(l)]==int(l>0) for l in c) for c in cs):raise AssertionError('original model')
    (out/'model.json').write_text(json.dumps(model))
    return finish('SAT','sparse_model_lifted')
if __name__=='__main__':
    p=Path(sys.argv[1]);out=Path(sys.argv[2]);r=solve(p.read_bytes(),out,bool(int(sys.argv[3])))
    (out/'result.json').write_text(json.dumps(r));print('SPARSE_RESULT',json.dumps(r),flush=True)
