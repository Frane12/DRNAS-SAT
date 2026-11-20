# DRNAS HYBRID-11 — neizravne XOR mreže i potpisane 2-SAT veze

**Autori:** Frane Drnas i OpenAI asistent (GPT-6)  
**Datum:** 20. studenoga 2026.  
**Status:** izdvojena eksperimentalna grana; `main` nije mijenjan.  
**Provjera:** neovisni VeriPB 3.0.2, [uspješan GitHub Actions audit #44747431674](https://github.com/Frane12/DRNAS-SAT/actions/runs/44747431674).

## Istraživačko pitanje

Možemo li reproducirati trostruki matematički dokaz iz HYBRID-10 kad originalni CNF **više ne sadrži izravno XOR4 kodirana vrata**, nego ih definira preko više XOR3 vrata s pomoćnim varijablama? Možemo li obuhvatiti i negirane 2-SAT ekvivalencije?

Za ovaj ograničeni skup kodiranja odgovor je **da**: generator iz samih izvornih DIMACS klauzula rekonstruira zatvorenu mrežu, izvodi potrebne RUP/RED/CP korake i daje vanjski provjeren VeriPB certifikat.

## Matematička konstrukcija

Neka je (x_i\in\{0,1\}) izbor od ukupno (n) poslova. Izvorne ALO i AMO klauzule daju:

\[
\sum_{i=1}^{n} x_i=1 \quad \Rightarrow \quad \bigoplus_i x_i=1.
\]

Lanci binarnih implikacija dokazno daju potpisanu ekvivalenciju:

\[
x_i \oplus y_i=d_i, \qquad d_i\in\{0,1\}.
\]

Ako je (d_i=0), imamo (x_i=y_i). Ako je (d_i=1), imamo (x_i=\neg y_i).
Izdvojeni izlazni dokaz upotrebljava odgovarajuće dvije RUP klauzule izvedene iz izvornih binarnih implikacija.

Za svaki vrh kubičnog grafa paritetno pravilo

\[
y_v\oplus z_{v,1}\oplus z_{v,2}\oplus z_{v,3}=b_v
\]

u izvornom se CNF-u može pojaviti **neizravno** kao dvije pune XOR3 tablice:

\[
y_v\oplus z_{v,1}\oplus t_v=0,\qquad
t_v\oplus z_{v,2}\oplus z_{v,3}=b_v.
\]

Pomoćna varijabla (t_v) javlja se dvaput. Pri sumiranju svih vršnih XOR jednadžbi svaki se brid (z_e) također javlja dvaput (po jednom na svakom kraju) i nestaje nad GF(2). Slijedi:

\[
\bigoplus_v y_v=\bigoplus_v b_v=:B.
\]

Iz potpisanih 2-SAT relacija i kapaciteta slijedi:

\[
\bigoplus_v y_v=1\oplus\bigoplus_i d_i=1\oplus D.
\]

U testnoj UNSAT obitelji odabrano je (B=D). Zato istodobno mora vrijediti (B=1\oplus B), kontradikcija.

To je dokazana **dovoljna UNSAT leme** za ovu strukturu, ne opći algoritam za proizvoljan CNF.

## Izvođenje dokaza

1. Iz samog CNF-a prepoznati puni pozitivni ALO i sve negativne AMO parove.
2. Prepoznati potpuna XOR3 ili XOR4 vrata iz **svih njihovih izvornih zabranjenih dodjela**. Ne vjerovati komentarima ni imenima varijabli.
3. Iz 2-CNF implikacijskog grafa dokazati (x=y) ili (x=\neg y) i odrediti točno jednu vezu po odabiru.
4. Pratiti povezana XOR vrata kroz pomoćne varijable (t), sve do zatvorene mreže. Nepripadni odvojeni XOR3 šum ignorira se samo ako nije dio potrebnog svjedoka.
5. Potvrditi: svaki (y_i) javlja se jednom u mreži, svaka druga mrežna varijabla točno dvaput, te je globalna paritetna kontradikcija stvarna.
6. Koristiti RED definicije, RUP korake i cjelobrojne cutting-planes operacije preuzete iz vanjski provjerenog HYBRID-10/XOR234 mosta.
7. Izvještaj prije vanjske provjere označava dokaz kao `EMITTED_UNCHECKED`. Jedino vanjski VeriPB 3.0.2 vraća prihvaćen `UNSAT`.

## Rezultati vanjske provjere

Svi brojevi su iz uspješnog GitHub Actions audita; koraci znače zbroj RED + RUP + CP, ne broj DPLL koraka.

| Vrsta izvora | Vrhovi | Izvorni XOR3/XOR4 redci | VeriPB koraci | Bajtovi | Vanjski rezultat |
|---|---:|---:|---:|---:|---|
| Potpuno razdijeljeni | 4 | 8 / 0 | 138 | 4.190 | VERIFIED |
| Potpuno razdijeljeni | 6 | 12 / 0 | 205 | 6.338 | VERIFIED |
| Potpuno razdijeljeni | 8 | 16 / 0 | 268 | 8.357 | VERIFIED |
| Mješoviti XOR3/XOR4 | 8 | 10 / 3 | 316 | 10.108 | VERIFIED |
| Mješoviti XOR3/XOR4 | 12 | 16 / 4 | 471 | 15.332 | VERIFIED |
| Potpuno razdijeljeni | 16 | 32 / 0 | 537 | 17.768 | VERIFIED |
| Mješoviti XOR3/XOR4 | 20 | 26 / 7 | 784 | 27.215 | VERIFIED |
| Potpuno razdijeljeni | 32 | 64 / 0 | 1.085 | 38.982 | VERIFIED |
| Tri dodatne preimenovane/presložene formule | 12, 16, 20 | različito | 407, 633, 672 | 13–23 KB | 3/3 VERIFIED |

**Ukupno: 11/11 izvana prihvaćenih UNSAT dokaza.** U svakom se testu provjerava SHA-256 istog izvornog CNF-a koji je predao generator.

Na potpuno razdijeljenim formulama izvorni CNF uopće ne sadrži punu XOR4 klauzulnu skupinu. To je namjerno teži oblik od HYBRID-10. Ipak, oba oblika i dalje pripadaju unaprijed poznatoj vrsti mreže XOR vrata.

### Negativne kontrole

- 2 SAT kontrolne formule: izričito izgrađeni i provjereni zadovoljavajući modeli; generator vraća `UNKNOWN`.
- 3 promijenjena izvora (jedna uklonjena XOR klauzula, 2-SAT veza ili AMO klauzula): generator ne izdaje UNSAT dokaz.
- 4 druge izvorne DRNAS formule (XOR234 Grid, Petersen PCMAX, Graph K11 i PCMAX m14): `UNKNOWN`, bez lažne UNSAT tvrdnje.
- Dodatne nepovezane potpune XOR3 tablice ne smiju se zamijeniti za dio povezanog dokaza.

## Granice tvrdnje

Ovo je izravna, vanjski provjerena realizacija poznatih dokaznih pravila za **posebne konstruirane grafovsko-paritetne CNF-ove**. Nije dokaz univerzalne polinomne veličine certifikata, nije pokazatelj brzine na neviđenim stvarnim SAT Competition instancama, nije benchmark prema Kissat/CaDiCaL/CMS-u i ne zaključuje ništa novo o (P=NP) ili (NP=coNP).

**Sljedeći presudni korak:** prospektivno zamrznuti neviđene CNF-ove s posve drukčijim kodiranjima, bez algoritmu poznate sheme, zatim mjeriti broj dokazano riješenih izvora, vanjsku provjeru i E2E vrijeme na jednom CPU-u.

## Reprodukcija

- [Izvorni dokazni generator](../research/hybrid11/emit_veripb_indirect.py)
- [Generator izvornih testnih CNF-ova](../research/hybrid11/generate_indirect.py)
- [GitHub Actions workflow](../.github/workflows/drnas-hybrid11-audit.yml)
- [Službeni audit #44747431674](https://github.com/Frane12/DRNAS-SAT/actions/runs/44747431674)

Izvođenje koristi Python 3 i neovisno instalirani VeriPB 3.0.2. Ispisani `EMITTED_UNCHECKED` rezultat nije valjan konačni UNSAT bez provjerivača.
