# QSVM historyczne, SCAR, HPO i komunikacja wyników

Kod historyczny ma teraz kanoniczną lokalizację `experiments/legacy/`.
Adaptery w `analysis_output/*.py` zachowują stare polecenia i importy.

## Osobna ocena ośmiu plików eksperymentalnych

| Plik | Ocena |
|---|---|
| `qsvm_hypothesis_experiment.py` | train-only PCA i selekcja skali, walidacja regularyzacji; wariant wieloklasowy rozwiązuje ridge na targetach, nie standardowy hinge-loss SVM. Nazwę LS-SVM doprecyzować |
| `qml_hypothesis_experiment.py` | poprawny binarny układ LS-SVM z biasem, wybór alignmentu na train; końcowy fit train+validation jest dopuszczalny, ale opisać refit preprocessingu |
| `qml_iterative_hypothesis_experiment.py` | poprawnie implementuje near-best z dolnym progiem q; interpretacja twierdzenia H2 jest za silna |
| `qml_nisq_hypothesis_experiment.py` | model efektywnego survival i pomiarów jest testem wrażliwości; nie stanowi kalibrowanego kanału bramkowego konkretnego QPU |
| `vqe_scar_ansatz_experiment.py` | unitarna bramka, sensowne deskryptory KL względem Haar i Meyer–Wallach; brak Hamiltonianu celu i minimalizacji energii, więc to test ansatzu, nie wynik VQE |
| `scar_wine_qnn_benchmark.py` | trening QNN z różnicami skończonymi, głowica klasyczna i MLP o tej samej liczbie parametrów; równość liczby parametrów nie wyrównuje kosztu ani pojemności |
| `ansatz_hardware_dataset_benchmark.py` | 14 adaptacji, preprocessing train-only, HPO wybiera po validation; profile dostawców to efektywne tłumienie i shot noise, nie symulacja pełnego urządzenia |
| `generate_scar_circuit_visualization_png.py` | rysunek obwodu do komunikacji; nie dowód równoważności ani raport zasobów natywnych |

## L-01 i L-02 — dowód H2 nie odpowiada regule selekcji

Źródło: lokalne `analysis_output/h2_mathematical_description_proof.md`, sekcje
2, 4, 6 i 7; odpowiednik PDF i generator `tools/generate_h2_proof_pdf.py`.

Lemat PSD dla |<ψ_i|ψ_j>|² jest poprawny. Monotoniczność błędu rekonstrukcji
PCA E_q=Σ_(k>q)λ_k jest poprawna w ustalonej przestrzeni standaryzowanych danych.
Nie jest to monotoniczność informacji o etykiecie ani jakości klasyfikacji.

**L-01 (P1).** Warunek q≥4 dopuszcza q=4,6,8. Stosunki wymiaru do 6 kubitów
wynoszą odpowiednio 1/4, 1 i 4. Nie wynika z niego dokładnie czterokrotna redukcja.
To prawda wyłącznie dla wybranego q*=4. Koszt O(N²2^q) opisuje idealne overlapy
w symulatorze, bez strojenia, przygotowania stanów, rozwiązywania układu i kosztu
sprzętowego. Na QPU czterokrotnie mniejszy wymiar nie oznacza czterokrotnie
mniejszej liczby shots, bramek lub czasu.

**L-02 (P2).** Kod wybiera najtańszą konfigurację z alignment≥0.95 A_max,
z preferencją liczby kubitów i entanglementu. Nie gwarantuje argmax alignmentu.
Zapis o „podobnej normie” także nie daje ścisłej równoważności maksymalizacji
alignmentu i licznika: potrzebna jest dokładnie ustalona norma lub normalizacja.

Poprawione twierdzenie: idealny fidelity kernel jest PSD; wybrany kandydat ma
alignment co najmniej 95% maksymalnego w danej siatce i minimalne q zgodnie
z tie-break; **jeżeli q*=4**, wymiar statevector jest czterokrotnie mniejszy niż
dla 6q. Wpływ na BA wymaga niezależnej oceny empirycznej. Zwiększenie liczby
zachowanych składowych PCA nie gwarantuje poprawy predykcji.

Eksperyment H2 został sformułowany po inspekcji wcześniejszych wyników H1.
Nowe splity tych samych datasetów stanowią eksploracyjną iterację, nie całkowicie
niezależne potwierdzenie uniwersalnej hipotezy. Zachować to w abstrakcie pracy.

## L-03 — wybór zwycięzcy HPO do QPU po teście (P1)

`tools/run_best_hpo_ibm_qpu.py:184–202`, `select_best_ibm_case`, sortuje po
`test_balanced_accuracy_profile_shots`. HPO wewnątrz ustalonego przypadku
poprawnie używa validation, ale wybór przypadku/datasetu/ansatzu na pilot używa
testu. Ten test staje się zbiorem selekcji. Nie powinien następnie służyć jako
niezależny dowód jakości „najlepszego modelu”.

Poprawka: wybór architektury na development/validation i nowy zamrożony holdout.
Dotychczasowy wynik można zachować jako pilot wybranego po eksploracji przypadku.
Przykładowy raport pilota ma tylko 15 próbek testowych, więc jeden błąd zmienia
accuracy o 1/15≈0.067. Potrzebny przedział niepewności, nie ranking na trzecim
miejscu po przecinku.

## L-04 — OptDigits traci oryginalny podział piszących (P1)

`ansatz_hardware_dataset_benchmark.py:125–143` łączy `optdigits.tra` i `.tes`;
analogiczna redukcja 3-vs-8 używa puli w `qml_hypothesis_experiment.py`.
Według [UCI](https://archive.ics.uci.edu/dataset/80/optical+recognition+of+handwritten+digits)
oryginalny podział obejmuje rozłącznych autorów pisma: 30 osób train i 13 test.
Nowy losowy podział próbek mierzy inne zadanie generalizacji i może korzystać
z podobnego stylu pisma po obu stronach granicy.

Nie jest to dosłowne nakładanie się identycznych indeksów train/test po podziale.
Jest to utrata kontroli grup i zmiana estymandu. Poprawka: zachować oficjalny
test, validation wydzielić wyłącznie z `.tra`; analizę mieszaną nazwać osobnym
zadaniem. Nie porównywać jej wyniku bezpośrednio z oficjalnym benchmarkiem.

## L-05 — analityczny trening w profilach (P2)

`ansatz_hardware_dataset_benchmark.py:948–975,1094–1134,1195–1201`:
attenuation=F1^G1 F2^G2(1−2p_readout); trening i walidacja wywołują `apply_profile`
z shots=0, a dopiero test próbuje dwumianowo. Jest to świadomy, uproszczony model
oczekiwań. Fidelities nie są ogólnie prawdopodobieństwami przeżycia całego obwodu,
a skalarny współczynnik nie odtwarza błędów koherentnych, topologii, korelacji,
T1/T2 ani wspólnego rozkładu wielu obserwabli.

Poprawka komunikacji: „trening na analitycznych cechach tłumionych; finite-shot
inference”. Osobno porównać trening finite-shot, symulator kanałów i QPU przy
tym samym algorytmie optymalizacji. W tabelach nie nazywać idealnego qubitowego
PennyLane sprzętem fotonicznym Xanadu.

## SCAR, sprzęt, mitygacja i nowość

Bramka SCAR ma strukturę wymiany XX+YY z fazą chiralną i ZZ; numeryczna kontrola
unitarności daje błąd 8,8e−17. Interpretacja Hamiltonianu jest spójna z macierzą.
Nadanie nowej nazwy makrobramce nie dowodzi nowości względem rodziny fSim/XY/ZZ
i lokalnych rotacji. Roszczenie nowości wymaga osobnego przeglądu i analizy
klas równoważności lokalnej. Losowe KL i splątanie nie dowodzą uniwersalności
przy ograniczonych, współdzielonych parametrach ani lepszej energii VQE.

`tools/scar_wine_ibm_qpu.py` i zapisany raport wyraźnie podają fizyczny `ibm_fez`:
accuracy 0.400 vs 0.971 MLP, 66 CZ po routingu, tylko 12 epok SPSA. Porównanie
z idealnym QNN 160 epok miesza szum i protokół treningu; raport uczciwie to
zaznacza. Równa liczba parametrów nie jest wyrównaniem budżetu optymalizacji.

`scar_rigetti_ionq_architecture.py` ocenia kompilację; `scar_physical_qpu_wine_benchmark.py`
oraz `scar_ibm_fez_simulated_reproduction.py` modelują scenariusze. Nazwa pliku
„physical” nie nadaje wynikom statusu QPU. `scar_measurement_mitigation.py`
i `scar_qpu_error_matrix_mitigation.py` należy oceniać z kosztem osobnych
kalibracji, conditioning macierzy błędu i niepewnością. Korekcja odczytu nie
odwraca ogólnie szumu bramek. Nie uruchamiano kont ani nowych zadań sprzętowych.

## Raporty, PDF, prezentacje i hipotezy

W treściach 5 PDF-ów i 3 prezentacji znaleziono zarówno dobre zastrzeżenia,
jak i powielanie starszego, zbyt mocnego „dowodu H2”. `output/QML_podsumowanie_projektu.pptx`,
slajd 16 mówi, że przewaga „pojawia się” po dopasowaniu systemu. To warunki
konieczne dobrego eksperymentu, a nie warunki wystarczające przewagi; zmienić
na „może być badana dopiero przy…”. Slajd 15 powinien dopisać, że H2 dotyczy
wyborów q*=4 w badanej próbie. H3 legacy nie jest H3 rezerwuarów.

Prezentacja resource-aware v2 trafniej rozdziela test finite-shot, mały pilot
QPU i brak SF/X8; nie trzeba przepisywać jej jako deklaracji porażki całego
projektu. Starszy `methodological_audit.md` ma datę 18 sierpnia i mówi o braku
wysłania konkretnego joba; późniejsze katalogi IBM z 25 sierpnia nie są z tym
logicznie sprzeczne. Dokumenty muszą mieć datę i zakres eksperymentu.

`tools/build_*`, `generate_h2_proof_pdf.py` oraz notebook QRC duplikują treści
i tabele. Poprawki powinny przechodzić przez jeden rejestr tez i metryk;
regenerowanie PDF bez korekty źródła szybko przywróci błąd. Ekstrakcja tekstu
nie zastępuje kontroli czytelności wykresów. W tym audycie nie zmieniano
historycznych binariów ani nie tworzono pozornego nowego wykonania eksperymentu.
