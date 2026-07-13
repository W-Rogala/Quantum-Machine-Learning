# Hipoteza i test: kompaktowa kalibracja jądra QSVM

## Ekstrakcja zasad działania QML

1. Quantum kernels/QSVM: klasyczne dane są kodowane w stan kwantowy `|phi(x)>`; podobieństwo próbek mierzy się jako overlap `|<phi(x)|phi(x')>|^2`, a klasyczny solver uczy granicę decyzyjną na macierzy jądra.
2. VQC/QNN: parametryzowany obwód kwantowy składa się z kodowania danych, ansatzu, pomiaru obserwabli i klasycznego optymalizatora; ryzykiem są barren plateaus, szum i koszt pomiarów.
3. Hybrid QNN: klasyczny preprocessing lub klasyczna sieć łączy się z warstwą kwantową; wymaga ablacji, bo poprawa może pochodzić z klasycznej części pipeline'u.
4. QGAN/QCBM/QBM: modele generatywne uczą rozkłady próbek przez pomiar obwodu lub energetyczny Hamiltonian; są naturalne probabilistycznie, ale trudne w trenowaniu i skalowaniu.
5. QAOA/VQE/annealing: wariacyjne lub adiabatyczne procedury optymalizacji, często jako podprogramy ML, nie jako samodzielne klasyfikatory.
6. HHL/qPCA/QSVT/quantum transformer: algorytmy FTQC o obiecującej złożoności, lecz silnie zależne od kosztu read-in/read-out, qRAM i block encodingu.

## Hipoteza zespołu

Wybrany model: QSVM/quantum kernel classifier z jądrem `ZZFeatureMap` liczonym symulatorem stanu.

Hipoteza: dla małych danych tabularnych NISQ kompaktowa mapa cech z 4 składowymi PCA i skalą kątów dobraną przez kernel-target alignment poprawi lub utrzyma jakość klasyfikacji względem domyślnej mapy 6-kubitowej ze skalą `pi`, przy niższym koszcie symulacji (`2^4` zamiast `2^6` amplitud).

Role eksperckie: fizyk kwantowy wybrał jądro overlapowe i ograniczenie liczby kubitów; specjalista ML dobrał PCA, standaryzację i walidację; statystyk narzucił powtarzane splity i metryki balanced accuracy oraz macro-F1; inżynier obliczeń pilnował kosztu `O(n^2 * 2^q)` dla jądra ZZ.

## Protokół testu

- Dane: lokalne zbiory `breast_cancer_wdbc` oraz `wine`.
- Podział: 20 powtarzanych stratified splitów 60/20/20.
- Preprocessing: standaryzacja na train, PCA na train, skalowanie składowych do `[0, 1]`.
- Solver: jądrowy klasyfikator least-squares/LS-SVM z regularyzacją `1e-2`; test dotyczy macierzy jądra, nie zewnętrznej biblioteki SVM.
- Wariant bazowy: `baseline_zz_6q_pi`.
- Wariant hipotezy: `hypothesis_zz_4q_alignment`.
- Ablacje: separowalne jądro produktowe i klasyczne RBF, oba z tym samym doborem skali przez alignment.

## Wyniki średnie z 20 uruchomień

### breast_cancer_wdbc

| wariant | q/cechy | wymiar stanu | accuracy | balanced acc. | macro-F1 | czas jadra [s] | alignment |
|---|---:|---:|---:|---:|---:|---:|---:|
| ablation_product_4q_alignment | 4 | - | 0.944 +/- 0.018 | 0.932 +/- 0.023 | 0.939 +/- 0.020 | 0.0149 +/- 0.0024 | 0.493 +/- 0.033 |
| baseline_zz_6q_pi | 6 | 64 | 0.928 +/- 0.026 | 0.921 +/- 0.029 | 0.923 +/- 0.028 | 0.0250 +/- 0.0332 | 0.317 +/- 0.031 |
| classical_rbf_4pca_alignment | 4 | - | 0.951 +/- 0.014 | 0.942 +/- 0.018 | 0.947 +/- 0.015 | 0.0110 +/- 0.0033 | 0.497 +/- 0.032 |
| hypothesis_zz_4q_alignment | 4 | 16 | 0.947 +/- 0.020 | 0.936 +/- 0.024 | 0.942 +/- 0.022 | 0.0134 +/- 0.0274 | 0.498 +/- 0.039 |

### wine

| wariant | q/cechy | wymiar stanu | accuracy | balanced acc. | macro-F1 | czas jadra [s] | alignment |
|---|---:|---:|---:|---:|---:|---:|---:|
| ablation_product_4q_alignment | 4 | - | 0.956 +/- 0.035 | 0.960 +/- 0.033 | 0.959 +/- 0.033 | 0.0008 +/- 0.0002 | 0.746 +/- 0.028 |
| baseline_zz_6q_pi | 6 | 64 | 0.961 +/- 0.035 | 0.964 +/- 0.033 | 0.961 +/- 0.035 | 0.0059 +/- 0.0082 | 0.446 +/- 0.030 |
| classical_rbf_4pca_alignment | 4 | - | 0.967 +/- 0.030 | 0.970 +/- 0.029 | 0.968 +/- 0.029 | 0.0007 +/- 0.0003 | 0.749 +/- 0.027 |
| hypothesis_zz_4q_alignment | 4 | 16 | 0.966 +/- 0.035 | 0.969 +/- 0.032 | 0.968 +/- 0.033 | 0.0014 +/- 0.0015 | 0.720 +/- 0.032 |

## Wniosek

- breast_cancer_wdbc: hipoteza zmieniła accuracy o +0.019, macro-F1 o +0.019, a proxy kosztu symulacji spadł do 0.25 kosztu bazowego.
- wine: hipoteza zmieniła accuracy o +0.004, macro-F1 o +0.006, a proxy kosztu symulacji spadł do 0.25 kosztu bazowego.

## Test parowany

| zbiór | metryka | średnia różnica | mediana różnicy | wygrane/przegrane/remisy | sign-test p jednostronne |
|---|---|---:|---:|---:|---:|
| breast_cancer_wdbc | test_accuracy | +0.019 | +0.017 | 12/5/3 | 0.072 |
| breast_cancer_wdbc | test_macro_f1 | +0.019 | +0.017 | 12/8/0 | 0.252 |
| wine | test_accuracy | +0.004 | +0.000 | 8/6/6 | 0.395 |
| wine | test_macro_f1 | +0.006 | +0.002 | 10/6/4 | 0.227 |

Interpretacja: hipoteza jest wsparta jako decyzja inżynierska, bo kompaktowy wariant zachowuje lub poprawia metryki przy około czterokrotnie mniejszym wymiarze stanu. Test parowany pokazuje jednak, że przewaga jakościowa nie jest bardzo silna statystycznie przy 20 splitach; najmocniejszy wynik dotyczy relacji jakość/koszt.

Ograniczenia: test jest symulacyjny i małopróbkowy; jądro produktowe jest łatwo klasycznie symulowalne, a nawet jądro ZZ nie dowodzi przewagi kwantowej. Wyniki należy traktować jako test hipotezy projektowej dla pipeline'u QSVM, nie jako dowód quantum advantage.

Pliki wynikowe:

- `qsvm_hypothesis_results.csv`: wszystkie uruchomienia.
- `qsvm_hypothesis_summary.csv`: średnie i odchylenia.
- `qsvm_hypothesis_summary.json`: metadane maszynowe.
