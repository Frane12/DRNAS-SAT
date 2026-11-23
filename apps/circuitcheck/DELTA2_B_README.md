# DELTA2-B — kompozicijski dokaz dugih afinih prijelaza

**Istraživanje: Frane Drnas**  
Branch: `experiment/circuitcheck-delta2b-compose-20261123`  
Original `main` untouched.

## Matematička funkcija

U otkrivenom jednodobnom zakonu `s_(k+1)=A*s_k XOR B*x_k XOR c`
DELTA2-B dobiva A, B, c samo iz **Yosys sintetiziranog jednog koraka**
koji je prethodno izdvojen prepoznavanjem RTL `for`-petlje.
Polinom CRC-a ili nazivi registara ne unose se unaprijed.

`s_N=A^N s_0 XOR Σ_(k=0)^(N-1) A^(N-1-k)*B*x_k XOR c_N`

- `A^N` i `c_N` računaju se binarnim potenciranjem afinih transformacija.
- Koeficijenti za sve ulazne bitove izračunavaju se obrnutim propagiranjem
  jednog vektora `A^j B`; to je još uvijek **linearno u broju ulaznih bitova**
  po fiksnoj širini stanja, a ne opći polinomni algoritam za SAT.
- **Bez sintetiziranja svih N serijskih koraka** u brzom načinu rada.
- Neovisni `delta2b_verify.py` ponovno računa koeficijente **drugim
  algoritmom**, izravnom simboličkom iteracijom, i posebno ponavlja svaki
  Yosys netlist afini certifikat kroz `delta1_verify.py`.

## Dvije razine sigurnosti dokaza

1. `python3 apps/circuitcheck/delta2b.py --rtl my.v --reference reference --candidate candidate --out result`

   Brza kompozicija + neovisni dokaz pojedinačnog prijelaza, finalizacije,
   kandidata i matematičke kompozicije. Rezultat je **uvjetan** na
   ispravnost izvlačenja RTL petlje; nije pun dokaz sirovog Veriloga.

2. `python3 apps/circuitcheck/delta2b.py --rtl my.v --reference reference --candidate candidate --out result-audited --full-rtl-audit`

   Sve iz prve faze **plus** DELTA1 formalna provjera
   **originalni referentni RTL ↔ automatski generirani paralelni Verilog**,
   uključujući nezavisni replay certifikata. Ta provjera i dalje vjeruje
   Yosys prevođenju RTL-a u dvovrijednosnu logičku mrežu.

Brzo i puno ne smiju se uspoređivati kao ekvivalentno jaki dokazi.
Ni jedna metoda još ne daje originalni CNF DRAT/LRAT dokaz ni
pouzdanu potpunu formalnu verifikaciju proizvoljnog Veriloga.

## Eksperimentalni protokol

- Originalni zamrznuti CRC-32 `crc_64` i `crc_2048`, svaki
  jednak i s namjerno promijenjenim izlazom, preuzet iz izvornog
  GitHub Actions runa `45245092918`.
- Dva brza izvođenja i jedno odvojeno s potpunom RTL provjerom.
- Svako izvođenje ograničeno jednim logičkim CPU-om; brzom postupku
  dopušteno do 45 s, strogom do 180 s.
- SHA-256 originalnog izvora, izvedenog modela, gate netlista i
  certifikata zabilježen i provjeren.
- Matematička regresija: 300 proizvoljno generiranih afinih
  transformacija i direktna neovisna supstitucija.
- Adversarijalni testovi: mijenjanje izvornog SHA-a, matrice,
  koeficijenata izlaza, kandidata i gate netlista mora rezultirati
  odbijenim certifikatom.

## Najvažnije ograničenje i sljedeći korak

Otkrivanje granica danas se radi iz **strogo podržane RTL petlje**,
ne iz proizvoljno optimizirane ravne mreže. Uz provjeru cijelog
originala izbjegnuta pretraga opet zahtijeva skupu sintezu.
Sljedeće istraživanje treba proizvesti **mali provjerljiv certifikat
koji iz veze izvorne petlje i jednog koraka dokazuje ekvivalenciju
bez razvijanja svih N koraka**, uz potpuno neovisan frontend ili
kontrolirani formalni sustav za ograničeni RTL podskup.

**Ne tvrditi industrijski FPGA signoff, opću P/NP prekretnicu,
fizičko ubrzanje hardvera niti da Kissat i DELTA2-B dobivaju isti CNF.**
