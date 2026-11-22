# DRNAS SAT — ATLAS 12: GRAPH → HALL/PCMAX → standardni VeriPB

**Datum:** 22. studenoga 2026.  
**Eksperimentalna grana:** `experiment/atlas12-proof-modular-bridge2-20261122`. `main` netaknut.  
**GitHub Actions:** https://github.com/Frane12/DRNAS-SAT/actions/runs/45013171354 — **PASS**.  
**Opseg:** dokaziva međumodularna integracija **već poznatih** matematičkih pravila. Nije dokaz da modularna sinteza rješava prethodno nerješive probleme niti nova matematička formula ili P=NP rezultat.

## Zašto je ovaj test drugačiji od ATLAS-a 6–11?

Prethodna istraživanja pokrivala su izvorno maskirani XOR SAT/UNSAT: iz originalnog CNF-a rekonstruiramo AND maskiranje, dođemo do GF(2) sustava, izračunamo SAT model ili izdamo standardni UNSAT dokaz. Potvrđeni dobici odnose se na jednu obitelj XOR kodiranja.

ATLAS12 prvi put posebno povezuje **grafovske izvorne činjenice** s **poznatim PCMAX/Hall kapacitetnim certifikatom**. Važno: izvornu metodu za pronalazak obojive `k+1` klike i PCMAX proof emitter već smo imali; rezultat je potvrda da ih možemo učiniti odvojenim, strogo provjerenim modulima. **Ne tvrdimo da je nastao prvi dokaz grafovske klike ili novi kompleksni teorem.**

## Stvarni dokazni lanac

```
Neizmijenjeni izvorni CNF
      │
      ▼
GRAPH: pronalaženje source-backed grupa i međusobnih
       mutex klauzula, poravnanje boja po klikama
      │
      ▼
EXACTLY-ONE / ALO: odabranih k+1 zahtjeva
      │
      ▼
HALL/PCMAX: k potpunih međusobno disjunktnih
            mutex resursnih grupa nad svim odabirima
      │
      ▼
neovisni source checker: stvarne izvorne ALO i
mutex klauzule, disjunktnost i potpuna particija
      │
      ▼
postojeći PCMAX cutting-planes VeriPB emitter
      │
      ▼
vanjski VeriPB 3.0.2 na izvornom CNF-u → UNSAT
```

Matematička tvrdnja za izabranu instancu:

- `k+1` pozitivnih ALO klauzula jamči barem `k+1` istinitih selektorskih varijabli jer su grupe međusobno disjunktne;
- `k` dokazano potpunih mutex klika tvori točnu particiju svih selektora i u svakoj je dopušten najviše jedan istinit;
- stoga najviše `k` selektora može biti istinito: `k+1>k => UNSAT`.

**Dokazi za svaku pretpostavku izvedeni su iz originalnih CNF klauzula**. Za same ALO klauzule nije nužno posebno dokazivati AMO unutar iste grupe; traži se *at least one* za potražnju i *at most one* u svakoj mutex resursnoj kliki. Zato se proturječje može svesti na običan Hall/pigeonhole/cutting-planes oblik koji već verificira neovisni `check_php_partition.py`.

## Izvorno potvrđeni rezultati

| Test | Što je zaista potvrđeno | Vanjski standardni VeriPB |
|---|---|---|
| **Originalni `evidence/graph-k11/original.cnf`** | `11` izvornih pozitivnih grupa, `10` kapacitetskih mutex klika, izvori svih potrebnih `550` konfliktnih parova verificirani | **ACCEPTED ORIGINAL UNSAT** |
| Sintetički `K4` s `3` boje | `4 > 3`; puna izvorna ALO i mutex podloga | **ACCEPTED UNSAT** |
| Ista `K4` s bijektivnim preimenovanjem i preslagivanjem, sjeme 101 | Ponovna source-only rekonstrukcija | **ACCEPTED UNSAT** |
| Druga bijektivna permutacija `K4`, sjeme 202 | Ponovna source-only rekonstrukcija | **ACCEPTED UNSAT** |
| `K4` uz namjerno uklonjen jedan ključni izvorni mutex | SAT model zasebno potvrđen nad 21 originalnom klauzulom | **UNKNOWN — nema lažnog UNSAT** |
| Stari `K4` certifikat namjerno predan novoj formuli bez klauzule, a s **ažuriranim pravim SHA** | Neovisni izvorni checker odbio nepostojeću konfliktu premisu | **REJECTED** |

Ovo su **4/4 standardno prihvaćena VeriPB dokaza** unutar novog GRAPH→HALL mosta, uključujući **jedan originalni već poznati grafovski UNSAT CNF**. To nisu četiri neovisna natjecateljska problema; `K4` i njegove dvije permutacije su kontrolni primjeri.

## Što nam se dogodilo na originalnim PCMAX primjerima?

Kao posebnu dijagnostiku koristili smo izvorne CNF datoteke `evidence/pcmax-weighted2/05/original.cnf` i `evidence/pcmax-weighted2/15/original.cnf`:

- naš postojeći generički `PCMAX_DIRECT` otkrivač jednostavnih pozitivnih disjunktnih ALO i binarnih mutex klikova na oba je izvora vratio **UNKNOWN**, bez nove međumodularne potvrde;
- na isto vrijeme dva **već spremljena** standardna `weighted.pbp` dokaza prošla su neovisnu vanjsku VeriPB provjeru nad točnim originalima: **2/2 PASS**;
- ove stare dokaze nismo predstavili kao nove dokaze GRAPH→HALL mosta: oni su samo potvrda da je naša postojeća BDD/weighted-PCMAX grana i dalje valjana i upotrebljiva u idućoj modularnoj integraciji.

**Ovo je ključna dijagnoza:** jednostavno source-level binarno HALL zaključivanje i BDD/weighted-PCMAX zaključivanje nemaju ista kodiranja. Za stvarno šire povezivanje treba BDD source-premise modul koji iz lokalnih tranzicija izvodi provjerljivu težinsku granicu, a ne nužno eksplicitnu kompoziciju potpunih binarnih mutex klika.

## Što nismo pokazali?

- ne postoji još dokaz zajedničke koristi u izvoru koji GRAPH **i** PCMAX zasebno ne mogu riješiti;
- grafovski CLIQUE detector ne izvodi proizvoljan Hall/min-cut za svaku CNF, nego source-backed specifičnu `(k+1)` kliku pod ograničenim traženjem;
- opće potpisane zamjene polariteta za ovaj nesignirani source-positive ALO kontrolor nisu podržane; namjerno smo koristili **preimenovanja bez flipova**;
- ne postoje upareni Kissat/CaDiCaL E2E rezultati za ATLAS12 i ne treba tvrditi performansnu prednost zbog ovog mosta.

## Idući eksperimenti za istinsku sintezu

**ATLAS13-BDD/HALL bridge:** zajedničko sučelje treba prenositi dokazive nejednakosti poput
`L(S)<=Σ_i w_i x_i<=U(S)` bez gubitka izvora pojedine PB činjenice. GRAPH daje konfliktne gornje granice; BDD/PCMAX daje uvjetno ponderirane gornje granice; ALO daje donje granice. Tek kad se sve ujedine uz izvorne provjere i VeriPB format, imamo šansu naći stvarni zajednički dokaz koji nijedan modul sam nije znao izdati.

Pošten test: mješovita SAT i UNSAT kontrola u kojoj ni GRAPH ni PCMAX zasebno ne mogu dati standardni dokaz unutar granice, a njihova valjana sinteza može. Takav primjer treba unaprijed fiksirati, provjeriti na neviđenim originalima i upareno usporediti ON/OFF uvjete.

## Reproducibilnost

```bash
# Uz VeriPB v3.0.2
python3 research/atlas12_bridge/audit.py
```

Datoteke `research/atlas12_bridge/bridge.py` i `audit.py`. Izvorni matematički moduli nisu mijenjani:

- `research/graphclique/emit_veripb.py` (izvorne grafovske činjenice, proračun poravnanja),
- `research/pcmax_capacity/check_php_partition.py` (neovisni izvorni Hall checker),
- `research/pcmax_capacity/emit_veripb_source_clique.py` (izvorni VeriPB proof emitter),
- `research/pcmax_capacity/source_php_real26.py` (samo dijagnostička izvorna PCMAX izravna obrada).

Workflow `.github/workflows/atlas12-graph-hall-bridge.yml`. CI artefakt `DRNAS-ATLAS12-GRAPH-HALL-EO-MODULAR-BRIDGE` čuva certifikate, originale koji su generirani u testu, standardne PBP dokaze, izvornu SHA telemetriju, neovisne vanjske logove i rezultate negativnih kontrola.
