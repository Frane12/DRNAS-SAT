# Proba na prvom različitom potezu

F26 i H09 su poznati dijagnostički ulazi. Ispitana je samo faza popravka
modela iz prethodno snimljenih i objavljenih stanja. Na jednom logičkom CPU-u
vode se dva odvojena stanja popravka, table-first i table-rank. Svako zadržava
svoj generator slučajnih brojeva, raspored nezadovoljenih klauzula, brojače i
dodjelu. Izvorna se petlja pri gradnji pretvara u korutinu s jednom točkom
pauze po promjeni varijable. Obje se putanje naplaćuju i tijekom zajedničkog
prefiksa. Ukupna granica iznosi 2 160 000 stvarno izvršenih promjena.

Pri prvom izboru različitog literala počinje proba od 10 000 promjena po
redoslijedu, uključujući taj potez. Računa se broj nezadovoljenih klauzula
rezidualne formule **nakon** svake promjene. Nastavlja se putanja s manjim
prosjekom, pri izjednačenju table-first. Otkrivanje modela može prekinuti
pokus ranije. U dvije kontrole izvodi se isti prefiks i ista proba, a potom
se bez obzira na prosjek nastavlja unaprijed zadani redoslijed. Svaki dovršeni
model rekonstruira se i provjerava prema svim izvornim klauzulama.

| Ulaz | Razlaz | Prosjek table-first | Prosjek table-rank | Izbor manjeg prosjeka | Kontrola s provjerenim modelom |
|---|---:|---:|---:|---|---|
| F26 | 64 145 | 11,0294 | 9,5263 | table-rank, UNKNOWN 3/3 | table-first, SAT 3/3; ukupno 1 890 543 promjene |
| H09 | 660 003 | 10,7436 | 13,2427 | table-first, UNKNOWN 3/3 | table-rank, SAT 3/3; ukupno 1 972 536 promjena |

Pravilo nije ispunilo zadani uvjet za test na novim ulazima. Suprotan poredak
na ova dva već analizirana slučaja ne vrednuje pravilo izbora većeg prosjeka.
Tri ponavljanja koriste jednako sjeme i provjeravaju ponovljivost.

[Izvođenja i prihvaćeni modeli](results.zip) · [Izvorna stanja i CNF-ovi](../lemma-priority/evidence.zip)

## Reprodukcija

Iz korijena repozitorija pokrenuti:

```sh
bash core/build.sh
c++ -std=c++20 -O2 core/experiments/lemma-priority/order.cpp -o core/bin/priority-order
python3 core/experiments/divergence-probe/build.py
unzip -q core/experiments/lemma-priority/evidence.zip -d previous
python3 core/experiments/divergence-probe/run.py previous new-results
```

## Jedno prebacivanje pri zastoju

Pravilo `patience` počinje od minimuma zabilježenog na odabranoj grani tijekom
probe. Svaki novi strogi minimum ponovno pokreće brojač. Nakon 10 000 promjena
bez novog minimuma automat nastavlja iz sačuvanog stanja druge grane do kraja
budžeta. Kontrola `clock` uvijek prelazi nakon 10 000 promjena od kraja probe.
Kontrola `mean` nastavlja prvotni izbor. Svaka varijanta koristi jedan logički
CPU i zajednički budžet od 2 160 000 promjena po formuli. Pokus ispituje fazu
popravka iz snimljenog stanja. Svi dobiveni modeli prolaze provjeru na izvornom CNF-u.

| Dijagnostički ulaz | Bez prebacivanja | Fiksno prebacivanje | Prebacivanje pri zastoju |
|---|---|---:|---:|
| F26 | UNKNOWN | SAT, 1 900 543 | SAT, 1 901 840 |
| H09 | UNKNOWN | SAT, 1 982 536 | SAT, 1 993 505 |

Brojevi uključuju obje probe. Ishodi su se ponovili u sva tri izvođenja s istim
sjemenom. Nakon probe pravilo je ostalo na prvom izboru još 11 297 promjena na
F26 i 20 969 na H09.

Nakon prolaska obaju dijagnostičkih ulaza generirano je 12 novih formula,
po četiri iz svake od tri obitelji (slučajna, s ugrađenim modelom, s ugrađenim
modelom i uravnoteženim očekivanim predznacima). Svaka ima 500 varijabli i
2130 klauzula. Sjeme generatora je 69835217. Sažeci koda, binarnih programa
i generatora zabilježeni su prije stvaranja ijednog novog ulaza. Svaki od
triju načina pokrenut je jednom na svakom od sedam usporedivih stanja.
Preostalih pet izvorni CORE riješio je prije te faze.

| Novi ulazi | Bez prebacivanja | Fiksno prebacivanje | Prebacivanje pri zastoju |
|---|---|---|---|
| N00 | SAT, 1 301 887 | UNKNOWN | UNKNOWN |
| N05 | SAT, 34 639 | SAT, 34 639 | SAT, 34 639 |
| N02, N03, N06, N08, N11 | UNKNOWN | UNKNOWN | UNKNOWN |

Prebacivanje se aktiviralo na četiri ulaza. Na N05 model je pronađen prije
razlaza, a na N03 i N11 putanje su potrošile budžet bez zabilježenog razlaza.
U ovoj seriji okidač daje jednu regresiju i nula dobitaka prema nastavku prve
odabrane grane. Način ostaje u eksperimentalnom pokretaču.

[CNF ulazi, zamrznuta stanja, pojedinačni zapisi i modeli](stagnation-results.tar.xz)

Za ponavljanje, nakon gradnje osnovnog pokusa i raspakiravanja prethodnih
stanja kako je opisano iznad, pokrenuti:

```sh
python3 core/experiments/f26-replay/build.py
python3 core/experiments/divergence-probe/stagnation.py previous stagnation-rerun
```
