# Quantum clustering

## Status zrodlowy

Pokrycie czesciowe. AAL opisuje quantum clustering jako uzycie kwantowych miar odleglosci lub potencjalowych modeli, w tym quantum-enhanced k-means, gdzie odleglosci liczone sa przez stany kwantowe i interferencje. LN daje toy example klasyfikatora odleglosciowego z interferencja, ktory jest najblizszym szczegolowym wyprowadzeniem mechanizmu odleglosci.

## Zrodla

- AAL, s. 62: quantum clustering i quantum-enhanced k-means.
- LN, s. 7: QML moze wspierac clustering i classification.
- LN, s. 9-13: squared-distance classifier i interferencyjne obliczanie wielkosci zwiazanych z odlegloscia.
- LN, s. 42: feature map do przestrzeni Hilberta.

## Obiekty matematyczne

Dla znormalizowanych wektorow:

```text
||x - c||^2 = 2 - 2 Re <x|c>
```

Przypisanie klastra:

```text
label(x) = argmin_k d_Q(x, c_k)
```

Aktualizacja centroidu w hybrydowym k-means:

```text
c_k = mean{x_i : label(x_i)=k}
```

## Wyprowadzenie matematyczne

1. AAL, s. 62 mowi, ze quantum clustering wykorzystuje kwantowe miary odleglosci, a w quantum-enhanced k-means odleglosc moze byc liczona przez stany i interferencje.

2. LN, s. 9 definiuje odleglosciowy klasyfikator z waga:

```text
gamma_i = 1 - (1/c) ||x_i - x||^2
```

3. LN, s. 13 pokazuje, ze interferencja amplitud po bramce Hadamarda prowadzi do prawdopodobienstw zawierajacych normy typu:

```text
||x_i + x||^2
```

Dla znormalizowanych wektorow jest to rownowazne informacji o `||x_i - x||^2`, bo:

```text
||a + b||^2 + ||a - b||^2 = 4
```

4. Dla k-means wystarczy zamienic probke treningowa `x_i` na centroid `c_k`:

```text
d_Q(x, c_k)^2 = 2 - 2 Re <phi(x)|phi(c_k)>
```

5. Reszta algorytmu moze pozostac klasyczna: przypisanie do najblizszego centroidu i aktualizacja sredniej.

## Wyprowadzenie fizyczne

Mechanizm fizyczny to interferencja. Jesli amplitudy reprezentuja dwa wektory, operacja Hadamarda na rejestrze kontrolnym tworzy sumy i roznice amplitud. Pomiar okresla prawdopodobienstwa zwiazane z norma tych sum/roznic, a wiec z odlegloscia.

W tym sensie QPU nie "widzi" odleglosci jako liczby zapisanej jawnie. Odleglosc jest rekonstruowana statystycznie z czestosci pomiarow.

## Ograniczenia

- AAL daje szkic, nie pelny algorytm quantum clustering.
- Przy danych klasycznych koszt encodingu moze zdominowac obliczenie odleglosci.
- Klasyczne przyblizone nearest-neighbor/k-means sa bardzo szybkim baseline.
- Aktualizacja centroidow zwykle pozostaje klasyczna i moze ograniczac calkowite przyspieszenie.
