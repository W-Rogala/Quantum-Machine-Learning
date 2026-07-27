# Hybrid QNN

## Status zrodlowy

Pokrycie bezposrednie w PG. Material opisuje motywacje, architekture i trening hybrydowej sieci z klasycznymi warstwami oraz warstwa kwantowa.

## Zrodla

- PG, s. 468-470: sens hybrydowych architektur, laczenie klasycznej redukcji wymiaru z QNN.
- PG, s. 471-476: implementacja hybrydowej QNN w PennyLane/Keras.
- PG, s. 469: ostrzezenie, ze warstwa kwantowa nie jest magicznym ulepszeniem.
- PG, s. 470: przyklad klasycznego encoder + quantum classifier.

## Obiekty matematyczne

Klasyczna czesc:

```text
z = h_phi(x)
```

Warstwa kwantowa:

```text
q_theta(z) = Tr[M U(z, theta) rho_0 U(z, theta)^dag]
```

Caly model:

```text
F_{phi,theta}(x) = g_w(q_theta(h_phi(x)))
```

## Wyprowadzenie matematyczne

1. PG, s. 469-470 uzasadnia przypadek: klasyczna siec moze zmniejszyc wymiar danych, a QNN moze wykonac klasyfikacje na zredukowanej reprezentacji.

2. Matematycznie klasyczna czesc jest mapa:

```text
h_phi : R^d -> R^m
```

gdzie `m` jest liczba wejsc warstwy kwantowej.

3. Warstwa kwantowa koduje `z = h_phi(x)` i mierzy obserwable:

```text
q_theta(z) = <0| U(z, theta)^dag M U(z, theta) |0>
```

4. Jesli po QNN wystepuje klasyczna warstwa koncowa `g_w`, model koncowy to:

```text
F_{phi,theta,w}(x) = g_w(q_theta(h_phi(x)))
```

5. Trening wspolny minimalizuje:

```text
min_{phi,theta,w} (1/n) sum_i loss(y_i, F_{phi,theta,w}(x_i))
```

Gradient dla `theta` pochodzi z QNN, a dla `phi,w` z klasycznej backpropagacji. PG pokazuje taka integracje przez interfejsy ML.

## Wyprowadzenie fizyczne

Hybrid QNN dzieli eksperyment na dwa swiaty. Klasyczny procesor przygotowuje liczby sterujace bramkami. QPU wykonuje ewolucje unitarna i pomiar. Wynik pomiaru wraca jako liczba do klasycznego grafu obliczen.

Fizycznie wazne jest dopasowanie zakresu danych do bramek. PG, s. 470 ostrzega, ze jesli feature map wymaga normalizacji, poprzednia warstwa klasyczna powinna miec aktywacje zgodna z tym wymaganiem.

## Ograniczenia

- PG wyraznie ostrzega, ze warstwa kwantowa moze pogorszyc model, jesli jest uzyta bez celu.
- Trudno przypisac sukces konkretnie czesci kwantowej, bo klasyczna i kwantowa czesc ucza sie razem.
- Latencja QPU-CPU i liczba shotow sa kosztami niewidocznymi w zwyklym modelu klasycznym.
- Wymagane sa ablation studies: bez warstwy kwantowej, z losowa warstwa i z porownywalna warstwa klasyczna.
