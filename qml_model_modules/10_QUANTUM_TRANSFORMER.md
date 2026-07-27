# Quantum Transformer

## Status zrodlowy

Pokrycie bezposrednie w QMLB. Material opisuje fault-tolerant quantum transformer, zalozenia block encoding, quantum self-attention, residual connection i layer normalization. Jest to model FTQC dla inferencji, nie praktyczna architektura NISQ.

## Zrodla

- QMLB, s. 189-190: motywacja transformerow i koszt klasyczny.
- QMLB, s. 196-197: zalozenia input oracles i block encodings.
- QMLB, s. 197: informal theorem dla quantum transformer.
- QMLB, s. 199: quantum self-attention.
- QMLB, s. 205: residual connection i layer normalization.
- QMLB, s. 63-67: block encoding i QSVT jako narzedzia.

## Obiekty matematyczne

Klasyczny attention:

```text
Q = S W_q
K = S W_k
V = S W_v
G_soft = softmax(Q K^T / alpha_0) V
```

Zalozenie quantum transformer:

```text
U_A is a block encoding of A
A in {S, W_q, W_k, W_v, M_1, M_2}
```

Wyjscie dla pozycji `j`:

```text
|out_j> proportional to sum_k Transformer(S, j)_k |k>
```

## Wyprowadzenie matematyczne

1. QMLB, s. 196 zaklada dostep do macierzy sekwencji i wag przez block encoding. Dla macierzy `A`:

```text
|| A - alpha (<0|^a tensor I) U_A (|0>^a tensor I) || <= epsilon
```

2. Z tych encodingow mozna konstruowac produkty macierzy przez arytmetyke block encoding (QMLB, s. 63-64). Dla attention potrzebne sa:

```text
Q = S W_q
K = S W_k
V = S W_v
Q K^T
```

3. QMLB, s. 199 formuluje quantum self-attention: mozna skonstruowac block encoding macierzy `G`, ktorej `j`-ty wiersz odpowiada:

```text
G_j* = (softmax(QK^T / alpha_0) V)_j*
```

4. QMLB, s. 205 pokazuje dalszy blok residual + layer normalization w postaci stanu zakodowanego amplitudowo:

```text
sum_k LN(G_soft_j, S_j)_k |k> / zeta
```

5. Twierdzenie nieformalnie z QMLB, s. 197: dla pojedynczego head/block mozna skonstruowac obwod FTQC przygotowujacy stan proporcjonalny do wektora wyjscia transformera dla indeksu `j`.

## Wyprowadzenie fizyczne

Quantum Transformer nie mierzy kazdego kroku posredniego. Operacje attention, residual i normalization sa reprezentowane koherentnie przez block encodings i transformacje amplitud. Wynik jest stanem kwantowym, ktorego amplitudy odpowiadaja skladowym wektora transformera.

Fizycznie kluczowe jest zachowanie koherencji przez cala inferencje. Pomiar dopiero na koncu zamienia rozklad amplitud na klasyczna predykcje tokenu.

## Ograniczenia

- QMLB jednoznacznie osadza model w FTQC, nie w NISQ.
- Przyspieszenie zalezy od silnych zalozen o dostepie do block encoding/oracles.
- Odczyt pelnego wektora wyjscia zniszczylby przewage; sens ma czesciowy odczyt lub probkowanie tokenu.
- Model dotyczy inferencji juz wytrenowanego klasycznego transformera, nie pelnego treningu end-to-end na obecnym sprzecie.
