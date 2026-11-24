"""Bounded functional cut signatures and locally generated RUP proofs.
All cuts are evaluated exactly; SAT branching and CDCL are not used.
"""
import sys,time,json,itertools,collections,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'atlas28_local'))
from closure import E
K=6; KEEP=20; MAX_STEPS=30000; MAX_SECONDS=12
class RUP:
    def __init__(self,cs):
        self.cs=[];self.idx=collections.defaultdict(list);self.units=[];self.empty=False
        for c in cs:self.add(c)
    def add(self,c):
        c=tuple(dict.fromkeys(c));i=len(self.cs);self.cs.append(c)
        if not c:self.empty=True
        if len(c)==1:self.units.append(c[0])
        for l in c:self.idx[l].append(i)
    def check(self,assumptions):
        if self.empty:return True
        a=set();queue=collections.deque()
        def assign(l):
            if -l in a:return False
            if l not in a:a.add(l);queue.append(l)
            return True
        for l in itertools.chain(self.units,assumptions):
            if not assign(l):return True
        while queue:
            l=queue.popleft()
            for i in self.idx[-l]:
                c=self.cs[i]
                if any(x in a for x in c):continue
                rem=[x for x in c if -x not in a]
                if not rem:return True
                if len(rem)==1 and not assign(rem[0]):return True
        return False

def compose(ins,t,combo):
    sc=tuple(sorted(set(v for s,m in combo for v in s)))
    if len(sc)>K:return None
    pos={v:i for i,v in enumerate(sc)}
    loc=[tuple(pos[v] for v in s) for s,m in combo]
    result=0
    for row in range(1<<len(sc)):
        gateidx=0
        for j,((s,m),p) in enumerate(zip(combo,loc)):
            ix=sum(((row>>x)&1)<<h for h,x in enumerate(p))
            gateidx|=((m>>ix)&1)<<j
        result|=((t>>gateidx)&1)<<row
    return sc,result

def normalize(sc,m):
    # Canonical support, including polarity. Keep full cut separately for proof.
    support=[]
    for i,v in enumerate(sc):
        if any(((m>>r)^(m>>(r^(1<<i))))&1 for r in range(1<<len(sc))):support.append(i)
    reduced=0
    for i in range(1<<len(support)):
        j=sum(((i>>h)&1)<<p for h,p in enumerate(support))
        reduced|=((m>>j)&1)<<i
    full=(1<<(1<<len(support)))-1
    inv=bool(reduced&1)
    return (tuple(sc[i] for i in support),reduced^full if inv else reduced),inv

def solve(raw):
    start=time.perf_counter();n,cs=E.g.parse(raw)
    cs=[tuple(dict.fromkeys(c)) for c in cs if not any(-l in c for l in c)]
    cand,res,added=E.compact(cs)
    plan=E.g.make_plan(cand,res,cs,n,'numeric') or E.g.make_plan(cand,res,cs,n,'structure')
    proof=[];known=set();rup=RUP(cs)
    stats={'compact':added,'gates':len(cand),'dag':bool(plan),'cuts':0,'matches':0,'equalities':0,'constants':0,'rejected':0,'rounds':0}
    def emit(c):
        c=tuple(sorted(set(c),key=lambda l:(abs(l),l)))
        if c in known:return True
        if len(proof)>=MAX_STEPS or time.perf_counter()-start>MAX_SECONDS:return False
        if not rup.check([-l for l in c]):return False
        rup.add(c);known.add(c);proof.append(c);return True
    def certify(target,scope):
        if len(scope)>K:return False
        scope=tuple(v for v in scope if v not in set(map(abs,target)))
        rows=[tuple(target)+tuple(-v if i>>j&1 else v for j,v in enumerate(scope)) for i in range(1<<len(scope))]
        if not all(emit(c) for c in rows):return False
        for v in reversed(scope):
            rows=[c[:-1] for c in rows if c[-1]==v]
            if not all(emit(c) for c in rows):return False
        return emit(target)
    if emit([]):return 'UNSAT',proof,stats
    if not plan:return 'UNKNOWN',proof,stats
    topo,roots=plan
    for rep in range(3):
        stats['rounds']+=1;before=len(proof)
        cuts={v:[((v,),2)] for v in roots};signatures={((v,),2):(v,(v,),False) for v in []}
        # identity and constants are registered on actual variables, not imaginary roots.
        signatures={}
        for v in sorted(roots):
            key,inv=normalize((v,),2);signatures[key]=(v,(v,),inv)
        for g in topo:
            if time.perf_counter()-start>MAX_SECONDS:break
            z=g['out']; ins=g['ins'];t=g['table']; pool={}
            for combo in itertools.product(*(cuts[v] for v in ins)):
                c=compose(ins,t,combo)
                if c is not None:pool[c]=None
            # Retain both near and deeper cuts, ranked by support size and IDs.
            ordered=sorted(pool,key=lambda c:(len(c[0]),c[0]))
            if len(ordered)>KEEP:
                ordered=ordered[:KEEP//2]+ordered[-KEEP//2:]
            cuts[z]=[((z,),2)]+ordered
            stats['cuts']+=len(ordered)
            for sc,m in ordered:
                key,inv=normalize(sc,m)
                if not key[0]:
                    stats['matches']+=1
                    if certify([z if inv else -z],sc):stats['constants']+=1
                    else:stats['rejected']+=1
                    continue
                if key in signatures:
                    q,qs,qi=signatures[key]
                    if q==z:continue
                    stats['matches']+=1
                    q=q if inv==qi else -q
                    scope=tuple(sorted(set(sc)|set(qs)))
                    if certify([-z,q],scope) and certify([z,-q],scope):
                        stats['equalities']+=1
                    else:stats['rejected']+=1
                else:signatures[key]=(z,sc,inv)
            key,inv=normalize((z,),2)
            signatures.setdefault(key,(z,(z,),inv))
            if emit([]):return 'UNSAT',proof,stats
        if len(proof)==before:break
    return 'UNKNOWN',proof,stats

if __name__=='__main__':
    out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
    for i,p in enumerate(sorted(Path(sys.argv[1]).rglob('*.cnf'))):
        raw=p.read_bytes();t=time.perf_counter();s,proof,stats=solve(raw)
        (out/f'{i}.drup').write_text(''.join(' '.join(map(str,c))+' 0\n' for c in proof))
        (out/f'{i}.cnf').write_bytes(raw)
        print('ATLAS281',json.dumps(dict(file=str(p),status=s,steps=len(proof),seconds=time.perf_counter()-t,**stats)),flush=True)
