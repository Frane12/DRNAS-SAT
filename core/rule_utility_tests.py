"""Rule scheduling tests: cold exploration, audited credit, misses, cost and persistence."""
from pathlib import Path
from tempfile import TemporaryDirectory
from run import run
from rule_utility import choose, load, observe, context

def main():
    rules=['A2','C3+']
    def row(a,m,p,c):
        return dict(attempts=a,matches=m,proved=p,cost_us=c)
    assert choose(rules,{})=='A2'
    assert choose(rules,{'A2':row(1,1,1,100)})=='C3+'
    # A successful inexpensive rule wins exploitation; a dormant rule still
    # receives periodic exploration. Costs can reverse equal proof rates.
    assert choose(rules,{'A2':row(9,9,8,900),'C3+':row(2,0,0,200)})=='A2'
    assert choose(rules,{'A2':row(9,9,8,900),'C3+':row(1,0,0,100)})=='C3+'
    assert choose(rules,{'A2':row(3,3,3,30000),'C3+':row(3,3,3,300)})=='C3+'
    with TemporaryDirectory() as tmp:
        d=Path(tmp); mem=d/'rules.txt'; util=d/'rules.txt.utility.json'
        mem.write_text('drnas-rule-memory-v1\nA2\nC3+\n')
        seq=0
        def solve(terms,n=1,feedback=True,expected='PROVED'):
            nonlocal seq
            seq+=1
            src=d/f'{seq}.sop'; cert=d/f'{seq}.cert'
            src.write_text(f'p sop lower {n} {len(terms)} 0\n'+''.join(f'{c} {s}\n' for c,s in terms))
            r=run(src,cert,5,audit_seconds=15,rule_memory=mem,rule_feedback=feedback)
            assert r['status']==expected,r
            return r
        # A2 proves; C3+ is explored next, misses, and ordinary adaptive
        # decomposition proves the same source. No credit for that fallback.
        terms=[('3/2','I'),(1,'X'),(1,'Z')]
        first=solve(terms)
        second=solve(terms)
        assert first['rule_feedback']['selected']=='A2',first
        assert first['telemetry']['memory_proved'],first
        assert second['rule_feedback']['selected']=='C3+',second
        assert second['telemetry']['memory_matches']==0,second
        data=load(util)['mixed:small']
        assert data['A2']['proved']==1 and data['A2']['matches']==1,data
        assert data['C3+']['attempts']==1 and data['C3+']['proved']==0,data
        # Fixed memory is the paired no-learning arm, must not change scores.
        before=util.read_bytes()
        solve(terms,feedback=False)
        assert util.read_bytes()==before
        # False positivity must never receive proof credit, whichever rule is tried.
        bad=solve([(1,'I'),(1,'X'),(1,'Z')],expected='UNKNOWN')
        assert bad['rule_feedback']['observation']['proved']<=1,bad
        after=load(util)['mixed:small']
        assert sum(r['proved'] for r in after.values())==1,after
        # A new context starts its own exploration, not a global preference.
        solve([(1,'II'),(1,'ZI'),(1,'IZ'),(1,'ZZ')],n=2)
        assert 'diagonal:small' in load(util)
        # Invalid statistics cannot become mathematical evidence.
        util.write_text('not json')
        invalid=solve([(1,'I'),(1,'X'),(1,'Z')],expected='UNKNOWN')
        assert 'rule_feedback_error' in invalid,invalid
        print({'policy_checks':5,'native_cases':seq,'status':'PASS'})
if __name__=='__main__':main()
