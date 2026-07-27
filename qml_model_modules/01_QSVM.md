# QSVM - quantum support vector machine

## Status zrodlowy

Pokrycie bezposrednie. LN wyprowadza quantum kernel methods i quantum kernel SVM, a PG rozwija QSVM implementacyjnie. QMLB wskazuje QSVM jako klasyczny przyklad FTQC-QML oparty na metodach liniowo-algebraicznych.

## Zrodla

- LN, s. 42: kodowanie danych jako feature map `phi : X -> H`.
- LN, s. 53-55: quantum kernel methods, model liniowy w przestrzeni cech, kernel Hilberta-Schmidta.
- LN, s. 57-64: quantum kernel support vector machines, estymacja kernela, quantum advantage.
- PG, s. 386-421: QSVM w praktycznym pipeline.
- AAL, s. 61: QSVM jako algorytm nadzorowany oparty na quantum kernels.

## Obiekty matematyczne

Dane klasyczne `x in X` sa kodowane do stanu lub macierzy gestosci:

```text
x -> |phi(x)>
rho(x) = |phi(x)><phi(x)|
```

Quantum kernel:

```text
k_Q(x, x') = Tr[rho(x) rho(x')]
```

Dla stanow czystych:

```text
k_Q(x, x') = |<phi(x)|phi(x')>|^2
```

## Wyprowadzenie matematyczne

1. LN, s. 42 definiuje encoding jako feature map do przestrzeni Hilberta. To wystarcza, aby potraktowac kwantowy stan jako wektor cech.

2. LN, s. 54-55 pokazuje, ze pomiar obserwabli `M` daje model liniowy w przestrzeni cech:

```text
f(x) = Tr[rho(x) M]
```

3. Poniewaz przestrzen macierzy gestosci ma iloczyn Hilberta-Schmidta, naturalny kernel ma postac:

```text
k_Q(x, x') = <rho(x), rho(x')>_HS = Tr[rho(x) rho(x')]
```

4. Klasyczny SVM w dualu potrzebuje tylko wartosci kernela. Po podstawieniu `k_Q` otrzymujemy QSVM:

```text
maximize_alpha  sum_i alpha_i
                - 1/2 sum_ij alpha_i alpha_j y_i y_j k_Q(x_i, x_j)

subject to      0 <= alpha_i <= C,
                sum_i alpha_i y_i = 0
```

5. Predykcja pozostaje klasyczna:

```text
f(x) = sum_i alpha_i y_i k_Q(x_i, x) + b
y_hat = sign f(x)
```

To jest dokladnie sens rozdzielenia pracy w QSVM: QPU estymuje kernel, solver SVM pozostaje klasyczny.

## Wyprowadzenie fizyczne

Fizycznie `k_Q` jest miara nakladania sie stanow przygotowanych przez dwa obwody kodujace dane. Jesli przygotujemy `|phi(x)>`, a nastepnie odwracamy przygotowanie `|phi(x')>`, to prawdopodobienstwo pomiaru stanu bazowego `|0...0>` jest rowne overlapowi:

```text
Pr(0...0) = |<phi(x')|phi(x)>|^2
```

LN, s. 31-32 omawia Hadamard test jako metode pomiaru overlapow i wartosci oczekiwanych. Ten mechanizm jest fizyczna podstawa kernel estimation: wartosc kernela nie jest odczytana z amplitud bezposrednio, lecz estymowana statystycznie przez powtarzane pomiary.

## Ograniczenia

- Koszt macierzy kernela rosnie jak `O(n^2)` dla `n` probek.
- Feature map musi byc nietrywialna, ale nie moze prowadzic do nieinformatywnej koncentracji wartosci kernela.
- LN i QMLB podkreslaja problem read-in/read-out: przewaga znika, jesli przygotowanie danych lub odczyt dominuja koszt.
- AAL zaznacza, ze przewagi QML sa warunkowe i szczegolnie problematyczne w NISQ.
