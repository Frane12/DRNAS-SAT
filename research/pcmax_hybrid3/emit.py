#!/usr/bin/env python3
"""MATH-HYBRID3: original-to-experiment CNF + RUP/VeriPB 3.0 proof.

Source graph is a newly constructed (not archived SAT-Competition) CNF.
Fano: 7 jobs, 3 machines, each machine permits empty or a Fano line.
The compact mod-3 mathematical certificate is backed by a source-level
RUP refutation. Its DPLL expansion is not claimed to be polynomial.
"""
import argparse, hashlib, itertools, json
from pathlib import Path

def fano_lines():
    return sorted({tuple(sorted((a-1,b-1,(a^b)-1)))
                   for a in range(1,8) for b in range(a+1,8)})
def allowed(kind):
    if kind == "fano":
        n,m = 7,3
        a = [0] + [sum(1<<i for i in line) for line in fano_lines()]
    elif kind == "sat-control":
        n,m = 6,3
        a = [0] + [sum(1<<i for i in pair)
                   for pair in itertools.combinations(range(n),2)]
    else:
        raise ValueError("unknown kind")
    return n,m,sorted(a)

def generate(folder,kind):
    n,m,acc=allowed(kind)
    clauses=[]
    def add(c):
        c=tuple(c)
        assert all(type(x)==int and x for x in c)
        clauses.append(c)
    def selector(j,i): return j*n+i+1
    groups=[]
    for i in range(n):
        g=[selector(j,i) for j in range(m)]
        groups.append(g)
        add(g)
        for j in range(m):
            for h in range(j+1,m):add((-g[j],-g[h]))
    next_var=n*m+1
    machines=[]
    accset=set(acc)
    for j in range(m):
        prefixes=[set() for _ in range(n)]
        for pat in acc:
            for i in range(n):
                prefixes[i].add(pat&((1<<i)-1))
        nodes={}
        for i in range(n):
            for prefix in sorted(prefixes[i]):
                nodes[(i,prefix)]=next_var
                next_var+=1
        t=next_var
        f=next_var+1
        next_var+=2
        root=nodes[(0,0)]
        add((root,));add((t,));add((-f,))
        transitions=[]
        for (i,prefix),q in sorted(nodes.items()):
            x=selector(j,i)
            children=[]
            for taken in (0,1):
                newmask=prefix|(taken<<i)
                if i==n-1:
                    child=t if newmask in accset else f
                else:
                    child=nodes.get((i+1,newmask),f)
                children.append(child)
            low,high=children
            add((-q,x,low))
            add((-q,-x,high))
            transitions.append([q,x,low,high])
        machines.append({
            "root":root,"true_terminal":t,"false_terminal":f,
            "variable_order":[selector(j,i) for i in range(n)],
            "transitions":transitions})
    folder.mkdir(parents=True,exist_ok=True)
    cnf=folder/"source.cnf"
    cnf.write_text(
        f"c DRNAS MATH-HYBRID3 generated {kind}, NOT archived SAT PCMAX source\n"
        f"p cnf {next_var-1} {len(clauses)}\n"
        +''.join(' '.join(map(str,row))+' 0\n' for row in clauses)
    )
    cert={
        "format":"drnas-modq-source-bdd-v1",
        "kind":kind,
        "provenance":"newly constructed source CNF, not SAT competition original",
        "source_sha256":hashlib.sha256(cnf.read_bytes()).hexdigest(),
        "groups":groups,"machines":machines,
        "claimed_local_patterns":acc,
        "modulus":3 if kind=="fano" else 2,
        "required":n,
        "standard_proof_status":"NOT_CHECKED_WITH_VERIPB"
    }
    (folder/"certificate.json").write_text(json.dumps(cert,indent=2)+"\n")
    if kind=="fano":
        # Each total assignment of jobs to machines is individually
        # incompatible with at least one local Fano-line BDD.
        # Blocking clauses are source-level RUP. Derived subtree
        # clauses follow from all three children and an exact-one
        # source clause, also by RUP.
        derived=[]
        def recurse(prefix):
            depth=len(prefix)
            block=tuple(-selector(prefix[i],i) for i in range(depth))
            if depth==n:
                derived.append(block)
                return
            for j in range(m):
                recurse(prefix+(j,))
            derived.append(block)
        recurse(())
        drup=folder/"proof.drup"
        drup.write_text(''.join(' '.join(map(str,row))+' 0\n'
                               for row in derived))
        pbp=folder/"proof.pbp"
        with pbp.open("w") as out:
            out.write("pseudo-Boolean proof version 3.0\n")
            out.write(f"f {len(clauses)} ;\n")
            for row in derived:
                lits=' '.join("1 "+("~" if x<0 else "")+"x"+str(abs(x))
                              for x in row)
                out.write("rup "+(lits+" " if lits else "")+">= 1 ;\n")
            out.write("output NONE ;\n")
            out.write("conclusion UNSAT ;\n")
            out.write("end pseudo-Boolean proof ;\n")
        cert["rup_steps"]=len(derived)
        cert["drup_sha256"]=hashlib.sha256(drup.read_bytes()).hexdigest()
        (folder/"certificate.json").write_text(json.dumps(cert,indent=2)+"\n")
    print(json.dumps({
        "kind":kind,"groups":n,"machines":m,
        "machine_patterns":len(acc),"vars":next_var-1,
        "clauses":len(clauses),"rup_steps":cert.get("rup_steps"),
        "cnf_sha256":cert["source_sha256"]},sort_keys=True))

if __name__ == "__main__":
    arg=argparse.ArgumentParser()
    arg.add_argument("--kind",choices=("fano","sat-control"),default="fano")
    arg.add_argument("--out",type=Path,required=True)
    opts=arg.parse_args()
    generate(opts.out,opts.kind)
