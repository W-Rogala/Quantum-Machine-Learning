# 1. Wspólny język matematyczny: stany, kanały, pomiar i błędy

## 1.1 Przestrzenie i konwencje

Dla $n$ kubitów przyjmujemy przestrzeń Hilberta $\mathcal H=(\mathbb C^2)^{\otimes n}$ o wymiarze $d=2^n$. Wektory są kolumnami, iloczyn skalarny jest antyliniowy w pierwszym argumencie, a symbol $\dagger$ oznacza sprzężenie hermitowskie. Prawe mnożenie działa jako pierwsze: $U_2U_1|\psi\rangle$ oznacza najpierw $U_1$, następnie $U_2$. Założenie to ma praktyczne znaczenie w porównaniu zapisu Trottera z kolejnością bramek.

```math
\langle u,v\rangle=u^\dagger v,\qquad
\|A\|_2=\sup_{\|v\|=1}\|Av\|,\qquad
\|A\|_F=\sqrt{\operatorname{Tr}(A^\dagger A)},\qquad
\|A\|_1=\operatorname{Tr}\sqrt{A^\dagger A}.
```

Norma operatorowa kontroluje najgorszy błąd działania na jednostkowy stan. Norma Frobeniusa jest naturalna przy dopasowaniu macierzy i naprawie PSD. Norma śladowa kontroluje rozróżnialność stanów. Tych norm nie wolno zamieniać bez czynnika zależnego od wymiaru. Dla macierzy $d\times d$ zachodzi $\|A\|_2\le\|A\|_F\le\sqrt d\|A\|_2$, co wynika z porównania maksimum i sumy kwadratów wartości singularnych.

Podstawowe pojęcia stanów, kanałów i pomiarów odpowiadają rozdziałom 2–3 podręcznika Watrousa. Poniższe dowody to samodzielne wyprowadzenia zastosowane do projektu; nie reprodukcja rozdziałów książki. [@watrous2018]

## 1.2 Dlaczego macierz gęstości jest właściwą reprezentacją

Stan czysty opisuje jednostkowy wektor $|\psi\rangle$, a jego operator ma postać $\rho=|\psi\rangle\langle\psi|$. Faza globalna $e^{i\alpha}$ nie zmienia $\rho$. Dla mieszaniny z prawdopodobieństwami $p_j\ge0$ i $\sum_jp_j=1$ mamy:

```math
\rho=\sum_jp_j|\psi_j\rangle\langle\psi_j|,
\qquad \rho=\rho^\dagger,\quad \rho\succeq0,\quad\operatorname{Tr}\rho=1.
```

**Dowód niezmienników.** Hermitowskość zachowuje się przy rzeczywistej kombinacji hermitowskich projektorów. Dla dowolnego $v$, $v^\dagger\rho v=\sum_jp_j|\langle\psi_j|v\rangle|^2\ge0$. Ślad projektora jednostkowego wynosi jeden, więc ślad sumy wynosi $\sum_jp_j=1$. W drugą stronę twierdzenie spektralne rozkłada dowolną hermitowską PSD macierz śladu jeden na takie projektory: wartości własne pełnią rolę $p_j$.

Ta reprezentacja jest konieczna w QRC po resecie podukładu i w modelach szumu. Statevector może opisywać trajektorię czystą, ale po częściowym śladzie stan pozostającego rejestru bywa mieszany. Przejście do pojedynczego wektora bez dodatkowego losowania lub oczyszczania zmieniłoby model.

## 1.3 Unitarność ewolucji i bramki Pauliego

Hermitowski Hamiltonian $H$ ma rzeczywiste wartości własne. Przy jednostkach $\hbar=1$ ewolucja przez czas $t$ wynosi $U(t)=\exp(-itH)$. Ze spektralnego rozkładu $H=V\Lambda V^\dagger$ wynika $U=V\operatorname{diag}(e^{-it\lambda_j})V^\dagger$ i $U^\dagger U=I$. Ślad, dodatniość i wartości własne $\rho$ zachowują się w $\rho\mapsto U\rho U^\dagger$.

Dla hermitowskiego iloczynu Paulich $P$ z $P^2=I$ dzielimy szereg wykładniczy na potęgi parzyste i nieparzyste:

```math
e^{-i\theta P/2}
=\sum_{k\ge0}\frac{(-i\theta/2)^{2k}}{(2k)!}I
+\sum_{k\ge0}\frac{(-i\theta/2)^{2k+1}}{(2k+1)!}P
=\cos(\theta/2)I-i\sin(\theta/2)P.
```

To wyprowadzenie uzasadnia rzeczywisty kąt $2tJ$ w bramce RZZ reprezentującej $\exp(-itJ Z\otimes Z)$. Pominięcie czynnika dwa zmienia czas ewolucji; nie jest niewinną konwencją. Dla stanów $|00\rangle$, $|11\rangle$ wartość $Z\otimes Z$ wynosi $+1$, a dla $|01\rangle$, $|10\rangle$ wynosi $-1$, więc fazy wynoszą odpowiednio $e^{-itJ}$ i $e^{itJ}$.

## 1.4 Kanał CPTP: konstrukcja i znaczenie

Liniowe odwzorowanie E macierzy jest kanałem CPTP, jeśli jest całkowicie dodatnie i zachowuje ślad. W skończonym wymiarze przedstawienie Krausa daje konstrukcję:

```math
\mathcal E(\rho)=\sum_a K_a\rho K_a^\dagger,
\qquad \sum_aK_a^\dagger K_a=I.
```

**Dowód.** Po dołączeniu dowolnego ancilla dodatnia macierz $X$ przechodzi w $\sum_a(K_a\otimes I)X(K_a^\dagger\otimes I)$, sumę dodatnich macierzy. Ślad obrazu jest $\operatorname{Tr}(\sum_aK_a^\dagger K_a\rho)=\operatorname{Tr}\rho$. Unitarna ewolucja jest szczególnym przypadkiem jednego operatora $K=U$. Złożenie dwóch kanałów ma operatory $L_bK_a$ i ponownie spełnia sumę kompletności.

Dlaczego to istotne: pooling QCNN i reset QRC usuwają informację przez częściowy ślad. Ich całe działanie jest kanałem, choć pojedyncze bramki przed śladem mogą być unitarne. Odwracalność bramek nie czyni odwracalnym usunięcia podukładu. Przykład dwóch różnych stanów |0⟩⟨0|⊗σ i |1⟩⟨1|⊗σ daje po usunięciu pierwszego kubitu ten sam σ.

## 1.5 Reguła Borna i przejście do cech

Pomiar POVM jest zbiorem M_a≥0 z ΣM_a=I. Wynik a ma prawdopodobieństwo p_a=Tr(M_aρ). Dodatniość p_a wynika z Tr(M_a^{1/2}ρM_a^{1/2})≥0, a normalizacja z liniowości śladu. Dla obserwabli O=Σa aΠ_a jej średnia wynosi Tr(Oρ).

Dla pomiaru Pauliego wynik Z jest ±1. Jeżeli p=P(Z=+1), to μ=2p−1. Z S niezależnych odczytów estimator μ̂=S^{-1}ΣZ_s jest nieobciążony, a:

```math
\operatorname{Var}(\widehat\mu)=\frac{1-\mu^2}{S}\le\frac1S.
```

**Dowód.** E[Z²]=1, więc VarZ=1−μ². Niezależność shots powoduje sumowanie wariancji i podział przez S². Jeśli dwa Pauli P,Q mierzy się z tego samego bitstringu we wspólnej bazie, Cov(μ̂_P,μ̂_Q)=(E[PQ]−E[P]E[Q])/S. Losowanie niezależnych binomiali dla każdej cechy usuwa tę kowariancję i opisuje inny eksperyment.

To przejście ρ↦(Tr O₁ρ,…,Tr O_mρ) jest liniowe w operatorze ρ. Zależność od danych x może być nieliniowa, bo x↦ρ(x) jest nieliniowa. Jest to klucz do rozumienia modelu hybrydowego: klasyczna głowica liniowa może działać na nieliniowej reprezentacji kwantowej.

## 1.6 Granice błędu: od jednostki do predykcji

Dla dwóch ewolucji U,V i stanu ρ korzystamy z rozbicia:

```math
U\rho U^\dagger-V\rho V^\dagger
=(U-V)\rho U^\dagger+V\rho(U^\dagger-V^\dagger).
```

Nierówność $\|AXB\|_1\le\|A\|_2\|X\|_1\|B\|_2$ i $\|\rho\|_1=1$ dają $\|U\rho U^\dagger-V\rho V^\dagger\|_1\le2\|U-V\|_2$. Dla $\|O\|_2\le1$:

```math
|\operatorname{Tr}[O(\rho-\sigma)]|
\le\|O\|_2\|\rho-\sigma\|_1
=2\|O\|_2D(\rho,\sigma),\qquad
D(\rho,\sigma)=\tfrac12\|\rho-\sigma\|_1.
```

Jeśli cech jest $m$ i każda obserwabla ma normę $\le1$, to $\|f(\rho)-f(\sigma)\|_2\le2\sqrt m D$. Dla ustalonej głowicy liniowej $w$ mamy $|w^T\Delta f|\le\|w\|_2\|\Delta f\|_2$. Łącznie błąd jednostki, błąd stanu i błąd predykcji mają ciągłe połączenie przez jawne stałe. Nie ma z tego monotoniczności jakości po ponownym uczeniu głowicy: wówczas zmienia się także $w$.

## 1.7 Granica dokładności pomiarowej i alokacja shots

Dla estymacji średniej zmiennej w [−1,1] nierówność Hoeffdinga prowadzi do P(|μ̂−μ|≥ε)≤2exp(−Sε²/2). Dla m obserwabli union bound daje prawdopodobieństwo maksymalnego błędu >ε nie większe niż 2m exp(−Sε²/2), bez wymogu niezależności między obserwablami. Wystarczy S≥2log(2m/δ)/ε², aby uzyskać kontrolę 1−δ. Stałe różnią się od estimatorów Bernoulliego w [0,1].

Jeżeli wynik liniowy ma niezależnie mierzone składowe z wariancjami σ_j²/S_j, jego wariancja jest Σw_j²σ_j²/S_j. Przy kosztach c_j shots i budżecie Σc_jS_j=B mnożnik Lagrange'a daje S_j∝|w_j|σ_j/√c_j. To konstrukcja warunkowa: wymaga znajomości wag, wariancji i niezależnych grup. Nie należy zastępować nią zarejestrowanej alokacji po obejrzeniu wyników testu. Źródło nierówności koncentracji: [@hoeffding1963].

## 1.8 Granice tej formalizacji

Skończony wymiar pozwala bezpiecznie stosować szeregi macierzowe i normy operatorowe. W fotonice pełna przestrzeń Focka jest nieskończenie wymiarowa: operatory liczby i kwadratur są nieograniczone. Dowodu z bounded Hamiltonians nie przenosi się bez dodatkowego obcięcia lub warunków domenowych. Symulacja z cutoffem jest skończonym modelem; jej zgodność z pełnym modelem wymaga osobnej kontroli masy poza cutoffem i obserwabli.
