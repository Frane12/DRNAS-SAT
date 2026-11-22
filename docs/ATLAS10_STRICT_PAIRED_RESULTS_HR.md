# DRNAS ATLAS 10 — stroga uparena usporedba Kissat / CaDiCaL / ATLAS9 na javnom UNSAT izvorniku

**Datum:** 22. studenoga 2026.  
**GitHub CI rezultat:** [45008531303 — SUCCESS](https://github.com/Frane12/DRNAS-SAT/actions/runs/45008531303)  
**Grana:** `experiment/atlas10-multi-original-paired-20261122`. `main` nije mijenjan.  
**Svih 27/27 pokušaja evidentirano, 0 kritičnih netočnih SAT/UNSAT rezultata.**

## 1. Podrijetlo i ograničenje uzorka

Prvotni je plan bio više različitih originalnih javnih UNSAT formula maskirane XOR obitelji. Ali zasebno prethodno pokrenuti **metadata-only izbor** [45007955609](https://github.com/Frane12/DRNAS-SAT/actions/runs/45007955609) imao je tri uzastopna mrežna timeouta na GBD katalogu, pa **nije identificirao niti jednu dodatnu formulu**. Zato je unaprijed zaključana, reproducibilna ATLAS10 studija transparentno ograničena na:

- **jedan** povijesno poznati originalni `mod2c-rand3bip-unsat-105-3.shuffled-as.sat05-2325.cnf.xz`, GBD ID `07f5f3ca046261c3819c5c888ac837e5`;
- točan sirovi SHA-256 `828a649666ddc6cd3bd9085821eb5058737f6a9e55c8904eff0681720e5938eb`;
- **dvije dokazivo bijektivno ekvivalentne verzije**, sjemena 617 i 829 (preimenovanje, preslagivanje klauzula, te promjena polariteta za 829).

**To nisu tri neovisne formule!** Obje permutacije dijele isti izvorni matematički problem. Broj pokušaja **27** nastaje kao 3 zapisa × 3 serijska algoritma × 3 ponavljanja, a ne 27 nezavisnih problema. Usporedba je retrospektivna, ne nova slijepa generalizacija.

## 2. Zamrznuti pošteni protokol

| Uvjet | Vrijednost |
|---|---|
| DRNAS metoda | source-only ATLAS9 rekonstrukcija maskiranih XOR-a, dokaz i vanjski VeriPB 3.0.2 |
| Kissat | upstream 4.0.4, commit `8af8e56f174b778aef3aa45af9f739b2a5f492c2` |
| CaDiCaL | upstream 2.1.3, commit `f13d74439a5b5c963ac5b02d05ce93a8098018b8` |
| DRAT checker za obje reference | DRAT-trim, commit `2e3b2dc0ecf938addbd779d42877b6ed69d9a985` |
| Ponavljanja | tri po zapisu, zamrznuti promjenjivi redoslijed solvera |
| CPU | jedna logička jezgra po procesu, bez paralelnog portfelja |
| Vrijeme | 30 sekundi ukupno E2E, do 24 s proizvodnja dokaza, preostalo za vanjsku provjeru |
| Ostali limiti | 4 GiB memorije, najviše 128 MiB datoteka dokaza |
| Strogi UNSAT | samo ako nezavisni vanjski checker prihvati dokaz na točnom izvornom CNF-u |
| UNKNOWN/PAR2 | neuspjeli, neprovjereni, preskupi ili vremenski limitirani pokušaj = kazna 60 s |
| Uračunato u E2E | provjera izvornog SHA, pokretanje, dokazni postupak, vanjski checker |
| Nije uračunato u E2E | GitHub čekanje, `checkout`, preuzimanje izvora, kompilacija i instalacija alata |

## 3. Rezultat — svi pokušaji uključeni

| Kraka | Vanjski UNSAT provjeren | Prosječni E2E / pokušaj | Ukupni strogi PAR2 |
|---|---:|---:|---:|
| **DRNAS + VeriPB** | **9/9** | **0,055317 s** | **0,497853 s** |
| Kissat 4.0.4 + DRAT-trim | 9/9 | 10,779900 s | 97,019101 s |
| CaDiCaL 2.1.3 + DRAT-trim | 6/9 | 7,142179 s* | 221,022520 s |

\* CaDiCaL prosječni E2E iznosi vrijeme do povratka čak i za 3 neuspjela pokušaja. Oni nisu verificirani rezultati i u PAR2 je **svaki kažnjen sa 60 s**.

### Po pojedinom izvornom zapisu, ukupni strogi PAR2 kroz tri ponavljanja

| CNF zapis | DRNAS | Kissat | CaDiCaL |
|---|---:|---:|---:|
| Original | 0,172363 s | 25,745685 s | 24,103452 s |
| Permutacija 617 | 0,159860 s | 54,358072 s | 16,919068 s |
| Permutacija 829 | 0,165630 s | 16,915344 s | 180,000000 s (3× UNKNOWN) |

Na **originalnoj, nepermutiranoj** formuli srednji E2E kroz tri ponavljanja iznosi oko:
- DRNAS **0,057454 s**;
- Kissat **8,581895 s** (≈149× E2E u odnosu na DRNAS);
- CaDiCaL **8,034484 s** (≈140× E2E u odnosu na DRNAS).

Na sve tri **međusobno korelirane varijante** zajedno: Kissat/DRNAS prosječni E2E je ≈195×. To nije faktor generaliziranog ubrzanja SAT-a na različitim problemskim klasama ili novim originalima.

### Važno: CaDiCaL nije tri puta dosegnuo vremenski limit

Na permutaciji 829 CaDiCaL je u sva tri pokušaja završio **signalom -25 = SIGXFSZ**, nakon oko 7,71–7,79 sekundi, jer je dosegnuo zamrznutu gornju granicu od **128 MiB** za dokaznu datoteku. Dakle, rezultati su `UNKNOWN_RESOURCE_LIMIT`, **ne TIMEOUT** i ne pokušaji koji se smiju prihvatiti kao verificirani UNSAT. Rezultat bi se mogao promijeniti kad bismo povećali dokazni limit; to bi bio **novi odvojeni dijagnostički eksperiment**, a ne retroaktivna izmjena ove studije.

### O veličini i provjeri dokaza

Za original je dokaz DRNAS-a **50.534 bajta**. Kissatov DRAT bio je **46.833.565 B**, a CaDiCaL-ov DRAT **55.861.094 B**. Vanjska provjera DRAT-trim zahtijevala je otprilike 5–6 s na originalu; VeriPB je provjerio DRNAS dokaz za oko 0,007–0,009 s. Stoga se dio velike E2E razlike odnosi na **format/veličinu i trošak provjere dokaza**, a ne smije se u cijelosti pripisati bržem matematičkom zaključivanju.

## 4. Što je dokazano, a što nije

**Pokazano:** na jednom javnom, poznatom UNSAT primjeru obitelji maskiranog XOR-a i njegovim bijektivnim preslagivanjima, ATLAS9 reproducibilno rekonstruira matematički izvor, izvodi standardni dokaz i provjerava ga daleko brže od ovih dviju neizmijenjenih referenci pod navedenim resursnim uvjetima. Svi rezultati prikazani su s neovisnom standardnom verifikacijom; 27/27 pokušaja i tri potvrđena resource-UNKNOWN uključeni su bez prikrivanja.

**Nije pokazano:** da DRNAS općenito pobjeđuje Kissat/CaDiCaL na SAT Competition uzorku; da metoda univerzalno prepoznaje sve XOR, grafovske, BDD ili kardinalne kodere; da P=NP ili nešto slično; niti da uz veći proof-size limit CaDiCaL ne bi uspješno dokazao permutaciju 829. Potrebni su drugi nezavisni originali u **unaprijed zamrznutim veličinama i obiteljima**, kao i kontrola memorije, I/O i dokaznog formatiranja.

## 5. Reproducibilnost

```bash
python3 research/atlas10_paired/freeze.py
# nakon izgradnje SHA-pinned Kissat/CaDiCaL/DRAT-trim i VeriPB 3.0.2:
python3 research/atlas10_paired/paired.py
```

`research/atlas10_paired/prespec.json` sadrži unaprijed zaključane limite, broj ponavljanja i commitove alata. Workflow `.github/workflows/atlas10-strict-paired.yml` uključuje pune naredbe za build i sve pokušaje.

GitHub Actions artefakt `DRNAS-ATLAS10-STRICT-30S-THREE-ARMS-3REPS` sadrži izvorne i permutirane CNF-ove, 27 detaljnih zapisa, standardne dokazne datoteke, checkerske logove, verzije i SHA-256 hashove.
