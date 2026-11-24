"""Separate exact proof replay, no import from engine."""
import hashlib,itertools,json
def verify(raw,r):
    assert hashlib.sha256(raw).hexdigest()==r['sha256']
    tokens=[]
    for line in raw.decode().splitlines():
        if line.strip() and line.strip()[0] not in 'cp':tokens.extend(map(int,line.split()))
    cs=[]; c=[]
    for x in tokens:
        if x:c.append(x)
        else:cs.append(c);c=[]
    assert not c and len(cs)==r['clauses']
    if r['status']=='SAT':
        a={int(k):v for k,v in r['model'].items()}
        assert set(a)==set(range(1,r['variables']+1)) and all(v in (0,1) for v in a.values())
        assert all(any(a[abs(l)]==(l>0) for l in c) for c in cs)
        return 'SAT_MODEL_VERIFIED'
    if r['status']=='UNKNOWN':return 'UNKNOWN'
    assert r['status']=='UNSAT'
    def assignments(sc):
        for b in itertools.product((0,1),repeat=len(sc)):yield dict(zip(sc,b))
    def get(m,sc,a):
        return (m>>sum(a[v]*(2**j) for j,v in enumerate(sc)))&1
    active={}
    for i,f in enumerate(r['facts']):
        sc=f['scope'];ids=f['clause_ids']
        assert len(sc)<=8 and sc==sorted(set(sc))
        assert all(0<=j<len(cs) and set(map(abs,cs[j]))<=set(sc) for j in ids)
        expected=sum(2**sum(a[v]*2**j for j,v in enumerate(sc)) for a in assignments(sc)
                     if all(any(a[abs(l)]==(l>0) for l in cs[k]) for k in ids))
        assert f['mask']==expected
        active[i]=(sc,expected)
    for e in r['trace']:
        ids=e['parents']; v=e['var']
        assert len(ids)==len(set(ids)) and ids and e['id'] not in active
        assert all(v in active[i][0] for i in ids)
        allvars=sorted(set(x for i in ids for x in active[i][0]))
        assert len(allvars)<=11 and e['scope']==[x for x in allvars if x!=v]
        # Entailment of each projected tuple independently, not detector join code.
        sc=e['scope']; valid=0
        for a in assignments(sc):
            if any(all(get(active[i][1],active[i][0],dict(a,**{})|{v:b}) for i in ids) for b in (0,1)):
                valid |= 1<<sum(a[x]*2**j for j,x in enumerate(sc))
        assert valid==e['mask']
        for i in ids:del active[i]
        active[e['id']]=(sc,valid)
    assert active[r['empty_id']][1]==0
    return 'UNSAT_RELATION_TRACE_VERIFIED'
