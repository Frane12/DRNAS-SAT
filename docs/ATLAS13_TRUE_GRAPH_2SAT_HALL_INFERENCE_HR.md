# DRNAS SAT — STRUCTURE ATLAS 13: dokaziva komunikacija GRAPH → HALL

**Datum:** 22. studenoga 2026.  
**Grana:** `experiment/atlas13-inference-exchange-20261122` (bez promjene `main`).  
**GitHub Actions:** [45014432105 — SUCCESS](https://github.com/Frane12/DRNAS-SAT/actions/runs/45014432105).  
**Status:** **4/4 vanjski prihvaćeni standardni VeriPB 3.0.2 UNSAT dokazi na neizmijenjenim izvornim CNF-ovima**. Tri različita konstruirana problema i jedna neovisno preimenovana verzija. Nijedna konstrukcija nije neviđeni natjecateljski original.

## 1. Zašto ovo nije samo ATLAS 12B s drugim imenom?

ATLAS12B je pokazao da GRAPH full-clique detektor može biti UNKNOWN, a zasebni Hall izvorni detektor već može sam dokazati UNSAT. To je **korisno pokrivanje više načina rješavanja**, ali ne matematička ovisnost između njihovih dokazanih činjenica.

ATLAS13 strože zahtijeva da na ISTOM originalu:

1. Dosadašnji zasebni `GRAPH_CLIQUE` način **ne može potvrditi potreban potpuni klika-uzorak** i konzervativno vraća UNKNOWN.
2. Izvorni `HALL_DIRECT` bez novih izvoda **ne vidi potrebnu potpunu resursnu mutex kliku**, stoga vraća UNKNOWN; postojeći `source_php_real26.py` također ostaje UNKNOWN.
3. Dio izvornog problema koji čine samo binarne klauzule izričito je **zadovoljiv all-false modelom**, tako da sami grafovi 2-SAT implikacija ne nose potpuno UNSAT rješenje.
4. Izvorni dvorazinski graf implikacija pronalazi novu klauzulu `(¬a∨¬b)`, čiji je **točan dvokorak potvrđen izvorom**, i šalje je Hallu.
5. Tek Hall koji primi sve izvorno potkrijepljene zabrane može utvrditi `d>c` i izdati standardan original-source dokaz.
6. Vanjski VeriPB ne vjeruje matematičkom opisu; on provjerava i **RUP svake nove klauzule** i cjelokupni Hall cutting-planes dokaz protiv **originalnog, neizmijenjenog CNF-a**.

To je dokaziva **komunikacija zaključaka između modula**, ne samo programski `if/else` za odabir postojećeg solvera.

## 2. Nova dokaziva činjenica: 2-SAT graf izvodi nedostajući mutex

Iz originalnih binarnih klauzula:

\[
(\neg a\lor t),\qquad(\neg t\lor\neg b)
\]

slijedi graf implikacija

\[
a\implies t\implies\neg b.
\]

Dakle, cijeli izvor podrazumijeva:

\[
\boxed{\neg a\lor\neg b}.
\]

Ključni detalj: **ta klauzula NIJE bila izvorna**. Izvorni GRAPH/2SAT modul mora predati Hallu dokazivo izvedenu novu zabranu, uz `source_sha256` i točnu putanju između izvornih klauzula. Neovisni `research/atlas13_exchange/witness_checker.py`, koji ne uvozi producer, provjerava sam originalni DIMACS, obje izvorne premise i točno članstvo pozitivnih varijabli u zasebnim ALO grupama.

Zatim Hall grupira odabrane varijable prema svim provjerenim resursnim zabranama i dobiva:

\[
\underbrace{\sum x_i}_{\text{obvezni ALO zahtjevi}}\ge d,
\qquad
\underbrace{\sum x_i}_{\text{kapacitet mutex resursa}}\le c.
\]

Za `d>c` to daje proturječje. Hallovo otkrivanje posebno provjerava da su resursne grupe potpune, da je pokrivenost disjunktna i da su svi iskorišteni odabiri isti.

### Dokazni transport — bitna novost integracije

Postojeći `emit_veripb_source_clique.py` očekuje doslovno izvorne mutex klauzule. ATLAS13 mu zato priprema **internu kopiju** CNF-a s izvornim klauzulama plus dokazane mutex leme i pokreće nezavisni `check_php_partition.py`. Taj **interni CNF nije rezultat kojeg smijemo proglasiti UNSAT izvorom**.

Da bismo dobili dokaz na ORIGINALU, novi `research/atlas13_exchange/bridge.py`:

1. Generira Hall CP dokaz u pomoćnoj bazi `original + verificirane implikacijske leme`.
2. Prepisuje standardni dokazni header na stvarni **izvorni broj klauzula**.
3. **Ispred** preostalih CP koraka ubacuje redak `rup 1 ~x_a 1 ~x_b >= 1 ;` za svaku novu izvornu implikacijsku zabranu, u točno istom redoslijedu u kojem su bile dodane internom pomoćnom CNF-u.
4. Zadržava numeričke identifikatore ostalih klauzula, jer prva nova RUP lema u dokazu preuzima baš mjesto prve dodatne klauzule iz internog CP dokaza.
5. Za konačni `STRICT VERIFIED` zahtijeva vanjski `veripb --cnf ORIGINAL.cnf original-proof.pbp` s kodom 0 i porukom `s VERIFIED UNSATISFIABLE`.

Time se verifikacija **ne oslanja** na to što je pomoćna formula jača od originalne. Svaka njena dodatna klauzula prije upotrebe mora biti dokazano posljedica izvorne formule.

## 3. Kontrolirana nepoznata kodiranja i rezultati

Izvorni generator priprema **tri različite nepravilne list-coloring/capacity konstrukcije**, svaku s drugačijim brojem zahtjeva, resursa i širina EXACTLY-ONE grupa. Namjerno zamjenjuje jednu, dvije ili tri potrebne izvorne mutex klauzule s 2-SAT implikacijskim lancima preko novih pomoćnih varijabli, bez promjene matematičke UNSAT istine. Izvorni detektori ne dobivaju informacije o generatorovim bojama, imenima, popisu grupa niti o očekivanom rezultatu.

| Izvorni kontrolni CNF | Izvorne EO grupe | GRAPH zasebno | HALL izvorno | Leme predane Hallu | Vanjski VeriPB |
|---|---:|---|---|---:|---|
| 5 zahtjeva / 4 resursa | 5 | UNKNOWN | UNKNOWN | **1** | **UNSAT VERIFIED** |
| 6 zahtjeva / 5 resursa | 6 | UNKNOWN | UNKNOWN | **2** | **UNSAT VERIFIED** |
| 7 zahtjeva / 6 resursa | 7 | UNKNOWN | UNKNOWN | **3** | **UNSAT VERIFIED** |
| Preimenovani prvi izvor | 5, ekvivalentne varijable | UNKNOWN | UNKNOWN | **1** | **UNSAT VERIFIED** |

- Različiti generirani izvori: **3**; provjerenih UNSAT izvoda: **4/4**.
- Izvorno potvrđenih svih ALO + pairwise AMO klauzula: **5 / 6 / 7** EO grupa, zasebno potvrđeno postojećim `source_facts.py` i neovisnim `check_facts.py`.
- Provjerenih novih izvora RUP mutex činjenica koje su zaista prenesene: **7** kroz četiri izvođenja.
- ATLAS13 je na slučajevima s 2 i 3 prenesene leme posebno testirao **ablaciju bez posljednje leme**: Hall ne smije izdati certifikat sve dok ne primi potpuni potreban skup novih činjenica.
- Stvarni izvorni dokazi: **359, 646, 1088 bajtova**, te **359 bajtova** za preimenovanu verziju.
- Vanjski VeriPB 3.0.2 na ovim kratkim kontrolama provjeravao je potpune dokaze za približno **0,004–0,005 s** pojedinačno; to **nije** natjecateljski benchmark ili E2E ubrzanje nad Kissatom.

### Stroge negativne kontrole

Na prvoj formuli izbrisana je upravo druga originalna premisa jednoga ključnog implikacijskog puta. Novi CNF time postaje **SAT**, što potvrđuje konkretna dodjela svake izvorne varijable i svake klauzule.

- GRAPH-only ostaje UNKNOWN i HALL-direct ostaje UNKNOWN;
- graf ne može izmisliti nedostajući 2-koračni put pa ne predaje nedopuštenu lemu;
- pokušaj prisilnog korištenja starog certifikata, uz **ažurirani SHA** izmijenjenoga izvora, biva odbijen neovisnom provjerom sadržaja;
- namjerno pogrešni originalni SHA također se odbacuje.

Dakle nismo dobili lažni UNSAT kad je ključni izvorni dokaz zaista nedostajao.

## 4. Granice tvrdnje i sljedeći zahtjevi

Ovaj eksperiment prvi je u našoj Atlas seriji koji **u precizno definiranom kontroliranom izvoru** uvjetuje konačni dokaz stvarnim informacijskim prijenosom između dva odvojena matematizirana postupka: 2-SAT graf izvodi lemu koju Hall ne nalazi doslovno u izvorniku, a Hall završava dokaz samo nakon primitka nje.

**Nije dokazana nova matematička teorema**, P=NP, svijetski rekord, univerzalna generalizacija na proizvoljnu CNF semantiku, niti to da nijedan drugi *općenit* SAT solver ne može sam riješiti te male formule. Pojedinačna dva baseline modula su usko, jasno definirana; opći CDCL i kompletan 2SAT+neki dodatni zaključivač nisu testirani kao jednaki baseline.

Ovdje su svi izvori **namjerno konstruirane kontrole**. Sljedeći ključni test treba biti **javni originalni CNF s pomoćno kodiranim konfliktima**, odabran i SHA-zamrznut prije gledanja solverovih rezultata, uz nezavisnu provjeru izvora i zatim uparene ON/OFF ruke `GRAPH_ONLY/HALL_ONLY/GRAPH→HALL/Kissat/CaDiCaL`. Svaki neprepoznat slučaj ide u UNKNOWN, a vanjski VeriPB/DRAT ostaje isključivi standardni autoritet.

## 5. Reprodukcija

```bash
python3 research/atlas13_exchange/audit.py

# za jedan pravi originalni CNF:
python3 research/atlas13_exchange/bridge.py \
  --cnf ORIGINAL.cnf \
  --certificate proven-graph-lemmas-and-hall.json \
  --proof original-source.pbp \
  --meta log.json

veripb --cnf ORIGINAL.cnf original-source.pbp
```

Workflow: `.github/workflows/atlas13-graph-implication-hall.yml`. GitHub Actions artefakt `DRNAS-ATLAS13-TRUE-GRAPH-2SAT-HALL-INFERENCE` sadrži sve originale, punu nezavisnu evidenciju grafovskih izvoda, svaki originalni PBP, Hall certifikate, originalni SHA, SAT i krivotvorene kontrole i logove. **`main` nije mijenjan.**
