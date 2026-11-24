# DRNAS REAL4 — ZAVRŠNA ANALIZA SLIJEPROG TESTA (24. 11. 2026.)

**Istraživanje:** Frane Drnas  
**Eksperimentalna grana:** `experiment/real4-blind-gate-cuts-20261124`  
**Izvori:** 6 netaknutih originalnih javnih HDL datoteka zamrznutih *nakon*
pre-lock testa detektora i provjerivača u Actions
[45339922757](https://github.com/Frane12/DRNAS-SAT/actions/runs/45339922757).

**Završna neovisna ponovna provjera:**
[REAL4 fallback GitHub Actions 45341226748](https://github.com/Frane12/DRNAS-SAT/actions/runs/45341226748) —
SUCCESS, dokazni JSON i SHA manifest u artefaktu
`DRNAS-REAL4-BLIND-UNKNOWN-RTL-FALLBACK-INDEPENDENT-AUDIT`.

## Istina o rezultatu — sve zadržano

Testno računalo: Ubuntu 22.04, **Yosys 0.9**,
CaDiCaL 1.7.3 kompajliran iz izvora, Kissat na zaključanom
commitu `8af8e56f…`. Rezultati ovise o konkretnoj sintetiziranoj
logičkoj mreži Yosysa. Nisu inherentna svojstva originalnog HDL-a
na svim frontendima.

| Neviđeni projekt | Synthesis | Gate ćelije | Globalni afini izlaz/FF-D bitovi | Lokalno afini izlaz/FF-D bitovi | Nepoznati | Cutpoint signali |
|---|---|---:|---:|---:|---:|---:|
| AES S-box (secworks/aes) | OK | 5988 | 0 | 0 | 32 | 0 |
| UART TX (ZipCPU) | OK | 982 | 2 | 73 | 4 | 651 |
| Streaming FIFO (verilog-axis) | OK | 553 | 60 | 88 | 22 | 302 |
| PicoRV32 procesor (YosysHQ) | OK | 7395 | 171 | 416 | 351 | 2495 |
| HDMI TMDS (hdl-util) | **FRONTEND_UNSUPPORTED** | — | — | — | — | — |
| SHA256-W-MEM (secworks) | OK | 3963 | 0 | 512 | 32 | 2018 |

Kumulativno: **5/6 sinteza uspješno**, **5/5 potvrđenih
certifikata re-evaluirano**, 233 globalno, 1089 lokalno,
441 UNKNOWN izlaznih/FF-D bitova i 5466 definirana
nelinearna ili nepodržana logička cutpointa.

**HDMI nije dokazani matematički neuspjeh:** Yosys 0.9
odbija izvorni SystemVerilog već na liniji s
`parameter int CN = 0`. To je frontend verzijski problem,
ne dokaz da modul nema afine podstrukture.

**AES S-box nije dokazani afini sklop:** svi analizirani
izlazni bitovi su UNKNOWN zbog nedopuštenih X-vrijednosti
u trenutnoj sintetiziranoj mreži; nismo izmišljali rezultat.

## Ne smijemo napuhivati broj afinih bitova

Velik broj `GLOBAL_AFFINE_ONE_STEP` i
`LOCAL_AFFINE_WITH_CUTS` sondi trivijalna je kopija
jednog signala ili fizičkog cutpoint izlaza, a ne
neki duboki višekoračni GF(2) zakon.

Za konzervativnu dodatnu analizu nakon audita računali
smo `popcount(mask >> 1) >= 2`. Taj kriterij isključuje
konstantne vrijednosti i jednostavne alias-signale,
ali sam po sebi ne dokazuje da je obrazac nov niti dubok.

- **Vanjski izlazi i FF-D pinovi:** samo **2 netrivijalna globalna
  afina** bita (FIFO) i **24 netrivijalna lokalno afina**
  bita (FIFO) prema tom strožem kriteriju.
- **Zasebno uzorkovana interna XOR vrata (do 32 po modulu):**
  **42 netrivijalna globalno afina** i **80 lokalno
  afinih** rezultata (ukupno 122). Ovi su mali
  podsustavi stvarnih sintetiziranih mreža, ali često
  predstavljaju običan XOR dvaju signala.
- Navedena dva podskupa nisu mjerena kao puni dokaz rada
  originalnog CPU-a, SHA-a ili UART protokola.

Ovo je važan cilj sljedećeg eksperimenta: **raditi na netrivijalnom
relevantnom cone-of-influence grafu**; rangirati afine cjeline po
dubini, fan-in skupu, korisnim vanjskim izlazima i broju stvarno
uklonjenih nelinearnih granica — ali za novu evaluaciju
moramo prije toga zaključati novu verziju i uzeti novi holdout.

## Kissat i CaDiCaL — što zapravo znači rezultat

Za 12 lokalnih dokazanih mikro-kona izdvojenih iz stvarnih
Yosys mreža generiran je *posebni*, precizni CNF miter
`gate_cone ⊕ affine_formula`. Nelinearni cutpointovi su
slobodni Booleovi ulazi u tim miterima.

Kissat i CaDiCaL dobivaju isti CNF za svaki slučaj:

- **24/24 Kissat** rezultata UNSAT;
- **24/24 CaDiCaL** rezultata UNSAT;
- **0 timeouta ili pogrešnih SAT modela**.

UNSAT rezultati potvrđuju očekivane lokalne identitete, ali
nisu popraćeni standardnim DRAT/LRAT certifikatom.
To **nisu** CNF formule cijelog javnog FPGA projekta!
Ovo nije pobjeda nad općim SAT solverima; oni su
uspješno i brzo odradili svoj dijagnostički zadatak.

## Različite Yosys verzije — ne smije se usporediti kao isti ulaz

U preliminarnom GitHub Actions 24.04/Yosys 0.33
PicoRV32 sintetizirana je u drugačiju mrežu i dao je
210 globalnih / 308 lokalnih sondi, dok je reproducirani
završni Ubuntu22/Yosys 0.9 dao 171/416. **Oba su zasebno
replay-verificirana, ali nisu isto gate-netlist mjerenje**.
Za buduća mjerenja mora se strogo pinati i Yosys verzija,
frontend zastavice i SHA netlista, a ne samo izvorni RTL.

## Ocjena istraživačkog doprinosa

REAL4 demonstrira korisno **automatizirano izdvajanje
matematičkih međufunkcija iz pet različitih javnih
sintetiziranih sklopova**, uključujući sekvencijske
granice; vrsta podsustava nije zadavana unaprijed.
Ali zasad najveći dio otkrivenih bitova nije netrivijalan.
Nema dokaza cjelokupnog temporalnog ponašanja, izvornog
specifikacijskog standarda niti općeg SAT/UNSAT ubrzanja.

**Sljedeći prag:** dokazati stvarne dublje interne
matematičke obrasce i povezati ih s izvornom svrhom
podmodula, a ne samo sa sintetskim bitovima u netlistu.
