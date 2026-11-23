# DRNAS CircuitCheck v0.1 — proof-first provjera digitalnih sklopova

**Istraživanje i autor:** Frane Drnas. Eksperimentalni praktični alat koji uspoređuje dvije kombinacijske Verilog izvedbe i izvodi točan algebarski dokaz ili konkretan protuprimjer iz sintetizirane mreže.

Za pokretanje su potrebni Python 3.10+ i Yosys; nije nužan SAT solver.

## Upute

### Generiraj primjere
`python3 apps/circuitcheck/generate_examples.py --out examples`

### Provjeri LFSR-64 (dvije RTL izvedbe)
`python3 apps/circuitcheck/circuitcheck.py --rtl examples/lfsr_64_equal.v --reference reference --candidate candidate --out results/lfsr64`

### Ponovno provjeri certifikat neovisnim algebarskim programom
`python3 apps/circuitcheck/verify_certificate.py results/lfsr64`

Za vlastiti Verilog: postavi dva modula s istim imenima i širinama ulaznih i izlaznih portova u jednu ili više RTL datoteka, a zatim odaberi njihove nazive parametrima `--reference` i `--candidate`. Original se ne mijenja. Koristi `--rtl file1.v file2.v` za više izvornih datoteka.

## Kako funkcionira

1. Yosys učitava RTL, spušta hijerarhiju i izveze kombinacijsku mrežu logičkih vrata kao JSON.
2. DRNAS zapisuje izlaze kao **egzaktne algebarske normalne oblike (ANF)** nad GF(2), sa zakonima XOR = zbrajanje, AND = množenje, OR = a+b+ab i x²=x.
3. Identical output ANFs give `EQUIVALENT_NETLIST`. A difference yields `DIFFERENT_NETLIST` and a concrete input assignment, independently checked on the gate network. Unsupported gates, too many polynomial terms, cycles or X/Z produce `UNKNOWN_UNSUPPORTED`.
4. `verify_certificate.py` is separately written, recomputes the output ANFs from the exact netlist JSON, validates SHA-256, compares every output polynomial and bit-evaluates counterexamples.

## Dokazna granica

This is an exact, replayable **proof over a synthesized, two-state combinational Yosys netlist**, conditional on Yosys preserving the semantics of the input RTL. It is NOT an independent original-Verilog semantics certificate, DRAT/LRAT/VeriPB proof, formal hardware signoff, or a generalized SAT speedup. No result is inferred when there is unsupported logic.

Exit codes of `circuitcheck.py`: 0 proved equivalent, 10 demonstrated difference, 2 UNKNOWN. Only `EQUIVALENT_NETLIST` or `DIFFERENT_NETLIST` can yield accepted independent replays. The `certificate.json`, `interface.json` and `netlist.json` are preserved in the output folder, along with `report.json` and `yosys.log`.

## Primjeri

`generate_examples.py` produces actual CRC-32/LFSR serial-versus-parallel implementations; Gray code round-trip; AND logic; intentional fault controls; and one sequential negative control. CI compares the outputs against frozen expectations and runs the separate verifier. A deliberately modified certificate must be rejected.

## Plan

Standard certificates / independent RTL frontend audit, real third-party hardware benchmarks and robust end-to-end comparisons with open-source hardware verification suites remain future work.
