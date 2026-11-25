"""Fresh-process transfer; memory is a proposal, not a proof."""
from pathlib import Path
from tempfile import TemporaryDirectory
from run import run
from symbolic_verify import check

def main():
    with TemporaryDirectory() as tmp:
        d=Path(tmp); mem=d/'rules.txt'; seq=0
        def solve(n,terms,target=0,memory=True):
            nonlocal seq
            seq+=1
            src=d/f'{seq}.sop'; cert=d/f'{seq}.cert'
            src.write_text(f'p sop lower {n} {len(terms)} {target}\n'+''.join(f'{c} {p}\n' for c,p in terms))
            result=run(src,cert,5,audit_seconds=15,rule_memory=mem if memory else None)
            if result['status']=='PROVED': assert check(src,cert)['status']=='PROVED'
            return result
        # Diagonal frustrated triangle -> generic signed product identity.
        train=solve(2,[(1,'II'),(1,'ZI'),(1,'IZ'),(1,'ZZ')])
        assert train['status']=='PROVED' and 'C3+' in train['learned_rules'],train
        assert 'C3+' in mem.read_text(),train
        # Different basis, coefficients, and support. Fresh process.
        terms=[(5,'IIII'),(2,'XIII'),(3,'IIXI'),(4,'XIXI')]
        cold=solve(4,terms,memory=False)
        warm=solve(4,terms)
        assert cold['status']==warm['status']=='PROVED',(cold,warm)
        assert warm['telemetry']['memory_proved'] and warm['telemetry']['memory_matches']>=1,warm
        assert warm['telemetry']['partitions_tried']<cold['telemetry']['partitions_tried'],(cold,warm)
        # Same pattern shape but opposite product sign: true minimum -2.
        bad=solve(2,[(1,'II'),(1,'XX'),(1,'YY'),(1,'ZZ')])
        assert bad['status']=='UNKNOWN' and not bad['telemetry']['memory_proved'],bad
        before=mem.read_text()
        # No rule should be learned from failed proof.
        assert 'C3-' not in before,before
        # Inject wrong hint explicitly: rechecking the new operator must reject.
        mem.write_text(before+'C3-\n')
        poisoned=solve(2,[(1,'II'),(1,'XX'),(1,'YY'),(1,'ZZ')])
        assert poisoned['status']=='UNKNOWN' and not poisoned['telemetry']['memory_proved'],poisoned
        # Learn anticommuting norm rule and transfer to different weights/labels.
        a=solve(1,[('3/2','I'),(1,'X'),(1,'Z')])
        assert a['status']=='PROVED' and 'A2' in a['learned_rules'],a
        b=solve(3,[(6,'III'),(3,'IIX'),(4,'IIZ')])
        assert b['status']=='PROVED' and b['telemetry']['memory_proved'],b
        print({'rule_memory_cases':7,'cold_partitions':cold['telemetry']['partitions_tried'],
               'warm_partitions':warm['telemetry']['partitions_tried'],'status':'PASS'})
if __name__=='__main__':main()
