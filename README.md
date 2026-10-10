# QML Research Workbench

Badania nad relacją między jakością predykcji, dynamiką kwantową i kosztem
pomiarowym: kernele Hamiltonowskie, skalowanie Trottera, rezerwuary kwantowe
oraz fotoniczne kernele CV/GBS. Materiały są głównie po polsku.

**Stan naukowy:** projekt zawiera wyniki eksploracyjne, benchmarki symulacyjne
i wybrane zapisane piloty sprzętowe. Nie wykazuje przewagi kwantowej.
Pełne badanie Trotter v3 ma obecnie 1/1600 ukończonych warunków i status
`not_confirmatory`. Przed dalszymi eksperymentami przeczytaj
[audyt i rejestr poprawek](docs/audit/README.md).

## Główne osiągnięcia pracy

**Najważniejszy wkład projektu to połączenie jakości predykcji, dynamiki kwantowej
i rzeczywistego budżetu pomiarowego w jednym warsztacie badawczym.**

- **Porównanie estymatorów przy ograniczonych pomiarach.** W zapisanym benchmarku
  przy 1 mln circuit-shots średnia balanced accuracy wynosi **95,89% dla projected**
  i **87,34% dla fidelity**: różnica **8,56 punktu procentowego**. Wynik dotyczy
  trzech ustalonych zbiorów i symulowanych pomiarów; klasyczny SVM-RBF osiąga 97,75%.
- **Spójny formalizm matematyczny.** Powiązano stany i kanały kwantowe, zmierzone
  cechy, macierze Grama oraz odczyt ridge. Wyprowadzenia pokazują, które
  transformacje zachowują informację i gdzie ograniczenie odczytu zmienia model.
- **Kontrolowana metodologia eksperymentów.** Wprowadzono zagnieżdżoną walidację,
  preprocessing wewnątrz foldów, równy budżet strojenia i osobny rachunek
  circuit-shots, wykonań mapy oraz bramek dwukubitowych ważonych shots.
- **Analiza mechanizmów pamięci rezerwuarów.** Rozdzielono pamięć stanu,
  obserwowalność i zdolność odczytu; wskazano kontrprzykłady dla bezwarunkowej
  kontrakcji po resecie i uniwersalnie korzystnej trotteryzacji.
- **Porównywalne reprezentacje fotoniczne.** Z tych samych zdarzeń pomiarowych
  budowane są różne rodziny cech, z jawnym uwzględnieniem overflow, strat i detekcji.
- **Odtwarzalna dokumentacja i kontrola jakości.** Monografia łączy wyprowadzenia,
  graf transformacji, bibliografię i kod. Aktualizacja przeszła **109 testów kodu**
  i **22 kontrole matematyczne oraz integralności**.

[Pełne uzasadnienie osiągnięć, dane, kod i granice wnioskowania](docs/ACHIEVEMENTS.md).
Te osiągnięcia obejmują wynik porównawczy, analizę matematyczną i warsztat badawczy;
nie stanowią dowodu przewagi kwantowej ani potwierdzenia wszystkich hipotez.

## Nawigacja po projekcie

| Część | Zawartość |
|---|---|
| [Mapa projektu](docs/project_map.md) | graf wszystkich gałęzi, pojęć i wyników |
| [Szczegółowy raport całego projektu](docs/report/README.md) | 18 rozdziałów, wyjaśnienia matematyczne i katalog wszystkich relacji grafowych |
| [Monografia matematyczna](docs/mathematical_report/README.md) | szczegółowe dowody i kontrprzykłady, hipotezy, kod, bibliografia i interaktywny raport offline |
| [Hamiltonian kernels](hamiltonian_kernel/README.md) | exact/Trotter, fidelity/projected, KRR, budżety |
| [Protokół publikacyjny](hamiltonian_kernel/PUBLICATION_BENCHMARK.md) | nested CV i kontrolowane porównania |
| [Trotter v3](hamiltonian_kernel/TROTTER_SCALING_V3.md) | rząd, krok, topology, niezależne osie kosztu |
| [Rezerwuary](quantum_reservoir/RESEARCH_PROTOCOL_H1_H5.md) | reset, pamięć, H1–H5 i szeregi czasowe |
| [Fotonika](photonic_kernel/README.md) | TMSV, GBS, detektory, histogramy i momenty |
| [19 kart teorii](qml_model_modules/00_INDEX.md) | algorytmy i założenia matematyczne |
| [Starsze eksperymenty](experiments/legacy/README.md) | QSVM, NISQ, SCAR i HPO |
| [Wybrane wyniki](results/README.md) | niewielkie historyczne zestawienia z proweniencją |
| [Odtwarzalność](docs/REPRODUCIBILITY.md) | środowiska, testy i nowe wykonania |

## Lokalny start

Python 3.12. Polecenia uruchamiaj z katalogu projektu. W PowerShell aktywuj
własne środowisko albo używaj bezpośrednio jego `Scripts/python.exe`.

```sh
python -m venv .venv
# PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements-local.txt
python -m pip install --no-deps -e .
python -m unittest discover -s tests -v
python -m audits.project_review_checks
```

Testy są lokalne. QPU wymaga osobnego konta i świadomego uruchomienia adaptera.
Strawberry Fields używa odrębnego historycznego środowiska Python 3.10,
opisanego w `requirements-xanadu-x8.txt`; nie instaluj go do środowiska NumPy 2.

Zastany zestaw: **107/107 testów PASS** na Windows, Python 3.12.14, także
w osobno wypakowanej paczce publikacyjnej. Reprodukcje
audytu wykazują znane problemy opisane w raporcie; ich wykonanie nie oznacza
usunięcia tych problemów. Workflow GitHub Actions skonfigurowano, ale nie został
jeszcze wykonany w chmurze GitHub.

## Struktura repozytorium

```text
hamiltonian_kernel/   quantum_reservoir/   photonic_kernel/  # główne implementacje
experiments/legacy/                                      # wcześniejsze badania
qml_model_modules/                                      # atlas teorii
tests/                 audits/                           # kontrole lokalne
tools/                 scripts/                          # narzędzia i adaptery
datasets/                                                # małe dane UCI + opis
docs/                                                    # mapa, audyt, instrukcje
results/                                                 # małe zestawienia
analysis_output/                                         # lokalne pełne wyniki
output/                                                  # lokalne PDF/PPT/obrazy
```

W `analysis_output` publikowane są adaptery starych importów, README oraz pięć jawnie wskazane pliki CSV/MD wymagane do odtworzenia monografii.
Duże wyniki, środowiska, cudze PDF-y, MNIST i niezwiązany `personal-project-crm`
są wyłączone przez `.gitignore`. Oryginałów nie usunięto. Małe dane UCI mają
[atrybucję i opis](datasets/README.md).

[Przygotowanie publikacji](docs/GITHUB_PREPARATION.md) opisuje zakres plików,
eksport oraz kwestie autorstwa i licencji. Repozytorium zdalne: [W-Rogala/Quantum-Machine-Learning](https://github.com/W-Rogala/Quantum-Machine-Learning).
Aktualizacja z 10 października 2026 nakłada zweryfikowaną paczkę z 9 października
na istniejącą historię gałęzi `main`.

Korekta raportu i pakiet aktualizacji z 9 października 2026:
[rejestr zmian i kontroli](docs/mathematical_report/REVIEW_2026-10-09.md).

Kontrola aktualizacji: **109/109 testów PASS** w wypakowanej kopii po normalizacji
LF oraz **22/22 kontroli matematycznych i integralności PASS**. Wyniki zapisano
w `docs/mathematical_report/verification/github_update_validation.json`.
