#!/usr/bin/env python3
"""Independent DRNAS HYBRID4 verifier: source CNF, local BDDs, lattice,
LP witness, modular small-k controls, SAT model, and each RUP proof step.
Nothing from the emitter is imported.
"""
import argparse, hashlib, itertools, json
from pathlib import Path

N=6; M=2
# Source-experiment specification, not taken from the certificate.
EDGES=((0,1,5),(0,2,3),(0,2,4),(1,3,4),(1,2,5),(0,3,5),(1,2,3))

def mask(xs):return sum(1<<x for x in xs)
def expect(c,msg):
    if not c:raise ValueError(msg)

def read_cnf(data):
    nv=nc=None;cl=[];cur=[]
    for row in data.decode('ascii').splitlines():
        tok=row.split()
        if not tok or tok[0]=='c':continue
        if tok[0]=='p':
            expect(nv is None and len(tok)==4 and tok[1]=='cnf','bad header')
            nv,nc=map(int,tok[2:]);continue
        expect(nv is not None,'clause before DIMACS header')
        for t in tok:
            v=int(t)
            if v:
                expect(1<=abs(v)<=nv,'literal exceeds DIMACS header')
                cur.append(v)
            else:
                cl.append(tuple(cur));cur=[]
    expect(nv is not None and len(cl)==nc and not cur,'bad clause count')
    return nv,cl

def source_bdd(machine,groups,clause_set,nv):
    order=machine['variable_order']
    expect(len(order)==N and len(set(order))==N,'bad machine order')
    gmap={v:i for i,g in enumerate(groups) for v in g}
    expect(set(gmap[i] for i in order)==set(range(N)),'missing group in BDD')
    rank={v:i for i,v in enumerate(order)}
    root,t,f=(machine[k] for k in ('root','true_terminal','false_terminal'))
    expect(len({root,t,f})==3,'terminal alias')
    expect(all(frozenset((x,)) in clause_set for x in (root,t))
           and frozenset((-f,)) in clause_set,'root/terminal unit missing')
    nodes={}
    for row in machine['transitions']:
        expect(len(row)==4,'bad BDD row')
        q,x,lo,hi=row
        expect(all(type(v)==int and 1<=v<=nv for v in row),'BDD var out of bounds')
        expect(q not in nodes and x in rank and len({q,x,lo})==3
               and len({q,x,hi})==3,'bad BDD transition')
        expect(frozenset((-q,x,lo)) in clause_set
               and frozenset((-q,-x,hi)) in clause_set,'source BDD edge missing')
        nodes[q]=(x,lo,hi)
    expect(root in nodes and t not in nodes and f not in nodes,'bad BDD root')
    states=set(nodes)|{t,f}
    expect(not(states & set(order)),'state selector alias')
    nr={q:rank[x] for q,(x,_,_) in nodes.items()};nr[t]=nr[f]=N
    for q,(x,lo,hi) in nodes.items():
        expect(lo in states and hi in states and nr[lo]>rank[x]
               and nr[hi]>rank[x],'BDD rank/child violation')
    def accepts(bits):
        q=root
        for _ in range(len(nodes)+1):
            if q not in nodes:return q==t
            x,lo,hi=nodes[q]
            q=hi if (bits>>gmap[x])&1 else lo
        raise ValueError('BDD cycle')
    patterns={bits for bits in range(1<<N) if accepts(bits)}
    return patterns,states,set(order),accepts

def validate(cnf_data,cert):
    expect(hashlib.sha256(cnf_data).hexdigest()==cert['source_sha256'],'bad CNF SHA256')
    nv,clauses=read_cnf(cnf_data)
    source_set={frozenset(c) for c in clauses}
    groups=cert['groups']
    expect(len(groups)==N and len(cert['machines'])==M,'wrong machine/job count')
    selectors=set()
    for group in groups:
        expect(len(group)==M and all(type(x)==int and x>0 and x<=nv for x in group)
               and len(set(group))==M,'bad group')
        expect(frozenset(group) in source_set,'group at-least-one absent')
        expect(frozenset((-group[0],-group[1])) in source_set,'group at-most-one absent')
        expect(not(selectors & set(group)),'overlap groups')
        selectors.update(group)
    states=set();selected=set();machine_pats=[];accepts=[]
    for machine in cert['machines']:
        p,s,o,fn=source_bdd(machine,groups,source_set,nv)
        expect(not(states&s) and not(selected&o),'BDD state or selector overlap')
        states|=s;selected|=o
        machine_pats.append(p);accepts.append(fn)
    expect(not(states&selected) and selected==selectors,'BDD selectors not disjoint/covering')
    spec={0}|{mask(edge) for edge in EDGES}
    kind=cert['kind']
    expect(kind in ('unsat_hole','sat_control'),'wrong experiment kind')
    if kind=='sat_control':spec.add(((1<<N)-1)^mask(EDGES[0]))
    for i,p in enumerate(machine_pats):
        expect(p==spec, f'machine {i} wrong accepted language')
    expect(set(cert['claimed_patterns'])==spec,'claimed patterns falsified')
    # Bounded exact-cover check, independently from any modular theorem.
    allones=(1<<N)-1
    exact=[(a,b) for a in machine_pats[0] for b in machine_pats[1]
           if (a & b)==0 and (a | b)==allones]
    if kind=='unsat_hole':expect(not exact,'UNSAT instance contains exact cover')
    else:expect(bool(exact),'SAT control has no exact cover')
    # Full original 7-edge family has no two disjoint nonempty triples.
    if kind=='unsat_hole':
        for a,b in itertools.combinations(sorted(spec-{0}),2):
            expect(bool(a&b),'disjoint triples invalidate claimed obstruction')
    # Verify fractional LP certificate: 4 triple patterns each with weight 1/4
    # per machine, each job must occur twice across those four patterns.
    fractionals=cert['fractional_patterns']
    expect(len(fractionals)==4 and len(set(fractionals))==4,
           'invalid fractional witness length')
    expect(all(p in machine_pats[0] and p in machine_pats[1] for p in fractionals),
           'fractional pattern not in local language')
    expect(all(sum((p>>i)&1 for p in fractionals)==2 for i in range(N)),
           'fractional coverage not exactly one job per machine mixture')
    # Integer lattice witness: 7 signed multiplicities of local patterns,
    # total signed number of patterns=2 and each job signed incidence=1.
    coeff=cert['signed_coefficients']
    witness=[mask(edge) for edge in EDGES]
    expect(len(coeff)==7 and all(type(c)==int for c in coeff),'bad signed witness')
    expect(sum(coeff)==M and all(sum(coeff[j]*((witness[j]>>i)&1)
             for j in range(len(witness)))==1 for i in range(N)),
             'target not in integer configuration lattice')
    # Confirm no single or pair GF2-projection detects target.
    def gs(p,supports):
        return sum((((p & a).bit_count() &1)<<i) for i,a in enumerate(supports))
    support_masks=range(1,1<<N)
    target=(1<<N)-1
    scalar_subset_count=0
    # A stronger scalar control than scanning selected moduli:
    # for each 0/1 support there are TWO locally accepted patterns
    # with exactly the demanded count on that support.
    for subset in support_masks:
        goal=subset.bit_count()
        expect(any((a&subset).bit_count()+(b&subset).bit_count()==goal
                   for a in machine_pats[0] for b in machine_pats[1]),
               'scalar subset count contradicts claimed limitation')
        scalar_subset_count+=1
    single_count=pair_count=0
    for k in (1,2):
        for chosen in itertools.combinations(support_masks,k):
            S={gs(p,chosen) for p in machine_pats[0]}
            R={x^y for x in S for y in S}
            fail=gs(target,chosen) not in R
            expect(not fail,f'k={k} GF2 witness exists, falsifies benchmark')
            if k==1:single_count+=1
            else:pair_count+=1
    triple=(4,11,33)
    S={gs(p,triple) for p in machine_pats[0]}
    R={x^y for x in S for y in S}
    if kind=='unsat_hole':
        expect(gs(target,triple) not in R,'3-dimensional GF2 obstruction missing')
    else:
        expect(gs(target,triple) in R,'SAT control incorrectly excluded by parity')
    return {'status':'UNSAT_STRUCTURAL_EXACT_COVER_CONFIRMED' if not exact
                  else 'SAT_CONTROL_HAS_EXACT_COVER',
            'source_sha256':cert['source_sha256'],'vars':nv,'clauses':len(clauses),
            'patterns_per_machine':len(spec),'exact_covers':len(exact),
            'fractional_cover_checked':True,'integer_lattice_witness_checked':True,
            'scalar_subset_supports_checked':scalar_subset_count,
            'one_parity_projections_tested':single_count,
            'two_parity_projection_pairs_tested':pair_count,
            'three_parity_witness':list(triple),
            'rup_steps_claimed':cert.get('rup_steps'),
            'source_standard_proof':'EXTERNAL_VERIPB_REQUIRED'}

def verify_sat_model(cnf_data,cert):
    nv,clauses=read_cnf(cnf_data)
    spec0=mask(EDGES[0]);spec1=((1<<N)-1)^spec0
    true_vars=set()
    for i in range(N):true_vars.add(cert['groups'][i][0 if (spec0>>i)&1 else 1])
    for m in cert['machines']:
        nodes={q:(x,l,h) for q,x,l,h in m['transitions']}
        true_vars.add(m['true_terminal'])
        q=m['root']
        while q in nodes:
            true_vars.add(q)
            x,lo,hi=nodes[q]
            q=hi if x in true_vars else lo
        expect(q==m['true_terminal'],'SAT model BDD path invalid')
    expect(all(any((abs(v) in true_vars)==(v>0) for v in c) for c in clauses),
           'source CNF SAT model invalid')
    return {'status':'SAT_MODEL_VERIFIED','source_clauses_checked':len(clauses)}

def unit_conflict(clauses,assumptions):
    assign={}
    for lit in assumptions:
        v=abs(lit);b=lit>0
        if v in assign and assign[v]!=b:return True
        assign[v]=b
    while True:
        changed=False
        for clause in clauses:
            unsat=[];sat=False
            for lit in clause:
                v=abs(lit)
                if v not in assign:unsat.append(lit)
                elif assign[v]==(lit>0):sat=True;break
            if sat:continue
            if not unsat:return True
            if len(unsat)==1:
                lit=unsat[0];v=abs(lit);b=lit>0
                if v in assign:
                    if assign[v]!=b:return True
                else:assign[v]=b;changed=True
        if not changed:return False

def check_rup(data,drup_bytes):
    _,src=read_cnf(data)
    steps=[]
    for line in drup_bytes.decode('ascii').splitlines():
        row=list(map(int,line.split()))
        expect(row and row[-1]==0,'DRUP line not zero-terminated')
        steps.append(tuple(row[:-1]))
    db=list(src)
    for index,step in enumerate(steps):
        expect(unit_conflict(db,[-x for x in step]),f'RUP failure at step {index+1}')
        db.append(step)
    expect(steps and steps[-1]==(),'proof lacks final empty clause')
    return {'status':'ALL_RUP_STEPS_CHECKED','rup_steps':len(steps)}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cnf',type=Path,required=True);p.add_argument('--certificate',type=Path,required=True)
    p.add_argument('--drup',type=Path)
    a=p.parse_args()
    try:
        data=a.cnf.read_bytes();cert=json.loads(a.certificate.read_text())
        obj=validate(data,cert)
        if a.drup:obj['rup_audit']=check_rup(data,a.drup.read_bytes())
        elif cert['kind']=='sat_control':obj['sat_audit']=verify_sat_model(data,cert)
        print(json.dumps(obj,indent=2,sort_keys=True))
    except (KeyError,ValueError,TypeError) as e:
        print(json.dumps({'status':'INVALID_CERTIFICATE','reason':str(e)}))
        raise SystemExit(1)
