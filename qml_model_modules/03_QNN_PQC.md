# QNN / PQC - quantum neural network / parametrized quantum circuit

## Status zrodlowy

Pokrycie bezposrednie. LN opisuje QNN jako rodzine modeli deterministycznych i probabilistycznych, QMLB rozwija architekture QNN oraz trzy krytyczne osie teorii: expressivity, generalization i trainability.

## Zrodla

- LN, s. 15-17: VQA jako hybrydowa petla kwantowo-klasyczna.
- LN, s. 39-42: basis, amplitude, angle i feature-map encoding.
- LN, s. 47-50: QNN, modele deterministyczne i probabilistyczne.
- QMLB, s. 140: wejscie, obwod modelu i pomiar w QNN.
- QMLB, s. 150-160: podstawy teoretyczne QNN: expressivity, generalization, trainability.
- QMLB, s. 184: przeglad teorii overparameterization, QNTK i generalizacji.

## Obiekty matematyczne

Wejscie moze byc stanem kwantowym `rho_in` albo klasycznym `x` zakodowanym przez `E(x)`. Obwod modelu:

```text
rho_out(x, theta) = V(theta) E(x) rho_0 E(x)^dag V(theta)^dag
```

Wyjscie deterministyczne:

```text
f_theta(x) = Tr[M rho_out(x, theta)]
```

Wyjscie probabilistyczne:

```text
p_theta(y | x) = Tr[Pi_y rho_out(x, theta)]
```

## Wyprowadzenie matematyczne

1. LN, s. 39-42 daje mapy kodowania danych. Kazda z nich tworzy stan poczatkowy zalezy od `x`.

2. QMLB, s. 140 opisuje QNN przez trzy bloki: input, model circuit i measurement. Formalnie jest to kompozycja:

```text
x -> rho_in(x) -> V(theta) rho_in(x) V(theta)^dag -> measurement
```

3. Jesli pomiar jest obserwabla `M`, model jest funkcja oczekiwanej wartosci:

```text
f_theta(x) = Tr[M V(theta) rho_in(x) V(theta)^dag]
```

4. Jesli pomiar ma projektory klas `Pi_y`, model zwraca rozklad:

```text
p_theta(y | x) = Tr[Pi_y V(theta) rho_in(x) V(theta)^dag]
```

5. Trening jest optymalizacja klasyczna:

```text
theta* = argmin_theta (1/m) sum_i loss(y_i, f_theta(x_i))
```

6. QMLB, s. 150-160 uzasadnia, ze analiza modelu nie moze konczyc sie na ekspresyjnosci. Potrzebne sa trzy warunki: model musi reprezentowac hipoteze, generalizowac z ograniczonej liczby probek i miec krajobraz straty, ktory da sie trenowac.

## Wyprowadzenie fizyczne

PQC jest sekwencja fizycznych operacji unitarnych sterowanych klasycznymi parametrami. Bramka parametryczna `exp(-i theta P/2)` jest ewolucja pod generatorem Pauliego `P`. Splatanie w ansatzu tworzy korelacje miedzy kubitami, a pomiar redukuje stan do danych klasycznych.

QNN nie jest "siecia neuronowa" w sensie doslownych neuronow. Jest ukladem kwantowym, ktorego dostepne transformacje i pomiary tworza rodzine funkcji uczacych.

## Ograniczenia

- Wieksza przestrzen Hilberta nie gwarantuje przewagi.
- Glebokie losowe ansatze moga prowadzic do barren plateaus.
- Odczyt pelnego stanu wymaga tomografii i skaluje sie zle; praktyczne QNN mierza tylko wybrane obserwable.
- QMLB ostrzega, ze koszty read-in/read-out moga zdominowac zysk.
