"""ATLAS31 MRC: finite Boolean relations, exact joins and existential projection.
Input is exclusively DIMACS. No CDCL, branching search or external solver in core.
Truth tables use assignment index sum(x_i*2**i); 1 denotes permitted tuple.
"""
import sys,time,json,heapq,collections,itertools,functools,hashlib
from pathlib import Path
MAXW=14
def parse(raw):
    n=m=None;cs=[];p=[]
    for line in raw.decode().splitlines():
        line=line.strip()
        if not line or line.startswith('c'):continue
        if line.startswith('p'):
            a,b,n,m=line.split();n=int(n);m=int(m)
            if a!='p' or b!='cnf':raise ValueError('header')
            continue
        for x in map(int,line.split()):
            if x:p.append(x)
            else:cs.append(tuple(p));p=[]
    if n is None or p or len(cs)!=m or any(abs(x)>n for c in cs for x in c):raise ValueError('bad DIMACS')
    return n,cs
def full(k):return (1<<(1<<k))-1
def lift(mask,scope,target):
    # Insert one free coordinate at a time, duplicating blocks.
    scope=set(scope);k=len(scope)
    for pos,v in enumerate(target):
        if v in scope:continue
        b=1<<pos;unit=(1<<b)-1;out=0
        for start in range(0,1<<k,b):
            chunk=(mask>>start)&unit
            out|=(chunk|(chunk<<b))<<(2*start)
        mask=out;k+=1
    return mask
def project(mask,k,pos):
    b=1<<pos;unit=(1<<b)-1;out=0
    for start in range(0,1<<k,2*b):
        out|=(((mask>>start)|(mask>>(start+b)))&unit)<<(start//2)
    return out
@functools.lru_cache(maxsize=4096)
def signature(k,mask):
    # Exact NPN equivalence for small symmetric relations: signed input permutations.
    if k>4:return None
    best=mask
    for p in itertools.permutations(range(k)):
        perm=[sum(((a>>i)&1)<<p[i] for i in range(k)) for a in range(1<<k)]
        for flip in range(1<<k):
            q=sum(((mask>>(b^flip))&1)<<a for a,b in enumerate(perm))
            best=min(best,q)
    return f'{k}:{best:x}'
def extract(cs):
    groups={}
    for raw in cs:
        c=set(raw)
        if any(-x in c for x in c):continue
        s=tuple(sorted(map(abs,c)))
        if len(s)>MAXW:raise ValueError('wide_input')
        bad=sum(1<<i for i,v in enumerate(s) if -v in c)
        groups[s]=groups.get(s,full(len(s)))&~(1<<bad)
    return groups
def histogram(groups):
    h=collections.Counter()
    for s,m in groups.items():
        sig=signature(len(s),m)
        if sig is not None:h[sig]+=1
    return dict(h)
def write_proof(out,history,cap,deadline,initial_false=False):
    count=0
    with (out/'proof.drup').open('w') as f:
        if initial_false:f.write('0\n');return 1
        for s,m in history:
            bad=full(len(s))^m
            if count+bad.bit_count()>cap:raise OverflowError('proof_cap')
            while bad:
                if count%1024==0 and time.monotonic()>deadline:raise TimeoutError('proof_time')
                bit=bad&-bad;a=bit.bit_length()-1;bad^=bit
                f.write(' '.join(str(-v if a>>i&1 else v) for i,v in enumerate(s))+' 0\n')
                count+=1
    return count
def solve(raw,out,width=12,cap=20,adaptive=True):
    t=time.monotonic();deadline=t+cap;out.mkdir(parents=True,exist_ok=True)
    n,cs=parse(raw);features=dict(n=n,m=len(cs),density=len(cs)/max(n,1),widths=dict(collections.Counter(map(len,cs))))
    base=dict(features=features,sha=hashlib.sha256(raw).hexdigest(),status='UNKNOWN',audit='NONE')
    try:g=extract(cs)
    except ValueError as e:return dict(base,reason=str(e),decision_s=time.monotonic()-t)
    initial=histogram(g);created=collections.Counter();h=[];trace=[];peak=0;steps=0
    F={};inc=collections.defaultdict(set);uid=0
    def add(s,m):
        nonlocal uid
        if m==full(len(s)):return
        F[uid]=(s,m)
        for v in s:inc[v].add(uid)
        uid+=1
    def drop(i):
        s,m=F.pop(i)
        for v in s:inc[v].remove(i)
    def finish(status,reason):
        if status=='UNKNOWN':
            state=dict(eliminated=[v for v,_,_ in h],factors=[dict(scope=list(s),mask=hex(m)) for s,m in F.values()],reason=reason)
            (out/'residual.json').write_text(json.dumps(state))
        return dict(base,status=status,reason=reason,decision_s=time.monotonic()-t,steps=steps,peak_width=peak,initial_motifs=initial,derived_motifs=dict(created),novel_motifs=sorted(set(created)-set(initial)),remaining_factors=len(F),remaining_variables=sum(bool(x) for x in inc.values()))
    if g.get(())==0:
        r=finish('UNSAT','original_empty')
        r['proof_steps']=write_proof(out,[],1000000,deadline,True);return r
    for s,m in g.items():add(s,m)
    while F:
        if time.monotonic()>deadline:return finish('UNKNOWN','time_cap')
        if steps>=20000:return finish('UNKNOWN','step_cap')
        # choose bounded bucket with smallest separator, then a sparse-product tie break.
        if adaptive:
            def rank(v):
                ids=inc[v];u=set()
                for i in ids:u.update(F[i][0])
                return (len(u),len(ids),v)
            v=min((v for v in inc if inc[v]),key=rank)
        else:v=min(v for v in inc if inc[v])
        ids=sorted(inc[v]);s=tuple(sorted(set().union(*(F[i][0] for i in ids))))
        if len(s)>width:return finish('UNKNOWN','width_cap')
        peak=max(peak,len(s));m=full(len(s))
        for i in ids:
            a,b=F[i];m&=lift(b,a,s)
            if not m:break
        pos=s.index(v);q=tuple(x for x in s if x!=v);p=project(m,len(s),pos)
        h.append((v,s,m));trace.append((q,p))
        for i in ids:drop(i)
        steps+=1
        if len(q)<=4:
            sig=signature(len(q),p)
            created[sig]+=1
        if not q and not p:
            r=finish('UNSAT','relation_contradiction')
            try:r['proof_steps']=write_proof(out,trace,1000000,time.monotonic()+20)
            except (OverflowError,TimeoutError) as e:r['audit']='PROOF_INCOMPLETE';r['proof_error']=str(e)
            r['proof_s']=max(0,time.monotonic()-t-r['decision_s']);return r
        add(q,p)
    a={}
    for v,s,m in reversed(h):
        j=sum(a.get(x,0)<<i for i,x in enumerate(s) if x!=v)
        if (m>>j)&1:a[v]=0
        elif (m>>(j|(1<<s.index(v))))&1:a[v]=1
        else:raise AssertionError('invalid reverse lift')
    for v in range(1,n+1):a.setdefault(v,0)
    if not all(any(a[abs(l)]==int(l>0) for l in c) for c in cs):raise AssertionError('invalid model')
    (out/'model.json').write_text(json.dumps(a))
    return finish('SAT','model_lifted')
if __name__=='__main__':
    p=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
    r=solve(p.read_bytes(),out,int(sys.argv[3]),float(sys.argv[4]),bool(int(sys.argv[5])))
    (out/'result.json').write_text(json.dumps(r));print('MRC_RESULT',json.dumps(r),flush=True)
