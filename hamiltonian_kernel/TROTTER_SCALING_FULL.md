# Pelny, prerejestrowany eksperyment skalowania Trottera

## Zakres

Pipeline `trotter_scaling_full.py` realizuje zamrozony benchmark dla:

- `n = 2, 3, 4, 5, 6` kubitow;
- ewolucji dokladnej oraz formul iloczynowych rzedu `1`, `2`, `4`;
- `delta_t = 0.01, 0.02, ..., 1.00`;
- Hamiltonianow Isinga `ZZ+X+Z`, losowych rzadkich Hamiltonianow
  2-lokalnych oraz ich wariantow o promieniu widmowym `1` i `3`;
- topologii `chain`, `ring`, `grid`, `all_to_all`;
- 20 niezaleznych seedow Hamiltonianu;
- trzech lacznych poziomow budzetu: transpilowanej glebokosci,
  `circuit-shots` i `2Q-gate-shots`;
- dwoch replik finite-shots, nested repeated CV `2 x 3` i wewnetrznego
  wyboru hiperparametrow w dwoch foldach.

Kazdy z 480 000 punktow siatki otrzymuje diagnostyke zasobowa i
komutatorowa. Kosztowne obliczenia statevector sa wykonywane dla zamrozonej
shortlisty: punktow wskazanych przez proxy, ich sasiadow `+/-0.01` oraz
kotwic `0.05, 0.10, 0.25, 0.50, 0.75, 1.00`. Kotwice sa liczone takze wtedy,
gdy nie mieszcza sie w zadnym budzecie; nie staja sie przez to kandydatami
wdrozeniowymi.

## Model kosztu

Obwod jednej warstwy formul iloczynowych jest jawnie dekomponowany na gadzety
eksponent Pauliego i transpilowany w Qiskit do bazy `rz,sx,x,cx` na zamrozonej
mapie sprzezen. Pelny obwod jest kompozycja takich blokow z granicami miedzy
warstwami. Raportowane sa:

- transpilowana glebokosc mapy cech;
- liczba `CX` i wszystkich bramek po transpilacji;
- `circuit-shots`;
- liczba wykonan mapy cech, rowna `2 * circuit-shots` dla fidelity kernel;
- `2Q-gate-shots`.

Czas QPU i kredyty nie sa estymowane dla symulatora. Topologie sa syntetyczne,
nie sa snapshotem kalibracji fizycznego backendu.

## Estymacja i izolacja testu

Dla kazdego zewnetrznego foldu kandydaci i regularyzacja kernel ridge sa
wybierani wylacznie przez wewnetrzne CV. Blok testowy fidelity kernel jest
probkowany dopiero po wyborze. Budzet obejmuje cala ocene kandydatow i finalny
blok testowy.

Dla reprezentatywnego `outer_repeat=0`, `outer_fold=0`, `shot_replicate=0`
publikowane sa macierze treningowe `raw`, po obcieciu ujemnych wartosci
wlasnych do PSD oraz po progowaniu spektralnym. Pozostale powtorzenia zachowuja
diagnostyki widmowe w `outer_results.csv`.

## Test hipotezy

Odpowiedzia wielowymiarowa sa osobno standaryzowane:

1. `log(delta_t)`,
2. wybrany rzad Trottera.

Statystyka glowna jest suma kwadratow wspolczynnikow dla standaryzowanej liczby
kubitow, logarytmu budzetu glebokosci i ich interakcji. Czynniki kontrolne to
profil Hamiltonianu, topologia, norma komutatorow, promien widmowy i zewnetrzny
podzial CV. Test wykorzystuje 10 000 permutacji reszt Freedmana-Lane'a wewnatrz
zamrozonych blokow. Przedzialy 95% pochodza z 5000 bootstrapow klastrowanych po
seedzie Hamiltonianu.

## Uruchomienie

Wymagane sa pakiety z `requirements-hamiltonian-kernel.txt` oraz Qiskit z
`requirements-qml-hardware.txt`.

```powershell
.\.venv_qml\Scripts\python.exe -m hamiltonian_kernel.trotter_scaling_full freeze `
  --profile full `
  --output analysis_output\trotter_scaling_full_preregistered_corrected\protocol.json

.\.venv_qml\Scripts\python.exe -m hamiltonian_kernel.trotter_scaling_full run `
  --protocol analysis_output\trotter_scaling_full_preregistered_corrected\protocol.json `
  --output-dir analysis_output\trotter_scaling_full_preregistered_corrected `
  --max-workers 12

.\.venv_qml\Scripts\python.exe -m audits.trotter_scaling_full_audit `
  analysis_output\trotter_scaling_full_preregistered_corrected

.\.venv_qml\Scripts\python.exe -m hamiltonian_kernel.trotter_scaling_summary `
  analysis_output\trotter_scaling_full_preregistered_corrected
```

Przebieg jest wznawialny. Shard jest pomijany tylko wtedy, gdy zgadza sie hash
protokolu oraz hashe tabel i archiwow macierzy.

## Wynik z 18 wrzesnia 2026

Protokol ma hash
`79611ef13c099fcb3b444514c442098ef7d7ca34e6762353bda37326fbcfbb0e`.
Audyt przeszedl 13/13 kontroli. Test laczny dal `p = 1/10001`, czyli
`0.00009999`.

Wiekszy poziom zasobow wybieral srednio mniejszy krok i wyzszy rzad. Wzrost
liczby kubitow byl zwiazany ze slabszym, przeciwnym przesunieciem: nieco
wiekszym krokiem i nieco nizszym rzedem. Przedzialy interakcji `n x budzet`
obejmowaly zero dla obu odpowiedzi. Druga replika finite-shots odtworzyla
kierunki i istotnosc efektow glownych.

Nie oznacza to ostro zidentyfikowanego optimum. Identyczna para
`(rzad, delta_t)` zostala wybrana w obu replikach tylko w `6.15%` porownan,
zgodnosc samego rzedu wyniosla `38.95%`, a mediana roznicy kroku `0.21`.
Wynik wspiera zatem zaleznosc rozkladu wybieranej polityki od `n` i poziomu
zasobow, ale nie stabilnosc pojedynczej konfiguracji.

## Ograniczenia

- Trzy budzety zmieniaja sie razem, wiec nie mozna rozdzielic przyczynowego
  wplywu glebokosci, liczby strzalow i `2Q-gate-shots`.
- Dane sa syntetyczne, idealnie opisane i pozbawione szumu etykiet.
- Szum dotyczy probkowania kernela; nie modeluje bledow bramek, readoutu ani
  dryfu kalibracji.
- Dokladna ewolucja jest referencja symulacyjna, nie kandydatem QPU.
- Wynik nie jest dowodem przewagi kwantowej ani wynikiem z fizycznego QPU.

Najwazniejsze artefakty znajduja sie w
`analysis_output/trotter_scaling_full_preregistered_corrected`: `protocol.json`,
`grid_candidates.csv`, `outer_results.csv`, `hypothesis_analysis.json`,
`hypothesis_sensitivity_shot_replicate_1.json`, `scientific_summary.json`,
`results_summary.md`, `kernel_stage_manifest.json`, `implementation_manifest.json`
oraz `independent_audit.json`.
