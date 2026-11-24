# DRNAS REAL6 — konačni rezultat na pet novih stvarnih sklopova

**Istraživanje:** Frane Drnas  
**Datum:** 24. 11. 2026.  
**Grana:** `experiment/real6-motif-linking-20261124`  
**Završni GitHub Actions test i neovisni audit:**
[run 45348217885](https://github.com/Frane12/DRNAS-SAT/actions/runs/45348217885).  
**Završni dokazni artefakt:**
[REAL6 originalni izvori i JSON rezultati](https://github.com/Frane12/DRNAS-SAT/actions/runs/45348217885/artifacts/14899561606).

## Metoda

Prethodno provjereni i SHA-256 zaključani `real6_motifs.py`
i `real6_verify.py` (zeleni test
[45347547028](https://github.com/Frane12/DRNAS-SAT/actions/runs/45347547028))
primijenjeni su bez prepravljanja na **pet prethodno neviđenih javnih
originalnih RTL modula**. Git commit i Git blob SHA-1 svakog modula
provjereni su prije mjerenja.

Matematički detektor ne traži posebna imena sklopova.
Ulaz su točni, ranije neovisno verificirani Booleovi polinomi
`REAL5-Q` iz sintetizirane Yosys logičke mreže.
Motivi `CH`, `MAJ`, `SUM3` i povezivanje dva izlaza u
jednobitno puno zbrajalo provjeravaju se na svih
`2³ = 8` kombinacija ulaznih bitova.

## Rezultati

| Novi originalni RTL | Yosys | CH | MAJ | SUM3 | Parovi punog zbrajala | Globalno | Uz slobodne nelinearne cutpointove |
|---|---|---:|---:|---:|---:|---:|---:|
| secworks ChaCha quarter-round | OK | 0 | 0 | 0 | 0 | 0 | 0 |
| secworks AES key memory | OK, ali analiza staje na `PROBE_BUDGET` | — | — | — | — | — | — |
| ZipCPU UART FIFO | OK | **16** | 0 | **3** | 0 | **10** | **9** |
| alexforencich AXI adapter | OK | 0 | 0 | 0 | 0 | 0 | 0 |
| secworks SHA-512 core | `FRONTEND_OR_DEPENDENCY_UNSUPPORTED` | — | — | — | — | — | — |

- **5/5** unaprijed zaključanih izvora evidentirano.
- **4/5** originalnih modula sintetizirano; jedan nije mogao
  dovršiti elaboraciju zbog fronte/ovisnosti.
- **3/3** proizvedenih ANF gate certifikata neovisno re-evaluirano.
- **3/3** povezanih REAL6 certifikata neovisno re-evaluirano.
- **19 novih obrazaca** (16 CH, 3 SUM3), 10 globalnih i 9
  samo uvjetno lokalnih; svih 19 potječe iz UART FIFO-a.
- **0** MAJ obrazaca i **0** kompletnih spojenih full-adder
  parova u ovom testu. Ne tvrditi da u izvorima nema zbrajala:
  možda su previše duboka ili uzorkovanje nije obuhvatilo oba pina.

## Kissat, CaDiCaL i Yosys kontrole

Ukupno je izdvojeno **6 originalnih lokalnih gate-cone mitera**.
Svaki je izvođen iz neizmijenjene sintetizirane mreže i točnog
GF(2) certifikata. Kissat i CaDiCaL dobili su **identičan
DIMACS** po mikrostrukturi i dva ponavljanja, ograničenje
10 s i jedan logički CPU po pokušaju.

| Skupina lokalnih kona | Yosys formalno | Kissat | CaDiCaL |
|---|---|---|---|
| UART FIFO, 3 originalna motivska kona | **3/3 dokazano** | 6/6 prijavljeno UNSAT | 6/6 prijavljeno UNSAT |
| ChaCha, 3 generička REAL5-Q kontrolna kona (nisu REAL6 motivi!) | **0/3 dokazano** | **6 timeoutova** | **6 timeoutova** |

Dakle, ukupno **3/6** Yosys lokalnih identiteta formalno
potvrđena; **12/24** poziva Kissata i CaDiCaLa prijavilo UNSAT,
a **12/24** je isteklo na 10 s. Ovo je važno prikazati, ne
pretvarati timeout u pobjedu našeg algoritma.

**Znanstvena granica:**
Unatoč matematičkim provjerama izvornog ANF certifikata,
neprovjereni ChaCha kontrolni miteri zahtijevaju
dodatnu istragu kvalitete izdvajanja i opsega provjere,
ne proglašavanje potvrđenog formalnog rezultata.
Ne postoje dodatno replay-verificirani standardni
DRAT/LRAT dokazi prijavljenih UNSAT statusa.

## Što su nas stvarni sklopovi naučili?

1. **REAL6 nalazi CH i XOR3 u neviđenom UART FIFO-u** uz
   neovisnu matematičku provjeru. Tu je smislen rezultat.
2. **REAL6 nije našao MAJ ni puni zbrajač u pet izvora**;
   širinu uzorkovanja i prepoznavanje propagacije prijenosa
   treba istražiti prije daljnjih afirmacija.
3. **Sinteza i limiti sondiranja su aktivna istraživačka
   ograničenja.** AES memorija nije riješena niti proglašena
   nemogućom, a SHA512 core ne pruža potpun gate netlist.
4. **Čak i kad je polinom provjeren, generički veliki gate
   miter može biti teži od 10 s.** To nije automatski dokaz
   prednosti nad Kissatom ili CaDiCaLom, nego zahtijeva
   kvalitetnije granice lokalnih certifikata.

## Sljedeći ciljani korak

Novi izolirani `REAL6.1`: detekcija full-adder odnosa
iz izvornog aritmetičkog konusa uz automatske granice
bitnih prijenosa i protuprimjere na krivim zbrojevima;
te selektivno, dokazno sigurno povećanje `PROBE_BUDGET`
i učitavanje SHA-zaključanih ovisnih modula. Svaku
promjenu treba zaključati na novom razvojnom korpusu
**prije** sljedeće prospektivne provjere.

**Ne tvrditi dokaz cijelog RTL programa, hardversku
formalnu certifikaciju, temporalnu ispravnost, industrijsko
PPA ubrzanje niti općeniti napredak protiv P ≠ NP.**
