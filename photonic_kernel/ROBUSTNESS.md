# CV/GBS robustness study in Strawberry Fields

## Osobna hipoteza

Ten eksperyment nie jest portem kubitowego Hamiltonian kernel na X8. Bada
odpornosc cech fotonicznych na straty i detekcje dla osmio-modowego GBS. Wspolny
surowy strumien PNR jest przetwarzany przez factorial sweep, aby zmiana cutoffu
nie byla mylona z inna realizacja losowa.

## Czynniki

- `max_total_photons`: sweep progu overflow;
- `transmissivity`: fizyczny kanal strat przed detektorem;
- `quantum_efficiency`: dodatkowa sprawnosc detekcji;
- `dark_count_mean`: niezalezne zliczenia ciemne Poissona;
- detektor `pnr`, `threshold` lub `pnr_saturation`;
- `saturation_count` dla ograniczonej rozdzielczosci PNR.

`overflow` jest jawnym binem normalizowanym przez wszystkie raw shots. Nie ma
postselekcyjnego uzupelniania odrzuconych zdarzen. Moment features zawieraja
truncated first/second moments oraz acceptance/overflow rate.

## Rodziny cech

- `pattern_hellinger`: wzorce Focka plus overflow;
- `moment_rbf`: momenty i overflow;
- `event_hellinger`: klasy `(total photons, click count)` plus overflow;
- `orbit_hellinger`: orbity permutacyjne, czyli posortowane obsadzenia modow,
  plus overflow.

Wszystkie cztery macierze sa budowane z tych samych zdarzen. Modul
`photonic_kernel.strawberry_fields_robustness` tworzy program z `S2gate`, dwoma
kopiami interferometru, `LossChannel` na kazdym modzie i `MeasureFock` lub
`MeasureThreshold`. Strawberry Fields definiuje `LossChannel(T)` przez
transmisyjnosc energii `T` i wspiera pomiar Focka w backendzie Gaussian:

- [Strawberry Fields: LossChannel](https://strawberryfields.readthedocs.io/en/stable/code/api/strawberryfields.ops.LossChannel.html)
- [Strawberry Fields: MeasureFock](https://strawberryfields.readthedocs.io/en/latest/code/api/strawberryfields.ops.MeasureFock.html)
- [Strawberry Fields operations](https://strawberryfields.readthedocs.io/en/latest/introduction/ops.html)

## Uruchomienie sweepu

Plik NPZ musi zawierac po jednej macierzy `(shots, 8)` dla kazdej probki:

```powershell
.\.venv_x8\Scripts\python.exe -m photonic_kernel.strawberry_fields_robustness `
  analyze-samples `
  --samples analysis_output\photonic_raw_samples.npz `
  --cutoffs 2,4,6,8 `
  --transmissivities 1.0,0.9,0.75,0.5 `
  --output-dir analysis_output\photonic_robustness
```

Strawberry Fields 0.23 jest izolowane w srodowisku CPython 3.10 opisanym przez
`requirements-xanadu-x8.txt`. Brak tego runtime oznacza, ze mozna testowac czysta
analize probek, ale nie wolno raportowac wykonania programu SF ani QPU.

## Wnioskowanie

Praca fotoniczna jest metodyczna: glownym estymandem powinna byc degradacja
macierzy i balanced accuracy wzgledem transmisyjnosci, z cutoffem i detektorem jako
czynnikami. Nie nalezy laczyc jej p-value z testem Hamiltonian kernels ani wybierac
cutoffu na zbiorze testowym.
