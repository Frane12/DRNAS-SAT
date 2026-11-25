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
