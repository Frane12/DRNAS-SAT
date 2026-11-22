# DRNAS SAT — ATLAS 10: uparena, standardno verificirana usporedba na izvornom maskiranom XOR-u

**Datum:** 22. studenoga 2026.  
**Eksperimentalna grana:** `experiment/atlas10-multi-original-paired-20261122`  
**GitHub Actions:** https://github.com/Frane12/DRNAS-SAT/actions/runs/45008531303

## Što je izvorno planirano i što je stvarno dostupno

Cilj je usporedba DRNAS ATLAS9 prema neizmijenjenim Kissat/CaDiCaL na više izvornih maskiranih XOR UNSAT formula različitih veličina. Poseban prethodni *metadata-only* workflow [45007955609](https://github.com/Frane12/DRNAS-SAT/actions/runs/45007955609) pokušao je katalogizirati javne GBD izvore prije ikakva novog solverskog mjerenja. Tri GBD upita završila su s mrežnim timeoutom. Posljedično, **ni jedan dodatni javni UNSAT izvor nije mogao biti identificiran i zamrznut u toj seriji**.

Umjesto da proizvoljno zamijenimo izvore, ATLAS10 je transparentno prilagođen **jednom već poznatom javnom originalu**: `mod2c-rand3bip-unsat-105-3.shuffled-as.sat05-2325.cnf.xz`, GBD `07f5f3ca046261c3819c5c888ac837e5`, izvorni SHA-256 `828a649666ddc6cd3bd9085821eb5058737f6a9e55c8904eff0681720e5938eb`. Iz prethodnog Atlasa9 već postoji izvorno prihvaćen VeriPB UNSAT dokaz, pa je novi eksperiment **retrospektivna, usko ograničena usporedba**.

Uz original mjere se dvije matematički ekvivalentne bijektivne transformacije (sjeme 617: zamjena oznaka i poretka; sjeme 829: dodatno preokretanje polariteta). To je ukupno **3 zapisa ISTOG problema**, a ne tri nezavisne nove natjecateljske instance.

## Strogo predodređeni protokol

- Izvorni GBD ID i raniji sirovi SHA fiksirani u `research/atlas10_paired/prespec.json`; prije mjerenja `freeze.py` ponovno dohvaća original i potvrđuje točan SHA. Nema zamjena po rezultatima.
- Tri nezavisna algoritamska kraka: izvorni ATLAS9 semantički dekoder + dokazni izvoznik + vanjski VeriPB 3.0.2; originalni Kissat **4.0.4** (commit `8af8e56f174b778aef3aa45af9f739b2a5f492c2`); originalni CaDiCaL **2.1.3** (commit `f13d74439a5b5c963ac5b02d05ce93a8098018b8`). Referentni izlazi UNSAT provjeravaju se neovisnim **DRAT-trim** (commit `2e3b2dc0ecf938addbd779d42877b6ed69d9a985`).
- Svaki od tri zapisa po **3 ponavljanja**, 3 algoritma, ukupno **27 pokušaja**. Redoslijed unutar para deterministički se mijenja, sve ruke rade serijski.
- Po ruci **jedna logička CPU jezgra**, **30 s strogi E2E** (uključuje ulazni SHA, pokretanje, dokaz i nezavisnu provjeru), potrošnja programa ograničena do 24 s za dokaznu produkciju. Memory 4 GiB, veličina izlazne dokazne datoteke 128 MiB. Instalacija programa i preuzimanje ulaza nisu uključeni u sam E2E, i to je jednako za sve ruke.
- Uspjeh samo ako **neovisni vanjski provjerivač potvrdi UNSAT dokaz nad izvornim CNF-om unutar ukupnog limita**. `s UNSATISFIABLE` bez prihvaćenog dokaza NIJE certificirani rezultat. SAT modeli, ako nastanu, moraju zadovoljiti sve izvorne klauzule.
- Timeouts, nevalidni ili nepotpuni dokazi boduju se `UNKNOWN`, osim kritične nesuglasice koja prekida audit. Strogi PAR2: 60 s za neuspješan pokušaj. Niti jedan pokušaj ne uklanjamo zbog neuspjeha.

## Što bi bio valjan znanstveni zaključak?

Ova studija može pokazati upareno vrijeme i provjerene uspjehe **na jednom fiksnom, povijesno poznatom problemu i njegovim permutacijama**, ali iz nje ne slijedi zaključak o superiornosti na drugim problemskim obiteljima, generalizaciji na druge veličine ili P naspram NP. Originali u drugim veličinama zahtijevaju nezavisnu, unaprijed fiksiranu izvornu selekciju i istu standardnu provjeru.

## Reprodukcija

```bash
python3 research/atlas10_paired/freeze.py
# uz već izgrađene i verificirane binarne reference:
python3 research/atlas10_paired/paired.py
```

Rezultat benchmarka nastaje tek po završetku CI u `atlas10_paired_results/summary.json`; prije njegova vanjskog pregleda **ne prikazivati izmišljene rezultate, vremena ni brojeve uspjeha**. Izvorni proof/cert logovi ostaju u GitHub Actions artefaktu `DRNAS-ATLAS10-STRICT-30S-THREE-ARMS-3REPS`.
