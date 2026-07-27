# QCBM - quantum circuit Born machine

## Status zrodlowy

Pokrycie ograniczone. QMLB wymienia QCBM jako jedna z pionierskich architektur generatywnych QNN i wskazuje, ze parametryzowane obwody generuja dyskretne rozklady prawdopodobienstwa. Pelne wyprowadzenie QCBM nie jest w analizowanych materialach rozpisane. Ponizszy modul formalizuje tylko konsekwencje tej definicji oraz reguly Borna z LN.

## Zrodla

- QMLB, s. 186: QCBM jako model generujacy dyskretne rozklady za pomoca parametryzowanych obwodow.
- LN, s. 49: probabilistyczny model kwantowy i regula Borna.
- LN, s. 39-42: kodowanie i pomiar w przestrzeni Hilberta.

## Obiekty matematyczne

Obwod:

```text
|psi(theta)> = U(theta) |0...0>
```

Rozklad Bornowski:

```text
p_theta(z) = |<z|psi(theta)>|^2
```

Cel generatywny:

```text
p_theta(z) approx p_data(z)
```

## Wyprowadzenie matematyczne

1. Z LN, s. 49, pomiar stanu kwantowego w bazie daje prawdopodobienstwa zgodne z regula Borna.

2. QCBM nie potrzebuje dyskryminatora. Caly model generatywny jest rozkladem:

```text
p_theta(z) = |<z|U(theta)|0...0>|^2
```

gdzie `z` jest bitstringiem pomiarowym.

3. Dla empirycznego rozkladu danych `p_data`, uczenie polega na minimalizacji miary odleglosci rozkladow. Analizowane materialy nie narzucaja jednej straty, wiec bezpieczna postac ogolna to:

```text
theta* = argmin_theta D(p_data, p_theta)
```

gdzie `D` moze byc dobrana przez eksperymentatora.

4. Jesli przestrzen bitstringow ma rozmiar `2^n`, pelne porownanie rozkladow wymaga kontroli wielu prawdopodobienstw. W praktyce korzysta sie z probkowania, ale zrodla nie podaja jednego kanonicznego algorytmu treningu QCBM.

## Wyprowadzenie fizyczne

QCBM jest najczystszym przypadkiem "maszyny Borna": fizyczny obwod przygotowuje superpozycje amplitud, a pomiar zamienia kwadrat modulu amplitudy na probke klasyczna. Splatanie w obwodzie moze tworzyc korelacje miedzy bitami probki.

Nie ma tutaj klasycznej funkcji generujacej jawnie wartosc `z`. Zrodlem probki jest akt pomiaru stanu `|psi(theta)>`.

## Ograniczenia

- Pelne wyprowadzenie QCBM nie wystepuje w analizowanych PDF-ach; modul nie dopisuje twierdzen o przewadze.
- Pelny rozklad rosnie jak `2^n`, wiec ocena straty moze byc kosztowna.
- Trening dziedziczy problemy QNN: shot noise, szum sprzetu i barren plateaus.
- QMLB, s. 186 klasyfikuje QCBM jako architekture generatywna, ale nie podaje gwarancji praktycznej przewagi.
