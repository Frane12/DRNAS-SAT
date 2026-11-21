# DRNAS STRUCTURE ATLAS 7B — ponovna provjera na dva druga ORIGINALNA maskirana XOR SAT problema

**Datum:** 21. studenoga 2026.  
**GitHub CI završni audit:** https://github.com/Frane12/DRNAS-SAT/actions/runs/44953060033  
**Status:** PASS; izvorni SAT modeli neovisno provjereni na dvama ranije neanaliziranim originalima i na četiri njihove permutacije. **Nisu mijenjana pravila detektora iz ATLAS6**, samo je pokrenut na drugim izvorima. Produkcijski `main` je netaknut.

## Prespec i neuspjeli troslučajni izvorni pokus

Prvo je **prije bilo kakvog ATLAS7 detektorskog pokretanja** fiksiran skup od tri javna GBD izvora, dva poznata SAT i jedan poznati UNSAT. Taj je pokušaj ispravno prekinut jer je treći GBD original `073c28dfd3204f440015b21e85359ef082a44d2` vraćao **HTTP 404 na sva tri pokušaja preuzimanja**. Nije zamijenjen drugim UNSAT izvorom i nije pripisan nikakav solver rezultat: [neuspjeli samo-izvorni CI](https://github.com/Frane12/DRNAS-SAT/actions/runs/44952863254).

Zatim je zasebno označena serija ATLAS7B s **oba dostupna prethodno fiksirana** izvorna GBD ID-a. Njihovi su SHA-256 iz prvog preuzimanja dodatno zaključani u `research/atlas7_two/prespec.json` **prije** izvođenja ATLAS7B detektora. Takav potpun, javno dokumentiran postupak nije izvorni idealni troslučajni prospektivni skup; riječ je o zasebnom dvostrukom izvornom testu s transparencijom o razlogu izbora.

## Stvarna pitanja i izvori

Dva izvora potječu iz SAT Competition 2005 obitelji maskiranih logičkih sustava temeljenih na nasumičnim 3-regularnim bipartitnim grafovima, ponovno indeksiranih u GBD. Oba imaju poznat javni SAT status, **ali ni jedna oznaka, naziv datoteke ni očekivani odgovor nisu predani detektoru**.

| Original GBD | SHA-256 sirovog CNF-a | Varijable | Klauzule |
|---|---|---:|---:|
| `0462a0427297f8979588174b502bd044` | `9794f4cbff9f0e1136b5711a88d58bc7eabdcc1e78fb2594dd50e9bac8a5bc0f` | 322 | 2.220 |
| `1b0780e82e41f6ca9c6c2f37b5350789` | `935b7936ef02e2029d9d08e04f6ee4e76117351b0ffd37280b7427a51910dfa6` | 311 | 2.216 |

## Potpuni izvorno provjereni rezultati

| Izvor | Izvorni skriveni AND parovi | Virtualne varijable | Rekonstruirane GF(2) jednadžbe | Izvorni SAT model |
|---|---:|---:|---:|---|
| SAT230-1 | **92** | **230** | **230** | **2.220/2.220 klauzula zadovoljeno** |
| SAT220-1 | **91** | **220** | **220** | **2.216/2.216 klauzula zadovoljeno** |

Uz original svaka formula ima dvije determinističke bijektivno ekvivalentne varijante: preimenovanje i preslagivanje, te drugo preimenovanje + promjene polariteta. Svaki je iznova riješen **bez prijenosa originalne mape**, a `check_semantic.py` samostalno provjerava sve izvorne truth-table premise, virtualni XOR CNF i svih 2.220/2.216 originalnih klauzula konkretnog modela.

- **6/6** ukupno potpunih izvornoklauzulnih SAT modela, svi neovisno prihvaćeni.
- **6/6** punih source-semantic AND/XOR izvornih podstruktura ponovno verificirano.
- **0** lažnih dovršenih SAT modela; **0** tvrdnji o standardnom original-source VeriPB UNSAT certifikatu (nijedna testirana dostupna formula nije bila poznata UNSAT izvor).
- Originalne matematičke analize s neovisnom provjerom unutar iste lokalne Python procedure: SAT230-1 **0,067404 s**, SAT220-1 **0,069755 s**; dodatne četiri varijante između **0,0670 i 0,0737 s**. Bez vremena preuzimanja, GitHub pripreme i usporedbe s Kissatom.

## Što sada doista znamo

ATLAS6 + ATLAS7B: **tri različita originalna** `mod2c-rand3bip-sat` SAT izvora, veličina 250, 230 i 220 virtualnih varijabli, svaki matematički rekonstruiran iz neizmijenjenog izvornog CNF-a. Za sve originale plus ukupno **7 kontroliranih permutacija** postoje SAT modeli provjereni protiv **svake njihove originalne klauzule**.

Ovo potvrđuje **stvarnu generalizaciju unutar jedne poznate obitelji kodiranja**, ne automatsku generalizaciju među svim problemskim obiteljima ili preko proizvoljnih nepoznatih kodiranja. Izvorna AND-maskirana XOR konstrukcija i standardna Gaussova eliminacija poznate su prije DRNAS projekta; ovdje je potvrđena sigurnost praktične *automatske rekonstrukcije iz sirovog CNF-a*, uključujući neovisne source-truth-table provjere.

## Sljedeći znanstveni uvjet

Nakon ovog potvrđenog SAT rezultata na istoj obitelji slijedi stvarni originalni UNSAT izvor s neovisno provjerenom AND/XOR rekonstrukcijom i, presudno, pokušaj izvoza **standardnog original-source VeriPB/DRAT dokaza**. Sam GF(2) kontradikcijski svjedok na virtualnom kodiranju nije zamjena za standardni dokaz na neizmijenjenom originalnom CNF-u.

Nadalje birati originalne obitelji gdje skriveno ograničenje nije sintaktički AND/XOR nego primjerice sekvencijalni kardinalni brojač, BDD kapacitet ili grafovski all-different. Novi izvori trebaju biti odabrani i zamrznuti prije pregleda rezultata, bez zamjene po željenom ishodu.

## Reprodukcija

```bash
python3 research/atlas7_two/freeze.py
python3 research/atlas7_two/audit.py
```

Originalni kod za matematičku rekonstrukciju i neovisni checker ostaje `research/atlas6_camouflage/semantic_and_xor.py` i `research/atlas6_camouflage/check_semantic.py`. Dodatni CLI workflow `.github/workflows/atlas7b-two-sources.yml`.

GitHub Actions artefakt `DRNAS-ATLAS7B-TWO-ACCESSIBLE-ORIGINAL-CAMOUFLAGED-XOR-SAT` sadrži oba stvarna originalna CNF-a, šest original-source/SAT-model potvrda, sve logove, izvorne SHA i argumente eksperimenta.
