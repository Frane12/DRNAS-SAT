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

## CORE-OP7: contextual rule utility (experimental, opt-in)

Use python3 core/run.py input.sop new.cert --rule-memory rules.txt --rule-feedback. A separate rules.txt.utility.json stores counts of isolated replay attempts, structural matches, independently accepted proofs produced by replay, and cumulative measured replay cost (microseconds). Coarse label-free contexts distinguish diagonal/mixed and three input-size buckets. Each eligible run selects one known rule; untried rules are explored, otherwise a smoothed proof-success/cost score ranks them, with periodic exploration every fifth prior attempt. Native replay remains bounded and ordinary adaptive decomposition is still available if replay fails. A fallback proof does not earn replay credit. The score measures observed replay success, not causal advantage versus a cold baseline; no claim of speedup or cross-domain learning. Rule schemas are not deleted; utility only changes scheduling, and statistics are never accepted as evidence. Sidecar writes are locked and atomic, invalid statistics are ignored with an error, and no-feedback mode leaves the sidecar untouched. CNF defaults unchanged. Run python3 core/rule_utility_tests.py. Tests include two identical inputs with different selected rules, no-credit fallback, context isolation, corrupted statistics, and negative claims. Full CI results pending confirmation.

## YM11: exact spectral bracketing without a supplied vacuum (experimental)

Input p op interval-gap N GAMMA followed by a rational real symmetric matrix (N<=24). Native exact congruence inertia and rational bisection discover U0 and L1 with at least one eigenvalue <= U0 and at most one eigenvalue < L1; L1-U0 >= GAMMA >0 proves a simple ground state and the requested gap. Independent auditor computes characteristic coefficients and counts sign variations of the real-rooted det(I+t(H-cut I)) polynomial, including its degree to count zero eigenvalues. Neither the ground vector nor its exact energy is required. Up to 48 iterations, existing wall budget; a failed proof is UNKNOWN, not a counterexample. Degenerate ground spaces are not handled by this task. Test suite includes entangled two-spin matrices, irrational energies, and finite SU(2) one-loop truncations at N=4,8,12. No tail estimate or infinite-volume/continuum claim from these truncations. Run python3 core/interval_gap_tests.py. CI pending.

## YM12 — infinite rotor-index Schur comparison (experimental)

Input: p op rotor-gap D N GAMMA K C (D=1 or 2, head cutoff N=2..4, rational parameters, C=0 for D=1). Defines an infinite operator on l2(N0^D), diagonal sum j(j+2), axial hopping -K and simultaneous (1,1) hopping -C for D=2. This is a coupled rotor-index toy model, not a full shared-link SU(2) gauge Hamiltonian. The diagonal has compact resolvent and the bounded hopping has norm at most 2(D|K|+|C|); hence the full operator is self-adjoint on the diagonal domain and has compact resolvent. The omitted tail satisfies T >= tau I, tau=N(N+2)-2(D|K|+|C|). For cut l<tau the Schur complement is bounded below by A-lI-BB^T/(tau-l), with B the exact head-tail coupling. At most one negative eigenvalue of this matrix implies E1>=l. Rayleigh-Ritz gives E0<=u when the finite head has at least one eigenvalue <=u. Native exact rational bisection seeks l-u>=GAMMA; independent verifier reconstructs the matrices using coordinate differences and characteristic coefficient sign counts. No supplied vacuum, no uncontrolled truncation. This is not volume-uniform or a continuum mass-gap proof. Nine prepared CI cases, seven positive and two impossible targets, with tamper checks. Run python3 core/rotor_gap_tests.py. Integrated CI status not yet confirmed.

## YM13 — full finite-graph pure SU(2) Hamiltonian (experimental)

Input p op gauge-gap N M P ALPHA GAMMA, then M unordered vertex pairs (0-based) for a simple graph, then P rows LENGTH K V0 ... V(LENGTH-1) specifying distinct simple cycle boundaries and their real rational magnetic couplings. N<=256, M<=1024, P<=512. Hamiltonian H=alpha sum_e C_e - sum_p k_p Tr(U_p), Haar-normalized physical gauge-invariant Hilbert space, no matter, no electric representation cutoff. A nontrivial spin network cannot have a vertex with just one nonzero-spin incident link (no invariant vector in a nontrivial irreducible SU(2) representation). Its support contains a cycle; hence the first electric excitation costs at least 3 alpha girth(G)/4. Equality is attained by the fundamental Wilson character on a shortest cycle. The electric vacuum is the constant function. Min-max on its orthogonal complement yields E1(H)>=3 alpha girth/4 - 2 sum_p |k_p|. For any loop p, the orthonormal functions 1 and W_p=Tr(U_p) give a trial vector 1+(k_p/e_p)W_p, with e_p=3 alpha length(p)/4. The vacuum/loop matrix element is -k_p by Haar orthogonality and edge-center parity; all diagonal magnetic elements on these two functions vanish (distinct loop edge sets). Rayleigh-Ritz gives E0<=-k_p^2 e_p/(e_p^2+k_p^2); also E0<=0. CORE computes the strongest of these trial bounds and certifies the difference when positive and at least GAMMA. Independent verifier derives girth via edge deletion and exact rational arithmetic. Finite graph compact resolvent follows from the electric Laplacian and bounded magnetic perturbation. This bound deteriorates with total magnetic weight, is NOT uniform in volume at fixed nonzero coupling, and does not address continuum construction. The formula is standard min-max/representation reasoning, not a claimed novel theorem. Thirteen prepared tests; integrated CI not yet confirmed. Run python3 core/gauge_gap_tests.py.

## YM14 — qualitative volume-uniform SU(2) stability

ATLAS theorem application schema: [derivation and limitations](YM14_ATLAS_STABILITY.md). Input p op gauge-stability D ALPHA for periodic hypercubic spatial lattices, D=2..4, ALPHA>0. Output THEOREM_APPLIED, not numerical PROVED: native and independent auditor compute local block gap and normalized perturbation coefficient for Yarotsky's existing stability theorem. The result establishes a volume-independent positive gap for sufficiently small magnetic coupling, without providing a numeric threshold or a continuum claim. No separate ATLAS executable or proof-assistant formalization is involved. Tests: python3 core/gauge_stability_tests.py. CI pending.

## YM15 — ATLAS30 / CORE exact spectral decimation (experimental)

ATLAS30 is used as an actual CNF planner at pinned commit 283af5a80491d31b08250c62e91a8118cc8c20bc, not as a quantum solver. The adapter selects up to 12 high-diagonal candidates, encodes incompatible matrix-coupled pairs as clauses and requests up to four selected indices. It independently checks each returned SAT assignment against the planning CNF. Failure to find a plan is UNKNOWN; an ATLAS UNSAT report is not used as a mathematical certificate. Native CORE input p op decimation-gap N GAMMA K I0 ... I(K-1) followed by N rows of rational matrix entries checks that the eliminated principal block D is diagonal, positive after subtracting the cut, and applies exact Schur congruence at two rational spectral cuts. The independent Python verifier checks the original full-matrix characteristic coefficients, not the reduced block. A certificate proves a finite simple-ground gap at least GAMMA. The two executables are run serially, with no external CDCL fallback. Separate workflow core-ym15.yml uses the pinned ATLAS source. Tests cover permuted matrices, rational couplings, degenerate ground and too-large gap targets, and invalid elimination plans. This is a proof-preserving finite spectral projection, not an actual spatial renormalization flow, not a full SU(2) lattice construction and not a continuum mass gap. CI results must be checked separately.

## YM16 — successive ATLAS / CORE spectral projection (experimental)

ATLAS30 at the same pinned source commit is called on successive symbolic fill graphs. The two smallest diagonal states are protected; each proposed independent layer is checked against the original planning CNF, then fill edges between remaining neighbors are added. CORE input p op multiscale-gap N GAMMA S followed by S rows K indices..., then the symmetric rational matrix, executes successive exact Schur complements at each spectral cut; positive pivots and layer diagonality are checked at every step. A Gershgorin lower bound of the entire eliminated block limits admissible cuts. Independent verification uses the original full characteristic polynomial, positivity of the full eliminated block, and symbolic graph fill. No approximation is introduced (zero arithmetic truncation error); the effective matrix depends on the spectral cut, is not an energy-independent Hamiltonian, and the layers are algebraic, not physical lattice spacings. N<=24. No continuum or volume-uniform claim, no CDCL fallback. Run python3 core/atlas_multiscale_tests.py PATH_TO_PINNED_ATLAS. Five prepared tests; CI results separate.

## YM17 — exact spatial gauge blocking (experimental)

See [analytic equivalence and limitations](YM17_GAUGE_BLOCK.md). Actual pinned ATLAS30 proposes safe degree-two vertex sets, the structural auditor reconstructs original weighted paths and Wilson loops, and the native CORE independently certifies the original graph gap. Run python3 core/atlas_gauge_block_tests.py PATH_TO_PINNED_ATLAS. This is an exact graph subdivision equivalence, not a continuum limit. Four prepared controls; CI status separate.

## YM18 — maximal-tree SU(2) coordinates (experimental)

[Analytic transformation and scope](YM18_TREE_GAUGE.md). Pinned ATLAS30 chooses a rooted spanning tree using CNF parent choices; the independent structural auditor reconstructs all Wilson words and signed electric derivation rows, including mixed terms. CORE independently certifies the original gauge-gap bound. Run python3 core/tree_gauge_tests.py PATH_TO_PINNED_ATLAS. The gauge coordinates are eliminated exactly, but this is not physical coarse-graining or a new continuum gap result. CI pending.
