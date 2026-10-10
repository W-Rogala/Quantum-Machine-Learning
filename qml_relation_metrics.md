# Metryki stosowane w doborze cechy relacji w grafie QML

## Cel metryki

Graf ma pokazywac relacje miedzy algorytmami QML po wybranej cesze:

- rodzina algorytmiczna,
- typ uczenia,
- era/sprzet,
- model obliczen,
- kodowanie danych,
- trening/optymalizacja,
- zrodlo potencjalnej przewagi,
- wspolne ograniczenia,
- zastosowania.

Dla kazdej takiej cechy kazdy algorytm ma liste wartosci. Relacja miedzy dwoma algorytmami powstaje wtedy, gdy ich listy maja co najmniej jedna wspolna wartosc.

## Metryka podstawowa: wazony overlap wartosci

Dla dwoch modeli `A` i `B` oraz cechy `f`:

```text
V_A(f) = zbior wartosci cechy f dla modelu A
V_B(f) = zbior wartosci cechy f dla modelu B
C(A,B|f) = V_A(f) intersect V_B(f)
```

Jesli:

```text
C(A,B|f) = empty
```

to krawedz nie powstaje.

Jesli wspolne wartosci istnieja, liczony jest wynik:

```text
df(v) = liczba modeli, ktore zawieraja wartosc v
score(A,B|f) = sum_{v in C(A,B|f)} 1 / df(v)
```

To jest metryka podobna intuicyjnie do inverse document frequency:

- wartosc bardzo ogolna, np. `NISQ`, wystepuje w wielu modelach, wiec daje maly wklad,
- wartosc rzadsza, np. specyficzny mechanizm lub waska rodzina, daje wiekszy wklad,
- kilka wspolnych wartosci sumuje sie, wiec relacja z wieloma konkretnymi podobienstwami jest silniejsza.

## Wizualna waga krawedzi

Wynik `score` jest przeskalowany do wagi wizualnej:

```text
weight = clamp(1 + 5 * score, 1, 5)
```

gdzie:

```text
clamp(x, 1, 5) = min(5, max(1, x))
```

Waga ma zakres od 1 do 5 i steruje:

- gruboscia krawedzi,
- sila przyciagania miedzy wezlami,
- docelowa odlegloscia krawedzi w ukladzie silowym.

W implementacji:

```text
strokeWidth = 1 + 0.42 * weight
force = (dist - desired) * linkStrength * weight
desired = linkDistance - min(44, 8 * weight)
```

Silniejsza relacja jest wiec grubsza i mocniej przyciaga wezly.

## Sortowanie i limit relacji

Dla cech liczonych automatycznie wszystkie mozliwe pary modeli sa oceniane wedlug `score`. Potem krawedzie sa sortowane malejaco:

```text
edges = sort_by_desc(score)
```

Widoczna jest tylko pierwsza grupa najmocniejszych relacji:

```text
visible_edges = top(edgeLimit)
```

Suwak `Limit relacji` steruje liczba widocznych krawedzi w zakresie 20-100. To jest filtr czytelnosci wizualnej, nie zmiana samej metryki.

## Relacje eksperckie

Dla parametru `relacje eksperckie` metryka overlapu nie jest uzywana.

Te krawedzie zostaly dobrane recznie na podstawie analizy materialow zrodlowych i zaleznosci merytorycznych:

```text
edge.weight = reczna ocena z zakresu 1..5
```

Interpretacja wag:

- `1` - relacja posrednia lub kontekstowa,
- `2` - relacja pomocnicza,
- `3` - wspolna rama, rodzina lub podprogram,
- `4` - silny wspolny mechanizm matematyczny/fizyczny,
- `5` - zaleznosc definicyjna albo bezposrednie uzycie jednego algorytmu przez drugi.

Przy relacjach eksperckich pokazywana jest cala kuracja, bez filtrowania suwakiem limitu relacji.

## Znaczenie poszczegolnych cech

### Rodzina algorytmiczna

Laczy modele wedlug klasy metody: QNN, VQA, metody jadrowe, generatywne, linear algebra, optymalizacja. Ta cecha dobrze pokazuje genealogie algorytmow.

### Typ uczenia

Laczy modele wedlug zadania ML: nadzorowane, nienadzorowane, generatywne, regresja, reinforcement, optymalizacja lub subroutine. Ta cecha odpowiada na pytanie: "do jakiego typu problemu ML sluzy model?".

### Era/sprzet

Laczy modele wedlug rezimu wykonania: NISQ, FTQC, annealing, podejscie teoretyczne. Ta cecha jest szczegolnie wazna przy ocenie praktycznosci.

### Model obliczen

Laczy modele przez sposob realizacji obliczen: model bramkowy, hybrydowy, annealer, sampling, QPE, QSVT, block encoding. Ta cecha pokazuje wspolna infrastrukture wykonawcza.

### Kodowanie danych

Laczy modele przez sposob wejscia danych lub problemu: feature map, angle encoding, amplitude encoding, Hamiltonian, QUBO/Ising, block encoding. Ta cecha jest mocno zwiazana z kosztem read-in.

### Trening/optymalizacja

Laczy modele wedlug procedury uczenia: classical optimizer, parameter shift, kernel estimation, minimax, maximum likelihood, amplitude amplification, QPE. Ta cecha pomaga identyfikowac wspolne problemy treningowe.

### Zrodlo potencjalnej przewagi

Laczy modele przez deklarowany mechanizm przewagi: ekspresyjnosc Hilberta, probkowanie, speedup algebry liniowej, tunelowanie, block encoding, Grover-like search. Ta cecha jest najbardziej krytyczna metodologicznie, bo podobne obietnice zwykle maja podobne zalozenia.

### Wspolne ograniczenia

Laczy modele przez ograniczenia: szum, koszt pomiarow, state preparation, read-out, barren plateaus, koszt oracle, topologia sprzetu. Ta cecha jest dobra do projektowania benchmarkow.

### Zastosowania

Laczy modele przez obszary aplikacji: klasyfikacja, regresja, obrazy, finanse, chemia, logistyka, portfolio, generowanie danych. Ta cecha pokazuje alternatywne algorytmy dla podobnego problemu domenowego.

## Czego metryka nie robi

Metryka nie mierzy:

- rzeczywistej przewagi kwantowej,
- empirycznej skutecznosci na benchmarkach,
- kosztu sprzetowego w sekundach,
- dokladnosci predykcyjnej,
- jakosci dowodu matematycznego,
- poziomu dojrzalosci technologicznej.

Jest to metryka strukturalnej bliskosci opisow algorytmow, przydatna do eksploracji mapy metod QML.

