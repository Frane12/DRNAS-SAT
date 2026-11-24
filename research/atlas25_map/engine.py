"""ATLAS25: exact raw CNF scope mapping and bounded Boolean variable elimination.
No filenames, expected status, generator metadata or source netlist used in solve().
Classification is descriptive; proofs depend only on exact clause relations.
"""
import itertools as I, json, math, random, time, hashlib
from collections import defaultdict,Counter
from functools import lru_cache
from pathlib import Path

MAX_LOCAL=8
MAX_JOIN=11
MAX_WORK=4_000_000

def parse(raw):
    n=None; m=None; clauses=[]; pending=[]
    for line in raw.decode().splitlines():
        line=line.strip()
        if not line or line.startswith('c'):continue
        if line.startswith('p'):
            if n is not None:raise ValueError('duplicate header')
            _,typ,n,m=line.split();n,m=int(n),int(m)
            if typ!='cnf':raise ValueError('header')
        else:
            for x in map(int,line.split()):
                if x:pending.append(x)
                else:clauses.append(tuple(pending));pending=[]
    if n is None or pending or len(clauses)!=m or any(abs(x)>n for c in clauses for x in c):raise ValueError('bad DIMACS')
    return n,clauses

def bits(i,k):return tuple((i>>j)&1 for j in range(k))
def index(b):return sum(x<<j for j,x in enumerate(b))
def mask(rows):return sum(1<<r for r in set(rows))
def rowids(m):return [i for i in range(m.bit_length()) if m>>i&1]
def subindex(row,positions):return sum(((row>>p)&1)<<j for j,p in enumerate(positions))

@lru_cache(None)
def templates(k):
    patterns=[]
    def add(label,pred):
        patterns.append((label,[i for i in range(1<<k) if pred(bits(i,k))]))
    if k==2:add('EQUALITY_XOR2',lambda b:b[0]==b[1])
    if k==3:
        add('AND_OR_GATE',lambda b:b[2]==(b[0]&b[1]))
    if k==4:
        add('MUX_GATE',lambda b:b[3]==(b[1] if b[2] else b[0]))
        add('MAJORITY_GATE',lambda b:b[3]==int(sum(b[:3])>=2))
        add('HALF_ADDER',lambda b:b[0]+b[1]==b[2]+2*b[3])
        for q in range(4):add('ARITH2_OFFSET',lambda b,q=q:(b[0]+2*b[1]+q)%4==b[2]+2*b[3])
    if k==5:add('FULL_ADDER',lambda b:sum(b[:3])==b[3]+2*b[4])
    out=defaultdict(set)
    for label,rows in patterns:
        for p in I.permutations(range(k)):
            rr=[sum(((r>>j)&1)<<p[j] for j in range(k)) for r in rows]
            for f in range(1<<k):
                out[mask(r^f for r in rr)].add(label)
    return out

def labels(k,m):
    rows=rowids(m); r=len(rows); out=set(templates(k).get(m,())) if k<=5 else set()
    if r==0:out.add('EMPTY_RELATION')
    if k==1:out.add('UNIT')
    if k>=2 and r==2**k-1:out.add('CLAUSE')
    if k==2 and r==3:out.add('BINARY_EXCLUSION')
    if k>=2 and r==2**(k-1) and len({v.bit_count()%2 for v in rows})==1:out.add('GF2_PARITY')
    if k>=2 and r not in (0,2**k):
        # signed cardinality: exact Hamming layer or threshold in any polarity.
        for f in range(1<<k):
            weights=Counter((v^f).bit_count() for v in rows)
            if any(cnt!=math.comb(k,w) for w,cnt in weights.items()):continue
            ws=sorted(weights)
            if len(ws)==1:out.add('CARDINALITY_EXACT')
            elif ws==list(range(ws[-1]+1)) or ws==list(range(ws[0],k+1)):
                out.add('CARDINALITY_BOUND')
    return sorted(out or {'GENERIC_RELATION'})

def extract(clauses):
    groups=defaultdict(list)
    for i,c in enumerate(clauses):
        if any(-x in c for x in c):continue
        groups[tuple(sorted(set(map(abs,c))))].append((i,c))
    facts=[]; wide=[]
    for scope,cs in sorted(groups.items()):
        if len(scope)>MAX_LOCAL:
            wide.append({'scope':list(scope),'clause_ids':[i for i,c in cs]});continue
        pos={v:j for j,v in enumerate(scope)}
        m=mask(i for i in range(1<<len(scope)) if all(any(((i>>pos[abs(l)])&1)==(l>0) for l in c) for _,c in cs))
        facts.append({'scope':list(scope),'mask':m,'clause_ids':[i for i,c in cs],'labels':labels(len(scope),m)})
    return facts,wide

def mapping(facts,wide):
    counts=Counter(); varlabels=defaultdict(set); edges=Counter()
    for f in facts:
        for label in f['labels']:
            counts[label]+=1
            for v in f['scope']:varlabels[v].add(label)
    for ls in varlabels.values():
        for pair in I.combinations(sorted(ls),2):edges['+'.join(pair)]+=1
    # raw signed pair exclusions: clique pattern, not proof of application meaning
    adj=defaultdict(set)
    for f in facts:
        if 'BINARY_EXCLUSION' not in f['labels']:continue
        a,b=f['scope']; bad=next(i for i in range(4) if not (f['mask']>>i&1))
        x=(a if bad&1 else -a); y=(b if bad&2 else -b)
        adj[x].add(y);adj[y].add(x)
    triangles=sum(1 for a in adj for b in adj[a] if a<b for c in adj[a]&adj[b] if b<c)
    return {'local_categories':dict(counts),'category_overlap_shared_variables':dict(edges),
            'binary_conflict_edges':sum(map(len,adj.values()))//2,
            'binary_conflict_triangles':triangles,'wide_unclassified_groups':len(wide)}

def solve(raw,work_cap=MAX_WORK,join_cap=MAX_JOIN):
    n,cs=parse(raw);fs,wide=extract(cs); mp=mapping(fs,wide)
    trace=[]; active={i:(tuple(f['scope']),f['mask']) for i,f in enumerate(fs)}
    base={'sha256':hashlib.sha256(raw).hexdigest(),'variables':n,'clauses':len(cs),'facts':fs,'wide':wide,'map':mp,'trace':trace}
    def finish(status,**kw):return dict(base,status=status,**kw)
    if any(not m for _,m in active.values()):return finish('UNSAT',empty_id=next(i for i,(_,m) in active.items() if not m),work=0)
    if wide:return finish('UNKNOWN',reason='wide_scope_not_supported',work=0)
    # Eliminate a variable via exact conjunction and existential projection.
    # Bounded induced width; no branching, no conflict learning, no CDCL.
    work=0; next_id=len(fs); history=[]
    while active:
        variables=set(v for sc,m in active.values() for v in sc)
        if not variables:break
        buckets=defaultdict(list)
        for i,(sc,m) in active.items():
            for v in sc:buckets[v].append(i)
        def union(v):return set(x for i in buckets[v] for x in active[i][0])
        v=min(variables,key=lambda v:(len(union(v)),len(buckets[v]),v))
        ids=buckets[v]; scope=tuple(sorted(union(v)))
        if len(scope)>join_cap:return finish('UNKNOWN',reason='induced_width',work=work)
        estimate=(1<<len(scope))*len(ids)
        if work+estimate>work_cap:return finish('UNKNOWN',reason='work_cap',work=work)
        work+=estimate
        constraints=[(tuple(scope.index(x) for x in active[i][0]),active[i][1]) for i in ids]
        valid=[r for r in range(1<<len(scope)) if all((m>>subindex(r,p))&1 for p,m in constraints)]
        reduced=tuple(x for x in scope if x!=v)
        positions=tuple(scope.index(x) for x in reduced)
        newmask=mask(subindex(r,positions) for r in valid)
        event={'var':v,'parents':ids,'scope':list(reduced),'mask':newmask,'id':next_id}
        trace.append(event);history.append((v,scope,valid))
        for i in ids:del active[i]
        active[next_id]=(reduced,newmask)
        if not newmask:return finish('UNSAT',empty_id=next_id,work=work)
        next_id+=1
    assignment={}
    for v,scope,valid in reversed(history):
        r=next(r for r in valid if all(x==v or assignment[x]==((r>>j)&1) for j,x in enumerate(scope)))
        assignment[v]=(r>>scope.index(v))&1
    for v in range(1,n+1):assignment.setdefault(v,0)
    assert all(any(assignment[abs(l)]==int(l>0) for l in c) for c in cs)
    return finish('SAT',model=assignment,work=work)
