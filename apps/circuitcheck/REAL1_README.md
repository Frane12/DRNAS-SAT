# DRNAS REAL1 — originalni vanjski FPGA projekti

**Istraživanje i eksperiment:** Frane Drnas.  
**Branch:** `experiment/delta-real1-thirdparty-rtl-20261124`.  
**Originalni `main` nije mijenjan.**

## Zašto sada stvarni RTL?

Prijašnji DRNAS DELTA2-C CRC-2048 uspjeh potvrđen je na
**našim deterministički generiranim demonstracijskim sklopovima**.
Nije valjano automatski prenositi njihovu uspješnost na stvarne
FPGA/IP projekte drugih autora.

Ovaj eksperiment preuzima javne *izvorne* Verilog datoteke od
tri različita autora, zaključava njihove Git commitove i
Git blob SHA-1 identifikatore i ne mijenja niti jedan njihov
DUT/source file.

### Originalni izvori (pinovi i stvarne funkcije)

1. [Alex Forencich, verilog-lfsr, rtl/lfsr.v](https://github.com/alexforencich/verilog-lfsr/blob/c1f86d036745935f3812ec6ddc7821c70ef4c9de/rtl/lfsr.v),
   commit `c1f86d036745935f3812ec6ddc7821c70ef4c9de`,
   blob `e3a472e3f280f3a697dee718b0416f2667181c00`, MIT.
   Stvarna parametarska CRC i LFSR implementacija s dva izvorna
   različita načina sinteze: `STYLE="LOOP"` i
   `STYLE="REDUCTION"`.
2. [ZipCPU, wbuart32, rtl/rxuart.v](https://github.com/ZipCPU/wbuart32/blob/f43a6b83c3a70fb2ac0696a45c5545b233fb860b/rtl/rxuart.v):
   stvarni UART prijamnik s taktovima, stanjem i kontrolnim
   signalima. Sadašnji kombinacijski afini dokaz ga **ne podržava**,
   pa je svjesno negativna kontrola.
3. [secworks, sha256, src/rtl/sha256_core.v](https://github.com/secworks/sha256/blob/837c5cc396f001d18f2c765721c585716eb439ae/src/rtl/sha256_core.v):
   stvarni SHA-256/224 hardverski kriptografski sklop sa
   sekvencijskim i nelinearnim ponašanjem.
   Također kontrola izvan sadašnje klase.

## Dvanaest stvarnih implementacijskih usporedbi

Od **neizmijenjenog** Forencicheva modula formirani su tanki testni
Verilog omotači koji instanciraju dvije njegove originalne implementacije
na istim proizvoljnim ulazima i počecima registra.

- CRC16-CCITT, 8 data bitova, 16-bitno stanje
- CRC32 Ethernet, 32 data bita, 32-bitno stanje
- CRC32C iSCSI, 32 data bita, 32-bitno stanje
- PRBS31, 64 data bita, 31-bitno stanje
- Scrambler 64b/66b, 64 data bita, 58-bitno stanje
- CRC32 Ethernet, 128 data bitova, 32-bitno stanje

Za svaku vrstu jedna usporedba bez greške i jedna s namjernom
invertiranom bitnom vrijednošću **samo u omotaču** (ukupno 12).

**Nisu to dva neovisno napisana CRC algoritma niti dokaz
ispravnosti IP-a prema vanjskoj protokolarnoj specifikaciji.**
To je dokaz ekvivalentnosti dvaju objavljenih stilova iste
praktične FPGA implementacije.

## Kontrole i vremenska pravila

- DELTA1 nad Yosysovom sintetiziranom kombinacijskom mrežom
  vrši egzaktno afino GF(2) dokazivanje. Prihvaćaju se samo
  dokazi koje je neovisni `delta1_verify.py` ponovno provjerio.
- Kissat i CaDiCaL dobivaju **isti originalni Yosys miter CNF**,
  bez dodatnih preinaka formula.
- Dva ponavljanja i promijenjen redoslijed solvera.
- 30 sekundi po solveru, jedan logički CPU u svakom pokušaju.
- Iznad limita bilježimo `TIMEOUT`, nepodržani sklop `UNKNOWN`,
  a ne uspjeh.
- Svaki SAT model mora zadovoljiti **svaku CNF klauzulu**.
  UNSAT rezultat konkurenta nema zasebni standardni
  DRAT/LRAT certifikat u ovoj studiji.
- Bilježe se broj varijabli, klauzula, trajanje pretvaranja u
  CNF, korištenje memorije i vrijeme.
- Trošak Yosys CNF izvoza prikazan je zasebno i nije uračunat
  u vrijeme Kissat/CaDiCaL solvera; DRNAS uključuje
  stvarno sintetiziranje i replay.

**Ne uspoređuju se isti prikazi problema:** DELTA1 dobiva Yosys
mrežu logičkih vrata, a Kissat i CaDiCaL DIMACS. Omjer vremena
je rezultat putova u konkretnom inženjerskom postupku, ne dokaz
prednosti općeg SAT solvera na identičnom CNF-u.

## Pokretanje

`python3 apps/circuitcheck/real1_generate.py --out external`

`python3 apps/circuitcheck/real1_run.py --manifest external/manifest.json --out results --shard 0 --shards 4 --kissat /path/kissat --cadical /path/cadical`

GitHub CI: `.github/workflows/drnas-real1-thirdparty.yml`.
Završni `REAL1_REPORT.md` i `REAL1_RESULTS.json` nastaju samo
ako su sva četiri mjerna dijela prisutna i provjerena.

## Sljedeći zaista opći korak

Razvijati automatsko prepoznavanje afinih konačnih automata
s nepoznatim registarskim stanjima, uz **potpunu sekvencijsku
formalnu verifikaciju**, i neovisno specificirane CRC/UART
protokole. Bez toga ne tvrdimo da DELTA2-C može
validirati stvarni UART ili SHA256 sklop.
