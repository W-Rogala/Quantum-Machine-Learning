# Iteracyjny test hipotezy QSVM

Cel: sprawdzic, czy negatywny wynik agresywnej redukcji do 2 kubitow mozna naprawic przez poprawke hipotezy.

## Hipotezy

- H0: bazowe jadro `ZZFeatureMap`, 6 kubitow, skala 1.0, entanglement 1.0.
- H1: agresywna redukcja - wybierz najmniejsza konfiguracje bliska najlepszemu kernel-target alignment; w praktyce czesto 2 kubity.
- H2: poprawiona hipoteza - zachowaj kalibracje alignment, ale narzuc dolny limit 4 kubitow, aby nie zgubic zbyt duzo informacji po PCA.

Uruchomienia na zbior: 10.

## Wyniki

| Zbior | Hipoteza | Balanced acc. | Delta vs H0 | Macro-F1 | Wymiar stanu | Czas jadra vs H0 | Wniosek |
|---|---|---:|---:|---:|---:|---:|---|
| OptDigits: digit 3 vs digit 8, capped at 220/class | H0_baseline_6q | 0.945 +/- 0.023 | +0.000 | 0.945 | 64 | 1.00 | punkt odniesienia |
| OptDigits: digit 3 vs digit 8, capped at 220/class | H1_aggressive_2q_alignment | 0.957 +/- 0.028 | +0.011 | 0.957 | 4 | 0.20 | zaakceptowana jako poprawa kosztu |
| OptDigits: digit 3 vs digit 8, capped at 220/class | H2_floor_4q_alignment | 0.976 +/- 0.021 | +0.031 | 0.976 | 16 | 0.30 | zaakceptowana jako poprawa kosztu |
| WDBC breast cancer: malignant vs benign | H0_baseline_6q | 0.902 +/- 0.036 | +0.000 | 0.906 | 64 | 1.00 | punkt odniesienia |
| WDBC breast cancer: malignant vs benign | H1_aggressive_2q_alignment | 0.926 +/- 0.020 | +0.024 | 0.933 | 4 | 0.28 | zaakceptowana jako poprawa kosztu |
| WDBC breast cancer: malignant vs benign | H2_floor_4q_alignment | 0.946 +/- 0.017 | +0.044 | 0.949 | 16 | 0.39 | zaakceptowana jako poprawa kosztu |
| Wine: class 1 vs class 2 | H0_baseline_6q | 0.951 +/- 0.045 | +0.000 | 0.953 | 64 | 1.00 | punkt odniesienia |
| Wine: class 1 vs class 2 | H1_aggressive_2q_alignment | 0.921 +/- 0.049 | -0.030 | 0.919 | 4 | 0.08 | negatywna lub zbyt agresywna |
| Wine: class 1 vs class 2 | H2_floor_4q_alignment | 0.979 +/- 0.024 | +0.027 | 0.977 | 16 | 0.17 | zaakceptowana jako poprawa kosztu |

## Decyzja zespolu

H1 nie przechodzi jako uniwersalna poprawa: na czesci zbiorow zysk kosztowy jest okupiony spadkiem balanced accuracy. Przyczyna fizyczno-informatyczna jest zgodna z oczekiwaniem: 2 kubity oznaczaja tylko 4 amplitudy stanu, a PCA do 2 skladowych moze usunac separujace kierunki.

H2 jest poprawka hipotezy: alignment pozostaje mechanizmem kalibracji geometrii jadra, ale zespol narzuca minimalna pojemnosc 4 kubitow. Taki wariant utrzymuje lub poprawia jakosc w granicy 0.01 balanced accuracy wzgledem H0, przy czterokrotnie mniejszym wymiarze stanu.

To nadal nie jest dowod przewagi kwantowej. Jest to potwierdzona poprawa inzynierska dla badanego pipeline'u QSVM: mniej zasobow przy zachowanej jakosci.
