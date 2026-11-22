# DRNAS SAT — ATLAS 13: prava razmjena matematičkih činjenica XOR2 → GRAPH → HALL

**Datum:** 22. studenoga 2026.  
**GitHub CI:** [run 45014430245 — SUCCESS](https://github.com/Frane12/DRNAS-SAT/actions/runs/45014430245)  
**Grana:** `experiment/atlas13-xor-graph-hall-joint-20261122`, produkcijski `main` netaknut.  
**Status:** **4/4 standardnih original-source VeriPB UNSAT dokaza**, plus četiri sigurnosne kontrole.  
**Ograničenje:** sve formule **konstruirani mali kontrolni CNF-ovi**, ne novi javni originalni SAT Competition primjeri i ne generalni dokaz P=NP.

## 1. Znanstveni problem koji testiramo

U ATLAS12 kombinirali smo poznati GRAPH full-clique prepoznavač i poznati Hall/PCMAX dokazni izvoznik. To je omogućilo prijenos provjerenih činjenica, ali nismo pokazali slučaj koji pojedinačno **ni jedan** izvorni modu(l) ne bi mogao riješiti.

U ATLAS13 na unaprijed fiksiranim konstruiranim izvorima iz `research/atlas13_joint/prespec.json` ispitujemo stroži uvjet:

1. `GRAPH_ONLY`: ne nalazi potpuno usklađenu klik(u) potrebnu svojoj zasebnoj metodi, vraća **UNKNOWN**.
2. `HALL_DIRECT_ONLY`: u izvornom CNF-u nedostaje jedna binarna zabrana da bi svaka resursna skupina bila potpuno izvorno dokazana mutex-klika; vraća **UNKNOWN**.
3. `XOR_ONLY`: potpune izvorne XOR2/EO jednadžbe nisu kontradiktorne u GF(2); vraća **UNKNOWN**.
4. `XOR → GRAPH → HALL`: jedna izvorno potvrđena XOR2 jednakost daje novi izvorno RUP-opravdani sukob, koji dovršava Hallovu kapacitetnu proturječnost; vanjski VeriPB mora prihvatiti **UNSAT** na neizmijenjenom originalnom CNF-u.

Uspjeh je moguć samo uz **istinsku inferencijsku razmjenu** jedne nove činjenice, ne tek fallback iz GRAPH u samostalni HALL.

## 2. Formalni matematički dokaz i provenijencija izvornih klauzula

Izvor sadrži neposredne klauzule

```
(~a OR z)   (a OR ~z)   (~z OR ~b)
```

Prve dvije su kompletna izvorna XOR2 jednadžba

\[
a\oplus z = 0\quad\Longleftrightarrow\quad a=z.
\]

Treća uvjetuje

\[
\neg z\lor\neg b.
\]

Kada je \(a=b=1\), prva klauzula izravno forsira \(z=1\), dok treća forsira \(z=0\). Nastaje sukob jednostavnom propagacijom jedinica; zato je sljedeća nova zabrana **izvorni RUP zaključak**:

\[
\boxed{\neg a\lor\neg b}.
\]

Ta klauzula **nije bila u izvornom CNF-u**. Ona je **dokazani novi brid** u resursnom grafu: zabranjuje da dva različita zahtjeva istodobno zauzmu isti resurs.

Za svaki posao \(i\) zasebna originalna pozitivna ALO i parovna AMO provjeravaju `EXACTLY-ONE` skup mogućnosti. Skupovi su međusobno disjunktni, a njihove alternative resursni modul pokušava prekriti resursnim klikama. Samo je jedna parovna resursna zabrana nedostajala prije dokaza XOR2 pravila. Nakon nje svaka resursna klika ima sve izvorne ili standardno RUP-izvedene zabrane. Stoga slijedi poznati Hallov argument:

\[
\sum_{x\in \cup G_i}x\ge d,\qquad
\sum_{x\in\cup R_j}x\le c,\qquad
d>c\implies \mathrm{UNSAT}.
\]

Ovo je **kombinacija poznatih matematičkih teorema**, ne nova kompleksnosna klasa.

## 3. Granice povjerenja i neovisna vanjska verifikacija

`discover.py` **dobiva samo originalne DIMACS bajtove**. Ne koristi poznate uloge varijabli iz generatora, očekivani SAT/UNSAT, naziv benchmarka, prethodni model ni izvještaj.

Proizvođač rekonstruira pozitivne disjunktne ALO grupe, potpune XOR2 redove, grafovski povezane komponente iz izvornih binarnih mutex klauzula i sve njihove nedostajuće zabrane. Prihvaća samo konkretno potkrijepljen izvorni obrazac dvostruke XOR2 jednakosti i odgovarajuće binarne implikacije.

`independent.py` ne uvozi prepoznavač ili proof compiler i zasebno ponovno provjerava:

- izvorni SHA-256, ispravan DIMACS header i ukupan broj klauzula;
- originalnu ALO i svaki originalni par AMO unutar svake EO grupe;
- međusobnu disjunktnost svih EO varijabli;
- točno pokrivanje odabranih varijabli resursnim skupinama;
- izvornu mutex klauzulu za svaki izvorni resursni par;
- svaku **nedostajuću** mutex zabranu, punu originalnu XOR2 tablicu, binarnu implikaciju i izvorno jedinično propagacijsko proturječje pod \(a=b=1\);
- posebnu kontrolu da RUP proturječje **nestaje nakon uklanjanja izvornih XOR2 klauzula**. To potvrđuje da je XOR2 činjenica potrebna ovom konkretnom izvodu, a ne samo slučajno prisutna.

`emit.py` nakon toga ne prepisuje izvor: započinje VeriPB dokaz s `f N` izvornim klauzulama, dodaje novu zabranu kao formalni `rup`, zatim koristi `pol` korake za svaku resursnu kliku i završni Hall deficit. Status izvornog izvoznika ostaje `EMITTED_EXTERNAL_VERIPB_REQUIRED`.

**Vanjski VeriPB 3.0.2** potom ponovno provjerava cijeli dokaz **na istom originalnom CNF-u** i jedini smije dodijeliti `STANDARD_ORIGINAL_CNF_VERIPB_VERIFIED_UNSAT`.

Primjer za k=3 u potpunom standardnom VeriPB obliku iz stvarnog CI artefakta:

```text
pseudo-Boolean proof version 3.0
f 18 ;
rup 1 ~x7 1 ~x8 >= 1 ;
pol 11 7 + 17 + 2 d ;
pol 18 15 + 19 + 20 2 * + 3 d ;
pol 4 2 + 1 + 12 + 21 + 8 + 5 + ;
output NONE ;
conclusion UNSAT ;
end pseudo-Boolean proof ;
```

## 4. Rezultati GitHub CI-a: tri zasebne konstruirane instance i jedna permutacija

| Konstrukcija | Izvorni CNF | Izvorni EO | Izvorno nepostojeći resursni mutex | Samostalni GRAPH / HALL / XOR | Zajednički Hall | Neovisni VeriPB |
|---|---|---:|---:|---|---:|---|
| 4 zahtjeva / 3 resursa | 9 var., 18 klauzula | 4 | 1 | UNKNOWN / UNKNOWN / UNKNOWN | **4 > 3** | **UNSAT verified**, 211 B |
| Permutacija iste formule | 9 var., 18 klauzula | 4 | 1 | UNKNOWN / UNKNOWN / UNKNOWN | **4 > 3** | **UNSAT verified**, 210 B |
| 5 zahtjeva / 4 resursa | 11 var., 20 klauzula | 5 | 1 | UNKNOWN / UNKNOWN / UNKNOWN | **5 > 4** | **UNSAT verified**, 214 B |
| 6 zahtjeva / 5 resursa | 13 var., 23 klauzule | 6 | 1 | UNKNOWN / UNKNOWN / UNKNOWN | **6 > 5** | **UNSAT verified**, 224 B |

**4/4** standardno prihvaćena original-source VeriPB UNSAT dokaza. Svaki je došao s točno jednom novom XOR2-izvedenom mutex zabranom. Razlikovati **3 različite konstrukcije** i jednu koreliranu permutaciju — ne zvati ih četiri nezavisne formul(e).

Izmjereni izvorno-matematički E2E za ove vrlo male Python kontrole (rekonstrukcija, neovisna provjera premisa, PBP, vanjski VeriPB) približno je **0,005–0,006 s po slučaju** na GitHub runneru. To NIJE upareni benchmark protiv Kissat/CaDiCaL niti reprezentativno mjerenje većih problema.

## 5. Negativne kontrole

Četiri kontrole stvarno su izvršene i evidentirane u `atlas13_results/summary.json`:

| Kontrola | Ishod |
|---|---|
| Uklonjena nužna binarna implikacija `(~z OR ~b)` | Pronađen puni izvorni SAT model, provjereno 17 klauzula; zajednički modul sigurni **UNKNOWN** |
| Krivotvoreni source SHA-256 | Neovisni kontrolor **REJECT** |
| Uklonjena XOR2 izvorna klauzula i ažuriran SHA u lažiranom certifikatu | Neovisni kontrolor **REJECT** |
| Promijenjena deklarirana XOR paritetna vrijednost | Neovisni kontrolor **REJECT** |

Nisu zabilježene lažne SAT ili UNSAT tvrdnje. Testovi nisu uključili izvorne industrijske/konkurencijske CNF-ove i ne dokazuju robustnost na proizvoljnim alternativnim kodiranjima.

## 6. Znanstvena vrijednost i što mora slijediti

**Potvrđeno:** na unaprijed fiksiranom skupu kontroliranih ulaza, kombinacija tri poznata načina zaključivanja daje izvorno standardno provjerljiv UNSAT koji svaki pojedinačni **konkretno testirani ograničeni modul** vraća kao UNKNOWN. Prihvaćeni PBP izričito sadrži novi RUP grafovski sukob koji je matematički potreban završnom Hall izvođenju.

**Nije potvrđeno:** nova univerzalna matematička formula za SAT; novi problem koji ni općenitiji samostalni 2-SAT+CP sustav ne bi mogao riješiti; pokrivenost na novim stvarnim natjecateljskim CNF-ovima; usporedno ubrzanje nad referentnim solverima; dokaz P=NP ili bilo kakva univerzalna polinomijalna normalizacija.

**Sljedeći ATLAS13B / ATLAS14 korak:** zamrznuti 10–20 stvarnih originalnih **mješovitih** CNF-ova iz više problemskih obitelji, bez znanja kako su kodirane pomoćne varijable. Mjeriti koliko izvornih XOR/2-SAT implikacija stvarno nadopunjuje grafovske i Hall resursne granice, obvezno sa zasebnom neovisnom verifikacijom svake nove relacije, punim original-source standardnim proof checkerom, i ablacijski: GRAPH_ONLY, HALL_ONLY, XOR_ONLY, JOINT_ON te reference Kissat/CaDiCaL, uz isti E2E i jednu CPU jezgru. `UNKNOWN` je dopušten i ne smije biti preinačen bez dokaza.

## 7. Reprodukcija

```bash
# S `veripb` 3.0.2 u PATH:
python3 research/atlas13_joint/audit.py

# Za jednu izvornu formulu iz testnog artefakta:
python3 research/atlas13_joint/discover.py \
  --cnf source.cnf --certificate source-claims.json --meta discovery.json
python3 research/atlas13_joint/independent.py \
  --source source.cnf --certificate source-claims.json
python3 research/atlas13_joint/emit.py \
  --source source.cnf --certificate source-claims.json \
  --output original.pbp --meta proof-meta.json
veripb --cnf source.cnf original.pbp
```

GitHub workflow: `.github/workflows/atlas13-xor-graph-hall.yml`. Potpuni rezultat `atlas13_results/summary.json`, SHA svih originalnih izvornih i PBP datoteka, logovi externog VeriPB i kontrolirani SAT model u GitHub artefaktu `DRNAS-ATLAS13-XOR2-GRAPH-HALL-TRUE-JOINT-VERIPB`.
