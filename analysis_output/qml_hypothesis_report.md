# Raport: hipoteza poprawy wydajnosci modelu QML

## 1. Ekstrakcja podstaw dzialania algorytmow QML

Z przeanalizowanych materialow wynika, ze praktyczne QML w erze NISQ opiera sie glownie na modelach hybrydowych:

- Quantum kernels / QSVM: dane klasyczne sa kodowane jako stan `|phi(x)>`, a podobienstwo dwoch probek jest mierzone jadrem `K(x,x') = |<phi(x)|phi(x')>|^2`. Solver moze pozostac klasyczny. Glowne ograniczenia: koszt macierzy jadra `O(n^2)`, koszt kodowania danych, szum i ryzyko jadra latwego do klasycznej symulacji.
- VQC / QNN: obwod ma encoder danych, parametryzowany ansatz, pomiar obserwabli i klasyczny optymalizator. Glowne ograniczenia: barren plateaus, niestabilnosc optymalizacji, koszt pomiarow i silna wrazliwosc na architekture.
- Hybrid QNN: klasyczny preprocessing lub klasyczna siec laczy sie z warstwa kwantowa. Jest to najbardziej realistyczna sciezka inzynierska, ale wymaga ablacji, bo poprawa moze pochodzic z klasycznej czesci pipeline'u.
- QGAN / QCBM / QBM: modele generatywne ucza rozklady probek przez pomiar obwodu lub Hamiltonian energetyczny. Sa naturalnie probabilistyczne, ale trudne w trenowaniu i skalowaniu.
- VQE / QAOA / annealing: wazne jako procedury optymalizacji i podprogramy ML, lecz nie sa typowymi klasyfikatorami danych tabularnych.
- HHL / qPCA / QSVT / quantum transformer: kierunek FTQC z obiecujaca zlozonoscia, ale obecnie zalezy od trudnych zalozen: qRAM, block encoding, koszt read-in/read-out.

## 2. Wybrany model

Zespol wybral quantum kernel classifier / QSVM-like LS-SVM, bo pozwala najczysciej testowac sama czesc kwantowa: macierz jadra. Uzyte jadro symuluje idealny obwod `ZZFeatureMap`, a klasyczny solver uczy granice decyzyjna na gotowej macierzy podobienstw.

Role zespolu:

- fizyk kwantowy: wybor jadra overlapowego i kontrola liczby kubitow;
- specjalista ML: standaryzacja, PCA, walidacja i metryki;
- statystyk: powtarzane splity, balanced accuracy i macro-F1;
- inzynier obliczen: koszt `O(n^2 * 2^q)` i pomiar czasu jadra.

## 3. Hipoteza

Hipoteza podstawowa H4: kompaktowa kalibracja jadra QSVM, czyli redukcja danych do 4 skladowych PCA i dobranie skali katow przez kernel-target alignment, poprawi lub utrzyma jakosc wzgledem domyslnej 6-kubitowej mapy `ZZFeatureMap`, a jednoczesnie obnizy koszt symulacji stanu z `2^6 = 64` do `2^4 = 16` amplitud.

Uzasadnienie fizyczne: zbyt gleboka lub zbyt ekspresyjna mapa cech moze prowadzic do koncentracji jadra, gdzie probki staja sie prawie rowno odlegle albo jadro robi sie nadmiernie diagonalne. Alignment dobiera skale tak, aby geometria Hilberta byla zgodna z etykietami, a mniejsza liczba kubitow ogranicza koszt i ryzyko nadmiernej ekspresyjnosci.

## 4. Test

Glowny test zostal wykonany na lokalnych zbiorach `breast_cancer_wdbc` i `wine`:

- 20 powtarzanych podzialow stratified split 60/20/20;
- preprocessing: standaryzacja na train, PCA na train, skalowanie do `[0, 1]`;
- solver: jadrowy klasyfikator LS-SVM;
- wariant bazowy: 6-kubitowy `ZZFeatureMap` ze skala `pi`;
- wariant hipotezy: 4-kubitowy `ZZFeatureMap` ze skala dobrana przez alignment;
- punkty odniesienia: jadro produktowe i klasyczne RBF.

## 5. Wyniki glowne, srednia z 20 uruchomien

| Zbior | Wariant | Balanced accuracy | Macro-F1 | Wymiar stanu | Czas jadra |
|---|---|---:|---:|---:|---:|
| WDBC | baseline 6q | 0.921 +/- 0.029 | 0.923 +/- 0.028 | 64 | 0.0250 s |
| WDBC | hipoteza 4q | 0.936 +/- 0.024 | 0.942 +/- 0.022 | 16 | 0.0134 s |
| Wine | baseline 6q | 0.964 +/- 0.033 | 0.961 +/- 0.035 | 64 | 0.0059 s |
| Wine | hipoteza 4q | 0.969 +/- 0.032 | 0.968 +/- 0.033 | 16 | 0.0014 s |

Wynik: H4 jest wsparta jako hipoteza inzynierska. Wariant 4-kubitowy poprawil srednie metryki na obu zbiorach i zmniejszyl wymiar stanu czterokrotnie. Najwieksza korzysc jest w relacji jakosc/koszt, nie w samej przewadze accuracy.

## 6. Test kontrolny: agresywna redukcja do 2 kubitow

Dodatkowo uruchomiono test kontrolny na WDBC, Wine i OptDigits 3-vs-8. Regula wybierala najmniejsza konfiguracje bliska najlepszemu alignmentowi.

| Zbior | Baseline 6q balanced acc. | Alignment-selected 2q balanced acc. | Wniosek |
|---|---:|---:|---|
| WDBC | 0.865 | 0.935 | poprawa i duza redukcja kosztu |
| Wine | 0.964 | 0.893 | redukcja zbyt agresywna |
| OptDigits 3-vs-8 | 0.966 | 0.932 | redukcja zbyt agresywna |

Ten pojedynczy test pokazal granice hipotezy: alignment pomaga, ale minimalizacja liczby kubitow do 2 nie jest uniwersalnie bezpieczna. Zgodnie z wymaganiem celu zespol wyprowadzil poprawke hipotezy i uruchomil test iteracyjny.

## 7. Iteracja po wyniku negatywnym

Negatywny element testu: H1, czyli agresywna redukcja do najmniejszej konfiguracji bliskiej najlepszemu alignmentowi, potrafi wybierac tylko 2 kubity. To daje bardzo niski koszt, ale moze usunac informacyjnie wazne skladowe PCA.

Poprawiona hipoteza H2: zachowac kalibracje przez kernel-target alignment, ale narzucic dolny limit 4 kubitow. Fizycznie oznacza to minimalna pojemnosc `2^4 = 16` amplitud zamiast `2^2 = 4`, nadal przy czterokrotnie mniejszym stanie niz baseline 6-kubitowy.

W ponizszej iteracji etykiety oznaczaja: H0 = baseline 6q, H1 = agresywna redukcja do najmniejszej konfiguracji, H2 = poprawka z limitem 4q. Test iteracyjny wykonano w 10 powtorzeniach na WDBC, Wine i OptDigits 3-vs-8:

| Zbior | H0 baseline 6q | H1 agresywne 2q | H2 poprawione 4q | Wniosek |
|---|---:|---:|---:|---|
| WDBC | 0.902 | 0.926 | 0.946 | H2 najlepsza, 1/4 wymiaru stanu |
| Wine | 0.951 | 0.921 | 0.979 | H1 negatywna, H2 naprawia hipoteze |
| OptDigits 3-vs-8 | 0.945 | 0.957 | 0.976 | H2 najlepsza, 1/4 wymiaru stanu |

Wniosek z iteracji: H1 nie przechodzi jako uniwersalna poprawa, bo na Wine traci okolo 0.030 balanced accuracy. H2 przechodzi test na wszystkich trzech zbiorach: poprawia balanced accuracy wzgledem H0 i zachowuje czterokrotnie mniejszy wymiar stanu.

## 8. Wniosek koncowy

Ostateczna hipoteza po poprawce zostala potwierdzona w praktycznej postaci: kalibracja jadra QSVM przez PCA + kernel-target alignment + minimalny limit 4 kubitow poprawia relacje jakosc/koszt i ogranicza zasoby kwantowe bez utraty jakosci w badanych zadaniach. Nie jest to jednak dowod quantum advantage. Klasyczne RBF pozostaje bardzo mocnym punktem odniesienia, a wyniki sa symulacyjne. Nastepny krok badawczy to test shot noise, blad bramek i porownanie z realnym backendem lub modelem szumu.

## 9. Pliki

- `analysis_output/qsvm_hypothesis_report.md` - pelny raport z 20 powtorzen.
- `analysis_output/qsvm_hypothesis_summary.csv` - tabela srednich i odchylen.
- `analysis_output/qsvm_hypothesis_results.csv` - wszystkie uruchomienia glownego testu.
- `analysis_output/qml_hypothesis_experiment.py` - dodatkowy test kontrolny 2-kubitowy.
- `analysis_output/qml_hypothesis_results.csv` - wyniki testu kontrolnego.
- `analysis_output/qml_iterative_hypothesis_experiment.py` - test iteracyjny H0/H1/H2.
- `analysis_output/qml_iterative_hypothesis_report.md` - raport z poprawionej hipotezy.
- `analysis_output/qml_iterative_hypothesis_summary.csv` - podsumowanie 10 powtorzen.
- `analysis_output/h2_mathematical_description_proof.md` - opis i dowod matematyczny hipotezy H2.
