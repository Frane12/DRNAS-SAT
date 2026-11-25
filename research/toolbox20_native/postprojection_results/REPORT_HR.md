# Što je donio lokalni dokaz nakon projekcije

Na 24 izdvojene formule izvan obitelji kvarova sklopova nova verzija potvrdila je 16/24, prethodna 16/24, Kissat 22/24 i CaDiCaL 23/24. Obje verzije DRNAS-a riješile su istih 16 formula u svakom ponavljanju.

| Solver | SAT | UNSAT | Potvrđeno u sva 3 pokretanja | PAR-2 (s) |
|---|---:|---:|---:|---:|
| DRNAS s lokalnim dokazom | 13 | 3 | 16/24 | 2,0350 |
| TOOLBOX20 prije ugradnje | 13 | 3 | 16/24 | 2,0348 |
| Kissat 4.0.3 | 17 | 5 | 22/24 | 0,5879 |
| CaDiCaL 2.2.0 | 17 | 6 | 23/24 | 0,4609 |

| Obitelj | Novi DRNAS | Prethodni DRNAS | Kissat | CaDiCaL |
|---|---:|---:|---:|---:|
| AIM, umjetni 3-SAT | 4/4 | 4/4 | 4/4 | 4/4 |
| JNH, promjenjiva širina klauzula | 4/4 | 4/4 | 4/4 | 4/4 |
| Učenje pariteta | 2/4 | 2/4 | 3/4 | 3/4 |
| Ograničena provjera modela sustava (BMC) | 1/4 | 1/4 | 4/4 | 4/4 |
| Kvazigrupe | 1/4 | 1/4 | 3/4 | 4/4 |
| 3-bojanje grafova | 4/4 | 4/4 | 4/4 | 4/4 |

## Trošak i pokrivenost

Novi korak pokrenuo se na 16 od 24 različite formule. U 48 izmjerenih poziva medijan mu je bio 1,29 ms, a raspon 0,25–51,80 ms. Na ovom skupu lokalno grananje nije zatvorilo dodatnu formulu. Ovo vrijeme obuhvaća samo dodatni rad između projekcije i popravka modela. PAR-2 uključuje sve faze solverova procesa, od pokretanja do izlaza.

Kad početna dodjela zadovoljava ostatak, solver odmah rekonstruira model izvornog CNF-a. U ostalim slučajevima nakon projekcije ispituje prisilne vrijednosti i otvara ograničeno stablo dokaza. Odabire do četiri kandidata u čvoru prema kratkim aktivnim klauzulama i propagaciji. Stablo ima dubinu do šest i do 512 poziva propagacije. Nakon otvorenog stabla kreće postojeći popravak modela u preostalom vremenu. CDCL se ne koristi.

## Ranije poznate formule

Na prethodnom benchmarku pokrivenost je porasla s 26/36 na 27/36. Nova verzija zadržala je svih ranijih 26 i dokazala UNSAT za bf2670-001.cnf. Svih šest dodatnih kontrola BF/SSA ranije su služile za dijagnostiku. Integrirani solver riješio je 6/6, naspram prethodnih 4/6. Oba su rezultata prikazana odvojeno od 24 naknadno izdvojene formule.

| Izvorna formula | Medijan cijelog novog solvera (ms) | Medijan dodatnog koraka (ms) | Medijan vanjske provjere (ms) |
|---|---:|---:|---:|
| bf1355-075.cnf | 125,90 | 0,20 | 48,04 |
| bf2670-001.cnf | 125,19 | 0,82 | 57,67 |
| ssa0432-003.cnf | 34,99 | 0,21 | 41,00 |

Pri provjeri implementacije ponovno smo pokrenuli 66 arhiviranih ulaza TOOLBOX20 iz izvornih klauzula. Svih 66 odgovora prošlo je provjeru, uključujući 54 SAT i 12 UNSAT. Na 250 malih razvojnih formula solver se podudarao s iscrpnom provjerom svih dodjela (95 SAT i 155 UNSAT).

## Protokol i dokazi

Prije izbora članova javnih arhiva zamrznuti su kandidat i postupak uzorkovanja na commitu `c4da19253f25f954ebf75de4d2aeb529b46d7573`. U svakoj od šest zbirki uzeta su četiri dopuštena člana rangirana po SHA-256. Uspoređeni su poznati razvojni otisci i eksplicitna imena, prošlih 36 formula i imena šest dodatnih kontrola kvarova. Poznatost formula izvan evidentiranih podataka nije utvrđena. BMC uzorci su imali od 11.683 do 326.999 klauzula. Svakom solveru dostavljen je isti kanonski DIMACS pod neutralnim imenom.

Sva četiri solvera pokretana su serijski na istoj logičkoj jezgri uz 3 s po pokušaju i promjenu redoslijeda. 288 transfernih pokretanja i 126 kontrolnih pokretanja imaju pojedinačne zapise. PAR-2 dodjeljuje šest sekundi svakom pokušaju bez potvrđenog odgovora. Potpuni SAT modeli provjeravaju se nad izvornim klauzulama. Novi lokalni UNSAT dokazi zapisuju se kao standardni DRUP i prolaze drat-trim. Vrijeme vanjske provjere bilježi se odvojeno. Kissat je qg6-12.cnf riješio dvaput uz jedan istek vremena, pa ta formula ne ulazi u njegovih 22/24. Na par32-3-c.cnf ni jedan solver nije dao provjeren odgovor unutar tri sekunde. Svaka je obitelj zastupljena s četiri formule.

- [Svaka transferna formula i vremena](by_instance.csv)
- [288 izvornih pokretanja](runs.csv)
- [126 kontrolnih pokretanja](replay.csv)
- [Sažetak i dobitci po identifikatoru](comparison.json)
- [Manifest ulaza sa SHA-256](manifest.json)
- [Verzije i otisci izvršnih datoteka](environment.json)
- [DRNAS modeli i dokazi, uključujući kontrolne formule](evidence_drnas.zip)
- [Dokazi i modeli prethodne verzije](evidence_drnas_parent.zip)
- [Kissat dokazi i modeli](evidence_kissat.zip)
- [CaDiCaL dokazi i modeli](evidence_cadical.zip)
- [Upute za ponavljanje](../POSTPROJECTION.md)
- [Javne zbirke SATLIB](https://www.cs.ubc.ca/~hoos/SATLIB/benchm.html)
