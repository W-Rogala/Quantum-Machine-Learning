# SCAR-QNN na IBM Quantum: wynik sprzętowy

Data wykonania: 2026-07-20.

## Wynik

Trening został wykonany na rzeczywistym QPU `ibm_fez` w instancji IBM
Quantum Open. Wszystkie 13 zadań Runtime zakończyło się statusem `complete`.

| Metryka testowa | SCAR-QNN, IBM QPU | Klasyczny MLP | Różnica QPU - MLP |
|---|---:|---:|---:|
| Accuracy | 0,400 | 0,971 | -0,571 |
| Macro F1 | 0,249 | 0,967 | -0,718 |

Oba modele miały po 43 parametry. Najlepszy checkpoint QPU pochodził z epoki
10. SCAR-QNN osiągnął 0,411 accuracy na treningu i 0,389 na walidacji.

Macierz pomyłek SCAR-QNN na zbiorze testowym:

```text
[[ 0, 11, 1],
 [ 1, 13, 0],
 [ 0,  8, 1]]
```

Model przewidywał głównie klasę 1. Strata treningowa spadła tylko z 1,105 do
1,062 i pozostawała blisko `ln(3) = 1,099`, czyli poziomu losowego klasyfikatora
trzech klas.

## Architektura

- procesor: `ibm_fez`, IBM Heron r2;
- 156 kubitów, topologia heavy-hex;
- natywne bramki dwukubitowe: `CZ`;
- brak fizycznego cyklu czterech kubitów;
- głębokość po transpilerze: 260;
- liczba bramek `CZ`: 66;
- dokładność algebraicznego rozkładu SCAR: maksymalny błąd `2,24e-16`.

Logiczny SCAR-ring wymaga zamknięcia cyklu 0-1-2-3-0. Heavy-hex nie zawiera
czterokubitowego cyklu, dlatego transpiler musiał dodać routing. To zwiększa
głębokość i ekspozycję na błędy dwukubitowe. Jest to zasadnicza różnica względem
siatkowej architektury Nighthawk, która może osadzić taki pierścień bez
dodatkowego zamykania cyklu. Nighthawk nie był dostępny w tej instancji Open.

## Protokół

- dane: UCI Wine, 178 próbek, 13 cech i 3 klasy;
- redukcja: PCA do 4 wymiarów, zachowana wariancja 0,757;
- podział: 107 trening / 36 walidacja / 35 test;
- ansatz: 4 kubity, 2 warstwy SCAR, 28 parametrów kwantowych;
- głowica klasyczna: 15 parametrów;
- optymalizacja: 12 epok SPSA + Adam dla głowicy;
- liczba strzałów: 256;
- włączone w żądaniu: measurement mitigation i dynamical decoupling `XpXm`;
- liczba konfiguracji obwodu: 3178;
- czas ścienny części QPU: 619,45 s;
- naliczone użycie QPU: 384 s, czyli 6,4 min;
- pozostały limit z początkowych 10 min: około 216 s, czyli 3,6 min;
- rzeczywisty czas wykonywania obwodów: 325,75 s.

Tymczasowy klucz IBM Cloud API został utworzony wyłącznie na czas wykonania,
nie został zapisany w profilu lokalnym i został usunięty po pobraniu wyników.

## Kontekst symulatora

Dla tego samego seedu wcześniejszy idealny SCAR-QNN osiągnął accuracy 0,857 i
macro F1 0,843, a MLP 0,971 i 0,967. Idealny QNN był jednak trenowany przez 160
epok innym, znacznie droższym protokołem gradientowym. Różnica 0,857 vs 0,400
nie jest więc czystą miarą szumu QPU: łączy wpływ topologii heavy-hex, 66 bramek
`CZ`, skończonej liczby strzałów oraz krótszej optymalizacji SPSA.

Najmocniejszy wniosek z eksperymentu jest praktyczny: bieżący SCAR-ring nie jest
dobrym ansatzem sprzętowym dla Heron heavy-hex. Kolejna wersja powinna używać
entanglementu zgodnego z drzewem lub ścieżką heavy-hex albo kompilować SCAR jako
warstwy na dopasowanych krawędziach bez logicznego domknięcia pierścienia.

## Identyfikatory wykonania

Batch IBM Quantum:
`e6ef9c37-9d0a-4168-995d-698a0c83fca6`.

Zadania Estimator:

```text
d9f52kqneu4c739p4sa0
d9f533sjeosc73fjg510
d9f53eineu4c739p4t4g
d9f53p9htsac739ev6ug
d9f547sinv1c73aqtti0
d9f54ikjeosc73fjg6cg
d9f54tkjeosc73fjg6pg
d9f558phtsac739ev8dg
d9f55lcjeosc73fjg7h0
d9f55vsinv1c73aqtv9g
d9f56f4jeosc73fjg8bg
d9f56pphtsac739eva20
d9f576kjeosc73fjg930
```

## Xanadu

Nie wykonano zadania na QPU Xanadu. Publicznie opisane X-Series/X8 to
architektura fotoniczna Gaussian Boson Sampling, a nie uniwersalny procesor
kubitowy zgodny z bieżącą bramką SCAR. Dokładna realizacja wymagałaby kodowania
kubitowego, zachowania podprzestrzeni dla stanu `|11>` i nieliniowej fazy
dwucząstkowej. Nazwanie obwodu GBS wykonaniem tego samego SCAR-QNN byłoby
niepoprawne metodologicznie.
