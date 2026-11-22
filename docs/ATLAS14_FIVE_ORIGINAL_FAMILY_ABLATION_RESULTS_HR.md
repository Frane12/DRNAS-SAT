# DRNAS SAT — ATLAS14: originalna petoizvorna ablacija modula, provjera standardnih dokaza

**Datum:** 22. studenoga 2026.  
**Izvršen GitHub Actions:** https://github.com/Frane12/DRNAS-SAT/actions/runs/45015109178 — **SUCCESS**  
**Eksperimentalna grana:** `experiment/atlas14-original-five-family-ablation-20261122`  
**Status:** 30/30 unaprijed planiranih pokušaja evidentirano; bez prihvaćenog pogrešnog SAT/UNSAT; `main` nije diran.

## Hipoteza koju smo zapravo provjeravali

ATLAS13 je na **konstruiranim** primjerima pokazao pravi izvorno dokaziv prijenos jedne, dvije ili tri nove RUP zabrane iz grafa implikacija u Hallov kapacitetni zaključivač. ATLAS14 pokušava isti **zamrznuti kod** na pet originalnih objavljenih CNF datoteka iz četiri domene, ne birajući ih prema rezultatima novoga audita.

To je **retrospektivni pilot** (izvori već postoje u DRNAS repozitoriju i ranije su analizirani, po jedno ponavljanje), ne novi blind SAT Competition uzorak. Otvoreno znamo da na istim originalima postoje stariji pohranjeni standardni dokazi — oni nisu predani nijednom novom algoritamskom kraku.

## Prethodno zamrznuti originali

Izvori su zapisani prije mjerenja u `research/atlas14_five/prespec.json`, a `freeze.py` je potvrdio njihov sirovi SHA-256 i točan DIMACS broj klauzula. Povijesni stored proof se hashira zasebno i ne koristi pri dokaznoj pretrazi.

| Original | Problemska domena | Izvor |
|---|---|---|
| `graph-k11` | Grafovsko bojanje | `evidence/graph-k11/original.cnf` |
| `petersen-ipg` | Petersenova konfiguracija | `evidence/ipg7b-petersen/original.cnf` |
| `pcmax-m00` | PCMAX scheduling | `evidence/pcmax-weighted2/00/original.cnf` |
| `pcmax-m05` | PCMAX scheduling | `evidence/pcmax-weighted2/05/original.cnf` |
| `xor-grid5` | Mješovita XOR mreža | `evidence/xor234-grid5/original.cnf` |

## Strogi protokol: šest ruku

- `GRAPH_ONLY`: izvorno potvrđen k+1 grafovski klik / k boja uz izvorni VeriPB.
- `HALL_ONLY`: source-PHP/kapacitetni izvorni mutex izvod uz VeriPB.
- `EXCHANGE_ONLY`: izvorni 2-SAT graf implikacija → RUP dokazane nove zabranjene klauzule → Hall → vanjski VeriPB na **neizmijenjenom** originalu. Metoda ne dobiva poznatu strukturu iz naziva formule.
- `BRIDGE_FULL`: serijski GRAPH → HALL → EXCHANGE, svi na istom ulazu i uz zajednički limit. Nije paralelni portfelj.
- **Kissat 4.0.4**, upstream commit `8af8e56f174b778aef3aa45af9f739b2a5f492c2` + neovisni DRAT-trim.
- **CaDiCaL 2.1.3**, upstream commit `f13d74439a5b5c963ac5b02d05ce93a8098018b8` + neovisni DRAT-trim.

Jedna logička CPU jezgra, serijski procesi, **12 s E2E**, maksimalna pojedinačna proof datoteka **128 MiB**, memorija **4 GiB**, strogi PAR2 neuspjeha **24 s**. Kompilacija i pribavljanje alata nisu dio E2E. Svaki `UNSAT` prihvaćen je isključivo nakon standardne vanjske verifikacije točnog izvornog CNF-a. `UNKNOWN` i resource-limit slučajevi nisu pripisani kao SAT/UNSAT.

## Rezultati: svi pokušaji, bez skrivanja UNKNOWN

| Ruka | Verificiranih UNSAT / 5 | Ukupni strogi PAR2 |
|---|---:|---:|
| `GRAPH_ONLY` | **1/5** | 96,096069 s |
| `HALL_ONLY` | **0/5** | 120,000000 s |
| `EXCHANGE_ONLY` | **0/5** | 120,000000 s |
| `BRIDGE_FULL` | **1/5** | 96,094910 s |
| Kissat 4.0.4 | **2/5** | 74,420256 s |
| CaDiCaL 2.1.3 | **1/5** | 96,074497 s |

### Po izvornom problemu

| Original | GRAPH | HALL | EXCHANGE | BRIDGE_FULL | Kissat | CaDiCaL |
|---|---|---|---|---|---|---|
| `graph-k11` | VERIFIED | UNKNOWN | UNKNOWN | VERIFIED | VERIFIED | TIMEOUT |
| `petersen-ipg` | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | VERIFIED | VERIFIED |
| `pcmax-m00` | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | TIMEOUT | TIMEOUT |
| `pcmax-m05` | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | TIMEOUT | TIMEOUT |
| `xor-grid5` | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | RESOURCE_LIMIT | RESOURCE_LIMIT |

Na `xor-grid5` oba referentna solverska procesa prekinuta su zbog ograničenja **128 MiB proof datoteke** (`UNKNOWN_RESOURCE_LIMIT`), a ne vremenskog timeouta. Drugi označeni TIMEOUT nisu dokaz da referentni solveri s većim limitima ne bi riješili instance.

**Nema nijednog potvrđenog originalnog UNSAT koji je `EXCHANGE_ONLY` riješio, a `GRAPH_ONLY` i `HALL_ONLY` zasebno nisu.** Proširenje pokrivenosti s ATLAS13 kontroliranih konstrukcija **nije dokazano** u ATLAS14 petoizvornom uzorku.

Na graf-k11 razlika je praktički zanemariva: `GRAPH_ONLY` 0,096069 s, `BRIDGE_FULL` 0,094910 s (u ovom pojedinačnom pokretanju); oba standardno verificiraju isti izvorni grafovski UNSAT koji je već poznat. To ne predstavlja novu dobit od razmjene činjenica.

## Odvojena provjera već pohranjenih, starijih znanstvenih rezultata

Posebno, tek **nakon** svih 30 novog algoritamskog pokušaja, GitHub je vanjskim VeriPB v3.0.2 neovisno ponovno provjerio već spremljeni dokaz svake od pet originalnih formula.

| Original | Stariji originalni PBP | Neovisni VeriPB audit |
|---|---:|---|
| graph-k11 | 5.841 B | **ACCEPTED** |
| petersen-ipg | 16.663 B | **ACCEPTED** |
| pcmax-m00 | 181.816 B | **ACCEPTED** |
| pcmax-m05 | 557.597 B | **ACCEPTED** |
| xor-grid5 | 165.156 B | **ACCEPTED** |

**5/5 povijesnih certifikata je valjano**, ali to nije `5/5` novog BRIDGE_FULL algoritma. Razlika je centralni nalaz ATLAS14: različiti stari dokazni moduli već znaju riješiti te formule, ali ova nova zajednička arhitektura još ne rekonstruira njihove izvorno dokazive primitive (npr. PCMAX BDD kapacitete, Petersenovo IPG kodiranje ili mješoviti XOR).

## Što dalje i zašto?

**ATLAS15 — zajednički dokazni jezik činjenica**. Umjesto još jednog uskog parsera treba normirati:
- `ALO/EO/AMO` činjenice s točnim original-source RUP ili drugim standardnim provjerljivim premisama i mapom pomoćnih varijabli;
- `GRAPH_MUTEX` zabrane, uključujući dokazive izvorne implikacijske putanje;
- `XOR_RELATION` činjenice s GF(2) izvornim redovima i proof-carrying prijelazima;
- `CAPACITY_BOUND` iz BDD, Hall i PCMAX, uz standardno provjerljive izvode i identifikatore izvornih literala.

Proizvodnja jedne stvarne *nove* međumodulske leme koja izvodi dokaz u mješovitom javnom originalu mora biti odvojena od općeg fallbacka postojećih modula. Budući testovi moraju imati ON/OFF izolaciju i nezavisne izvore koji nisu izabrani po rezultatu.

## Reprodukcija

```bash
python3 research/atlas14_five/freeze.py
# nakon SHA-pinned Kissat/CaDiCaL/DRAT-trim i VeriPB 3.0.2:
python3 research/atlas14_five/benchmark.py
```

Workflow `.github/workflows/atlas14-five-original-ablation.yml`, [run 45015109178](https://github.com/Frane12/DRNAS-SAT/actions/runs/45015109178).

Arhiv `DRNAS-ATLAS14-FIVE-ORIGINAL-SIX-ARM-PILOT` sadrži sve rezultate, source manifest SHA, 30 zasebnih trial logova, stare dokazne provjere, vanjske proof checkere i svaki uspješni originalni dokaz. Ograničenje: samo jedno ponavljanje, pet već korištenih izvornih datoteka, četiri šire domene; bez statističke tvrdnje o performansama cijele klase SAT-a.
