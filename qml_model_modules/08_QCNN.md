# QCNN - quantum convolutional neural network / quanvolution

## Status zrodlowy

Pokrycie ograniczone. QMLB i AAL wymieniaja QCNN/quantum convolutional neural networks w kontekscie architektur QNN i trenowalnosci, ale analizowane materialy nie zawieraja pelnego wyprowadzenia QCNN. Ponizszy modul daje konserwatywna formalizacje QCNN jako strukturalnie ograniczonego QNN.

## Zrodla

- QMLB, s. 140: QNN jako input, model circuit, measurement.
- QMLB, s. 249: bibliograficzna wzmianka o braku barren plateaus w quantum convolutional neural networks.
- AAL, s. 64: variational classifiers i zastosowania QML; wzmianki o architekturach kwantowych.
- LN, s. 47-50: QNN i VQC jako baza formalna.

## Obiekty matematyczne

Lokalny blok konwolucyjny:

```text
C_l(theta_l)
```

Pooling lub redukcja rejestru:

```text
P_l
```

Caly obwod:

```text
U_QCNN(theta) = P_L C_L(theta_L) ... P_1 C_1(theta_1) E(x)
```

Wyjscie:

```text
f_theta(x) = Tr[M U_QCNN(theta) rho_0 U_QCNN(theta)^dag]
```

## Wyprowadzenie matematyczne

1. Z QMLB, s. 140 i LN, s. 47-50, kazda QNN ma trzy skladniki: kodowanie wejscia, obwod modelu i pomiar.

2. QCNN powstaje przez nalozenie ograniczenia architektonicznego na obwod modelu: bramki dzialaja lokalnie, a kolejne warstwy redukuja liczbe aktywnych stopni swobody.

3. Formalnie jest to nadal QNN:

```text
rho_out = U_QCNN(theta) rho_0 U_QCNN(theta)^dag
```

a wynik pochodzi z pomiaru:

```text
f_theta(x) = Tr[M rho_out]
```

4. Element "convolution" nie jest w analizowanych zrodlach wyprowadzony jako scisly odpowiednik klasycznej konwolucji. Bezpieczna interpretacja: jest to lokalny, powtarzalny lub warstwowy blok unitarny, ktory ogranicza zasieg oddzialywan.

## Wyprowadzenie fizyczne

Fizycznie QCNN wykorzystuje lokalnosc. Zamiast splatac wszystkie kubity globalnie, obwod buduje korelacje lokalne, a pooling usuwa lub agreguje czesc informacji przez pomiar, odrzucenie kubitow albo dalsza redukcje rejestru.

Taki obraz jest zgodny z intuicja ukladow kwantowych: lokalne unitarne ewolucje moga najpierw wykrywac krotkozasiegowe korelacje, a kolejne warstwy przenosza informacje na bardziej globalny poziom.

## Ograniczenia

- Analizowane materialy nie daja pelnego algorytmu QCNN, wiec modul nie przypisuje mu zrodlowo udowodnionej przewagi.
- Przy danych obrazowych klasyczne CNN sa bardzo mocnym baseline.
- Jesli kazdy patch wymaga osobnego uruchomienia obwodu, koszt shotow szybko rosnie.
- Wzmianka QMLB o trenowalnosci QCNN ma charakter bibliograficzny, nie jest w tych materialach pelnym dowodem.
