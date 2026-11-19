#!/usr/bin/env python3
"""MATH-PARITY3 candidate: regenerate a SAT-equivalent exact-fill CNF
and source-level RUP/VeriPB proof for an isolated 15-job example.
DO NOT confuse this CNF with the archived PCMAX SAT competition inputs.
"""
from pathlib import Path
from collections import deque
import hashlib, json

D = (7,8,8,9,10,10,11,11,11,13,13,17,22,23,25)
M=6
U=33
N=len(D)
PARITY=(1,2,14)
DEST=Path(__file__).resolve().parent
clauses=[]
def add_source(vs):
    assert all(x != 0 for x in vs)
    clauses.append(tuple(vs))

def var(j,i): return j*N+i+1
for i in range(N):
    add_source(tuple(var(j,i) for j in range(M)))
    for j in range(M):
        for k in range(j+1,M): add_source((-var(j,i),-var(k,i)))

nextvar=M*N+1
machines=[]
for j in range(M):
    reach={(0,U)}
    frontier=[(0,U)]
    for i in range(N):
        for _,rem in [pair for pair in frontier if pair[0]==i]:
            if i+1<N:
                reach.add((i+1,rem))
                if rem >= D[i]: reach.add((i+1,rem-D[i]))
        frontier=sorted(reach)
    states={v:nextvar+k for k,v in enumerate(sorted(reach))}
    nextvar+=len(states)
    t=nextvar
    f=nextvar+1
    nextvar+=2
    root=states[(0,U)]
    add_source((root,));add_source((t,));add_source((-f,))
    trans={}
    for (i,rem),q in sorted(states.items(),reverse=True):
        if i==N-1:
            low=t if rem==0 else f
            high=t if rem==D[i] else f
        else:
            low=states[(i+1,rem)]
            high=states[(i+1,rem-D[i])] if rem >= D[i] else f
        x=var(j,i)
        add_source((-q,x,low))
        add_source((-q,-x,high))
        trans[(i,rem)]=(q,low,high)
    machines.append({'j':j,'root':root,'true':t,'false':f,'trans':trans,'states':states})

num_source=len(clauses)
numvar=nextvar-1
cnf=DEST/'source_exactfill.cnf'
cnf.write_text('c DRNAS MATH-PARITY3 generated exact-fill CNF, NOT archived original\n'+
               'c 15 jobs 6 machines 33 capacity; selectors first 90 variables\n'+
               f'p cnf {numvar} {num_source}\n'+
               ''.join(' '.join(map(str,c))+' 0\n' for c in clauses))

proof=[]
seen=set(clauses)
counts={'bdd_state_lemmas':0,'parity_forbiddens':0,'pair_lemmas':0,'single_lemmas':0,'empty':0}
def learn(c, tag):
    c=tuple(c)
    assert not any(-x in c for x in c), 'no tautologies'
    if c in seen: return
    seen.add(c)
    proof.append(c)
    counts[tag]+=1

for ma in machines:
    j=ma['j']; qmap=ma['states']; f=ma['false']; t=ma['true']
    for vals in [(a,b,c) for a in (0,1) for b in (0,1) for c in (0,1) if (a+b+c)%2==1]:
        fixed=dict(zip(PARITY,vals))
        live={t:True,f:False}
        for i,rem in sorted(qmap,reverse=True):
            q,lo,hi=ma['trans'][(i,rem)]
            if i in fixed:
                viable=live[hi if fixed[i] else lo]
            else:
                viable=live[lo] or live[hi]
            live[q]=viable
            if not viable:
                clause=[-q]+[(-var(j,k) if fixed[k] else var(j,k)) for k in PARITY if k >= i]
                learn(clause,'bdd_state_lemmas')
        assert not live[ma['root']], (j,vals)
        learn([(-var(j,k) if fixed[k] else var(j,k)) for k in PARITY],'parity_forbiddens')

a,b,c=PARITY
for j in range(M):
    for k in range(M):
        learn((-var(j,a),-var(k,b)),'pair_lemmas')
for j in range(M):
    learn((-var(j,a),),'single_lemmas')
learn((), 'empty')
drup=DEST/'proof.drup'
drup.write_text(''.join(' '.join(map(str,c))+' 0\n' for c in proof))
pbp=DEST/'proof.pbp'
with pbp.open('w') as fd:
    fd.write('pseudo-Boolean proof version 3.0\n')
    fd.write(f'f {num_source} ;\n')
    for c in proof:
        terms=' '.join(f'1 {"~" if lit<0 else ""}x{abs(lit)}' for lit in c)
        fd.write(f'rup {terms+" " if terms else ""}>= 1 ;\n')
    fd.write('output NONE ;\nconclusion UNSAT ;\nend pseudo-Boolean proof ;\n')
manifest={'jobs':list(D),'machines':M,'capacity':U,'total':sum(D),
          'parity_support_zero_based':list(PARITY),'source_cnf_sha256':hashlib.sha256(cnf.read_bytes()).hexdigest(),
          'source_vars':numvar,'source_clauses':num_source,'proof_lines':len(proof),
          'counts':counts,'cnf_type':'generated exact-fill source BDD, not original PCMAX benchmark',
          'proof_type':'RUP-only, DRUP and VeriPB v3.0; independent external verification required'}
(DEST/'manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest,indent=2))
