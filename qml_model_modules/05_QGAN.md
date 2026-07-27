# QGAN - quantum generative adversarial network

## Status zrodlowy

Pokrycie bezposrednie w PG oraz wzmianka architektoniczna w QMLB. PG wyprowadza klasyczne funkcje strat GAN i nastepnie opisuje warianty quantum GAN.

## Zrodla

- PG, s. 489-493: klasyczny GAN, straty generatora i dyskryminatora.
- PG, s. 493-495: definicja quantum GAN i typy architektur.
- PG, s. 496-499: czysto kwantowy QGAN uczacy stan jednokubitowy.
- PG, s. 518-552: dalsze przyklady QGAN.
- QMLB, s. 186: QGAN jako generatywna architektura QNN.

## Obiekty matematyczne

Dyskryminator:

```text
D_gamma(x) in [0,1]
```

Generator:

```text
G_theta(s)
```

Strata dyskryminatora w notacji PG:

```text
L_D = - 1/(|X|+|S|) [sum_{x in X} log D(x)
                     + sum_{s in S} log(1 - D(G(s)))]
```

Stabilniejsza strata generatora:

```text
L_G = - 1/|S| sum_{s in S} log D(G(s))
```

## Wyprowadzenie matematyczne

1. PG, s. 491-492 wyprowadza GAN jako gre dwoch modeli. Dyskryminator minimalizuje blad rozrozniania danych prawdziwych i generowanych.

2. Generator minimalizuje strate, ktora rosnie, gdy dyskryminator latwo wykrywa falszywe probki. W praktycznej wersji PG stosuje:

```text
L_G = - E_s log D(G_theta(s))
```

3. W QGAN co najmniej jeden z elementow `G_theta` lub `D_gamma` jest modelem kwantowym. Dla generatora kwantowego:

```text
rho_G(theta, s) = U_G(theta, s) rho_0 U_G(theta, s)^dag
```

4. Jesli dyskryminator jest kwantowy, jego wynik moze byc oczekiwana wartoscia projektora:

```text
D_gamma(rho) = Tr[M U_D(gamma) rho U_D(gamma)^dag]
```

5. W czysto kwantowym przykladzie PG, s. 496-499, generator probuje przygotowac stan podobny do stanu treningowego, a dyskryminator dziala na stanie wejscia i ancilli.

## Wyprowadzenie fizyczne

Generator jest fizycznym obwodem przygotowujacym stan lub rozklad pomiarow. Dyskryminator jest eksperymentem pomiarowym, ktory ma odroznic stan/probke zrodla od stanu/probki generatora.

PG, s. 496 podkresla, ze uczenie stanu z wielu kopii nie lamie twierdzenia o no-cloning. Proces przypomina tomografie: wielokrotne pomiary niszcza kopie treningowe, ale dostarczaja informacji do dostrojenia generatora.

## Ograniczenia

- GAN nie ma jednej prostej metryki sukcesu; PG omawia niestabilnosc i mode collapse.
- W QGAN dochodzi shot noise i ograniczona liczba kubitow.
- Pelny kwantowy QGAN wymaga dostepu do kwantowych danych albo architektury bez posrednich pomiarow.
- QMLB wymienia QGAN jako architekture generatywna, ale nie daje ogolnego twierdzenia o przewadze.
