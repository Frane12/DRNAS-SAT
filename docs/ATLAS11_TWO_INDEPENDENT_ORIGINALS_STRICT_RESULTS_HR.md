# DRNAS STRUCTURE ATLAS 11 — dva različita originalna UNSAT benchmarka, 18 striktno certificiranih pokušaja

**Datum:** 22. studenoga 2026.  
**GitHub izvorno zamrzavanje, PASS:** https://github.com/Frane12/DRNAS-SAT/actions/runs/45009764793  
**GitHub strogi benchmark, PASS:** https://github.com/Frane12/DRNAS-SAT/actions/runs/45010204421  
**Eksperimentalna grana:** `experiment/atlas11-sat05-independent-120-135-20261122`; `main` netaknut.

## Zašto ovaj test?

ATLAS 10 je na prethodno poznatoj formuli `mod2c-rand3bip-unsat-105-3` i dvije njezine bijektivne permutacije izmjerio značajnu prednost certificiranoga matematičkog dokaza pred referentnim solverima. Međutim, to je **jedan** povijesno poznati original i dvije njegove ekvivalentne varijante, pa nije dostatna potvrda generalizacije na različite originalne probleme.

ATLAS11 zato odabire **dva dodatna, zasebna povijesna originala** različite veličine, prije ikakve analize njihovih klauzula, te koristi neizmijenjeni izvorni ATLAS9 prepoznavač i ATLAS8 VeriPB emitter.

## Povijesni originali i provjerljivo podrijetlo

Izvor: Laurent Simon, javna distribucija SAT Competition 2005 crafted benchmarka [Zenodo 6528885](https://zenodo.org/records/6528885). Cijela originalna arhiva od **360.116.523 bajta** provjerena je objavljenim **MD5 `70ca9acc105a889302db71724aab6da7`** prije izdvajanja. Članovi unutar arhive bili su zasebno komprimirani `.cnf.bz2` (što je zahtijevalo tehničku ispravku čitača arhive nakon prvog source-only pokušaja; algoritam nije izmijenjen). Izvori su odabrani točnim imenima `unsat-120-3` i `unsat-135-2` u unaprijed commitanu `research/atlas11_real2/prespec.json`.

| Izvorni natjecateljski original | Izvorni DIMACS | SHA-256 |
|---|---|---|
| `mod2c-rand3bip-unsat-120-3.shuffled-as.sat05-2340.cnf.bz2` | 160 varijabli, 640 klauzula, 14.312 B | `ee41e4fbebfa6dbe24dd1136b9e86679b151b9d46985537e12cbd38698c083e2` |
| `mod2c-rand3bip-unsat-135-2.shuffled-as.sat05-2354.cnf.bz2` | 180 varijabli, 720 klauzula, 15.912 B | `60cd6525a1180a7ce9bfd8f5817efda6aa63dc5e1b02c3d9f4547cf8080dd6bc` |

Ova dva originala imaju **različite izvorne SHA-256 vrijednosti i različite instance grafova**. Nisu permutacije jednog istog CNF izvora. Povijesno su javno označeni kao UNSAT; te oznake ne ulaze u naš detektor. Njihova obitelj je **ista AND-maskirana XOR obitelj** kao kod ranijeg ATLAS9 rezultata, nije druga problemska klasa.

## Strogi usporedni protokol

Tri algoritamske ruke, tri ponavljanja na **oba** izvora, ukupno **18 obveznih pokušaja**. U parovima redoslijed je deterministički promijenjen, a procesi su izvršavani serijski na jednoj logičkoj CPU jezgri.

| Element | Protokol |
|---|---|
| DRNAS | Source-only ATLAS9: neovisna izvorna AND/XOR semantika → GF(2) → originalni PBP → VeriPB 3.0.2 |
| Kissat | Upstream **4.0.4**, commit `8af8e56f174b778aef3aa45af9f739b2a5f492c2`, DRAT-trim |
| CaDiCaL | Upstream **2.1.3**, commit `f13d74439a5b5c963ac5b02d05ce93a8098018b8`, DRAT-trim |
| DRAT provjerivač | `2e3b2dc0ecf938addbd779d42877b6ed69d9a985` |
| E2E vremensko ograničenje | **30 s** za hash ulaza + pokretanje + solver/proof emitter + vanjski checker; proces solverskog koraka ograničen 24 s |
| Resursi | 4 GiB RAM, **128 MiB maksimalna pojedinačna datoteka dokaza**, jedno CPU jezgro |
| UNSAT prihvat | Isključivo vanjski VeriPB (DRNAS) ili DRAT-trim (Kissat/CaDiCaL) na izvornoj CNF |
| Ostali slučajevi | `UNKNOWN`, bez ikakve tvrdnje o SAT/UNSAT; strogi PAR2 kazna **60 s** |
| Izvan mjerenja | GitHub čekanje, preuzimanje izvora, kompilacija i instalacija solverskih binarnih programa |

Nije dopušteno zaključivati o prednosti nad svim SAT problemima: dvije instance iste problemske obitelji nisu reprezentativan SAT Competition uzorak.

## Potpuni verificirani rezultati

| Solver | Originali s vanjski prihvaćenim dokazom (u tri rep.) | Ukupni prihvaćeni pokušaji | Srednji E2E svi pokušaji | Zbroj strogi PAR2 |
|---|---|---:|---:|---:|
| **DRNAS ATLAS9 + VeriPB** | **120-3: 3/3; 135-2: 3/3** | **6/6** | **0,071522 s** | **0,429134 s** |
| Kissat 4.0.4 + DRAT | 120-3: 3/3; 135-2: 0/3 | 3/6 | 6,825906 s* | 196,971875 s |
| CaDiCaL 2.1.3 + DRAT | 120-3: 3/3; 135-2: 0/3 | 3/6 | 11,192787 s* | 230,495590 s |

\* Za neuspješne pokuse prikazani E2E je stvarno vrijeme do prekida; **strogi PAR2** dodjeljuje 60 sekundi svakom pokušaju bez provjerenog dokaza. Stoga se usporedba srednjih E2E preko nepotpune pokrivenosti **ne smije** tumačiti kao brzina rješavanja svih formula.

### Original 120-3: svi solveri potvrdili UNSAT

| Solver | Verificirano | Srednji puni E2E | Srednji proizvodnja dokaza | Srednji vanjski checker | Veličina datoteke dokaza |
|---|---:|---:|---:|---:|---:|
| DRNAS | **3/3** | **0,068975 s** | 0,059138 s | 0,009584 s | **57.366 B** |
| Kissat | 3/3 | 5,657292 s | 1,659343 s | 3,966932 s | 32.153.617 B |
| CaDiCaL | 3/3 | 16,831863 s | 5,746263 s | 10,958586 s | 115.961.542 B |

Na ovom istom nepermutiranom originalu, uključujući sve verifikacijske korake, ukupni E2E DRNAS-a je oko **82× manji od Kissata** i **244× manji od CaDiCaL-a**. To vrijedi **samo za ovaj izvor i navedene obvezne resurse**. Razlika je djelomično posljedica formata i veličine dokaza i cijene provjere, a ne samo vremena matematičkog zaključivanja.

### Original 135-2: veća maskirana UNSAT instanca

| Solver | Verificirano | Srednji stvarni E2E do završetka/prekida | Status |
|---|---:|---:|---|
| **DRNAS + VeriPB** | **3/3** | **0,074070 s** | Strict UNSAT |
| Kissat + DRAT | 0/3 | 7,994521 s | UNKNOWN_RESOURCE_LIMIT |
| CaDiCaL + DRAT | 0/3 | 5,553712 s | UNKNOWN_RESOURCE_LIMIT |

**Neuspjesi Kissata i CaDiCaL-a NISU timeoutovi.** Svaki od šest pokušaja na 135-2 završio je s povratnim kodom **-25, signal `SIGXFSZ`**, tj. dostignuta je predefinirana granica datoteke dokaza od 128 MiB. Bez proširenog proof-size limita i dodatnih mjerila **nije dokazano da referentni solveri ne bi mogli riješiti tu instancu**. U ovom strogo zaključanom protokolu ne smiju se prihvatiti kao verificirani UNSAT. DRNAS PBP za 135-2 ima **65.432 bajta**, a na 120-3 57.366 bajta; VeriPB je oba prihvatio na točnim izvorima.

## Što ovo znači za naš istraživački smjer?

1. Doista smo prošli korak **samo jedne izvorne formule + permutacije**: izvorno različiti grafovi s različitim brojem varijabli i klauzula rekonstruirani su istom matematičkom metodom, bez prepravljanja pravila po primjeru.
2. Na oba javna originala DRNAS je proizveo standardno provjerljive dokaze na **neizmijenjenim izvornim CNF-ovima**, što je dokaziva generalizacija **unutar jedne obitelji maskiranog XOR-a**.
3. Reference su pri zadanom limitu dokaza pokazale osjetljivost na veličinu izlaznog DRAT certifikata. Ovo je često značajna komponenta pune E2E usporedbe; buduća studija treba testirati i dovoljno velik proof-size limit, s kompletnom verifikacijom, kako bi se odvojila veličina dokaza od računalnog procesa.
4. Sljedeći najvažniji cilj je neovisna originalna UNSAT obitelj čije ograničenje **nije** maskirani XOR (Hall, BDD, grafovsko bojanje, sekvencijalni kardinalni brojač) i ON/OFF test matematičke sinteze. Bez toga nema opravdanog zaključka o općoj SAT nadmoći.

## Reprodukcija, izvorne datoteke i pohrana

```bash
# Izvorna arhiva i izvorno-zaključani članovi: 45009764793
python3 research/atlas11_real2/freeze.py atlas11-sat2005-crafted.tar.bz2

# Uz izvorne hash-pinned binarne reference i VeriPB 3.0.2:
python3 research/atlas11_real2/paired.py
```

GitHub grana `experiment/atlas11-sat05-independent-120-135-20261122`, workflowi `.github/workflows/atlas11-source-freeze.yml` i `.github/workflows/atlas11-strict-paired.yml`.

GitHub Actions artefakti:
- source-only originali `DRNAS-ATLAS11-TWO-ORIGINAL-SOURCE-FREEZE` (run 45009764793);
- kompletni modeli/proof logovi, 18 pokušaja, reference `DRNAS-ATLAS11-TWO-INDEPENDENT-STRICT-18-TRIALS` (run 45010204421).
