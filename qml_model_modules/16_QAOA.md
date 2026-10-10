# QAOA - quantum approximate optimization algorithm

## Status zrodlowy

Pokrycie bezposrednie. LN wyprowadza QAOA przez Hamiltonian kosztu, mixer, stan poczatkowy i warstwy `p`. PG zawiera praktyczny rozdzial QAOA i przyklady optymalizacji.

## Zrodla

- LN, s. 21-23: definicja QAOA, `U(C,gamma)`, `U(B,beta)`, stan `|s>`, Max-Cut.
- LN, s. 23: przejscie od bitow/spinow do operatorow `Z_i`.
- PG, s. 207-244: praktyczne uzycie QAOA.
- LN, s. 15-17: VQA jako ogolna hybrydowa rama.

## Obiekty matematyczne

Hamiltonian kosztu:

```text
H_C
```

Ewolucja kosztu:

```text
U_C(gamma) = exp(-i gamma H_C)
```

Mixer:

```text
H_B = sum_i X_i
U_B(beta) = exp(-i beta H_B)
```

Stan QAOA:

```text
|psi(gamma,beta)> =
U_B(beta_p) U_C(gamma_p) ... U_B(beta_1) U_C(gamma_1) |s>
```

## Wyprowadzenie matematyczne

1. LN, s. 21 definiuje problem kombinatoryczny przez funkcje celu `C`, ktora koduje sie w diagonalnym Hamiltonianie `H_C`.

2. Sam `H_C` zmienia tylko fazy stanow bazowych, wiec nie zmienia prawdopodobienstw. LN wyjasnia dlatego potrzebe mixera `H_B`, ktory wprowadza przejscia miedzy bitstringami.

3. Stan poczatkowy jest jednorodna superpozycja:

```text
|s> = 1/sqrt(2^n) sum_{z in {0,1}^n} |z> = |+>^{tensor n}
```

4. Po `p` warstwach:

```text
|psi(gamma,beta)> =
U_B(beta_p) U_C(gamma_p) ... U_B(beta_1) U_C(gamma_1) |s>
```

5. Parametry sa optymalizowane klasycznie:

```text
maximize C(gamma,beta) =
<psi(gamma,beta)|H_C|psi(gamma,beta)>
```

albo rownowaznie minimalizuje sie minus te wartosc.

6. Dla Max-Cut LN, s. 23 przechodzi od spinow `s_i=(-1)^{z_i}` do operatorow `Z_i`:

```text
C(z) = sum_{(i,j) in E} (1 - s_i s_j)/2
H_C = sum_{(i,j) in E} (1 - Z_i Z_j)/2
```

## Wyprowadzenie fizyczne

QAOA jest zdyskretyzowana intuicja adiabatyczna. Hamiltonian kosztu nadaje fazy zalezne od energii bitstringow, a mixer przemieszcza amplitude po grafie stanow. Dopiero naprzemiennosc tych dwoch operacji pozwala interferencji wzmacniac prawdopodobienstwa dobrych rozwiazan.

Parametr `gamma` jest czasem/sila dzialania Hamiltonianu kosztu, a `beta` czasem/sila dzialania Hamiltonianu mixera. Klasyczny optymalizator stroi te czasy.

## Ograniczenia

- Dla malych `p` obwod moze byc za malo ekspresyjny.
- Dla duzych `p` rosnie glebokosc i wrazliwosc na szum.
- Krajobraz optymalizacji moze miec lokalne minima.
- QAOA jest algorytmem optymalizacji; w QML jest podprogramem, np. dla feature selection lub QUBO, a nie samodzielnym modelem klasyfikacji.

