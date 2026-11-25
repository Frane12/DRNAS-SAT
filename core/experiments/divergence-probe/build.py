"""Expose one suspension point per flip in the published repair loop."""
from pathlib import Path
import subprocess,tempfile
here=Path(__file__).resolve().parent
core=here.parents[1]
src=(core/'vendor/unified/repair.hpp').read_text()
old='inline bool repair(int n,const Clauses& cs,Model& m,Time until,uint64_t& steps)'
assert src.count(old)==1 and src.count('++steps;')==1
src=src.replace(old,'inline Cursor observe(int n,const Clauses& cs,Model& m,Time until,uint64_t& steps)')
src=src.replace('return true;', 'co_return;').replace('return false;', 'co_return;')
src=src.replace('++steps;', '++steps; co_yield Move{chosen, int(bad.size())};')
with tempfile.TemporaryDirectory() as tmp:
    (Path(tmp)/'observe.hpp').write_text(src)
    subprocess.run(['c++','-O3','-std=c++20','-I',str(core/'vendor/unified'),'-I',tmp,
                    str(here/'trial.cpp'),'-o',str(core/'bin/divergence-trial')],check=True)
