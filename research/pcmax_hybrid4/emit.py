#!/usr/bin/env python3
"""DRNAS MATH-HYBRID4: 6-job exact-cover incompatibility source CNF and RUP.

This emits a new, explicitly synthetic benchmark (NOT original PCMAX SAT2024).
The RUP generator is based on source-checked BDD prefix exclusions.
"""
import argparse, hashlib, json
from pathlib import Path

EDGES=[(0,1,5),(0,2,3),(0,2,4),(1,3,4),(1,2,5),(0,3,5),(1,2,3)]
N=6
M=2

def mask(xs):return sum(1<<x for x in xs)

def allowed(control):
    out={0}|{mask(e) for e in EDGES}
    if control:
        out.add(((1<<N)-1)^mask(EDGES[0]))
    return sorted(out)

def emit(dest,control=False):
    dest.mkdir(parents=True,exist_ok=True)
    patterns=allowed(control)
    cl=[]
    def add(*xs):
        assert all(type(x)==int and x for x in xs)
        cl.append(tuple(xs))
    groups=[[j*N+i+1 for j in range(M)] for i in range(N)]
    for group in groups:
        add(*group)
        add(-group[0],-group[1])
    nxt=M*N+1
    machines=[]
    for j in range(M):
        pref=[{p&((1<<i)-1) for p in patterns} for i in range(N)]
        nodes={}
        for i in range(N):
            for p in sorted(pref[i]):
                nodes[(i,p)]=nxt;nxt+=1
        t=nxt;f=nxt+1;nxt+=2
        root=nodes[(0,0)]
        add(root);add(t);add(-f)
        transitions=[]
        for (i,p),q in sorted(nodes.items()):
            x=groups[i][j]
            children=[]
            for bit in (0,1):
                newp=p|(bit<<i)
                child=(t if newp in patterns else f) if i==N-1 else nodes.get((i+1,newp),f)
                children.append(child)
            low,high=children
            add(-q,x,low);add(-q,-x,high)
            transitions.append([q,x,low,high])
        machines.append({'root':root,'true_terminal':t,'false_terminal':f,
                         'variable_order':[groups[i][j] for i in range(N)],
                         'transitions':transitions})
    source=dest/'source.cnf'
    source.write_text('c synthetic DRNAS HYBRID4 exact-cover: NOT unchanged SAT Competition PCMAX\n'
                      +f'p cnf {nxt-1} {len(cl)}\n'
                      +''.join(' '.join(map(str,c))+' 0\n' for c in cl))
    cert={'format':'drnas-hybrid4-v1','kind':'sat_control' if control else 'unsat_hole',
          'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
          'source_provenance':'new synthetic 6-job two-machine BDD CNF',
          'groups':groups,'machines':machines,'claimed_patterns':patterns,
          'fractional_patterns':[mask(EDGES[i]) for i in (2,3,4,5)],
          'signed_pattern_indices':[1,2,3,4,5,6],
          'signed_coefficients':[0,-1,1,0,0,1,1],
          'standard_proof_status':'NOT_CHECKED_WITH_VERIPB'}
    if not control:
        clauses=[];rejected_count=[0]*(N+1)
        def rejected(prefix):
            depth=len(prefix);known=(1<<depth)-1
            for machine in range(M):
                bits=sum(1<<i for i,j in enumerate(prefix) if j==machine)
                if not any((p&known)==bits for p in patterns):return True
            return False
        def walk(prefix):
            block=tuple(-groups[i][machine] for i,machine in enumerate(prefix))
            if rejected(prefix):
                rejected_count[len(prefix)]+=1
                clauses.append(block)
                return
            assert len(prefix)<N,'full exact cover should be impossible'
            for machine in range(M):walk(prefix+(machine,))
            clauses.append(block)
        walk(())
        assert clauses[-1]==()
        (dest/'proof.drup').write_text(''.join(' '.join(map(str,c))+' 0\n' for c in clauses))
        with (dest/'proof.pbp').open('w') as fd:
            fd.write('pseudo-Boolean proof version 3.0\n')
            fd.write(f'f {len(cl)} ;\n')
            for c in clauses:
                terms=' '.join('1 ~x'+str(-v) for v in c)
                fd.write('rup '+(terms+' ' if terms else '')+'>= 1 ;\n')
            fd.write('output NONE ;\nconclusion UNSAT ;\nend pseudo-Boolean proof ;\n')
        cert['rup_steps']=len(clauses)
        cert['rup_leaf_counts']=rejected_count
        cert['proof_sha256']=hashlib.sha256((dest/'proof.pbp').read_bytes()).hexdigest()
    (dest/'certificate.json').write_text(json.dumps(cert,indent=2)+'\n')
    out={'control':control,'jobs':N,'machines':M,'patterns':len(patterns),
         'source_vars':nxt-1,'source_clauses':len(cl),'rup_steps':cert.get('rup_steps'),
         'source_sha256':cert['source_sha256']}
    print(json.dumps(out,sort_keys=True))
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--control',action='store_true')
    args=p.parse_args();emit(args.out,args.control)
