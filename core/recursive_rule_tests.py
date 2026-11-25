"""Recursive closure and cross-instance transfer; fresh processes, exact audits."""
from pathlib import Path
from tempfile import TemporaryDirectory
from run import run
from symbolic_verify import check
from itertools import product

def word(n,mask,axis):
    return ''.join(axis if mask>>i&1 else 'I' for i in range(n))

def energy(masks,coeff,n):
    return min(sum(c*(-1 if (x&m).bit_count()%2 else 1) for m,c in zip(masks,coeff)) for x in range(1<<n))

def main():
    with TemporaryDirectory() as tmp:
        d=Path(tmp); mem=d/'rules.txt'; seq=0; rows=[]
        def solve(label,n,terms,memory=None,task='lower',expected='PROVED'):
            nonlocal seq
            seq+=1; src=d/f'{seq}.sop'; cert=d/f'{seq}.cert'
            src.write_text(f'p sop {task} {n} {len(terms)} 0\n'+''.join(f'{c} {p}\n' for c,p in terms))
            r=run(src,cert,5,audit_seconds=15,rule_memory=memory)
            assert r['status']==expected,(label,r)
            if expected=='PROVED': assert check(src,cert)['status']=='PROVED'
            rows.append(dict(label=label,**r))
            return r
        # Four triples, with a chain of shared intermediate words.
        masks=[1,2,3,4,7,8,15,16,31]
        coeff=[1]*len(masks)
        assert energy(masks,coeff,5)==-5
        train=solve('train',5,[(5,'I'*5)]+[(c,word(5,m,'X')) for m,c in zip(masks,coeff)],mem)
        assert train['closure_depth']>=2,train
        assert {'C4+','C5+','C6+'}<=set(train['composed_rules']),train
        assert 'C5+' in mem.read_text() and 'C6+' in mem.read_text(),train
        for item in train['rule_derivations']:
            assert set(item['left'])^set(item['right'])==set(item['result'])
            assert item['left_sign']*item['right_sign']==item['sign']
        # Transfer to only the endpoints (no intermediate words), changed
        # dimension, Pauli frame, support, and coefficient scales.
        for k,scale in [(5,2),(6,3)]:
            n=k+3; indices=[0,2,3,5,6][:k-1]
            masks=[1<<i for i in indices]
            masks.append(sum(masks))
            coeff=[scale]*k
            if k%2==0: coeff[-1]=-scale
            # Preferred eigenvalues have inconsistent product +1.
            offset=scale*(k-2)
            assert energy(masks,coeff,n)==-offset
            terms=[(offset,'I'*n)]+[(c,word(n,m,'Y')) for m,c in zip(masks,coeff)]
            cold=solve(f'cold{k}',n,terms)
            warm=solve(f'warm{k}',n,terms,mem)
            assert warm['telemetry']['memory_proved'],warm
            assert warm['telemetry']['partitions_tried']<cold['telemetry']['partitions_tried'],(cold,warm)
            solve(f'fixed{k}',n,terms,task='lower-fixed',expected='UNKNOWN')
            # Flip a coefficient: all preferred signs become compatible.
            bad=terms[:-1]+[(-terms[-1][0],terms[-1][1])]
            assert energy(masks,coeff[:-1]+[-coeff[-1]],n)==-scale*k
            solve(f'negative{k}',n,bad,mem,expected='UNKNOWN')
        print({'recursive_cases':len(rows),'training_depth':train['closure_depth'],
               'derived':train['composed_rules'],'rows':rows,'status':'PASS'})
if __name__=='__main__':main()
