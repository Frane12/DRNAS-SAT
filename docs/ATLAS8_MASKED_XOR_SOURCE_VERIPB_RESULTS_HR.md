# DRNAS SAT — ATLAS8: maskirani XOR, standardni VeriPB UNSAT na izvornom CNF-u

**Datum:** 21. studenoga 2026.  
**GitHub Actions:** https://github.com/Frane12/DRNAS-SAT/actions/runs/44955708511  
**Eksperimentalna grana:** `experiment/atlas8-masked-xor-unsat-proof-20261121`; `main` nije mijenjan.  
**Rezultat:** **PASS**. Šest standardnih VeriPB 3.0.2 UNSAT dokaza na izvornim generiranim CNF-ovima + tri permutirana original-source VeriPB UNSAT + šest neovisno provjerenih SAT kontrola. Svi ulazi ovog testa su **sintetičke kontrolne konstrukcije**, ne novi stvarni natjecateljski UNSAT benchmarkovi.

## Motivacija

ATLAS6/7B već su dokazivo rekonstruirali AND-maskirani XOR na trima različitim originalnim SAT natjecateljskim formulama. Posljednji neuspio izvorno fiksirani tročlani holdout za SAT/SAT/UNSAT (run 44952863254) prekinut je prije detektorskog pokretanja jer je treći UNSAT GBD izvor javljao HTTP 404. Nije zamijenjen.

ATLAS8 ispituje **može li se iz dokazane izvornoklauzulne semantike AND-maskiranja sastaviti standardni VeriPB dokaz na izvornom, neizmijenjenom CNF-u**, bez prihvaćanja samo projekcijskog certifikata. Zato koristimo tri mala kontrolirana grafovska izvora (`K4`, trokutasta prizma i `K3,3`) s dvije unaprijed zadane varijante sjemena i parovima SAT/UNSAT.

## Source-only matematički lanac

U svakoj izvornoj formuli postoji podjela na virtualne varijable `z_e`. Određeni izvorni Booleovi literali predstavljaju `z_e = literal_a AND literal_b`, drugi su pojedinačne varijable. Svaka od izvornih skupina klauzula iscrpno predstavlja maskirani troargumentni XOR:

```
z_e XOR z_f XOR z_g = b_v
```

Samo ako `check_semantic.py` neovisno ustanovi **točnu jednakost svih izvornih truth-tablica** sa svim izvornim klauzulama i provjeri generirani kvocijent, prelazimo na standardni proof emitter.

Za UNSAT kontrolu odabiremo graf u kojem je svaka virtualna varijabla brid koji sudjeluje u **dvije jednadžbe** (oba krajnja čvora) te je XOR svih desnih strana **1**. Zbrajanje redaka daje `0=1`.

Ali ovaj projektni GF2 argument sam po sebi nije dopušten UNSAT certifikat izvornog CNF-a. Zato se proizvodi **standardni VeriPB 3.0 dokaz od originalnih klauzula**:

1. `RED`: uvesti svježu varijablu `q` sa tri dokazane definicijske klauzule za `q <-> (a AND b)`.
2. `RUP`: iz svake potpune izvorne AND/XOR tablice eksplicitno izvesti uvjetne implikacije za `a` i `b` kada virtualni `q` mora biti istinit.
3. `RUP`: iz izvora i tih dokazanih implikacija izvesti sve zabranjene XOR3 klauzule za virtualne `q` varijable. Niti jedna takva klauzula se **ne pretpostavlja unaprijed kao izvorna**.
4. `RED/RUP/CP`: poznatim, prethodno testiranim XORLIN1 proof compilerom dobiti cjelobrojne paritetne relacije i konačnu kontradikciju.
5. **Vanjski VeriPB 3.0.2** provjerava svaku izvedenu klauzulu, RED ekstenzije i cijeli zaključak **protiv originalnog neizmijenjenog maskiranog CNF-a**, ne protiv sintetiziranog kvocijenta.

Za SAT kontrole koristi se dosadašnji neovisni source checker koji potvrđuje originalnu AND/XOR semantiku i **svaki literal svih izvornih klauzula** za dobiveni SAT model.

## Prvi neuspjeh i njegov uzrok

Prva potpuna standardna provjera (run https://github.com/Frane12/DRNAS-SAT/actions/runs/44955553889) prijavila je na prvi pokušaj `k4-111-unsat`: `Verification error ... constraint is not implied by RUP` na prvom virtualnom XOR retku. Ovo nije bio prihvaćen dokaz. Uzrok: kada je izlaz AND-maske lažan, sama definicija `q=a AND b` ne daje dovoljno jedinične propagacije za izvođenje pune XOR klauzule. Dodane su dvije izvorno opravdane RUP implikacije s odgovarajućim ostalim virtualnim literalima kao guard uvjetima. **Tek nakon toga** je vanjski VeriPB prihvatio cijeli dokaz.

To je konkretna razlika između valjane matematičke semantičke rekonstrukcije i provjerljivog dokaznog transporta.

## Rezultati GitHub audita (jedna logička CPU jezgra)

| Grafovski oblik | Broj virtualnih XOR redaka | Izvorne varijable | Izvorne klauzule | SAT kontrole | UNSAT original-source standardni VeriPB |
|---|---:|---:|---:|---:|---:|
| `K4` | 4 | 8 | 32 | 2/2 verified | **2/2 verified** |
| Trokutasta prizma | 6 | 12 | 48 | 2/2 verified | **2/2 verified** |
| `K3,3` | 6 | 12 | 48 | 2/2 verified | **2/2 verified** |
| **Zbroj** | | | | **6/6** | **6/6** |

Tri dodatne bijektivno ekvivalentne permutacije UNSAT izvora `K4 seed 111`, s preimenovanjem i promjenama polariteta: **3/3** zasebna standardna VeriPB dokaza prihvaćena protiv točno tih izmijenjenih izvornih formula.

Negativne kontrole: jedna izvorna klauzula izbrisana i izvorni SHA ažuriran u staroj tvrdnji -> nezavisni izvorni checker odbija. Stari `PBP` predan izmijenjenom izvoru -> vanjski VeriPB također odbija. **2/2** sigurnosna odbijanja.

Uži izmjereni wall-time samog vanjskog VeriPB checkera na ovim mikroprimjerima otprilike **0,003–0,005 s**. To **nije** potpuni benchmark niti mjeri odabir pravila i generiranje dokaza na većim izvornim instancama.

## Što smo pokazali, a što tek trebamo pokazati?

**Potvrđeno:** maskirana izvorno-kodirana XOR formula može se **iz izvornog CNF-a** rastaviti u dokazivo semantički ekvivalentne AND/XOR redove; na tri kontrolirana grafovska oblika (dva sjemena) naš dokazni transport izvodi potpun standardni UNSAT, a ne samo posebni projektni GF2 svjedok. Paralelno SAT kontrole dobivaju original-source verified model. Permutacije i negativne kontrole prolaze.

**Nije potvrđeno:** standardni UNSAT na novoj javnoj realnoj maskiranoj XOR instanci. Ovdje su svi UNSAT izvori namjerno **generirani**, s najviše jednim maskiranim AND tokenom po izvornoj XOR jednadžbi, i znamo matematičku konstrukciju. Šira pravila s više AND parova po retku, pomoćnim kodiranjem, većim klauzulama ili nepoznatim industrijskim semantikama nisu obrađena. Ne tvrditi općenit SAT algoritam ili empirijsku prednost nad Kissatom/CaDiCaL.

**Sljedeće:** bez prilagodbe pravila na ishod prethodno zamrznuti novi originalni UNSAT maskirani XOR izvor, provjeriti dostupnost izvora i original-source standardni VeriPB, napraviti SAT/UNSAT/UNKNOWN uparene ruke sa standardnim solverskim referencama pod istim E2E limitom. Ako izvor nije dostupan, zadržati transparentni NO-SOURCE, ne zamijeniti ga radi željenog rezultata.

## Reprodukcija

```bash
python3 research/atlas8_masked_unsat/audit.py
```

Za samostalne slučajeve generator i izvozni modul `research/atlas8_masked_unsat/proof.py`. Neovisni original-source truth-table checker: `research/atlas6_camouflage/check_semantic.py`; javno dostupni standardni checker `veripb` v3.0.2.

GitHub artefakt `DRNAS-ATLAS8-MASKED-XOR-UNSAT-VERIPB-CONTROLS` uključuje **originalne generirane CNF-ove, svaki standardno prihvaćeni PBP, model SAT kontrola, neovisne certifikate, logove i SHA vrijednosti**.
