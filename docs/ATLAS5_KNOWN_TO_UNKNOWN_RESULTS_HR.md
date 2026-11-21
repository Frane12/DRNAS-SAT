# DRNAS SAT — ATLAS5: od poznatog matematičkog pravila do dokazive CNF formule

**Datum:** 21. studenoga 2026.  
**Eksperimentalna grana:** `experiment/atlas5-known-to-unknown-proofchain-20261121`  
**GitHub Actions audit (PASS):** https://github.com/Frane12/DRNAS-SAT/actions/runs/44950781478  
**Status:** reprodukcija poznatoga dokaznog mehanizma u modularnom Atlasa; nije nova, prethodno nepoznata natjecateljska UNSAT pobjeda. `main` nije mijenjan.

## Zašto ovaj eksperiment?

ATLAS4 je na deset originalnih CNF formula iz sedam obitelji potvrđivao izvorne EO/XOR/GRAPH činjenice, ali nije izveo standardni UNSAT. ATLAS5 provjerava može li se EXISTING, općenito valjana matematička metoda umetnuti između detektora i dokaznog izvoznika bez imenovanja obitelji, te dobiti stvarni vanjski potvrđeni rezultat.

Poznato pravilo: za jednadžbe nad GF(2) s potvrđenim izvornim klauzulama, ako se neka kombinacija redaka zbroji u `0=1`, CNF je UNSAT. Nužno je sačuvati točne izvorne redove, potvrditi svaku premisu i izdati vanjski standardni dokaz; sama matematička pretpostavka nije dovoljan certifikat.

## Provjerljiv cjeloviti lanac

1. `source_facts.py` prepoznaje potpune XOR2/3/4 CNF tablice isključivo iz izvornih klauzula.
2. **Neovisni izvorni kontrolor** `check_facts.py` ponovno provjerava prisutnost svake zabranjene XOR kombinacije u istom SHA-256 vezanom originalu.
3. `xorlin1/extract.py` funkcija `gaussian` kao **odvojeni matematički zaključni modul** prima samo potvrđene redove, izvodi eliminaciju i vraća precizan podskup redova koji daje proturječje `0=1`. Ako takve kombinacije nema, vraća UNKNOWN.
4. `check_math5.py` neovisno ponovno provjerava izvorno odabrane redove i globalni paritet.
5. `xorlin1/emit_veripb.py` kompilira izvorno vezan redoslijed RED, RUP i CP koraka.
6. Samo **VeriPB 3.0.2** koji prihvati potpuni neizmijenjeni izvornik i emitirani PBP daje status `STANDARD_VERIPB_VERIFIED_UNSAT`.

## Izvorni natjecateljski test

Deset već SHA-fiksiranih originalnih SAT Competition 2025 Main CNF-ova (sedam obitelji), obnovljeno iz javne GBD baze s prethodno poznatim izvornim hashovima. Ta su pitanja već ranije analizirana; ovo je RETROSPEKTIVNA provjera modulske integracije, ne novi slijepi holdout.

| Ishod | Broj |
|---|---:|
| Izvorni CNF-ovi | 10 |
| Različite problemske obitelji | 7 |
| Izvorno provjerene matematičke činjenice pod limitom | 4/10 |
| Izvorno potvrđen standardni VeriPB UNSAT | **1/10** |
| Siguran UNKNOWN | **9/10** |
| Tri permutacije potvrđene formule | **3/3 standardno VeriPB VERIFIED UNSAT** |
| Krivotvorena premisa, izbrisana iz izvornika i osuvremenjen SHA u tvrdnji | **1/1 odbijena** |
| Kritična nepravilnost | **0** |

**Originalni ID6 Tseitin:** sirovi SHA-256 `9e4c57b9739f39a924d03267f05542831dc87fec9e9e2238f5e4ba11886378f4`, 282 varijable, 752 klauzule, 188 izvornih XOR3 relacija; izlučeno svih 188 redova i dobiven izvorni VeriPB dokaz od **76.967 bajtova**, SHA-256 `70b7f97138400c4ab8167822f85ce4f00b9bb9fda616440911e0b72ed7b5a48a`. Taj isti dokaz i ishod **već su bili poznati iz 17. studenoga**: `research/MATH5_XOR3_CARRY_VERIPB_RESULTS.md`. Naš dokazni lanac je iz source-only Atlasa ponovno došao do njega i SHA dokaza se podudara s prethodno objavljenom vrijednošću.

**Permutacije ID6:** tri unaprijed zadana slučaja (sjeme 101: promjena naziva i poretka; 202 i 303: dodatno različite promjene polariteta). Svaki je ekvivalentan poznatom originalu točnom inverznom mapom, svaki je iznova prepoznat, provjeren i dobio zaseban, original-source-vezan standardni VeriPB UNSAT dokaz.

**Preostalih devet originala:** šest je isključeno po unaprijed definiranom limitu veličine/varijabli/klauzula za postojeći GF2 proof emitter, tri su bila obuhvaćena ali nemaju potpunu izvornu XOR tablicu pod ovim detektorom. Nijedan UNKNOWN nije SAT tvrdnja. Za te izvore Atlas može imati druge verified činjenice iz prethodnog, šireg audita.

## Koju opću zakonitost smo operacionalizirali?

Matematička tvrdnja:

\[
\bigoplus_{i\in I}\left(\bigoplus_{v\in S_i}x_v=b_i\right)
\quad\text{uz }\bigoplus_{i\in I}S_i=\varnothing,\quad
\bigoplus_{i\in I}b_i=1\implies\mathrm{UNSAT}.
\]

Indeksi se izvode Gaussovom eliminacijom i ostaju vezani uz dokazivo prisutne izvorne klauzule. Metoda je poznata; doprinos Atlasa 5 je sigurna modularna integracija i potvrđena reprodukcija na neizmijenjenom natjecateljskom CNF-u i njegovim trima preslagivanjima.

## Sljedeći najmanji korak iz UNKNOWN prema poznatom

Prvi izbor je original **ID8 `random-graph-xorsat`** sa SHA `f9dcbbbcb2abc290439c21978d04cdc44efffbed9b4e5cdee96dd63856a5a156`: naziv sugerira XOR, ali postojeći detector ne vidi **nijednu izvornu potpunu XOR2/3/4 tablicu**. To NIJE dokaz da u formuli postoji skriveni XOR: sljedeći korak treba iz same CNF strukture, nezavisno od naziva, izvući moguće XOR jednadžbe kroz manje implikacije, pomoćne varijable i definicijske tragove, a svaku novu jednadžbu *dokazati* original-source RUP/RED/VeriPB koracima. Ako se ne može dokazati, ostaje UNKNOWN.

Drugi izbor: problem Independent Set/Reconfiguration velikog izvora, s prepoznatim kardinalnim i grafovskim činjenicama; pokušati dokazive kombinacije donje potražnje i gornjeg Hall/GRAPH kapaciteta. Nitko ne smije prihvatiti novo rješenje bez neovisne standardne verifikacije.

Nije potvrđeno da svi stvarni SAT problemi dijele konačan broj lako otkrivih obrazaca ili da su sve kodifikacije jednostavno normalizabilne. ATLAS mjeri stvarnu pokrivenost i bilježi gdje je svaki dokazni lanac zapeo.

## Reprodukcija

```bash
python3 research/structure_atlas4/freeze10.py
python3 research/structure_atlas5/known_to_unknown.py
```

GitHub artefakt `DRNAS-ATLAS5-known-to-unknown-veripb` sadrži originalne source manifest hashove, pojedinačne UNKNOWN statuse, SHA svakoga izlučenog originalnog/paritetnog dokaza, tri permutirane CNF datoteke, VeriPB certifikate i rezultate.
