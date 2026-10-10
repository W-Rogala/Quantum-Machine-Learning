# Fotoniczny kernel CV/GBS dla Xanadu X8

> Aktualny sweep strat, cutoffu, modeli detektorow oraz cechy event/orbit opisuje
> [`ROBUSTNESS.md`](ROBUSTNESS.md). Overflow jest teraz jawnym binem cech, a nie
> warunkowaniem histogramu po postselekcji.

## Zakres

Ten moduł jest osobnym modelem badawczym. Nie tłumaczy kubitowej ewolucji Isinga,
bramek `RX/RZ/RZZ` ani fidelity kernel na mody optyczne. Wykorzystuje strukturę,
którą akceptował kompilator `Xunitary` dla X8:

1. cztery źródła TMSV na parach `(0,4)`, `(1,5)`, `(2,6)`, `(3,7)`;
2. tę samą zależną od danych macierz unitarną na modach `0-3` i `4-7`;
3. pomiar liczby fotonów PNR we wszystkich ośmiu modach.

Aktualna dokumentacja Strawberry Fields stwierdza, że Xanadu Quantum Cloud nie
jest już dostępny. Kod sprzętowy pozostaje więc walidowalnym adapterem
historycznym/prywatnym, a nie obietnicą publicznego uruchomienia X8. Żaden wynik w
repozytorium nie jest oznaczony jako wykonanie na QPU.

## Mapa cech

Po preprocessingu próbka ma postać `x in [-1,1]^4`. Dwa stałe, losowe i
reprodukowalne interferometry `R1`, `R2` definiują

```text
U(x) = R2 diag(exp(i pi alpha x_j)) R1.
```

Na osiem modów działa `W(x) = diag(U(x), U(x))`. Dla macierzy źródłowej
`B0`, której jedyne niezerowe elementy łączą pary TMSV, macierz sąsiedztwa czystego
stanu GBS wynosi

```text
B(x) = W(x) B0 W(x)^T.
```

Prawdopodobieństwo wzorca PNR `n` jest liczone bez przybliżenia momentowego:

```text
p(n|x) = sqrt(det(I - B B†)) |Haf(B_n)|^2 / product_j(n_j!).
```

Własna implementacja hafnianu jest przeznaczona do małego, ośmiomodowego pilota.
Koszt rośnie wykładniczo z liczbą wykrytych fotonów.

## Dwa kernele z tych samych próbek

Eksperyment zapisuje jeden rekord surowych próbek PNR dla każdego `x`. Z tego
samego rekordu powstają:

- `hellinger`: iloczyn skalarny pierwiastków warunkowych histogramów Focka;
- `moment_rbf`: RBF na 8 momentach pierwszego rzędu i 36 momentach drugiego rzędu.

Oba kernele są PSD z konstrukcji. Zdarzenia o łącznej liczbie fotonów większej niż
`max_total_photons` są raportowane jako odrzucone i nie są uzupełniane dodatkowymi
strzałami. Porównanie używa więc identycznego całkowitego budżetu surowych
pomiarów, choć efektywny rozmiar warunkowego histogramu zależy od akceptacji.

Siatka obejmuje siłę ściskania `r` i skalę kodowania fazowego `alpha`. Jedna wspólna
konfiguracja optyczna jest wybierana przez średni wynik walidacyjny obu kernelów.
Gamma kernela momentowego jest wybierana przez alignment na train, regularyzacja
KRR na validation, a test nie jest argumentem funkcji selekcji. Klasyczny RBF jest
obowiązkowym punktem odniesienia.

## Uruchomienie lokalne

Szybki, w pełni deterministyczny eksperyment:

```powershell
.\.venv_qml\Scripts\python.exe -m photonic_kernel.experiment `
  --profile smoke --dataset moons --budget 12000 `
  --output-dir analysis_output\photonic_kernel_x8_smoke
```

Walidacja topologii X8 bez archiwalnego SDK:

```powershell
.\.venv_qml\Scripts\python.exe -m photonic_kernel.xanadu_x8 validate `
  --workload analysis_output\photonic_kernel_x8_smoke\workload.json
```

Ponowna analiza tych samych zliczeń:

```powershell
.\.venv_qml\Scripts\python.exe -m photonic_kernel.xanadu_x8 analyze `
  --workload analysis_output\photonic_kernel_x8_smoke\workload.json `
  --counts analysis_output\photonic_kernel_x8_smoke\local_counts.json `
  --output-dir analysis_output\photonic_kernel_x8_smoke\reanalyzed
```

Testy i niezależny audyt:

```powershell
.\.venv_qml\Scripts\python.exe -m unittest `
  tests.test_photonic_kernel tests.test_photonic_kernel_experiment -v

.\.venv_qml\Scripts\python.exe -m audits.photonic_kernel_audit `
  analysis_output\photonic_kernel_x8_smoke `
  --output-dir analysis_output\photonic_kernel_x8_audit
```

## Kompilacja Xunitary

Strawberry Fields 0.23 wspiera Python 3.8-3.10, a obecne środowisko projektu używa
Pythona 3.12. Kompilację należy izolować:

```powershell
py -3.10 -m venv .venv_x8
.\.venv_x8\Scripts\python.exe -m pip install -r requirements-xanadu-x8.txt
.\.venv_x8\Scripts\python.exe -m photonic_kernel.xanadu_x8 validate `
  --workload analysis_output\photonic_kernel_x8_smoke\workload.json `
  --require-compiler
```

Publiczna usługa nie przyjmie obecnie zadania. Komenda `submit` jest blokowana
zarówno przez `--confirm-submit`, jak i przez dodatkową zgodę na wycofany endpoint.
Druga flaga ma sens wyłącznie wtedy, gdy Xanadu potwierdziło dla danego konta
działający prywatny lub historyczny endpoint. Stan zapisuje job ID po każdym
zgłoszeniu; `retrieve --wait` odtwarza rekordy PNR i oba kernele.

## Artefakty

- `screening.csv`: wyniki siatki bez użycia testu;
- `selected_model.json`: zamrożony model i hiperparametry;
- `workload.json`: próbki, unitarne macierze, budżet i programy logiczne;
- `local_counts.json`: pojedynczy zestaw rekordów PNR dla obu kernelów;
- `analysis.json`: macierze, diagnostyka, wyniki idealne i finite-shot;
- `xanadu_validation.json`: topologia, unitarność i status kompilatora;
- `report.md`: krótki raport eksperymentu.

## Granice wnioskowania

- Rozkład idealny jest bezstratny; rzeczywisty detektor może generować także
  wzorce o nieparzystej liczbie fotonów. Analizator je akceptuje, ale model szumu
  wymaga osobnej kalibracji.
- Histogram i momenty są warunkowane na skończonym oknie fotonowym. Akceptacja jest
  raportowana, nie ukrywana.
- Profil `smoke` jest małym, zbalansowanym pilotem. Nie jest estymacją przewagi
  kwantowej ani pełnego błędu populacyjnego.
- Koszt symulacyjnego strojenia siatki pozostaje poza budżetem sprzętowym i jest
  jawnie oddzielony od liczby surowych pomiarów PNR.

## Źródła techniczne

- [Kod kompilatora Xunitary](https://strawberryfields.readthedocs.io/en/stable/_modules/strawberryfields/compilers/xunitary.html)
- [Status Xanadu Quantum Cloud](https://strawberryfields.readthedocs.io/en/latest/introduction/circuits.html#compilation)
- [Repozytorium Strawberry Fields i zakres wersji Pythona](https://github.com/XanaduAI/strawberryfields)
- [Eksperyment GBS na X8](https://www.nature.com/articles/s41586-021-03202-1)
