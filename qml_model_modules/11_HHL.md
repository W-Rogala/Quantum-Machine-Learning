# HHL - quantum linear systems algorithm

## Status zrodlowy

Pokrycie posrednie. QMLB wskazuje HHL jako kamien milowy FTQC-QML i zrodlo technik matrix inversion dla QSVM, qPCA i innych algorytmow. Pelny obwod HHL nie jest w analizowanych materialach rozpisany krok po kroku; QMLB omawia natomiast block encoding, matrix inversion przez QSVT oraz caveats HHL-based QML.

## Zrodla

- QMLB, s. 23-24: HHL jako quantum linear equations solver i podprogram FTQC-QML.
- QMLB, s. 24-25: caveats HHL-based QML, w tym silny model dostepu do danych.
- QMLB, s. 63-67: block encoding i matrix inversion przez QSVT.
- QMLB, s. 73: HHL jako przyklad algorytmu, w ktorym stan rozwiazania lezy w przestrzeni wierszy/kolumn macierzy.
- LN, s. 40: amplitude encoding i koszt przygotowania stanu.

## Obiekty matematyczne

Problem:

```text
A x = b
```

Stan wejscia:

```text
|b> = sum_j beta_j |u_j>
```

Rozklad spektralny:

```text
A |u_j> = lambda_j |u_j>
```

Stan rozwiazania:

```text
|x> proportional to A^{-1}|b> = sum_j beta_j/lambda_j |u_j>
```

## Wyprowadzenie matematyczne

1. QMLB, s. 23-24 wskazuje, ze HHL redukuje problem rozwiazywania ukladow liniowych do procedury kwantowej, ale pod warunkami dotyczacymi macierzy i wejscia.

2. Jesli `A` ma baze wektorow wlasnych `|u_j>`, mozemy zapisac:

```text
|b> = sum_j beta_j |u_j>
```

3. Idealna inwersja macierzy powinna dac:

```text
A^{-1}|b> = sum_j beta_j lambda_j^{-1} |u_j>
```

4. QMLB, s. 67 daje analogiczna idee matrix inversion przez QSVT: przy dolnym ograniczeniu niezerowych wartosci singularnych mozna przyblizac funkcje `1/x` wielomianem na przedziale oddalonym od zera.

5. HHL realizuje ten cel jako stan kwantowy `|x>`, a nie jako wypisany klasyczny wektor. To jest zgodne z QMLB, s. 73, gdzie podkreslony jest problem read-out i rekonstrukcji stanu.

## Wyprowadzenie fizyczne

Fizyczny rdzen HHL to interferencyjne przetworzenie faz zwiazanych z wartosciami wlasnymi. W standardowym obrazie fazy pozwalaja warunkowo obracac ancille z amplituda zalezec od `1/lambda_j`, po czym odwraca sie etap estymacji fazy. Po postselekcji ancilli pozostaje stan proporcjonalny do `A^{-1}|b>`.

W analizowanych zrodlach ten obwod nie jest rozpisany w pelni, dlatego modul traktuje go jako znany schemat HHL przywolany przez QMLB, a scisle zrodlowe rozwijanie inwersji opiera na QSVT z QMLB, s. 63-67.

## Ograniczenia

- HHL wymaga efektywnego przygotowania `|b>`; LN, s. 40 ostrzega, ze amplitude encoding moze byc kosztowny.
- Pelny odczyt `x` jako klasycznego wektora moze usunac przewage.
- Warunek uwarunkowania macierzy i odstep od zera jest krytyczny.
- QMLB, s. 24-25 wskazuje, ze HHL-based QML ma silne caveats zwiazane z input model, QRAM i porownaniem z algorytmami klasycznymi.

