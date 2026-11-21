# DRNAS STRUCTURE ATLAS 1 — izvori, permutacije i različita kodiranja

**Datum:** 21. studenoga 2026.  
**Status:** potvrđen CI audit; samo eksperimentalna grana, `main` nije mijenjan.  
**GitHub Actions:** [prvi izvorni audit](https://github.com/Frane12/DRNAS-SAT/actions/runs/44945746544) · [konačni audit + semantički pilot](https://github.com/Frane12/DRNAS-SAT/actions/runs/44945902146).

## Svrha

Ne pokušavamo klasificirati formule pomoću imena datoteke ili očekivanog SAT statusa. Čitamo originalne DIMACS izvore, izvlačimo potpisne značajke, dokazivo prepoznajemo izvorne podstrukture i mjerimo što se događa kad se zapis promijeni.

Ključno razgraničenje:
- **Sirovi SHA-256** čuva izvornu reproduktivnost, ali se mijenja pri permutaciji.
- **ATLAS1 coarse fingerprint** ostaje jednak pri promjeni redoslijeda klauzula/literala, bijektivnom preimenovanju i bilo kojem preokretu polariteta pojedinih varijabli. To je *nužno obilježje*, **nije** jedinstven kanonski zapis: mogući su strukturni kolizijski slučajevi, čak i bez kriptografskog SHA sudara.
- **Source-backed motif extraction** prepoznaje sintaktičke obrasce; početni detektor nije polaritetno robustan.
- **Source-backed RUP/UCP rekonstrukcija** prepoznaje potvrđeni uvjet EXACTLY-ONE i kada je AMO drukčije kodiran te kad selektori imaju promijenjen polaritet. Ovo je valjana logička posljedica iz klauzula, ne opći dokaz SAT/UNSAT.
- **Potvrda ekvivalencije** kod kontroliranih transformacija dolazi iz poznate inverzne mape i točnog podudaranja multiseta originalnih klauzula. Podudaranje otisaka ne predstavlja dokaz ekvivalencije proizvoljnih formula.

## Test 1: pet originalnih CNF-ova

| Original | Varijable | Klauzule | Pronađeni kandidati iz izvora |
|---|---:|---:|---|
| Graph K11 | 1.900 | 14.440 | 100 pozitivnih ALO, bez izravnih potpunih AMO skupina |
| Petersen IPG | 45 | 300 | 15 potpuno podržanih exactly-one skupina |
| XOR234 Grid | 264 | 968 | 40 XOR3 + 100 XOR4 tabela, 4 exactly-one skupine |
| PCMAX m14 | 3.639 | 14.524 | 25 exactly-one skupina |
| PCMAX m30 | 14.112 | 167.638 | 46 exactly-one skupina |

Izvorne datoteke su postojeći, ranije proučeni originali repozitorija. Skup nije novi slijepi reprezentativni industrijski uzorak.

**Promjene bez promjene problema:** četiri zamrznute varijante za svaki od pet originala, ukupno 20. Svaka je ostvarena bijektivnom promjenom oznaka te po potrebi varijabilnog polariteta i poretka. Svaku varijantu verificirali smo inverznim vraćanjem i točnim poređenjem izvornog multiseta klauzula.

| Kontrola | Rezultat |
|---|---:|
| Transformacije uz dokazivu ekvivalenciju | **20/20** |
| Coarse fingerprint invarijantan | **20/20** |
| Izravni sintaktički motivi pri samom preimenovanju | **10/10** |
| Izravni sintaktički motivi pri polaritetnim transformacijama | **0/10** |
| Namjerno promijenjeni izvori: drugačiji potpis | **5/5** |
| Različiti potpisi pet originala | **5/5** |

**Važno:** 0/10 ne znači da se matematička struktura izgubila; to znači da prvotni sintaktički prepoznavač ne rekonstruira polaritet. Time smo točno locirali potrebu za semantičkim slojem.

## Test 2: dva istovjetna matematička zahtjeva, različiti CNF-ovi

Razvijen je `semantic_eo.py`, koji ne zna ime ni podrijetlo ulaza. Traži originalnu ALO klauzulu sa selektorskim literalima, a za svaki par `a,b` dokazuje da pretpostavke `a=b=TRUE` daju **konflikt jediničnom propagacijom**. Stoga izvorna formula implicira `~a OR ~b` kao RUP, a grupa je EXACTLY-ONE.

Na dvije različite reprezentacije iste projektirane veze:
1. parne AMO klauzule;
2. sekvencijalni AMO s dodatnim pomoćnim brojačkim varijablama.

Za `n=4,6,7` provjereno je iscrpno da oba kodiranja, uz egzistencijalno kvantificirane pomoćne varijable, opisuju **točno jedan od n odabira**. Zatim su kodiranja neovisno preimenovana, promijenjen im je polaritet varijabli i presložen redoslijed klauzula/literala.

| Kontrola | Rezultat |
|---|---:|
| Dva različita CNF kodiranja, tri veličine, tri transformacije | **18/18** prepoznato EXACTLY-ONE |
| Poznata bijektivna transformacija provjerena inverzom | **18/18** |
| Neovisna iscrpna provjera originalnih projekcija | **6/6** |
| Namjerno oštećene SAT kontrole | **6/6** ispravno UNKNOWN |

To je prvi potvrđeni semantički most *između različitih CNF kodiranja* u ovom Atlas pilotu. Ne dokazuje još robusnu rekonstrukciju stvarnih velikih PCMAX BDD/kompleksnih aritmetičkih kodiranja. Nije benchmark opće SAT brzine, a prepoznavanje točno-jedan odnosa nije samo po sebi UNSAT dokaz.

## Sljedeća faza

1. Proširiti dokazivu EXACTLY-ONE detekciju na originalne CNF-ove koji koriste skrivene kardinalne kodere i kompleksne kanale; svaki izdani odnos mora imati izvorno provjerljiv RUP/VeriPB ili drugi jasno označen certifikat.
2. Uvesti `source fact exchange` za klasifikaciju ALO/AMO/kardinalnosti, XOR, 2-SAT, grafovskih zabrana i BDD kapaciteta, ali bez globalnog nagađanja SAT statusa.
3. Različite kodifikacije od iste stvarne vrste problema testirati slijepo, s negativnim SAT kontrolama i preslikavanjem pomoćnih varijabli.
4. Tek nakon toga ON/OFF, međumodulski dokaz, stvarni novi UNSAT i vanjski standardni VeriPB, pod jednakim resursnim limitom.

## Reproducibilnost

- `python3 research/structure_atlas1/audit.py`
- `python3 research/structure_atlas1/semantic_audit.py`
- Originali iz `evidence/{graph-k11,ipg7b-petersen,xor234-grid5,pcmax-weighted2/...}`.
- CI artefakt: `DRNAS-STRUCTURE-ATLAS1-REAL-CNF-variants`, sa svim izvornim hashovima, tablicama, rezultatima i kodnim hashovima.
