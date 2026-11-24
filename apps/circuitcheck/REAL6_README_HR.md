# DRNAS REAL6 — automatsko prepoznavanje CH, MAJ i punog zbrajala

**Istraživač:** Frane Drnas  
**Grana:** `experiment/real6-motif-linking-20261124`  
**Originalni `main`:** neizmijenjen.

## Cilj: od izoliranog nelinearnog bita do povezane matematičke cjeline

REAL5-Q daje točan Booleov polinom drugog stupnja za pojedine
bitove stvarne Yosys logičke mreže, uz stroga ograničenja broja
monoma i prisilne nelinearne cutpointove. REAL6 na takvim
**već neovisno provjerenim** polinomima traži poznate matematičke
motive pomoću potpune trivarijantne tablice istinitosti:

- `CH(s,a,b) = s*a XOR s*b XOR b` — ako je s=1 odabire a,
  inače b.
- `MAJ(a,b,c) = a*b XOR a*c XOR b*c` — većinska funkcija.
- `SUM3(a,b,c) = a XOR b XOR c` — bit trostrukog zbrajanja.
- `FULL_ADDER` — pronalazak **dva različita fizička izlazna
  bita** na kojima `SUM3` i `MAJ` imaju *točno isti* skup
  ulaznih varijabli. Ne treba unaprijed poznavati naziv CPU,
  registara, signala ni raspored logičkih vrata.

Trenutno se prihvaćaju samo egzaktni stupanj-2 izrazi o tri
varijable s eventualnom konstantnom inverzijom. Nisu podržane
proizvoljne višebitne aritmetičke identitete, više taktova,
nelinearni izrazi višeg stupnja ni originalni RTL DRAT/LRAT.

## Provjera

`real6_motifs.py` otkriva parove prema monomima i naznačuje
izlaze. `real6_verify.py` ne uvozi detektor: ponovno poziva
neovisni REAL5-Q dokaz originalne gate mreže, a zatim računa
svih osam mogućih ulaza iz svakog točno zadanog polinoma i
provjerava funkciju `CH`, `MAJ` ili `SUM3`. Za par `FULL_ADDER`
obavezno uspoređuje tri iste varijable i dva različita fizička
izlaza. Provjerava SHA-256 originalnog Yosys gate netlista,
polinomnog certifikata i vezu svake etikete s izvornim sondiranim
bitom. Izmijenjeni dokaz se odbija.

**Granica dokaza:**

- `GLOBAL_ONE_STEP` — točan izraz u odnosu na primarne ulaze
  i slobodno trenutačno stanje flip-flopova, bez cutpointa.
- `CONDITIONAL_CUT_SYMBOLS` — točna veza nad **fizičkim
  cutpoint izlazima tretiranima kao slobodni simboli**; nije
  dokaz da cijeli izvorni sklop ima kvadratnu složenost.
- Nijedan status ne predstavlja dokaz izvorne četverovrijednosne
  SystemVerilog semantike, inter-ciklusnog ponašanja, ispravnog
  kriptografskog protokola ni SAT/UNSAT cijelog sklopovlja.

## Zaključani matematički testovi

GitHub Actions `45347547028` (PASS) prije odabira novih RTL
izvora: dva različita načina realizacije `MAJ`, izborni MUX,
`SUM3` i dva ispravno povezana full-adder izlaza,
uvjetni cutpoint obrazac i namjerno krivi prijenos.
Neovisni checker odbija šest vrsta izmijenjenog dokaza.

## Retrospektivni stvarni razvojni podaci

GitHub Actions `45347705001` (PASS), pet ranije poznatih
originalnih RTL netlista, **nije blind**.

| Stvarni modul | CH | MAJ | SUM3 | Full-adder |
|---|---:|---:|---:|---:|
| UART TX | 30 | 0 | 0 | 0 |
| AXI-Stream FIFO | 10 | 0 | 16 | 0 |
| PicoRV32 | 85 | 0 | 0 | 0 |
| AES S-box | 0 | 0 | 0 | 0 |
| SHA-256 W-MEM | 0 | 0 | 0 | 0 |

U 141 obrascu CH/SUM ima 29 potpuno globalnih dokaza
(UART), ostalo se oslanja na slobodne cutpointove.
**Nije** dokazan kompletan zbrajač u izvorima tog korpusa.
To može biti posljedica uskog polinomnog limita ili sondiranja
samo odabranih izlaza, a ne dokaz odsutnosti zbrajala.

## Novi prospektivni test

GitHub workflow `drnas-real6-blind.yml` počinje zaključavanjem
originalnog vanjskog izvora **nakon** zelenog matematičkog testa,
bez naknadnog podešavanja detektora:

- ChaCha originalni `chacha_qr`
- AES originalni `aes_key_mem`
- ZipCPU originalni `ufifo`
- Alex Forencich originalni `axis_adapter`
- Secworks originalni `sha512_core`

Svi ovi izvori ostaju u uzorku čak i kad originalni stari Yosys
ne može učitati ovisni modul ili ANF prekorači zadani limit
sondiranja, te takvo izvođenje nije dokaz gubitka Kissata ili
CaDiCaLa.

Za najviše tri automatski izdvojene dokazive gate-kone po
modulu izrađujemo stvarni miter između izvornog sintetiziranog
konusa i njegove polinomne formule. **Kissat i CaDiCaL dobivaju
identičan DIMACS**, 1 CPU po pokušaju, dva ponavljanja i
10 s limita. Uz to se pokreće Yosysov neovisni lokalni dokaz.
Ako nisu pronađeni REAL6 motivi, dopušten je zasebno označen
REAL5-Q polinomni kontrolni konus, nikad lažno predstavljen
kao CH/MAJ/full-adder.

Prepoznavanje motiva i lokalni miter **nisu** ista stvar kao
rješavanje cijelog izvornog SAT zadatka. Za standardni UNSAT
nisu automatski proizvedeni/verificirani DRAT ili LRAT dokazi.

## Sljedeća stvarna granica

Potrebno je otkrivanje polinomnih obrazaca unutar dubljih
unutarnjih konusa, precizno automatsko učitavanje HDL
ovisnosti, sondiranje opravdano uporabom u stvarnim
izlaznim/stanjskim relacijama i složenije n-bitne
zbrajalačke mreže s dokazom propagacije prijenosa.
