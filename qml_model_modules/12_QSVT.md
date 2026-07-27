# QSVT - quantum singular value transformation

## Status zrodlowy

Pokrycie bezposrednie w QMLB. Material podaje definicje block encoding, twierdzenie QSVT dla macierzy rzeczywistych oraz zastosowanie do matrix inversion i transformacji amplitud.

## Zrodla

- QMLB, s. 63-64: definicja block encoding i LCU.
- QMLB, s. 66: QSVT jako metoda implementowania funkcji macierzowych.
- QMLB, s. 67: matrix inversion i nonlinear amplitude transformation.
- QMLB, s. 196-205: uzycie block encoding/QSVT w quantum transformer.

## Obiekty matematyczne

Block encoding:

```text
|| A - alpha (<0|^a tensor I) U_A (|0>^a tensor I) || <= epsilon
```

SVD:

```text
A = sum_i sigma_i |psi_i><phi_i|
```

Transformacja singular values:

```text
P^(SV)(A) = sum_i P(sigma_i) |psi_i><phi_i|
```

## Wyprowadzenie matematyczne

1. QMLB, s. 63 definiuje block encoding: nieunitarna macierz `A` jest osadzona jako blok wiekszej unitarnej operacji `U_A`.

2. Poniewaz bramki kwantowe musza byc unitarne, block encoding jest warstwa posrednia miedzy algebra liniowa ML a fizycznym obwodem kwantowym.

3. Dla SVD:

```text
A = sum_i sigma_i |psi_i><phi_i|
```

QSVT implementuje wielomianowa funkcje na wartosciach singularnych:

```text
A -> P^(SV)(A/alpha)
```

4. QMLB, s. 66 podaje, ze jezeli `P` jest wielomianem stopnia `d` spelniajacym ograniczenia normy na `[-1,1]`, to istnieje obwod uzywajacy `d` wywolan `U_A` i `U_A^dag`, ktory block-encoduje `P^(SV)(A/alpha)` z kontrolowanym bledem.

5. Matrix inversion jest przypadkiem szczegolnym: wybiera sie wielomian przyblizajacy `1/x` poza przedzialem wokol zera. QMLB, s. 67 zapisuje zaleznosc kosztu od dolnego ograniczenia singular values i dokladnosci.

## Wyprowadzenie fizyczne

QSVT jest fizycznie sekwencja kontrolowanych odbic i faz, ktore nie mierza macierzy, lecz transformuja jej spektrum wewnatrz koherentnego obwodu. Informacja o singular values jest zakodowana w dzialaniu unitarnego bloku, a QSVT zmienia amplitudy tak, jakby zastosowano funkcje `P`.

To dlatego QSVT moze byc "parasolem" nad wieloma algorytmami: zmiana wielomianu zmienia operacje matematyczna, ale rdzen fizyczny pozostaje block encoding + sekwencja faz.

## Ograniczenia

- QSVT wymaga dobrego block encoding; to czesto najtrudniejsza czesc.
- Nie jest samodzielnym modelem ML, tylko podprogramem.
- Funkcja musi byc dobrze przyblizalna wielomianem w dozwolonym zakresie.
- Gdy singular values sa blisko zera, inwersja wymaga regularyzacji albo koszt rosnie.
