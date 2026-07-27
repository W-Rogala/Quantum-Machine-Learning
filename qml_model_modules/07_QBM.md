# QBM - quantum Boltzmann machine

## Status zrodlowy

Pokrycie ograniczone. QMLB wymienia Quantum Boltzmann Machines jako modele uzywajace urzadzen kwantowych do przygotowania rozkladow Boltzmanna. AAL klasyfikuje je jako energetyczne modele probabilistyczne. LN daje formalizm Isinga/QUBO i quantum annealingu, ktory jest najblizszym szczegolowym materialem fizycznym.

## Zrodla

- QMLB, s. 186: QBM jako generatywny model QNN przygotowujacy rozklady Boltzmanna.
- QMLB, s. 255: referencja do pracy o Quantum Boltzmann Machine.
- AAL, s. 62: QBM jako model energetyczny w rodzinie QNN.
- LN, s. 25-28: adiabatic computation, quantum annealing, Ising Hamiltonian i QUBO.

## Obiekty matematyczne

Hamiltonian energetyczny:

```text
H_theta
```

Stan termiczny:

```text
rho_theta = exp(-beta H_theta) / Z_theta
Z_theta = Tr exp(-beta H_theta)
```

Rozklad obserwowanych zmiennych:

```text
p_theta(v) = Tr[Pi_v rho_theta]
```

## Wyprowadzenie matematyczne

1. LN, s. 28 pokazuje Hamiltonian Isinga:

```text
H_P = - sum_{i<j} J_ij Z_i Z_j - sum_i h_i Z_i
```

2. Dla modelu Boltzmanna energia stanu okresla jego prawdopodobienstwo. Minimalna formalizacja QBM zgodna ze zrodlami to:

```text
rho_theta = exp(-beta H_theta) / Tr exp(-beta H_theta)
```

3. Jesli `v` oznacza widzialne bity, prawdopodobienstwo danych uzyskujemy przez projekcje lub marginalizacje pozostalych stopni swobody:

```text
p_theta(v) = Tr[Pi_v rho_theta]
```

4. Uczenie przez maximum likelihood ma postac:

```text
theta* = argmax_theta sum_i log p_theta(v_i)
```

Analizowane dokumenty nie wyprowadzaja gradientow QBM, dlatego modul nie rozwija contrastive divergence ani szczegolowych metod treningu.

## Wyprowadzenie fizyczne

QBM interpretuje uczenie jako dostrajanie Hamiltonianu ukladu tak, aby stan termiczny lub probki z urzadzenia mialy statystyke podobna do danych. W polaczeniu z LN, s. 25-28 fizyczny obraz jest energetyczny: konfiguracje o nizszej energii sa czestsze, a sprzet typu annealer probkuje konfiguracje powiazane z krajobrazem energii.

Jesli Hamiltonian zawiera tylko skladniki diagonalne `Z_i`, model jest bliski klasycznemu Ising/Boltzmann. Elementy niekomutujace sa kwantowym rozszerzeniem, ale analizowane PDF-y nie rozwijaja ich szczegolowo.

## Ograniczenia

- Brak pelnego wyprowadzenia QBM w analizowanych dokumentach.
- Probkowanie z `exp(-beta H)` jest trudne i zalezy od temperatury, szumu oraz topologii sprzetu.
- Interpretacja wynikow annealera jako idealnego rozkladu Boltzmanna jest zalozeniem, a nie automatycznym faktem.
- QBM jest w materialach raczej kierunkiem badawczym niz gotowym pipeline ML.
