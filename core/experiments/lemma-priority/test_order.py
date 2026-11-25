"""Unit checks of the native selector; the CNF proof audit is tested separately."""
from pathlib import Path
import subprocess,tempfile

CORE=Path(__file__).resolve().parents[2]
def main():
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp)
        # x1 occurs positively three times; x2 occurs negatively three times.
        source=['1 3 0','1 4 0','1 5 0','-2 3 0','-2 4 0','-2 5 0']
        (d/'source').write_text('p cnf 5 6\n'+'\n'.join(source)+'\n')
        def check(active,claims,mode,order,ordinal):
            (d/'active').write_text('\n'.join(source+active)+'\n')
            (d/'claims').write_text('\n'.join('t '+c for c in claims)+'\n')
            r=subprocess.check_output([CORE/'bin/priority-order',d/'source',d/'active',d/'claims',mode,d/'out'],text=True)
            assert int(r.split()[0])==ordinal
            assert (d/'out').read_text().splitlines()==source+order
        s=['1 0','2 0','4 5 0']
        check(s,s[:2],'table-rank',['2 0','4 5 0','1 0'],2)
        check(s,s[:2],'table-pick-first',['1 0','4 5 0','2 0'],1)
        check(s,s[:2],'table-first',s,0)
        check(s,[],'table-rank',s,0)
        check(s,['2 0','-4 0'],'table-rank',['2 0','1 0','4 5 0'],1)
        check(['3 0','4 0','1 5 0'],['3 0','4 0'],'table-rank',['3 0','1 5 0','4 0'],1)
    print('6 native scheduling checks passed')
if __name__=='__main__':main()
