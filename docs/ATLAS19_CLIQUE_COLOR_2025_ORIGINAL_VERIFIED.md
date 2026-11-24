# ATLAS19 — originalni clique-coloring 2025: VeriPB dokaz i integracija

**24. studenoga 2026.** Uspješan original-source GitHub CI, [run 45349086364](https://github.com/Frane12/DRNAS-SAT/actions/runs/45349086364).

**Važno:** Ovo je retrospektivna integracija već postojećeg specijaliziranog dokaza iz modula research/clique_color_er, a ne prvi UNSAT dokaz te poznate obitelji ili novi teorem. Glavna grana nije promijenjena.

## Izvorna formula

- 6.050 varijabli, 205.556 klauzula.
- 100 vrhova, 4.950 varijabli bridova.
- Šest položaja klike (600 selektora).
- Pet boja za svaki vrh (500 selektora).
- Šest pozitivnih klauzula širine 100 i 100 pozitivnih klauzula širine 5.
- Izvorne klauzule nameću različite odabrane vrhove, sve bridove klike i zabranu jednake boje na povezanom paru vrhova.

SHA-256 originalne formule:

92d69a56836e0abbc2381d8ad1f00d5b409e4627685080e869c4432b8de36188

## Matematička metoda i dokaz

Izvorom provjerene RED-definicije uvode Q(i,u,z) = P(i,u) AND C(u,z) i Y(i,z) = OR_u Q(i,u,z). Potom RUP + source-hints dokazuju da svaki od šest položaja ima boju, dok ista boja može pripadati najviše jednom odabranom položaju. Zbroj Hallovih/pigeonhole ograničenja daje 6 <= 5, proturječje. Postupak koristi poznati mehanizam RED/RUP/Cutting-Planes dokaza, bez CDCL-a.

- 3.030 novih pomoćnih varijabli.
- 12.030 RED koraka.
- 758.181 RUP korak.
- 21 POL/CP korak.
- 62.033.404 bajta izvornog VeriPB dokaza.

SHA-256 proof.pbp:

b3119e81e068c5b8cd8e14681bdc8036cdabe4c64ffc0bf53ec027f9cda56af6

VeriPB 3.0.2 neovisno je prihvatio oba svježe generirana dokaza na nepromijenjenom originalnom CNF-u; kasnije dvostruke provjere također su prihvaćene.

## Upareni original-source test

Jedan logički CPU po pokušaju, dva ponavljanja, 15 sekundi za svaki potpun postupak uključujući vanjski checker. Redoslijed starih i novih ATLAS pokušaja obrnut je u drugom ponavljanju.

| Solver | Ponavljanje 0 | Ponavljanje 1 | Verificirano |
| --- | --- | --- | --- |
| ATLAS18 stari router | UNKNOWN, 4,842465 s | UNKNOWN, 4,728893 s | 0/2 |
| ATLAS19 s clique-color postupkom | UNSAT, 4,872690 s | UNSAT, 4,789112 s | 2/2 |
| Kissat 4.0.4 | UNKNOWN, 10,652907 s | UNKNOWN, 10,505782 s | 0/2 |
| CaDiCaL 2.1.3 | UNKNOWN, 12,676943 s | UNKNOWN, 12,527389 s | 0/2 |

Kissat i CaDiCaL dosegli su limit veličine izlazne DRAT dokazne datoteke od 256 MiB. Iz tog se razloga ne smije zaključiti da ne bi riješili problem uz veći diskovni limit ili duže vrijeme, niti ovo prikazivati kao opći svjetski rezultat.

## Provjere sigurnosti i regresija

Modul je točno odbio svih 80 sintetskih SAT kontrola s modelima i prihvatio deset malih izvornih dokaza kod vanjskog VeriPB-a. Ponašanje preostalih pet javnih originala ostalo je nepromijenjeno: GRAPH-color, exam-scheduling i php-mixed su verificirani, xor-shift i boxfolding ostaju UNKNOWN.

Pokrivenost šest javnih formula iz ATLAS17: 2/6 u ATLAS17, 3/6 u ATLAS18, 4/6 u ATLAS19. Novi rezultat je povezivanje prethodno odvojenog matematičkog modula s automatskom sadržajnom detekcijom, ne dokaz novog teorema.

## Reprodukcija

Na eksperimentalnoj grani experiment/atlas19-clique-color-er-router-20261124:

    python3 research/atlas17_probe/freeze.py
    cargo install veripb --version 3.0.2 --locked
    python3 research/atlas19_clique/source_gate.py atlas17_original_inputs/clique-color-2025.cnf
    python3 research/clique_color_er/emit_veripb.py --cnf atlas17_original_inputs/clique-color-2025.cnf --pbp proof.pbp --meta evidence.json
    veripb --cnf atlas17_original_inputs/clique-color-2025.cnf proof.pbp

Za cjelovitu automatsku usporedbu: .github/workflows/atlas19-clique-color-router.yml.

Nikakav sačuvani prethodni dokaz nije korišten kao ulaz za ATLAS19; sačuvani povijesni rezultati ostaju odvojeni od ovog mjerenja.
