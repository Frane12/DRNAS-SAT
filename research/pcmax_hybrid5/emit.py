#!/usr/bin/env python3
"""DRNAS MATH-HYBRID5: 9 jobs, 3 machines, global triple compatibility.

Produces a NEW synthetic source CNF with source-backed ordered BDDs;
NOT an original SAT Competition PCMAX CNF. A prefix-pruned RUP trace
is an independently checkable UNSAT proof, not a polynomial bound
for arbitrary X3C or SAT.
"""
import argparse
import hashlib
import json
from pathlib import Path

N=9
M=3
EDGES=[
    (2,5,6),(3,4,8),(1,3,7),(1,5,6),(5,7,8),
    (6,7,8),(0,2,4),(0,3,4),(0,1,2),(0,1,5)
]

def mask(vs):
    return sum(1<<v for v in vs)

def patterns(control=False):
    out={0}|{mask(e) for e in EDGES}
    if control:
        # One 6-job configuration complements edge zero; the third
        # machine may take the empty pattern. This makes a SAT control.
        out.add(((1<<N)-1)^mask(EDGES[0]))
    return sorted(out)

def emit(folder,control=False):
    folder.mkdir(parents=True,exist_ok=True)
    allowed=patterns(control)
    clauses=[]
    def add(*row):
        assert all(type(x)==int and x!=0 for x in row)
        clauses.append(tuple(row))
    groups=[[j*N+i+1 for j in range(M)] for i in range(N)]
    for g in groups:
        add(*g)
        for j in range(M):
            for k in range(j+1,M):
                add(-g[j],-g[k])
    nextvar=M*N+1
    machines=[]
    for j in range(M):
        prefixes=[{a & ((1<<i)-1) for a in allowed}
                  for i in range(N)]
        nodes={}
        for i in range(N):
            for p in sorted(prefixes[i]):
                nodes[(i,p)]=nextvar
                nextvar+=1
        t,f=nextvar,nextvar+1
        nextvar+=2
        root=nodes[(0,0)]
        add(root)
        add(t)
        add(-f)
        transitions=[]
        for (i,p),q in sorted(nodes.items()):
            x=groups[i][j]
            child=[]
            for bit in (0,1):
                y=p | (bit<<i)
                if i==N-1:
                    c=t if y in allowed else f
                else:
                    c=nodes.get((i+1,y),f)
                child.append(c)
            lo,hi=child
            add(-q,x,lo)
            add(-q,-x,hi)
            transitions.append([q,x,lo,hi])
        machines.append({
            'root':root,'true_terminal':t,'false_terminal':f,
            'variable_order':[groups[i][j] for i in range(N)],
            'transitions':transitions,
        })
    source=folder/'source.cnf'
    source.write_text(
        'c MATH-HYBRID5 newly generated synthetic source; NOT original PCMAX benchmark\n'
        +f'p cnf {nextvar-1} {len(clauses)}\n'
        +''.join(' '.join(map(str,c))+' 0\n' for c in clauses))
    # A fractional LP witness uses the first 9 edges, every vertex
    # has incidence 3. Each machine places probability 1/9 on
    # each such edge. Across 3 machines every job has expected count 1.
    signed=[0,0,0,1,1,0,0,1,1,-1]
    disjoint=[]
    for i,a in enumerate(EDGES):
        for j,b in enumerate(EDGES[i+1:],i+1):
            if not (mask(a)&mask(b)):
                missing=((1<<N)-1)^(mask(a)|mask(b))
                disjoint.append([i,j,missing])
    assert len(disjoint)==16
    cert={
        'format':'drnas-hybrid5-global3-v1',
        'kind':'sat_control' if control else 'global3_unsat',
        'source_provenance':'NEW synthetic 9-job, 3-machine BDD CNF',
        'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'groups':groups,'machines':machines,
        'claimed_patterns':allowed,
        'fractional_patterns':[mask(e) for e in EDGES[:9]],
        'fractional_denominator':9,
        'signed_coefficients':signed,
        'pairwise_disjoint_witnesses':disjoint,
        'standard_proof_status':'EXTERNAL_VERIPB_REQUIRED'
    }
    if not control:
        derived=[]
        excluded=[0]*(N+1)
        internal=[0]*(N+1)
        def impossible(prefix):
            known=(1<<len(prefix))-1
            for j in range(M):
                selected=sum(1<<i for i,x in enumerate(prefix) if x==j)
                if not any((a&known)==selected for a in allowed):
                    return True
            return False
        def visit(prefix):
            depth=len(prefix)
            block=tuple(-groups[i][chosen] for i,chosen in enumerate(prefix))
            if impossible(prefix):
                excluded[depth]+=1
                derived.append(block)
                return
            assert depth < N, 'globally satisfying assignment found'
            for j in range(M):
                visit(prefix+(j,))
            internal[depth]+=1
            derived.append(block)
        visit(())
        assert derived and derived[-1]==()
        (folder/'proof.drup').write_text(
            ''.join(' '.join(map(str,c))+' 0\n' for c in derived))
        with (folder/'proof.pbp').open('w') as out:
            out.write('pseudo-Boolean proof version 3.0\n')
            out.write(f'f {len(clauses)} ;\n')
            for c in derived:
                terms=' '.join('1 ~x'+str(-x) for x in c)
                out.write('rup '+(terms+' ' if terms else '')+'>= 1 ;\n')
            out.write('output NONE ;\n')
            out.write('conclusion UNSAT ;\n')
            out.write('end pseudo-Boolean proof ;\n')
        cert['rup_steps']=len(derived)
        cert['pruned_prefix_leaves']=excluded
        cert['internal_nodes']=internal
        cert['proof_sha256']=hashlib.sha256(
            (folder/'proof.pbp').read_bytes()).hexdigest()
        assert len(derived)==301,(len(derived),excluded,internal)
    (folder/'certificate.json').write_text(json.dumps(cert,indent=2)+'\n')
    result={'control':control,'jobs':N,'machines':M,
            'nonempty_patterns':len(EDGES),
            'vars':nextvar-1,'clauses':len(clauses),
            'disjoint_pairs':len(disjoint),
            'rup_steps':cert.get('rup_steps'),
            'source_sha256':cert['source_sha256']}
    print(json.dumps(result,sort_keys=True))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--control',action='store_true')
    a=p.parse_args()
    emit(a.out,a.control)
