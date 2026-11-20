#!/usr/bin/env python3
"""Source-only 175-step RUP/VeriPB candidate via safe BDD-prefix pruning.

Only supports exact generated Fano CNF from emit.py; the certificates
still cite the exact source.cnf SHA256. This is a proof-size experiment,
not an asymptotic polynomial-time claim.
"""
import argparse, hashlib, json
from pathlib import Path
from emit import allowed

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--folder",type=Path,required=True)
    a=p.parse_args()
    folder=a.folder
    source=folder/"source.cnf"
    cert=json.loads((folder/"certificate.json").read_text())
    assert cert["kind"]=="fano"
    assert cert["source_sha256"]==hashlib.sha256(source.read_bytes()).hexdigest()
    n,m,patterns=allowed("fano")
    assert cert["claimed_local_patterns"]==patterns
    assert len(cert["groups"])==n and len(cert["machines"])==m
    lines=set(patterns)
    prefix_rejections=[0]*(n+1)
    internal=[0]*(n+1)
    derived=[]

    def rejected(prefix):
        d=len(prefix)
        examined=(1<<d)-1
        for j in range(m):
            local=sum(1<<i for i,chosen in enumerate(prefix)
                      if chosen==j)
            if not any((pat&examined)==local for pat in lines):
                return True
        return False

    def visit(prefix):
        depth=len(prefix)
        block=tuple(-cert["groups"][i][j] for i,j in enumerate(prefix))
        if rejected(prefix):
            prefix_rejections[depth]+=1
            derived.append(block)
            return
        assert depth<n,"a full Fano assignment unexpectedly passes"
        for j in range(m):
            visit(prefix+(j,))
        # A source exact-one group clause and three already proven
        # child blocking clauses make this parent blocking clause RUP.
        internal[depth]+=1
        derived.append(block)

    visit(())
    assert derived and derived[-1]==()
    # This assertion is for this frozen generated Fano instance only.
    assert len(derived)==175,(len(derived),prefix_rejections,internal)
    drup=folder/"compact.drup"
    pbp=folder/"compact.pbp"
    drup.write_text(''.join(' '.join(map(str,row))+' 0\n' for row in derived))
    source_lines=source.read_text().splitlines()
    header=[l for l in source_lines if l.startswith('p cnf ')]
    assert len(header)==1
    source_clauses=int(header[0].split()[3])
    with pbp.open("w") as fd:
        fd.write("pseudo-Boolean proof version 3.0\n")
        fd.write(f"f {source_clauses} ;\n")
        for row in derived:
            terms=" ".join("1 ~x"+str(-v) for v in row)
            fd.write("rup "+(terms+" " if terms else "")+">= 1 ;\n")
        fd.write("output NONE ;\n")
        fd.write("conclusion UNSAT ;\n")
        fd.write("end pseudo-Boolean proof ;\n")
    meta={
        "source_sha256":cert["source_sha256"],
        "algorithm":"prefix-pruned RUP tree, all clauses check against original generated CNF",
        "old_proof_steps":cert["rup_steps"],
        "compact_proof_steps":len(derived),
        "prefix_rejected_at_depth":prefix_rejections,
        "internal_nodes_by_depth":internal,
        "compact_pbp_sha256":hashlib.sha256(pbp.read_bytes()).hexdigest(),
        "compact_drup_sha256":hashlib.sha256(drup.read_bytes()).hexdigest(),
        "external_veripb_status":"PENDING_INDEPENDENT_CHECK",
        "provenance":"generated Fano source, NOT archival PCMAX benchmark"
    }
    (folder/"compact.json").write_text(json.dumps(meta,indent=2)+"\n")
    print(json.dumps(meta,sort_keys=True,indent=2))

if __name__=="__main__":main()
