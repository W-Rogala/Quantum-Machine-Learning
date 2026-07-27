# Test hipotezy QML w warunkach NISQ

## Hipoteza

H2-NISQ: w klasyfikatorze QSVM jądro `ZZFeatureMap` powinno być kalibrowane przez kernel-target alignment, ale z narzuconą minimalną pojemnością 4 kubitów i preferencją małej liczby bramek splątujących.

Po teście negatywnym w szumie poprawka H3-NISQ dodaje walidacyjny wybór liczby kubitów, skali, splątania i regularyzacji LS-SVM. Funkcja wyboru karze lukę train-val oraz koszt bramek, więc hipoteza celuje bezpośrednio w poprawę precyzji bez overfittingu w warunkach NISQ.

## Model NISQ

- Skończona liczba pomiarów: estymator jądra `K_ij` próbkowany z rozkładu dwumianowego.
- Szum bramek: globalne przybliżenie depolaryzacyjne `p' = s p + (1-s)/2^q`, gdzie `s` zależy od liczby bramek 1q, 2q i odczytu.
- Korekcja inżynierska stosowana po równo do obu wariantów: diagonalna normalizacja jądra, czyli `K_ij/sqrt(K_ii K_jj)`.

Powtórzenia na zbiór i scenariusz: 8.

## Wyniki średnie

### OptDigits: digit 3 vs digit 8, capped at 220/class

| scenariusz | wariant | balanced acc. | macro-F1 | luka train-test | survival | wymiar stanu | 2q bramki vs H0 | wniosek |
|---|---|---:|---:|---:|---:|---:|---:|---|
| ideal_exact | H0_6q_full_zz | 0.952 +/- 0.020 | 0.952 +/- 0.020 | 0.048 +/- 0.020 | 1.000 +/- 0.000 | 64 | 1.00 | punkt odniesienia |
| ideal_exact | H2_4q_alignment_floor | 0.977 +/- 0.024 | 0.977 +/- 0.024 | 0.007 +/- 0.031 | 1.000 +/- 0.000 | 16 | 0.00 | wsparta |
| ideal_exact | H3_nisq_validation_gap_penalty | 0.977 +/- 0.025 | 0.977 +/- 0.025 | 0.006 +/- 0.030 | 1.000 +/- 0.000 | 28 | 0.10 | wsparta |
| nisq_4096_low_noise | H0_6q_full_zz | 0.952 +/- 0.020 | 0.952 +/- 0.020 | 0.048 +/- 0.020 | 0.855 +/- 0.000 | 64 | 1.00 | punkt odniesienia |
| nisq_4096_low_noise | H2_4q_alignment_floor | 0.500 +/- 0.044 | 0.498 +/- 0.043 | 0.042 +/- 0.022 | 0.957 +/- 0.000 | 16 | 0.00 | warunkowa |
| nisq_4096_low_noise | H3_nisq_validation_gap_penalty | 0.977 +/- 0.018 | 0.977 +/- 0.018 | 0.002 +/- 0.022 | 0.946 +/- 0.016 | 22 | 0.10 | wsparta |
| nisq_1024_medium_noise | H0_6q_full_zz | 0.950 +/- 0.022 | 0.950 +/- 0.022 | 0.050 +/- 0.022 | 0.647 +/- 0.000 | 64 | 1.00 | punkt odniesienia |
| nisq_1024_medium_noise | H2_4q_alignment_floor | 0.557 +/- 0.052 | 0.556 +/- 0.052 | 0.130 +/- 0.093 | 0.915 +/- 0.000 | 16 | 0.00 | warunkowa |
| nisq_1024_medium_noise | H3_nisq_validation_gap_penalty | 0.940 +/- 0.124 | 0.940 +/- 0.124 | -0.005 +/- 0.021 | 0.871 +/- 0.051 | 22 | 0.15 | wsparta |
| nisq_512_high_noise | H0_6q_full_zz | 0.892 +/- 0.128 | 0.892 +/- 0.128 | 0.079 +/- 0.049 | 0.444 +/- 0.000 | 64 | 1.00 | punkt odniesienia |
| nisq_512_high_noise | H2_4q_alignment_floor | 0.511 +/- 0.067 | 0.511 +/- 0.066 | 0.119 +/- 0.092 | 0.871 +/- 0.000 | 16 | 0.00 | warunkowa |
| nisq_512_high_noise | H3_nisq_validation_gap_penalty | 0.980 +/- 0.023 | 0.980 +/- 0.023 | -0.000 +/- 0.026 | 0.803 +/- 0.078 | 34 | 0.10 | wsparta |

### WDBC breast cancer: malignant vs benign

| scenariusz | wariant | balanced acc. | macro-F1 | luka train-test | survival | wymiar stanu | 2q bramki vs H0 | wniosek |
|---|---|---:|---:|---:|---:|---:|---:|---|
| ideal_exact | H0_6q_full_zz | 0.892 +/- 0.034 | 0.897 +/- 0.029 | 0.108 +/- 0.034 | 1.000 +/- 0.000 | 64 | 1.00 | punkt odniesienia |
| ideal_exact | H2_4q_alignment_floor | 0.942 +/- 0.017 | 0.947 +/- 0.016 | 0.013 +/- 0.020 | 1.000 +/- 0.000 | 16 | 0.25 | wsparta |
| ideal_exact | H3_nisq_validation_gap_penalty | 0.946 +/- 0.023 | 0.952 +/- 0.020 | 0.016 +/- 0.028 | 1.000 +/- 0.000 | 34 | 0.10 | wsparta |
| nisq_4096_low_noise | H0_6q_full_zz | 0.887 +/- 0.037 | 0.891 +/- 0.034 | 0.113 +/- 0.037 | 0.855 +/- 0.000 | 64 | 1.00 | punkt odniesienia |
| nisq_4096_low_noise | H2_4q_alignment_floor | 0.507 +/- 0.054 | 0.496 +/- 0.050 | 0.032 +/- 0.072 | 0.936 +/- 0.018 | 16 | 0.25 | warunkowa |
| nisq_4096_low_noise | H3_nisq_validation_gap_penalty | 0.944 +/- 0.020 | 0.947 +/- 0.021 | 0.004 +/- 0.036 | 0.928 +/- 0.007 | 34 | 0.25 | wsparta |
| nisq_1024_medium_noise | H0_6q_full_zz | 0.808 +/- 0.118 | 0.808 +/- 0.124 | 0.174 +/- 0.081 | 0.647 +/- 0.000 | 64 | 1.00 | punkt odniesienia |
| nisq_1024_medium_noise | H2_4q_alignment_floor | 0.504 +/- 0.051 | 0.494 +/- 0.051 | 0.075 +/- 0.064 | 0.850 +/- 0.054 | 16 | 0.25 | warunkowa |
| nisq_1024_medium_noise | H3_nisq_validation_gap_penalty | 0.938 +/- 0.018 | 0.945 +/- 0.018 | 0.016 +/- 0.019 | 0.861 +/- 0.045 | 34 | 0.15 | wsparta |
| nisq_512_high_noise | H0_6q_full_zz | 0.593 +/- 0.057 | 0.584 +/- 0.060 | 0.290 +/- 0.104 | 0.444 +/- 0.000 | 64 | 1.00 | punkt odniesienia |
| nisq_512_high_noise | H2_4q_alignment_floor | 0.487 +/- 0.043 | 0.479 +/- 0.046 | 0.167 +/- 0.066 | 0.754 +/- 0.097 | 16 | 0.25 | warunkowa |
| nisq_512_high_noise | H3_nisq_validation_gap_penalty | 0.935 +/- 0.026 | 0.941 +/- 0.026 | 0.003 +/- 0.029 | 0.733 +/- 0.142 | 34 | 0.28 | wsparta |

### Wine: class 1 vs class 2

| scenariusz | wariant | balanced acc. | macro-F1 | luka train-test | survival | wymiar stanu | 2q bramki vs H0 | wniosek |
|---|---|---:|---:|---:|---:|---:|---:|---|
| ideal_exact | H0_6q_full_zz | 0.960 +/- 0.044 | 0.961 +/- 0.042 | 0.040 +/- 0.044 | 1.000 +/- 0.000 | 64 | 1.00 | punkt odniesienia |
| ideal_exact | H2_4q_alignment_floor | 0.978 +/- 0.027 | 0.976 +/- 0.029 | 0.017 +/- 0.024 | 1.000 +/- 0.000 | 16 | 0.00 | wsparta |
| ideal_exact | H3_nisq_validation_gap_penalty | 0.977 +/- 0.027 | 0.976 +/- 0.029 | 0.014 +/- 0.030 | 1.000 +/- 0.000 | 34 | 0.00 | wsparta |
| nisq_4096_low_noise | H0_6q_full_zz | 0.955 +/- 0.046 | 0.956 +/- 0.045 | 0.045 +/- 0.046 | 0.855 +/- 0.000 | 64 | 1.00 | punkt odniesienia |
| nisq_4096_low_noise | H2_4q_alignment_floor | 0.929 +/- 0.060 | 0.928 +/- 0.060 | 0.023 +/- 0.061 | 0.957 +/- 0.000 | 16 | 0.00 | warunkowa |
| nisq_4096_low_noise | H3_nisq_validation_gap_penalty | 0.967 +/- 0.037 | 0.966 +/- 0.038 | 0.019 +/- 0.039 | 0.954 +/- 0.007 | 22 | 0.00 | wsparta |
| nisq_1024_medium_noise | H0_6q_full_zz | 0.960 +/- 0.044 | 0.961 +/- 0.042 | 0.040 +/- 0.044 | 0.647 +/- 0.000 | 64 | 1.00 | punkt odniesienia |
| nisq_1024_medium_noise | H2_4q_alignment_floor | 0.642 +/- 0.169 | 0.637 +/- 0.173 | -0.030 +/- 0.176 | 0.915 +/- 0.000 | 16 | 0.00 | warunkowa |
| nisq_1024_medium_noise | H3_nisq_validation_gap_penalty | 0.972 +/- 0.026 | 0.971 +/- 0.027 | 0.019 +/- 0.027 | 0.900 +/- 0.021 | 34 | 0.00 | wsparta |
| nisq_512_high_noise | H0_6q_full_zz | 0.945 +/- 0.071 | 0.946 +/- 0.070 | 0.055 +/- 0.071 | 0.444 +/- 0.000 | 64 | 1.00 | punkt odniesienia |
| nisq_512_high_noise | H2_4q_alignment_floor | 0.554 +/- 0.109 | 0.550 +/- 0.113 | 0.084 +/- 0.130 | 0.871 +/- 0.000 | 16 | 0.00 | warunkowa |
| nisq_512_high_noise | H3_nisq_validation_gap_penalty | 0.977 +/- 0.040 | 0.976 +/- 0.041 | 0.016 +/- 0.045 | 0.849 +/- 0.030 | 34 | 0.00 | wsparta |

## Porównanie parowane względem H0

| zbiór | scenariusz | wariant | Δ balanced acc. | wygrane/przegrane/remisy | Δ luka train-test | bez dodatkowego overfittingu |
|---|---|---|---:|---:|---:|---:|
| OptDigits: digit 3 vs digit 8, capped at 220/class | ideal_exact | H2_4q_alignment_floor | +0.026 | 7/0/1 | -0.042 | 8/8 |
| OptDigits: digit 3 vs digit 8, capped at 220/class | ideal_exact | H3_nisq_validation_gap_penalty | +0.026 | 6/0/2 | -0.042 | 8/8 |
| OptDigits: digit 3 vs digit 8, capped at 220/class | nisq_1024_medium_noise | H2_4q_alignment_floor | -0.393 | 0/8/0 | +0.080 | 3/8 |
| OptDigits: digit 3 vs digit 8, capped at 220/class | nisq_1024_medium_noise | H3_nisq_validation_gap_penalty | -0.010 | 7/1/0 | -0.054 | 8/8 |
| OptDigits: digit 3 vs digit 8, capped at 220/class | nisq_4096_low_noise | H2_4q_alignment_floor | -0.452 | 0/8/0 | -0.006 | 7/8 |
| OptDigits: digit 3 vs digit 8, capped at 220/class | nisq_4096_low_noise | H3_nisq_validation_gap_penalty | +0.026 | 6/0/2 | -0.047 | 8/8 |
| OptDigits: digit 3 vs digit 8, capped at 220/class | nisq_512_high_noise | H2_4q_alignment_floor | -0.381 | 1/7/0 | +0.040 | 3/8 |
| OptDigits: digit 3 vs digit 8, capped at 220/class | nisq_512_high_noise | H3_nisq_validation_gap_penalty | +0.088 | 7/0/1 | -0.080 | 8/8 |
| WDBC breast cancer: malignant vs benign | ideal_exact | H2_4q_alignment_floor | +0.049 | 8/0/0 | -0.095 | 8/8 |
| WDBC breast cancer: malignant vs benign | ideal_exact | H3_nisq_validation_gap_penalty | +0.054 | 8/0/0 | -0.092 | 8/8 |
| WDBC breast cancer: malignant vs benign | nisq_1024_medium_noise | H2_4q_alignment_floor | -0.304 | 1/7/0 | -0.099 | 7/8 |
| WDBC breast cancer: malignant vs benign | nisq_1024_medium_noise | H3_nisq_validation_gap_penalty | +0.130 | 8/0/0 | -0.158 | 8/8 |
| WDBC breast cancer: malignant vs benign | nisq_4096_low_noise | H2_4q_alignment_floor | -0.380 | 0/8/0 | -0.082 | 7/8 |
| WDBC breast cancer: malignant vs benign | nisq_4096_low_noise | H3_nisq_validation_gap_penalty | +0.057 | 7/1/0 | -0.109 | 8/8 |
| WDBC breast cancer: malignant vs benign | nisq_512_high_noise | H2_4q_alignment_floor | -0.106 | 1/7/0 | -0.123 | 8/8 |
| WDBC breast cancer: malignant vs benign | nisq_512_high_noise | H3_nisq_validation_gap_penalty | +0.342 | 8/0/0 | -0.287 | 8/8 |
| Wine: class 1 vs class 2 | ideal_exact | H2_4q_alignment_floor | +0.018 | 4/1/3 | -0.023 | 7/8 |
| Wine: class 1 vs class 2 | ideal_exact | H3_nisq_validation_gap_penalty | +0.017 | 4/2/2 | -0.026 | 7/8 |
| Wine: class 1 vs class 2 | nisq_1024_medium_noise | H2_4q_alignment_floor | -0.318 | 0/8/0 | -0.070 | 4/8 |
| Wine: class 1 vs class 2 | nisq_1024_medium_noise | H3_nisq_validation_gap_penalty | +0.012 | 3/2/3 | -0.021 | 7/8 |
| Wine: class 1 vs class 2 | nisq_4096_low_noise | H2_4q_alignment_floor | -0.026 | 3/3/2 | -0.022 | 6/8 |
| Wine: class 1 vs class 2 | nisq_4096_low_noise | H3_nisq_validation_gap_penalty | +0.013 | 4/2/2 | -0.026 | 7/8 |
| Wine: class 1 vs class 2 | nisq_512_high_noise | H2_4q_alignment_floor | -0.391 | 0/8/0 | +0.029 | 4/8 |
| Wine: class 1 vs class 2 | nisq_512_high_noise | H3_nisq_validation_gap_penalty | +0.032 | 4/1/3 | -0.039 | 7/8 |

## Decyzja zespołu

Pierwotna hipoteza H2-NISQ jest wsparta w idealnej symulacji, ale w modelu shot/noise jest zbyt krucha, gdy wybiera niesplątane, bardzo gładkie jądra 4-kubitowe. Ostateczna hipoteza H3 jest wsparta w badanym protokole: walidacyjne strojenie geometrii jądra i regularyzacji utrzymuje lub poprawia balanced accuracy względem H0 przy wyraźnie mniejszej luce train-test. Kryterium anty-overfittingowe jest praktyczne, nie absolutne: wymagamy, aby średnia jakość testowa nie spadała o więcej niż 0.01 balanced accuracy i aby luka train-test nie rosła o więcej niż 0.02.

To nie jest dowód przewagi kwantowej. Jest to test odporności projektu QSVM na warunki NISQ: mniej kubitów, mniej głęboki obwód, skończone shoty i prosty szum depolaryzacyjny.
