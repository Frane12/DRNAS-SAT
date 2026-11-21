# DRNAS STRUCTURE ATLAS 3 — 14 ORIGINAL CNF-ova, 42 permutacije i 4 promjene kodiranja

**Datum:** 21. studenoga 2026.  
**GitHub završni audit (PASS):** https://github.com/Frane12/DRNAS-SAT/actions/runs/44947379345  
**Eksperimentalna grana:** `experiment/structure-atlas3-diverse-encoding-validation-20261121`  
**Zaključak:** source-clause činjenice provjereno su robusne na kontrolirane permutacije i preimenovanja, uključujući promjene polariteta. Ovo NIJE novi UNSAT/SAT rezultat ni mjerenje prednosti nad Kissatom. `main` nije mijenjan.

## 1. Što je testirano

- 14 već postojećih, SHA-mjerljivih ORIGINALNIH DIMACS datoteka iz četiri skupine: graph coloring (1), Petersen/IPG (1), XOR234 Grid (1), PCMAX (11).
- Tri potpuno unaprijed zadane varijante svakoga originala, ukupno **42**: bijektivno preimenovanje i miješanje poretka; preimenovanje + polarnost; druga nezavisna permutacija s promjenama polariteta.
- Svaku varijantu verifier vraća na original preko poznate inverzne mape pa se uspoređuje točan multiskup klauzula, uključujući duplikate. Izostane li i jedna klauzula, dokaz ekvivalencije iz ove mape ne prolazi.
- Izvornoklauzulni detektor prepoznaje grupe `exactly-one` sa signed literalima (ALO i svi AMO parovi u izvorniku), kao i potpune tablice `XOR2/3/4`. Ne koristi ime datoteke, porijeklo ili očekivani status.
- Zaseban izvorni provjerivač `check_facts.py` čita istu izmijenjenu CNF formulu i ponovno provjerava svaku prijavljenu ALO, parnu mutex zabranu i izvornu zabranjenu XOR dodjelu.
- Namjerno pokvareni original, sa stvarno izbrisanom jednom izvornom klauzulom i *namještenim novim hashom u lažnom certifikatu*, mora biti odbačen.
- Provjerena je zamjena jednoga `exactly-one` podsustava na četiri stvarna originala: originalni parni AMO se briše i zamjenjuje sekvencijalnim Sinz AMO kodiranjem s novim pomoćnim varijablama, uz očuvanje izvorne ALO. Matematička semantika nakon egzistencijalnog uklanjanja pomoćnih varijabli mora ostati ista.

## 2. Izmjereni rezultati, bez selekcije po rezultatu

| Pokus | Rezultat | Što to točno potvrđuje |
|---|---:|---|
| Različiti originalni izvori | **14** | 11 PCMAX, 1 GRAPH, 1 Petersen/IPG, 1 XOR234 |
| Kontrolirane varijante s točnom inverznom ekvivalencijom | **42/42** | Isti izvorni logički problem nakon bijektivnog preslikavanja |
| Source-verified EO grupa očuvano | **42/42** | Isti broj izvorno dokazivih EO grupa |
| Source-verified XOR2/3/4 tabela očuvano | **42/42** | Isti broj potpunih izvornih XOR tabela po širini |
| Coarse strukturni otisak očuvan | **42/42** | Nužni, ali ne potpuni invariant |
| Neovisne provjere prijavljenih činjenica | **56** | 14 originala + 42 varijante |
| Pokvarena izvornoklauzulna premisa odbijena | **13/13 primjenjivih** | Jedan original nije imao odgovarajuću EO/XOR premisu za ovaj kontrolni tip |
| Različito kodirani podsustavi na originalnim formulama | **4/4** | Ekzistencijalno ekvivalentan sekvencijalni AMO |
| Permutacije *nakon* promjene kodiranja | **8/8** | Novi kodovi ostaju sigurni na još dvije signed varijante |
| Kontrole semantike lokalnog kodera | **n=2..6** iscrpno; **n=7,9,12** preko konstrukcije prefiksnih svjedoka i parnih UCP konflikata | Lokalni encoder, ne globalna originalna formula |

### Pojedinačne promjene kodiranja

| Izvorni CNF | Prije var. / klauz. | Poslije var. / klauz. | Širina zamijenjene EO grupe | Rezultat |
|---|---|---|---:|---|
| Petersen/IPG | 45 / 300 | 47 / 302 | 3 | Lokalna projekcija očuvana |
| XOR234 Grid | 264 / 968 | 265 / 969 | 2 | Lokalna projekcija očuvana |
| PCMAX m14 | 3.639 / 14.524 | 3.644 / 14.523 | 6 | Lokalna projekcija očuvana |
| PCMAX m30 | 14.112 / 167.638 | 14.113 / 167.639 | 2 | Lokalna projekcija očuvana |

**Važna lekcija o kodiranju:** XOR234 Grid je prije promjene imao 4 pune izravne XOR2 tablice, 40 XOR3 i 100 XOR4. Nakon ekvivalentnog sekvencijalnog prekodiranja jednog EO2 odnosa bile su vidljive 3 XOR2, 40 XOR3 i 100 XOR4 tablice. Matematička mogućnost dodjele na izvornim varijablama ostala je ista, ali izravna sintaktička prepoznatljivost nije. Za m30 jedan izravni XOR2 motiv također više nije vidljiv. Broj izravno prepoznatih EO grupa može pasti više od jedan nakon zamjene dijeljenih klauzula — ne smijemo ga zamijeniti sa stvarnom semantičkom pokrivenošću.

## 3. Točno što je, a što NIJE dokazano

**Potvrđeno:** svih 42 bijektivnih permutacija i promjena polariteta dokazivo je ekvivalentno originalima poznatom inverznom mapom; samostojeći EO i XOR source-witnessi ostali su provjerljivi iz stvarnih klauzula. Ekvivalentnost četiri alternativna AMO kodiranja pod projekcijom na stare varijable slijedi iz lokalnog dokaznog argumenta za sekvencijalni brojač; provjerena je i odgovarajućim SAT/UNSAT kontrolama lokalnog podsustava.

**Nije potvrđeno:** da Atlas zna prepoznati sve *nepoznate* varijante kodiranja bez mape ili da je već povećao broj riješenih SAT instanci. Ovdje se ne izvozi standardni VeriPB/DRAT *UNSAT dokaz za cijelu izvornu formulu*. Klauzule mogu sadržavati korisne strukture i bez globalne kontradikcije. Nismo testirali nove, po obiteljima neviđene SAT Competition 2025 izvore u ovom pokusu; ovo je razvojna regresija na postojećim originalima.

## 4. Znanstveno utemeljen sljedeći krug

1. **Prvo odabrati 10–20 originalnih CNF formula iz različitih već definiranih problemskih obitelji** (izvorni GBD ID, provenijencija, objavljeni SHA, bez unaprijed poznatih rješenja za naš novi modul).
2. **Bez metapodataka** pokrenuti izvorne detektore i izraditi `SOURCE_FACTS_ONLY` certifikate. Izostanak prepoznate strukture vraća UNKNOWN; nije negativni dokaz.
3. Za svaki original načiniti tri kategorije transformacija: bijektivna permutacija, promjena polariteta i drugo poznato logički ekvivalentno kodiranje s pomoćnim varijablama. Za nove nepoznate kodere ne tvrditi ekvivalenciju bez dokaza.
4. Spojiti module uz source-bound fact exchange i ponovnu provjeru premisa. Obvezne ruke: SOLO_A, SOLO_B, BRIDGE_ON, BRIDGE_OFF, standardni referentni solver.
5. Brojati **samo** SAT modele koji zadovoljavaju originalne klauzule i UNSAT dokaze koje prihvati nezavisni standardni VeriPB/DRAT/FRAT provjerivač, uz jedno logičko CPU i isti E2E vremenski limit.
6. Ponoviti sve po sjemenu i obitelji, zabilježiti regresije i UNKNOWN. Promicati tek novu, dokazivu pokrivenost bez netočnih odgovora.

## Reprodukcija

```bash
python3 research/structure_atlas3/audit.py
```

Glavne datoteke:
- `source_facts.py`: potpisane EO i izravne XOR izvornoklauzulne činjenice i uski reencoder
- `check_facts.py`: neovisna ponovna provjera matematičkih premisa
- `audit.py`: 14 originala, 42 permutacije, kvarenje premise, 4 ekvivalentna kodiranja, izvještaj
- `.github/workflows/structure-atlas3-diverse-encoding-audit.yml`: GitHub reprodukcija i artefakt `DRNAS-ATLAS3-14ORIGINAL-42VARIANTS`
