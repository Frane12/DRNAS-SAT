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

## Privremeni posjet drugoj grani

Na tri ranije ispitane formule uspoređena su dva fiksna trajanja posjeta.
Pravilo do prvog zastoja radi jednako kao `patience`. Nakon zastoja privremeno
nastavlja drugu granu i vraća se na prvu po isteku kvote. Ako ranije nađe
model, završava odmah. Oba sačuvana stanja uključuju dodjelu, generator
slučajnih brojeva i redoslijed klauzula. Kraća kvota iznosi 60 000 promjena
(jedan ciklus popravka za 500 varijabli), a dulja 720 000 (trećina budžeta).
U sve četiri varijante obračunavaju se obje probe. Jedno izvođenje koristi
jedan logički CPU i ukupno najviše 2 160 000 promjena.

| Ulaz | Nastavi prvu | Trajni prelazak | Posjet 60 000 | Posjet 720 000 |
|---|---:|---:|---:|---:|
| F26 | UNKNOWN | SAT · 1 901 840 | UNKNOWN | UNKNOWN |
| H09 | UNKNOWN | SAT · 1 993 505 | UNKNOWN | SAT · 1 993 505 |
| N00 | SAT · 1 301 887 | UNKNOWN | SAT · 1 361 887 | SAT · 2 021 887 |

Brojevi označavaju ukupne promjene do provjerenog modela. Svaki UNKNOWN potrošio
je cijeli budžet. U 36 izvođenja (tri ponavljanja s istim sjemenom za svaku od
12 kombinacija) ponovili su se status, broj promjena i sažetak svakog modela.

### Granice fiksne kvote na snimljenim putanjama

Na F26 kontrola s trajnim prelaskom nalazi model pri ukupno 1 901 840 promjena,
a na drugu granu prelazi pri 159 585. Jednokratni posjet mora trajati najmanje
1 742 255 promjena da bi stigao do tog modela. Kontrola koja ostaje na prvoj
grani iscrpljuje budžet. Na H09 ista razlika iznosi 632 532 promjene.

Na N00 trajni prelazak potroši ostatak budžeta na drugoj grani bez modela.
Kad se automat vrati na prvu granu, pauza joj dodaje točno trajanje posjeta na
izvornih 1 301 887 ukupnih promjena do modela. Stoga posjet smije trajati
najviše 858 113 promjena. Ta se gornja granica i donja granica za F26 ne
preklapaju. Zaključak vrijedi za isti okidač, sačuvana stanja, sjeme, budžet i
jedan posjet s jednakom kvotom na svim formulama. Sva tri ulaza su dijagnostička.

[36 zapisa, sažeci izvora i provjereni modeli](temporary-results.zip)

Nakon gradnje osnovnog pokusa i raspakiravanja `previous` prema gornjim uputama,
iz korijena repozitorija pokrenuti:

```sh
tar -xf core/experiments/divergence-probe/stagnation-results.tar.xz
python3 core/experiments/divergence-probe/temporary.py previous stagnation-results temporary-rerun
```
