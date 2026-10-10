# 2. Od reprezentacji do uczenia: PSD, RKHS, ridge i alignment

## 2.1 Wspólna konstrukcja dla trzech gałęzi

Niech $\Phi:\mathcal X\to\mathcal V$ będzie odwzorowaniem do przestrzeni Hilberta. Definiujemy $k(x,z)=\langle\Phi(x),\Phi(z)\rangle$. Dla dowolnych próbek $x_1,\ldots,x_N$ i $c\in\mathbb C^N$:

```math
c^\dagger Kc
=\sum_{i,j}\overline{c_i}c_j\langle\Phi(x_i),\Phi(x_j)\rangle
=\left\|\sum_jc_j\Phi(x_j)\right\|^2\ge0.
```

To pełny dowód dodatniej półokreśloności macierzy Grama. W jądrze fidelity Φ=vecρ i k=Tr(ρ_xρ_z); dla stanów czystych równa się |⟨ψ_x|ψ_z⟩|². W fotonice Φ może być histogramem p_x lub zestawem funkcji charakterystycznych. W rezerwuarze Φ(u_{≤t}) jest wektorem oczekiwań po całej historii. Wszystkie konstrukcje prowadzą do PSD, ale opisują inne informacje.

Przestrzeń RKHS można zbudować bez postulowania przewagi sprzętowej. W dalszym uczeniu korzystamy z rzeczywistego kernela; zaczynamy od skończonych sum $f=\sum_i a_i k(x_i,\cdot)$. Iloczyn $\langle f,g\rangle=\sum_{i,j}a_i b_jk(x_i,z_j)$ jest półokreślony. Iloraz przez elementy normy zero, a następnie uzupełnienie dają przestrzeń Hilberta. Własność reprodukująca $\langle f,k(x,\cdot)\rangle=f(x)$ wynika bezpośrednio z definicji. Dla zespolonego kernela stosuje się sprzężenie pierwszego współczynnika i odpowiednią orientację sekcji kernela; nie wolno bez zmiany tej konwencji przenosić rzeczywistego wzoru. Omawiana konstrukcja odpowiada standardowej teorii kerneli; odniesienie akademickie: [@rasmussen2006].

## 2.2 Rozkład Pauliego tworzy most fidelity–projected

Iloczyny Paulich $P_a$, $a=0,\ldots,4^n-1$, są ortogonalne: $\operatorname{Tr}(P_aP_b)=d\delta_{ab}$, $P_0=I$. Każdy operator stanu ma więc rozwinięcie:

```math
\rho=\frac1d\sum_a r_aP_a,\qquad r_a=\operatorname{Tr}(P_a\rho),\qquad
\operatorname{Tr}(\rho_x\rho_z)=\frac1d\sum_a r_a(x)r_a(z).
```

**Dowód.** Rozwijamy ρ w ortogonalnej bazie macierzy i wyznaczamy współczynniki przez ślad. Po pomnożeniu dwóch rozwinięć podwójna suma redukuje się przez δ_ab. Dla czystych stanów wynik to fidelity; dla mieszanych jest iloczynem Hilberta–Schmidta, a nie ogólną fidelity Uhlmanna.

Projected kernel zachowuje podzbiór obserwabli. Jeżeli f(x)=(r_a(x))_{a∈A}, to liniowe jądro jest iloczynem tylko tych współrzędnych. Pełne fidelity odpowiada wszystkim współrzędnym z czynnikiem 1/d. Usunięcie współrzędnych jest projekcją w przestrzeni operatorów; późniejsze zastosowanie RBF jest kolejną, odrębną mapą. Nie jest dokładnym zachowaniem pełnego fidelity.

Koszt tomografii wszystkich 4^n współczynników może być wykładniczy. Lokalny projected kernel wybiera mniej obserwabli, aby ograniczyć zasoby i wprowadzić bias reprezentacji. Własność PSD przeżywa to ograniczenie; informacja rozróżniająca stany nie musi. [@huang2021], [@schuld2021]

## 2.3 Gaussian RBF jest PSD: dowód przez jawne cechy

Dla $f,g\in\mathbb R^m$ i $\gamma\ge0$:

```math
e^{-\gamma\|f-g\|^2}
=e^{-\gamma\|f\|^2}e^{-\gamma\|g\|^2}
\sum_{k=0}^{\infty}\frac{(2\gamma)^k}{k!}\langle f^{\otimes k},g^{\otimes k}\rangle.
```

Każdy składnik jest dodatnim iloczynem cech tensorowych. Definiujemy $\Phi_{\rm RBF}(f)$ jako sumę prostą $e^{-\gamma\|f\|^2}\sqrt{(2\gamma)^k/k!}\,f^{\otimes k}$. Jej norma kwadratowa wynosi $e^{-2\gamma\|f\|^2}e^{2\gamma\|f\|^2}=1$, więc konstrukcja ma sens w przestrzeni Hilberta. Iloczyn tych cech daje powyższy szereg i kończy dowód.

To uzasadnia implementowanie RBF na cechach kwantowych, histogramach i danych klasycznych. „Kwantowość” dotyczy pochodzenia f, a PSD wynika tu ze standardowej konstrukcji klasycznej. Współczynnik γ ma wymiar odwrotności kwadratu jednostki cech. Standaryzacja f zmienia jego znaczenie i musi być dopasowana na treningu.

## 2.4 Ridge w cechach: skąd bierze się rozwiązanie

Dla $X\in\mathbb R^{N\times m}$, $y\in\mathbb R^N$ i $\lambda>0$ minimalizujemy $L(w)=\|y-Xw\|^2+\lambda\|w\|^2$. Gradient to $-2X^T(y-Xw)+2\lambda w$. Hessian $2(X^TX+\lambda I)$ jest dodatnio określony, dlatego istnieje jedno minimum:

```math
w=(X^TX+\lambda I)^{-1}X^Ty
=X^T(XX^T+\lambda I)^{-1}y.
```

**Dowód drugiej równości.** $(X^TX+\lambda I)X^T=X^T(XX^T+\lambda I)$. Obie macierze przesuwane są odwracalne, więc możemy pomnożyć przez odwrotności. Predykcja $f(x)^Tw$ przechodzi w $k(x,X)(K+\lambda I)^{-1}y$. Tak QRC z liniowym readoutem staje się klasyczną metodą jądrową na historii wejścia, a kernel Hamiltonowski staje się odpowiednikiem ridge na własnych cechach.

Jeżeli cel definiuje średnią N^{-1}||y−Xw||², regularizacja prowadzi do XᵀX+NλI. Stąd ta sama liczba λ w dwóch implementacjach nie oznacza tej samej siły kary. Intercept bez kary usuwa się przez centrowanie X,y; po dopasowaniu b=ȳ−x̄ᵀw. Centrowanie musi być oparte na train i stosowane bez refitu na test.

## 2.5 Twierdzenie o reprezentacji: dlaczego rozwiązanie leży w span

W RKHS rozważamy $\|y-f(X)\|^2+\lambda\|f\|^2$. Rozkład $f=f_\parallel+f_\perp$ względem $\operatorname{span}\{k(x_i,\cdot)\}$ daje $f_\perp(x_i)=\langle f_\perp,k(x_i,\cdot)\rangle=0$. Strata danych jest ta sama dla $f$ i $f_\parallel$, a norma $\|f\|^2=\|f_\parallel\|^2+\|f_\perp\|^2$. Ponieważ $\lambda>0$, minimum ma $f_\perp=0$.

Zatem f=Σα_i k(x_i,·). Dla PSD K można przyjąć α=(K+λI)^{-1}y, co prowadzi do powyższej predykcji; przy singular K współczynniki reprezentacji funkcji mogą nie być jednoznaczne, lecz funkcja minimum jest jednoznaczna. Dowód span nie stosuje się do macierzy indefinite udającej kernel: brak wtedy odpowiedniego dodatniego iloczynu RKHS.

## 2.6 LS-SVM, SVM i ridge: różne cele

W binarnej LS-SVM minimalizuje się ½||w||²+(γ/2)Σe_i² przy y_i(w·Φ_i+b)=1−e_i. Lagrangian z mnożnikami α_i daje w=Σα_i y_iΦ_i, Σα_i y_i=0 i e_i=α_i/γ. Po podstawieniu:

```math
\begin{bmatrix}0&y^T\\y&YKY+\gamma^{-1}I\end{bmatrix}
\begin{bmatrix}b\\\alpha\end{bmatrix}
=\begin{bmatrix}0\\\mathbf1\end{bmatrix},\qquad Y=\operatorname{diag}(y).
```

Klasyczny SVM z hinge loss ma inne ograniczenia i inną dualną optymalizację. Wieloklasowe dopasowanie A=(K+λI)^{-1}T i argmax wyniku jest kernel ridge classification, nawet gdy skrypt historyczny używa nazwy QSVM. Odnośniki do obu konkretnych wariantów: [[code:experiments/legacy/qml_hypothesis_experiment.py#L237-L256]] oraz [[code:experiments/legacy/qsvm_hypothesis_experiment.py#L189-L203]].

## 2.7 Alignment: geometria, nie gwarancja jakości

Dla C=I−11ᵀ/N mamy C=Cᵀ=C² i centrowane macierze K_c=CKC, T_c=CTC. Alignment to cosinus Frobeniusa:

```math
A(K,T)=\frac{\langle K_c,T_c\rangle_F}{\|K_c\|_F\|T_c\|_F}.
```

Cauchy–Schwarz daje |A|≤1. Dla PSD obu macierzy licznik Tr(K_cT_c)≥0, więc A∈[0,1], o ile normy nie są zerowe. Gdy wszystkie etykiety są jednakowe, centrowany target może być zerowy; wskaźnik jest matematycznie niezdefiniowany, nawet jeśli kod zwraca kontrolne zero.

Dla targetu yyᵀ licznik yᵀK_cy jest kwadratową formą. Jeżeli norma K_c jest dokładnie stała w rodzinie, maksymalizacja A odpowiada maksymalizacji licznika. „Podobne” normy nie dają tej równoważności. Teoria centered alignment wymaga szerszych warunków przy wnioskowaniu o predyktorach. [@cortes2012]

## 2.8 Wrażliwość regularizowanego rozwiązania

Niech $K\succeq0$, $\widetilde K=K+E$ z hermitowską perturbacją $E$ i $\|E\|_2=\varepsilon<\lambda$. Wtedy najmniejsza wartość własna $\widetilde K+\lambda I$ wynosi co najmniej $\lambda-\varepsilon$. Tożsamość resolwenty daje:

```math
(\widetilde K+\lambda I)^{-1}-(K+\lambda I)^{-1}
=-(\widetilde K+\lambda I)^{-1}E(K+\lambda I)^{-1},
\qquad \|\widetilde\alpha-\alpha\|_2
\le\frac{\varepsilon\|y\|_2}{\lambda(\lambda-\varepsilon)}.
```

Jeśli ||k̃_x−k_x||≤δ i ||k_x||≤M, różnica predykcji wynosi najwyżej δ||y||/(λ−ε)+Mε||y||/[λ(λ−ε)]. Dowód polega na dodaniu i odjęciu k_xᵀα̃ oraz zastosowaniu powyższej normy. Wskazuje, dlaczego mała regularizacja może wzmacniać shot noise. Nie dowodzi optymalności jednego λ dla wszystkich danych; dobór λ pozostaje walidacyjny.
