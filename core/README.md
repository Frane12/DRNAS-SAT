# DRNAS CORE 0.1.2

**Glavni i zadani automat za daljnji rad na DRNAS SAT-u.** Objavljena verzija nalazi se u `core/` na grani `main`. Daljnji razvoj, poboljšanja i benchmarkovi nastavljaju se u istom direktoriju na stalnoj grani `development/drnas-core`, uz verzije i dnevnik promjena. FUSION, GENERAL, UNIFIED i ATLAS ostaju izvori metoda i povijesnih rezultata.

CORE je jedan izvorni C++ program. Metode rade redom na jednom CPU-u, unutar zajedničkog vremenskog budžeta. Zajednički zapis sadrži izvornu formulu i provjerene RUP posljedice. Metode ne dijele nepotpunu rekonstrukciju eliminiranih varijabli. Unutar GENERAL jezgre nastavlja se prijenos između projekcije, tablica i simboličkog zaključivanja.

## Pokretanje

Linux, C++20 compiler, OpenSSL development headers/library (`libssl-dev`) i Python 3; osnovni automat ne zahtijeva druge SAT solvere. OpenSSL služi samo za vezanje strukturnog certifikata uz SHA256 izvorne formule.

```bash
bash core/build.sh
python3 core/tests.py
python3 core/run.py formula.cnf dokaz.cert --seconds 5
```

`run.py` je javni ulaz: pokreće automat, nameće vanjski timeout i zasebno provjerava dokaz. Vraća JSON sa statusom, metodom, vrstom dokaza, vremenom rješavanja i vremenom provjere. Provjera ima zaseban budžet od pet sekundi (`--audit-seconds`). Postojeći put dokaza se ne prepisuje. `UNKNOWN`, `TIMEOUT` i `AUDIT_LIMIT` nisu riješeni slučajevi.

Izravni native CLI: `core/bin/drnas-core formula.cnf dokaz.cert 5`. Izlazni kodovi: 10 SAT, 20 UNSAT s dokazom, 0 neriješeno, 2 pogreška. Izlazni kod 20 sam po sebi nije neovisna potvrda; za prihvaćen rezultat koristi `run.py` ili `verify.py`.

## Što je objedinjeno

| Izvor | Uloga u CORE-u | Provjera i ograničenja |
|---|---|---|
| AFFINE23 | Rekonstrukcija domena GF(3), afini sklopovi i konstrukcija modela | Samo SAT; model se provjerava na cijeloj izvornoj formuli. Circuit metoda zasad traži određeni topološki raspored oznaka. |
| WORDLIFT23 | Rekonstrukcija operacija nad riječima iz vrata: pomaci, XOR i zbrajanje | Predlaže SAT modele; provjera na izvornom CNF-u ostaje obavezna. Naslijeđen iz source-pinned testa 23/23 prema prethodnih 14/23. |
| UNIFIED3 | Povezivanje lokalnih relacija, probe, uvjetni zaključci, prilagodljiva projekcija i otkrivanje lokalnih posljedica | Zajednički RUP zapis; neproduktivne petlje imaju granice. |
| PCMAX / MATH4 | Hallov manjak kapaciteta s promijenjenim oznakama i polaritetima, GF(2) s početnim jedinicama | Neovisni izvorni checkeri i SHA256 veze; posebno označeni strukturni certifikati. |
| UNIFIED8 | Tablice lokalnih faktora, projekcija na granicu i presjek s globalno dokazanim ograničenjima | Samo potpune tablice; svaki preneseni zaključak ima RUP trag. |
| FUSION1 / GENERAL5 | Komponente, GF(2), detekcija vrata, eliminacija, ograničena razgradnja na slučajeve, konstrukcija i popravak modela | Rekonstrukcija modela do izvornog CNF-a; DRUP ili posebno označen dokaz kapaciteta. |
| GENERAL11/12 preko GENERAL14 `contract` | Nastavak projekcije, točan prijenos faktora, lokalni simbolički zaključci natrag u projekciju, tablice i ROBDD | RUP ili RUP + neovisno simboličko ponavljanje. |
| GENERAL13/14 | Odgođena lokalna memorija i reaktivacija | Dostupno kroz `--mode memory`; nije zadano jer dosadašnji ukupni rezultat nije bolji od kontrola. Nema pamćenja između formula. |

`--mode no-share` isključuje vanjski UNIFIED sloj za dijagnostiku. Ne isključuje unutarnji prijenos GENERAL metode i nije izolirana ablacija jedne pojedinačne promjene.

Starije metode uključene su kroz njihove nasljednike, a ne kao duplikati koji ponovno troše cijeli budžet. U5–U7 heuristike naučene politike nisu uključene kao zadani put: zabilježene novosti u zaključcima nisu pokazale stabilan dobitak u broju riješenih formula. U8 lokalna faktorizacija dodana je nakon njegova provjerenog dobitka 45/50 prema 44/50, uz 0/8 oporavljenih starih neuspjeha. To je uzak eksperimentalni dokaz, ne opća prednost.

## Dokazni ugovor

- SAT: odvojeni Python checker provjerava potpunu dodjelu na izvornom CNF-u.
- DRUP: odvojeni C++ checker ponovno izvodi svaku adiciju propagacijom. Završetak mora biti prazna klauzula.
- `RUP+SYMBOLIC`: checker prvo provjerava RUP prefiks i pripadnost rezidualnih klauzula dokazanom zapisu. Neovisni Python ROBDD auditor zatim ponovno izračunava eliminaciju. **To nije standardni DRAT/LRAT certifikat.**
- `CAPACITY`: zasebni Python checker provjerava izvor svake klauzule, disjunktne zahtjeve i potpune mutex klike te strogu nejednakost zahtjeva i kapaciteta. **To nije DRAT/LRAT.**
- `HALL` / `GF2`: odvojeni checkeri ponovno potvrđuju izvorne zahtjeve i mutex klike, odnosno cijele paritetne kodove i početnu propagaciju. Provjeravaju i SHA256 izvornog CNF-a. **To nisu DRAT/LRAT certifikati.**

Dokazni zapis i aktivne klauzule odvojeni su. Pomoćni koraci ostaju dostupni provjeri, a među metodama se prenose izabrane dokazane posljedice. Time se izbjegava nepotrebno pretraživanje tisuća pomoćnih klauzula.

Nema CDCL-a ni poziva Kissatu/CaDiCaLu u rješavanju CORE-a. Postoje ograničena razgradnja na slučajeve, lokalna enumeracija i simbolička eliminacija; ne tvrdimo da nema nikakve pretrage ili da je opći SAT postao polinoman. Jedan proces obrađuje jednu formulu; naslijeđeni kernel s globalnim stanjem nije API za paralelna ili uzastopna rješavanja u istom procesu.

## Mjerenje i nastavak razvoja

```bash
bash core/prepare_references.sh
python3 core/benchmark.py generate --out core/results/novi-test
python3 core/benchmark.py run --out core/results/novi-test
```

Reference su vezane uz točne commitove. Benchmark radi serijski, s jednim logičkim CPU-om po solveru, rotira redoslijed i provjerava odgovore. Prospektivni panel ima 50 novih instanci iz 10 poznatih obitelji; nije test 10 posve neviđenih obitelji. Odvojeno ponavlja 38 različitih arhiviranih primjera. Budžet rješavanja je 1 s, tolerancija zida 50 ms, vanjski prekid nakon 100 ms tolerancije. Audit je zaseban i ograničen. To je pilot s jednim ponavljanjem, a ne završni natjecateljski benchmark.

Rezultati početne integracije i sve regresije zapisani su u [VALIDATION.md](VALIDATION.md). Sljedeće promjene trebaju širiti pokrivenost unutar CORE-a, a raspodjelu budžeta vrednovati na novom zamrznutom skupu. Dodavanje svih metoda ne jamči da će svaka formula ostati riješena pri istom kratkom budžetu.

Objedinjeni CORE zasebno je ponovio i **23/23 javne izvorne WORDLIFT formule**, s neovisno provjerenim modelima. To je poznat, odabran skup iz dvije obitelji. Ponoviti ga možeš naredbama `python3 core/public_replay.py download` i `python3 core/public_replay.py run`; podrijetlo ulaza i prihvaćeni modeli vezani su u izvještaju.

Točno podrijetlo izvora: [provenance.json](provenance.json). Uvozi su sačuvani bez izmjena; integracija je u `core.cpp`. Datoteke iz drugih solvera služe samo kao razvojne reference i preuzimaju se u zanemareni direktorij `results/`.

## Experimental operator domain (CORE-OP1)

The same native CORE binary and public run.py accept rational real-symmetric matrices (dimension 1–24). Requires Boost headers (libboost-dev) in addition to the existing requirements. CNF mode and its certificate formats remain unchanged. Operator tasks use the default mode; output code 30 is only a proposed result until the independent verifier accepts it as PROVED.

Format: p op psd N / p op pd N / p op commute N / p op gap N E gamma / p op auto-gap N gamma, followed by N rows of N rational entries, and a second matrix for commute. Integers or fractions with positive denominator; whitespace separated. Example:

```
p op auto-gap 2 2
3 -1
-1 3
```

```bash
bash core/build.sh
python3 core/run.py example.op proof.cert --seconds 5 --audit-seconds 15
python3 core/operator_tests.py
```

Exact congruence checks PSD/PD; gap checks A=H-EI PSD with nonempty kernel and excited space, then A^2-gamma*A PSD. auto-gap proposes rational E from bounded candidates, never trusts the heuristic. Independent Python verification uses characteristic coefficients and source SHA256. Nonpositive, unsupported or unproven claims return UNKNOWN (no negative witness yet). This is a finite real-matrix pilot, not general symbolic operator algebra, not a proof of Yang–Mills, and not a CNF proof format. The small SAT projector test is explicitly exponential; scalable CNF transfer requires local symbolic operators and source-bound certificates. No CDCL. No new independent solver.

## CORE-OP2: sparse symbolic operators (experimental)

Same executable and run.py; input p sop lower N M TARGET followed by M lines COEFF PAULI_WORD (N chars from IXYZ). Or p sop commute N M K followed by M and K terms for two operators. N <= 256, at most 4096 terms per sum, exact real rational coefficients. Terms are Hermitian Pauli tensor products, with complex phases handled algebraically. Example:

```
p sop lower 1 4 0
2 I
1 X
1 Y
1 Z
```

The native engine merges duplicate terms and discovers a partition into pairwise anticommuting groups and diagonal local factors (up to 16 active variables). It combines certified local lower bounds; anticommuting groups have square equal to sum of squared coefficients times identity. The separate Python verifier reconstructs the source by SHA256, checks all group indices, uses independent symplectic commutators, and exactly checks bounds. Return code 31 is accepted only as PROVED after audit. UNKNOWN is not a refutation. No dense matrix, no CDCL, but bounded local enumeration is used. Tests include Boolean clause-projector lifts and frustrated triangles. These are synthetic symbolic inputs, not direct DIMACS certificates; CNF solver behavior is unchanged. This is not a continuum or full SU(2) lattice solver. Next step: source-bound CNF projector rules, adaptive repartition and gauge-invariant symbolic operators.

Run: python3 core/symbolic_tests.py

## CORE-OP3: adaptive operator decomposition (experimental)

For p sop lower the engine first tries its previous partition, then, if insufficient, up to six candidate partitions using different ordering and commutation priorities. Mixed anticommuting groups may include Z terms; commuting groups of up to ten terms are evaluated in their joint eigenbasis with signed Pauli dependencies. The strongest completed lower bound is kept; search stops once the requested bound is proved, not necessarily at the mathematical optimum. Telemetry records partitions_tried and best_lower. Time slices limit attempts. The p sop lower-fixed input selects the previous partition for paired controls (same operator and target). The independent auditor checks commuting dependencies via binary pivot reduction, independently of the native product table. Two paired synthetic controls cover mixed X/Z and commuting XX/YY/ZZ with sign dependency; a negative sign-control is also included. No claims of learned new mathematics, general SU(2) capability, scalable original CNF proof, or benchmark gains until CI passes. The search policies remain programmed, not learned.

## CORE-OP4: reusable rule memory (experimental, opt-in)

Use python3 core/run.py input.sop new.cert --rule-memory rules.txt. Only independently PROVED symbolic certificates are mined: anticommuting norm-improving groups A2–A10 and signed commuting identities C3+/C3- (P_i P_j = +/- P_k) from checked groups. Templates contain neither source variable labels, coefficients, nor answers. On a subsequent source, the native engine attempts to match these identities before other partitions, recalculates coefficients and the bound and emits the existing source-bound certificate. The verifier checks the actual new source and partition, never trusting memory. A missing rule is not a contradiction. The file is local, explicitly selected, atomically updated and locked; no default persistence. Metrics: rules_added, memory_matches, memory_proved, partitions_tried. This is limited theorem-schema extraction using programmed algebraic families, not unrestricted theorem invention. No direct CNF proof transfer yet. Tests exercise cross-basis/changed coefficients, opposite sign, and a poisoned memory hint. CI results are not presumed.

## CORE-OP5: composition of verified rule schemas (experimental)

Two commuting signed three-word identities in an independently verified partition, sharing exactly one word, are composed by cancellation into a four-word identity C4+ or C4-. The auditor derives the sign from both identities and records composed_rules; no source variable names or coefficients are retained. Native replay matches two disjoint pairs with equal unsigned product and checks every cross-pair commutator and the product sign. The intermediate word is not required in the new input. The existing exact commuting-block verifier checks the complete partition from the new source, independently of stored hints. Pair scan capped at 50,000 and 16 cached pairs per product, under the existing solve budget. This is bounded composition of known algebraic identities, not unrestricted theorem discovery. Eight tests cover cold/warm transfer, sign changes, missing intermediate, and false claims. The earlier OP4 benchmark now passes the explicit rule-memory option to run.py rather than relying on an environment variable cleared by the public wrapper. Run python3 core/composed_rule_tests.py. No main-branch change or claimed CI result until verified.

## CORE-OP6: recursive signed-relation closure (experimental)

Within each independently audited commuting group, seed signed three-word identities and repeatedly combine relations sharing exactly one involution using symmetric difference and sign multiplication. Newly derived relations may participate in the next layer. Limits: up to five closure layers, up to 128 retained relations per block (initial triples are mined only for groups of at most 32 terms), persistent signed schemas C3..C8 plus A2..A10. The audit emits closure_depth, closure_steps and bounded local rule_derivations with parent term indices and signs. Persist only schema size/sign, not inputs or answers. Native replay searches bounded commuting neighborhoods of at most ten words and checks signed subset products; up to 50,000 subset scans and neighborhood checks under the solve budget. Every replay still receives independent exact certification. No unrestricted theorem invention, cross-domain theorem transfer, or performance claim yet. Tests: four-triple training chain, fresh endpoint-only five/six-word inputs, cold/warm/fixed and false-bound controls. Run python3 core/recursive_rule_tests.py. No main changes.
