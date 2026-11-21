# DRNAS SAT — STRUCTURE ATLAS 4: stvarni CNF izvori i matematičke strukture

**Datum:** 21. studenoga 2026.  
**Eksperimentalna grana:** `experiment/atlas4-seven-family-source-20261121`; produkcijski `main` nije izmijenjen.  
**Prvi završeni audit:** https://github.com/Frane12/DRNAS-SAT/actions/runs/44948411499  
**Prošireni resursni audit:** https://github.com/Frane12/DRNAS-SAT/actions/runs/44948718444

## Cilj

Ne zaključivati iz naziva benchmarka; iz izvornoga CNF-a, bez očekivanog SAT statusa, prepoznati izvorno dokazive EXACTLY-ONE, XOR i jednostavne grafovske sukobe, uz neovisnog provjerivača. Isti strukturirani skup matematike testirati nakon bijektivnih promjena varijabli/polariteta i preslagivanja klauzula. Potencijalna razmjena činjenica između modula nije sama po sebi UNSAT dokaz.

## Izvori i provenijencija

Točno deset ranije odabranih SAT Competition 2025 Main izvora iz `research/graph_family_disjoint25/prespec.json`, s pripadnim GBD ID/isohash i prethodno zamrznutim sirovim SHA-256 u `evidence/ci/graph-disjoint10.json`. Službeni GBD: https://benchmark-database.de/; objavljene SAT2025 upute: https://satcompetition.github.io/2025/downloads.html.

Obitelji: Hamiltonian (1), Independent Set Reconfiguration (3), Independent Set (2), Rooks (1), Tseitin (1), Ramsey (1), Random Graph XORSAT (1).

**VAŽNO:** izvori su već korišteni u prethodnom eksperimentu Graph Family Disjoint. Za ATLAS detektor predstavljaju novi pregled i ne preklapaju se s ranijim 67+10 manifestima; nisu posve novo, nedirnuto slijepo ispitivanje u cijeloj povijesti projekta.

## Rezultat prvog završenog testa

- 10/10 originalnih CNF-ova, ukupno **143.046.609 izvornih bajtova**, uspješno dohvaćeno; svaki provjeren prema ranijem raw SHA-256 (GitHub status PASS).
- U prvom unaprijed određenom proračunu 4/10 detektirano i neovisno provjereno; 6/10 `UNKNOWN_RESOURCE_GATE`, uključujući izvore s više od 2 milijuna klauzula. Svi preskočeni evidentirani.
- 8/8 izvorno provjerenih kontroliranih bijektivnih varijacija na četiri prihvaćena izvora.
- Hamiltonian: **400** source-supported EXACTLY-ONE grupa.
- Tseitin: **188** source-supported XOR2/3/4 redaka.
- Na Ramsey i random-graph-XORSAT izvoru izravni EO/XOR prepoznavač nije pronašao potpunu prepoznatljivu tablicu.
- 2/2 namjerno krivotvorenih SHA tvrdnji odbijeno.
- **0 novih standardno verificiranih UNSAT slučajeva; 0 dosad potvrđenih zajedničkih EO-XOR dokaza na tom podskupu.** GRAPH i MATCH3-Hall scout nisu opravdali UNSAT za taj pregled.
- Ne tvrditi poboljšanje u odnosu na Kissat; za ovaj Atlas izvorni audit nije rađena nova uparena evaluacija istih referentnih binarnih programa.

## Prošireni resursni test

Nakon uvida da su 6 izvora isključivo resursno ograničena, pokrenut je **odvojeno označen, poslije prvog rezultata proširen dijagnostički test**. Svi ulazi ostaju isti; samo gornja granica za pokušaj iznosi do 60 MB, 2,5 milijuna klauzula i 4 milijuna varijabli, uz 4 GB memorijskog limita na pojedinačni izvorni matematički probni proces. U svakom slučaju neuspjeh se boduje kao UNKNOWN. Dodani su izvorni binarni grafovski mutex i implikacijski opisi te veza između exactly-one selektora i izravnih grafovskih zabrana. Ovaj test ne može se proglasiti novim slijepim pokusom.

Završni rezultat proširenog testa smije se navesti **tek nakon završetka njegovog GitHub CI audita** i očitanja sačuvanog `atlas4_results/summary.json`. GitHub Actions je izvršavanje na stvarnom runneru; ova napomena ne tvrdi unaprijed PASS ili rezultat.

## Izravne matematičke tvrdnje i vanjska provjera

`research/structure_atlas4/probe_one.py` izvodi izvorni sken bez metapodatkovnih obiteljskih oznaka i nakon toga poziva `research/structure_atlas3/check_facts.py`, koji čita originalne klauzule. Za EXACTLY-ONE je potreban izvorni ALO i svi odgovarajući AMO parovi; za XOR je potreban kompletan skup izvornoklauzulnih zabranjenih kombinacija. Pri bijektivnoj transformaciji inverzno vraćanje čuva točan multiskup originalnih klauzula.

`research/structure_atlas4/audit.py` pokušava zasebne bounded module GRAPH (standardni VeriPB tek ako emitter daje potpun dokaz) i MATCH3-FLOW-HALL (izvorni projektni certifikat, **nije standardni UNSAT**). Razmjenski kandidati EO/XOR i EO/GRAPH ostaju `SOURCE_FACTS_ONLY`, ne računaju se kao rješenje.

## Sljedeći dokazni zahtjev

Odabrati stvarne formule gdje jedna samostalna metoda ne rješava CNF, druga ne rješava CNF, a **kombinirani izvorno verificirani skup premisa proizvodi novi standardno provjerljiv dokaz na neizmijenjenom originalu**. Upariti ON/OFF/SOLO i Kissat/CaDiCaL uz jednaku jednu CPU jezgru, totalni E2E limit i ponavljanja. Do tada ne tvrditi da je detektirana matematička veza dokazna pobjeda.

## Reprodukcija

```bash
python3 research/structure_atlas4/freeze10.py
python3 research/structure_atlas4/audit.py
```

`freeze10.py` automatski odbija izvore s novim SHA, nedostupne ili prevelike izvore; nikad ih ne zamjenjuje proizvoljnim drugim formulama.
