# Hamiltonian kernels i skalowanie Trottera

## Poprawne elementy i rzeczywisty zakres wyników

`core.py` rozdziela H(x)=A(x)+B, exact i formuły produktowe; fidelity jest
iloczynem Hilberta–Schmidta stanów czystych. RBF na lokalnych wektorach Blocha
jest PSD jako klasyczny kernel na cechach. Małe n umożliwia kontrolę przez
diagonalizację. Testy obejmują ewolucję, normę stanu, zbieżność Trottera,
kompilację, budżety, protokoły i lokalne estymatory.

`experiment.py` i `grid_experiment.py` są etapami eksploracyjnymi. `protocol.py`
i `publication_benchmark.py` wprowadzają nested CV, zamrożone splity, baseline'y,
oddzielenie train/validation/test i koszt całego wyszukiwania. `estimation.py`
ma istotną zaletę: projected mierzy wspólne bitstringi dla X/Y/Z, zachowując
kowariancje obserwabli. Starszy niezależny model dwumianowy cech nie jest z nim
równoważny. Reprezentację spektralną należy dopasować wyłącznie na train.

Historyczny błąd licznika J=0 jest już opisany i poprawiony w osobnej wersji
`outer_results_cost_corrected`; nie zgłaszamy go jako nadal nieusuniętej usterki
tego benchmarku. Lokalne `methodological_audit.md` podaje 75 splitów, 1950
wyników i 1500 artefaktów macierzy. Te liczby opisują zapisany historyczny audyt,
nie nowo przeprowadzoną pełną replikację.

Najmocniejszy zapisany wniosek: przy 1 mln circuit-shots projected ma średnią BA
0,95892, fidelity 0,87336, a SVM-RBF 0,97754. To wynik tego protokołu na trzech
zbiorach; nie dowód przewagi kwantowej. P-value oparte na 15 klastrach
dataset×powtórzenie ma ograniczenie zależności między powtórzeniami CV.

## H-01 — surowy Gram w v3 i znaczenie słowa KRR (P1)

Lokalizacje: `hamiltonian_kernel/trotter_scaling_v3.py`, `select_policy` ok. 408–424,
`_post_selection_diagnostics` ok. 459–497; `learning.py:14`.

Inner CV dostaje `raw`; końcowy `_score_kernel` także dostaje raw train/cross.
Dopiero później `kernel_stages(raw_train)` tworzy macierze PSD/spectral do zapisu.
Nie należy interpretować ich jako macierzy użytej w predykcji. Skończone pomiary
poszczególnych overlapów mogą zniszczyć PSD: przykładowo macierz z diagonalą 1
i górnym trójkątem (0.9,0.9,0) ma λ_min=1−sqrt(1.62)<0.

Rozwiązanie `(K+λI)α=y` można policzyć dla nieokreślonej K, ale nie ma ono
standardowej interpretacji wypukłej regresji w RKHS. Małe dodatnie λ nie zapewnia
dodatniej określoności ani stabilności. To problem definicji i potencjalnie
wyników, nie dowód, że każda dotychczasowa predykcja jest zła.

Poprawka: jawnie zadeklarować estymator indefinite albo zastosować jednolitą
mapę PSD do train i cross; dopasowywać ją osobno w każdym inner train, a po wyborze
ponownie na outer train. Nie wystarczy obciąć widma train i zostawić cross bez
zgodnej transformacji. Zapisać `prediction_kernel_stage`, macierz faktycznie
użytą, minimalną wartość własną i conditioning. Ponownie zamrozić protokół.

## H-02 — rezerwacja kosztu opisana jako zużycie (P2)

Lokalizacja: `trotter_scaling_v3.py:358`, `_candidate_budget`, zapis wyników ok. 610
i 812; `TROTTER_SCALING_V3.md:39` deklaruje realized counts.

Koszt testu jest liczony przez maksimum liczby bramek 2Q wszystkich kandydatów,
mimo że test wykonuje tylko wybranego. Takie maksimum jest sensowną rezerwacją
przed selekcją, lecz nie faktycznym zużyciem po selekcji.

Reprodukcja: koszty map 1 i 10 bramek, 3 pary train, 4 pary test, 68 shots dają
raportowane 9928 gate-shots. Jeśli wybrano mapę z 1 bramką, rzeczywisty rachunek
w tym samym modelu kosztu wynosi 5032. Nie oznacza to naruszenia budżetu, tylko
zawyżenie deklarowanego zużycia. Poprawka: zachować konserwatywne przydzielenie
shots, zapisać oddzielnie `reserved_*` i `used_*`, ten drugi z kosztem wybranego
kandydata. Osobno odróżnić proxy dwóch map od kompilacji pełnego overlap circuit.

## H-03 — etykieta widma nie odpowiada znormalizowanemu kernelowi (P2)

Lokalizacja: `estimation.py:200–254`, `estimate_fidelity_spectral`;
`publication_benchmark.py` zapis `spectral_kernel_all` i `spectral_eigenvalues`.

Po obcięciu widma powstają cechy, których normy są następnie skalowane do
zmierzonej diagonali. To transformacja kongruencji D K D, a nie podobieństwa:
wartości własne na ogół się zmieniają. Zwracane `spectral_eigenvalues` pozostaje
widmem obciętej macierzy landmarków przed normalizacją. Przy Nyström różni się
również wymiar od pełnego kernela. Sam estymator cech pozostaje PSD.

Na 12 stanach czterowymiarowych, pełnym train i 156 shots maksymalna rozbieżność
widm wyniosła **0,45105**. Poprawka: `landmark_truncated_eigenvalues_pre_normalization`
oraz osobne `normalized_train_eigenvalues`; wskazać, do której macierzy i zbioru
próbek odnosi się rząd i widmo. Przeliczenia metadanych nie utożsamiać ze zmianą BA.

## Trotter: ocena wersji i granic teoretycznych

`universal_hamiltonian.py` daje wspólną reprezentację sum Paulich i rzędy 1/2/4.
Asymptotyczne O(t²/r) i O(t³/r²) wymagają stałych zależnych od komutatorów;
nie są uniwersalną gwarancją dla dowolnego n, t i Hamiltonianu. Ujemne podkroki
Suzukiego czwartego rzędu są dopuszczalne dla unitarnej symulacji, ale nie wolno
przenosić ich bezpośrednio na dowolny nieodwracalny kanał szumu.

V2 mieszało w celu polityki kryteria jakości i diagnostyki exact. Dokument v3
prawidłowo degraduje dawne p≈0,0001 do wyniku eksploracyjnego. V3 wybiera politykę
przez inner CV, a exact służy diagnostyce po selekcji. Siatka 0.01–1.00 jest
wstępnie filtrowana kosztowo; nie wykonano pełnego wyszukiwania 300 punktów.
`random_k_local` jest w tym protokole co najwyżej 2-local.

W zapisanym pełnym v3 ukończono 1/1600 warunków, 96 outer rows. `v3_audit.json`
ma `status: passed`, 995 checks, lecz `confirmatory: false`. Zgadza się to
z `v3_summary.json`. Nie ma podstaw do deklaracji zakończenia badania skalowania.
Exact finite-shot stanowi kontrolę liczby pomiarów; nie ma równoważnego fizycznego
kosztu ISA/QPU. Wnioski o optymalnym rzędzie pozostają zależne od modelu, szumu,
shortlisty, funkcji celu i jednostki inferencji.

## Sprzęt i pozostałe pliki

`hardware_circuits.py`, `hardware_providers.py`, `hardware_experiment.py` rozdzielają
budowę obwodu, wykonanie i analizę; audyty kontrolują completion/protocol hashes.
Fake backend i Aer nie są fizycznym QPU. Snapshot kalibracji i job ID są dowodem
zapisanej proweniencji, a nie automatycznym dowodem przewagi ani powtarzalności
między dniami. `correct_resource_costs.py` powinien pozostać narzędziem
wersjonowanej korekty. Wszystkie helpery i raporty są wyliczone w katalogu źródeł.
