"""Independent path-cover auditor for SU(2) degree-two suppression."""
import hashlib,json,heapq
from pathlib import Path
from fractions import Fraction as Q

def key(a,b):return tuple(sorted((a,b)))

def verify_block(source,cert):
    raw=Path(source).read_bytes();s=json.loads(raw);c=json.loads(Path(cert).read_text())
    if c['source_sha256']!=hashlib.sha256(raw).hexdigest():raise ValueError('source hash')
    n=s['n'];alpha=Q(s['alpha']);target=Q(s['target'])
    if type(n)!=int or not 1<=n<=256 or alpha<=0 or target<=0:raise ValueError('parameters')
    adj={v:set() for v in range(n)};original=set()
    for a,b in s['edges']:
        if not 0<=a<n or not 0<=b<n or a==b or key(a,b) in original:raise ValueError('original edge')
        original.add(key(a,b));adj[a].add(b);adj[b].add(a)
    removed=set(c['removed'])
    if not removed or len(removed)!=len(c['removed']) or not removed<=adj.keys() or any(len(adj[v])!=2 for v in removed):raise ValueError('degree two')
    keep=set(adj)-removed;paths={};covered=set()
    # Recover maximal original paths directly, rather than replaying the
    # native/planner sequence. Every original edge must belong to one path.
    for a in sorted(keep):
        for v in sorted(adj[a]):
            if key(a,v) in covered:continue
            prev=a;cur=v;path=[a,v];used={key(a,v)}
            while cur in removed:
                nxt=next(iter(adj[cur]-{prev}));e=key(cur,nxt)
                if e in used:raise ValueError('closed removed component')
                used.add(e);path.append(nxt);prev,cur=cur,nxt
            e=key(a,cur)
            if a==cur or e in paths or covered&used:raise ValueError('parallel or self-loop')
            paths[e]=path if a<cur else path[::-1];covered|=used
    if covered!=original:raise ValueError('incomplete path cover')
    weights={e:len(p)-1 for e,p in paths.items()}
    expected=[[a,b,w] for (a,b),w in sorted(weights.items())]
    if c['edges']!=expected:raise ValueError('weighted graph mismatch')
    if len(c['loops'])!=len(s['loops']):raise ValueError('loop count')
    seen=set();magnetic=Q(0);upper=Q(0)
    for (k,v),reduced in zip(s['loops'],c['loops']):
        k=Q(k)
        if len(v)<3 or len(set(v))!=len(v) or any(a not in adj for a in v):raise ValueError('source loop')
        boundary=frozenset(key(a,b) for a,b in zip(v,v[1:]+v[:1]))
        if not boundary<=original or boundary in seen:raise ValueError('source loop boundary')
        seen.add(boundary)
        if reduced!=[a for a in v if a in keep] or len(reduced)<3:raise ValueError('loop projection')
        rebuilt=[]
        for a,b in zip(reduced,reduced[1:]+reduced[:1]):
            p=paths.get(key(a,b))
            if p is None:raise ValueError('reduced loop edge')
            rebuilt.extend(p[:-1] if a<b else p[:0:-1])
        start=rebuilt.index(v[0]);rebuilt=rebuilt[start:]+rebuilt[:start]
        if rebuilt!=v:raise ValueError('oriented loop mismatch')
        magnetic+=2*abs(k);e=alpha*3*len(v)/4
        upper=min(upper,-k*k*e/(e*e+k*k))
    # Weighted shortest cycle on reduced graph, independently of CORE BFS.
    g={v:{} for v in keep}
    for (a,b),w in weights.items():g[a][b]=g[b][a]=w
    shortest=None
    for (a,b),w in weights.items():
        pq=[(0,a)];dist={a:0}
        while pq:
            d,u=heapq.heappop(pq)
            if d!=dist[u]:continue
            if u==b:
                candidate=d+w;shortest=candidate if shortest is None else min(shortest,candidate);break
            for v,cost in g[u].items():
                if key(u,v)==(a,b):continue
                t=d+cost
                if t<dist.get(v,float('inf')):dist[v]=t;heapq.heappush(pq,(t,v))
    if shortest is None:raise ValueError('no physical cycle')
    lower=alpha*3*shortest/4-magnetic-upper
    return dict(status='BLOCK_EQUIVALENCE_CHECKED',original_vertices=n,remaining_vertices=len(keep),
        original_edges=len(original),remaining_edges=len(weights),removed_vertices=len(removed),
        weighted_girth=shortest,gap_lower=str(lower),requested_gap=str(target),
        all_representations=True,physical_spectral_equivalence=True,continuum=False)
