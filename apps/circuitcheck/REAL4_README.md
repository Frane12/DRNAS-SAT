# DRNAS REAL4 — zamrznuti slijepi pokus na nepoznatim RTL modulima

**Autor istraživanja:** Frane Drnas  
**Grana:** experiment/real4-blind-gate-cuts-20261124  
**Main:** nije mijenjan.

## Cilj

Ispitati može li se matematička struktura izdvojiti iz *neviđenih*
izvornih HDL projekata **bez prepoznavanja posebnog naziva projekta,
CRC polinoma, varijable ili već pripremljene ručne klase problema**.

Za razliku od REAL2/REAL3, REAL4 ulaz čita kao proizvoljnu Yosys
techmapanu mrežu logičkih ćelija. Algoritam ne poznaje niti jedan
upstream Git SHA, ime ni familiju korištenih testnih sklopova.

**Kontrolirani blind postupak:** nezavisni program detektora
`real4_islands.py` i provjerivač `real4_verify.py` uspješno su testirani
i SHA-zaključani u GitHub Actions runu
[45339922757](https://github.com/Frane12/DRNAS-SAT/actions/runs/45339922757)
*prije* odabira šest stvarnih novih RTL izvora. Njihovi SHA-256
provjeravaju se prije svakog mjernog pokušaja i u završnom auditu.
Naknadno se ne smiju mijenjati prema rezultatima testnih izvora.

## Matematika i svojstvo koje stvarno dokazujemo

Za pojedini bit sintetizirane mreže razmatramo:

`f(x,q,z)=c XOR Σ a_i x_i XOR Σ b_j q_j XOR Σ d_k z_k`

gdje su `x` primarni ulazi, `q` slobodni trenutačni izlazi
sekvencijskih registara, a `z` izlazni signali fizičkih nelinearnih
ili nepodržanih logičkih ćelija — **cutpointovi**.

- Ako izraz ne ovisi ni o jednom `z`, dobili smo **globalno
  afinu jednodobnu funkciju** nad `x` i `q`, za taj pojedini bit
  iz sintetizirane mreže.
- Ako ovisi o barem jednom `z`, dobili smo **lokalnu afinu
  funkciju relativno prema stvarnim izlazima nelinearnih ćelija**.
  To je egzaktna algebra zamjenom `z` nazad stvarnim signalima,
  ali **nikad nije dokaz da je cijeli sklop afini**.
- Ako se pojavi X/Z, nedriveni signal, kombinacijska petlja,
  višestruki driver ili prekoračenje ograničenja analize,
  rezultat se prijavljuje kao **UNKNOWN**.

Za FF registre Q se tretira kao slobodno trenutno stanje,
a D pinovi kao zasebni izlazi za dokazivanje jednog prijelaza.
To nije dokaz reset sekvence, dosegljivosti, vremenskog svojstva,
bezgraničnog ponašanja automata niti formalna zamjena za BMC/IC3.

### Neovisna provjera

`real4_islands.py` računa GF(2) funkciju preko bit-maskih
koeficijenata, dok `real4_verify.py` ponovno prolazi istu
nepromijenjenu sintetiziranu mrežu preko skupova varijabli,
neovisno rekonstruira sve linearne i nelinearne granice
te odbija svaki nepodudarni dokaz. Sve matematičke tvrdnje
ovise o Yosysovu 2-state spuštanju izvornog RTL-a u gate netlist;
nije proizveden neovisni izvorno-jezični Verilog semantički dokaz.

## Šest zaključanih originalnih izvora

Svaka originalna upstream HDL datoteka čuva se bez preinaka,
s commitom, Git blob SHA-1 i SHA-256 u `frozen/manifest.json`.

| Projekt | Vrsta nepoznatog originala | Primarna uloga |
|---|---|---|
| secworks/aes — aes_sbox | AES S-box | kontrola nelinearnosti |
| ZipCPU/wbuart32 — txuart | UART odašiljač | sekvencijski automat |
| alexforencich/verilog-axis — axis_fifo | AXI streaming FIFO | kontrole i spremnik |
| YosysHQ/picorv32 — picorv32 | RISC-V procesor | veliki stvarni CPU |
| hdl-util/hdmi — tmds_channel | HDMI/TMDS | paritet i kodiranje |
| secworks/sha256 — sha256_w_mem | raspored SHA-256 riječi | aritmetika, sekvence |

Nijedan izvor ne izbacuje se ako Yosys ne uspije sintetizirati
originalni HDL unutar 100 s ili ako REAL4 ostane bez dokaza.
Takav ishod nije dokaz poraza SAT solvera.

## Kissat i CaDiCaL

`real4_miter.py` iz zaista sintetizirane Yosys mreže izdvaja do tri
provjerene mikrostrukture. Za svaku generira miter:

`mismatch = originalni precizni gate-cone XOR matematički GF(2) izraz`

s nelinearnim cutpointovima kao **slobodnim simbolima**.
Kissat i CaDiCaL dobivaju isti generirani CNF uz jedan CPU,
dva ponavljanja i 10 s limita po pokušaju. SAT rješenje bi
bilo alarm neispravnosti našeg mikro-dokaza. Prijavljeni UNSAT
bez standardnog DRAT/LRAT checkera dodatni je kontrolni
ishod, ne samostalno formalno certificirani globalni UNSAT.

**To nije CNF cijelog nepoznatog CPU-a / AES-a**, nije izravno
mjerilo ubrzanja globalnog SAT solvera i nije dokaz vrijednosti
originalnog IP-a prema njegovoj vanjskoj specifikaciji.

Za model koji nema dokazivu mikrostrukturu nećemo generirati
izmišljeni SAT kontrolni rezultat; izvještaj kaže
`NO_CERTIFIED_CONE`, uz razlog nedostupnosti.

## Neizmijenjeni algoritam i auditi

- `real4_islands.py` — pre-lock strukturni detektor.
- `real4_verify.py` — pre-lock neovisni certifikacijski replay.
- `real4_selftest.py` — 80 randomiziranih logičkih mreža, FF Q,
  nelinearne cut granice, slučajevi X/Z i napadi na certifikat.
- `real4_freeze.py` — freeze *nakon* green prelock runa.
- `real4_run.py` — 3 paralelna izračuna, 2 izvora po poslu,
  1 CPU po solveru, Yosys limit 100 s, odvojeni SAT benchmark.
- `real4_miter.py` — mikro-miter za dokazive realne gate-cone izlaze.
- `real4_audit.py` — ponovno pokreće neovisni replay za svako
  potvrđeno izvorno stanje, priznaje neuspjehe i provjerava
  prelock SHA-256 algoritma.
- `.github/workflows/drnas-real4-blind.yml` — cijeli protokol.

Prilikom interpretacije razlikovati:
1. pronalazak lokalnog GF(2) zakona;
2. dokaz punog globalno afinog bitnog izlaza;
3. dokaz trenutnog prijelaza nad FF Q ulazima;
4. formalni SAT/UNSAT cijelog projekta — još nije riješen.

**REAL4 je istraživački strukturni analizator, ne univerzalni SAT solver.**
