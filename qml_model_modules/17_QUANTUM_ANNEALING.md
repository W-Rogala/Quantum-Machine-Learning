# Quantum annealing

## Status zrodlowy

Pokrycie bezposrednie. LN wyprowadza adiabatic quantum computation i quantum annealing przez Hamiltonian poczatkowy, problemowy i harmonogram. PG daje szeroki praktyczny opis quantum optimization i annealingu.

## Zrodla

- LN, s. 25-28: adiabatic quantum computation, quantum annealing, Ising Hamiltonian, QUBO.
- LN, s. 28: Hamiltonian Isinga i interpretacja sprzetowa.
- PG, s. 142-165: quantum annealing i QUBO w praktyce.
- PG, s. 157-164: formulacje optymalizacyjne i ograniczenia.

## Obiekty matematyczne

Hamiltonian poczatkowy:

```text
H_0
```

Hamiltonian problemowy:

```text
H_P
```

Interpolacja adiabatyczna:

```text
H(t) = A(t) H_0 + B(t) H_P
```

Hamiltonian Isinga:

```text
H_P = - sum_{i<j} J_ij Z_i Z_j - sum_i h_i Z_i
```

## Wyprowadzenie matematyczne

1. LN, s. 25 opisuje zasade adiabatyczna: jesli Hamiltonian zmienia sie dostatecznie wolno, uklad pozostaje w stanie podstawowym.

2. Startujemy od prostego `H_0`, ktorego stan podstawowy jest znany. Nastepnie zmieniamy Hamiltonian w czasie:

```text
H(t) = A(t) H_0 + B(t) H_P
```

gdzie poczatkowo dominuje `H_0`, a na koncu `H_P`.

3. Problem optymalizacyjny koduje sie w `H_P`, tak aby jego stan podstawowy odpowiadal najlepszemu rozwiazaniu.

4. LN, s. 28 daje postac Isinga:

```text
H_P = - sum_{i<j} J_ij Z_i Z_j - sum_i h_i Z_i
```

5. QUBO jest rownowaznym zapisem binarnym, ktory trzeba przeksztalcic do sprzetowo dostepnego Hamiltonianu.

## Wyprowadzenie fizyczne

Quantum annealing jest analogowa ewolucja ukladu kwantowego. Poczatkowy Hamiltonian czesto zawiera skladniki `X_i`, ktore tworza superpozycje i tunelowanie miedzy konfiguracjami. Problemowy Hamiltonian `H_P` jest krajobrazem energii: dobre rozwiazania maja niska energie.

Jesli ewolucja jest wystarczajaco wolna wzgledem minimalnej szczeliny energetycznej, system ma pozostac blisko stanu podstawowego. Pomiar na koncu daje bitstring, czyli kandydat na rozwiazanie.

## Ograniczenia

- Zbyt mala szczelina energetyczna wymaga dlugiego czasu annealingu.
- Realny sprzet ma szum, temperature i ograniczona topologie polaczen.
- Minor embedding moze znaczaco zwiekszyc liczbe kubitow fizycznych.
- Wyniki sa probkami, nie gwarancja optimum.
- Trzeba porownywac caly pipeline z klasycznymi heurystykami i solverami QUBO/MILP.

