"""OP5: derive signed four-word rules from verified triples; fresh-process transfer."""
from pathlib import Path
from tempfile import TemporaryDirectory
from run import run
from symbolic_verify import check

def main():
    with TemporaryDirectory() as tmp:
        d=Path(tmp); seq=0; rows=[]
        def solve(label,n,terms,mem=None,expected='PROVED',task='lower'):
            nonlocal seq
            seq+=1
            src=d/f'{seq}.sop'; cert=d/f'{seq}.cert'
            src.write_text(f'p sop {task} {n} {len(terms)} 0\n'+''.join(f'{c} {p}\n' for c,p in terms))
            r=run(src,cert,5,audit_seconds=15,rule_memory=mem)
            assert r['status']==expected,(label,r)
            if expected=='PROVED': assert check(src,cert)['status']=='PROVED'
            rows.append((label,r.get('telemetry',{}).get('partitions_tried'),r.get('learned_rules',[])))
            return r
        plus=d/'plus.txt'; minus=d/'minus.txt'
        # P1 P2 P3=I and P3 P4 P5=I. No C4 rule initially.
        train=solve('train+',3,[(3,'III')]+[(1,w) for w in ['IIX','IXI','IXX','XIX','XXI']],plus)
        assert 'C4+' in train['composed_rules'] and 'C4+' in plus.read_text(),train
        # Only four endpoint words, in a new basis and with a changed sign.
        # Their product is +I, but all four individually preferred eigenvalues
        # have product -1, so the minimum is 0 after adding 2I.
        hold=[(2,'IIIII'),(1,'IIIYI'),(1,'IYIII'),(1,'YIIYI'),(-1,'YYIII')]
        cold=solve('cold+',5,hold)
        warm=solve('warm+',5,hold,plus)
        assert warm['telemetry']['memory_proved'] and warm['telemetry']['memory_matches']>=1,warm
        assert warm['telemetry']['partitions_tried']<cold['telemetry']['partitions_tried'],(cold,warm)
        solve('fixed+',5,hold,expected='UNKNOWN',task='lower-fixed')
        # All four preferred signs now compatible: false positive-bound request.
        bad=[(c if c!=-1 else 1,w) for c,w in hold]
        solve('negative+',5,bad,plus,expected='UNKNOWN')
        # A second composed rule with negative sign, discovered independently.
        train2=solve('train-',3,[(3,'III')]+[(1,w) for w in ['XXI','YYI','ZZI','IIX','ZZX']],minus)
        assert 'C4-' in train2['composed_rules'] and 'C4-' in minus.read_text(),train2
        neg=[(2,'IIII'),(1,'IXXI'),(1,'IYYI'),(1,'IIIX'),(1,'IZZX')]
        r=solve('warm-',4,neg,minus)
        assert r['telemetry']['memory_proved'],r
        # A sign-flipped coefficient removes the frustration. Even a stored
        # rule must not certify this false bound.
        negbad=neg[:-1]+[(-1,neg[-1][1])]
        solve('negative-',4,negbad,minus,expected='UNKNOWN')
        print({'op5_cases':len(rows),'rows':rows,'status':'PASS'})
if __name__=='__main__': main()
