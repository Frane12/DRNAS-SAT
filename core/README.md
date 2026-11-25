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

## Eksperiment s izravnim tabličnim certifikatima (CNF)

`--mode table-first` prvo pokušava prenijeti lokalnu posljedicu iz potpune tablice
izvornih premisa. `--mode table-fallback` isti prijenos iskušava nakon neuspjele
konstrukcije uobičajenog RUP traga. Provjerivač ponovno računa tablicu i tek
potom prihvaća klauzalni ili simbolički završetak dokaza.
[Protokol, ograničenja i rezultati uparenog testa](experiments/direct-table/README.md).

Na istoj eksperimentalnoj grani `--mode table-rank` daje jednoj dokazanoj
tabličnoj klauzuli prednost prije projekcije i popravka modela. Procjena se
računa iz pojavljivanja literala u izvornom CNF-u. Kontrola
`--mode table-pick-first` na isto mjesto stavlja prvi raspoloživi zaključak.
[Pravilo, kontrole i rezultati na novim formulama](experiments/lemma-priority/README.md).
