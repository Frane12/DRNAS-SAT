# DRNAS STRUCTURE ATLAS 9 — originalni javni maskirani XOR UNSAT, standardni VeriPB

**Datum:** 21. studenoga 2026.  
**Grana:** `experiment/atlas9-original-unsat-105-3-20261121`; `main` nije mijenjan.  
**Ciljana originalna CNF:** `mod2c-rand3bip-unsat-105-3.shuffled-as.sat05-2325.cnf.xz`, SAT Competition 2005 obitelj `random-graph-xorsat`.  
**GBD ID:** `07f5f3ca046261c3819c5c888ac837e5`; isohash `c76cc643e32004f5840c305a217d58de`.  
**Točan sirovi originalni SHA256:** `828a649666ddc6cd3bd9085821eb5058737f6a9e55c8904eff0681720e5938eb`.  
**Izvorna javna datoteka:** https://benchmark-database.de/file/07f5f3ca046261c3819c5c888ac837e5?context=cnf

## Zašto baš ovaj javni original?

ATLAS6/7B su neovisno rekonstruirali XOR sustave na **tri različite originalne javne SAT** formule iste maskirane obitelji. ATLAS8 je na malim **konstruiranim** SAT i UNSAT primjerima pokazao da iz originalno provjerene AND/XOR semantike može izvesti potpuni VeriPB RED/RUP/CP dokaz.

Prethodni originalni UNSAT izvor `073c28dfd3204f4c51e03c297ac841c1` iz starijeg GBD odabira nije bio dostupan i vraćao je HTTP 404. Novi izvor izabran je prema katalogu (bio je poznat kao UNSAT i označen kao raspoloživ), a GBD ID/iSO vrijednosti unaprijed su zapisani u `research/atlas9_original105/prespec.json` **prije preuzimanja i pokretanja detektora**. Nije naknadno zamijenjen prema ishodu.

To nije natjecanje s nepoznatom povijesnom oznakom SAT/UNSAT; **novi rezultat je provjerljiv automatski izvod dokaza na izvornom CNF-u**, ne prvo otkriće njegova UNSAT statusa.

## Original i source-only rekonstrukcija

GitHub izravno preuzima točan izvor iz prethodno određenog GBD ID-a, provjerava dimenzije te zapisuje sirovi SHA256 u `atlas9_original105_source/source-frozen.json` **prije** bilo kakvog detektorskog postupka.

| Mjera | Original / rekonstrukcija |
|---|---:|
| Izvorne Booleove varijable | **140** |
| Izvorne klauzule | **560** |
| Veličina izvornog DIMACS-a | **9.486 bajtova** |
| Automatski prepoznati potpisani AND parovi | **35** |
| Rekonstruirane virtualne varijable | **105** |
| Neovisno potvrđene skrivene XOR jednadžbe | **70** |
| Dokazni format | **VeriPB 3.0.2 RED/RUP/CP** |
| Potpun izvorni UNSAT dokaz | **50.534 bajta** |
| SHA256 izvorno prihvaćenog PBP-a | `68f6cdefcc5f706b73fe411ef3921b29bcd9016d915c1364ad925a2ea63bed3f` |

`semantic_and_xor.py` iz samih izvornih klauzula rekonstruira istu apsolutnu incidenciju parova, njihove točne potpisane AND orijentacije iz **kompletnih zabranjenih tablica**, te 70 tročlanih virtualnih XOR redaka. Neovisni `check_semantic.py` ponovno provjerava izvorni SHA, potpunost svih izvornih skupina klauzula i sve njihove male tablice, te točnu jednakost rekonstruiranog XOR kvocijenta.

Gaussova eliminacija pokazuje da je matematički rekonstruirani XOR sustav nedosljedan. To samo po sebi nije dovoljan izvorni standardni UNSAT certifikat, pa postojeći **neizmijenjeni** ATLAS8 `build_standard_original_proof` dodaje:
- RED svježe svjedoke za `q \leftrightarrow (literal_a \land literal_b)`;
- sve RUP guard međukorake za izvornu maskiranu jednadžbu;
- originalno potkrijepljene virtualne XOR klauzule;
- cjelobrojni GF2/paritetni cutting-planes zaključak do `0 \ge 1`.

Zatim neovisni **vanjski VeriPB 3.0.2** čita **potpuno neizmijenjeni originalni javni CNF** i vraća `s VERIFIED UNSATISFIABLE` bez vjerovanja generatoru ili internom detektoru.

## Potvrdni testovi i varijacije

| Ulaz | Matematički rezultat | Standardna provjera |
|---|---|---|
| Originalni SAT05 `unsat-105-3` | 35 AND, 70 XOR, nedosljedan GF(2) | **VERIPB VERIFIED UNSAT** |
| Preimenovanje/permutacija, sjeme 617 | isti maskirani matematički sustav | **VERIPB VERIFIED UNSAT** |
| Drugo bijektivno preimenovanje + promjene polariteta, sjeme 829 | isti maskirani matematički sustav | **VERIPB VERIFIED UNSAT** |

Svaki permutirani CNF ponovno je rekonstruiran bez originalne pomoćne mape u detektoru. Njegova ekvivalentnost izvorniku zasebno je potvrđena poznatim točnim inverznim preslikavanjem svih izvornih klauzula, a **VeriPB je ponovno samostalno provjerio dokaz na samom permutiranom CNF-u**.

Negativne kontrole originalne semantike:
- lažirani SHA izvora -> nezavisni provjerivač odbacuje;
- fizički izbrisana klauzula uz ažurirani SHA u tvrdnji -> odbacuje;
- pogrešna orijentacija jednog maskiranog AND-a -> odbacuje.

## Transparentnost dosadašnjeg CI-a

Prvi proof-run https://github.com/Frane12/DRNAS-SAT/actions/runs/44957239513 već je izdao **3/3 vanjski prihvaćenih standardnih VeriPB dokaza**, ali posljednja programska kontrola vlastitog sažetka pogrešno je tražila nepostojeće polje `original_veripb_strict` umjesto `standard_original_veripb_verified` i označila CI kao FAILED. Nije bilo odbijanja formalnog dokaza; ispravljena je samo programska provjera završnog rezultata i ponovno pokrenut isti potpuno fiksirani izvor na novom CI-u: https://github.com/Frane12/DRNAS-SAT/actions/runs/44957373323.

**Brzine nisu upareno uspoređivane s Kissatom, CaDiCaL-om ili CMS-om.** E2E u izvornom Python auditu (~0,02–0,03 sekunde za pojedinu formulu, uključujući dokaz i checker nakon učitavanja) ne obuhvaća GitHub checkout, preuzimanje ni instalaciju VeriPB-a. Prije tvrdnje o ubrzanju potreban je isti CPU/cap, tri ponavljanja, provjera modela/dokaza za sve ruke.

## Učenje opće zakonitosti: idući cilj

Ovo je **prvi javni izvorno neizmijenjeni UNSAT** maskiranog XOR-a koji je ATLAS9 dokazao standardnim postupkom, uz ranija tri originalna SAT rješenja i sintetičke SAT/UNSAT kontrole. Konstrukcija XOR/AND i GF(2) teorem su poznati; predmet znanstvenog doprinosa je automatska rekonstrukcija iz općeg sirovog CNF-a i siguran dokazni transport.

Sljedeći koraci trebaju provjeriti druge već zamrznute javne UNSAT originale s drukčijim brojem AND maski, veličinama XOR sustava i različitim lokalnim kodiranjem. Uz potpunu original-source sigurnost, mjeriti **stvarni novi verificirani obuhvat i trošak** u odnosu na suvremene solver reference. Nije dokazana univerzalna normalizacija svih CNF-ova.

## Reproducibilnost

```bash
python3 research/atlas9_original105/freeze.py
python3 research/atlas9_original105/audit.py
```

Github workflow: `.github/workflows/atlas9-original-unsat105.yml`, CI artefakt `DRNAS-ATLAS9-GBD-UNSAT105-ORIGINAL-VERIPB` (frozen raw original, proof, semantic source certificates, two permutation proofs, negative controls, CPU i SHA izvještaji).
