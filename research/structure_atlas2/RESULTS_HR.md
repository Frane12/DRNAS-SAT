# DRNAS STRUCTURE ATLAS 2 — stvarna pitanja, problemske obitelji, izvorni CNF i razmjena modula

**Datum:** 21. studenoga 2026.  
**Grana:** `experiment/structure-atlas2-domain-taxonomy-20261121`  
**Završeni CI:** https://github.com/Frane12/DRNAS-SAT/actions/runs/44946479104  
**Status:** PASS, **izvorni audit**, ne novi SAT/UNSAT rezultat. Ne dirati main bez odobrenja.

## Osnovni predmet istraživanja

Ne klasificiramo proizvoljni CNF u problemsku klasu po nazivu ili grubom otisku.
Razdvajamo tri pitanja:
1. **Odakle potječe formula?** Povezujemo jasnu definiciju izvornog problema s deklariranom razredbom, GBD familijom, izvornim katalogom ili konkretnim poslovnim pitanjem.
2. **Koje se matematičke činjenice mogu dokazati iz stvarnih klauzula?** ALO, EO, AMO, XOR3/4, 2-SAT, kapacitet, Hall, grafovske zabrane, vremenski prijelazi, BDD.
3. **Koje dokazive činjenice međusobno djeluju?** Kandidatska razmjena nije uspješno rješavanje; poboljšanje vrijedi tek nakon ON/OFF/SOLO usporedbe i standardne provjere izvornog CNF-a.

## Katalog — klasa izvornoga pitanja, ne samo sintaksa

| Problem, ljudsko pitanje | Formalni tip | Složenost generalne obitelji | Moduli koje treba provjeriti |
|---|---|---|---|
| Raspored poslova na strojevima, stignemo li do roka? | P||Cmax feasibility | NP-potpun opći slučaj | PCMAX, Hall, BDD |
| Sukobljeni ispiti, koliko termina treba? | k-coloring | NP-potpun za k≥3 | GRAPH, Hall, EO |
| Ruta kroz svaku lokaciju jedanput | Hamiltonov ciklus | NP-potpun | GRAPH, EO, CONNECTIVITY |
| Istodobni odabiri bez međusobnog konflikta | Independent set | NP-potpun | GRAPH, kardinalnost |
| Rekonfiguracija iz jednog valjanog stanja u drugo | Independent-set reconfiguration | PSPACE-potpun u općem neograničenom obliku, uz iznimke | GRAPH, stanja, implikacije |
| Dodjela elemenata po redcima/stupcima | Rooks, matching | P za jednostavni matching, ovisi o dodatnim uvjetima | Hall, EO, GRAPH |
| Paritetne mreže logičkih signala | Tseitin / XOR linearni sustav | P za sam GF(2) | XOR, GF2 |
| Ramsey izbjegavanje zabranjenih uzoraka | Finite Ramsey coloring | Ne donositi opću NP-potpunu etiketu iz naziva | GRAPH, symmetry |
| Miješana XOR/kardinalnost | Mixed Boolean constraints | Opći SAT NP-potpun, podstruktura XOR u P | XOR, EO, 2-SAT |

U registru se odvojeno vode izvorno podržani detalji, pitanja iz života kao analogije, te uvjeti na koje se odnosne klase složenosti primjenjuju. Ne proglašavamo svaku teško izgrađenu CNF instancu nužno teškom.

## Izvorni audit — pet ORIGINAL CNF-ova iz repozitorija

`research/structure_atlas2/real_source_audit.py` pregledava *sadržaj* prethodno verificiranih i SHA-fiksiranih originala, bez uvida u oznaku obitelji tijekom pretrage motiva. Tek naknadno pridružujemo izvornu metapodatkovnu obitelj.

| Originalni CNF | Varijable | Klauzule | Source-based motivi | Kandidat za razmjenu |
|---|---:|---:|---|---|
| Graph K11 | 1.900 | 14.440 | 100 pozitivnih ALO; bez izravnog potpuno podržanog EO | GRAPH / dokazni kapacitet tek treba izvući |
| Petersen IPG | 45 | 300 | 15 EO skupina | EO / graf (kapacitet još nije skeniran) |
| XOR234 Grid | 264 | 968 | 4 EO, 40 XOR3, 100 XOR4 | **EO ↔ XOR kandidat** |
| PCMAX m14 | 3.639 | 14.524 | 25 EO | PCMAX / BDD, potrebno izdvojeno provjeriti |
| PCMAX m30 | 14.112 | 167.638 | 46 EO | PCMAX / Hall, potrebno izdvojeno provjeriti |

**Bitna razlika:** EO i XOR motivi istodobno postoje u `XOR234 Grid` originalu, no **to samo po sebi ne dokazuje da EO doprinosi XOR kontradikciji**. Za taj original već postoji zaseban raniji original-source VeriPB XOR2/3/4 dokaz; naš Atlas 2 ne smije ga prikazivati kao novu međumodulsku pobjedu. Vidjeti `research/MATH5_XOR234_GRID_VERIPB_RESULTS.md`.

### Robusnost na varijacije stvarnih izvora

- **Petersen IPG:** izravna EXACTLY-ONE rekonstrukcija vratila je **15 EO skupina prije i poslije** preimenovanja, promjene polariteta, preslagivanja. Svaka transformacija ima dokazan inverzni povratak na identičan izvorni skup klauzula.
- **XOR234 Grid:** isti potpis i dokaziva inverzna transformacija, ali ograničeni EO-RUP detektor ostao je UNKNOWN i prije i poslije. To nije greška dokaza, nego nepokrivenost tog oblika u odabranom semantičkom detektoru. Grublji izvornoklauzulni sken detektira XOR i četiri EO obrasca.
- Pet originala pregledano; **nije** zamrznut nov zasebni slijepi skup, a iz ove probe nema novog standardnog UNSAT odgovora.

## Realni SAT Competition 2025 katalog — 10 vanjskih izvora

Katalog doslovno indeksira **10 točnih GBD hashova** iz prethodno prespecificiranog `research/graph_family_disjoint25/prespec.json`. Sedam obitelji: Hamiltonian (1), independent-set-reconfiguration (3), independent-set (2), rooks (1), Tseitin (1), Ramsey (1), random-graph-XORSAT (1).

**Ograničenje ovog ATLAS2 audita:** tih deset GBD unosa su metapodaci; izvorne CNF datoteke **nisu preuzete niti skenirane u ovom novom runu**. Prethodni validirani benchmark ove obitelji ima zasebne rezultate, ali ih ovdje ne reinterpretiramo kao novo prepoznavanje strukture.

Konačno ciljamo i primjere iz stvarnih operacijskih sala, industrijskih rasporeda, hardverskog BMC-a i programske konfiguracije, ali bez izmišljenih formula: stvarni javni izvor i hash moraju se tek zamrznuti.

## Kako ćemo eksperimentalno ocjenjivati sintezu

**A. Prepoznaj.** Detektori iz originalnog CNF-a emitiraju `SOURCE_FACTS_ONLY`, s točnim klauzulama/premisama i gornjim vremenom/prostornim limitom.

**B. Normaliziraj.** Dopuštene su promjene polariteta, naziva varijabli, poretka i dokazivo ekvivalentna alternativna kodiranja; svaki prijelaz mora očuvati izvornu semantiku i logički dokaz.

**C. Razmijeni.** Modul A šalje relevantnu relaciju modulu B; B mora provjeriti ili ponovno dokazati premisu iz originala. Činjenica nije UNSAT tvrdnja.

**D. Sastavi.** Poseban dokazni sloj mora dokazati proturječje ili valjani model. Standardni VeriPB/DRAT/FRAT verifikator mora potvrditi izvorni CNF prije strogog uspjeha.

**E. Ispitaj korisnost.** Usporediti SOLO-A, SOLO-B, BRIDGE-ON i BRIDGE-OFF sa istim CPU i E2E limitom; po mogućnosti usporedno s Kissat/CaDiCaL, sve ulaze fiksirati unaprijed, tri ponavljanja, međusobno neovisne obitelji i nema prešućivanja UNKNOWN.

**F. Proširi.** Nova značajka ulazi u Atlas samo ako razumijemo što dokazivo prepoznaje i nema opasnih lažnih UNSAT slučajeva; nova nerješiva obitelj ne preimenuje se u pobjedu samo zbog novih empirijskih metrika.

## Što ostaje otvoreno

Isti mali rječnik matematičkih predikata može se kombinirati i kodirati u neograničeno mnogo slučajeva; ograničen praktični katalog primjena sam po sebi **ne znači** da ćemo garantirano prepoznati ili riješiti svaku formulu. Znanstvena metrika je verificirana pokrivenost, ne univerzalna tvrdnja.

## Izvori i reprodukcija

- GitHub originali: `evidence/graph-k11/original.cnf`, `evidence/ipg7b-petersen/original.cnf`, `evidence/xor234-grid5/original.cnf`, `evidence/pcmax-weighted2/05/original.cnf`, `evidence/pcmax-weighted2/15/original.cnf`.
- Indeks javnih izvora: https://satcompetition.github.io/2025/benchmarks.html i https://benchmark-database.de/?context=cnf&track=main_2025
- PSPACE-složenost rekonfiguracije: https://doi.org/10.1016/j.tcs.2012.03.004
- Oblik Tseitin formula: `research/MATH5_XOR234_GRID_VERIPB_RESULTS.md`
- Audit: `python3 research/structure_atlas2/real_source_audit.py`
- Završni izvještaj: CI artefakt `DRNAS-STRUCTURE-ATLAS2-real-family-source-facts`
