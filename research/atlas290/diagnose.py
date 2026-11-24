"""Diagnostic: identical DP pivot ordering with incremental literal index.
No CNF name or status enters the algorithm. No CDCL, no final SAT claim."""
import sys,time,json,heapq,collections,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'atlas285'))
import core as C
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'atlas286'))
import affine as A

def describe(cs):
    ix=C.index(cs);vs=set(map(abs,ix)); rows,rest=A.extract(list(cs))
    widths=collections.Counter(map(len,cs))
    graph={v:set() for v in vs}
    for c in cs:
        sc={abs(l) for l in c}
        if len(sc)<=64:
            for v in sc:graph[v].update(sc-{v})
    seen=set();components=[]
    for v in graph:
        if v in seen:continue
        stack=[v];seen.add(v);n=0
        while stack:
            x=stack.pop();n+=1
            for y in graph[x]-seen:seen.add(y);stack.append(y)
        components.append(n)
    rank,_=A.basis(rows,sorted(vs))
    return dict(variables=len(vs),clauses=len(cs),widths=dict(sorted(widths.items())),xor_rows=len(rows),xor_rank=len(rank),xor_clauses=len(cs)-len(rest),components=sorted(components,reverse=True)[:10],mean_degree=sum(map(len,graph.values()))/max(1,len(vs)),max_degree=max(map(len,graph.values()),default=0),wide_graph_omitted=sum(len(c)>64 for c in cs),min_pairs=min((len(ix[v])*len(ix[-v]) for v in vs),default=0))

def project(raw,incremental,cap=15):
    t=time.monotonic();deadline=t+cap;n,cs=C.E.g.parse(raw)
    active={frozenset(c) for c in cs if not any(-l in c for l in c)}
    known=set(active);proof=[];steps=0;reason='complete'
    ix=C.index(active);heap=[]
    def score(v):return (len(ix[v])*len(ix[-v]),len(ix[v])+len(ix[-v]),v)
    for v in set(map(abs,ix)):heapq.heappush(heap,score(v))
    rebuild_s=0;resolve_s=0
    while active and frozenset() not in active:
        if time.monotonic()>=deadline:reason='time_cap';break
        if len(active)>150000 or len(proof)>300000:reason='diagnostic_memory_cap';break
        z=time.monotonic()
        if incremental:
            while heap:
                item=heapq.heappop(heap);v=item[2]
                if item==score(v) and item[1]>0:break
            else:reason='empty_index';break
        else:
            ix=C.index(active);vs={abs(l) for c in active for l in c}
            v=min(vs,key=score)
        rebuild_s+=time.monotonic()-z
        z=time.monotonic()
        res,why=C.resolve(ix,v,3000,12,deadline)
        resolve_s+=time.monotonic()-z
        if res is None:reason=why;break
        removed=ix[v]|ix[-v]
        for c in sorted(res,key=lambda c:(len(c),sorted(c))):
            if c not in known:proof.append(c);known.add(c)
        if incremental:
            added=res-(active-removed)
            changed=set()
            for c in removed:
                active.remove(c)
                for l in c:ix[l].remove(c);changed.add(abs(l))
            for c in added:
                active.add(c)
                for l in c:ix[l].add(c);changed.add(abs(l))
            for x in changed:heapq.heappush(heap,score(x))
            if len(heap)>max(10000,8*len(ix)):
                heap=[score(x) for x in set(map(abs,ix)) if ix[x] or ix[-x]];heapq.heapify(heap)
        else:active=(active-removed)|res
        steps+=1
    elapsed=time.monotonic()-t
    return active,proof,dict(mode='indexed' if incremental else 'rebuild',projected=steps,reason=reason,projection_s=elapsed,index_s=rebuild_s,resolve_s=resolve_s,proof_steps=len(proof),empty_clause=frozenset() in active)

def main(inputs,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    for p in sorted(Path(inputs).rglob('*.cnf')):
        raw=p.read_bytes();n,cs=C.E.g.parse(raw);d=out/p.stem;d.mkdir(exist_ok=True)
        orig=describe({frozenset(c) for c in cs if not any(-l in c for l in c)})
        print('ATLAS290_ORIG',json.dumps(dict(case=p.stem,sha=hashlib.sha256(raw).hexdigest(),**orig)),flush=True)
        rows=[];cores=[]
        for mode in (False,True):
            core,proof,r=project(raw,mode);cores.append(core)
            r.update(core=describe(core),case=p.stem,original=orig)
            rows.append(r)
            C.write_cnf(d/(r['mode']+'.cnf'),core,n)
            (d/(r['mode']+'.drup')).write_text(''.join(' '.join(map(str,sorted(c)))+' 0\n' for c in proof))
            print('ATLAS290_ROW',json.dumps(r),flush=True)
        if rows[0]['reason']!='time_cap' and rows[1]['reason']!='time_cap':
            assert cores[0]==cores[1], 'different completed core'
        (d/'summary.json').write_text(json.dumps(rows,indent=2))
if __name__=='__main__':main(*sys.argv[1:])
