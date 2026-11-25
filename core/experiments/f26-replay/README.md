# F26: utjecaj redoslijeda šest dokazanih klauzula

Na F26 oba načina predaju fazi projekcije i popravka modela istih 2484 klauzula.
Prvih 2130 pripada izvornom CNF-u. U načinu table-first šest promatranih
zaključaka zauzima pozicije 2131–2136, a u osnovnom načinu 2479–2484
(brojanje od 1). Ostalih 2478 redaka identično je i po sadržaju i po redoslijedu.
Neovisni tablični auditor prihvatio je sve zaključke na izvornim premisama.
RUP provjerivač potvrdio je svih šest i na osnovnom dnevniku od 890 koraka.

| Oznaka | Literali jedne izvedene klauzule (disjunkcija) |
|---|---|
| C1 | −4, −7, −82, −377, −485 |
| C2 | 5, 16, 430, −491 |
| C3 | 6, −16, 167, 416, −491 |
| C4 | 6, 167, 416, 430, −491 |
| C5 | 16, 167, 416, 430, −491 |
| C6 | −6, 168, −221, 338, 380 |

## Pokus

Dijagnostička kopija objavljenog CNF koda sa snimljenim stanjem ulazi u istu
implementaciju projekcije, suradnje i popravka modela. Svaki prihvaćeni SAT model
zasebno se provjerava na izvornom F26. Jedan logički CPU po pokusu, fiksno sjeme
popravka iz jezgre. Ispitane su sve 64 podskupine na ranijim pozicijama i tri
kontrole koje križaju redoslijed s dnevnikom dokaza. Svaki se uvjet ponavlja
tri puta u promiješanom redoslijedu. To je pokus nad snimljenom fazom, izvan
ranijih stupnjeva rješavanja. Uklanjaju se samo eksplicitne pojave promatranih
klauzula; ostali zaključci ostaju u snimljenom stanju.

**Jednak rad.** Obje faze prije popravka dobivaju jednake limite (150 i 90 ms).
Za popravak vrijedi izvorni maksimum od 36 × 60 000 promjena varijable i vanjski
limit 2 s. Svaki neriješeni pokušaj na F26 dosegnuo je svih 2 160 000 promjena.
Sa svih šest na ranijim pozicijama dobiven je SAT u 3/3 nakon 1 816 399 promjena.
Sa svih šest na kasnijim pozicijama ishod je UNKNOWN u 3/3. Zamjena dnevnika
između ta dva rasporeda zadržava upravo te ishode i broj promjena. Bez svih
šest dobivamo UNKNOWN u 3/3. Ukupno 27 od 64 podskupine daje SAT u 3/3.
Minimalne uspješne podskupine s obzirom na inkluziju su {C1}, {C2}, {C4} i
{C3,C6}. Sam C4 dovodi do prihvaćenog modela nakon 683 570 promjena. Prisutnost
uspješnog podskupa nije dovoljna da svaki njegov nadskup bude uspješan. Svi
brojevi odnose se na konkretni izvor, poredak ostalih klauzula i fiksno sjeme.

**Jednak kratak vremenski limit.** Prethodno je ponovljen isti panel sa 145 ms
za popravak. Oba puna rasporeda i prazna podskupina daju 0/3; sam C4 daje 3/3.
U 14 od 64 podskupine SAT je prihvaćen u sva tri ponavljanja. Vrijeme i broj
dostupnih promjena očito utječu na reprodukciju nalaza.

**Novi ulazi.** Prije uvida u rezultate ablacije generirano je osam novih
3-CNF formula s 500 varijabli i 2130 klauzula: četiri s ugrađenim modelom,
četiri s nasumičnim predznacima bez uvjetovanja. Ugrađena dodjela nije predana
solveru. Oba produkcijska načina na istom binarnom programu uz 5 s po formuli
i 5 s za audit rješavaju ista četiri ugrađena i jedan neuvjetovani primjer u
svakom od tri ponavljanja. U zasebnom pokusu s redoslijedom četiri formule
dosežu ispitivanu fazu. Premještanje istih dokazanih klauzula na kraj zadržava
istu pokrivenost (1/4); na tom jednom prihvaćenom slučaju rani raspored koristi
548 521, a kasni 650 686 promjena. Osam ulaza čini mali usporedni pilot.

[Sažetak po podskupini i ulazu](summary.json) · [CNF-ovi, snimke, rezultati i modeli](evidence.zip)

## Ponavljanje

Iz korijena repozitorija pokrenuti sljedeće naredbe. Putanje rezultata moraju
biti nove. Snimke se mogu iznova pribaviti ili preuzeti iz arhive.

```sh
bash core/build.sh
cd core/experiments/f26-replay
python3 build.py
python3 panel.py f26-states f26-ablation
DRNAS_FULL_REPAIR=1 python3 panel.py f26-states f26-full
python3 fresh.py f26-fresh
python3 order_control.py f26-fresh f26-order
python3 report.py .
```

Kontrolni binarni program prihvaća samo eksperimentalno radno stanje za traženje
SAT modela, koji se provjeravaju na originalu. Skripte provjeravaju ciljani
oblik produkcijskog koda pri gradnji. U sažetku bit 0 odgovara C1, bit 5 C6.
Ponavljanja mjere stabilnost pri istom sjemenu; uzorci nisu neovisne formule.
