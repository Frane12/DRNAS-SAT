# DRNAS SAT — Modulna razmjena 2-SAT → XOR → VeriPB: ponovljeni audit

**Datum:** 21. studenoga 2026.  
**Eksperimentalna grana:** `experiment/hybrid11-modular-bridge-ablation-20261121`  
**GitHub Actions:** https://github.com/Frane12/DRNAS-SAT/actions/runs/44942684324  
**Status:** PASS, strogo ograničena razvojna demonstracija; bez izmjene `main`.

## Što je doista spojeno

1. Zasebni proces `signed_2sat_exchange.py` čita izvorni DIMACS CNF, prepoznaje točno-jedan izbor i mrežu XOR klauzula, rekonstruira potpisane 2-SAT ekvivalencije i izdaje **izvorno vezanu JSON poruku**, ne SAT/UNSAT odgovor.
2. Za svaki par `x,y` šalje bit `d` za `x XOR y = d` i dva eksplicitna puta implikacija. Poruka je vezana SHA-256 sa sadržajem ulaza.
3. Drugi proces `emit_veripb_indirect.py --exchange ... --require-exchange` **sam ponovno provjerava** SHA, svaki korak oba puta prema izvornim binarnim klauzulama, dopuštene varijable, XOR vrata i globalnu paritetnu strukturu. Emitira original-source VeriPB RUP/RED/CP dokaz.
4. Neovisni **VeriPB 3.0.2** prihvaća dokaz protiv istog neizmijenjenog CNF-a. Odbijen ili nepotpun ulaz vraća UNKNOWN; poruka sama nikada ne autorizira UNSAT.
5. ABLACIJA OFF izričito onemogućuje prijenos u **modularnom** načinu rada. Postojeći **monolitni HYBRID11 može i dalje dokazati iste formule sam**. OFF stoga nije usporedba protiv općeg SAT solvera.

## Ponovljeni rezultati (GitHub Actions)

Tri konstruirana izvora, svaki SHA-fiksiran i izveden tri puta, jednom logičkom CPU jezgrom po pozivu. Vremena su wall-clock po procesu, uključujući Python pokretanje i vanjski VeriPB, ali ne i vrijeme stvaranja CNF-a ni cjelokupnog CI pripremanja.

| CNF izvor | Ponavljanja | Razmjena → VeriPB | Izravni monolitni → VeriPB | Bitno jednaki dokazi |
|---|---:|---:|---:|---:|
| split8 | 3 | 3/3 VERIFIED UNSAT | 3/3 VERIFIED UNSAT | 3/3 |
| mixed12 | 3 | 3/3 VERIFIED UNSAT | 3/3 VERIFIED UNSAT | 3/3 |
| permuted16 | 3 | 3/3 VERIFIED UNSAT | 3/3 VERIFIED UNSAT | 3/3 |
| **Ukupno** | **9** | **9/9** | **9/9** | **9/9** |

**Medijan ukupnog wall vremena po pokušaju:**  
- Razmjena + emitter + vanjski VeriPB: **0,105551 s**.  
- Izravni monolitni emitter + VeriPB: **0,063533 s**.  
- Dodatni trošak modularne komunikacije: **oko 66 %** u medijanu (različit broj Python procesa i dodatna provjera putova).

**Sigurnosni testovi:** 2/2 krivotvorene poruke (SHA i implikacijski put) odbijene; 4/4 kontrolne CNF formule (SAT, broken_link, missing_amo, missing_gate) ostale UNKNOWN; 9/9 OFF-modularnih izvođenja UNKNOWN.

Zasebni CSV redci, hashovi ulaza, izvorni CNF, razmijenjene poruke, VeriPB dokazi i kompletni stdout/stderr logovi nalaze se u GitHub Actions artefaktu `DRNAS-HYBRID11-2SAT-XOR-bridge-3repeat`.

## Vrijednost i granice

**Potvrđeno:** dvije zasebne logičke faze razmjenjuju konkretne matematičke činjenice, prijamnik ih ponovno dokazuje iz izvornoga CNF-a, vanjski alat verificira nastali UNSAT. Ponovljeno je tri puta na tri različite konstruirane kodifikacije. Odbijanje pokvarenih poruka ispravno funkcionira.

**Nije potvrđeno:** povećana brzina ili novi riješeni slučajevi zbog same razmjene; monolitni program već je rješavao iste formule i u ovim mjerenjima bio brži. Nije potvrđena opća komunikacija GRAPH/PCMAX/MATH5 u jednom C++ procesu ni uspjeh na novim originalnim benchmark obiteljima.

## Sljedeći najmanji korak

Jedna nova korisna matematička veza, bez dodavanja svih modula odjednom: neka **GRAPH** preda izvornu kliku i veze boja **kapacitetnom / Hall modulu**, pa tražiti izvorni CNF gdje tek zajednički zaključak, a ne samostalna dva detektora, omogućuje novi standardno verificirani dokaz. Prije proširenja zahtijevati ON/OFF/SOLO ablacijski test, neovisne certifikate i jednako CPU/verification-inclusive mjerenje.
