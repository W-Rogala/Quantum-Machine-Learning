# VQC - variational quantum classifier

## Status zrodlowy

Pokrycie bezposrednie. LN wyprowadza probabilistyczne modele kwantowe i VQC, a PG podaje praktyczny trening QNN/VQC. Mechanika gradientu i ograniczenia trenowalnosci sa omowione w LN przez parameter-shift rule i barren plateaus.

## Zrodla

- LN, s. 15-17: ogolna rama VQA.
- LN, s. 31-36: Hadamard test, parameter-shift rule, barren plateaus.
- LN, s. 47-50: QNN, probabilistyczne modele kwantowe, VQC.
- PG, s. 424-464: implementacja i trening QNN/VQC.
- AAL, s. 61-62: variational classifiers jako QML supervised learning.

## Obiekty matematyczne

Stan modelu:

```text
|psi(x, theta)> = U(x, theta) |0...0>
```

Pomiar z projektorami klas:

```text
M = sum_y y |y><y|
p_theta(y | x) = |<y|psi(x, theta)>|^2
```

Funkcja straty:

```text
L(theta) = (1/M) sum_i loss(y_i, y_hat_i)
```

## Wyprowadzenie matematyczne

1. Z LN, s. 49, probabilistyczny model kwantowy przypisuje predykcji `y` prawdopodobienstwo Bornowskie:

```text
p_theta(y | x) = |<y|psi(x, theta)>|^2
```

2. Dla klasyfikacji binarnej mozna uzyc pomiaru Pauli-Z albo projektorow `|0><0|`, `|1><1|`. Jesli wynik ma byc etykieta `+-1`, oczekiwana wartosc:

```text
f_theta(x) = <psi(x, theta)|Z|psi(x, theta)>
```

moze byc interpretowana jako margines decyzyjny.

3. LN, s. 50 zapisuje trening jako minimalizacje sredniej straty po zbiorze uczacym:

```text
L(theta) = (1/M) sum_i L(y_i, y_hat_i)
```

gdzie `y_hat_i` pochodzi z pomiaru obwodu.

4. Gradient parametru bramki rotacyjnej mozna estymowac regula przesuniecia parametru. W standardowym przypadku generatora o dwoch wartosciach wlasnych:

```text
d f(theta)/d theta = 1/2 [f(theta + pi/2) - f(theta - pi/2)]
```

LN, s. 32-36 podaje kontekst pomiarow i problem barren plateaus.

## Wyprowadzenie fizyczne

VQC jest kontrolowanym ukladem kwantowym. Dane `x` ustalaja bramki kodujace, a parametry `theta` sa klasycznymi nastawami impulsow/bramek. Ewolucja jest unitarna, ale wynik uczenia jest klasyczny, poniewaz predykcja powstaje przez pomiar. Losowosc predykcji nie jest bledem implementacji - wynika z reguly Borna.

Rotacje typu `R_Y(x)` odpowiadaja ewolucji pod Hamiltonianem Pauliego, zgodnie z LN, s. 41. W tym sensie angle encoding jest fizycznie ewolucja przez czas lub kat zalezy od danych.

## Ograniczenia

- Pomiar wprowadza wariancje zalezne od liczby shotow.
- Szum NISQ zaburza prawdopodobienstwa klas.
- Barren plateaus moga powodowac zanik gradientu wraz ze wzrostem liczby kubitow.
- VQC nie ma automatycznej przewagi nad klasycznym klasyfikatorem; potrzebny jest baseline.

