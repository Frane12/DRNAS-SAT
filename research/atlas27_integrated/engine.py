"""ATLAS27 shared raw CNF gate/relational discovery. No case labels in solver."""
import importlib.util,sys,itertools,hashlib,collections,json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def load(name,p):
    spec=importlib.util.spec_from_file_location(name,R/p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
g=load('gate26','atlas26_raw/engine.py'); gv=load('verify26','atlas26_raw/verify.py')
r=load('rel25','atlas25_map/engine.py'); rv=load('verify25','atlas25_map/verify.py')
original_discover=g.discover
original_extract=r.extract
def compact(cs):
    cand,res=original_discover(cs)
    fixed={next(iter(opts)) for _,_,opts in cand if len(opts)==1}
    idx=collections.defaultdict(list)
    for i in res:
        if len(set(cs[i]))==2 and len({abs(x) for x in cs[i]})==2:
            idx[frozenset(cs[i])].append(i)
    used=set()
    added=0
    for i in res:
        c=cs[i]
        if i in used or len(c)!=3 or len(set(map(abs,c)))!=3:continue
        for z in c:
            if abs(z) in fixed:continue
            a,b=[x for x in c if x!=z]
            j=next((k for k in idx[frozenset((-a,-z))] if k not in used),None)
            k=next((k for k in idx[frozenset((-b,-z))] if k not in used),None)
            if j is None or k is None or j==k:continue
            ins=tuple(sorted([abs(a),abs(b)])); table=0
            ids=[i,j,k]
            for x,y in itertools.product((0,1),repeat=2):
                v=dict(zip(ins,(x,y)));out=[]
                for q in (0,1):
                    v[abs(z)]=q
                    if all(any(v[abs(l)]==(l>0) for l in cs[h]) for h in ids):out.append(q)
                if len(out)!=1:break
                table|=out[0]<<(x+2*y)
            else:
                cand.append((tuple(sorted(map(abs,c))),ids,{abs(z):(ins,table)}))
                fixed.add(abs(z));used.update(ids);added+=1;break
    return cand,[i for i in res if i not in used],added
def extract_shared(cs):
    cand,res,added=compact(cs)
    facts=[];wide=[]
    def fact(sc,ids):
        sc=tuple(sorted(sc));pos={v:j for j,v in enumerate(sc)}
        m=r.mask(i for i in range(1<<len(sc)) if all(any(((i>>pos[abs(l)])&1)==(l>0) for l in cs[h]) for h in ids))
        facts.append({'scope':list(sc),'mask':m,'clause_ids':ids,'labels':r.labels(len(sc),m)})
    for sc,ids,opts in cand:fact(sc,ids)
    groups=collections.defaultdict(list)
    for i in res:groups[tuple(sorted(set(map(abs,cs[i]))))].append(i)
    for sc,ids in groups.items():
        if len(sc)>r.MAX_LOCAL:wide.append({'scope':list(sc),'clause_ids':ids})
        else:fact(sc,ids)
    return facts,wide
def solve(raw):
    n,cs=g.parse(raw)
    base={'sha256':hashlib.sha256(raw).hexdigest(),'variables':n,'clauses':len(cs)}
    if n>3000 or len(cs)>20000:return dict(base,status='UNKNOWN',reason='pilot_input_cap',attempts=[])
    cand,res,added=compact(cs);facts,wide=extract_shared(cs)
    mp=r.mapping(facts,wide);base.update(map=mp,compact_gates=added,reconstructed_gate_relations=len(cand))
    attempts=[]
    # Shared compact relations are transferred to the bounded elimination module.
    r.extract=lambda _: (facts,wide)
    try:
        a=r.solve(raw,work_cap=1000000)
    finally:r.extract=original_extract
    attempts.append(['SHARED_RELATIONAL',a['status']])
    if a['status']!='UNKNOWN':
        audit=rv.verify(raw,a)
        return dict(base,status=a['status'],route='SHARED_RELATIONAL',audit=audit,proof=a,attempts=attempts)
    # Same recovered gate facts are reused by the functional symbolic module.
    g.discover=lambda _: (cand,res)
    try:
        a=g.solve(raw)
    finally:g.discover=original_discover
    attempts.append(['SHARED_GATE_BDD',a['status']])
    if a['status']!='UNKNOWN':
        audit=gv.verify(raw,a)
        return dict(base,status=a['status'],route='SHARED_GATE_BDD',audit=audit,proof=a,attempts=attempts)
    return dict(base,status='UNKNOWN',route=None,attempts=attempts,reason=a.get('attempts'))
