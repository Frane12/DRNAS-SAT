# DRNAS TOOLBOX20 na 36 izdvojenih formula

DRNAS je u sva tri ponavljanja potvrdio **26/36** formula bez CDCL-a. Na 24 javna originala potvrđeno je **13 od 14 SAT** i **3 od 10 UNSAT**. Na 12 novogeneriranih formula potvrđeno je pet SAT i pet UNSAT. Kissat je sva tri puta riješio svaku formulu. CaDiCaL je riješio svaku barem dvaput, a 35 formula sva tri puta.

## Upareni rezultati

| Skup | Solver | SAT 3/3 | UNSAT 3/3 | Potvrđeno | PAR-2 (s) |
|---|---|---:|---:|---:|---:|
| Javni originali | DRNAS | 13 | 3 | 16/24 | 2,043 |
| Javni originali | Kissat | 14 | 10 | 24/24 | 0,026 |
| Javni originali | CaDiCaL | 14 | 10 | 24/24 | 0,013 |
| Javni originali | DRNAS-no-repair | 2 | 3 | 5/24 | 4,755 |
| Novogenerirane | DRNAS | 5 | 5 | 10/12 | 1,020 |
| Novogenerirane | Kissat | 5 | 7 | 12/12 | 0,085 |
| Novogenerirane | CaDiCaL | 5 | 6 | 11/12 | 0,302 |
| Novogenerirane | DRNAS-no-repair | 1 | 5 | 6/12 | 3,005 |
| Ukupno | DRNAS | 18 | 8 | 26/36 | 1,702 |
| Ukupno | Kissat | 19 | 17 | 36/36 | 0,045 |
| Ukupno | CaDiCaL | 19 | 16 | 35/36 | 0,109 |
| Ukupno | DRNAS-no-repair | 3 | 8 | 11/36 | 4,172 |

PAR-2 je prosjek preko svih mjerenja. Potvrđen odgovor nosi izmjereno vrijeme procesa, otvoren ili nepotvrđen pokušaj nosi dvostruki limit od 6 s. Manja vrijednost je bolja. Brojevi SAT i UNSAT odnose se na jedinstvene formule s potvrdom u sva tri ponavljanja. CaDiCaL je na najvećem generiranom Tseitinovu primjeru imao dva provjerena dokaza i jedan istek vremena. DRNAS je deset otvorenih formula svaki put eksplicitno označio kao UNKNOWN.

## Što je dobiveno konstrukcijom modela

Matematičke faze s isključenim popravkom modela riješile su **11/36**. Uključeni popravak dodao je 15 provjerenih SAT modela, od kojih 11 na javnim originalima. Na javnom skupu pokrivenost se time pomaknula s **5/24 na 16/24**. Sve formule riješene s isključenim popravkom ostale su riješene u punoj konfiguraciji. Nakon ograničene egzistencijalne eliminacije popravak radi na preostalim klauzulama. Obrnuta supstitucija vraća eliminirane varijable, a poseban provjerivač provjerava svaku izvornu klauzulu.

Jezgra objedinjuje kratku rezoluciju s povratom izvedenih klauzula, implikacije pod pretpostavkom, dokaz po slučajevima nad stvarnom disjunkcijom, sustave pariteta nad GF(2), Hallov uvjet i egzistencijalnu projekciju. Izvorni TOOLBOX20 i ovaj izvršni program imaju različite skupove modula. Mjerenje s isključenim popravkom ne predstavlja usporedbu brzine s izvornim Pythonom.

Na zasebnoj razvojnoj provjeri solver je iz izvornih klauzula 66 arhiviranih TOOLBOX20 primjera dao 54 provjerena SAT i 10 provjerenih UNSAT odgovora. Dvije su formule ostale otvorene. Na 250 malih CNF-ova za koje su iscrpno provjerene sve dodjele dobiveno je 95 SAT i 155 UNSAT odgovora uz potpuno podudaranje. Ti primjeri bili su dostupni prije zamrzavanja.

## Rezultati po obitelji

| Skup | Obitelj | DRNAS | Kissat | CaDiCaL | DRNAS bez popravka |
|---|---|---:|---:|---:|---:|
| SATLIB | Planiranje poteza blokova | 2/3 | 3/3 | 3/3 | 1/3 |
| SATLIB | Mostni kvarovi u sklopovima (BF) | 0/3 | 3/3 | 3/3 | 0/3 |
| SATLIB | Kvarovi sa zaglavljenim signalom (SSA) | 1/3 | 3/3 | 3/3 | 1/3 |
| SATLIB | Induktivno zaključivanje (II) | 3/3 | 3/3 | 3/3 | 0/3 |
| SATLIB | Kvazigrupe | 1/3 | 3/3 | 3/3 | 0/3 |
| SATLIB | Nizovi svih intervala | 3/3 | 3/3 | 3/3 | 0/3 |
| SATLIB | Dubois | 3/3 | 3/3 | 3/3 | 3/3 |
| SATLIB | 3-bojanje grafa na 75 vrhova | 3/3 | 3/3 | 3/3 | 0/3 |
| Generirano | Tseitinovi pariteti | 3/3 | 3/3 | 2/3 | 3/3 |
| Generirano | Slučajni 3-SAT | 1/3 | 3/3 | 3/3 | 0/3 |
| Generirano | 3-bojanje grafa | 3/3 | 3/3 | 3/3 | 1/3 |
| Generirano | Usporedba izlaza dvaju sklopova | 3/3 | 3/3 | 3/3 | 2/3 |

## Dva primjera s vremenima

Vrijeme obuhvaća pokretanje procesa, učitavanje CNF-a, rad solvera i zapis modela ili dokaza. Provjera je mjerena zasebno. Kissat i CaDiCaL stvaraju binarni DRAT, a DRNAS na Tseitinovu primjeru izdaje algebarski certifikat. Razlika u vrsti izlaza ulazi u usporedbu.

| Formula | DRNAS | Kissat | CaDiCaL |
|---|---:|---:|---:|
| Novogenerirani Tseitin, 87 varijabli i 232 klauzule (UNSAT) | 5,13 ms | 891,00 ms | 2,310 s, 2,325 s i jedan istek na 3 s |
| Javni original ii32c3.cnf (SAT) | 40,54 ms | 164,62 ms | 8,68 ms |

U tablici su medijani triju mjerenja kad su sva završila odgovorom. Kod najvećeg Tseitinova primjera zaseban izvoz iz GF(2) u standardni DRUP stvorio je 197.163 koraka za 0,84 s, a provjera dobivenog dokaza trajala je 5,90 s. Na 24 javne formule najbolji medijan imao je Kissat na 16, a CaDiCaL na osam. Na dva od tri generirana Tseitinova primjera najbrži je bio DRNAS. Tri uzorka po obitelji daju opis ovog skupa i ograničavaju procjenu prijenosa na druge distribucije.

## Gdje je ostao UNKNOWN

Referentni modeli i dokazi utvrđuju da je među deset otvorenih jedna SAT i devet UNSAT formula. Jedini propušteni SAT je **bw_large.c.cnf**, problem planiranja. Među javnim UNSAT primjerima ostala su sva tri mostna kvara, dva kvara sa zaglavljenim signalom i dvije kvazigrupe. Još su dvije novogenerirane slučajne 3-SAT formule ostale bez strukturnog dokaza. Pojedinačni zapis za svaku formulu daje završnu fazu, broj izvedenih činjenica, broj eliminiranih varijabli i veličinu ostatka.

## Provjera i ponovljivost

Kod i pravilo izbora zamrznuti su na commitu `9eb21b61d07e2c4feca7bb84db506eb6ec602511`. Njegov SHA određuje poredak javnih članova arhiva, sjeme novih formula i redoslijed mjerenja. Odabrana su po tri javna originala iz osam SATLIB zbirki. Arhivirani razvojni podaci i dostupna povijest repozitorija pokrili su 2.195 različitih otisaka i 1.379 eksplicitnih imena. Izvorni `dubois100.cnf` ispao je zbog neslaganja zaglavlja s brojem klauzula, prema unaprijed zadanom pravilu. Svaki javni ulaz ima SHA-256 izvornog člana i točan SHA-256 normaliziranog DIMACS-a. Ponovnom obnovom manifesta dobiveni su isti ulazi. Javne zbirke su postojeći akademski benchmarki. Njihova uporaba u drugim projektima ili nedostupnim pokusima nije utvrđivana.

Sva 324 glavna i 108 kontrolnih pokretanja izvedena su serijski na jednoj logičkoj jezgri Intel Xeon Platinum 8573C. Svaki solver imao je isti vanjski limit od 3 s. Nakon izlaska procesa provjerava se potpuni SAT model ili UNSAT dokaz. Nijedna provjera nije odbila odgovor. Od osam različitih DRNAS refutacija pet je imalo izvorni GF(2) certifikat, jedna Hallov certifikat, a dvije izravni DRUP prihvaćen u drat-trim. Svih osam DRNAS-ovih UNSAT rezultata ima i standardni dokaz prihvaćen u drat-trim. Dva je solver izravno zapisao, a preostalih šest strukturnih certifikata zaseban je izvoznik nakon završetka benchmarka pretvorio u DRUP. Dodatni izvoz ne ulazi u primarni PAR-2.

## Datoteke

- [Manifest, izvori, sjemena i SHA-256](manifest.json)
- [Jedan redak po formuli](by_instance.csv)
- [Sva 324 glavna mjerenja](primary/runs.csv)
- [Svih 108 mjerenja s isključenim popravkom modela](ablation/runs.csv)
- [Izvršne verzije i otisci binarnih datoteka](primary/environment.json)
- [Evidencija naknadne provjere i standardnih DRAT dokaza](audit.json)
- [DRNAS modeli i dokazi](evidence_drnas.zip)
- [Kissat modeli i dokazi](evidence_kissat.zip)
- [CaDiCaL modeli i dokazi](evidence_cadical.zip)
- [Izvoz algebarskog ili Hallova certifikata u standardni DRUP](../standard_proof.py)
- [Izgradnja i ponavljanje eksperimenta](../README.md)
- [Izvorne javne zbirke SATLIB](https://www.cs.ubc.ca/~hoos/SATLIB/benchm.html)

ZIP arhive sadrže prvi provjereni model ili dokaz za svaku riješenu formulu po konfiguraciji. CSV sadrži otisak izlaza svakog potvrđenog ponavljanja te zasebna vremena rješavanja i provjere.
