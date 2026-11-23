#!/usr/bin/env python3
"""Independent project-level checker for DRNAS MIX2 on *unchanged* Yosys CNF.
Rebuild AND/OR gate definitions from original 3-clause templates, validate
each gate's truth table, independently reconstruct XOR macros, and run separate
GF(2) and unit propagation. This is NOT a standard DRAT/LRAT/VeriPB proof.
"""
from __future__ import annotations
import argparse, hashlib, itertools, json, sys, time
from collections import defaultdict
from pathlib import Path

def source_cnf(path):
    n=declared=None;clauses=[];acc=[]
    for line in path.open():
        if not line.strip() or line.startswith(('c','%')):continue
        if line.startswith('p '):
            _,kind,n,declared=line.split();assert kind=='cnf';n=int(n);declared=int(declared);continue
        assert n is not None
        for s in line.split():
            x=int(s);assert abs(x)<=n
            if x==0:clauses.append(tuple(acc));acc=[]
            else:acc.append(x)
    assert not acc and len(clauses)==declared
    return n,clauses

def satisfies(clause, values):
    return any(values[abs(lit)]==(lit>0) for lit in clause)

def truth_table_gate(support, y, op, a, b):
    allvars=sorted(set(map(abs,(y,a,b))))
    for choice in itertools.product((0,1),repeat=len(allvars)):
        values={v:bool(choice[i]) for i,v in enumerate(allvars)}
        if not all(satisfies(cl,values) for cl in support):continue
        va=values[abs(a)]^(a<0);vb=values[abs(b)]^(b<0)
        target=(va|vb) if op=='OR' else (va&vb)
        if values[y]!=target:return False
    return True

def build_gates(clauses):
    binaries=set(tuple(sorted(c)) for c in clauses if len(c)==2)
    candidates=defaultdict(list)
    for clause in clauses:
        if len(clause)!=3 or len({abs(t) for t in clause})!=3:continue
        maximum=max(abs(t) for t in clause)
        for j,out in enumerate(clause):
            if abs(out)!=maximum:continue
            rest=[t for k,t in enumerate(clause) if k!=j]
            b1=tuple(sorted((-out,-rest[0])))
            b2=tuple(sorted((-out,-rest[1])))
            if b1 not in binaries or b2 not in binaries:continue
            a,b=(rest if out<0 else [-t for t in rest]);op='OR' if out<0 else 'AND'
            assert truth_table_gate((clause,b1,b2),abs(out),op,a,b),'gate support failure'
            candidates[abs(out)].append((op,a,b))
    gates={}
    for y,options in candidates.items():
        distinct={tuple([op]+sorted((a,b))) for op,a,b in options}
        if len(distinct)==1:gates[y]=options[0]
    return gates

def xor_motifs(gates):
    found=[]
    for y,(op,a,b) in gates.items():
        if op!='OR' or a<=0 or b<=0 or a not in gates or b not in gates:continue
        if gates[a][0]!='AND' or gates[b][0]!='AND':continue
        x1,z1=gates[a][1:];x2,z2=gates[b][1:]
        if {abs(x1),abs(z1)}!={abs(x2),abs(z2)} or abs(x1)==abs(z1):continue
        x,z=sorted((abs(x1),abs(z1)))
        def gate_value(g,values):
            op,a,b=g;va=values[abs(a)]^(a<0);vb=values[abs(b)]^(b<0)
            return (va|vb) if op=='OR' else (va&vb)
        outcomes=[]
        for xx,zz in itertools.product((0,1),repeat=2):
            vals={x:xx,z:zz}
            result=gate_value(gates[a],vals)|gate_value(gates[b],vals)
            outcomes.append((xx,zz,result))
        if all(r==(xx^zz) for xx,zz,r in outcomes):rhs=0
        elif all(r==((xx^zz)^1) for xx,zz,r in outcomes):rhs=1
        else:continue
        found.append((x,z,y,rhs))
    return found

class Gaussian:
    def __init__(self):self.rows={};self.contradiction=False
    def reduce(self,mask,rhs=0):
        while mask:
            p=(mask & -mask).bit_length()-1
            if p not in self.rows:break
            q,t=self.rows[p];mask^=q;rhs^=t
        return mask,rhs
    def add(self,terms,rhs):
        mask=0
        for term in terms:mask^=1<<term
        mask,rhs=self.reduce(mask,int(rhs))
        if mask==0:
            if rhs:self.contradiction=True
            return False
        p=(mask&-mask).bit_length()-1;self.rows[p]=(mask,rhs)
        return True
    def fixed(self,v):
        mask,rhs=self.reduce(1<<v)
        return rhs if mask==0 else None
    def relation(self,a,b):
        mask,rhs=self.reduce((1<<a)^(1<<b))
        return rhs if mask==0 else None

def bcp(clauses,known):
    changed=True
    while changed:
        changed=False
        for clause in clauses:
            unresolved=[];sat=False
            for lit in clause:
                val=known.get(abs(lit))
                if val is None:unresolved.append(lit)
                elif val==(lit>0):sat=True;break
            if sat:continue
            if not unresolved:return True
            if len(unresolved)==1:
                lit=unresolved[0];v=abs(lit);val=lit>0
                if v in known and known[v]!=val:return True
                if v not in known:known[v]=val;changed=True
    return False

def verify(path):
    t=time.perf_counter()
    n,cls=source_cnf(path)
    gates=build_gates(cls);xors=xor_motifs(gates)
    known={}
    if bcp(cls,known):result='UNSAT';reason='CNF_UNIT_CONTRADICTION'
    else:
        gauss=Gaussian()
        for x,z,y,rhs in xors:gauss.add((x,z,y),rhs)
        for v,val in known.items():gauss.add((v,),val)
        reason='NONE';result='UNKNOWN'
        if gauss.contradiction:result='UNSAT';reason='XOR_INIT_CONFLICT'
        else:
            for iteration in range(12):
                new=0
                for y,(op,a,b) in gates.items():
                    va=gauss.fixed(abs(a));vb=gauss.fixed(abs(b))
                    if va is not None:va^=a<0
                    if vb is not None:vb^=b<0
                    terms=rhs=None
                    if va is not None and vb is not None:
                        terms=(y,);rhs=int(va|vb) if op=='OR' else int(va&vb)
                    elif va is not None:
                        if (op=='OR' and va) or (op=='AND' and not va):terms=(y,);rhs=int(va)
                        else:terms=(y,abs(b));rhs=int(b<0)
                    elif vb is not None:
                        if (op=='OR' and vb) or (op=='AND' and not vb):terms=(y,);rhs=int(vb)
                        else:terms=(y,abs(a));rhs=int(a<0)
                    else:
                        diff=gauss.relation(abs(a),abs(b))
                        if diff is not None:
                            diff^=(a<0)^(b<0)
                            if diff==0:terms=(y,abs(a));rhs=int(a<0)
                            else:terms=(y,);rhs=int(op=='OR')
                    if terms is not None and gauss.add(terms,rhs):new+=1
                    if gauss.contradiction:break
                if gauss.contradiction:result='UNSAT';reason='GATE_AFFINE_CONTRADICTION';break
                new_fixed=0
                for v in range(1,n+1):
                    val=gauss.fixed(v)
                    if val is None:continue
                    if v not in known:known[v]=bool(val);new_fixed+=1
                    elif known[v]!=bool(val):result='UNSAT';reason='UNIT_CONTRADICTION';break
                if result=='UNSAT':break
                old=len(known)
                if bcp(cls,known):result='UNSAT';reason='SOURCE_CLAUSE_CONTRADICTION';break
                new_fixed+=len(known)-old
                for v,val in known.items():gauss.add((v,),val)
                if gauss.contradiction:result='UNSAT';reason='SOURCE_XOR_CONTRADICTION';break
                if not new and not new_fixed:break
    return {'result':result,'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'vars':n,'clauses':len(cls),'gates_source_checked':len(gates),
        'xor_macro_truth_tables_checked':len(xors),'reason':reason,
        'seconds':round(time.perf_counter()-t,6),
        'checker':'PROJECT_SOURCE_CHECKER_NOT_STANDARD_UNSAT_PROOF'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('cnf',type=Path)
    p.add_argument('--expected',choices=['UNSAT','UNKNOWN'],default=None)
    a=p.parse_args();r=verify(a.cnf);print(json.dumps(r,indent=2))
    if a.expected is not None and r['result']!=a.expected:sys.exit(1)
