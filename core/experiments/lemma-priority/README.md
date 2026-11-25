# Odabir prioriteta dokazanoj klauzuli prije popravka modela

Dva uključiva načina rada proširuju izvornu CNF jezgru. Oba koriste isti izvod
i provjeru tabličnih klauzula kao `table-first`. Nakon što formula stigne u
fazu traženja modela projekcijom i popravkom, jedan zaključak dobiva prvo
mjesto iza izvornih klauzula. Ostale izvedene netablične klauzule slijede ga
u svom dotadašnjem poretku, a ostale dokazive tablične posljedice dolaze na
kraj. Skup klauzula i njihov broj su jednaki; izvorni prefiks ostaje istovjetan.

* `table-rank`: za svaki literal l prebroji N(l) i N(-l) u izvornim,
  normaliziranim klauzulama. Za kandidata C izračunaj umnožak
  ∏[l u C] (1+N(-l))/(2+N(l)+N(-l)). Odaberi najveću vrijednost, a pri
  izjednačenju prvog kandidata. To je heuristička procjena koliko bi lako
  cijela klauzula bila nezadovoljena uz pojednostavljenu pretpostavku
  neovisnosti. Vrijednost služi rasporedu obrade; originalni provjerivači
  zadržavaju odluku o prihvaćanju.
* `table-pick-first`: ista promjena rasporeda, prvi kandidat, bez bodovanja.
* `table-first`: postojeći raspored sa svim izravnim posljedicama naprijed.
* `default`: postojeći RUP način rada. Nijedan način ne koristi CDCL.

Kandidati i njihova ocjena računaju se u samom programu prije popravka.
Telemetrija daje broj kandidata, redni broj i literale odabranog kandidata
te ocjenu. Nula za redni broj znači da odabir nije izvršen.

## Protokol

Zamrznuti su izvorni kod, binarni program, pravilo i generator prije generiranja
12 novih 3-CNF formula. Četiri slučaja imaju neuvjetovane slučajne predznake,
četiri imaju ugrađenu zadovoljivu dodjelu, a četiri je imaju uz uravnoteženi
očekivani broj pozitivnih ishoda literala pri toj dodjeli. Sve formule imaju
500 varijabli i 2130 klauzula. Solver dobiva samo DIMACS. F26 je izdvojeni
retrospektivni slučaj. Svaki od četiri načina dobiva po 5 s za rješavanje i
zasebnih 5 s za audit; tri ponavljanja, rotiran redoslijed, isti pinirani
logički CPU za sve načine na pojedinačnoj formuli. Četiri različite formule
mogu se izvoditi istodobno na zasebnim CPU-ovima. Primarni ishod je broj
različitih formula riješenih u sva tri ponavljanja. Uzorak služi procjeni na
ovom generatoru i rasponu veličina.

U drugom pokusu izolirana je samo faza projekcije i popravka. Za svaki ulaz
snima se zajedničko stanje načina table-first. Na onima koji dosegnu tu fazu s
dokazanim kandidatima neovisno se provjeravaju sve tablične premise, zadržava
isti dokazni dnevnik i raspoređuju iste klauzule. Uspoređuju se prethodni
raspored, odabir prvog, odabir prema ocjeni te svaka moguća pojedinačna prednost
(naknadna dijagnostika). Istovjetni rasporedi dijele jedno mjerenje po
ponavljanju. Projekcija dobiva 150 ms, suradnja modula 90 ms, a popravak najviše
2 160 000 promjena i 2 s. Svaka se dobivena dodjela provjerava na izvornom
CNF-u. Ranija ablacija koja je potpuno uklonila neodabrane klauzule predstavlja
drugi eksperiment.

## Ponavljanje

```sh
bash core/build.sh
python3 core/tests.py
python3 core/experiments/direct-table/test_certificate.py
python3 core/experiments/f26-replay/build.py
c++ -O2 -std=c++20 core/experiments/lemma-priority/order.cpp -o core/bin/priority-order
python3 core/experiments/lemma-priority/test_order.py
python3 core/experiments/lemma-priority/pilot.py new-panel
python3 core/experiments/lemma-priority/fixed.py new-panel new-fixed
python3 core/experiments/lemma-priority/report.py new-panel new-fixed
```

[Brojevi po formuli, načinu i ponavljanju](summary.json) ·
[Ulazi, SHA-256 zamrznutih izvora, snimke stanja, rezultati i dokazi](evidence.zip)

## Rezultati na novim ulazima

| Način | Riješeno od 12 u tri ponavljanja | Riješeno u sva tri |
|---|---|---:|
| default | 7, 6, 7 | 6 |
| table-first | 6, 6, 6 | 6 |
| table-pick-first | 6, 6, 6 | 6 |
| table-rank | 7, 7, 7 | 7 |

Razlika je H09 (neuvjetovani nasumični 3-CNF). Pravilo odabire drugog od dva
kandidata, disjunkciju −6, −64, −120, −156, −484. Ona ima ocjenu 0,01932,
prva klauzula 0,01620. U javnom načinu table-rank sva tri modela prolaze
provjeru pri 3,116–3,131 s rješavanja. Osnovni način prolazi 2/3, a dvije
kontrole s izravnim tablicama 0/3. Na šest novih ulaza sa snimljenim stanjem
i kandidatima u izoliranoj fazi, na H09 samo prioritet drugog kandidata
daje model (1 302 534 promjene u svakom ponavljanju); prioritet prvom i
prethodni raspored troše svih 2 160 000 promjena. Ostalih pet dostupnih
slučajeva ne mijenja stabilno riješen status u odnosu na table-first.

Na izdvojenom F26 table-first prolazi 3/3, a table-rank bira drugu klauzulu i
ostaje na 0/3, čak i u kontroli uz pun limit promjena. Naknadno iscrpno
ispitivanje pojedinačnih prioriteta na zamrznutom stanju nalazi trećeg
kandidata (794 636 promjena). Ostale su klauzule i ovdje zadržane.
Ovaj rezultat potvrđuje regresiju na razvojnom primjeru uz jedan stabilan
dobitak na malom novom uzorku. Pravilo ostaje eksperimentalno i uključivo.

Prošli su postojeći CORE testovi, uključujući 420 formula s iscrpnom kontrolom,
provjere tabličnih certifikata, šest testova izvornog raspoređivača i
dodatno provjereni TABLE+DRUP odgovori na F09 i F11 u oba nova načina.
