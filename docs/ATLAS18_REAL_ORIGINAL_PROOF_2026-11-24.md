# ATLAS18 – izvorni CNF: graf implikacija → Hallov dokaz

**Status: 24. studenoga 2026.** Eksperiment na javnom, unaprijed SHA-zamrznutom CNF-u; original je naknadno analiziran, stoga je riječ o ciljanoj retrospektivnoj nadogradnji, a ne slijepom holdoutu. Ovdje se ne tvrdi otkriće opće polinomijalne SAT metode niti prva ikad potvrda statusa ove formule.

Izvor: [ATLAS17 unaprijed odabrani CNF-ovi](../research/atlas17_probe/prespec.json).  
Provjera: [ATLAS18 prihvaćen UNSAT dokaz, run 45345358124](https://github.com/Frane12/DRNAS-SAT/actions/runs/45345358124).

## Što je bilo pogrešno u prepoznavanju

Originalni php-mixed-2023 sadrži **354 varijable i 2.938 klauzula**. Ima 16 disjunktnih izvornih pozitivnih klauzula širine 15, nad 240 selektorskih varijabli. Preostale 114 varijable služe drugim ograničenjima. Stari izravni HALL zahtijevao je pokrivenost svih deklariranih varijabli, premda je za dokaz UNSAT dovoljan proturječan podskup ulaznih ograničenja.

Na 240 selektora nalazi se **2.534 izravnih binarnih zabrana**, koje naivna heuristika za particiju dijeli u 72 resursa (nema dokaza). Kraći grafovski most daje 202 nove zabrane, ali još 61 resurs (UNKNOWN).

UCP izvorne formule pod jednom pozitivnom selektorskom pretpostavkom izvodi **1.156 dodatnih RUP zabrana**. Neovisno istražen graf izvornih binarnih implikacija s putovima duljine 2–16 daje istih 1.156 parova. Nema CDCL-a ni čitanja kataloškog SAT/UNSAT odgovora.

Nakon razmjene novih zabrana s HALL-om, pronađena je particija u **15 resursnih klika po 16 selektora**. Za svaku kliku ulazne ili RUP-izvedene binarne zabrane osiguravaju da može biti istinit najviše jedan selektor. Pozitivne ulazne grupe traže najmanje 16 istinitih selektora:

\[
\sum_{i=1}^{16}\sum_{j=1}^{15}x_{ij}\ge16,\quad
\sum_{j=1}^{15}\sum_{i=1}^{16}x_{ij}\le15
\quad\Longrightarrow\quad \mathrm{UNSAT}.
\]

**Dokaz ne briše pomoćne varijable iz originala.** Samo koristi podskup izvornih zahtjeva i izvorom dokazive posljedice, dok se konačna provjera provodi na svim izvornim klauzulama.

## Granica povjerenja

1. ATLAS18 čita original i prepoznaje disjunktne pozitivne grupe i binarne zabrane.
2. UCP modul predlaže zabrane neg a ili neg b (RUP leme), ne UNSAT presudu.
3. HALL gradi manje kapacitetnih klika nego što ima grupa zahtjeva.
4. Emiter započinje izvorni VeriPB dokaz sa 1.156 RUP redaka, zatim dodaje cutting-planes dokaz kapaciteta. Privremeni CNF s lemama koristi se samo interno pri sastavljanju dokaza.
5. **Samo vanjski VeriPB 3.0.2 koji prihvati dokaz nad neizmijenjenim izvornim CNF-om daje status UNSAT_VERIFIED.**

Izvorna formula SHA-256:

a768fde6183e8193b62b47bdbb833826730c4d67f5055a89cdfc6c904bd62bff

Prihvaćeni dokaz: **46.368 bajtova**, SHA-256:

02f45702699d6740d793c4583b5dba3aefed55cb22a2ad599d08c0dcc276d1ad

Prvo završeno mjerenje: **0,099189 s** za UCP→HALL arm s vanjskom VeriPB provjerom i **0,337754 s** za puni serijski ATLAS18 router, jedan logički CPU. To su pojedinačna mjerenja, ne parni višestruko ponovljeni benchmark.

## Rezultati i kontrola

| Formula | Rezultat u ATLAS18 |
| --- | --- |
| Javni php-mixed-2023 | UCP+HALL, UNSAT_VERIFIED; prethodni pojedinačni moduli UNKNOWN |
| Javni exam-scheduling-2026 | Broad HALL, UNSAT_VERIFIED; potvrda povezivanja postojeće metode |
| Javni graph-color-2026 | GRAPH, UNSAT_VERIFIED |
| Javni clique-color-2025, xor-shift-2026, boxfolding-2026 | UNKNOWN |
| Četiri ranije poznata PCMAX originala | 4/4 verificirana, retrospektivna kontrola |
| Ranije poznati XOR original | 1/1 verificiran, retrospektivna kontrola |
| Ranije poznat Petersen | UNKNOWN unutar ovog routera; zaseban izvorni IPG dokaz je dokumentiran |
| Tri konstruirana GRAPH+XOR+HALL primjera | 3/3 verificirana, sintetske kontrolne formule |
| Namjerno SAT konstruirana kontrola | UNKNOWN; originalni SAT model neovisno provjeren |

**Pokrivenost šest novih javnih originala povećana je s 2/6 u ATLAS17 na 3/6 u ATLAS18.** Nova je potvrđena suradnja UCP+HALL na izvornom php-mixed primjeru. Nije pokazana opća prednost nad Kissatom i CaDiCaL-om. U istom testu oba referentna solvera dosegnula su 96 MiB ograničenje izlazne dokazne datoteke, pa njihov UNKNOWN ne znači nemogućnost rješavanja pod većim limitima.

## Reprodukcija na izoliranoj grani

~~~bash
python3 research/atlas17_probe/freeze.py
cargo install veripb --version 3.0.2 --locked
mkdir -p /tmp/atlas18
python3 research/atlas18_probe/hall_subset.py \
  --cnf atlas17_original_inputs/php-mixed-2023.cnf \
  --mode UCP \
  --proof /tmp/atlas18/php-mixed.pbp \
  --meta /tmp/atlas18/php-mixed.json
veripb --cnf atlas17_original_inputs/php-mixed-2023.cnf \
  /tmp/atlas18/php-mixed.pbp
~~~

Sve razvijeno na eksperimentalnoj grani. Main nije promijenjen. Za tvrdnje o prijenosu metode na nove familije potrebno je dodatno neviđeno, neovisno testiranje.
