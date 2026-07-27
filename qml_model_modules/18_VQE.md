# VQE - variational quantum eigensolver

## Status zrodlowy

Pokrycie bezposrednie. LN wyprowadza VQE z wariacyjnej zasady energii i Hamiltonianu, PG rozwija praktyczne implementacje dla chemii i pomiarow.

## Zrodla

- LN, s. 15-17: VQA i poczatek VQE.
- LN, s. 17-21: Hamiltonian, stan podstawowy, koszt `C(theta)`, dekompozycja Pauliego.
- PG, s. 280-335: VQE w praktyce.
- QMLB, s. 296: VQE jako wazny algorytm wariacyjny w kontekscie chemii/materialow.

## Obiekty matematyczne

Rownanie wlasne Hamiltonianu:

```text
H |psi_i> = E_i |psi_i>
```

Energia stanu podstawowego:

```text
E_0 = min_psi <psi|H|psi>
```

Ansatz:

```text
|psi(theta)> = W(theta) |0...0>
```

Koszt VQE:

```text
C(theta) = <psi(theta)|H|psi(theta)>
```

## Wyprowadzenie matematyczne

1. LN, s. 17 zapisuje problem fizyczny jako znalezienie najmniejszej wartosci wlasnej Hamiltonianu:

```text
H |psi_i> = E_i |psi_i>
```

2. Z zasady wariacyjnej:

```text
E_0 = min_psi <psi|H|psi>
```

3. VQE ogranicza przeszukiwanie do rodziny stanow przygotowanych przez ansatz:

```text
|psi(theta)> = W(theta)|0...0>
```

4. Minimalizowana funkcja kosztu:

```text
C(theta) = <psi(theta)|H|psi(theta)>
```

5. Jesli Hamiltonian rozklada sie na sumy operatorow Pauliego:

```text
H = sum_k c_k P_k
```

to:

```text
C(theta) = sum_k c_k <P_k>_theta
```

Kazde `<P_k>_theta` mozna estymowac pomiarem odpowiedniej bazy.

## Wyprowadzenie fizyczne

VQE jest eksperymentem wariacyjnym. QPU przygotowuje stan probny, mierzy energie jako wartosc oczekiwana Hamiltonianu, a CPU zmienia parametry ansatzu, aby obnizyc energie. Fizycznie korzysta to z faktu, ze prawdziwy stan podstawowy minimalizuje energie.

W chemii kwantowej Hamiltonian opisuje molekule lub material. Jesli ansatz potrafi przyblizyc stan podstawowy, minimalizacja energii daje przyblizenie stabilnej konfiguracji ukladu.

## Ograniczenia

- Liczba pomiarow skladnikow Pauliego moze byc bardzo duza.
- Ansatze zbyt ubogie nie zawieraja dobrego stanu, a zbyt glebokie sa podatne na szum.
- Barren plateaus i lokalne minima utrudniaja trening.
- VQE jest wazne dla QML jako rama wariacyjna, ale samo w sobie jest algorytmem chemii/materialow, nie klasyfikatorem danych.

## Propozycja nowego ansatzu: SCAR-ring

Kandydat roboczy dla plytkiego VQE:

```text
SCAR-ring:
warstwa RY/RZ + pierscien bramek SCAR(theta, delta, phi)
```

SCAR oznacza `Skew-Chiral Amplitude Router`. Jest to dwukubitowa bramka fSim-like, ktora miesza amplitudy `|01>` i `|10>`, dodaje faze korelacyjna oraz ma wspoldzielony parametr chiralnosci osi. Dla `n` kubitow i `L` warstw:

```text
liczba parametrow: L(3n + 2)
liczba bramek dwukubitowych: nL
```

Wniosek: nie da sie miec pelnego pokrycia calej przestrzeni stanow przy malej liczbie parametrow dla ogolnego `n`, bo pelny czysty stan n-kubitowy wymaga `2^(n+1)-2` rzeczywistych stopni swobody. SCAR-ring jest kompromisem: plytki, umiarkowanie parametryczny i ekspresyjny.

Szczegolowy raport i mini-eksperyment:

```text
analysis_output/vqe_scar_ansatz_report.md
analysis_output/vqe_scar_ansatz_experiment.py
analysis_output/vqe_scar_ansatz_results.csv
```
