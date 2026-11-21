# DRNAS SAT — GRAPH → PCMAX/Hall: dokazno utemeljena komunikacija (BRIDGE1)

**Datum:** 21. studenoga 2026.  
**Grana:** `experiment/graph-pcmax-proof-bridge1-20261121`, bez izmjena `main`.  
**Audit:** https://github.com/Frane12/DRNAS-SAT/actions/runs/44943526319  
**Rezultat:** PASS, **9/9 original-source VeriPB 3.0.2 VERIFIED UNSAT** na tri konstruirane formule × tri ponavljanja.

## Motivacija i kompatibilnost

- **GRAPH:** iz izvornih pozitivnih klauzula bojanja (vertex-color ALO) i negativnih klauzula susjedstva (isti color AMO) otkriva povezanu kliku od `k` vrhova, svaki s `k` dostupnih boja. Ovo samo po sebi **nije** UNSAT; kompletan graf `K_k` moguće je obojiti s `k` boja.
- **PCMAX/kapacitet:** dodatne pozitivne klauzule `OR_{j!=i} x[j,color]` za svaki `i` znače da barem **dva** vrha moraju koristiti odabranu boju. PCMAX quota modul bez dokaznog informacije o grafovskim zabranama nema opravdanu kapacitetnu granicu.
- **Razmjena:** GRAPH šalje `aligned_vertices`, `source_sha256` i `capacity_per_color = 1`. Sadržaj je samo `SOURCE_FACTS_ONLY_NO_SAT_VERDICT` — nikad samostalna tvrdnja UNSAT. PCMAX/kapacitet sam ponovno provjerava sve potrebe iz **originalnih** CNF klauzula i nalazi dodatnu donju kvotu.
- **Zajednički zaključak:** dva potrebno > jedan moguć, `2 > 1`, te derivacija standardnog VeriPB cutting-planes dokaza.
- **Nije** automatska integracija postojećih C++ produkcijskih modula. Eksperiment je dvofazni Python adapter sa zasebnim CLI procesima i neovisnim source checkerom.

## Pojasnjenje dokaznog pravila

Za `k` međusobno susjednih vrhova, neka je `a_i` indikator da je vrh `i` dobio odabranu boju. Iz izvornih grafovskih AMO klauzula `~a_i OR ~a_j` za sve parove slijedi

\[
\sum_i a_i\le 1\qquad (\sum_i \neg a_i\ge k-1).
\]

Za svako `i` izvorna kvotna klauzula `OR_{j\ne i} a_j` implicira, nakon zbrajanja svih `k` takvih klauzula,

\[
(k-1)\sum_i a_i\ge k
\quad\Rightarrow\quad \sum_i a_i\ge2.
\]

Stoga je formula UNSAT. Obje strane izvode se cutting-planes operacijama od originalnih DIMACS klauzula; `veripb --cnf ORIGINAL.cnf PROOF.pbp` ih prihvaća.

## Ponovljena mjerenja (jedna CPU jezgra)

| CNF | Varijabli | Klauzula | Samostalni prethodni GRAPH i MATCH3 | Spojeni standardni VeriPB | Veličina dokaza | Vrijeme E2E po pokretanju |
|---|---:|---:|---|---:|---:|---|
| k=4 | 16 | 56 | UNKNOWN / UNKNOWN | **3/3** | 196 B | 0.0828–0.0839 s |
| k=6 | 36 | 192 | UNKNOWN / UNKNOWN | **3/3** | 301 B | 0.0847–0.0857 s |
| k=10 | 100 | 920 | UNKNOWN / UNKNOWN | **3/3** | 585 B | 0.0868–0.0889 s |

Ukupni medijan **0.084960 s**, najveće izmjereno **0.088947 s**. Mjere se izvorni GRAPH proces, zasebna provjera premise, PCMAX dokazni emitter i vanjski VeriPB, uključujući pokretanje svakog procesa, bez generiranja ulaznog CNF-a i CI pripreme.

Svi primjeri su **sintetički**, pripremljeni specifično za jedinstveni spoj grafovske gornje granice i dodatne kvote. Zbog male veličine nije dopušten zaključak o ubrzanju u odnosu na Kissat, niti se ovdje tvrdi neka nova matematička nejednakost.

## ABLACIJA i sigurnost

- **GRAPH-only:** sam graf `K_k` s `k` boja jest obojiv. Postojeći `graphclique` detektor na punim CNF-ovima, koji sadrže i kvotne klauzule, ispravno vraća UNKNOWN.
- **MATCH3/Hall-only:** postojeći prepoznavač ne može izvorno rekonstruirati ovaj miješani ALO/kvota zapis i vraća UNKNOWN.
- **Bridge OFF:** PCMAX prijamnik bez GRAPH poruke odbija proizvesti dokaz i vraća UNKNOWN.
- **Bridge ON:** prima poruku, original-source checker provjerava izvornu hash vezu, sve `k * binom(k,2)` negativne grafovske klauzule i `k` kvotnih klauzula; vanjski VeriPB prihvaća **9/9** UNSAT dokaza.
- **Zlonamjerno izmijenjene poruke:** 2/2 odbijene (krivi hash; neispravno izjednačavanje selektora).
- **SAT kontrole:** 3/3 bez lažnog UNSAT (`no_quota`, `drop_quota`, `drop_edge`), sa zadovoljavajućim modelima iz konstrukcije.
- **Dva originalna nepodržana CNF-a:** postojeći graf-k11 i PCMAX-m14 ostali UNKNOWN u ovom *specifičnom* mostu; imaju zasebne ranije prihvaćene dokaze i to nije njihovo pobijanje.

## Smisao za razvoj DRNAS SAT-a

Ovo **jest** dokazano zajedničko zaključivanje u uskoj kompatibilnoj obitelji: dokazana gornja granica GRAPH-a korištena je zajedno s odvojeno otkrivenim donjim zahtjevom PCMAX-a. Samostalni projektni detektori nisu riješili iste kombinirane ulaze, dok je novi dokazno provjerljiv most uspio.

**Još nije potvrđeno:** primjenjivost na širok uzorak stvarnih grafovskih/PCMAX kodiranja, performanse u istom C++ procesu, općeniti prospektivni uspjeh, ni prednost nad standardnim CDCL-om. Činjenica da stari detektori vraćaju UNKNOWN ne dokazuje da neki drugi monolitni solver ne bi brzo našao isti dokaz.

**Sljedeći korak:** izgraditi source-bound transport za stvarne *partial-color list* slučajeve i/ili kapacitetne BDD granice; napraviti paired ablation na neviđenim originalnim CNF-ovima, `GRAPH_ONLY / PCMAX_ONLY / BRIDGE_ON / BRIDGE_OFF / Kissat / CaDiCaL`, uz external proof checker i ukupni E2E cap. Sve do tada bez automatskog mergea u main.

### Reprodukcija

```bash
python3 research/graph_pcmax_bridge1/audit.py
```

Potrebni su Python 3, `taskset` i neovisno instalirani `veripb` 3.0.2.

- Producer i emitiranje VeriPB: [module_bridge.py](module_bridge.py)
- Neovisni izvorni checker: [source_check.py](source_check.py)
- Potpuni ponovljeni testovi: [audit.py](audit.py)
- GitHub workflow: [graph-pcmax-bridge1-audit.yml](../../.github/workflows/graph-pcmax-bridge1-audit.yml)
