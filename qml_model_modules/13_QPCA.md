# qPCA - quantum principal component analysis

## Status zrodlowy

Pokrycie czesciowe. AAL podaje bezposrednia definicje: qPCA ma znajdowac skladowe glowne macierzy gestosci przez estymacje wartosci i wektorow wlasnych z quantum phase estimation. QMLB wskazuje qPCA jako przyklad FTQC-QML powiazany z HHL/matrix inversion. Pelny obwod qPCA nie jest w analizowanych materialach rozpisany.

## Zrodla

- AAL, s. 62: qPCA jako estymacja eigenvalues/eigenvectors density matrix przez QPE.
- AAL, s. 61: przewagi qPCA sa warunkowe i zalezne od idealizowanych zalozen.
- QMLB, s. 24: qPCA jako notable example HHL-based/FTQC QML.
- QMLB, s. 56-57: tomografia i koszt rekonstrukcji density matrix.
- QMLB, s. 67: matrix inversion/QSVT jako narzedzia algebry liniowej.

## Obiekty matematyczne

Macierz gestosci:

```text
rho = sum_j lambda_j |u_j><u_j|
```

Cel PCA:

```text
wybrac najwieksze lambda_j i odpowiadajace |u_j>
```

QPE:

```text
|u_j> -> |lambda_j>|u_j>
```

## Wyprowadzenie matematyczne

1. AAL, s. 62 okresla qPCA jako problem znalezienia skladowych glownych density matrix.

2. Jesli density matrix ma rozklad spektralny:

```text
rho = sum_j lambda_j |u_j><u_j|
```

to skladowe glowne odpowiadaja najwiekszym `lambda_j`.

3. Quantum phase estimation moze estymowac fazy/wartosci wlasne operacji zwiazanej z `rho`, dajac schemat:

```text
sum_j beta_j |u_j> -> sum_j beta_j |lambda_j>|u_j>
```

4. Po pomiarze rejestru wartosci wlasnej mozna probkowac komponenty proporcjonalnie do ich udzialu w stanie wejsciowym. To daje dostep do dominujacych kierunkow bez pelnego klasycznego wypisywania macierzy.

5. QMLB, s. 56-57 przypomina jednak, ze pelna rekonstrukcja stanu przez tomografie wymaga bardzo wielu pomiarow; dlatego qPCA ma sens tylko, gdy wynik pozostaje kwantowy albo odczyt jest ograniczony.

## Wyprowadzenie fizyczne

qPCA traktuje statystyke danych jako stan mieszany `rho`. Fizyczna operacja QPE wydobywa informacje spektralna: energia/faza zwiazana z wektorem wlasnym trafia do rejestru pomocniczego. Pomiar tego rejestru selekcjonuje komponenty spektralne.

Jesli dane sa juz kwantowe, `rho` moze byc naturalnym stanem ukladu. Dla danych klasycznych trzeba je najpierw zakodowac, co jest czescia kosztu.

## Ograniczenia

- AAL, s. 62 podaje kluczowe ograniczenie: wymagany jest kwantowy dostep do pelnego datasetu jako density matrix.
- Pelny odczyt wielu komponentow moze wymagac tomografii.
- Przewaga jest warunkowa; AAL, s. 61 ostrzega przed idealizowanymi zalozeniami.
- Analizowane zrodla nie podaja pelnego algorytmu implementacyjnego qPCA.
