# DRNAS HYBRID-10 — source-bound three-theory VeriPB proof

**Date:** 2026-11-20  
**Authors:** Frane Drnas and OpenAI assistant (GPT-6)  
**Status:** experimental, isolated branch; production \`main\` unchanged.  
**Result:** independent VeriPB 3.0.2 accepted all 17 tested UNSAT certificates (seven baseline/scale sizes, four variable permutations and six new connected cubic topologies). These are **synthetic restricted-family instances, not a blind benchmark**.

## Izvorna matematička ideja

Neka CNF sadrži n logičkih izbora x_i. Izvorni pozitivni ALO i svi parovi \`(~x_i or ~x_j)\` dokazuju:

\[
\sum_{i=1}^{n}x_i =1.
\]

Binarne implikacije (uz obostranu dosezljivost u 2-CNF implikacijskom grafu) potvrđuju x_i = y_i. Za svaki vrh v, izvorna XOR4 CNF-kodirana jednadžba je

\[
y_v \oplus \bigoplus_{e\in\delta(v)}z_e=b_v.
\]

Svaki brid ima točno dva kraja, pa se pri zbrajanju svih redaka nad GF(2) svaki z_e poništi. Za testiranu obitelj \(\bigoplus_v b_v=0\), dakle \(\bigoplus_v y_v=0\). Ali iz \(\sum_i x_i=1\) slijedi \(\bigoplus_i x_i=1\); kako je x_i=y_i, dobivamo \(0=1\).

## Zašto je VeriPB dokaz polinomne veličine na ovoj obitelji?

1. Izvornim RUP koracima dokazujemo dvije ekvivalencijske klauzule za svaki x_i=y_i; nikakvi nazivi iz generatora nisu potrebni.
2. Za svaki izvorni XOR4 redak uvodimo RED definiciju q=x XOR y. Iz originalnih klauzula slijede dva XOR3 retka, a poznati XOR/carry RED–RUP–cutting-planes postupak dokazuje odgovarajuće cjelobrojne nejednakosti.
3. Iz izvornoga ALO uzimamo donju granicu \(\sum x_i\ge1\). Gornju granicu iz AMO parova izvodimo cutting-planes indukcijom:

Za j=2, izvorni par daje \(\sum_{i\le 2}\neg x_i\ge1\). Ako već imamo \(S_{j-1}=\sum_{i<j}\neg x_i\ge j-2\), zbrajanje svih j−1 izvornih parova s novim x_j daje

\[
S_{j-1}+(j-1)\neg x_j\ge j-1.
\]

Pomnožimo raniju granicu s j−2, zbrojimo i podijelimo s j−1, uz zaokruživanje naviše:

\[
S_j\ge
\left\lceil\frac{(j-2)^2+(j-1)}{j-1}\right\rceil=j-1.
\]

Tako je \(S_n\ge n-1\), odnosno \(\sum x_i\le1\), izvedeno u **O(n) cutting-planes linija**, ali te linije sadrže ukupno više zapisanih operanada.

4. Kad se XOR jednakosti, ekvivalencije i granica \(\sum_i x_i=1\) zbroje, svaka pomoćna i izvorna varijabla ima paran koeficijent, a desna strana neparan. VeriPB potvrđuje konačnu podjelu s 2 i kontradikciju.

**Broj dokaznih koraka** u ovom generatoru i ovoj 3-regularnoj obitelji:

\[
L(n)=52n+3,\quad RED=19n,\quad RUP=22n,\quad CP=11n+3.
\]

Broj koraka je linearan. To **ne tvrdi linearne bajtove**, jer s rastom n raste duljina pojedinih CP redaka. Izvorni AMO kod već ima \(\Theta(n^2)\) klauzula.

## Neovisni standardni rezultati

**Vanjski provjerivač**: VeriPB 3.0.2, pokrenut iz GitHub Actions, s izlazom \`s VERIFIED UNSATISFIABLE\`.

| Izvor CNF | n | VeriPB koraci | Dokaz (B) | Rezultat |
|---|---:|---:|---:|---|
| HYBRID-9 graf | 4 | 211 | 6,767 | VERIFIED |
| HYBRID-9 graf | 6 | 315 | 10,195 | VERIFIED |
| HYBRID-9 graf | 8 | 419 | 13,663 | VERIFIED |
| Prošireni graf | 10 | 523 | 17,133 | VERIFIED |
| Prošireni graf | 12 | 627 | 20,750 | VERIFIED |
| Prošireni graf | 16 | 835 | 28,532 | VERIFIED |
| Prošireni graf | 20 | 1,043 | 36,925 | VERIFIED |
| Presloženi graf n=12, četiri različite permutacije | 12 | 627 svaki | 20.7 KB približno | VERIFIED 4/4 |
| Novih šest povezanih kubičnih grafova (n=10,10,12,12,16,20) | 10–20 | 523–1,043 | 17–37 KB | VERIFIED 6/6 |

**Audit:** [GitHub Actions 44742547146](https://github.com/Frane12/DRNAS-SAT/actions/runs/44742547146). Prvotni test: [44741272484](https://github.com/Frane12/DRNAS-SAT/actions/runs/44741272484). Prošireni test: [44742007608](https://github.com/Frane12/DRNAS-SAT/actions/runs/44742007608).

**Kontrole:** SAT model na modificiranim grafovima; odbijanje izostavljenog AMO para, 2-SAT veze ili XOR klauzule; te vraćanje \`UNKNOWN\` na četiri originalne, nepodržane DRNAS formule: XOR234 Grid, Petersen PCMAX, Graph K11 i PCMAX m14. Nijedan od tih \`UNKNOWN\` statusa ne govori je li formula SAT.

## Reprodukcija

Datoteke na ovoj grani:
- \`research/hybrid10/emit_veripb_three_theory.py\` — detektor, generator RED/RUP/CP certifikata.
- \`research/hybrid10/generate_cases.py\` — izvorni HYBRID-9 ulazi vezani SHA-256 kontrolom.
- \`research/hybrid10/make_extended.py\` — dodatne veličine, permutacije, SAT kontrola.
- \`research/hybrid10/graph_topology.py\` — povezani 3-regularni grafovi različite topologije.
- \`.github/workflows/drnas-hybrid10-audit.yml\` — vanjski VeriPB 3.0.2 audit.

Na GitHubu otvorite workflow logove radi potpunih statusa, izvornog SHA-256 i rezultata. Lokalni generator piše \`EMITTED_UNCHECKED\` dok neovisni VeriPB potvrdi certifikat.

## Znanstvene granice

- Cutting planes, RED proširenja i paritetni dokazi poznate su dokazne tehnike. Ovdje je doprinos konkretno povezivanje i implementacija na izvornim CNF-ovima.
- Ovo **nije dokaz P=NP, P=coNP ili NP=coNP** niti dokaz da sve UNSAT formule imaju polinomske certifikate.
- Ova je obitelj poznata i konstruirana; različite topologije još uvijek pripadaju istoj 3-regularnoj XOR/one-hot/2SAT klasi.
- Ovaj test nije CPU/E2E benchmark protiv Kissata, CaDiCaLa ili CryptoMiniSata; broj dokaznih koraka dvaju različitih sustava nije izravna mjera brzine.
- Sljedeći smisleni eksperiment jest obitelj s neugodnijim, neprepoznatljivim kodiranjem XOR/PB ograničenja, zatim stvarni neviđeni CNF-ovi i prospektivna provjera.
