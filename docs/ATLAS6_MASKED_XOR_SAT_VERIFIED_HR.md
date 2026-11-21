# DRNAS STRUCTURE ATLAS 6 — originalni maskirani XOR SAT: otkrivanje značenja iz klauzula

**Datum:** 21. studenoga 2026.  
**GitHub Actions:** https://github.com/Frane12/DRNAS-SAT/actions/runs/44952552943  
**Eksperimentalna grana:** `experiment/atlas6-camouflaged-xor-id8-20261121`; `main` nije mijenjan.  
**Ishod:** **PASS, originalni SAT model neovisno verificiran**, ponovno na 3 različite bijektivno ekvivalentne varijante.

## Stvarni problem i povijesni izvor

Originalni SAT Competition 2005-derived `random-graph-xorsat` ID8, ponovno dostupan u Main 2025 katalogu:

- Originalni GBD ID: `b5431f41e3264c64508c30da215c69c6`.
- Isti izvorni SHA256 prethodno zamrznut u DRNAS `evidence/ci/graph-disjoint10.json`: `f9dcbbbcb2abc290439c21978d04cdc44efffbed9b4e5cdee96dd63856a5a156`.
- Stvarni DIMACS: **352 varijable, 2.492 klauzule**, sve širine 4–6.
- Originalni naziv datoteke: `mod2c-rand3bip-sat-250-3.shuffled-as.sat05-2535.cnf.xz`.
- Povijesni SAT status je poznat (vidi [SAT Competition 2011 zapis](https://www.cril.univ-artois.fr/SAT11/results/trace.php?idev=45&idjob=3264859)), ali **nije korišten u detektoru, modelu ili provjerivaču**.
- Autori izvornog benchmarka: Haanpää, Järvisalo, Kaski, Niemelä, [SAT Benchmarks based on 3-Regular Graphs (2005)](https://www.tcs.hut.fi/Publications/mjj/hjkn.sat05benchmarks.pdf). Camouflage je poznata matematička konstrukcija; ne tvrditi povijesnu novost AND-maskiranja ili Gaussove eliminacije.

## Čemu je prvi pokušaj bio neuspješan?

Prvi `inverse.py` tražio je dvije varijable koje imaju **jednake predznakom označene pojave**. Rezultat je bio 0 para i UNKNOWN na originalu i trima varijantama (CI https://github.com/Frane12/DRNAS-SAT/actions/runs/44951915404). To je stvaran početni neuspjeh.

Analiza točno istog izvora pokazala je da se parovi moraju prepoznavati po **apsolutnoj, bezpredznačnoj pojavnosti** u svim klauzulama, a zatim matematički razjasniti njihov **predznakom označeni AND uvjet** preko cijele zabranjene tablice istinitosti. Ovo je jače od heuristike o podudaranju broja klauzula.

## Izvorno potvrđena rekonstrukcija

`semantic_and_xor.py` rekonstrurira grupe varijabli koje u svakom izvornom CNF retku nastupaju zajedno (potpuno ista apsolutna incidencija). Na ovom originalu:

- **102 grupe po dvije varijable** (skriveni AND odabrana dva potpisana literala);
- **148 jednostrukih varijabli**;
- ukupno **250 virtualnih logičkih odabira**.

Original sadrži točno **250 potpunih izvornih tablica** nad 4, 5 ili 6 izvornih Booleovih varijabli. Svaka je neovisno protumačena kao točno jedna XOR jednadžba nad tri virtualna odabira. Virtualni odabir je ili jedna Booleova varijabla, ili `(signed_a AND signed_b)`, sa znakovima određenim iz source-truth-table zahtjeva, ne iz naziva.

Za svaku izvornu tablicu provjeravaju se **sve 2^w kombinacije** ulaznih vrijednosti, i kompletan izvorni skup zabranjenih dodjela mora se podudarati s matematičkim pravilom:

\[
z_i = x_i\ \text{ili}\ z_i=(\ell_a\land\ell_b),\qquad
z_i\oplus z_j\oplus z_k=b.
\]

Zatim se na svih **250** XOR jednadžbi provodi standardna Gaussova eliminacija nad GF(2), dobiva se konzistentno rješenje, podiže u originalnih 352 varijable i neovisno provjerava svaka originalna CNF klauzula. **Originalni, ponovno sastavljeni XOR CNF ima 250 varijabli i 1.000 klauzula.**

## Neovisni provjerivač

`check_semantic.py` NE uvozi izvorni detektor i NE vjeruje njegovoj procjeni. On:

1. čita točan originalni CNF i izvorni SHA;
2. potvrđuje da su tokeni particija svih izvornih varijabli;
3. potvrđuje da je svih 250 izvornih skupina klauzula pokriveno, bez izmišljanja ili ispuštanja klauzula;
4. **ponovno iscrpno računa** zabranjenu tablicu za svaku skupinu (uključujući potpisane AND parove) i uspoređuje s izvornikom;
5. izvodi zasebno očekivane virtualne XOR CNF klauzule i točno ih uspoređuje s generiranim virtualnim CNF-om;
6. provjerava da predana dodjela virtualnih varijabli odgovara originalnoj dodjeli, zatim svaku izvornu CNF klauzulu.

Samo kada originalni model zadovolji **svih 2.492 klauzule** dopušta se `ORIGINAL_SAT_MODEL_INDEPENDENTLY_VERIFIED`. Za SAT nije potreban VeriPB UNSAT certifikat; potpuno zadovoljavanje originalnog CNF-a je standardna neposredna provjera SAT modela.

## GitHub rezultati

| Izvođenje | Rekonstruirano | Neovisno provjeren model | Lokalni wall, uključujući sve provjere |
|---|---|---|---:|
| Original | 102 AND para / 250 XOR / 250 virtualnih var. | **SAT 2.492/2.492** | 0,038258 s |
| Preimenovanje + preslagivanje #101 | 102 / 250 / 250 | **SAT 2.492/2.492** | 0,039433 s |
| Preimenovanje, preslagivanje, promjena polariteta #202 | 102 / 250 / 250 | **SAT 2.492/2.492** | 0,048690 s |
| Druga neovisna promjena polariteta #303 | 102 / 250 / 250 | **SAT 2.492/2.492** | 0,039190 s |

Ukupno **1.000 neovisno provjerenih izvornih tablica** i **9.968 provjera klauzula SAT modela** kroz četiri izvođenja.

Negativne kontrole sve PASS: jedna uklonjena izvorna klauzula s ažuriranim SHA-om odbijena; izmijenjeni AND predznak odbijen; namjerno pogrešan SAT model odbijen; lažirani source SHA odbijen.

Wall-time odnosi se samo na sam matematički postupak i njegov izvorni checker na GitHub runneru, **ne** uključuje checkout, instalaciju paketa, čekanje runnera ili preuzimanje originalnog CNF-a. Nema parnog benchmarka protiv novog Kissata na istom CPU-u; ne tvrditi kvantificirano ubrzanje bez njega.

## Istraživačka vrijednost i ograničenja

**Potvrđeno:** baš na javnoj, već poznatoj realnoj izvornoj SAT instanci detektor je bez poznate mape i bez oznaka izvora rekonstruirao netrivijalni maskirani AND/XOR sustav, te sastavio i neovisno potvrdio SAT model. Potvrđeno na tri bijektivno ekvivalentne promjene kodiranja (imenovanja, redoslijeda i polariteta).

**Nije potvrđeno:** opća pokrivenost svih nepoznatih CNF kodiranja; rješavanje proizvoljnog SAT-a; nova matematička činjenica o P/NP; novi prethodno nepoznat SAT status te instance; standardna prednost nad modernim Kissatom. Ovo je retrospektivni jedinstveni izvor + tri varijante, ne statistički reprezentativan generalizacijski rezultat.

**Sljedeći pošteni znanstveni krug:** zamrznuti kod, birati neviđene originalne različite AND-camouflage i druge XOR/gate obitelji po GBD metapodacima bez uvida u rezultat; onda dokazno provjereni isti algoritam, SAT/UNSAT/UNKNOWN računanje, stvarne negativne kontrole, in-source alternative encoding, jedna CPU jezgra, i eventualni verificirani upareni Kissat test.

## Reprodukcija

```bash
python3 research/atlas6_camouflage/semantic_and_xor.py \
   --cnf original.cnf --quotient quotient.cnf \
   --certificate semantics.json --model original-model.json

python3 research/atlas6_camouflage/check_semantic.py \
   --source original.cnf --quotient quotient.cnf \
   --certificate semantics.json --model original-model.json

python3 research/atlas6_camouflage/audit_semantic.py
```

CI workflow: `.github/workflows/atlas6-semantic-xor.yml`. GitHub evidence artifact: `DRNAS-ATLAS6-SEMANTIC-AND-XOR-SAT`.
