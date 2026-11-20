#!/usr/bin/env python3
"""Independent DRNAS HYBRID5 verifier: CNF, three-machine configuration
compatibility, fractional/signed witnesses, GF2 small-k tests and RUP.
Nothing from the emitter is imported.
"""
import argparse, hashlib, itertools, json
from pathlib import Path

N=9; M=3
# Source-experiment specification, not taken from the certificate.
EDGES=((2,5,6),(3,4,8),(1,3,7),(1,5,6),(5,7,8),(6,7,8),(0,2,4),(0,3,4),(0,1,2),(0,1,5))

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
    expect(len(groups)==N and len(cert['machines'])==M,'wrong job/machine count')
    selectors=set()
    for group in groups:
        expect(len(group)==M and len(set(group))==M
               and all(type(x)==int and 1<=x<=nv for x in group),'invalid group')
        expect(frozenset(group) in source_set,'missing at-least-one source group')
        for a,b in itertools.combinations(group,2):
            expect(frozenset((-a,-b)) in source_set,'missing source at-most-one')
        expect(not (selectors & set(group)),'overlapping groups')
        selectors.update(group)
    all_states=set()
    all_orders=set()
    machine_pats=[]
    for machine in cert['machines']:
        p,states,order,fn=source_bdd(machine,groups,source_set,nv)
        expect(not(all_states & states) and not(all_orders & order),
               'overlapping machine states or selectors')
        all_states|=states
        all_orders|=order
        machine_pats.append(p)
    expect(not(all_states & selectors) and all_orders==selectors,
           'machine state/selector alias or missing selectors')
    kind=cert['kind']
    expect(kind in ('global3_unsat','sat_control'),'wrong experiment kind')
    base_patterns={0}|{mask(e) for e in EDGES}
    spec=set(base_patterns)
    if kind=='sat_control':
        spec.add(((1<<N)-1)^mask(EDGES[0]))
    for i,pats in enumerate(machine_pats):
        expect(pats==spec,f'machine {i} does not have claimed local BDD language')
    expect(set(cert['claimed_patterns'])==spec,
           'claimed local patterns do not match independently audited BDDs')

    allones=(1<<N)-1
    all_exact=[]
    for a in machine_pats[0]:
        for b in machine_pats[1]:
            if a&b:continue
            for c in machine_pats[2]:
                if not((a|b)&c) and ((a|b|c)==allones):
                    all_exact.append((a,b,c))
    if kind=='global3_unsat':
        expect(not all_exact,'UNSAT candidate has an exact cover')
    else:
        expect(bool(all_exact),'SAT control has no exact cover')

    # Derive a *complete* pairwise-disjoint compatibility list from the
    # original 10 local configurations and require absence of a third
    # complement. All patterns are independently source-BDD checked above.
    base=[mask(e) for e in EDGES]
    witness=[]
    for i,a in enumerate(base):
        for j,b in enumerate(base[i+1:],i+1):
            if not (a&b):
                missing=allones^(a|b)
                witness.append([i,j,missing])
                if kind=='global3_unsat':
                    expect(missing not in spec,
                           'disjoint pair has complement: exact cover exists')
    expect(len(witness)==16,'expected 16 disjoint pairs')
    expect(cert['pairwise_disjoint_witnesses']==witness,
           'malformed exhaustive compatibility witness')

    # The 9 original triples each cover each job 3 times.
    # On EACH machine put probability 1/9 on each of these triples.
    # Total expected coverage per job is 3*3/9=1, with per-machine
    # probabilities summing to one.
    frac=cert['fractional_patterns']
    expect(len(frac)==9 and len(set(frac))==9 and
           set(frac)=={mask(e) for e in EDGES[:9]},
           'bad fractional patterns')
    expect(cert['fractional_denominator']==9,'bad fractional denominator')
    expect(all(p in spec for p in frac),'fractional config is not allowed')
    expect(all(sum((p>>i)&1 for p in frac)==3 for i in range(N)),
           'fractional solution does not cover every job exactly once')
    # A SIGNED (not feasible) integer witness. Its existence proves
    # the demand belongs to the integer span; no necessary additive
    # congruence from this span can exclude it.
    coeff=cert['signed_coefficients']
    expect(len(coeff)==len(EDGES) and all(type(x)==int for x in coeff),
           'invalid integer lattice coefficients')
    expect(sum(coeff)==M and
           all(sum(coeff[j]*((base[j]>>i)&1) for j in range(len(base)))==1
               for i in range(N)),
           'target not in integer configuration lattice')
    expect(any(x<0 for x in coeff),'unexpected nonnegative exact-cover witness')

    # Exhaust all *linear* GF(2) signatures of dimension 1 or 2.
    # A tuple of local patterns matches a chosen parity support tuple
    # exactly when all differences from the all-ones target have
    # zero parity on every support. Use exact Python integer bitsets
    # to avoid floating point or heuristic sampling.
    differences={allones^a^b^c for a in spec for b in spec for c in spec}
    if kind=='global3_unsat':
        expect(0 not in differences,
               'XOR-exact triple unexpectedly exists in UNSAT instance')
    # For SAT control it is okay (and expected) for difference 0 to exist.
    bits=sorted(differences)
    compatible={}
    single_count=0
    for support in range(1,1<<N):
        support_set=sum(1<<i for i,d in enumerate(bits)
                        if (d&support).bit_count()%2==0)
        compatible[support]=support_set
        expect(support_set!=0,
               '1D GF2 witness exists; claimed separation is false')
        single_count+=1
    pair_count=0
    chosen=list(compatible.items())
    for j,(a,mask_a) in enumerate(chosen):
        for b,mask_b in chosen[j+1:]:
            expect(mask_a&mask_b,'2D GF2 witness exists; claimed separation false')
            pair_count+=1
    expect(single_count==511 and pair_count==130305,
           'unexpected number of GF2 support tests')

    return {
        'status':'UNSAT_GLOBAL3_COMPATIBILITY_CONFIRMED'
          if not all_exact else 'SAT_CONTROL_HAS_EXACT_COVER',
        'cnf_sha256':cert['source_sha256'],
        'jobs':N,'machines':M,'vars':nv,'clauses':len(clauses),
        'nonempty_patterns':len(EDGES),
        'disjoint_pairs':len(witness),
        'disjoint_triples':len(all_exact),
        'fractional_cover_checked':True,
        'integer_lattice_witness_checked':True,
        'one_dimensional_gf2_tested':single_count,
        'two_dimensional_gf2_tested':pair_count,
        'rup_steps_claimed':cert.get('rup_steps'),
        'external_veripb_status':'INDEPENDENT_CI_REQUIRED'
    }

def verify_sat_model(cnf_data,cert):
    nv,clauses=read_cnf(cnf_data)
    jobmask=mask(EDGES[0])
    complement=((1<<N)-1)^jobmask
    # Machine 0 takes EDGES[0], machine 1 takes complement,
    # and machine 2 takes the empty configuration.
    true_vars=set()
    for i in range(N):
        machine=0 if (jobmask>>i)&1 else 1
        true_vars.add(cert['groups'][i][machine])
    for j,m in enumerate(cert['machines']):
        nodes={q:(x,l,h) for q,x,l,h in m['transitions']}
        true_vars.add(m['true_terminal'])
        q=m['root']
        while q in nodes:
            true_vars.add(q)
            x,lo,hi=nodes[q]
            q=hi if x in true_vars else lo
        expect(q==m['true_terminal'],
               f'candidate control model rejected by machine {j} BDD')
    expect(all(any((abs(v) in true_vars)==(v>0) for v in clause)
               for clause in clauses),'SAT model fails a source CNF clause')
    return {'status':'SAT_MODEL_VERIFIED','source_clauses':len(clauses),
            'source_vars':nv,'true_variables':len(true_vars)}

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
