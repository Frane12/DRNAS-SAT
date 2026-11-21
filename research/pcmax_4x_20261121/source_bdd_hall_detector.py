#!/usr/bin/env python3
"""Recover BDD capacity structure from original DIMACS only; no generator metadata."""
import argparse, collections, hashlib, heapq, json, time
from pathlib import Path

def read_cnf(path):
    raw=Path(path).read_bytes()
    nv=nc=None;clauses=[];pending=[]
    for line in raw.decode('ascii').splitlines():
        t=line.split()
        if not t or t[0]=='c':continue
        if t[0]=='p':
            if nv is not None or len(t)!=4 or t[1]!='cnf':raise ValueError('header')
            nv,nc=int(t[2]),int(t[3]);continue
        if nv is None:raise ValueError('missing header')
        for tok in t:
            x=int(tok)
            if abs(x)>nv:raise ValueError('literal out of bounds')
            if x:pending.append(x)
            else:clauses.append(tuple(pending));pending=[]
    if nv is None or pending or len(clauses)!=nc:raise ValueError('clause count')
    return raw,nv,clauses

def topo_selectors(nodes):
    used=set(x for x,_,_ in nodes.values())
    adj={x:set() for x in used};indeg={x:0 for x in used}
    for p,(x,lo,hi) in nodes.items():
        for child in (lo,hi):
            if child in nodes:
                y=nodes[child][0]
                if x==y:raise ValueError('repeated selector')
                if y not in adj[x]:adj[x].add(y);indeg[y]+=1
    todo=[x for x in used if indeg[x]==0];heapq.heapify(todo);order=[]
    while todo:
        x=heapq.heappop(todo);order.append(x)
        for y in adj[x]:
            indeg[y]-=1
            if indeg[y]==0:heapq.heappush(todo,y)
    if len(order)!=len(used):raise ValueError('cycle')
    return order

def capacity(machine,weight):
    order=machine['variable_order'];rank={v:i for i,v in enumerate(order)}
    pref=[0]
    for v in order:pref.append(pref[-1]+weight.get(v,0))
    nodes={p:(x,lo,hi) for p,x,lo,hi in machine['transitions']}
    tr=machine['true_terminal'];fl=machine['false_terminal']
    nr={p:rank[x] for p,(x,_,_) in nodes.items()}
    nr[tr]=nr[fl]=len(order)
    best={tr:0,fl:None}
    for p in sorted(nodes,key=lambda p:nr[p],reverse=True):
        x,lo,hi=nodes[p];i=rank[x];opts=[]
        for child,b in ((lo,0),(hi,weight.get(x,0))):
            if child not in best or nr[child]<=i:raise ValueError('BDD ordering')
            if best[child] is not None:opts.append(best[child]+pref[nr[child]]-pref[i+1]+b)
        best[p]=max(opts) if opts else None
    root=machine['root']
    if root not in best or best[root] is None:raise ValueError('no accepting BDD path')
    return pref[nr[root]]+best[root]

def parse_structure(clauses):
    groups=sorted({tuple(sorted(c)) for c in clauses if len(c)>=2 and all(x>0 for x in c)})
    if not groups:raise ValueError('no positive groups')
    chosen=set()
    for g in groups:
        if chosen.intersection(g):raise ValueError('overlapping ALO groups')
        chosen.update(g)
    posunits={c[0] for c in clauses if len(c)==1 and c[0]>0}
    negunits={-c[0] for c in clauses if len(c)==1 and c[0]<0}
    parents=collections.defaultdict(dict)
    for c in clauses:
        if len(c)!=3:continue
        selects=[x for x in c if abs(x) in chosen]
        states=[x for x in c if abs(x) not in chosen]
        if len(selects)!=1 or len(states)!=2:continue
        s=selects[0]
        neg=[-x for x in states if x<0];pos=[x for x in states if x>0]
        if len(neg)!=1 or len(pos)!=1:continue
        par,child=neg[0],pos[0]
        which='low' if s>0 else 'high'
        val=(abs(s),child)
        if which in parents[par] and parents[par][which]!=val:raise ValueError('conflicting transition')
        parents[par][which]=val
    nodes={}
    for p,d in parents.items():
        if set(d)!={'low','high'} or d['low'][0]!=d['high'][0]:
            raise ValueError('incomplete BDD state')
        nodes[p]=(d['low'][0],d['low'][1],d['high'][1])
    roots=sorted(posunits & set(nodes))
    if not roots:raise ValueError('no BDD root')
    machines=[];allstates=set();allselectors=set()
    for root in roots:
        pending=[root];seen=set();leaves=set()
        while pending:
            p=pending.pop()
            if p in seen:continue
            if p in nodes:
                seen.add(p)
                _,lo,hi=nodes[p]
                pending.extend((lo,hi))
            else:leaves.add(p)
        if len(leaves)!=2 or len(leaves&posunits)!=1 or len(leaves&negunits)!=1:
            raise ValueError('invalid BDD terminals')
        tr=next(iter(leaves&posunits));fl=next(iter(leaves&negunits))
        if allstates.intersection(seen|leaves):raise ValueError('overlapping states')
        allstates.update(seen|leaves)
        subnet={p:nodes[p] for p in seen}
        order=topo_selectors(subnet)
        if allselectors.intersection(order):raise ValueError('selector duplicated between machines')
        allselectors.update(order)
        machines.append({'root':root,'true_terminal':tr,'false_terminal':fl,
            'variable_order':order,
            'transitions':[[p,*subnet[p]] for p in sorted(seen)]})
    if chosen!=allselectors:raise ValueError('selector cover mismatch')
    return groups,machines

def min_cut(groups,machines,weight):
    caps=[capacity(m,weight) for m in machines]
    idx={x:i for i,m in enumerate(machines) for x in m['variable_order']}
    J=len(groups);M=len(machines);src=J+M;snk=src+1;N=snk+1
    edges=[{} for _ in range(N)]
    def edge(a,b,c):
        edges[a][b]=edges[a].get(b,0)+c
        edges[b].setdefault(a,0)
    for j,g in enumerate(groups):
        edge(src,j,1)
        for m in sorted({idx[x] for x in g}):edge(j,J+m,1)
    for m,c in enumerate(caps):edge(J+m,snk,c)
    flow=0
    while True:
        prev={src:None};q=collections.deque([src])
        while q and snk not in prev:
            a=q.popleft()
            for b,c in edges[a].items():
                if c>0 and b not in prev:prev[b]=a;q.append(b)
        if snk not in prev:break
        d=10**10;v=snk
        while v!=src:
            u=prev[v];d=min(d,edges[u][v]);v=u
        v=snk
        while v!=src:
            u=prev[v];edges[u][v]-=d;edges[v][u]+=d;v=u
        flow+=d
    reach={src};q=collections.deque([src])
    while q:
        u=q.popleft()
        for v,c in edges[u].items():
            if c>0 and v not in reach:reach.add(v);q.append(v)
    S=sorted(j for j in range(J) if j in reach)
    Ns=sorted({idx[x] for j in S for x in groups[j]})
    if flow<J and len(S)<=sum(caps[m] for m in Ns):raise ValueError('invalid mincut')
    return flow,caps,S,Ns

def discover(path):
    t=time.perf_counter()
    raw,n,clauses=read_cnf(path)
    groups,machines=parse_structure(clauses)
    weight={x:1 for g in groups for x in g}
    flow,caps,S,Ns=min_cut(groups,machines,weight)
    if flow==len(groups):
        return None,{'status':'UNKNOWN','reason':'no structural contradiction',
            'jobs':len(groups),'machines':len(machines),
            'elapsed_s':time.perf_counter()-t}
    selected_groups=[groups[j] for j in S]
    selected_weights={x:1 for g in selected_groups for x in g}
    for m in machines:m['capacity']=capacity(m,selected_weights)
    required=len(S);capacity_sum=sum(m['capacity'] for m in machines)
    if required<=capacity_sum:raise ValueError('no contradiction')
    cert={'source_sha256':hashlib.sha256(raw).hexdigest(),
        'selected_groups':[list(g) for g in selected_groups],
        'group_weights':[1]*len(selected_groups),
        'machines':machines,'required':required,'capacity_sum':capacity_sum}
    return cert,{'status':'UNSAT_CERTIFICATE_EMITTED_UNCHECKED',
        'jobs':len(groups),'machines':len(machines),
        'total_capacity_all_jobs':sum(caps),'flow':flow,
        'hall_subset_jobs':len(S),'required':required,'capacity':capacity_sum,
        'bdd_nodes':sum(len(m['transitions']) for m in machines),
        'elapsed_s':time.perf_counter()-t}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('cnf');p.add_argument('--cert',type=Path)
    args=p.parse_args()
    cert,result=discover(args.cnf)
    if cert is not None:
        if not args.cert:raise ValueError('certificate path required')
        args.cert.write_text(json.dumps(cert,separators=(',',':'))+'\n')
    print(json.dumps(result,sort_keys=True))
