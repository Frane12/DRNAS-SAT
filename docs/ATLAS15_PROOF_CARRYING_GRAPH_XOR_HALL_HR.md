# DRNAS STRUCTURE ATLAS 15 — dokaziva razmjena matematičkih činjenica GRAPH + XOR + HALL

**Datum:** 22. studenoga 2026.  
**GitHub eksperimentalna grana:** `experiment/atlas15-proof-fact-exchange-20261122`. `main` je netaknut.  
**GitHub Actions konačni PASS:** https://github.com/Frane12/DRNAS-SAT/actions/runs/45016993709  
**Status:** 4/4 vanjski VeriPB 3.0.2 standardno verificirana UNSAT dokaza na potpuno originalnim **konstruiranim** CNF-ovima; tri različite konstrukcije i jedna bijektivno preimenovana varijanta. Negativni SAT kontrolni primjer ima provjeren model. Četiri već ranije objavljena stvarna originala na novom prepoznavaču ostaju `UNKNOWN`.

## 1. Istraživačko pitanje i odnos na ATLAS13/14

ATLAS13 je pokazao da graf dvovarijabilnih implikacija može predati izvorno dokazivu binarnu zabranu HALL-u koji tek potom može izvesti nedostatak kapaciteta. Ali to je bila **dva modula**, a ATLAS14 na pet povijesnih stvarnih originala nije pokazao novu pokrivenost te arhitekture.

**ATLAS15 postavlja stroži zahtjev:** konstruirati i testirati CNF u kojem **GRAPH+HALL** sam ne uspijeva, **XOR+HALL** sam ne uspijeva, a **GRAPH+XOR+HALL** na *istom potpuno neizmijenjenom izvornom CNF-u* izvozi standardni dokaz koji potvrđuje neovisan checker.

To je teza o funkcionalnom **međuovisnom prijenosu dokazivih činjenica između istraživačkih modula**, a ne novi teorem o složenosti ili tvrdnja da nijedan drugi opći SAT algoritam ne može sam riješiti ove male primjere.

## 2. Zajednički format izvorno dokazive matematičke činjenice

Modul `research/atlas15_exchange/facts.py` čita samo sirovi originalni DIMACS — ne naziv obitelji, ne predviđeni SAT/UNSAT i ne staro rješenje — i emitira skup tipiziranih činjenica `DRNAS-ATLAS15-FACT-TRANSFER-v1` koji nosi SHA-256 izvornika, broj varijabli i klauzula, deklarirani izvorni implikacijski put ili kompletnu XOR3 tablicu, te par izvornih selektora `a,b`.

### A. GRAPH činjenica

Iz izvornih parova

\[
(\neg a\lor t),\qquad(\neg t\lor\neg b)
\]

logički nužno slijedi

\[
a\Rightarrow t\Rightarrow\neg b\quad\Longrightarrow\quad
\boxed{\neg a\lor\neg b}.
\]

To je original-source RUP lema, ne proizvoljno pretpostavljeni izvorni mutex. Pomoćna varijabla `t` ne pripada izvornim ALO grupama.

### B. XOR3 činjenica

Iz **potpune četiri klauzule koje kodiraju izvornu paritetnu jednadžbu**

\[
a\oplus b\oplus u=0
\]

i doslovne izvorne jedinične klauzule \(u=1\) slijedi

\[
a\oplus b=1
\quad\Longrightarrow\quad
\boxed{\neg a\lor\neg b}.
\]

**Važna preciznost:** izvorni XOR odnos ovdje podrazumijeva *točno jednu* od \(a,b\) kao istinitu, dakle jači je od mutex zabrane koju predajemo Hallu. `facts.py` smije izvesti ovaj mutex isključivo nakon pronalaska sve **četiri doslovne forbidden-assignment klauzule** i točne jedinične klauzule iz originala; nije dovoljno ime formule ili približno prepoznavanje XOR-a.

### C. HALL kapacitet

Iz izvornika postoje `d` međusobno disjunktnih obveznih ALO grupa. Za dobivene resursne klike vrijedi

\[
\sum x_i\ge d,\qquad \sum x_i\le c.
\]

Kada stignu **SVE** potrebne izvorno dokazane GRAPH i XOR mutex leme, Hall rekonstruira potpune resursne kapacitete i za \(d>c\) izvodi proturječje.

## 3. Neovisna verifikacija činjenica i standardni dokazni transport

`research/atlas15_exchange/witness.py` samostalno ponovno čita originalne klauzule; ne uvozi detector `facts.py`, Hall engine ili proof compiler. Za svaku prenesenu činjenicu:

1. Neovisno provjerava SHA-256 izvornog CNF-a i potpuni DIMACS broj klauzula.
2. Potvrđuje da su `a,b` različiti izvorni selektori iz različitih pozitivnih ALO grupa.
3. Za GRAPH činjenicu ponovno potvrđuje obje točne izvorne binarne klauzule i korake implikacije.
4. Za XOR činjenicu ponovno potvrđuje sva četiri izvorna retka potpune XOR3 tablice i jedinicu \(u=1\).
5. Zasebnim algoritmom **unit propagacije na originalnom CNF-u pod pretpostavkom \(a=b=1\)** potvrđuje RUP kontradikciju; sama strukturna tvrdnja nije dovoljna.
6. Ne prihvaća duplikate, nepravilne granice varijabli, izmijenjeni izvor ili proizvoljno izmišljene premise.

`research/atlas15_exchange/bridge.py` zatim gradi *internu* kopiju originalnih klauzula + samostalno provjerene leme. Za tu kopiju radi odvojeni, postojeći `research/pcmax_capacity/check_php_partition.py`, a `emit_veripb_source_clique.py` iz nje izvodi CP Hall dokaz.

**Interna kopija NIJE smjela biti proglašena izvornim UNSAT-om.** Zato se konačni PBP preuređuje na originalni broj CNF klauzula, a na početak se ubacuju **standardne `rup` naredbe za SVAKU novu GRAPH/XOR lemu** u točnom redoslijedu privremenih dokaza. Numerički indeksi kasnijih CP koraka ostaju isti jer su `rup` izvodi dodani baš na mjesta pomoćnih izvornih klauzula.

Samo vanjski **VeriPB 3.0.2** izvršen kao `veripb --cnf ORIGINAL.cnf ORIGINAL.pbp` i koji vrati kod 0 i `s VERIFIED UNSATISFIABLE` smije odobriti `STRICT UNSAT`. Nijedan interni checker ne može zamijeniti taj završni uvjet.

## 4. Stvarna GitHub mjerenja — 22. studenoga

| Konstruirani izvorni CNF | DIRECT GRAPH+HALL | XOR+HALL | GRAPH+XOR+HALL | GRAPH i XOR leme | Original-source VeriPB |
|---|---|---|---|---|---|
| 5 ALO zahtjeva / 4 resursa, 16 varijabli, 46 klauzula | UNKNOWN | **UNSAT** | **UNSAT** | 0 GRAPH + 1 XOR | ACCEPTED, 361 B |
| 6 ALO zahtjeva / 5 resursa, 26 varijabli, 95 klauzula | UNKNOWN | UNKNOWN | **UNSAT** | 1 GRAPH + 1 XOR | ACCEPTED, 647 B |
| Isti n=6 nakon neovisnog bijektivnog preimenovanja | UNKNOWN | UNKNOWN | **UNSAT** | 1 GRAPH + 1 XOR | ACCEPTED, 650 B |
| 7 ALO zahtjeva / 6 resursa, 38 varijabli, 175 klauzula | UNKNOWN | UNKNOWN | **UNSAT** | 1 GRAPH + 2 XOR | ACCEPTED, 1.091 B |

Dodatno je sam prethodni `GRAPH_ONLY` (potpuna grafovska klika) na sve četiri formule ostao UNKNOWN, a sam `HALL_DIRECT_ONLY` bez izvorno izvedenih zabrana također UNKNOWN. Podsustav izvornih binarnih klauzula ima jednostavan **all-false** model i nije sam po sebi puni UNSAT dokaz.

**4/4** standardna original-CNF UNSAT potvrda; **ukupno osam** prenesenih činjenica kroz četiri izvođenja (3 GRAPH + 5 XOR). Na tri izvođenja s dva tipa skrivenih ograničenja (`k5`, `k5` preimenovan i `k6`) oba parcijalna para `GRAPH+HALL` i `XOR+HALL` ostaju UNKNOWN, dok je potpuna matematička sinteza prihvaćena.

Cijene samo vanjske standardne verifikacije na tim sintetičkim mikroprimjerima iznose ~0,0033–0,0036 s. Te brojke **nisu** parni natjecateljski benchmark ili dokaz brzinske prednosti.

## 5. Namjerno zadovoljivi kontrolni slučaj

Za najveći kontrolirani izvor obrisana je točno **jedna ključna XOR3 forbidden-assignment klauzula**, dok su sve druge originalne premise sačuvane. Nova formula više ne podrazumijeva taj mutex i postaje **SAT**; izračunata je potpuna dodjela koja zadovoljava svaku od **174** stvarne klauzule. **Potpuni source-SHA-vezani model** arhiviran je u `source-mutation-SAT/source-SAT-model.json`, a *zasebni* `witness.py::verify_full_original_sat_model` ponovno je parsirao sve klauzule bez uvoza generatora i prihvatio model. Evidencija je arhivirana u `source-mutation-SAT/independent-SAT-check.json`.

- XOR producent vidi samo preostalu cjelovitu XOR3 tablicu (jedan je dokazni red namjerno nepotpun).
- Namjerno ponovno korišten stari certifikat s **novim ispravnim SHA izvora** ne prolazi neovisnu source-XOR premisnu provjeru.
- Drugi certifikat s izmišljenim SHA također je odbijen.

To je nužna zaštita od zaključivanja UNSAT na temelju prepoznatljive ali **nepotpune** strukture.

## 6. Ponovna provjera četiri ranije poznata stvarna originala

Bez korištenja spremljenih rješenja pri zaključivanju, isti ATLAS15 izvorni GRAPH+XOR+HALL prepoznavač pokrenut je na:

| Već poznati stvarni original | Novi ATLAS15 rezultat |
|---|---|
| `evidence/graph-k11/original.cnf` | **SAFE UNKNOWN** |
| `evidence/pcmax-weighted2/00/original.cnf` | **SAFE UNKNOWN** |
| `evidence/xor234-grid5/original.cnf` | **SAFE UNKNOWN** |
| `evidence/ipg7b-petersen/original.cnf` | **SAFE UNKNOWN** |

Ovi originali imaju stare standardno valjane VeriPB dokaze, ali **ne u novom ATLAS15 zajedničkom uskom prepoznavaču**. Njihova automatska rekonstukcija zahtijeva širi, siguran format izvođenja izvora (BDD kapaciteti, pomoćno kodiran XOR i IPG globalna konfiguracija). Ne pripisivati ATLAS15 uspjeh drugih starih modula!

## 7. Znanstveni rezultat i ograničenja

**Potvrđeno:** originalni, izvorno dokazivi GRAPH i XOR3 zaključci mogu se sigurno prenijeti u Hall na jednom općem, tipiziranom proof-carrying kanalu; postoje kontrolirani primjeri gdje je **svaka dvomodulska kombinacija nedostatna**, a trostruka kombinacija valjano dobiva standardni original-CNF UNSAT. Neovisni izvorni provjerivač plus vanjski VeriPB potvrđuju sve prenesene premise, njihovu ugradnju i konačni zaključak.

**Nije potvrđeno:** znanstveno nova Hallova ili XOR teorema; P=NP; općenito polinomijalno rješavanje SAT-a; prednost naspram Kissata/CaDiCaL-a na proizvoljnim izvorima; ni uspjeh ovoga uskog prepoznavača na četiri već poznata stvarna originala. Proizvodnja konstruiranih primjera poznaje matematički uzorak, ali **detektori ne primaju taj opis** kao ulaz.

**Sljedeći strogi eksperiment:** usvojiti tipizirani kanal bez gubitka soundnessa i uključiti već postojeći izvorno zasnovani PCMAX BDD kapacitetni modul (s vlastitim VeriPB koracima), ali ne pretpostavljati da se proizvoljni izvorni Hall mutex može izvesti iz BDD-a. Potom zamrznuti originalne javne probleme miješanih domena, i odvojeno mjeriti `GRAPH`, `XOR`, `CAPACITY`, `GRAPH+XOR+CAPACITY`, te standardne reference u jednakim E2E limitima, ne izostavljajući UNKNOWN.

## 8. Reprodukcija

```bash
python3 research/atlas15_exchange/audit.py
```

Za jedan izvorni CNF, kada se na njemu prepoznaju točne premise:

```bash
python3 research/atlas15_exchange/bridge.py \
  --cnf ORIGINAL.cnf \
  --mode TRIPLE_HALL \
  --claims source-facts.json \
  --proof original.pbp \
  --meta telemetry.json

veripb --cnf ORIGINAL.cnf original.pbp
```

Workflow `.github/workflows/atlas15-proof-fact-exchange.yml`, GitHub [run 45016993709](https://github.com/Frane12/DRNAS-SAT/actions/runs/45016993709) i arhiva `DRNAS-ATLAS15-GRAPH-XOR-HALL-PROOF-EXCHANGE` čuvaju izvorne CNF-ove, dokazne source-fact certifikate, originalne VeriPB PBP-ove, SHA izvora, negativni SAT model i sve opažene UNKNOWN rezultate. Nema promjena glavne grane.
