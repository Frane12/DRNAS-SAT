# DRNAS STRUCTURE ATLAS 12 / 12B — GRAPH + HALL + EXACTLY-ONE, izvorno provjerljiv standardni dokaz

**Datum:** 22. studenoga 2026.  
**Eksperimentalna grana:** `experiment/atlas12-graph-hall-eo-bridge-20261122`  
**ATLAS 12 GitHub Actions, PASS:** https://github.com/Frane12/DRNAS-SAT/actions/runs/45013319196  
**ATLAS 12B GitHub Actions, PASS:** https://github.com/Frane12/DRNAS-SAT/actions/runs/45013625163  
**Status:** modularni izvorno provjerljiv izvod poznatog Hallovog/pigeonhole proturječja. `main` nije mijenjan.

## 1. Matematička pretpostavka

Neka izvorni CNF ima `d` međusobno varijabilno disjunktnih grupa s izvorno potvrđenim ALO klauzulama:

\[
\forall i\in\{1,\ldots,d\}\quad\bigvee_{x\in G_i}x.
\]

Neka sve odabrane varijable točno pokriva `c` resursnih grupa, a svaka resursna grupa ima u **izvornom CNF-u** potvrđenu zabranu za svaki par različitih alternativa:

\[
\forall j,\;\forall x\ne y\in R_j,\quad(\neg x\lor\neg y).
\]

Iz izvornih ALO klauzula slijedi \(\sum_{x\in\cup G_i}x\ge d\); iz resursnih mutex klika \(\sum_{x\in\cup R_j}x\le c\). Ako je \(d>c\), izvodimo \(0\ge1\), dakle UNSAT. To je postojeći, poznati Hall/pigeonhole argument. Same logičke činjenice bez original-source provjere nisu dovoljne.

## 2. Kako komuniciraju moduli

`research/atlas12_graph_hall/bridge.py` koristi već postojeći izvorno-zasnovani `research/graphclique/emit_veripb.py` za otkrivanje potpunog grafovskog `(k+1)`-klika obojenja s `k` boja. On proizvodi **samo izvorno SHA-vezani strukturni certifikat** u istom kanonskom formatu `DRNAS-source-clique-capacity-v1` koji prihvaća PCMAX/Hall modul. Sadržaj uključuje originalne disjunktne ALO klauzule i izvorno potkrijepljenu razdiobu svih njihovih varijabli u disjunktne mutex resursne klike.

Nezavisni `research/pcmax_capacity/check_php_partition.py` **ponovno učitava izvorne CNF klauzule** i potvrđuje svaku ALO i svaki pojedinačni mutex par, punu particiju svih traženih varijabli, broj grupa i deficit. Ne uvozi kod grafovskog pronalazača, ne vjeruje njegovom izlazu i ne koristi katalog UNSAT oznaku.

`research/pcmax_capacity/emit_veripb_source_clique.py` zatim na točnom **originalnom** CNF-u izdaje standardni VeriPB 3.0 cutting-planes dokaz. Tek vanjski **VeriPB 3.0.2** s izričitim `s VERIFIED UNSATISFIABLE` i kodom izlaza 0 može potvrditi UNSAT. `bridge.py` uvijek prijavljuje `PROOF_EMITTED_EXTERNAL_VERIPB_REQUIRED`, nikad sam ne tvrdi da je PBP već prihvaćen.

Izvorni EXACTLY-ONE dokaz razlikujemo od same ALO premise: u kontrolama su izvorne klauzule svih parova unutar svake grupe prisutne, pa ATLAS3 `source_facts.py` i nezavisni `check_facts.py` provjeravaju sve EO. **Na velikom originalnom grafovskom CNF-u imamo 0 izravno potvrđenih para AMO za izabrane grupe** — tamo je dokazani ulaz ALO + grafovski mutex, a dodatni EO semantički sloj ostaje otvoren jer je AMO kodiran pomoćnim klauzulama.

## 3. ATLAS12: stvarni, prethodno poznati grafovski original

Originalni CNF: `evidence/graph-k11/original.cnf`, SHA-256 `69d4e0ad868e920920d214acaf0c37f52870655ecc8a6807fd1ee3e4dcaa91e0`; **1.900 varijabli / 14.440 klauzula**.

- Graf modul rekonstruirao je source-verified 11-članu kliku s 10 boja.
- Hall/PCMAX-source checker neovisno je potvrdio 11 izvornih ALO zahtjeva i **10** izvorno kompletnih resursnih mutex klika: deficit 1.
- Standardni original-source PBP ima **5.841 bajt**.
- Vanjski VeriPB 3.0.2 **prihvatio je puni UNSAT dokaz** nad točnim CNF-om.
- Izvorno direktno potvrđenih EO grupa među izabranima: **0** (AMO pomoćno kodiran, pa nije opravdano prikazati dokaz izvornog direktnog EO).
- Ovo je RETROSPEKTIVNI original, već analiziran starijim grafovskim modulima, ne nova prije nepoznata UNSAT pobjeda.

Dodatni ATLAS12 kontrolni slučajevi: **pet** malih K(k+1) obojenja (k=2,3,4,5 plus jedna deterministička preimenovana varijanta), svih **5/5** puni original-source VeriPB UNSAT, s direktno potvrđenim EO za svaku izabranu ALO grupu. Pet kontrola negativnih/različitog oblika (između ostaloga eksplicitno zadovoljivi izvori i lažirani SHA certifikati) nije proizvelo pogrešan UNSAT.

GitHub run: [45013319196](https://github.com/Frane12/DRNAS-SAT/actions/runs/45013319196).

## 4. ATLAS12B: širenje izvan samoga klika-grafskog detektora

Drugi pokus ciljano konstruira **list-coloring** sustave s nepravilno raspodijeljenim dopuštenim resursima: na razini grupa nema izvornog potpuno usklađenog `(k+1))-klika koji prepoznaje stari GRAPH detektor, ali pozitivne ALO i izvorne grafovske mutex klauzule ipak znače da je svaka grupa obvezna, a svaka resursna klika može preuzeti najviše jednu istinitu alternativu.

`research/atlas12_graph_hall/unified.py` sada prvo pokušava GRAPH full-clique način. Samo ako on sigurno vrati UNKNOWN, na **istim neizmijenjenim izvornim klauzulama** pokreće `research/pcmax_capacity/source_php_real26.py`, koji prepoznaje izvornu particiju po konfliktnim susjedstvima. Izlaz se kompilira u isti, neovisno potvrđeni Hall certifikat i zatim standardni VeriPB original-source dokaz.

| Kontrolna konstrukcija | Potvrđeni izvorni EO zahtjevi | Graf detektor sam | Hall/PCMAX fallback | Vanjski VeriPB na originalu |
|---|---:|---|---|---|
| n=4 zahtjeva, k=3 resursa | 4 | UNKNOWN (nema punog klika) | 4>3 | **UNSAT VERIFIED** |
| n=5 zahtjeva, k=4 resursa | 5 | UNKNOWN (nema punog klika) | 5>4 | **UNSAT VERIFIED** |
| n=6 zahtjeva, k=5 resursa | 6 | UNKNOWN (nema punog klika) | 6>5 | **UNSAT VERIFIED** |
| Preimenovana n=4,k=3 instanca | izvorište matematički bijektivno | ista semantika | 4>3 | **UNSAT VERIFIED** |

**4/4** vanjski standardni dokazi prihvaćeni. U sva tri različita konstruirana slučaja zasebni grafovski detektor ostao je siguran UNKNOWN, a Hall fallback proizveo je source-verified puni dokaz. Ovo je provjerljivo proširenje **pokrivenosti zajedničkoga mode-selector sustava naspram GRAPH-only načina**, ali ne dokazuje novu sposobnost koja ranije nije postojala ni u Hall modulu zasebno.

Negativni sigurnosni slučajevi:
- Uklonjena jedna ključna izvorna konfliktna klauzula; konkretan puni model potvrdio je SAT i **oba** strukturna načina ostala su UNKNOWN.
- Isti uklonjeni mutex, ali lažni certifikat s **osvježenim točnim SHA** izmijenjenoga izvora — nezavisni Hall kontrolor odbio je premisu.
- Krivotvoreni izvorni SHA u certifikatu — također odbijen.

Sve su to **namjerno konstruirane male dokazne kontrole**, a ne neviđeni natjecateljski originali.

GitHub run: [45013625163](https://github.com/Frane12/DRNAS-SAT/actions/runs/45013625163).

## 5. Što je dokazano i koje je pravo sljedeće pitanje?

**Dokazano sada:** dvije već postojeće, izvorno-zasnovane istraživačke komponente mogu razmijeniti kanonske matematičke premise i proizvesti zasebno prihvaćen VeriPB original-source UNSAT; izvori nisu mijenjani, negativni SAT kontrole i krivotvorene premise odbijene. Dodatni Hall fallback uspijeva na konstruiranim slučajevima u kojima GRAPH-full-clique sam ispravno ostaje UNKNOWN.

**Još uvijek NIJE dokazano:** dokaziva inferencijska sinteza u kojoj su dva pojedinačna modula oba UNKNOWN, ali njihova **međusobna iterativna razmjena novih zaključaka** daje UNSAT. To mora biti glavni cilj budućeg ATLAS13 (izvorno validni ALO/AMO/GRAPH/XOR relacijski most, bez izmišljanja činjenica). Nije dokazana generalizacija na arbitrarne grafove, alternativna pomoćna kodiranja ni prednost nad Kissatom/CaDiCaL na unaprijed zamrznutom, međusobno neovisnom stvarnom uzorku druge obitelji.

## 6. Reprodukcija

```bash
# Kod u research/atlas12_graph_hall/
python3 research/atlas12_graph_hall/audit.py
python3 research/atlas12_graph_hall/audit_unified.py
```

Za programatsko izdavanje jedne original-source PBP izvorne formule:

```bash
python3 research/atlas12_graph_hall/bridge.py \
    --cnf original.cnf --certificate proof-source.json \
    --proof original.pbp --meta data.json

veripb --cnf original.cnf original.pbp
```

Za automatski odabir između punog GRAPH klika i HALL resource-clique načina `research/atlas12_graph_hall/unified.py`.

Fiksirani Github Actions artefakti `DRNAS-ATLAS12-GRAPH-HALL-EO-VERIPB` i `DRNAS-ATLAS12B-NONCLIQUE-GRAPH-HALL-EO-VERIPB` čuvaju izvorne CNF-ove, sve nezavisno provjerene standardne PBP-ove, kontrole SAT, source SHA, dokazne logove i infrastrukturne hashove. Nijedan rezultat nije promoviran u `main`.
