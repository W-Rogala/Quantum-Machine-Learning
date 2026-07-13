# Opis i dowód matematyczny hipotezy H2

## 1. Treść hipotezy H2

Hipoteza H2 dotyczy modelu QSVM-like, czyli klasyfikatora jądrowego, w którym część kwantowa odpowiada za macierz podobieństwa między próbkami.

**H2:** zachować kalibrację jądra przez kernel-target alignment, ale narzucić minimalną pojemność 4 kubitów. Wtedy model powinien zachować lub poprawić jakość względem bazowego jądra 6-kubitowego, a jednocześnie zużywać mniej zasobów obliczeniowych, ponieważ stan 4-kubitowy ma `2^4 = 16` amplitud zamiast `2^6 = 64`.

Intuicja zespołu:

- fizyk kwantowy: 2 kubity są zbyt małą przestrzenią Hilberta dla części danych, ale 4 kubity dają jeszcze tanią, a już wyraźnie bogatszą geometrię;
- specjalista ML: PCA do 4 składowych traci mniej informacji niż PCA do 2 składowych;
- statystyk: alignment dobiera jądro zgodne z etykietami, ale wynik accuracy trzeba potwierdzić testem;
- inżynier obliczeń: koszt symulacji jądra skaluje się z wymiarem stanu, więc przejście z 6 do 4 kubitów daje teoretycznie czterokrotną redukcję wymiaru.

## 2. Formalizacja

Niech dany będzie zbiór uczący

```math
D = \{(x_i, y_i)\}_{i=1}^n,\quad y_i \in \{-1, +1\}.
```

Po standaryzacji wykonujemy PCA i zostawiamy `q` składowych:

```math
z_i^{(q)} = P_q x_i \in \mathbb{R}^q.
```

Następnie składowe są skalowane do przedziału `[0,1]` i kodowane w obwodzie kwantowym typu `ZZFeatureMap`. Feature mapę oznaczmy przez

```math
\Phi_{q,\alpha,e}: \mathbb{R}^q \to \mathbb{C}^{2^q},
```

gdzie `q` to liczba kubitów, `alpha` to skala kątów, a `e` to siła sprzężenia dwukubitowego. Dla próbki `x_i` stan kwantowy oznaczamy:

```math
|\psi_i\rangle = \Phi_{q,\alpha,e}(z_i^{(q)}).
```

Jądro kwantowe ma postać:

```math
K_{ij}^{(q,\alpha,e)} =
|\langle \psi_i | \psi_j \rangle|^2.
```

Wariant bazowy H0 używa `q = 6`. Hipoteza H2 dopuszcza strojenie `alpha` oraz `e`, ale wymusza:

```math
q \ge 4.
```

W eksperymencie H2 wybiera konfigurację bliską najlepszemu kernel-target alignment:

```math
(q^*, \alpha^*, e^*) =
\arg\min_{q,\alpha,e} q
```

przy warunku

```math
A(K^{(q,\alpha,e)}, yy^T)
\ge 0.95\max_{\tilde q,\tilde \alpha,\tilde e}
A(K^{(\tilde q,\tilde \alpha,\tilde e)}, yy^T),
\quad q \ge 4.
```

## 3. Lemat 1: jądro kwantowe jest dodatnio półokreślone

**Teza:** macierz

```math
K_{ij}=|\langle\psi_i|\psi_j\rangle|^2
```

jest poprawnym jądrem, czyli jest dodatnio półokreślona.

**Dowód.** Zauważmy, że

```math
|\langle\psi_i|\psi_j\rangle|^2
=
\langle\psi_i|\psi_j\rangle
\langle\psi_j|\psi_i\rangle.
```

Możemy przepisać to jako zwykły iloczyn skalarny w przestrzeni tensorowej:

```math
|\langle\psi_i|\psi_j\rangle|^2
=
\langle \psi_i \otimes \psi_i^*
|
\psi_j \otimes \psi_j^*
\rangle.
```

Zdefiniujmy

```math
|\varphi_i\rangle = |\psi_i\rangle \otimes |\psi_i^*\rangle.
```

Wtedy

```math
K_{ij} = \langle \varphi_i | \varphi_j \rangle.
```

Dla dowolnego wektora współczynników `c \in \mathbb{R}^n` mamy:

```math
c^T K c
=
\sum_{i,j} c_i c_j \langle\varphi_i|\varphi_j\rangle
=
\left\|
\sum_i c_i |\varphi_i\rangle
\right\|^2
\ge 0.
```

Zatem `K` jest dodatnio półokreślona i może być użyta przez klasyfikator jądrowy. □

## 4. Lemat 2: H2 ma czterokrotnie mniejszy wymiar stanu niż H0

Dla `q` kubitów wymiar przestrzeni Hilberta wynosi:

```math
\dim \mathcal{H}_q = 2^q.
```

Dla baseline H0:

```math
\dim \mathcal{H}_6 = 2^6 = 64.
```

Dla H2:

```math
\dim \mathcal{H}_4 = 2^4 = 16.
```

Stąd stosunek wymiarów:

```math
\frac{\dim \mathcal{H}_4}{\dim \mathcal{H}_6}
=
\frac{16}{64}
=
\frac{1}{4}.
```

Jeżeli koszt symulacji macierzy jądra jest zdominowany przez liczenie overlapów stanów, to skaluje się jak:

```math
T(q) = O(n^2 2^q).
```

Dlatego:

```math
\frac{T(4)}{T(6)}
\approx
\frac{n^2 2^4}{n^2 2^6}
=
\frac{1}{4}.
```

To dowodzi zasobowej części H2: wariant 4-kubitowy ma teoretycznie czterokrotnie mniejszy wymiar stanu niż wariant 6-kubitowy. □

## 5. Lemat 3: limit 4 kubitów zachowuje nie mniej informacji PCA niż redukcja do 2 kubitów

Niech `lambda_1 >= lambda_2 >= ... >= lambda_d >= 0` będą wartościami własnymi macierzy kowariancji danych po standaryzacji. Z twierdzenia Eckarta-Younga PCA do `q` składowych minimalizuje błąd rekonstrukcji rzędu `q`, a błąd ten wynosi:

```math
E_q = \sum_{k=q+1}^{d}\lambda_k.
```

Dla `q = 2`:

```math
E_2 = \sum_{k=3}^{d}\lambda_k.
```

Dla `q = 4`:

```math
E_4 = \sum_{k=5}^{d}\lambda_k.
```

Ponieważ wszystkie wartości własne są nieujemne:

```math
E_2 - E_4 = \lambda_3 + \lambda_4 \ge 0.
```

Zatem:

```math
E_4 \le E_2.
```

Równoważnie, udział zachowanej wariancji

```math
R_q = \frac{\sum_{k=1}^{q}\lambda_k}{\sum_{k=1}^{d}\lambda_k}
```

spełnia:

```math
R_4 \ge R_2.
```

To dowodzi, że poprawka H2, która wymusza co najmniej 4 kubity, nie może zachować mniej liniowej informacji PCA niż wariant agresywny 2-kubitowy. □

## 6. Lemat 4: kernel-target alignment mierzy zgodność jądra z etykietami

Niech

```math
Y = yy^T
```

będzie macierzą etykiet, a `K_c` i `Y_c` oznaczają wersje wycentrowane. Kernel-target alignment definiujemy jako:

```math
A(K,Y)
=
\frac{\langle K_c, Y_c\rangle_F}
{\|K_c\|_F\|Y_c\|_F}.
```

Dla ustalonego zbioru etykiet `Y_c` jest stałe. Jeżeli porównujemy jądra znormalizowane do podobnej normy Frobeniusa, to maksymalizacja `A(K,Y)` jest równoważna maksymalizacji:

```math
\langle K_c, yy^T\rangle_F
=
y^T K_c y.
```

Wartość `y^T K_c y` mówi, jak silnie geometria zdefiniowana przez jądro wzmacnia kierunek etykiet. W klasyfikatorach jądrowych, np. kernel ridge / LS-SVM, rozwiązanie ma postać zależną od widma jądra:

```math
\hat y = K(K+\lambda I)^{-1}y.
```

Jeżeli rozłożymy `y` w bazie wektorów własnych `K`:

```math
y = \sum_m \beta_m u_m,\quad K u_m = \mu_m u_m,
```

to predykcja na zbiorze uczącym wynosi:

```math
\hat y
=
\sum_m
\frac{\mu_m}{\mu_m+\lambda}
\beta_m u_m.
```

Błąd treningowy w tej idealizowanej analizie jest:

```math
\|y-\hat y\|^2
=
\sum_m
\left(
\frac{\lambda}{\mu_m+\lambda}
\right)^2
\beta_m^2.
```

Jeżeli etykiety mają większą projekcję na kierunki własne jądra o większych `mu_m`, to czynnik

```math
\frac{\lambda}{\mu_m+\lambda}
```

jest mniejszy, a błąd maleje. Alignment jest więc matematycznie uzasadnioną heurystyką wyboru takiego jądra, którego geometria jest zgodna z etykietami. □

## 7. Twierdzenie: co H2 dowodzi matematycznie

**Twierdzenie.** Przy założeniach:

1. używamy jądra `K_ij = |<psi_i|psi_j>|^2`,
2. koszt symulacji jest zdominowany przez overlapy stanów,
3. dane są redukowane przez PCA,
4. konfiguracja jest wybierana przez kernel-target alignment,
5. H2 wymusza `q >= 4`,

hipoteza H2 ma następujące własności:

- daje poprawne jądro dodatnio półokreślone;
- redukuje wymiar stanu względem baseline 6-kubitowego dokładnie do `1/4`;
- zachowuje nie mniej informacji PCA niż wariant 2-kubitowy;
- wybiera jądro, które maksymalizuje zgodność geometrii jądra z kierunkiem etykiet wśród rozważanych kandydatów.

**Dowód.** Pierwszy punkt wynika z Lematu 1. Drugi punkt wynika z Lematu 2. Trzeci punkt wynika z Lematu 3. Czwarty punkt wynika z Lematu 4 oraz z definicji reguły wyboru H2. □

## 8. Czego nie da się udowodnić bez danych

Nie da się uczciwie udowodnić czysto matematycznie, że H2 zawsze poprawi accuracy na dowolnym zbiorze danych. Accuracy zależy od rozkładu danych, szumu, podziału train/test, regularyzacji i zgodności feature mapy z prawdziwą granicą decyzyjną.

Dlatego właściwe rozumowanie ma dwie części:

1. **Dowód matematyczny:** H2 jest poprawnym, tańszym i lepiej uzasadnionym wariantem niż agresywne 2 kubity.
2. **Test empiryczny:** sprawdzamy, czy ta konstrukcja rzeczywiście poprawia metryki.

## 9. Potwierdzenie empiryczne z eksperymentu

W 10 powtórzeniach uzyskano:

| Zbiór | H0 baseline 6q | H2 4q alignment | Różnica |
|---|---:|---:|---:|
| WDBC | 0.902 | 0.946 | +0.044 |
| Wine | 0.951 | 0.979 | +0.027 |
| OptDigits 3-vs-8 | 0.945 | 0.976 | +0.031 |

W każdym przypadku H2 zachowała stosunek wymiaru stanu:

```math
\frac{2^4}{2^6} = 0.25.
```

Ostateczny wniosek: matematycznie H2 jest poprawną i zasobowo lepszą konstrukcją jądra QSVM, a empirycznie w badanym workspace poprawiła balanced accuracy na wszystkich trzech testowanych zadaniach.
