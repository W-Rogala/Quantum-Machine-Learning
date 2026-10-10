# Framework skalowania polityki Trottera

## Cel i hipoteza

Framework testuje zamrożoną hipotezę:

> Polityka Trottera optymalna na zbiorze walidacyjnym, opisana przez rząd
> formuły iloczynowej `p` i nominalny krok `delta_t`, zależy od liczby kubitów
> `n` oraz od zewnętrznie narzuconego budżetu głębokości szeregowej `D_max`.

Hipoteza zerowa mówi, że po ustaleniu danych, Hamiltonianu, podziału danych i
funkcji celu wybrana polityka jest niezależna od `n` i `D_max`.

Sformułowanie dotyczy **polityki warunkowanej zasobami**, a nie niezależnego
wpływu przyczynowego głębokości. Trotteryzacja sama zmienia głębokość obwodu,
więc tych dwóch wielkości nie można traktować jak niezależnych czynników.

## Parametr optymalizowany

Termin „stopień trotteryzacji” jest niejednoznaczny. Framework rozdziela go na:

- `p`: dyskretny rząd formuły Suzuki-Trottera, domyślnie `1` lub `2`;
- `delta_t`: nominalny czas jednego kroku, przeszukiwany dokładnie co `0,01`.

Liczba kroków jest całkowita. Jeśli `delta_t` nie dzieli czasu ewolucji `t`,
ostatni dodatni krok jest skracany tak, aby suma czasów była dokładnie równa
`t`. Dzięki temu siatka `0,01` nie zmienia całkowitego czasu ewolucji.

## Rodzina Hamiltonianów

Hamiltonian ma postać

```text
H(x) = sum_{P in P_k} [b_P + w_P^T x] P,
```

gdzie `P_k` zawiera wszystkie nieidentycznościowe ciągi Pauliego o lokalności
nie większej niż `k`. Współczynniki są rzeczywiste, więc `H(x)` jest hermitowski.
Rodzina obejmuje osie `X`, `Y`, `Z`, dowolne podpory i mieszane oddziaływania.

Dla `k=n` i bez limitu składników baza obejmuje wszystkie `4^n - 1` kierunków
Pauliego i jest uniwersalna dla hermitowskich Habmiltonianów na `n` kubitach.
Koszt takiej reprezentacji jest wykładniczy. Profil pełny stosuje jawny limit
rzadkości; nie wolno interpretować go jako pełnego Hamiltonianu `n`-lokalnego.
Profil `smoke` używa `k=n` bez limitu, natomiast profil `full` losuje w sposób
deterministyczny najwyżej `64` składniki z pełnej rodziny `n`-lokalnej.

## Dane i izolacja testu

Założenie „optymalnie zanotowanych danych” jest operacjonalizowane jako:

- deterministyczny, zamrożony nauczyciel generujący etykiety;
- brak wstrzykniętego szumu etykiet;
- klasy zbilansowane;
- minimalny margines od granicy decyzyjnej;
- skrót SHA-256 danych w manifeście.

Jest to założenie eksperymentalne, nie stwierdzenie o rzeczywistych zbiorach.
Preprocessing jest dopasowywany wyłącznie na train. Kandydaci, model
kwadratowy, QUBO, wyżarzanie i QAOA korzystają tylko z train/validation. Test
jest liczony dopiero po wyborze konfiguracji przez każde ramię optymalizatora.

## Funkcja celu i zasoby

Dla konfiguracji wykonalnej przy `D <= D_max` minimalizowana jest funkcja

```text
L = 0.55 (1 - BA_val)
  + 0.15 mean_state_infidelity
  + 0.20 relative_kernel_Frobenius_error
  + 0.10 D / D_max.
```

Wagi są częścią zamrożonego protokołu. Raportowane zasoby obejmują liczbę
eksponent Pauliego, rotacji jednokubitowych, bramek dwukubitowych oraz
szeregowy proxy-depth standardowego gadżetu Pauliego. Jest to koszt logiczny,
nie głębokość po transpile na konkretny backend.

## Ramiona optymalizacji

1. `grid_reference` przeszukuje całą siatkę i wyznacza wynik referencyjny.
2. `quadratic_surrogate` dopasowuje osobny model `a + b delta_t + c delta_t^2`
   dla każdego rzędu wyłącznie na zamrożonych punktach pilotażowych.
3. `exact_shortlist_qubo` dokładnie rozwiązuje one-hot QUBO na krótkiej liście
   wskazanej przez model kwadratowy.
4. `simulated_annealing_shortlist_qubo` jest klasyczną kontrolą Metropolisa dla
   tego samego QUBO; zapisany JSON można przenieść do annealera.
5. `qaoa_p1_shortlist_qubo` rozwiązuje ten sam QUBO przez dokładną symulację
   stanu QAOA `p=1` i siatkę kątów.

One-hot QUBO ma postać

```text
E(z) = sum_i s_i z_i + lambda (sum_i z_i - 1)^2.
```

To mała instancja wyboru konfiguracji i jest klasycznie łatwa. Ramię QAOA służy
sprawdzeniu integracji metodologicznej, a nie wykazaniu przewagi kwantowej.
Framework nie oznacza symulowanego wyżarzania jako quantum annealing ani
symulacji stanu jako wykonania QPU.

## Uruchomienie

Najpierw należy zamrozić protokół:

```powershell
.\.venv_qml\Scripts\python.exe -m hamiltonian_kernel.trotter_scaling freeze `
  --profile smoke `
  --output analysis_output\trotter_scaling_smoke\protocol.json
```

Następnie uruchomić benchmark i niezależny audyt:

```powershell
.\.venv_qml\Scripts\python.exe -m hamiltonian_kernel.trotter_scaling run `
  --protocol analysis_output\trotter_scaling_smoke\protocol.json `
  --output-dir analysis_output\trotter_scaling_smoke

.\.venv_qml\Scripts\python.exe -m audits.trotter_scaling_output_audit `
  analysis_output\trotter_scaling_smoke
```

Profil `smoke` waliduje pipeline i daje wyłącznie wynik opisowy. Profil `full`
jest przeznaczony do testu hipotezy, ale pojedynczy sztuczny benchmark nadal nie
uzasadnia generalizacji na wszystkie dane i urządzenia.

## Artefakty

- `protocol.json`: niezmienny protokół i jego hash;
- `annotation_manifest.json`: definicja oraz hash danych;
- `hamiltonians/n*.json`: pełne współczynniki i hash Hamiltonianu;
- `candidates.csv`: cała siatka bez metryk testowych;
- `optimizer_instances/*.json`: pilot, shortlist, QUBO i wyniki solverów;
- `selections.csv`: wybrane konfiguracje i jednokrotna ocena testowa;
- `hypothesis_analysis.json`: regresja zależności i test permutacyjny;
- `independent_audit.json` oraz `.md`: ponowne obliczenie kontroli integralności.

## Warunki dalszej walidacji

Przed wnioskiem publikacyjnym należy dodać powtarzane, zagnieżdżone podziały,
hierarchiczne przedziały ufności, kilka rodzin danych oraz głębokość po
transpilacji na ustalone topologie. Wynik sprzętowy wymaga zapisania ISA/QPY,
layoutu, kalibracji, liczby strzałów i seeda transpile.
