# DRNAS REAL5 / REAL5-Q — višekonusna algebra i slijepi test stvarnih FPGA sklopova

**Autor:** Frane Drnas  
**Datum istraživačkog izvještaja:** 24. 11. 2026.  
**Eksperimentalna grana:** `experiment/real5-crosscone-gf2-relations-20261124`  
**Izvorni `main`:** nije mijenjan.

## I. Hipoteza: mogu li se nelinearni cutpointovi poništiti između više izlaza?

Za pojedine sklopovske signale imali smo dokazane lokalne GF(2) izraze

`y_i = L_i(x,q) XOR C_i(z)`,

gdje su `x` primarni ulazi, `q` trenutno slobodno stanje registara,
a `z` stvarni izlazni bitovi nelinearnih ili nepodržanih ćelija.

Po linearnoj algebri, ako za odabrane izlaze vrijedi
`XOR_i C_i(z)=0`, tada točno vrijedi
`XOR_i y_i=XOR_i L_i(x,q)`, neovisno o vrijednosti `z`.
Čak ni poznavanje same nelinearne funkcije nije nužno.

### Eksperimenti

- `real5_relations.py` računa eliminaciju GF(2) nad vektorima nelinearnih
  cutpointova, s ograničenjem broja izlaza po relaciji.
- `real5_verify.py` radi neovisnu provjeru preko simetrične razlike skupova
  GF(2) varijabli i ponovljenog realnog gate-level certifikata.
- Testovi s dvama i trima izlazima, kao i izmijenjenim dokazima, prošli su
  u [runu 45343899765](https://github.com/Frane12/DRNAS-SAT/actions/runs/45343899765).
- Retrospektivni razvojni test na pet stvarnih originalnih RTL netlista
  [45344178005](https://github.com/Frane12/DRNAS-SAT/actions/runs/45344178005):
  **nula novih netrivijalnih višekonusnih identiteta** od 1157 signala ovisnih o
  nelinearnim cutpointovima. To je *negativan rezultat*, ne dokaz da takvi
  odnosi ne postoje — sadašnji nezavisni cutpointovi mogu biti pregruba
  reprezentacija.

## II. REAL5-Q: točni Booleovi polinomi 2. stupnja

Umjesto da svaku nelinearnu operaciju odmah izdvojimo kao novu
nepoznatu, REAL5-Q simbolički razvija GF(2) polinome nad
kvadratno-idempotentnim Booleovim varijablama:

`x_i²=x_i`; `NOT(a)=1+a`; `AND(a,b)=ab`;
`OR(a,b)=a+b+ab`; `MUX(s,a,b)=a+s(a+b)`.

Gornji zapis koristi zbrajanje i množenje nad GF(2).
Polinomi su egzaktni. Ako se prekorače granice
`degree<=2`, `max_monomials=96` ili
`product_pairs<=4096`, program **ne zaključuje da je polinom netočan**:
umjesto toga stvara simboličku granicu na originalnom izlazu ćelije.
Tako dobiva samo lokalnu identitetnu formulu, uz otvoren problem
izračuna stvarne nelinearne unutarnje funkcije.

- `real5q_anf.py`: ANF kao skup bitmaski monoma.
- `real5q_verify.py`: neovisan povratni izračun kao skup skupova indeksa
  (druga matematička reprezentacija).
- `real5q_miter.py`: izdvaja do tri originalna kvadratna gate-kona po
  modulu te generira miter "precizan izvorni gate-cone XOR izračunati
  GF(2) polinom".
- `real5q_sat.py`: Kissat i CaDiCaL na **istom CNF-u**,
  jedan CPU, dva ponavljanja, uz zasebnu Yosys formalnu provjeru.
  Nijedna metoda time ne provjerava automatski cijeli izvorni projekt.

### Dev korpus, već ranije viđeni REAL4 izvori — nije blind

[REAL5-Q algebra, run 45344738069](https://github.com/Frane12/DRNAS-SAT/actions/runs/45344738069)

| Stvarni projekt | Globalno kvadratni izvani izlazi ili FF-D bitovi | Od toga s >=2 kvadratna člana |
|---|---:|---:|
| UART TX | 31 | 29 |
| Streaming FIFO | 3 | 0 |
| PicoRV32 procesor | 2 | 1 |
| AES S-box | 0 | 0 |
| SHA-256 W-MEM | 0 | 0 |

Svih pet izvora ponovno je prošlo neovisnu provjeru izvorne
Yosys mreže. Ipak, mnogi izdvojeni izrazi su mali ili trivijalni:
ne smiju se automatski nazvati dubokim matematičkim zakonima.

[REAL5-Q SAT kontrola, run 45345192400](https://github.com/Frane12/DRNAS-SAT/actions/runs/45345192400):
**15 od 15** izvornih gate-level mikro-kona prošlo je Yosysovu
provjeru; **30/30 Kissat** i **30/30 CaDiCaL** pokušaja
prijavilo je UNSAT (60/60 ukupno). Standardni DRAT/LRAT proof
artefakt za svaki UNSAT nije neovisno provjeren.

### Prospektivno zaključani novi izvori — stvarni holdout

Algoritam i provjerivač prošli su green prelock u
[runu 45344568141](https://github.com/Frane12/DRNAS-SAT/actions/runs/45344568141)
prije odabira **pet novih javnih RTL modula**, s nepomičnim SHA
otiscima matematike i originala.

[Prospektivni konačni audit — run 45345960356](https://github.com/Frane12/DRNAS-SAT/actions/runs/45345960356).

| Novi originalni RTL | Sinteza Yosys 0.9 | Globalno kvadratni FF-D ili vanjski bitovi | Lokalni polinomni FF-D ili vanjski bitovi | Interno uzorkovani globalno kvadratni bitovi |
|---|---|---:|---:|---:|
| secworks SHA512 W-MEM | OK | 0 | 1031 | 6 |
| alexforencich AXIS Register | OK | 0 | 23 | 2 |
| secworks ChaCha Core | FRONTEND_UNSUPPORTED (nedostaje chacha_qr) | — | — | — |
| alexforencich Ethernet MAC 1G | FRONTEND_UNSUPPORTED (nedostaje axis_gmii_tx) | — | — | — |
| lowRISC Ibex ALU | FRONTEND_UNSUPPORTED (SystemVerilog package syntax) | — | — | — |

**2/5** izvora sintetizirano, **2/2** proizvedena ANF
certifikata neovisno provjerena, **6/6** lokalnih realnih gate-kona
prošlo Yosysov dokaz, **12/12 Kissat + 12/12 CaDiCaL**
rezultata očekivani UNSAT. Nula prijavljenih timeouta samih
solver pokušaja. Nepodržani izvori nisu računani kao dokaz matematičke
nemoći niti kao poraz SAT solvera.

**Važna ograda:** 1054 lokalna polinomna vanjska/FF-D bita ne znači
1054 globalno kvadratna izlaza; mnogi izrazi jednostavno koriste
neovisne cutpointove i mogu biti malog stupnja.
Kod nova dva sintetizirana modula ne postoji potvrđen globalno
kvadratni *vanjski/FF-D* bit. To znači da hipoteza o potpunoj
kvadratnosti većih originalnih izlaza ovdje **nije** potvrđena.

## III. Što sljedeće ima smisla razvijati?

1. Bez mijenjanja izvornih modula generički otkriti i učitati
   ovisne module (npr. `chacha_qr`, `axis_gmii_tx`), uz SHA
   svih originalnih izvora i pouzdan RTL parser. To je **frontend
   problem**, a ne signal da treba mijenjati matematičku teoriju.
2. Razviti strogo **ograničeno** računsko proširenje na
   GF(2) stupanj 3/4 uz rast broja monoma i obavezno neovisno
   dokazivanje; posebno prepoznati Booleove funkcije
   `CH`, `MAJ` i aritmetičke prijenose, bez preuranjenog
   odsjecanja vrijednih struktura.
3. Prije sljedećeg slijepog korpusa zaključati klasifikaciju
   netrivijalnosti: više kvadratnih ili kubnih monoma,
   stvaran pristup izlazima, dubina konusa, eliminirane
   nelinearne granice i broj preostalih nedokazanih dijelova.
4. Kissat/CaDiCaL zadržati kao stalne kontrolne metode na
   **identičnim** generiranim CNF formulama, uz mjerenje
   izvoza i dokaznog checkera odvojeno. Ne tvrditi
   "pobjedu nad CDCL" ako SAT solver radi drukčiji problem.

**Glavni zaključak:** REAL5-Q daje dokazive kvadratne
podstrukture u stvarnim sintetiziranim hardverskim mrežama,
ali nije riješio proizvoljni nelinearni ili sekvencijski problem.
GF(2) algebra po lokalnim kategorijama obećava; svako ponovno
oslanjanje na generički CDCL valja istražiti kao nedostatak
prepoznate matematičke strukture, a ne zatvaranje problema.
