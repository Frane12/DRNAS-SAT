"""Build a separate diagnostic binary from the pinned production projection path."""
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
CORE = HERE.parents[1]


def instrument(s, old, new):
    if s.count(old) != 1:
        raise RuntimeError('CORE source no longer matches the diagnostic hook: ' + old)
    return s.replace(old, new)


def main():
    src = (CORE/'core.cpp').read_text()
    src = instrument(src, 'int discover(){', '''int discover(){
        if (const char* out = getenv("DRNAS_CAPTURE_STATE")) {
            fs::path dest(out);
            write_file(dest / "active.rows", clauses_text(all));
            write_file(dest / "ledger.rows", clauses_text(ledger));
            ostringstream witness;
            witness << "drnas-table-v1 " << source_digest << '\\n';
            for (const auto& group : table_messages.groups) {
                witness << "i ";
                for (int id : group.premises) witness << id << ' ';
                witness << "0\\n";
                for (const auto& c : group.claims) witness << "t " << clauses_text({c});
            }
            write_file(dest / "messages.txt", witness.str());
        }
        bool replay = getenv("DRNAS_REPLAY_STATE") != nullptr;''')
    src = instrument(src, 'consistent=projection.run(p,part(.25))',
                     'consistent=projection.run(p,replay ? toolbox::after(.150) : part(.25))')
    src = instrument(src, 'work,fixed,p,part(.20),cases',
                     'work,fixed,p,replay ? toolbox::after(.090) : part(.20),cases')
    src = instrument(src, 'm,part(.35),repair_flips',
                     'm,replay ? toolbox::after(getenv("DRNAS_FULL_REPAIR") ? 2.0 : .145) : part(.35),repair_flips')
    src = instrument(src, '        auto r=consistent?', '        if(replay)return 0;\n        auto r=consistent?')
    src = instrument(src, 'int rc=core.solve(argv[1]);', '''int rc;
        if (const char* state = getenv("DRNAS_REPLAY_STATE")) {
            core.original = toolbox::parse(read_file(argv[1]));
            core.all = parse_proof(read_file(fs::path(state)/"active.rows"),core.original.n);
            core.ledger = parse_proof(read_file(fs::path(state)/"ledger.rows"),core.original.n);
            rc = core.discover();
        } else rc=core.solve(argv[1]);''')
    with tempfile.TemporaryDirectory() as tmp:
        unit = Path(tmp)/'replay.cpp'
        unit.write_text(src)
        (CORE/'bin').mkdir(exist_ok=True)
        subprocess.run(['c++','-std=c++20','-O3','-I',str(CORE),str(unit),'-lcrypto',
                        '-o',str(CORE/'bin/f26-replay')],check=True)

if __name__ == '__main__':
    main()
