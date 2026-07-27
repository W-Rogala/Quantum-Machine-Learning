# GAS - Grover Adaptive Search

## Status zrodlowy

Pokrycie bezposrednie w PG. Material opisuje GAS jako adaptacje Grovera do minimalizacji funkcji, z naciskiem na oracles, Durr-Hoyer method i QUBO. QMLB omawia Grover search w szerszym kontekscie quantum perceptron, ale dla GAS najwazniejszym zrodlem jest PG.

## Zrodla

- PG, s. 246-247: motywacja GAS i rozroznienie od algorytmow NISQ.
- PG, s. 247-251: Grover, oracles i obwody.
- PG, s. 251-273: GAS, QUBO i implementacja.
- PG, s. 273: przyklad Qiskit GroverOptimizer.
- QMLB, s. 132: Grover search jako mechanizm kwantowego przeszukiwania.

## Obiekty matematyczne

Przestrzen kandydatow:

```text
x in {0,1}^n
```

Funkcja kosztu:

```text
f(x)
```

Prog adaptacyjny:

```text
y
```

Oracle:

```text
O_y |x>|q> = |x>|q xor [f(x) < y]>
```

## Wyprowadzenie matematyczne

1. PG, s. 246-247 ustawia GAS jako adaptacje Grovera do minimizacji.

2. Dla aktualnego progu `y` definiujemy zbior dobrych kandydatow:

```text
G_y = {x : f(x) < y}
```

3. Oracle oznacza elementy z `G_y`. Grover amplification zwieksza amplitude oznaczonych stanow.

4. Po pomiarze, jesli znaleziono `x'` z `f(x') < y`, aktualizujemy:

```text
y <- f(x')
```

5. Proces powtarza sie adaptacyjnie. W idealnym przypadku Grover daje kwadratowe przyspieszenie wzgledem nieustrukturyzowanego przeszukiwania, ale tylko po uwzglednieniu kosztu oracle.

6. Dla QUBO funkcja `f(x)` jest wielomianem binarnym. PG opisuje, ze trzeba zbudowac oracle obliczajacy wartosc wielomianu i porownujacy ja z progiem.

## Wyprowadzenie fizyczne

Grover amplification to interferencja kontrolowana. Oracle zmienia faze lub bit ancilli dla dobrych rozwiazan, a operator dyfuzji odbija amplitudy tak, aby dobre stany rosly amplitudowo. Pomiar po odpowiedniej liczbie iteracji daje kandydata z wiekszym prawdopodobienstwem.

Adaptacyjnosc GAS polega na klasycznej petli z progiem: QPU probuje znalezc cos lepszego niz obecny kandydat, a CPU aktualizuje prog.

## Ograniczenia

- PG, s. 246 podkresla, ze GAS nie jest projektowany specjalnie dla NISQ i pelny potencjal wymaga FTQC.
- Koszt oracle moze byc dominujacy.
- Kwadratowe przyspieszenie nie oznacza wykladniczej przewagi.
- Dla praktycznych QUBO QAOA i annealing bywaja latwiejsze do uruchomienia na dostepnych platformach.
