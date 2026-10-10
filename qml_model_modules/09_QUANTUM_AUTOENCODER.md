# Quantum Autoencoder

## Status zrodlowy

Pokrycie ograniczone. QMLB wymienia quantum autoencoders jako modele kompresji i rekonstrukcji stanow kwantowych. PG omawia klasyczne autoenkodery jako redukcje wymiaru w hybrydowych modelach, ale nie wyprowadza quantum autoencodera. Modul formalizuje tylko minimalny schemat zgodny z ta wzmianka.

## Zrodla

- QMLB, s. 186: quantum autoencoders dla kompresji i rekonstrukcji stanow kwantowych.
- QMLB, s. 255: referencja do pracy o quantum autoencoders.
- PG, s. 470: klasyczne autoenkodery jako redukcja wymiaru w hybrydowych architekturach.
- LN, s. 49-50: pomiar probabilistyczny i trening QNN.

## Obiekty matematyczne

Wejscie:

```text
|psi>_{AB}
```

Rejestr `A` jest latentny, rejestr `B` jest "trash". Obwod kompresji:

```text
U_theta |psi>_{AB} approx |z_psi>_A |0...0>_B
```

Strata:

```text
L(theta) = 1 - F(rho_B(theta), |0...0><0...0|)
```

## Wyprowadzenie matematyczne

1. Z QMLB, s. 186 wynika, ze celem quantum autoencodera jest kompresja i rekonstrukcja stanow kwantowych.

2. Minimalny warunek kompresji: po obwodzie `U_theta` informacja o stanie ma pozostac w mniejszym rejestrze `A`, a rejestr `B` ma byc resetowalny do znanego stanu:

```text
U_theta |psi>_{AB} -> |z_psi>_A |0...0>_B
```

3. Jesli `rho_B(theta)` jest stanem zredukowanym rejestru trash, strata moze mierzyc, jak blisko jest on stanu odniesienia:

```text
L(theta) = 1 - <0...0|rho_B(theta)|0...0>
```

4. Rekonstrukcja jest mozliwa przez zastosowanie odwrotnego obwodu:

```text
U_theta^dag (|z_psi>_A |0...0>_B) approx |psi>_{AB}
```

Analizowane dokumenty nie podaja szczegolowej funkcji straty ani dowodu optymalnosci; powyzsze jest minimalna formalizacja kompresji z QMLB.

## Wyprowadzenie fizyczne

Quantum autoencoder jest operacja unitarna uczona tak, aby oddzielic informacyjna czesc stanu od nadmiarowej. Poniewaz unitarna ewolucja zachowuje informacje globalnie, "kompresja" nie polega na skasowaniu informacji, lecz na przeniesieniu jej do mniejszego podukladu i ustawieniu reszty w znany stan.

Fizycznie testem sukcesu jest pomiar rejestru trash: im czesciej daje `|0...0>`, tym lepsza kompresja dla rozkladu stanow treningowych.

## Ograniczenia

- Brak pelnego wyprowadzenia quantum autoencodera w analizowanych PDF-ach.
- Model jest najbardziej naturalny dla danych kwantowych; dla danych klasycznych koszt przygotowania stanu moze dominowac.
- Pomiar fidelity lub test trash-register wymaga wielu powtorzen.
- Rekonstrukcja jest gwarantowana tylko w zakresie danych podobnych do treningowych i przy dobrze dobranym ansatzu.

