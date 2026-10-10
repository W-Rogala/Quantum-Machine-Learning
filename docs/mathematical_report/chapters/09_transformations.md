# 9. Graf zależności i płynne przejścia matematyczne

## 9.1 Jeden łańcuch z trzema realizacjami

Wspólny pipeline ma postać:

```math
x\ \xrightarrow{T_{\rm train}}\ z\ \xrightarrow{\mathcal E_z}\rho_z
\ \xrightarrow{\mathcal M}\ f(z)
\ \xrightarrow{\kappa}\ K
\ \xrightarrow{\lambda,\,\mathrm{fit}}\ \widehat y.
```

T_train jest klasycznym preprocessingiem dopasowanym na train. E_z przygotowuje lub aktualizuje stan. M daje oczekiwania albo rozkład pomiarów. κ tworzy podobieństwo. Fit wyznacza głowicę. Dla reservoiru x oznacza historię u_{≤t}, a E jest złożeniem kanałów. Dla fotoniki M jest PNR/threshold, a f to histogram lub momenty. Dla fidelity κ działa bezpośrednio na dwóch stanach przez ślad iloczynu.

Strzałki nie są równoważnościami. PCA może usuwać kierunki, pomiar traci część informacji stanu, a klasyfikacja redukuje wynik do etykiety. Gdy odwzorowanie jest wiele-do-jednego, nie istnieje ogólna transformacja odwrotna. Dowód: gdy F(x)=F(z) dla x≠z, jedna wartość obrazu nie może zostać przypisana jednocześnie obu oryginałom przez funkcję odwrotną.

## 9.2 Krawędź stan → cechy → kernel

Pełny zestaw Paulich daje ρ↔r z jednoznaczną rekonstrukcją ρ=d^{-1}Σr_aP_a. Z niego k_HS=d^{-1}r_xᵀr_z. Redukcja r→r_A usuwa współrzędne. Liniowy projected kernel to r_A(x)ᵀr_A(z); projected RBF stosuje dodatkową mapę tensorową z rozdziału 2. Ten ciąg dokładnie pokazuje, które przejście jest tożsamością i w którym miejscu pojawia się modelowe uproszczenie.

## 9.3 Krawędź reservoir → ridge → kernel historii

Niech f_t=F(u₀,…,u_t). Uczenie liniowe w cechach ma w=Xᵀ(XXᵀ+λI)^{-1}y, więc:

```math
\widehat y(u_{\le t})=\sum_i\alpha_i
\underbrace{f(u_{\le t})^Tf(u_{\le i})}_{k_{\rm history}(u_{\le t},u_{\le i})},
\quad\alpha=(K+\lambda I)^{-1}y.
```

W pokazanym wzorze $X$, $y$ i cechy nowego wejścia są wycentrowane statystykami treningowymi, a wyraz wolny odtworzony osobno jako $b=\bar y-\bar f^Tw$. Alternatywnie wzór dotyczy modelu bez interceptu. To dokładna równoważność primal–dual przy tej samej obsłudze interceptu, preprocessingu i λ. Nie utożsamia k_history z kernelem Hamiltonowskim pojedynczych tabularnych próbek. Reservoir zachowuje zależność od historii; klasyczny model na oknie opóźnień ma inną mapę historii, choć podobny readout.

## 9.4 Krawędź dynamika → błąd cech → stabilność rozwiązania

Łańcuch zależności formalnych to ||U−Ũ||₂≤a ⇒ D(ρ,ρ̃)≤a ⇒ ||Δf||₂≤2√m a. Dla liniowego kernela k=fᵀg, przy ||f||,||g||≤R i perturbacjach ≤δ:

```math
|\widetilde k-k|
\le|\Delta f^Tg|+|f^T\Delta g|+|\Delta f^T\Delta g|
\le2R\delta+\delta^2.
```

Jeżeli każdy z N² elementów macierzy zmienia się o ≤b, ||ΔK||₂≤||ΔK||F≤Nb. Granica ridge z rozdziału 2 wymaga Nb<λ. To oszacowanie zachowawcze, ale pokazuje wszystkie czynniki: liczbę próbek, liczbę cech, dokładność ewolucji i regularizację. Przy stabilnym reservoirze a zastępuje się granicą błędu trajektorii; bez kontrakcji kumulacja może rosnąć z czasem.

## 9.5 Krawędź histogram → coarse graining → utrata rozróżnialności

Niech L będzie macierzą agregacji koszyków, z nieujemnymi wpisami i sumą kolumn jeden. q=Lp jest prawidłowym rozkładem. Dla dwóch rozkładów:

```math
\|L(p-r)\|_1
\le\sum_a\sum_bL_{ab}|p_b-r_b|
=\|p-r\|_1.
```

Agregacja event/orbit i progowanie nie zwiększają total variation distance, ale mogą ją zmniejszyć. Mniejszy alfabet ogranicza wariancję estymacji rzadkich binów, jednocześnie usuwając rozróżniające informacje. To formalny kompromis bias–variance, którego optymalny punkt wymaga danych. Postselekcja nie jest tym samym liniowym coarse graining: p_Ω/Σ_Ωp jest nieliniowa i nie ma powyższej gwarancji dla całego pipeline'u.

## 9.6 Krawędź QSVT → HHL i qPCA: właściwy typ relacji

HHL przygotowuje stan proporcjonalny A^{-1}b przy wymaganiach dostępu i uwarunkowania. QSVT realizuje odpowiednią aproksymację funkcji odwrotności singular values w zakodowanym bloku, przez co może służyć do nowoczesnego solvera. To relacja „może realizować cel liniowo-algebraiczny”, nie stwierdzenie, że historyczny obwód HHL jest identyczny z QSVT.

qPCA zaczyna od macierzy gęstości, której eigenvalues są powiązane z kowariancją albo Gram po jawnej normalizacji danych. Jeśli A jest macierzą wierszy danych, niezerowe spectra AA† i A†A są jednakowe; dowód wynika z SVD A=UΣV†. HHL wykorzystuje odwrotność, qPCA identyfikuje składowe spektralne. Wspólny aparat spektralny nie oznacza tego samego celu.

## 9.7 Krawędź QAOA → Trotter → VQE

QAOA stosuje naprzemienne exp(−iβ_lH_B)exp(−iγ_lH_C), gdzie kąty są parametrami optymalizacji. Trotter przybliża ustaloną ewolucję exp[−it(H_A+H_B)] przez ustalony harmonogram małych kroków. Wybrane kąty γ=β=t/r mogą tworzyć formułę produktową, ale ogólne kąty QAOA nie służą aproksymacji jednego z góry ustalonego czasu.

VQE może używać ansatzu takiej postaci, lecz uczy przez energię H_target. Klasyfikator wariacyjny używa cross-entropy lub podobnej straty. Przejście między nimi polega na współdzieleniu obwodu i aparatu gradientów, a nie na identyczności zadań. Kod testujący ekspresywność SCAR dostarcza kandydacki ansatz, nie minimum energii.

## 9.8 Dlaczego wszystkie relacje mają jawny typ

Interaktywny graf matematyczny ma typy: „definiuje”, „dokładna transformacja”, „projekcja”, „warunkowe oszacowanie”, „podprogram”, „wspólny aparat” i „hipoteza empiryczna”. Kliknięcie krawędzi pokazuje wzór, warunki i właściwy rozdział. Osobny historyczny graf projektu zachowuje relacje organizacyjne i podobieństwa atlasu; ich wagi nie są prawdopodobieństwami ani miarą siły dowodu.

Krawędzie typed pozwalają odróżnić: PSD gwarantuje dopuszczalność standardowego kernela; alignment wskazuje dopasowanie na train; walidacja wybiera model; holdout ocenia konkretną generalizację. Żaden pojedynczy przeskok nie daje uniwersalnej przewagi kwantowej. Złożenie poprawnych krawędzi wymaga zgodności założeń po obu stronach, zwłaszcza normalizacji, tego samego splitu i dokładnej definicji wyniku.
