# ATLAS · Točno jedan od k izbora

Integracija dodaje dokazive konačne domene postojećem ulazu ATLAS16. Na ulazu su izvorni DIMACS bajtovi. Za grupu potpisanih literala S ATLAS mora opravdati disjunkciju svih članova i svaku zabranu istodobnog izbora para. Tako, primjerice, skup (x₃, ¬x₆, x₁₂) postaje jedan izbor među trima mogućnostima. Ista činjenica može označavati posao na jednom od tri stroja ili vrh obojen jednom od tri boje.

## Pokretanje

Iz korijena repozitorija, s Pythonom 3.10+ na Linuxu, dekodiranje i neovisna provjera lokalnih činjenica rade sa standardnom bibliotekom.

```sh
python3 research/atlas16_pilot/run.py --cnf evidence/ipg7b-petersen/original.cnf --facts-only --out out/eo
```

Polje `evidence_dir` daje direktorij s kopijom originalnog CNF-a i pripadnim činjenicama. Zasebni program može ponoviti provjeru. Ovaj primjer koristi spremljene činjenice za izvornu Petersenovu formulu.

```sh
python3 research/atlas_eo/check.py evidence/ipg7b-petersen/original.cnf evidence/atlas-eo/petersen-eo-facts.json
```

Za cijeli router eksperiment koristi izgrađeni `build/drnas-pcmax` i vanjski VeriPB 3.0.2 dostupan kao `veripb`. Postupak izgradnje, verzije referentnih rješavača i pokretanje nalaze se u [reproduktivnom workflowu](../../.github/workflows/atlas-eo-multiencoding.yml).

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --target drnas-pcmax -j2
python3 research/atlas16_pilot/run.py --cnf evidence/ipg7b-petersen/original.cnf --out out/atlas
```

Zastavica `--eo-only` pokreće samo putove koji koriste ovu integraciju, uz jediničnu propagaciju za neposredan sukob na korijenu. Zastavica `--without-eo` daje ablacijski rezultat prijašnjeg routera na istom ulazu. Svako CLI pokretanje sprema zaseban direktorij. Poziv bez `--cnf` zadržava postojeći pilot ATLAS16.

## Od klauzule do rezultata

| Korak | Što se računa | Što prihvaćamo |
|---|---|---|
| Pronalaženje kandidata | Izričita disjunkcija širine 1–32 ili listovi jednoznačno rekonstruiranog OR stabla s potvrđenim vratima i zadanim izlazom. | Kandidat može imati proizvoljne predznake i numeraciju. |
| Dokaz domene | Za disjunkciju „barem jedan” (ALO) i svaku od k(k−1)/2 parnih zabrana pretpostavimo suprotno i jediničnom propagacijom tražimo sukob. Ako je tražena klauzula već u izvoru, dovoljan je njezin ID. | Zasebni provjerivač reproducira uređeni niz ID-ova nad izvornim klauzulama. Potvrda sadrži SHA-256 točnih ulaznih bajtova. |
| GRAPH i Hall | Iz provjerenih disjunktnih grupa i međugrupnih zabrana stvara se pomoćni prikaz za postojeće detektore klika i deficita. Nađene premise vraćaju se na izvorne potpisane literale. | Svaka korištena premisa mora biti izvorna ili izvediva RUP-om. VeriPB provjerava ukupnu kontradikciju na izvornom CNF-u. |
| XOR | Točno jedan od k potpisanih izbora povlači neparan broj istinitih članova. Uspoređujemo to s potpunom izvornom XOR tablicom na istim varijablama širine 2–4, uz uračunate predznake. | Ako se pariteti protive, dokazujemo zabranu svakog izbora te praznu klauzulu. |
| Konačne domene i egzaktno pokrivanje | Pretražuju se samo potvrđene domene. Grupe se smiju preklapati. Kod jednakog preostalog broja opcija prednost imaju domene povezane s kraćim zabranama. Binarne ekvivalencije prvenstveno se propagiraju. | SAT prolazi provjeru svih izvornih klauzula, uključujući pomoćne varijable. Za zatvoreno stablo UNSAT zaključak traži vanjski prihvaćen dokaz. |

Puni ATLAS prvo ispituje izvorne putove GRAPH, GRAPH/XOR/Hall i ponderirani PCMAX. Slijede EO i ograničena redukcija na 2-SAT. Ponderirani PCMAX zadržava vlastiti izvorni dekoder težina. Razmjena EO činjenica sada radi za graf, jedinične kapacitete, lokalni paritet i pretraživanje konačnih domena. Širi moduli za opću aritmetiku, vremenske odnose, BDD i simetrije zahtijevaju daljnju integraciju.

## Značenje izlaza

- `FACTS_VERIFIED` potvrđuje navedene posljedice izvorne formule. Izvještaj daje koliko je grupa provjereno i je li pretražen cijeli dopušteni prostor kandidata.
- `SAT_VERIFIED` potkrepljuje potpuna valuacija izvornog CNF-a u `model.json`.
- `UNSAT_VERIFIED` potkrepljuje prihvaćen dokaz na originalu. Na novom putu dokaz je u `eo.pbp`.
- `UNKNOWN` čuva razlog svakog pokušaja, uključujući preostale neobjašnjene klauzule, limit ili nedostupan provjerivač. Ako se potroši budžet za prepoznavanje, prethodno dovršene, pojedinačno provjerene grupe ostaju upotrebljive.
- Dokaziva grupa može sadržavati i pomoćne varijable kodera. Za tumačenje grupe kao posla ili stroja potrebne su i veze među grupama.

## Ponovljivi test

```sh
python3 -m unittest -v research.atlas_eo.test_eo
python3 -m pip install python-sat==1.8.dev24
python3 -m research.atlas_eo.benchmark
```

PySAT služi za neovisno kodiranje kontrola i provjeru malih projekcija. Kissat 4.0.4 i CaDiCaL 2.1.3 izvršavaju se u zasebnim referentnim mjerenjima. Svaki pokušaj koristi jedan logički CPU. Usporedba ima tri ponavljanja i ukupni limit 15 s po pokušaju. Sažetak bilježi koliko je ponavljanja uspjelo i medijan trajanja, stoga brz `UNKNOWN` nema značenje ubrzanja. ZIP uz CI čuva ulaze, potpune modele, dokaze, pojedinačne rezultate i otiske binarnih alata.

Usporedba prepoznavanja koristi izravnu sintaktičku provjeru parnih zabrana iz `structure_atlas3/source_facts.py`. Raniji `structure_atlas1/semantic_eo.py` već je isprobavao parovni RUP na izravnom i sekvencijskom kodiranju. Ova promjena dodaje prenosiv trag dokaza, potrošače u routeru, alternativnu konstrukciju ALO-a i mjerenja s neovisnim koderima. Skup uključuje retrospektivne originale i kontrolirane konstrukcije.

## Početno mjerenje od 24. studenoga 2026.

Usporedba obuhvaća devet PySAT kodiranja pod nazivima `pairwise`, `seqcounter`, `sortnetwrk`, `cardnetwrk`, `bitwise`, `ladder`, `totalizer`, `mtotalizer` i `kmtotalizer`. Svako je ispitano za k ∈ {2, 3, 5, 8, 16}, u izvornom obliku i nakon preimenovanja, promjene predznaka i miješanja redoslijeda. Novi dekoder dokazao je ciljnu grupu u 90/90 zapisa, a prethodna izravna provjera parnih klauzula u 26/90. Za svako od devet kodiranja uklonjen je najmanje jedan redak, a zasebni rješavač potvrdio je da oslabljena formula dopušta dva istinita izbora. U svih devet oslabljenih formula dekoder je odbio ciljnu grupu. [Pojedinačni zapisi](../../evidence/atlas-eo/encodings.csv) · [Oslabljene formule](../../evidence/atlas-eo/mutations.json)

Na 15 različitih ulaza svaka se metoda pokrenula tri puta. U tablici se ulaz broji kad je rezultat potvrđen u sva tri pokušaja. Četiri izvornika su graf K11, ponderirani PCMAX m00, Petersen i slučajna formula UF20-01. Petnaesti je ulaz ista Petersenova formula s drukčije kodiranim izborom jednog od triju strojeva za svaki od 15 poslova.

| Postupak | Konstruirani (10) | Arhivski izvornici (4) | Prekodirani Petersen (1) | Ukupno (15) |
|---|---:|---:|---:|---:|
| ATLAS16 s novom integracijom | 10 | 3 | 1 | **14** |
| ATLAS16 s isključenom integracijom | 0 | 2 | 0 | **2** |
| Samostalni put „točno jedan” | 10 | 1 | 1 | **12** |
| Kissat 4.0.4 | 10 | 3 | 1 | **14** |
| CaDiCaL 2.1.3 | 10 | 2 | 1 | **13** |

Na izvornom Petersenu ATLAS je pronašao 15 grupa i razriješio formulu pretragom 100 čvorova. VeriPB prihvatio je dokaz od 3 952 bajta na izvornih 45 varijabli i 300 klauzula. Za istu je formulu projekt IPG7B ranije spremio dokaz od 16 663 bajta. [Rezultat IPG7B](../../evidence/ci/ipg7b.json)

Novi dokaz sadrži samo dodavanja klauzula pravilom RUP pa je dostupan i kao DRUP i LRAT. Isti se zaključak neovisno provjerava naredbama u nastavku. Zadnja dva programa dolaze iz revizije `drat-trim` navedene u konfiguraciji CI-ja.

```sh
veripb --cnf evidence/ipg7b-petersen/original.cnf evidence/atlas-eo/petersen.pbp
drat-trim-src/drat-trim evidence/ipg7b-petersen/original.cnf evidence/atlas-eo/petersen.drup
drat-trim-src/lrat-check evidence/ipg7b-petersen/original.cnf evidence/atlas-eo/petersen.lrat
```

Petersen s novim sekvencijskim brojačima također daje provjeren UNSAT. U prvom mjerenju ATLAS je na UF20-01 vratio `UNKNOWN`. Na primjeru pet zahtjeva za četiri mjesta parovni i sekvencijski zapis aktiviraju izravni Hallov dokaz. U prvom mjerenju kardinalitetna mreža za isti deficit zahtijevala je 11 čvorova pretrage. Za K11 i m00 puni ATLAS i dalje koristi postojeće module. Puna vremena uključuju provjeru odgovarajućeg dokaza ili modela, a omjeri ovise i o trošku provjerivača. [Medijani za svaki ulaz i metodu](../../evidence/atlas-eo/summary.csv) · [CI s izvornim zapisima svih pokušaja](https://github.com/Frane12/DRNAS-SAT/actions/runs/45301992914)

## Izravni Hallov dokaz na mrežama i SAT modeli za UF20

U kardinalitetnoj mreži iz prvog mjerenja izvor ima 111 varijabli i 155 klauzula. Propagacija bez pretpostavki određuje 51 varijablu. Dekoder među 66 potvrđenih EO grupa nalazi deset grupa širine tri. Pet ih ima barem jedan već određeni izbor. Kad detektor kapaciteta najprije razmotri grupe čiji su svi izbori otvoreni, dobije pet disjunktnih zahtjeva. Unakrsne zabrane dijele njihovih 15 literala na četiri skupa veličine 4, 4, 3 i 4. U svakom je dopušten najviše jedan istinit literal. Zbrajanje zahtjeva daje pet, a zbrajanje kapaciteta gornju granicu četiri. Za izračun tog dokaza nije potrebno granati po mogućim dodjelama. Stare projekcije i dalje su dostupne kad prva projekcija ne daje potvrdu.

Za SAT mreže pretraga može dovršiti preostale pomoćne varijable pravilom čistoga literala. Provjerivač pritom čita sve izvorne klauzule, uključujući ponovljene literale. Kad lokalna dovršenja ne uspiju, prijavljuje se puni model samo ako izvorni CNF prolazi provjeru. [Izvor, potpisane grupe i dokaz](../../evidence/atlas-eo/network-fix)

```sh
veripb --cnf evidence/atlas-eo/network-fix/five-jobs.cnf evidence/atlas-eo/network-fix/five-jobs.pbp
```

Nakon EO modula puni ATLAS može pokušati ograničenu redukciju na 2-SAT. Pohlepno bira varijable dok svaka klauzula izvan odabranog skupa ima najviše dva literala. Za pojedinu dodjelu odabranog skupa postojeći postupak za jake komponente implikacijskog grafa traži model preostalog 2-CNF-a. ATLAS vraća vrijednosti iz skupa u model i provjerava sve klauzule. Na UF20-01 skupu od 11 varijabli isprobao je 1 018 dodjela, uključujući 173 poziva postupka za 2-SAT. Granice ovog puta su najviše 12 odabranih varijabli i jedna sekunda unutar preostalog ukupnog vremena. U najgorem slučaju broj dodjela eksponencijalan je u veličini odabranog skupa. Kad model izostane, ovaj put vraća `UNKNOWN`. [Provjerljiv model UF20-01](../../evidence/atlas-eo/network-fix/uf20-01-model.json)

U završnom pokusu na izvornih 15 ulaza puni ATLAS potvrdio je 15/15 u sva tri ponavljanja. Samostalni EO put potvrdio je 12/15, Kissat 14/15 i CaDiCaL 13/15. Na mreži s pet zahtjeva VeriPB je prihvatio izravan dokaz od 881 bajta. U dodatnom pokusu pet kodiranja, tri veličine i tri potpisane permutacije dalo je 45 izravnih Hallovih dokaza i 45 potvrđenih SAT modela za izvedive parnjake. Promjena jednog predznaka u zahtjevu rezultirala je SAT modelom i odbijanjem izvornog UNSAT dokaza.

| Mjerenje | ATLAS | Kissat 4.0.4 | CaDiCaL 2.1.3 |
|---|---:|---:|---:|
| Mreža pet zahtjeva za četiri mjesta, UNSAT | 26,30 ms | 70,84 ms | 68,60 ms |
| Arhivski UF20-01, SAT | 18,16 ms | 3,82 ms | 3,25 ms |
| Svih 1 000 formula UF20-91, sve SAT | 12,88 ms | 3,81 ms | 3,25 ms |

Prva dva retka prikazuju medijan triju ponavljanja, a zadnji medijan po 1 000 različitih formula, s jednim pokušajem po formuli i metodi. Svaka metoda koristi jedan logički CPU. Svi su rješavači u istoj zbirci potvrdili 1 000/1 000 modela. Vrijeme uključuje provjeru na zajedničkom DIMACS zapisu. Za usporedbu se samo formatira isti popis izvornih klauzula jer referentni programi odbijaju završni znak postotka iz SATLIB-a. Svaki je model zasebno provjeren i nad datotekom iz zbirke. Novi postupak za 2-SAT dodatno je izravno primio svih 1 000 datoteka s njihovim izvornim bajtovima.

[Rezultati za svaku od 15 formula](../../evidence/atlas-eo/network-fix/pilot.csv) · [Vremena i svi modeli za 1 000 formula](../../evidence/atlas-eo/network-fix/uf20-results.csv.gz) · [CI s dokazima i izvorima](https://github.com/Frane12/DRNAS-SAT/actions/runs/45340635259)
