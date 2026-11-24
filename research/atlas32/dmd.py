"""DMD1: offline diagnosis only. No reference clauses ever enter MRC.
DRAT additions may be RAT (not implied by original formula); only independently
certified local consequences are treated as such. Original MRC limits unchanged.
"""
import sys,time,json,collections,hashlib,subprocess,itertools
from pathlib import Path
import mrc_trace as M
def literal_index(cs):
    ix=collections.defaultdict(list)
    for i,c in enumerate(cs):
        for l in c:ix[l].append(i)
    return ix
def rup(cs,ix,cl,deadline,maxwork=150000):
    # independent unit propagation with negated target; proof of implication, not search.
    a=set();q=collections.deque();work=0
    def push(l):
        if -l in a:return False
        if l not in a:a.add(l);q.append(l)
        return True
    for c in cs:
        if not c:return True,work
        if len(c)==1 and not push(c[0]):return True,work
    for l in cl:
        if not push(-l):return True,work
    while q:
        if work>maxwork or time.monotonic()>deadline:return None,work
        l=q.popleft()
        for i in ix[-l]:
            c=cs[i];work+=1
            if any(x in a for x in c):continue
            left=[x for x in c if -x not in a]
            if not left:return True,work
            if len(left)==1 and not push(left[0]):return True,work
    return False,work
def local(cs,ix,cl,deadline,width=10):
    # Greedy source-clause neighbourhood; exact join on <=10 variables.
    target=set(map(abs,cl));scope=set(target);ids=[];seen=set();mask=None
    if not target or len(target)>width:return None,[],0
    for _ in range(3):
        cand=set(i for v in scope for l in (v,-v) for i in ix[l])-seen
        cand=sorted(cand,key=lambda i:(len(set(map(abs,cs[i]))-scope),-len(set(map(abs,cs[i]))&target),i))
        for i in cand:
            if time.monotonic()>deadline:return None,ids,len(scope)
            s=set(map(abs,cs[i]))
            if len(scope|s)>width or len(ids)>=24:continue
            scope|=s;ids.append(i);seen.add(i)
        if len(ids)>=24:break
    s=tuple(sorted(scope));g=M.extract([cs[i] for i in ids])
    mask=M.full(len(s))
    for a,b in g.items():mask&=M.lift(b,a,s)
    bad=M.extract([cl])
    if not bad:return True,[],len(s)
    a,b=next(iter(bad.items()))
    if mask & (M.full(len(s)) ^ M.lift(b,a,s)):return False,ids,len(s)
    return True,ids,len(s)
def residual_check(state,cl):
    if not state:return 'NO_STATE'
    if set(map(abs,cl))&set(state['eliminated']):return 'ELIMINATED_SCOPE'
    target=set(map(abs,cl))
    # Test entailment by the conjunction of all factors contained in target scope.
    if len(target)>10 or not target:return 'OUTSIDE_LOCAL_BUDGET'
    s=tuple(sorted(target));mask=M.full(len(s));used=0
    for f in state['factors']:
        a=tuple(f['scope'])
        if set(a)<=target:
            mask&=M.lift(int(f['mask'],16),a,s);used+=1
    g=M.extract([cl])
    if not g:return 'TRIVIAL'
    a,b=next(iter(g.items()))
    return 'LOCAL_ENTAILED' if not(mask&(M.full(len(s))^M.lift(b,a,s))) else 'NOT_ENTAILED_BY_CONTAINED_FACTORS'
def sample_proof(path):
    # Deterministic stratified sample of short additions; do not infer all are RUP.
    first=[];last=collections.deque(maxlen=8);hist=collections.Counter();n=0;seen=set()
    with path.open(errors='replace') as f:
        for line in f:
            if n>=200000:break
            if not line.strip() or line[0] in 'cd':continue
            try:a=list(map(int,line.split()))
            except ValueError:continue
            if not a or a[-1]!=0:continue
            n+=1;c=tuple(sorted(set(a[:-1])));hist[len(c)]+=1
            if len(c)<=4 and c and not any(-l in c for l in c):
                if len(first)<8:first.append((n,c))
                last.append((n,c))
    result=[]
    for i,c in first+list(last):
        if c not in seen:result.append((i,c));seen.add(c)
    return result,dict(hist),n
def main(root,out):
    out.mkdir(parents=True,exist_ok=True);rows=[]
    for p in sorted(root.rglob('input.cnf')):
        d=p.parent;rf=d/'rows.json'
        if not rf.exists():continue
        orig=json.loads(rf.read_text());m=next((r for r in orig if r['arm']=='MRC'),None)
        if not m or m['status']!='UNKNOWN':continue
        raw=p.read_bytes();sha=hashlib.sha256(raw).hexdigest()
        assert sha==m['sha']
        n,cs=M.parse(raw);cs=[tuple(sorted(set(c))) for c in cs];ix=literal_index(cs)
        case=m['case'];dest=out/sha[:16];dest.mkdir(exist_ok=True)
        q=subprocess.run([sys.executable,str(Path(__file__).with_name('mrc_trace.py')),str(p),str(dest),'12','25','1'],capture_output=True,text=True,timeout=45)
        (dest/'trace.log').write_text(q.stdout+q.stderr)
        state=json.loads((dest/'residual.json').read_text()) if (dest/'residual.json').exists() else None
        row=dict(case=case,sha=sha,original_reason=m.get('reason'),traced=state is not None,n=n,m=len(cs),references=[])
        if state:
            incidence=collections.defaultdict(set)
            for f in state['factors']:
                for v in f['scope']:incidence[v].update(f['scope'])
            row.update(eliminated=len(state['eliminated']),remaining_factors=len(state['factors']),min_bucket_width=min(map(len,incidence.values()),default=0),max_bucket_width=max(map(len,incidence.values()),default=0))
        for arm in ('kissat','cadical'):
            ref=next((r for r in orig if r['arm']==arm),None)
            if not ref or ref['audit'] not in ('MODEL_VERIFIED','STANDARD_DRAT'):continue
            z=dict(arm=arm,status=ref['status'],audit=ref['audit'])
            if ref['status']=='SAT':
                a=json.loads((d/arm/'model.json').read_text())
                # reference model demonstrates compatibility; not used in MRC or inference.
                z['original_model_valid']=all(any(a.get(str(abs(l)))==int(l>0) for l in c) for c in cs)
                if state:
                    z['residual_model_valid']=all((int(f['mask'],16)>>sum(a[str(v)]<<i for i,v in enumerate(f['scope'])))&1 for f in state['factors'])
            else:
                proof=d/arm/'proof.drup'
                if not proof.exists():continue
                try:
                    check=subprocess.run(['/tmp/drat-check',str(p),str(proof)],capture_output=True,text=True,timeout=45)
                    z['proof_reverified']=check.returncode==0 and 's VERIFIED' in check.stdout
                except subprocess.TimeoutExpired:z['proof_reverified']=False
                if not z['proof_reverified']:row['references'].append(z);continue
                sample,hist,steps=sample_proof(proof);z.update(proof_widths=hist,scanned_additions=steps,samples=[])
                for i,cl in sample:
                    deadline=time.monotonic()+0.4
                    u,work=rup(cs,ix,cl,deadline)
                    loc,ids,w=local(cs,ix,cl,time.monotonic()+0.4)
                    z['samples'].append(dict(step=i,clause=list(cl),original_rup=u,up_work=work,local_exact=loc,source_ids=ids if loc else [],local_width=w,residual=residual_check(state,cl)))
            row['references'].append(z)
        rows.append(row);print('DMD_ROW',json.dumps(row),flush=True);(out/'rows.json').write_text(json.dumps(rows,indent=2))
if __name__=='__main__':main(Path(sys.argv[1]),Path(sys.argv[2]))
