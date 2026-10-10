# 0. Zakres, sposób czytania i status dowodów

Raport matematyczny projektu QML łączy formalne wyprowadzenia, sprawdzalne odwołania do kodu i analizę zachowanych wyników. Opracowanie powstało 5 października 2026; oznacza datę inspekcji materiału, a nie datę wykonania dawnych eksperymentów. Nie wykonano nowych treningów ani zadań QPU. Nowe obliczenia weryfikacyjne to małe przykłady algebraiczne, kontrprzykłady i kontrole integralności dokumentu. Ich rola jest inna niż rola benchmarku.

Korekta redakcyjna i techniczna: **9 października 2026**. Doprecyzowano kierunki zerowe QSVT, intercept ridge i nośnik polityki QRL, sprawdzono nawigację i uzupełniono eksport GitHub. Daty oraz wyniki archiwalnych eksperymentów pozostają bez zmian.

## 0.1 Co stanowi przedmiot oceny

Trzy implementowane gałęzie to jądra Hamiltonowskie, rezerwuary kwantowe i jądra fotoniczne. Odrębny materiał obejmuje historyczne klasyfikatory QSVM, ansatze SCAR, strojenie HPO, integracje sprzętowe oraz atlas dziewiętnastu rodzin algorytmów. Atlas jest dokumentacją koncepcji: obecność karty HHL, QSVT czy QPCA nie oznacza implementacji pełnego algorytmu. W każdym przypadku wskazujemy, gdzie kończy się matematyczna definicja, a zaczyna rzeczywisty kod.

Stan zachowanych danych obejmuje m.in. benchmark Hamiltonowski, eksperymenty spektralne QRC, badania pamięci H3 i szumu oraz wcześniejsze doświadczenia SCAR. Różne daty i jednostki replikacji nie pozwalają nadać wszystkim wynikom jednej wspólnej daty eksperymentu. Każdy wykres podaje plik źródłowy, poziom agregacji i ograniczenie interpretacji.

## 0.2 Pięć klas stwierdzeń

**Twierdzenie matematyczne** ma jednoznaczne założenia i dowód. Przykład: macierz iloczynów Hilberta–Schmidta stanów jest PSD. Dowód obowiązuje dla dowolnego skończonego zbioru stanów; nie jest statystycznym potwierdzeniem przewagi klasyfikatora.

**Twierdzenie warunkowe** wymaga założenia, którego projekt nie wykazał. Przykład: geometryczna granica błędu obcięcia historii zakłada wspólny współczynnik kontrakcji mniejszy od jedności. Sam reset jednego kubitu nie wystarcza, aby takie założenie uzyskać.

**Hipoteza empiryczna** dotyczy jakości, kosztu lub mechanizmu w określonej populacji eksperymentów. Przykład: wybrany schemat Trottera obniża NRMSE o przynajmniej 2%. Wymaga niezależnych jednostek replikacji i procedury selekcji zamrożonej przed testem.

**Diagnostyka numeryczna** potwierdza określoną tożsamość albo niezmiennik dla sprawdzonych przypadków. Mały błąd unitarności macierzy jest kontrolą implementacji. Nie zastępuje dowodu dla wszystkich parametrów ani badania błędów urządzenia.

**Projekt lub materiał teoretyczny** opisuje rodzinę metod bez uruchomionej implementacji. Jej przewagi z literatury obowiązują przy założeniach tej literatury; nie przechodzą automatycznie na lokalny projekt.

## 0.3 Dlaczego oznaczenia hipotez muszą mieć przestrzeń nazw

W projekcie symbol H2 oznacza kilka różnych pytań: ograniczenie liczby kubitów w historycznym QSVM, walidacyjny wybór schematu w QRC, spektralną możliwość poprawy predykcji, a w kolejnych protokołach inne kontrasty. Raport stosuje identyfikatory LEG-H2, QRC-H1–H5, SPEC-H1/H2 i HK-V3. Zgodność nazw nie jest zależnością logiczną.

Dowody autorskie w raporcie są rekonstrukcjami matematycznymi standardowych konstrukcji lub analizą lokalnego kodu. Nie oznaczają roszczenia o nowe odkrycie. Przy źródłach wskazujemy zakres wsparcia: definicja, kontekst, twierdzenie lub metoda analizy. Literatura nie potwierdza lokalnej jakości modelu bez danych.

## 0.4 Jak sprawdzać argument

Czytanie pojedynczego zagadnienia zaczyna się od definicji dziedziny i założeń. Następnie przechodzi przez wyprowadzenie, wniosek i ograniczenia. Odnośnik „kod” otwiera lokalnie zapisaną wersję pliku z numerami linii oraz wyróżnieniem konkretnego fragmentu. Hash SHA-256 określa, do której wersji odnoszą się linie. Kod w raporcie pozostaje dostępny po przeniesieniu samego pliku HTML na inny komputer.

Wzory są renderowane lokalnie. Skróty i pojęcia w tekście mają krótką definicję po najechaniu lub skupieniu klawiaturą; kliknięcie prowadzi do rozwiniętego słownika. Wzory używają notacji z kolejnego rozdziału. Symbole wyjaśnia się bezpośrednio przy ich pierwszym zastosowaniu, gdy mają znaczenie zależne od rozdziału.

Bibliografia w HTML jest dostępna offline, podobnie jak metadane w BibTeX, JSON i SQLite. Kliknięcie DOI lub adresu publikacji otwiera źródło zewnętrzne i wymaga internetu. Pakiet nie zawiera nieuprawnionych kopii podręczników. Odnośniki do rozdziałów i tematów wewnątrz raportu działają bez internetu.

## 0.5 Najważniejszy wniosek metodologiczny

Formalna poprawność reprezentacji, poprawność algorytmu numerycznego i przewaga predykcyjna są trzema osobnymi tezami. Projekt ma poprawne podstawy wielu konstrukcji i wartościowe kontrole, ale część zapisów zbyt silnie przechodzi między tymi poziomami. Raport pokaże dokładne przejścia, których można dowieść, oraz pytania wymagające nowych prób. Zapisane wyniki nie dowodzą uniwersalnej przewagi kwantowej ani zakończenia wszystkich zaplanowanych hipotez.

Poprawki opisane w tej monografii są propozycjami dla kolejnej wersji naukowej. Nie zmieniają archiwalnych eksperymentów ani nie przypisują im retrospektywnie nowego protokołu.


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


# 3. Kernele Hamiltonowskie: dynamika, estymacja i granice wnioskowania

Rozdział rekonstruuje matematyczny model gałęzi `hamiltonian_kernel` oraz oddziela jego własności formalne od zaobserwowanych wyników klasyfikacji. Podstawą są aktualne implementacje `core.py`, `estimation.py`, `learning.py`, `protocol.py`, `publication_benchmark.py`, `trotter_scaling_v3.py` i moduły, które one wywołują. Uwzględniono ustalenia `docs/audit/hamiltonian_review.md` oraz diagnostyki `docs/audit/review_checks.json`. Nie przeprowadzano nowych eksperymentów QPU ani ponownego pełnego uczenia modeli. Liczby z wcześniejszych artefaktów są oznaczone jako wyniki zapisane, a nie jako wyniki nowej replikacji.

Literatura dotycząca kwantowych map cech i kerneli dostarcza kontekstu konstrukcji [@havlicek2019] [@schuld2021]. W tym projekcie po przygotowaniu kernela uczenie pozostaje klasycznym rozwiązaniem układu liniowego. Samo użycie przestrzeni stanów o wymiarze $2^n$ nie dowodzi przewagi obliczeniowej ani predykcyjnej.

Wszystkie dowody oznaczone jako **wyprowadzenie własne** są samodzielnymi wyprowadzeniami dla modelu z repozytorium. Nie są deklaracją nowych twierdzeń naukowych. Literatura wskazuje szerszy kontekst; dowody nie zastępują warunków regularności, niezależności ani poprawności modelu szumu.

## 3.1. Przestrzeń stanów i dokładna definicja kodowania

Niech $n\in\mathbb N$, $n\geq1$, a $\mathcal H_n=(\mathbb C^2)^{\otimes n}$. Normę operatorową oznaczamy przez $\|\cdot\|$, normę Frobeniusa przez $\|\cdot\|_F$, a sprzężenie hermitowskie przez $\dagger$. Macierze Pauliego to

$$
X=\begin{pmatrix}0&1\\1&0\end{pmatrix},\qquad
Y=\begin{pmatrix}0&-i\\i&0\end{pmatrix},\qquad
Z=\begin{pmatrix}1&0\\0&-1\end{pmatrix}.
$$

Symbol $Z_j$ oznacza $Z$ na kubicie $j$ i identyczność na pozostałych. Implementacja numeruje kubit $0$ jako najmniej znaczący bit indeksu stanu. Dlatego dla indeksu bazowego $b$ wartość własna $Z_j$ wynosi $1-2b_j$. Funkcje `z_eigenvalues` i `plus_state` realizują tę konwencję oraz stan początkowy

$$
|+_n\rangle=|+\rangle^{\otimes n}
=2^{-n/2}\sum_{b=0}^{2^n-1}|b\rangle.
$$

Odwołanie do implementacji: [[code:hamiltonian_kernel/core.py#L49-L59]].

Dla przetworzonego wektora $x\in\mathbb R^n$ i nieskierowanego grafu oddziaływań $G=(V,E)$ podstawowy Hamiltonian ma postać

$$
H(x)=A(x)+B,\qquad
A(x)=\sum_{j=0}^{n-1}x_jZ_j+J\sum_{\{j,k\}\in E}Z_jZ_k,
\qquad B=g\sum_{j=0}^{n-1}X_j,
$$

gdzie $J,g\in\mathbb R$. Graf jest łańcuchem, pierścieniem albo grafem pełnym. Dla małego $n$ nazwy topologii mogą określać ten sam graf; przykładowo przy $n=2$ wszystkie trzy warianty mają jedną krawędź. Nie są wówczas trzema różnymi strukturami oddziaływań. Definicje znajdują się w [[code:hamiltonian_kernel/core.py#L37-L46]] i [[code:hamiltonian_kernel/core.py#L62-L74]].

Preprocessing jest częścią modelu. W benchmarku publikacyjnym obejmuje standaryzację, PCA i skalowanie do $[-1,1]$, dopasowane na odpowiednim zbiorze treningowym; brakujące współrzędne są uzupełniane zerami. Oznacza to, że wejście Hamiltonianu jest obrazem surowych danych przez transformację zależną od foldu. Nie wolno traktować analiz PCA i skalowania jako niezależnych od definicji kernela. Implementacja: [[code:hamiltonian_kernel/publication_benchmark.py#L54-L90]].

**Twierdzenie 3.1 — poprawność ewolucji, wyprowadzenie własne.** Dla skończonego $n$, rzeczywistych $x,J,g$ i rzeczywistego $t$ operator $H(x)$ jest hermitowski, a $U_x(t)=e^{-itH(x)}$ unitarny. W szczególności $|\psi_x\rangle=U_x(t)|+_n\rangle$ jest unormowany.

**Dowód.** Każdy składnik jest hermitowski. W iloczynie $Z_jZ_k$ operatory działają na różnych kubitach, więc komutują, a iloczyn pozostaje hermitowski. Rzeczywista kombinacja liniowa jest hermitowska. Twierdzenie spektralne daje $H=V\Lambda V^\dagger$, gdzie $V$ jest unitarny, a $\Lambda$ rzeczywista. Stąd $U=Ve^{-it\Lambda}V^\dagger$ i $U^\dagger U=I$. Ponadto $\langle+_n|+_n\rangle=2^{-n}2^n=1$, więc norma stanu zostaje zachowana. $\square$

`evolve_exact` realizuje właśnie diagonalizację hermitowską, a nie algorytm działający na QPU: [[code:hamiltonian_kernel/core.py#L124-L144]]. Dla gęstej macierzy o wymiarze $d=2^n$ sama reprezentacja wymaga $O(d^2)$ liczb; standardowa pełna diagonalizacja ma koszt sześcienny względem $d$. Referencja exact jest zatem użytecznym oracle'em dla małego $n$, lecz nie darmowym fizycznym urządzeniem.

## 3.2. Formuły produktowe i znaczenie kolejności

W tym podrozdziale $x$ jest ustalone, więc piszemy $A=A(x)$. Dla $r\geq1$ oraz $h=t/r>0$ pierwszy i drugi rząd zaimplementowano jako

$$
S_1(h)=e^{-ihB}e^{-ihA},\qquad
S_2(h)=e^{-ihA/2}e^{-ihB}e^{-ihA/2},
\qquad U_{p,r}(t)=S_p(h)^r.
$$

Prawy czynnik działa pierwszy. To istotne: kod najpierw stosuje część diagonalną, następnie rotacje $X$. Nie należy bez zmiany znaku komutatora zastępować tego schematu przez $e^{-ihA}e^{-ihB}$. Implementacja: [[code:hamiltonian_kernel/core.py#L98-L121]].

Ponieważ składniki $A$ wzajemnie komutują, $e^{-ihA}$ jest dokładnym iloczynem rotacji lokalnych $Z$ oraz rotacji $ZZ$. Analogicznie składniki $B$ komutują, więc $e^{-ihB}=\prod_j e^{-ihgX_j}$. W obrębie tych dwóch bloków nie występuje dodatkowy błąd Trottera. Kod wykorzystuje bezpośrednio fazy diagonalne i tożsamość $e^{-i\theta X}=\cos\theta I-i\sin\theta X$: [[code:hamiltonian_kernel/core.py#L77-L95]].

**Rozwinięcie BCH — wyprowadzenie własne.** Dla ustalonych skończonych macierzy $A,B$ i dostatecznie małego $|h|$, gdy logarytm analityczny istnieje w otoczeniu identyczności,

$$
\log S_1(h)
=-ih(A+B)+\frac{h^2}{2}[A,B]+O(h^3),
$$

$$
\log S_2(h)
=-ih(A+B)-ih^3\left(
\frac1{24}[A,[A,B]]+\frac1{12}[B,[A,B]]
\right)+O(h^5).
$$

**Uzasadnienie.** W pierwszym przypadku podstawienie $P=-ihB$, $Q=-ihA$ do $\log(e^Pe^Q)=P+Q+\tfrac12[P,Q]+O(h^3)$ daje $[P,Q]=h^2[A,B]$. Dla schematu symetrycznego dwukrotne zastosowanie BCH do $e^{P/2}e^Qe^{P/2}$, teraz z $P=-ihA$, $Q=-ihB$, daje

$$
P+Q-\frac1{24}[P,[P,Q]]+\frac1{12}[Q,[Q,P]]+O(h^5).
$$

Komutatory trzeciego stopnia po podstawieniu mają wskazane wyżej znaki. Relacja $S_2(-h)=S_2(h)^{-1}$ implikuje nieparzystość lokalnego analitycznego logarytmu, więc wyraz czwartego stopnia znika. Można także otrzymać te współczynniki, mnożąc trzy szeregi wykładnicze do stopnia trzeciego, a następnie rozwijając $\log(I+W)$. Dziedzina „dostatecznie małego $h$” jest konieczna dla tak zapisanej gałęzi logarytmu; globalne oszacowania poniżej nie wymagają istnienia tego logarytmu. $\square$

Rząd lokalnego błędu operatora wynosi odpowiednio $h^2$ i $h^3$, a globalnego, przy ustalonym $t$, $r^{-1}$ i $r^{-2}$. Stałe zależą od Hamiltonianu. Teoria komutatorowa błędów formuł produktowych analizuje tę zależność znacznie dokładniej niż sam symbol $O(\cdot)$ [@childs2021].

## 3.3. Jawne normowe granice Trottera

**Twierdzenie 3.2 — oszacowanie pierwszego rzędu, wyprowadzenie własne.** Jeśli $A,B$ są hermitowskimi macierzami skończonego wymiaru, $t\geq0$ i $r\in\mathbb N$, to

$$
\left\|e^{-it(A+B)}-S_1(t/r)^r\right\|
\leq\frac{t^2}{2r}\|[A,B]\|.
$$

**Dowód.** Niech $W(s)=e^{-isB}e^{-isA}$. Różniczkowanie daje

$$
W'(s)=-i\bigl(B+e^{-isB}Ae^{isB}\bigr)W(s).
$$

Sprzęganie unitarne zachowuje normę. Ponieważ

$$
e^{-isB}Ae^{isB}-A
=-i\int_0^s e^{-iuB}[B,A]e^{iuB}\,du,
$$

norma różnicy efektywnych generatorów jest nie większa niż $s\|[A,B]\|$. Formuła wariacji stałych dla różnicy propagatorów i unitarność obu propagatorów dają lokalnie $\|W(h)-e^{-ih(A+B)}\|\leq\int_0^h s\,ds\,\|[A,B]\|$. Dla dowolnych unitarnych $U,V$ tożsamość

$$
U^r-V^r=\sum_{k=0}^{r-1}U^{r-1-k}(U-V)V^k
$$

oraz nierówność trójkąta dają $\|U^r-V^r\|\leq r\|U-V\|$. Po podstawieniu $h=t/r$ otrzymujemy tezę. $\square$

**Twierdzenie 3.3 — oszacowanie drugiego rzędu, wyprowadzenie własne.** Przy tych samych założeniach

$$
\left\|e^{-it(A+B)}-S_2(t/r)^r\right\|
\leq\frac{t^3}{r^2}
\left(\frac{\|[A,[A,B]]\|}{24}
+\frac{\|[B,[A,B]]\|}{12}\right).
$$

**Dowód.** Oznaczmy $X=-iA$, $Y=-iB$, $C=[X,Y]$ i $\operatorname{Ad}_{e^{sX}}T=e^{sX}Te^{-sX}$. Dla $S(s)=e^{sX/2}e^{sY}e^{sX/2}$ defekt generatora $D(s)=S'(s)S(s)^{-1}-(X+Y)$ ma postać

$$
D(s)=\int_0^{s/2}\operatorname{Ad}_{e^{uX}}C\,du
-\frac12\operatorname{Ad}_{e^{sX/2}}
\int_0^s\operatorname{Ad}_{e^{vY}}C\,dv.
$$

Tożsamość wynika bezpośrednio z reguły iloczynu i całkowania pochodnej sprzężenia. Po dodaniu i odjęciu $(s/2)\operatorname{Ad}_{e^{sX/2}}C$ otrzymujemy

$$
\|D(s)\|
\leq\int_0^{s/2}(s/2-u)\,du\,\|[X,C]\|
+\frac12\int_0^s v\,dv\,\|[Y,C]\|
=\frac{s^2}{8}\|[X,C]\|+\frac{s^2}{4}\|[Y,C]\|.
$$

Użyto unitarności $e^{uX},e^{vY}$ oraz ponownie całkowej formuły na różnicę sprzężeń. Całkowanie defektu od $0$ do $h$ daje lokalną granicę $h^3\|[X,C]\|/24+h^3\|[Y,C]\|/12$. Normy zagnieżdżonych komutatorów są równe normom odpowiednich komutatorów $A,B$, ponieważ dodatkowe czynniki są potęgami $i$. Teleskopowanie $r$ kroków kończy dowód. $\square$

W modelu Isinga $[Z,X]=2iY$ daje dokładnie

$$
[A,B]=2ig\left(
\sum_jx_jY_j+J\sum_{\{j,k\}\in E}(Y_jZ_k+Z_jY_k)
\right).
$$

Ponieważ iloczyny Paulich mają normę $1$, dla $|x_j|\leq M$ zachodzą

$$
\|A\|\leq nM+|J||E|=:a,\qquad
\|B\|\leq n|g|=:b,
$$

$$
\|[A,B]\|\leq2|g|(nM+2|J||E|)=:c.
$$

Nierówność $\|[P,Q]\|\leq2\|P\|\|Q\|$ wynika z submultiplikatywności normy i nierówności trójkąta. Zatem prostsza, mniej ostra granica drugiego rzędu wynosi

$$
\|e^{-itH}-S_2(t/r)^r\|
\leq\frac{t^3c}{r^2}\left(\frac a{12}+\frac b6\right).
$$

To oszacowanie wyjaśnia, dlaczego porównanie samych rzędów nie usuwa zależności od $n$, amplitud danych i topologii. Dla łańcucha $|E|=n-1$, a dla grafu pełnego $|E|=n(n-1)/2$. Są to granice górne; ich wzrost nie dowodzi, że rzeczywisty błąd konkretnego stanu musi rosnąć z taką samą potęgą. Gdy prawa strona przekracza $2$, jest mniej użyteczna od trywialnej granicy różnicy dwóch operatorów unitarnych.

## 3.4. Od błędu ewolucji do błędu kernela

**Twierdzenie 3.4 — propagacja błędu, wyprowadzenie własne.** Niech $U_x,\widetilde U_x$ będą unitarne, a $\|U_x-\widetilde U_x\|\leq\varepsilon_x$. Dla odpowiadających im unormowanych stanów otrzymujemy

$$
1-|\langle\psi_x|\widetilde\psi_x\rangle|^2\leq\varepsilon_x^2,
$$

$$
\left||\langle\psi_x|\psi_y\rangle|^2-
|\langle\widetilde\psi_x|\widetilde\psi_y\rangle|^2\right|
\leq2(\varepsilon_x+\varepsilon_y).
$$

**Dowód.** Norma różnicy stanów jest nie większa niż $\varepsilon_x$. Jeśli $z=\langle\psi_x|\widetilde\psi_x\rangle$, to
$1-|z|^2\leq2(1-|z|)\leq2(1-\operatorname{Re}z)=\|\psi_x-\widetilde\psi_x\|^2$.
Różnica amplitud overlapu ma moduł co najwyżej $\varepsilon_x+\varepsilon_y$, po dodaniu i odjęciu $\langle\widetilde\psi_x|\psi_y\rangle$ i zastosowaniu Cauchy'ego–Schwarza. Dla amplitud $u,v$ o module co najwyżej $1$ mamy $||u|^2-|v|^2|\leq2|u-v|$. $\square$

Przy jednolitej granicy $\varepsilon$ oraz $N$ próbkach wynika z tego $\|K-\widetilde K\|_F\leq4N\varepsilon$, ponieważ macierz ma $N^2$ elementów, każdy ograniczony przez $4\varepsilon$. Są to gwarancje geometryczne. Nie implikują monotonicznego wzrostu balanced accuracy wraz ze zwiększaniem liczby kroków. Dyskretna decyzja klasyfikacyjna może zmienić się skokowo, a dokładniejszy kernel fizyczny nie musi lepiej reprezentować konkretnych etykiet.

`state_infidelity` mierzy powyższą niewierność stanów, nie normę różnicy propagatorów: [[code:hamiltonian_kernel/core.py#L203-L209]]. Zbieżność na jednym stanie początkowym jest słabszym sprawdzeniem niż kontrola operatorowa na całej przestrzeni Hilberta.

## 3.5. Szczególny przypadek: jeden krok pierwszego rzędu

**Twierdzenie 3.5 — dokładna redukcja kernela, wyprowadzenie własne.** W podstawowym modelu z `core.py`, przy wspólnych dla wszystkich danych $J,g,G,t$ i dokładnie jednym kroku pierwszego rzędu,

$$
k_1(x,y)=\prod_{j=0}^{n-1}\cos^2\bigl(t(x_j-y_j)\bigr).
$$

Kernel ten jest niezależny od $J$, $g$ oraz grafu $G$.

**Dowód.** Przy $|\psi_x\rangle=e^{-itB}e^{-itA(x)}|+_n\rangle$ wspólny czynnik $e^{-itB}$ skraca się w overlapie. Operatory $A(x),A(y)$ są diagonalne i komutują, a ich wspólna część oddziaływania $J\sum Z_jZ_k$ również się skraca. Zostaje

$$
\langle\psi_y|\psi_x\rangle
=\langle+_n|e^{-it\sum_j(x_j-y_j)Z_j}|+_n\rangle
=\prod_j\langle+|e^{-it(x_j-y_j)Z}|+\rangle
=\prod_j\cos\bigl(t(x_j-y_j)\bigr).
$$

Podniesienie modułu do kwadratu daje tezę. $\square$

To dokładny klasyczny punkt odniesienia o koszcie $O(n)$ na parę. Stan po części $ZZ$ może być splątany, ale ta wspólna operacja nie wnosi informacji do tego konkretnego fidelity kernela. Nie należy wyciągać stąd analogicznego wniosku dla projected kernela, wielu kroków, drugiego rzędu ani dla ogólnej rodziny v3, w której wiele współczynników zależy od danych. Kod jednoznacznie określający dziedzinę twierdzenia: [[code:hamiltonian_kernel/core.py#L62-L74]] i [[code:hamiltonian_kernel/core.py#L111-L120]].

## 3.6. Fidelity jako dodatnio półokreślony kernel

Definicja używana przez `fidelity_kernel` to

$$
k_F(x,y)=|\langle\psi_x|\psi_y\rangle|^2
=\operatorname{Tr}(\rho_x\rho_y),\qquad
\rho_x=|\psi_x\rangle\langle\psi_x|.
$$

Implementacja: [[code:hamiltonian_kernel/core.py#L156-L159]]. To kernel overlapowy znany z kwantowych map cech [@havlicek2019]. W przypadku mieszanych macierzy gęstości iloczyn Hilberta–Schmidta $\operatorname{Tr}(\rho\sigma)$ nadal definiuje PSD kernel, ale nie jest ogólnie wiernością Uhlmanna. Rozróżnienie staje się istotne po dodaniu szumu kanałowego.

**Twierdzenie 3.6 — PSD i normalizacja, wyprowadzenie własne.** Dla dowolnego skończonego zbioru unormowanych stanów macierz $K_{ij}=k_F(x_i,x_j)$ jest rzeczywista, symetryczna, dodatnio półokreślona i ma diagonalę równą $1$.

**Dowód.** Symetria i rzeczywistość wynikają z modułu kwadratowego. Dla $c\in\mathbb C^N$ oraz $R=\sum_jc_j\rho_j$,

$$
c^\dagger Kc=\operatorname{Tr}(R^\dagger R)=\|R\|_F^2\geq0.
$$

Dla stanów czystych $\rho_i^2=\rho_i$ oraz $\operatorname{Tr}\rho_i=1$, więc $K_{ii}=1$. $\square$

Dowód ujawnia właściwą przestrzeń cech: są nią operatory stanów z iloczynem Hilberta–Schmidta, nie sam wektor stanu z arbitralną fazą globalną. Jej wymiar liniowy nie przekracza $d^2=4^n$. Stąd $\operatorname{rank}K\leq\min(N,4^n)$, ponieważ $K$ jest Gramem $N$ wektorów w tej przestrzeni. Sama ta granica nie orzeka o wymiarze efektywnym konkretnego zbioru ani o trudności klasycznej symulacji.

## 3.7. Projected kernel i poprawny czynnik jednej drugiej

Jednokubitowa redukcja $\rho_{x,j}$ ma reprezentację Blocha

$$
\rho_{x,j}=\frac12\left(I+r_{x,j}^{(X)}X+r_{x,j}^{(Y)}Y+r_{x,j}^{(Z)}Z\right),
\qquad r_{x,j}^{(a)}=\langle\psi_x|\sigma_j^{(a)}|\psi_x\rangle.
$$

`bloch_vectors` oblicza te oczekiwania, w tym poprawny znak części $Y$, przez koherencje $\overline\psi_0\psi_1$: [[code:hamiltonian_kernel/core.py#L162-L186]]. Definiujemy $r_x\in\mathbb R^{3n}$ przez konkatenację lokalnych wektorów. Dzięki $\operatorname{Tr}(\sigma_a\sigma_b)=2\delta_{ab}$,

$$
\|\rho_{x,j}-\rho_{y,j}\|_F^2
=\frac12\|r_{x,j}-r_{y,j}\|_2^2.
$$

Dowód polega na rozwinięciu kwadratu $\tfrac12\sum_a(r_x^{(a)}-r_y^{(a)})\sigma_a$ i użyciu powyższej ortogonalności. Zatem implementowany kernel jest dokładnie

$$
k_P(x,y)=\exp\left(-\gamma\sum_j\|\rho_{x,j}-\rho_{y,j}\|_F^2\right)
=\exp\left(-\frac\gamma2\|r_x-r_y\|_2^2\right),\qquad\gamma>0.
$$

Implementacja: [[code:hamiltonian_kernel/core.py#L189-L200]]. Konstrukcja odpowiada lokalnej wersji projected quantum kernel [@huang2021].

**Twierdzenie 3.7 — PSD projected kernela, wyprowadzenie własne.** Dla dowolnych rzeczywistych wektorów $r_1,\ldots,r_N$ i $\gamma>0$ powyższy Gram jest PSD. Nie jest do tego konieczne, aby wektory były fizycznymi wektorami Blocha.

**Dowód.** Rozkładamy

$$
e^{-\gamma\|u-v\|^2/2}
=e^{-\gamma\|u\|^2/2}e^{-\gamma\|v\|^2/2}
\sum_{m=0}^\infty\frac{\gamma^m}{m!}\langle u,v\rangle^m.
$$

Dla każdego $m$ funkcja $\langle u,v\rangle^m$ jest iloczynem skalarnym tensorów $u^{\otimes m},v^{\otimes m}$. Każda częściowa suma z nieujemnymi współczynnikami ma PSD Gram; granica zachowuje nieujemność form kwadratowych. Dodatnie czynniki zależne osobno od $u$ i $v$ odpowiadają kongruencji diagonalnej, która również zachowuje PSD. $\square$

Projektowanie może usuwać istotną informację. Na przykład stany Bella $|\Phi^+\rangle$ i $|\Phi^-\rangle$ są ortogonalne, lecz każda ich jednokubitowa redukcja jest $I/2$. Dlatego fidelity między nimi wynosi $0$, a lokalny projected kernel $1$. Dowód redukcji uzyskuje się przez ślad częściowy: wyrazy krzyżowe $|00\rangle\langle11|$ i $|11\rangle\langle00|$ znikają. Większa odporność pomiarowa projected może zatem wiązać się z utratą informacji, co jest kompromisem reprezentacji, a nie uniwersalną poprawą każdego zadania.

## 3.8. Skończona liczba pomiarów i kowariancje

Dla idealnego overlap circuit sukces oznacza odczyt samych zer. Przy $s\geq1$ niezależnych identycznie rozłożonych pomiarach $B\sim\operatorname{Binomial}(s,k_F)$ i $\widehat k_F=B/s$:

$$
\mathbb E\widehat k_F=k_F,\qquad
\operatorname{Var}(\widehat k_F)=\frac{k_F(1-k_F)}s\leq\frac1{4s}.
$$

**Wyprowadzenie własne.** Estymator jest średnią $s$ wskaźników Bernoulliego. Liniowość wartości oczekiwanej daje pierwszą równość; niezależność usuwa kowariancje w wariancji średniej, a maksimum $p(1-p)$ na $[0,1]$ wynosi $1/4$. Założenie niezależnych, stacjonarnych pomiarów wyklucza m.in. dryf kalibracji i korelacje między shotami. Kod symulacyjny losuje dokładnie taki model: [[code:hamiltonian_kernel/estimation.py#L165-L184]].

Nieobciążoność poszczególnych elementów nie oznacza, że każda realizacja całej macierzy jest PSD. Ograniczenia Grama łączą wszystkie pary i nie są narzucane przez niezależne losowania dwumianowe. Symetryzacja przez wspólną górną i dolną połowę zapewnia jedynie symetrię.

Projected korzysta z trzech ustawień globalnych: pomiarów wszystkich kubitów w bazie $X$, następnie $Y$, następnie $Z$. Rotacja dla $Y$ to $HS^\dagger$ przed pomiarem $Z$. Jedna realizacja bitstringu w danej bazie dostarcza jednocześnie wartości $z_j\in\{-1,1\}$ dla wszystkich kubitów. `projected_basis_probabilities` i `estimate_projected_bloch` losują cały histogram wielomianowy: [[code:hamiltonian_kernel/estimation.py#L268-L335]].

**Twierdzenie 3.8 — wariancja i kowariancja lokalnych estymatorów, wyprowadzenie własne.** Przy $s$ niezależnych bitstringach z jednego ustawienia $a$,

$$
\widehat r_j^{(a)}=\frac1s\sum_{\ell=1}^s z_{j,\ell},\quad
\operatorname{Var}(\widehat r_j^{(a)})=\frac{1-(r_j^{(a)})^2}s,
$$

$$
\operatorname{Cov}(\widehat r_j^{(a)},\widehat r_k^{(a)})
=\frac{\langle\sigma_j^{(a)}\sigma_k^{(a)}\rangle-r_j^{(a)}r_k^{(a)}}s.
$$

**Dowód.** Ponieważ $z_j^2=1$, wariancja pojedynczej obserwacji wynosi $1-(\mathbb Ez_j)^2$. Przy sumowaniu po shotach pozostają wyłącznie składniki o tym samym numerze shota. Wspólny pomiar komutujących lokalnych obserwabli ma moment $\mathbb E(z_jz_k)=\langle\sigma_j\sigma_k\rangle$. Dzielenie przez $s^2$ daje wskazane wzory. $\square$

Starsza funkcja `sample_bloch_vectors` losuje niezależne zmienne dwumianowe dla wszystkich składowych i nie odtwarza tych kowariancji: [[code:hamiltonian_kernel/learning.py#L125-L130]]. Nie jest to równoważny model pomiarowy. Aktualny estymator wielomianowy zachowuje potrzebne zależności.

Dla niezależnie zmierzonych dwóch próbek nieobciążone wektory cech spełniają
$\mathbb E\|\widehat r_x-\widehat r_y\|^2=\|r_x-r_y\|^2+\operatorname{Tr}\operatorname{Cov}(\widehat r_x)+\operatorname{Tr}\operatorname{Cov}(\widehat r_y)$, co wynika z rozwinięcia kwadratu i wyzerowania średniej błędów. Nie daje to nieobciążoności wykładniczego kernela. Jednocześnie wspólny, raz oszacowany wektor dla każdej próbki gwarantuje PSD całego Grama przez twierdzenie 3.7, nawet gdy $\|\widehat r_{x,j}\|>1$. Brak fizyczności pojedynczej estymowanej redukcji nie niszczy wówczas matematycznej poprawności Gaussowskiego kernela na cechach.

## 3.9. Naprawa PSD i spójna ekstensja na nowe próbki

Dla symetrycznej obserwowanej macierzy $W=V\operatorname{diag}(\lambda_i)V^\top$ procedura `kernel_stages` tworzy

$$
W_+=V\operatorname{diag}(\max(\lambda_i,0))V^\top,
\qquad
W_\tau=V\operatorname{diag}(\lambda_i\mathbf1_{\lambda_i>\tau})V^\top,
$$

gdzie $\tau=\max(10^{-12},\lambda_{\max}(W_+)\cdot\texttt{relative\_threshold})$.
Implementacja: [[code:hamiltonian_kernel/estimation.py#L93-L117]].

**Twierdzenie 3.9 — projekcja Frobeniusa, wyprowadzenie własne.** Dla rzeczywistej symetrycznej $W$ macierz $W_+$ minimalizuje $\|W-X\|_F$ po $X\succeq0$.

**Dowód.** Niezmienniczość normy Frobeniusa względem transformacji ortogonalnych pozwala przejść do $Y=V^\top XV\succeq0$. Wtedy

$$
\|W-X\|_F^2=\sum_i(\lambda_i-Y_{ii})^2+\sum_{i\ne j}Y_{ij}^2.
$$

Dla PSD $Y$ wszystkie $Y_{ii}\geq0$, więc każdy składnik diagonalny jest co najmniej odległością $\lambda_i$ od $[0,\infty)$. Wybór $Y=\operatorname{diag}(\max(\lambda_i,0))$ osiąga te dolne granice i zeruje wszystkie składniki pozadiagonalne. $\square$

To standardowy problem najbliższej macierzy PSD [@higham1988]. Problem najbliższej macierzy korelacji zawiera dodatkowo warunek diagonali równej $1$. Jednorazowe obcięcie widma, a potem normalizacja diagonali nie otrzymuje z powyższego dowodu gwarancji rozwiązania tego dodatkowego problemu. Nazwa `nearest_correlation_kernel` jest zatem silniejsza niż wykazana własność procedury: [[code:hamiltonian_kernel/learning.py#L133-L143]]. Procedura daje PSD i jednostkową diagonalę; nie wykazano tu jej optymalności odległościowej w zbiorze macierzy korelacji.

Samo zastąpienie train-Grama przez $W_+$ nie określa, co należy zrobić z cross-kernelem test–train. Aktualny estymator fidelity tworzy wspólną mapę cech. Dla landmarków wybranych wyłącznie z train i macierzy pomiarów $C$ wszystkich próbek względem landmarków definiuje

$$
F=CV_R\Lambda_R^{-1/2},\qquad
R=\{i:\lambda_i>\tau\}.
$$

Następnie dla wiersza $f_x\ne0$ stosuje $\bar f_x=f_x\sqrt{d_x}/\|f_x\|$, gdzie $d_x$ jest zmierzoną diagonalą. Dla zerowego wiersza pozostawia zero. Używany Gram to $\bar F\bar F^\top$, a cross-kernel to $\bar F_{\rm test}\bar F_{\rm train}^\top$. Implementacja: [[code:hamiltonian_kernel/estimation.py#L192-L215]].

**Dowód spójności, wyprowadzenie własne.** Dla dowolnego $v$ zachodzi $v^\top\bar F\bar F^\top v=\|\bar F^\top v\|^2\geq0$. Wszystkie bloki pochodzą z tych samych wektorów cech, więc są ograniczeniami jednego PSD Grama. Dopasowanie $V_R,\Lambda_R$ korzysta wyłącznie z landmarków train; test dostarcza jedynie własny wektor $C_x$ i diagonalę. Nie jest potrzebne wspólne diagonalizowanie train i test. $\square$

**Niespójność metadanych H-03.** W pełnym train przed normalizacją $F_{\rm train}F_{\rm train}^\top=W_\tau$. Po normalizacji otrzymujemy $DW_\tau D$, czyli kongruencję, nie transformację podobieństwa. Widmo ogólnie się zmienia. Mimo to zwracane `spectral_eigenvalues` pochodzi z $W_\tau$: [[code:hamiltonian_kernel/estimation.py#L238-L248]]. Publikacyjny zapis zestawia je ze znormalizowanym `spectral_kernel_all`: [[code:hamiltonian_kernel/publication_benchmark.py#L451-L473]]. Przy Nyström liczba landmarków dodatkowo różni się od liczby wszystkich próbek. Potrzebne są oddzielne nazwy widm przed i po normalizacji oraz jawna identyfikacja macierzy. Diagnostyka wcześniejszego audytu zapisała rozbieżność $0{,}4510499440$ w małym przykładzie; jest to dowód niespójności etykiet, nie dowód błędnej PSD konstrukcji cech ani zmiany accuracy.

## 3.10. KRR: problem optymalizacyjny i kontrprzykład nieokreśloności

Niech $N$ będzie liczbą próbek train, $q$ liczbą klas, a $Y\in\mathbb R^{N\times q}$ macierzą etykiet one-versus-rest o elementach $+1$ dla klasy prawdziwej i $-1$ dla pozostałych. Dla PSD kernela standardowa regresja grzbietowa rozwiązuje

$$
\min_{f_1,\ldots,f_q\in\mathcal H_k}
\sum_{i=1}^N\sum_{c=1}^q(f_c(x_i)-Y_{ic})^2
+\lambda\sum_{c=1}^q\|f_c\|_{\mathcal H_k}^2,\qquad\lambda>0.
$$

Nie zastosowano tu normalizacji straty przez $N$; po jej wprowadzeniu równoważny układ zawiera $N\lambda I$. To istotne przy porównywaniu hiperparametrów między bibliotekami. Kod używa

$$
\Alpha=(K+\lambda I)^{-1}Y,\qquad
\widehat y(x)=\arg\max_c\,[k(x,X)\Alpha]_c.
$$

Implementacja etykiet, solve/pseudoinverse i decyzji: [[code:hamiltonian_kernel/learning.py#L6-L26]].

**Twierdzenie 3.10 — związek z minimum w RKHS, wyprowadzenie własne.** Przy PSD $K$ i $\lambda>0$ podany wzór definiuje minimizer problemu KRR.

**Dowód.** Rozkładamy dowolne $f$ na składową w przestrzeni rozpiętej przez $k(x_i,\cdot)$ i składową ortogonalną. Własność reprodukująca powoduje, że składowa ortogonalna ma wartość zero we wszystkich $x_i$; zwiększa jedynie karę normową. Wystarczy więc $f=\sum_i\alpha_i k(x_i,\cdot)$. Funkcjonał przyjmuje postać $\|K\alpha-y\|^2+\lambda\alpha^\top K\alpha$. W bazie własnej $K$ każda dodatnia wartość własna $\mu$ daje minimum przy $\alpha_\mu=y_\mu/(\mu+\lambda)$. Dla $\mu=0$ współczynnik nie zmienia funkcji; rozwiązanie $(K+\lambda I)^{-1}y$ wybiera jedną reprezentację. Macierz $K+\lambda I$ ma wartości własne co najmniej $\lambda$, zatem jest odwracalna. Wieloklasowy problem jest sumą takich zadań. $\square$

**Kontrprzykład 3.11 — surowy Gram pomiarowy, wyprowadzenie własne.** Rozważmy

$$
K=\begin{pmatrix}1&0.9&0.9\\0.9&1&0\\0.9&0&1\end{pmatrix}.
$$

Jego wartości własne wynoszą $1$, $1+0.9\sqrt2$, $1-0.9\sqrt2$. Ostatnia to około $-0.2727922061$. Wektory $(0,1,-1)$ i $(\pm\sqrt2,1,1)$ pozwalają bezpośrednio sprawdzić te wartości. Macierz ma prawidłowy zakres elementów i diagonalę, lecz nie jest Gramem żadnej przestrzeni Hilberta.

Taka obserwacja może wystąpić z dodatnim prawdopodobieństwem nawet dla prawidłowych stanów. Weźmy $|\psi_1\rangle=|0\rangle$ i $|\psi_{2,3}\rangle=\sqrt{0.9}|0\rangle\pm\sqrt{0.1}|1\rangle$. Ich prawdziwe fidelity wynoszą $(0.9,0.9,0.64)$ dla trzech par. Przy dziesięciu niezależnych shotach na parę wyniki $(9,9,0)$ mają dodatnie prawdopodobieństwo i dają dokładnie powyższy nieokreślony Gram.

Jeśli $\lambda=0.9\sqrt2-1$, układ $K+\lambda I$ jest osobliwy. W pobliżu tej wartości rozwiązywanie układu wzmacnia zaburzenia w kierunku ujemnej wartości własnej. Dla $\lambda=0.1$ macierz układu nadal jest nieokreślona. Samo dodanie dodatniej regularyzacji nie gwarantuje zatem zwykłych własności KRR.

Jest jeszcze mocniejszy problem interpretacyjny. Formalnie podstawiając ten $K$ do $\|K\alpha-y\|^2+\lambda\alpha^\top K\alpha$, w kierunku własnym o wartości $\mu<0$ otrzymujemy współczynnik kwadratowy $\mu(\mu+\lambda)$. Przy $\lambda=0.3$ zachodzi $\mu+\lambda>0$, ale $\mu(\mu+\lambda)<0$, więc funkcjonał jest nieograniczony z dołu w tym kierunku. Nawet dodatnia określoność $K+\lambda I$ nie przywraca interpretacji $\alpha^\top K\alpha$ jako kwadratu normy RKHS. To rozróżnienie zapobiega błędnemu utożsamieniu „układ da się rozwiązać” z „rozwiązano wypukłą regresję kernelową”.

**Niespójność H-01.** W v3 `select_policy` przekazuje surowy Gram do inner CV: [[code:hamiltonian_kernel/trotter_scaling_v3.py#L407-L424]]. `_post_selection_diagnostics` oblicza końcową predykcję z `raw_train` i `raw_cross`, a dopiero później tworzy PSD/spectral do diagnostyk: [[code:hamiltonian_kernel/trotter_scaling_v3.py#L459-L480]]. Zapisana PSD macierz nie jest dowodem, że właśnie na niej uczono klasyfikator.

Poprawka wymaga wyboru estymatora: albo jawnie badamy metodę opartą na nieokreślonych podobieństwach, albo używamy spójnej mapy PSD w każdym inner foldzie i ponownie na outer train. Pseudoinverse w `fit_kernel_ridge` jest mechanizmem numerycznym, nie naprawą modelu matematycznego. Nowa definicja estymatora wymaga nowego protokołu i nowych wyników; nie powinna być dopisywana do historycznego runu jako niewidoczna korekta.

## 3.11. Stabilność rozwiązania a stabilność decyzji

Prace dotyczące aproksymacji kerneli badają relację błędu macierzy do błędu uczonej hipotezy [@cortes2010]. Poniższa prosta granica pokazuje rolę regularyzacji w obecnym modelu.

**Twierdzenie 3.12 — perturbacja współczynników, wyprowadzenie własne.** Jeśli $K,\widetilde K\succeq0$, $E=\widetilde K-K$ i $\lambda>0$, to dla tej samej macierzy etykiet $Y$

$$
\|\widetilde\Alpha-\Alpha\|_F
\leq\frac{\|E\|}{\lambda^2}\|Y\|_F.
$$

**Dowód.** Tożsamość resolwenty daje

$$
(\widetilde K+\lambda I)^{-1}-(K+\lambda I)^{-1}
=-(\widetilde K+\lambda I)^{-1}E(K+\lambda I)^{-1}.
$$

Każda z norm odwrotności jest nie większa niż $1/\lambda$. Mnożenie przez $Y$ i submultiplikatywność dają tezę. $\square$

Dla pojedynczego wektora cross-kernela $k_x$ i jego przybliżenia $\widetilde k_x$ analogicznie

$$
\|\widetilde k_x\widetilde\Alpha-k_x\Alpha\|_2
\leq\|\widetilde k_x-k_x\|_2\frac{\|Y\|_F}{\lambda}
+\|k_x\|_2\frac{\|E\|\|Y\|_F}{\lambda^2}.
$$

Wynika to z dodania i odjęcia $k_x\widetilde\Alpha$ oraz użycia poprzedniej granicy. Jeśli margines między największą a drugą największą składową oryginalnego wektora wyników przekracza dwukrotność górnej granicy błędu każdej składowej, klasa zwycięska nie zmieni się: zwycięzca może spaść najwyżej o błąd, a konkurent wzrosnąć najwyżej o błąd. Bez dodatniego marginesu dowolnie mała perturbacja może zmienić argmax. Dlatego mały błąd Trottera nie daje sam w sobie monotonicznej gwarancji accuracy.

## 3.12. Zagnieżdżona selekcja i granica dostępu do danych

Właściwą jednostką porównania jest cały algorytm: preprocessing, lista kandydatów, szum pomiarowy, wybór $\lambda$, naprawa macierzy i reguła rozstrzygania remisów. Ocena samego wybranego kernela na danych użytych do wyboru nie ocenia generalizacji tego algorytmu.

W benchmarku publikacyjnym `_nested_select` dopasowuje preprocessing osobno w każdym inner train, a następnie przekształca inner validation: [[code:hamiltonian_kernel/publication_benchmark.py#L268-L310]]. Jest to poprawna granica dostępu. Jednak quantum selection używa idealnych stanów, a skończone pomiary pojawiają się dopiero podczas końcowej oceny. Wynik oznacza więc jakość pipeline'u strojonego idealnie i ocenianego przy ograniczonych pomiarach; nie oznacza optimum po niezależnym strojeniu $\lambda$ dla każdego finite-shot Grama.

V3 wprowadza inne zadanie: każda para `(order, delta_t)` otrzymuje surową próbkowaną macierz outer train, a jej regularyzacja jest oceniana przez inner CV. Funkcja przyjmuje tablice `values` i `labels`, ale w ścieżce selekcji indeksuje wyłącznie outer train. To własność kodu, nie ograniczenie samej sygnatury: [[code:hamiltonian_kernel/trotter_scaling_v3.py#L392-L435]]. Wybrana konfiguracja jest zapisywana przed wywołaniem exact: [[code:hamiltonian_kernel/trotter_scaling_v3.py#L578-L599]].

Jeżeli naprawimy H-01, nie wolno najpierw diagonalizować pełnego outer train, a potem używać podmacierzy otrzymanej mapy we wszystkich inner foldach. Wówczas dane inner validation uczestniczyłyby w dopasowaniu bazy cech. Poprawny algorytm dopasowuje mapę spektralną na każdym inner train, rozszerza ją na inner validation, wybiera hiperparametry, a dopiero później dopasowuje finalną mapę na całym outer train. Reużycie zmierzonych surowych par jest odrębną sprawą: samo przechowanie wszystkich pomiarów nie jest leakage, o ile transformacja i wybór używają wyłącznie dozwolonych bloków.

**Twierdzenie 3.13 — sens niezależnego holdoutu, wyprowadzenie własne.** Załóżmy, że klasyfikator $f$ jest funkcją tylko danych development i niezależnej losowości algorytmu. Jeśli test zawiera dla każdej klasy $c$ dodatnią liczbę niezależnych próbek z rozkładu $X\mid Y=c$, niezależnych od development, to empiryczna balanced accuracy jest warunkowo nieobciążonym estymatorem średniego recallu $f$ po klasach.

**Dowód.** Po uwarunkowaniu względem development i losowości $f$ jest ustalony. Każdy wskaźnik $\mathbf1\{f(X)=c\}$ w klasie $c$ ma średnią $r_c=\Pr(f(X)=c\mid Y=c)$. Średnia wskaźników ma więc wartość oczekiwaną $r_c$, a średnia po klasach wartość $q^{-1}\sum_cr_c$. $\square$

Twierdzenie nie mówi, że wszystkie wyniki repeated CV są niezależnymi estymatorami populacyjnymi. Nie mówi też, że po obejrzeniu testu można bez konsekwencji poprawiać preprocessing lub shortlistę. V3 finalnie zapisuje wszystkie decyzje i hashe macierzy przed wygenerowaniem holdoutu w `run_holdout`: [[code:hamiltonian_kernel/trotter_scaling_v3.py#L751-L773]]. Samo wcześniejsze wygenerowanie danych przy zamrażaniu ich fingerprintu jest techniczną częścią prerejestracji, a nie dowodem wykorzystania ich do selekcji.

## 3.13. Koszt pomiarów: estymacja, rezerwacja i wykonanie

Niech $N$ oznacza liczbę train, $M$ liczbę test, a $s$ shots na ustawienie. Dla fidelity z pomiarem pełnej górnej połowy train, wszystkich par test–train oraz diagonali test liczba ustawień wynosi

$$
C_F=\frac{N(N+1)}2+MN+M.
$$

Dla projected z trzema bazami globalnymi $C_P=3(N+M)$. Dowód jest bezpośrednim zliczeniem par i ustawień. Jest to przewaga skali liczby ustawień przy takim modelu pomiarowym, a nie bezwarunkowy dowód większej accuracy. Kod zliczania fidelity: [[code:hamiltonian_kernel/estimation.py#L120-L136]]; projected: [[code:hamiltonian_kernel/estimation.py#L297-L308]].

Przy całkowitym budżecie $S$ alokacja stosuje $S=Cq+r$, $0\leq r<C$: każde ustawienie otrzymuje $q$ shots, a $r$ losowo wybranych ustawień dodatkowy shot. Wtedy suma wynosi dokładnie $S$. Minimalny warunek wykonalności to $S\geq C$. „Taki sam shots per circuit” i „taki sam całkowity budżet” są różnymi porównaniami, ponieważ $C_F$ i $C_P$ mają inną zależność od liczby próbek.

`resource_cost` rozdziela circuit-shots, liczbę wywołań mapy cech oraz 2Q-gate-shots: [[code:hamiltonian_kernel/estimation.py#L73-L90]]. Overlap składa się z mapy i odwrotnej mapy, więc w modelu logicznym ma dwa wywołania mapy na shot; projected ma jedno. Czas QPU i kredyty są danymi providera, nie skutkiem przemnożenia tych liczników przez uniwersalną stałą.

W benchmarku publikacyjnym budżet pomiarowy dotyczy końcowej estymacji wybranej rodziny, podczas gdy strojenie wykonuje symulator idealny. Nie wolno opisywać tego budżetu jako pełnego fizycznego kosztu wyszukiwania. W v3 rozliczono osobno koszt $L$ kandydatów train oraz jednego wybranego kandydata test. Niech

$$
P=\frac{N(N+1)}2,\qquad T=NM,\qquad C=LP+T,
$$

a $g_\ell$ oznacza liczbę bramek 2Q pojedynczej mapy kandydata $\ell$. V3 nie dodaje osobnych diagonali test do tego rachunku; jest to zgodne z jego surową ścieżką predykcji, która ich nie używa. Przed wyborem kandydata kod rezerwuje

$$
G_{\rm reserve}=2s\left(P\sum_{\ell=1}^L g_\ell+T\max_\ell g_\ell\right).
$$

Po wybraniu $\ell_*$ rzeczywisty koszt w tym samym modelu dwóch map wynosi

$$
G_{\rm selected}=2s\left(P\sum_{\ell=1}^L g_\ell+Tg_{\ell_*}\right),
\qquad
G_{\rm reserve}-G_{\rm selected}
=2sT(\max_\ell g_\ell-g_{\ell_*})\geq0.
$$

**Niespójność H-02.** `_candidate_budget` prawidłowo używa maksimum do ostrożnej alokacji, lecz `run_condition` zapisuje je jako `two_qubit_gate_shots_used`: [[code:hamiltonian_kernel/trotter_scaling_v3.py#L359-L366]] i [[code:hamiltonian_kernel/trotter_scaling_v3.py#L604-L612]]. Przy $g_1=1$, $g_2=10$, $P=3$, $T=4$, $s=68$ rezerwacja wynosi $9928$, a koszt wyboru tańszego kandydata $5032$. To zawyżenie deklarowanego zużycia, nie przekroczenie budżetu. Naprawa polega na zapisaniu obu wielkości.

Trzeba jeszcze odróżnić koszt dwóch osobno skompilowanych map od kosztu kompletnego overlap circuit po optymalizacji. Bramki mogą się kasować; obwód diagonalnego overlapu w idealnym przypadku realizuje identyczność. `full_circuit_resources` v3 kompiluje całą pojedynczą mapę parametrów, a nie parę mapa–odwrotna mapa: [[code:hamiltonian_kernel/trotter_scaling_v3.py#L289-L312]]. Dlatego jego limit depth należy interpretować jako limit głębokości mapy. Do stwierdzenia wykonalności pełnego pomiaru na konkretnym QPU potrzebna jest transpilacja całego obwodu pomiarowego.

Porównanie exact przy tej samej liczbie shots izoluje część błędu estymacji. Nie wyrównuje kosztu bramek exact i Trotter. Wartość zerowa zwracana dla exact przez logiczny helper kosztów nie jest dowodem zerowego kosztu fizycznego: [[code:hamiltonian_kernel/core.py#L212-L222]].

## 3.14. Ogólne sumy Paulich i czwarty rząd w v3

Gałąź skalowania uogólnia model do

$$
H(x)=\sum_{\ell=1}^m c_\ell(x)P_\ell,
\qquad c_\ell(x)=b_\ell+w_\ell^\top x,
$$

gdzie $P_\ell$ są hermitowskimi iloczynami Paulich. Każdy składnik spełnia $P_\ell^2=I$, więc $e^{-i\theta P_\ell}=\cos\theta I-i\sin\theta P_\ell$. Tożsamość wynika z rozdzielenia szeregu wykładniczego na wyrazy parzyste i nieparzyste. Implementacja batch używa dokładnie tej reprezentacji: [[code:hamiltonian_kernel/universal_hamiltonian.py#L365-L395]].

Rodzina oznaczona w v3 jako `random_k_local` wybiera w rzeczywistości składniki co najwyżej dwulokalne. Nazwa nie oznacza przeprowadzenia badania dla dowolnego $k$: [[code:hamiltonian_kernel/trotter_scaling_full.py#L425-L447]]. Profile `spectral_radius_1` i `spectral_radius_3` kalibrują normę na skończonym zbiorze sond $0,\pm e_j$, a nie na wszystkich $x\in[-1,1]^d$: [[code:hamiltonian_kernel/trotter_scaling_full.py#L467-L496]]. Nie wolno zastąpić „maksimum po sondach wynosi 1” twierdzeniem „norma Hamiltonianu jest ograniczona przez 1 na całej dziedzinie”.

Symetryczna formuła drugiego rzędu dla wielu składników jest palindromicznym iloczynem połówek. Z niej zbudowano

$$
S_4(h)=S_2(ph)^2S_2((1-4p)h)S_2(ph)^2,
\qquad p=\frac1{4-4^{1/3}}.
$$

Konstrukcję wyższych rzędów opisuje [@suzuki1990]. Implementacja: [[code:hamiltonian_kernel/universal_hamiltonian.py#L285-L314]].

**Uzasadnienie rzędu, wyprowadzenie własne.** Jeśli lokalnie $\log S_2(h)=hL+h^3E+O(h^5)$, składanie skalowanych kroków daje w pierwszym rzędzie współczynnik $4p+(1-4p)=1$. W trzecim rzędzie współczynnik błędu to $4p^3+(1-4p)^3=0$. Komutatory składników liniowych z sobą znikają, ponieważ wszystkie są wielokrotnościami $L$. Symetria całego złożenia wyklucza parzyste potęgi logarytmu, w tym wyrazy stopnia czwartego. Pozostaje $hL+O(h^5)$, czyli błąd globalny $O(r^{-4})$ dla ustalonych skończonych generatorów i $t$. $\square$

Środkowy współczynnik $1-4p$ jest ujemny. Ujemny czas nie narusza unitarności ewolucji zamkniętej, ale odwrotność kanału strat lub depolaryzacji na ogół nie jest kanałem fizycznym. Zatem nie można bez dodatkowej konstrukcji przenieść tego samego palindromu na dowolną nieodwracalną dynamikę otwartą. Dokładne sumowanie czasu z ewentualnym skróconym ostatnim krokiem oraz łączenie kolejnych wykładników tego samego Pauliego realizuje [[code:hamiltonian_kernel/universal_hamiltonian.py#L267-L282]] i [[code:hamiltonian_kernel/universal_hamiltonian.py#L317-L340]].

## 3.15. Hipotezy v3 i ich dopuszczalna interpretacja

Protokół v3 ustala $n\in\{2,3,4,5,6\}$, cztery profile Hamiltonianu, cztery etykiety topologii, dwadzieścia seedów, trzy rzędy $(1,2,4)$ oraz siatkę kroku $0.01,\ldots,1.00$. Głębokość, circuit-shots i 2Q-gate-shots są krzyżowane niezależnie w ośmiu komórkach zasobowych. Definicja: [[code:hamiltonian_kernel/trotter_scaling_v3.py#L150-L188]].

Nie każdy z 300 punktów `(order, step)` przechodzi ocenę jakości. `_cost_screen` proponuje kotwice i kroki wybrane kosztowo, a `_feasible_candidates` zatrzymuje ograniczoną shortlistę, uwzględniając minimalną liczbę shots: [[code:hamiltonian_kernel/trotter_scaling_v3.py#L315-L389]]. Optimum uzyskane przez procedurę jest optimum tej procedury i shortlisty, nie wykazanym globalnym optimum całej siatki.

Hipoteza empiryczna brzmi: wybrane przez inner CV rząd i krok zależą od liczby kubitów oraz ograniczeń zasobowych. Nie jest to twierdzenie, że rząd Trottera jest matematyczną funkcją samego $n$. Już granice z rozdziału 3.3 pokazują zależność od $J,g,x,G,t$; o wyniku klasyfikacji dodatkowo decydują etykiety, regularyzacja, liczba próbek i estymator.

Analiza prerejestrowana rozpatruje dwa wyniki: $\log\delta_t$ i $\log_2p$. Dla każdego seeda dopasowuje regresję liniową obejmującą $n-4$, trzy wskaźniki budżetów, ich trzy interakcje z $n-4$ oraz efekty stałe rodziny i topologii. Siedem współczynników na dwa wyniki daje czternaście kontrastów. Kod zachowuje wyłącznie bloki posiadające wszystkie osiem komórek, wymaga co najmniej dwudziestu klastrów seedów, a następnie bootstrapuje średnie współczynników: [[code:hamiltonian_kernel/trotter_scaling_v3_summary.py#L99-L159]]. To liniowe podsumowanie zachowania polityki; $\log_2p$ jest zmienną o wartościach dyskretnych $0,1,2$, więc współczynnik nie opisuje ciągłego fizycznego „rzędu pośredniego”.

**Twierdzenie 3.14 — warunkowa kontrola Bonferroniego, wyprowadzenie własne.** Jeśli każdy z czternastu przedziałów ma prawdopodobieństwo niepokrycia własnego parametru co najwyżej $\alpha/14$, to prawdopodobieństwo co najmniej jednego niepokrycia jest co najwyżej $\alpha$.

**Dowód.** Dla zdarzeń niepokrycia $E_j$ nierówność sumy daje $\Pr(\bigcup_jE_j)\leq\sum_j\Pr(E_j)\leq14\alpha/14=\alpha$. Niezależność kontrastów nie jest potrzebna. $\square$

Wniosek jest warunkowy: samo nazwanie percentylowego bootstrapu „Bonferroni” nie dowodzi, że każdy przedział ma wymagane skończonopróbkowe pokrycie. Przy dwudziestu seedach i skrajnych kwantylach trzeba sprawdzić stabilność wnioskowania. Odrzucenie niekompletnych bloków dodatkowo ogranicza badaną populację do warunków, w których wszystkie komórki są wykonalne. Nie jest to wynik o niewykonalnych konfiguracjach.

Osobny `protocol.py` benchmarku publikacyjnego stosuje hierarchiczny bootstrap oraz sign-flip na średnich dataset–repeat: [[code:hamiltonian_kernel/protocol.py#L212-L307]]. Dla dokładnego uzasadnienia sign-flip potrzebna jest niezmienniczość wspólnego rozkładu klastrów pod niezależnymi zmianami znaków przy hipotezie zerowej; sama nierówność średniej $\mathbb E\Delta\leq0$ tego nie zapewnia. Dowód testu randomizacyjnego opiera się na równoprawdopodobności elementów orbity transformacji przy takim założeniu. Nakładające się dane repeated CV nie tworzą automatycznie nowych niezależnych datasetów. Można analizować losowość podziałów warunkowo względem ustalonego zbioru, ale wniosek populacyjny na nowe zadania wymaga dodatkowego modelu i nowych jednostek eksperymentalnych.

Zapisany pełny run `analysis_output/trotter_scaling_v3_full_release_20260920/v3_summary.json` ma **1 z 1600 warunków**, 96 outer rows, brak zakończonego holdoutu i `confirmatory_status: not_confirmatory`. To stan sprawdzony podczas opracowywania rozdziału. Zapisane `passed` w audycie dotyczy testowanych warunków integralności artefaktów; nie jest wynikiem testu hipotezy o skalowaniu. Smoke sprawdza wykonanie pipeline'u, a nie pełną hipotezę.

## 3.16. Wnioski recenzenckie i wymagane poprawki

Formalnie poprawne są hermitowskie kodowanie Isinga, unitarne formuły produktowe, definicja fidelity jako Grama operatorów, czynnik $1/2$ w odległości lokalnych redukcji oraz PSD Gaussowskiego kernela na wspólnie estymowanych cechach. Bieżący joint-bitstring estimator projected prawidłowo uwzględnia korelacje obserwabli mierzonych z tych samych shotów.

Trzy ustalenia wymagają rozdzielenia według skutków. **H-01** dotyczy samego estymatora i interpretacji KRR: zmianę należy zamrozić jako nowy protokół oraz ponownie obliczyć wyniki. **H-02** dotyczy rachunku kosztu po selekcji: trzeba zachować rezerwację i obok niej policzyć zużycie; korekta metadanych nie musi zmieniać predykcji. **H-03** dotyczy przypisania widm do właściwych macierzy: należy zapisać widma znormalizowanego train-Grama oddzielnie od widm landmarków przed normalizacją. Nie ma podstaw, by przez błąd etykiet widma odrzucać matematyczny dowód PSD mapy cech.

Wynik publikacyjnego benchmarku zapisany w wcześniejszym audycie — BA około $0.95892$ dla projected, $0.87336$ dla fidelity i $0.97754$ dla SVM-RBF przy wskazanym protokole i budżecie $10^6$ — wspiera opisowy wniosek o odporności wybranej procedury projected względem wybranej procedury fidelity na trzech zadaniach. Nie jest dowodem przewagi nad najlepszym modelem klasycznym, dowodem potrzeby splątania ani potwierdzeniem pełnej hipotezy v3. Te trzy zdania odpowiadają trzem odrębnym pytaniom naukowym.

Najbardziej informacyjne następne sprawdzenia to: regresja symbolicznego przypadku z twierdzenia 3.5; test, że zmiana outer-test labels nie zmienia selekcji; test zgodności rzeczywiście użytego Grama z zapisem `prediction_kernel_stage`; kontrprzykład 3.11 jako test odporności estymatora; porównanie widma zapisanej macierzy z zapisanym widmem; oraz rachunek rezerwacji i kosztu wybranego kandydata. Testy te walidują określone własności implementacji. Ich przejście nie zastępuje niezależnego eksperymentu statystycznego ani dowodu ogólnego twierdzenia o przewadze QML.

### Źródła przypisane do kluczy bibliograficznych

- `suzuki1990`: M. Suzuki, *Fractal decomposition of exponential operators with applications to many-body theories and Monte Carlo simulations*, Physics Letters A 146, 319–323 (1990), https://doi.org/10.1016/0375-9601(90)90962-N. Konstrukcja wyższych rzędów; niniejsze rachunki BCH i granice normowe przedstawiono z własnymi dowodami.
- `havlicek2019`: V. Havlíček i in., *Supervised learning with quantum-enhanced feature spaces*, Nature 567, 209–212 (2019), https://www.nature.com/articles/s41586-019-0980-2.
- `huang2021`: H.-Y. Huang i in., *Power of data in quantum machine learning*, Nature Communications 12, 2631 (2021), https://www.nature.com/articles/s41467-021-22539-9, w szczególności konstrukcja projected kernela oparta na lokalnych redukcjach.
- `schuld2021`: M. Schuld, *Supervised quantum machine learning models are kernel methods* (2021), https://arxiv.org/abs/2101.11020.
- `higham1988`: N. J. Higham, *Computing a nearest symmetric positive semidefinite matrix*, Linear Algebra and its Applications 103, 103–118 (1988), https://doi.org/10.1016/0024-3795(88)90223-6. Przywołanie dotyczy projekcji PSD, nie utożsamienia jej z problemem najbliższej macierzy korelacji.
- `cortes2010`: C. Cortes, M. Mohri, A. Talwalkar, *On the Impact of Kernel Approximation on Learning Accuracy*, PMLR 9, 113–120 (2010), https://proceedings.mlr.press/v9/cortes10a.html.
- `childs2021`: A. M. Childs, Y. Su, M. C. Tran, N. Wiebe, S. Zhu, *Theory of Trotter Error with Commutator Scaling*, Physical Review X 11, 011020 (2021), https://doi.org/10.1103/PhysRevX.11.011020; autorski preprint https://arxiv.org/abs/1912.08854.


# 4. Rezerwuary kwantowe: kanały z pamięcią, odczyt i wnioskowanie

Stan przeglądu: 5 października 2026 r. Rozdział opisuje aktualny kod i zachowane wyniki, a następnie wyprowadza twierdzenia potrzebne do ich interpretacji. Nie jest ponownym wykonaniem eksperymentów. Model należy do obliczeń rezerwuarowych: dynamika wewnętrzna pozostaje ustalona, a uczony jest klasyczny odczyt [@jaeger2001; @fujii2017]. Tożsamość operatorowa, warunkowe twierdzenie o stabilności i potwierdzenie hipotezy empirycznej są różnymi rodzajami wyniku.

## 4.1. Przestrzenie, Hamiltonian i konwencja czasu

Układ składa się z kubitu wejściowego \(I\) i pamięci \(M\):
\[
\mathcal H=\mathcal H_I\otimes\mathcal H_M,\qquad
\mathcal H_I=\mathbb C^2,\quad
\mathcal H_M=(\mathbb C^2)^{\otimes(n-1)}.
\]
Oznaczmy \(D=2^n\), \(d_M=2^{n-1}\). Stan spełnia
\(\rho=\rho^\dagger,\rho\succeq0,\operatorname{Tr}\rho=1\).
Kubit 0 jest najbardziej znaczącym czynnikiem tensorowym w implementacji macierzowej. Adapter Qiskit odwraca numerację przewodów, aby zachować tę konwencję. [[code:quantum_reservoir/core.py#L64-L72]] [[code:quantum_reservoir/ibm_hardware.py#L59-L63]]

Dla \(\hbar=1\) przyjęto
\[
H=A+B,\qquad
A=\sum_i h_iZ_i+J\sum_{(i,j)\in E}Z_iZ_j,\qquad
B=g\sum_iX_i.
\]
Pola \(h_i\) losuje się raz dla danego rezerwuaru. Domyślnie
\(n=4,\tau=0.8,g=0.9,J=0.7\), topologia jest pierścieniem, a
\(h_i\sim U[-0.5,0.5]\). Składniki \(A\) komutują między sobą, podobnie składniki \(B\), lecz na ogół \([A,B]\ne0\). [[code:quantum_reservoir/core.py#L16-L43]] [[code:quantum_reservoir/core.py#L74-L96]]

Dokładna ewolucja to \(U=e^{-i\tau H}\). Kod diagonalizuje hermitowski \(H=V\Lambda V^\dagger\) i składa
\[
U=V\operatorname{diag}(e^{-i\tau\lambda_j})V^\dagger.
\]
Jednostkowy moduł faz dowodzi \(U^\dagger U=I\). Dla \(h=\tau/r\):
\[
U_{1,r}=(e^{-ihB}e^{-ihA})^r,\qquad
U_{2,r}=(e^{-ihA/2}e^{-ihB}e^{-ihA/2})^r.
\]
Prawa macierz działa pierwsza. AB oznacza chronologicznie A, potem B, czyli macierzowo \(U_BU_A\). Wejście jest resetowane raz na \(\tau\), nie po każdym podkroku. Zwiększenie \(r\) nie dodaje nowych wejść ani momentów odczytu. [[code:quantum_reservoir/core.py#L99-L128]] [[code:quantum_reservoir/h3_memory_study.py#L48-L59]]

## 4.2. Reset wejścia jako kanał CPTP

Dla \(u\in[0,1]\):
\[
|\psi(u)\rangle=\sqrt{1-u}|0\rangle+\sqrt u|1\rangle,\qquad
\eta_u=|\psi(u)\rangle\langle\psi(u)|.
\]
Normalizacja wynika z \(1-u+u=1\). Cały krok wynosi
\[
\mathcal R_u(\rho)=\eta_u\otimes\operatorname{Tr}_I\rho,\qquad
\mathcal F_u(\rho)=U\mathcal R_u(\rho)U^\dagger,\qquad
\rho_t=\mathcal F_{u_t}(\rho_{t-1}).
\]
Kod najpierw przycina wejście do \([0,1]\). To część kodowania danych, której częstość należy raportować. [[code:quantum_reservoir/core.py#L167-L193]] [[code:quantum_reservoir/core.py#L228-L241]]

### 4.2.1. Ślad częściowy i operatory Krausa

Zapisując stan blokowo,
\[
\rho=\begin{pmatrix}\rho_{00}&\rho_{01}\\\rho_{10}&\rho_{11}\end{pmatrix},
\qquad \rho_{ab}\in\mathbb C^{d_M\times d_M},
\]
otrzymujemy
\[
(\operatorname{Tr}_I\rho)_{jk}
=\sum_{a=0}^1\rho_{(a,j),(a,k)}
=(\rho_{00}+\rho_{11})_{jk}.
\]
Zmiana kształtu tablicy na \((2,d_M,2,d_M)\) i ślad po pierwszej oraz trzeciej osi realizują ten wzór. [[code:quantum_reservoir/core.py#L173-L186]]

Niech \(K_a=|\psi(u)\rangle\langle a|\otimes I_M\). Wtedy
\[
\sum_aK_a\rho K_a^\dagger
=\eta_u\otimes\sum_a\rho_{aa}=\mathcal R_u(\rho),\qquad
\sum_aK_a^\dagger K_a=I.
\]
Dla dowolnej ancilli i dodatniego operatora \(Q\), każdy
\((K_a\otimes I)Q(K_a^\dagger\otimes I)\) jest dodatni. Suma dowodzi całkowitej dodatniości. Z drugiej tożsamości i cykliczności śladu wynika zachowanie śladu. Sprzężenie unitarne ma jeden operator Krausa \(U\); złożenie z resetem jest zatem CPTP [@watrous2018].

Reset zachowuje zredukowany stan pamięci, ale usuwa wcześniejsze korelacje pamięci z kubitem wejściowym. Nie zachowuje całego poprzedniego stanu. Dla ustalonego \(u\) jest liniowy względem \(\rho\), mimo nieliniowej zależności \(\eta_u\) od zewnętrznego wejścia.

Stan początkowy to \(|0\rangle^{\otimes n}\). Dodatkowe symetryzowanie i normalizacja śladu w transformatorze ograniczają błędy zaokrągleń, lecz same nie dowodzą dodatniości: hermitowska macierz o śladzie jeden może mieć ujemne wartości własne. Dodatniość wynika z konstrukcji kanału; numerycznie warto kontrolować ją niezależnie. [[code:quantum_reservoir/core.py#L189-L193]] [[code:quantum_reservoir/core.py#L234-L240]]

### 4.2.2. Kanał pamięci i redukcja widma

Wprowadźmy
\[
E_u(\sigma)=U(\eta_u\otimes\sigma)U^\dagger,\qquad
P(\rho)=\operatorname{Tr}_I\rho.
\]
Pełny kanał to \(E_uP\), a kanał pamięci \(\mathcal T_u=PE_u\). Jego operatory Krausa wynoszą
\[
L_a=(\langle a|\otimes I_M)U(|\psi(u)\rangle\otimes I_M),\qquad
\mathcal T_u(\sigma)=\sum_aL_a\sigma L_a^\dagger,
\quad \sum_aL_a^\dagger L_a=I_M.
\]
Przy kolumnowej wektoryzacji
\[
\operatorname{vec}(L_a\sigma L_a^\dagger)
=(\overline{L_a}\otimes L_a)\operatorname{vec}(\sigma).
\]
Macierz ma więc wymiar \(64\times64\) dla fizycznego układu czterokubitowego. [[code:quantum_reservoir/h3_memory_study.py#L117-L127]]

Niezerowe widma \(E_uP\) i \(PE_u\) są takie same. Jeżeli \(E_uPv=\lambda v\), \(\lambda\ne0\), to \(Pv\ne0\) i \(PE_u(Pv)=\lambda Pv\). Odwrotną konstrukcję daje \(E_uw\). Krotności algebraiczne wynikają z tożsamości \(\det(I-zE_uP)=\det(I-zPE_u)\). Redukcja reprezentacji nie zmienia liczby fizycznych kubitów. To inna operacja niż starsza diagnostyka spektralna wykonana rzeczywiście dla \(n=3\), przy predykcji dla \(n=4\). [[code:quantum_reservoir/spectral_h1_h2_study.py#L156-L162]]

## 4.3. Obserwable, prawo Borna i kowariancja shots

Podstawowy odczyt tworzą \(X_i,Z_i,Z_iZ_j\) na krawędziach. Dla czterokubitowego pierścienia jest \(m=12\) cech:
\[
f_j(t)=\operatorname{Tr}(\rho_tO_j),\qquad -1\le f_j(t)\le1.
\]
W predykcji dołącza się bieżące \(u_t\); w diagnostyce pamięci tego dodatku nie ma. [[code:quantum_reservoir/core.py#L195-L208]] [[code:quantum_reservoir/experiment.py#L116-L123]] [[code:quantum_reservoir/h3_noise_study.py#L203-L208]]

Warianty rozszerzone obejmują wszystkie słowa Pauliego wagi najwyżej dwa albo wszystkie nieidentycznościowe słowa:
\[
m_{\le2}=3n+9\binom n2=66,\qquad m_{\rm full}=4^n-1=255.
\]
Z \(\operatorname{Tr}(P_jP_k)=D\delta_{jk}\) wynika rekonstrukcja
\[
\rho=D^{-1}\left(I+\sum_j f_jP_j\right).
\]
Pełny wektor idealnych oczekiwań wyznacza stan, ale jego odczyt ma wykładniczy koszt. Liniowy readout z tego wektora nadal nie jest dowolnym nieliniowym dekoderem stanu. [[code:quantum_reservoir/h3_memory_study.py#L31-L45]]

Dla bazy \(s\) i bitstringu \(b\):
\[
p_s(b)=\operatorname{Tr}(\rho\Pi_{s,b}),\qquad \sum_bp_s(b)=1.
\]
Obserwabli zgodnej z bazą przypisujemy \(o_j(b)\in\{-1,+1\}\). Dla \(S\) niezależnych powtórzeń:
\[
\widehat f_j=S^{-1}\sum_{\ell=1}^So_j(B_\ell),\quad
\mathbb E\widehat f_j=f_j,\quad
\operatorname{Var}(\widehat f_j)=\frac{1-f_j^2}{S}.
\]
Wariancja pojedynczego wyniku wynosi \(1-f_j^2\), ponieważ \(o_j^2=1\); wariancja średniej niezależnych wyników jest \(S\) razy mniejsza.

Jeśli dwie cechy pochodzą z tych samych bitstringów:
\[
\operatorname{Cov}(\widehat f_i,\widehat f_j)
=\frac{\mathbb E[o_i(B)o_j(B)]-f_if_j}{S}
=\frac{\operatorname{Tr}(\rho O_iO_j)-f_if_j}{S}.
\]
Dla pary Bella wyniki \(Z_0\) i \(Z_1\) są zawsze identyczne. Niezależne losowanie binomialne ich estymatorów zniszczyłoby korelację i zmieniło rozkład wejść ridge. Kod poprawnie losuje wspólne zliczenia wielomianowe dla grupy, a następnie oblicza wszystkie przypisane parzystości. [[code:quantum_reservoir/h3_noise_study.py#L104-L144]]

Dwanaście cech wymaga dwóch baz globalnych: X i Z. Dla 66 cech zastosowano dziewięć ustawień \((s,t,s+t,s+2t)\) nad \(\mathbb F_3\). Każde dwie współrzędne są liniowo niezależnymi funkcjonałami \((s,t)\), więc przebiegają wszystkie dziewięć par osi X/Y/Z. Pokrywa to każdą obserwablę dwukubitową. Pełny odczyt używa \(3^4=81\) ustawień. Każdy operator przypisany jest do jednej zgodnej grupy; kod nie łączy jego estymat z kilku baz.

Błąd przypisania odczytu to osobna operacja:
\[
C=\begin{pmatrix}1-e_{01}&e_{01}\\e_{10}&1-e_{10}\end{pmatrix},
\qquad p'=pC^{\otimes n}.
\]
Dla jednego Z:
\[
\mathbb E[Z_{\rm measured}]
=(1-e_{01}-e_{10})\langle Z\rangle+e_{10}-e_{01}.
\]
Asymetria daje zarówno skurczenie, jak i przesunięcie. Nieskończone shots usuwają wariancję próbkowania, lecz nie to obciążenie. Tak zdefiniowano tryb expectation w badaniu szumu. [[code:quantum_reservoir/h3_noise_study.py#L124-L134]] [[code:quantum_reservoir/h3_noise_study.py#L191-L202]]

## 4.4. Ridge: wyraz wolny, normalizacja i stabilność

Niech \(X\in\mathbb R^{N\times m}\) zawiera cechy aktualnego zbioru dopasowania:
\[
\mu_j=N^{-1}\sum_iX_{ij},\quad
s_j^2=N^{-1}\sum_i(X_{ij}-\mu_j)^2,\quad
Z_{ij}=(X_{ij}-\mu_j)/s_j.
\]
Skale mniejsze niż \(10^{-12}\) zastępuje się przez 1. Minimalizowane kryterium to
\[
J(b,w)=\|y-b\mathbf1-Zw\|_2^2+\alpha\|w\|_2^2,\qquad \alpha>0.
\]
Wyraz wolny nie jest karany. Ponieważ \(\mathbf1^\top Z=0\), różniczkowanie względem \(b\) daje \(b=\bar y\). Warunek względem \(w\) prowadzi do
\[
(Z^\top Z+\alpha I)w=Z^\top(y-\bar y\mathbf1).
\]
Jednoznaczność wynika z
\(v^\top(Z^\top Z+\alpha I)v=\|Zv\|^2+\alpha\|v\|^2>0\)
dla \(v\ne0\). Implementacja rozwiązuje układ równań bez jawnej inwersji. [[code:quantum_reservoir/experiment.py#L65-L86]]

Predykcja nowych cech:
\[
\widehat y(x)=\bar y+\sum_jw_j(x_j-\mu_j)/s_j.
\]
W surowych współrzędnych \(\beta_j=w_j/s_j\) i
\(b_{\rm raw}=\bar y-\sum_j\beta_j\mu_j\).
To \(\beta\), nie samo \(w\), wyznacza wrażliwość na fizyczny błąd cech. Mała skala sygnału może dawać duży surowy współczynnik mimo umiarkowanej kary na \(w\).

Zapis ze średnią stratą,
\[
N^{-1}\|y-b\mathbf1-Zw\|^2+\lambda\|w\|^2,
\]
jest równoważny przy \(\alpha=N\lambda\). Zachowanie tej samej liczby \(\alpha\) po refit na train+validation zmniejsza efektywne \(\lambda\); nie jest dosłownie niezmienioną siłą kary względem średniej straty.

Dla wielu celów rozkłada się raz \(Z^\top Z=V\Lambda V^\top\):
\[
w_k(\alpha)=V(\Lambda+\alpha I)^{-1}V^\top Z^\top(Y_k-\bar Y_k).
\]
Jest to równoważne osobnym rozwiązaniom. Każda kolumna celu wybiera \(\alpha\) na validation, a średnie, skale i współczynniki są potem obliczane ponownie na train+validation. Test nie uczestniczy w dopasowaniu. [[code:quantum_reservoir/h3_memory_study.py#L87-L114]]

Istnieje różnica reguł remisu: starszy moduł minimalizuje \((E_{\rm val},\alpha)\), wybierając mniejsze \(\alpha\); moduł spektralny minimalizuje \((E_{\rm val},-\alpha)\), a H3 przegląda siatkę malejąco. Protokół przewiduje tolerancję remisu \(10^{-12}\), której zwykłe minimum leksykograficzne nie realizuje. Nowa próba powinna używać jednej jawnej funkcji wyboru. [[code:quantum_reservoir/experiment.py#L125-L135]] [[code:quantum_reservoir/spectral_h1_h2_study.py#L62-L73]] [[code:quantum_reservoir/h3_memory_study.py#L97-L106]]

### 4.4.1. Warunkowa granica perturbacji ridge

Załóżmy ustalony preprocessing i wspólne \(\lambda>0\). Dla wycentrowanych danych niech
\(\|x_i\|\le R,\|\widetilde x_i-x_i\|\le\delta,|y_i|\le Y\).
Oznaczając \(G=N^{-1}X^\top X,b=N^{-1}X^\top y\), mamy
\[
\|b\|\le RY,\quad \|\widetilde b-b\|\le\delta Y,\quad
\|\widetilde G-G\|\le2R\delta+\delta^2.
\]
Ostatnia granica wynika z rozwinięcia iloczynu
\((x_i+\Delta_i)(x_i+\Delta_i)^\top\) na dwa składniki mieszane i \(\Delta_i\Delta_i^\top\).
Ponieważ \(\|(G+\lambda I)^{-1}\|\le1/\lambda\), \(\|w\|\le RY/\lambda\). Odejmując równania normalne:
\[
(\widetilde G+\lambda I)(\widetilde w-w)
=(\widetilde b-b)-(\widetilde G-G)w,
\]
otrzymujemy
\[
\|\widetilde w-w\|
\le\frac{\delta Y}{\lambda}
+\frac{(2R\delta+\delta^2)RY}{\lambda^2}.
\]
Dla cechy testowej spełniającej te same ograniczenia:
\[
|\widetilde x^\top\widetilde w-x^\top w|
\le\delta RY/\lambda+(R+\delta)\|\widetilde w-w\|.
\]
Odwrotna nierówność trójkąta daje dalej
\[
|\operatorname{RMSE}(\widetilde y)-\operatorname{RMSE}(\widehat y)|
\le\sqrt{N_{\rm test}^{-1}\sum_t|\widetilde y_t-\widehat y_t|^2}.
\]
Podzielenie przez niezerowe odchylenie celu daje granicę NRMSE. Założenia są mocniejsze od aktualnego eksperymentu: konfiguracje mają własne skale i własne \(\alpha\). Zastosowanie lematu wymaga dodatkowej kontroli tych zmian.

## 4.5. Kontrakcja, ESP i skończone okno historii

Odległość śladowa to
\[
D_{\rm tr}(\rho,\sigma)=\tfrac12\|\rho-\sigma\|_1\in[0,1].
\]
Dla wspólnego kanału CPTP i tego samego wejścia nie może wzrosnąć. Dowód wykorzystuje dualną normę:
\[
\|\Phi(X)\|_1
=\max_{-I\preceq A\preceq I}\operatorname{Tr}[\Phi^\dagger(A)X],
\qquad X=X^\dagger.
\]
Dualny kanał jest dodatni i unitalny. Z \(I\pm A\succeq0\) wynika
\(I\pm\Phi^\dagger(A)\succeq0\). Maksimum jest więc brane po podzbiorze zbioru definiującego \(\|X\|_1\), co daje
\[
D_{\rm tr}(\Phi(\rho),\Phi(\sigma))\le D_{\rm tr}(\rho,\sigma)
\]
[@watrous2018]. Nieekspansywność nie oznacza ścisłej kontrakcji.

### 4.5.1. Dlaczego pojedynczy reset nie daje \(q<1\)

Weźmy ortogonalne stany pamięci \(|a\rangle,|b\rangle\) oraz
\[
\rho=|0\rangle\langle0|\otimes|a\rangle\langle a|,\qquad
\sigma=|0\rangle\langle0|\otimes|b\rangle\langle b|.
\]
Początkowa odległość wynosi jeden. Reset zastępuje wspólny czynnik wejściowy przez \(\eta_u\), pozostawiając ortogonalne czynniki pamięci. Norma śladowa iloczynu tensorowego jest iloczynem norm, więc odległość nadal wynosi jeden. Wspólne \(U\) jej nie zmienia. Współczynnik kontrakcji pełnego kroku, liczony po wszystkich parach stanów, jest zatem dokładnie jeden dla każdego \(u,U,n\ge2\).

Zachowany results/qrc/spectral_checks.json podaje \(1.000000000000001\), zgodne z tożsamością do błędu zaokrąglenia. [[code:quantum_reservoir/spectral_h1_h2_study.py#L334-L353]]

### 4.5.2. Warunkowe zapominanie blokowe

Załóżmy dodatkowo istnienie \(L\in\mathbb N\), \(0\le q<1\), takich że dla **każdej** dozwolonej sekwencji długości \(L\) i dowolnych stanów:
\[
D_{\rm tr}(\mathcal F_{u_L}\cdots\mathcal F_{u_1}(\rho),
\mathcal F_{u_L}\cdots\mathcal F_{u_1}(\sigma))
\le qD_{\rm tr}(\rho,\sigma).
\tag{QRC-C}
\]
Jest to założenie jednostajne po wejściach i stanach, nie rezultat skończonego wykresu washout.

Pełna trajektoria i odtworzenie ostatnich \(W\) wejść ze stanu zerowego różnią się przed oknem o odległość co najwyżej jeden. Dla \(W=kL+s\), \(0\le s<L\), stosujemy \(k\) razy (QRC-C), a potem nieekspansywność:
\[
D_{\rm tr}(\rho_t,\rho_t^{(W)})\le q^{\lfloor W/L\rfloor}.
\]
Dla obserwabli o normie najwyżej jeden dualność norm daje
\[
|f_j(t)-f_j^{(W)}(t)|\le2q^{\lfloor W/L\rfloor}.
\]
Przy zamrożonym odczycie w surowych współrzędnych:
\[
|\widehat y_t-\widehat y_t^{(W)}|
\le2\|\beta\|_1q^{\lfloor W/L\rfloor}
\le2\sqrt m\|\beta\|_2q^{\lfloor W/L\rfloor}.
\]
Dla \(0<q<1\) wystarcza liczba pełnych bloków
\(k\ge\log(2\|\beta\|_1/\varepsilon_y)/(-\log q)\), jeśli licznik jest dodatni. Ponowne uczenie readoutu wymaga również kontroli perturbacji estymatora.

Kod replay obejmuje bieżące wejście i \(W-1\) poprzednich; dla \(W\ge t+1\) odtwarza pełną historię. Krótsze okno rozpoczyna cały rezerwuar od stanu zerowego. To zmiana modelu cech, nie obcięcie tabeli już policzonej dla pełnej historii. [[code:quantum_reservoir/ibm_hardware.py#L109-L141]]

### 4.5.3. Widmo zamrożonego kanału nie certyfikuje ESP

Przy zmiennych wejściach występują iloczyny różnych macierzy kanałów. Ich zachowanie nie wynika automatycznie z promieni spektralnych każdej macierzy osobno, a pomiar jednego punktu \(u=0.5\) daje jeszcze mniej informacji. Potrzebna jest wspólna kontrola iloczynów lub odpowiednia wspólna norma.

Nienormalność może powodować wzrost normy współrzędnych, na przykład euklidesowej. Nie może jednak sprawić, że wspólny kanał CPTP zwiększy fizyczną odległość śladową: dowód powyżej to wyklucza. Kod jawnie nazywa widmo zamrożonego wejścia diagnostyką. [[code:quantum_reservoir/spectral_h1_h2_study.py#L94-L118]]


# 4B. Pamięć, propagacja błędów i hipotezy rezerwuarowe

## 4B.1 Pamięć liniowa i nieliniowa: co mierzy readout

Dla opóźnienia d celem liniowym jest v_{t−d}, gdzie v=√3(2u−1). Dla u iid Uniform[0,1] mamy E[v]=0 i E[v²]=1. Cel product v_{t−d}v_{t−d−1} ma również średnią zero i wariancję jeden, dzięki niezależności różnych chwil. Cel quadratic √5 P₂(2u_{t−d}−1), P₂(x)=(3x²−1)/2, ma średnią zero i normę L² równą jeden. Znormalizowane wielomiany Legendre'a są ortogonalne dla wejścia jednostajnego. Implementacja: [[code:quantum_reservoir/h3_memory_study.py#L75-L84]].

Rodzina linear/product/quadratic z opóźnieniami 1–20 stanowi skończony podzbiór zadań. Nie obejmuje wszystkich stopni wielomianowych ani wszystkich iloczynów opóźnień; jej suma nie jest pełną information processing capacity. Oryginalny framework pojemności przetwarzania odnosi się do ortogonalnych rodzin celów i określonych warunków readoutu. [@dambre2012]

Dla konkretnej próby testowej definiujemy C(d)=1−Σ(y_t−ŷ_t)²/Σ(y_t−ȳ)². Jest to testowe R² readoutu, zależne od liczby danych, regularizacji, wyboru obserwabli i podziału. W granicy populacyjnej optymalnego liniowego rzutu, po wycentrowaniu celu y i cech f, otrzymujemy:

```math
\Sigma_f=\mathbb E[ff^T],\quad c=\mathbb E[fy],\quad
w^*=\Sigma_f^+c,\qquad
C_{\rm pop}=\frac{c^T\Sigma_f^+c}{\mathbb E[y^2]}.
```

**Dowód.** E[(y−wᵀf)²]=E[y²]−2wᵀc+wᵀΣ_fw. Normal equations Σ_fw=c dają optimum na obrazie Σ_f, pseudoodwrotność wybiera rozwiązanie minimalnej normy. Przy x w jądrze Σ_f mamy E[(xᵀf)²]=0, więc xᵀc=0 i układ jest spójny. Podstawienie redukuje MSE o cᵀΣ_f^+c. Optymalne C_pop leży w [0,1], ale skończonopróbkowe C_test z wyuczonym w może być ujemne.

Dla ortonormalnych celów w L² i podprzestrzeni readoutu rzędu r suma squared projection norms nie przekracza r. **Dowód:** wybierz ortonormalną bazę g₁,…,g_r podprzestrzeni cech. Dla celów y_j, C_j=Σ_a|⟨g_a,y_j⟩|²; po zamianie sum nierówność Bessela daje Σ_jC_j≤Σ_a||g_a||²=r. To granica populacyjna optymalnych projekcji. Nie uprawnia do obcinania ujemnych C_test ani do przypisywania granicy r=4^n−1 readoutowi z tylko lokalnymi X,Z,ZZ.

W archiwum H3 T=(product10−linear10)/10. Wzrost T może pochodzić z mniejszej linear10 przy niezmienionej lub spadającej product10. Dlatego wymagamy równoległego wykresu obu składowych. Porównania widoków full_Pauli i local_XZ_ZZ badają dostępność informacji dla odczytu, a nie zmianę samego stanu.

## 4B.2 Propagacja błędu Trottera przez pamięć

Niech F_u i F̃_u będą dokładnym i przybliżonym kanałem kroku. Załóżmy sup_ρ D(F_uρ,F̃_uρ)≤ε_u. Nieekspansywność obu kanałów daje dla trajektorii z tym samym wejściem e_t=D(ρ_t,ρ̃_t)≤e_{t−1}+ε_{u_t}. Stąd e_t≤e₀+Σ_{j≤t}ε_{u_j}, z trywialną fizyczną granicą e_t≤1. To oszacowanie nie wymaga ESP.

Przy dodatkowej jednostajnej kontrakcji dokładnego kanału z q<1 otrzymujemy silniejszą rekurencję:

```math
e_t\le qe_{t-1}+\varepsilon,
\qquad e_t\le q^te_0+\varepsilon\frac{1-q^t}{1-q}.
```

**Dowód.** Dodajemy i odejmujemy F_{u_t}(ρ̃_{t−1}), stosujemy kontrakcję do pierwszej różnicy i granicę błędu modelu do drugiej. Iteracja rekurencji daje szereg geometryczny. Dla blokowej kontrakcji stosujemy argument do całego bloku L; ε_block można ograniczyć przez sumę błędów jego kroków. Założenie kontrakcji musi być udowodnione dla dozwolonej rodziny wejść albo jawnie pozostawać warunkowe.

Normowa granica jednostki ||U−Ũ||₂≤a prowadzi do ε≤a przez wyprowadzenie z rozdziału 1. Błąd cech jest ≤2√m e_t, a dla zamrożonego readoutu błąd predykcji ≤2||w||₁e_t. Nie ma z tego gwarancji, że poprawa operatorowa poprawi testowy NRMSE: po zmianie kanału readout jest ponownie dopasowywany, a target nie musi odpowiadać dokładnej dynamice.

## 4B.3 Rejestr QRC-H1–H5

Poniższe tezy pochodzą z [[file:quantum_reservoir/RESEARCH_PROTOCOL_H1_H5.md]]. Wszystkie dotyczą jawnych estymandów i konfiguracji. Ich kompletne potwierdzenie wymaga planu dwudziestu bloków i korekty pięciu testów; zachowane stresowe n=8 nie realizuje automatycznie tego planu.

**QRC-H1, non-inferiority:** ustalone p=2,r=2 ma średni log-iloraz błędów względem exact mniejszy niż log1.02, a logiczny koszt 2Q na wejście jest co najmniej 25% niższy od p=2,r=16. H0_quality:μ≥log1.02. Koszt to warunek deterministyczny obwodu; test jakości i ten warunek muszą przejść razem. Przy identycznej dekompozycji i niezerowych sprzężeniach osiem razy mniej powtórzeń bloku oznacza osiem razy mniej jego bramek 2Q; nie wyznacza całego czasu QPU, bo reset i pomiar mają inne koszty.

**QRC-H2, superiority:** wybór (p,r) wyłącznie po validation z zadeklarowanej siatki daje mean log(E_selected/E_exact)<log0.98. Regularizacja jest dobierana osobno każdej metodzie. H0:μ≥log0.98. Wybór lepszego wyniku exact diagnostycznie po testach nie spełnia protokołu. Wartość ilorazu 0.99 oznacza małą poprawę, lecz nie spełnia progu co najmniej 2%.

**QRC-H3, profil pamięci:** ustalone p=1,r=1 zmienia T względem exact. Test dwustronny H0:E[T_trotter−T_exact]=0. Dodatkowe zadania i obserwable są kontrolami. Korelacja T z NRMSE nie jest dowodem mediacji przyczynowej. Potwierdzenie zmiany nie musi oznaczać korzystnego kompromisu.

**QRC-H4, interakcja budżetu i schematu:** kontrast d_low−d_high porównuje log-ilorazy NRMSE p=2,r=2 versus r=16 przy dwóch wspólnych budżetach C₂Q. H0:średni kontrast=0. Liczba shots wynika z kosztu obwodów, więc porównanie celowo sprzęga głębokość i pomiary. Osobna kontrola equal-shots jest potrzebna do rozdzielenia czynników.

**QRC-H5, łączna oszczędność:** na validation wybieramy (p,r,W) najtańsze wśród konfiguracji o NRMSE≤1.02 reference. Test wymaga jakości <1.02 oraz geometrycznego kosztu wdrożenia <0.75 reference. Zerowa hipoteza jest sumą niepowodzeń jakości i kosztu; p_H5=max(p_quality,p_cost). Koszt wyboru polityki raportuje się dodatkowo, a nie odlicza od testowanego kosztu wdrożenia. Dowód IUT i Holma znajduje się w rozdziale 8.

## 4B.4 Chronologia i preprocessing

Starszy generator MG skaluje całym szeregiem; nowy mg_data wyznacza min/max z indeksów TRAIN i dopiero potem ogranicza wartości do [0,1]. Kod: [[code:quantum_reservoir/spectral_h1_h2_study.py#L75-L91]]. Etykiety są raw[t+5], więc trzeba rozdzielić czas cechy i czas dostępności celu. Podziały nowej ścieżki mają luki; refit train+validation dla końcowej oceny jest legalny, jeśli test był zamrożony i reguła została zadeklarowana: [[code:quantum_reservoir/spectral_h1_h2_study.py#L26-L32]], [[code:quantum_reservoir/spectral_h1_h2_study.py#L44-L72]].

Train-only scaling jest wymagane, ponieważ skaler dopasowany na teście jest funkcją testowego ogona. Można to wykazać kontrprzykładem: zostaw wszystkie dane train bez zmian i zwiększ jeden testowy maksimum. Przy globalnym minmax zmienią się wszystkie znormalizowane wartości train. Przy scalerze train-only nie zmieni się ani trening, ani wybory validation. Takie sprawdzenie invariance jest mocniejsze niż sama deklaracja „bez przecieku”.

Washout 200 to decyzja protokołu. Dowód ESP wymaga warunków dla wszystkich dopuszczalnych wejść, nie tylko zaniku różnic na kilku trajektoriach. Warunkowe granice wcześniejszego rozdziału należy czytać razem z kontrprzykładem jednostkowego resetu. Dla zamrożonych unitarnych kierunków pamięci może przetrwać zależność od inicjalizacji.

## 4B.5 CV: dokładna transformacja symplektyczna

Dla jednego modu przy [q,p]=i i H=p²/2+ω²q²/2 równania Heisenberga dają q̇=p, ṗ=−ω²q. Dla R=(q,p)ᵀ macierz generatora G=[[0,1],[−ω²,0]]. R(t)=S(t)R(0), S=exp(tG). Przy ω>0:

```math
S_{\rm ex}(h)=\begin{bmatrix}
\cos(\omega h)&\sin(\omega h)/\omega\\
-\omega\sin(\omega h)&\cos(\omega h)
\end{bmatrix}.
```

Dla części kinetycznej S_A(h)=[[1,h],[0,1]], a potencjalnej S_B(h)=[[1,0],[−ω²h,1]]. To ścinania o wyznaczniku jeden. Strang S_A(h/2)S_B(h)S_A(h/2) daje przez zwykłe mnożenie:

```math
S_2(h)=\begin{bmatrix}
1-\omega^2h^2/2&h(1-\omega^2h^2/4)\\
-\omega^2h&1-\omega^2h^2/2
\end{bmatrix},\quad
\det S_2=1,\quad\operatorname{Tr}S_2=2-\omega^2h^2.
```

Dla rzeczywistej 2×2 macierzy wyznacznika jeden wartości własne spełniają λ²−(TrS)λ+1=0. Przy |TrS|<2 są sprzężone zespolone o module jeden. Przy |TrS|>2 jedna ma moduł >1. Na granicy |TrS|=2 może występować blok Jordana i wzrost wielomianowy. Stabilność oscylacyjna Stranga wymaga zatem |ωh|<2; samo wyznacznik jeden nie wystarcza. Exact oscylatora nie ma tego ograniczenia kroku. Kod: [[code:quantum_reservoir/spectral_h1_h2_study.py#L219-L226]].

## 4B.6 Tłumienie i kontrprzykład stabilności

Kanał strat o transmisyjności η przekształca mean m w √η Sm, a covariance V w ηSVSᵀ+(1−η)I/2. Średnia z wejściowym displacementem d_t spełnia m_t=M(m_{t−1}+d_t), M=√η S. Dla stałego M, ρ(M)<1 gwarantuje zanik M^k i jednoznaczną stacjonarną kowariancję:

```math
V_* = \sum_{k=0}^{\infty}M^k\frac{1-\eta}{2}I(M^T)^k.
```

**Dowód.** Rozwijamy rekurencję Lyapunova do czasu T. Początkowy składnik M^TV₀(Mᵀ)^T zanika, a szereg norm jest zbieżny przy ρ(M)<1 w skończonym wymiarze. Różnica dwóch ewentualnych rozwiązań spełnia Δ=MΔMᵀ i po iteracji musi być zero. Dla bounded displacementów splot ΣM^jd_{t−j} jest także ograniczony. To twierdzenie o stałej mapie momentów, nie uniwersalne ESP nieliniowego kubitowego reservoiru.

Ustal ω=1,h=3,η=0.8. Exact ma eigenvalue moduli √0.8≈0.894427. Strang ma trace −7, więc własne wartości (−7±√45)/2, z których dominująca ma moduł około 6.85410. Po √η daje 6.13050>1. Tłumiony exact jest stabilny, a przybliżony r=1 niestabilny. Zwiększenie liczby kroków do r=2 daje h=1.5 wewnątrz strefy oscylacyjnej. Numeryczne sprawdzenie zachowano w [[code:quantum_reservoir/spectral_h1_h2_study.py#L334-L353]] i [[file:results/qrc/spectral_checks.json]].

Dla ω²=0 część potencjalna znika i split jest dokładny. Dla ω²<0 exact ma rozrost hiperboliczny; odpowiednio silne η może ustabilizować momenty, ale sama dodatniość kanału nie oznacza ograniczonej energii. Kod kontroluje peak photons i przerwanie przy 10^9 jako zabezpieczenie symulatora, nie jako fizyczny model saturacji.

## 4B.7 Cutoff nie jest neutralnym przepisaniem CV

W cutoff d operator a ma elementy √k na naddiagonali. Bezpośrednie mnożenie daje [a,a†]=I−d|d−1⟩⟨d−1|, zamiast I. **Dowód:** diagonala aa† to (1,2,…,d−1,0), a a†a to (0,1,…,d−1); różnica ma ostatni wpis −(d−1). Zatem błąd relacji kanonicznej skupia się na granicy, a jego norma operatorowa rośnie z d. Mała masa stanu przy granicy może mimo to dawać dobrą zgodność oczekiwań; wymaga kontroli stanowo zależnej.

Dla coherent state o amplitudzie α masa poza cutoff d to tail Poissona o średniej |α|². Renormalizacja obciętego wektora zmienia stan, a ewolucja obciętego Hamiltonianu może wytworzyć dalszy błąd graniczny. Kod sprawdza initial_tail_mass, boundary_mass_last2 i q²_error_vs_gaussian: [[code:quantum_reservoir/spectral_h1_h2_study.py#L267-L291]]. Należy zwiększać cutoff i porównywać odpowiedni moment, zamiast zakładać, że dwa różne cutoffy są tą samą fizyczną reprezentacją.

## 4B.8 Status wyników i następny eksperyment

Badania spektralne, H3 i szumu wykorzystują archiwalne bloki, w tym kontrasty n=8. Zgodność zapisanych hashy z wynikami potwierdza integralność materiału, nie niezależną replikację. Pełna próba potwierdzająca QRC-H1–H5 pozostaje osobnym planem. Przed jej wykonaniem trzeba zamrozić preprocessing, rodzinę testów, reguły wyboru, tryb replay, jednostkę blokową i koszt train/validation/test. Wyniki negative są równie informacyjne jak positive: mogą wyznaczyć reżim, w którym mały krok jest konieczny lub pamięć nie jest użyteczna dla konkretnego readoutu.


# 5. Fotonika: od stanu gaussowskiego do estymowanego jądra

## 5.1. Co rzeczywiście realizuje ta gałąź

Gałąź `photonic_kernel` implementuje lokalny model ośmiu modów optycznych: cztery pary dwumodowej ściśniętej próżni, dwa identyczne interferometry czteromodowe oraz pomiar liczby fotonów. Następnie klasyczny program konstruuje cechy i jądra. Jest to odrębna hipoteza fizyczna od kubitowego jądra Hamiltonianowego. Zgodność topologii z X8 nie jest dowodem wykonania sprzętowego, a dodatnia półokreśloność macierzy jądra nie jest dowodem przewagi predykcyjnej.

Program obwodu odtwarza tę topologię w [[code:photonic_kernel/xanadu_x8.py#L220-L239]], a walidator sprawdza m.in. unitarność, serializację oraz budżet w [[code:photonic_kernel/xanadu_x8.py#L100-L197]]. Aparatura X8 jest opisana w pracy [@arrazola2021], a środowisko symulacyjne w [@killoran2019]. Poniższe wyprowadzenia dotyczą modelu w kodzie, nie certyfikacji konkretnego urządzenia.

## 5.2. Stany, rozkłady i funkcje charakterystyczne

Dla $m$ modów przyjmijmy $[a_j,a_k^\dagger]=\delta_{jk}$ oraz

$$
q_j=\frac{a_j+a_j^\dagger}{\sqrt2},\qquad
p_j=\frac{a_j-a_j^\dagger}{i\sqrt2},\qquad
R=(q_1,p_1,\ldots,q_m,p_m)^T.
$$

W tej konwencji $[R_j,R_k]=i\Omega_{jk}$, a macierz kowariancji próżni wynosi $I_{2m}/2$. Stan opisują operator gęstości $\rho\succeq0$, $\operatorname{Tr}\rho=1$, wektor $d=\operatorname{Tr}(\rho R)$ i

$$
V_{jk}=\frac12\operatorname{Tr}\rho\{R_j-d_j,R_k-d_k\}.
$$

Kwantowa funkcja charakterystyczna Weyla ma postać

$$
\chi_\rho(t)=\operatorname{Tr}[\rho e^{it^TR}],\qquad
\chi_\rho(t)=\exp\left(it^Td-\frac12t^TVt\right)
\quad\text{dla stanu gaussowskiego}.
$$

Warunek fizyczności to $V+i\Omega/2\succeq0$. Samo dodatnie określenie klasycznej macierzy $V$ nie wystarcza. „Gaussowski” opisuje tutaj kwadratury, nie rozkład liczby fotonów. Próżnia jest gaussowska, ale jej rozkład PNR jest skupiony w zerze.

Dla mieszanki stanów $\rho=\sum_\lambda w_\lambda\rho_\lambda$, $w_\lambda\ge0$, $\sum_\lambda w_\lambda=1$, liniowość śladu daje

$$
\chi_\rho(t)=\sum_\lambda w_\lambda\chi_{\rho_\lambda}(t),\qquad
p_\rho(n)=\sum_\lambda w_\lambda p_{\rho_\lambda}(n).
$$

Mieszanka stanów gaussowskich na ogół nie jest stanem gaussowskim: suma wykładniczych form kwadratowych nie musi być jedną taką formą. Inny przypadek stanowi kanał strat działający na stan gaussowski; on zachowuje gaussowskość, choć na ogół usuwa czystość. Te rozróżnienia są potrzebne, aby nie stosować wzoru dla czystego GBS do dowolnego zaszumionego stanu.

Klasyczna funkcja charakterystyczna wyniku PNR jest innym obiektem:

$$
\Phi_x(t)=\mathbb E_x e^{it\cdot N}
=\sum_{n\in\mathbb N^m}p(n\mid x)e^{it\cdot n}.
$$

Jeżeli momenty istnieją, to $\partial_{t_j}\Phi_x(0)=i\mathbb E N_j$ oraz $\partial_{t_j}\partial_{t_k}\Phi_x(0)=-\mathbb E N_jN_k$. Nie wolno utożsamiać $\Phi_x$ z $\chi_{\rho(x)}$: pierwsza dotyczy operatorów liczby fotonów, druga kwadratur.

## 5.3. Źródło TMSV i dokładna normalizacja

Przy ustalonej konwencji fazy dwumodowa ściśnięta próżnia ma rozwinięcie

$$
|\operatorname{TMSV}(r)\rangle
=\frac1{\cosh r}\sum_{k=0}^\infty(\tanh r)^k|k,k\rangle.
$$

Suma geometryczna dowodzi normalizacji:

$$
\frac1{\cosh^2r}\sum_{k=0}^\infty\tanh^{2k}r
=\frac{1-\tanh^2r}{1-\tanh^2r}=1.
$$

Dla $q=\tanh^2r$ dostajemy $\Pr(K=k)=(1-q)q^k$, $\mathbb E K=q/(1-q)=\sinh^2r$. Para emituje $2K$ fotonów. Globalny znak amplitudy pary zależy od konwencji operatora ściskania; przy jednakowej zmianie faz wszystkich źródeł nie wpływa on na prawdopodobieństwa PNR. W modelu należy jednak zachować spójną konwencję, zwłaszcza przy różnych fazach źródeł.

W projekcie $m=8$, a macierz źródła ma bloki

$$
B_0=\begin{pmatrix}0&D_r\\D_r&0\end{pmatrix},
\qquad D_r=\operatorname{diag}(\tanh r_1,\ldots,\tanh r_4).
$$

Dane sterują interferometrem

$$
U(x)=R_2\operatorname{diag}(e^{i\pi\alpha x_1},\ldots,e^{i\pi\alpha x_4})R_1,
\quad W(x)=U(x)\oplus U(x),\quad B(x)=W(x)B_0W(x)^T.
$$

Koduje to [[code:photonic_kernel/core.py#L126-L160]]. Ponieważ $W$ jest unitarny, $B=B^T$ oraz wartości singularne $B$ są takie jak $B_0$, czyli $\tanh r_j$ każda dwukrotnie. Dla skończonych $r_j$ są mniejsze od jedności. Transpozycja w $WB_0W^T$ jest konieczna: operator tworzenia par zawiera dwa operatory kreacji, a nie operator i jego sprzężenie.

Jest też dokładna redundancja kodowania:

$$
U(x+c\mathbf1)=e^{i\pi\alpha c}U(x),\qquad
B(x+c\mathbf1)=e^{2i\pi\alpha c}B(x).
$$

Dla ustalonej liczby fotonów zmienia się tylko faza amplitudy, zatem $p(n\mid x+c\mathbf1)=p(n\mid x)$. Mapa PNR nie rozróżnia wspólnego przesunięcia czterech cech; ma najwyżej trzy niezależne kierunki faz względnych. To własność tej architektury, a nie ogólna własność fotonicznego QML.

## 5.4. Skąd bierze się hafnian

Czysty stan gaussowski bez przesunięcia można zapisać

$$
|\psi_B\rangle=C_B\exp\left(\frac12\sum_{j,k}B_{jk}a_j^\dagger a_k^\dagger\right)|0\rangle,
\qquad C_B=\det(I-BB^\dagger)^{1/4}.
$$

Uzasadnienie normalizacji otrzymujemy z faktoryzacji Takagiego $B=V\operatorname{diag}(s_j)V^T$. Pasywne $V$ zachowuje normę, a dla pojedynczego modu

$$
\left\|e^{s(a^\dagger)^2/2}|0\rangle\right\|^2
=\sum_{k\ge0}\frac{(2k)!}{2^{2k}(k!)^2}s^{2k}
=(1-s^2)^{-1/2}.
$$

Iloczyn po modach daje $|C_B|^2=\prod_j\sqrt{1-s_j^2}=\sqrt{\det(I-BB^\dagger)}$. To wyprowadzenie wyjaśnia, dlaczego czynnik występujący w prawdopodobieństwie jest pierwiastkiem z wyznacznika, a czynnik amplitudy pierwiastkiem czwartego stopnia.

Niech $|n|=\sum_jn_j=2k$, a $B_n$ oznacza macierz uzyskaną przez powtórzenie wiersza i kolumny $j$ dokładnie $n_j$ razy. Rozwijając wykładnik, wybieramy $k$ par. Komutacja operatorów kreacji sprawia, że wszystkie doskonałe skojarzenia $2k$ pozycji sumują swoje amplitudy:

$$
\operatorname{Haf}(A)=\sum_{\mathcal M}\prod_{\{u,v\}\in\mathcal M}A_{uv}.
$$

Czynniki $2^kk!$ z uporządkowania par skracają się z rozwinięciem wykładniczym. Normalizacja stanu Focka wnosi $\sqrt{\prod_jn_j!}$. Otrzymujemy

$$
\langle n|\psi_B\rangle
=\frac{C_B\operatorname{Haf}(B_n)}{\sqrt{\prod_jn_j!}},\qquad
p(n\mid x)=\frac{\sqrt{\det(I-BB^\dagger)}\,|\operatorname{Haf}(B_n)|^2}{\prod_jn_j!}.
$$

Dla nieparzystego $|n|$ amplituda wynosi zero; dla pustego wzorca przyjmujemy $\operatorname{Haf}(\varnothing)=1$. Kod realizuje rekurencję skojarzeń w [[code:photonic_kernel/core.py#L163-L191]] i powyższy wzór w [[code:photonic_kernel/core.py#L221-L270]]. Wzór jest zgodny z formalizmem GBS [@hamilton2017]. Nie obejmuje przesuniętych stanów wymagających odpowiednich loop-hafnianów ani ogólnego mieszanego stanu po stratach.

Kontrola analityczna dla jednej pary: macierz powtórzeń przy $n=(k,k)$ ma $k!$ dopuszczalnych skojarzeń, każde o wadze $(\tanh r)^k$. Stąd

$$
p(k,k)=(1-\tanh^2r)\tanh^{2k}r,
$$

co zgadza się bezpośrednio z rozwinięciem TMSV. Tę kontrolę zawiera [[code:tests/test_photonic_kernel.py#L55-L69]].

## 5.5. Zachowanie całkowitej liczby fotonów i ogon

Pasywna optyka komutuje z $N_{\mathrm{tot}}=\sum_ja_j^\dagger a_j$. Rozkład $N_{\mathrm{tot}}$ nie zależy zatem od $x$ ani $\alpha$ dla zamrożonych ściskań. Funkcja tworząca czterech niezależnych źródeł wynosi

$$
G_{N_{\mathrm{tot}}}(z)=\prod_{j=1}^4\frac{1-q_j}{1-q_jz^2},\qquad q_j=\tanh^2r_j.
$$

Dla jednakowych ściskań $q_j=q$ liczba par ma rozkład ujemny dwumianowy:

$$
\Pr(N_{\mathrm{tot}}=2s)=\binom{s+3}{3}(1-q)^4q^s,
\quad\mathbb E N_{\mathrm{tot}}=8\sinh^2r.
$$

W konsekwencji masa okna $a_L(x)=\Pr(N_{\mathrm{tot}}\le L\mid x)$ w idealnym modelu jest stała po próbkach. Można obliczyć ją niezależnie od hafnianów przez sumę powyższych współczynników. Przeciwnie, konkretne wzorce, rozkład kliknięć i orbity mogą zależeć od interferometru. Ten test nie uprawnia do oczekiwania stałego odsetka akceptacji w pojedynczej realizacji finite-shot.

## 5.6. Overflow oraz postselekcja definiują różne cechy

Niech $\Omega_L=\{n:|n|\le L\}$, $a_x=\sum_{n\in\Omega_L}p_x(n)$ i $o_x=1-a_x$. Bieżący domyślny model konstruuje pełny rozkład na zgrubionym alfabecie:

$$
\bar p_x=(\{p_x(n)\}_{n\in\Omega_L},o_x),\qquad \sum_z\bar p_x(z)=1.
$$

Zdarzenie overflow jest jednym dodatkowym symbolem. Nie przechowuje ono wektora liczby fotonów. Alternatywna cecha postselekcyjna to

$$
p_x^{\mathrm{cond}}(n)=p_x(n)/a_x,\qquad n\in\Omega_L,
$$

istniejąca tylko dla $a_x>0$. Różnica nie jest kosmetyczną normalizacją: obserwowany eksperyment statystyczny jest inny. Dla jąder pierwiastkowych zachodzi dokładnie

$$
k_{\mathrm{overflow}}(x,y)
=\sqrt{a_xa_y}\,k_{\mathrm{cond}}(x,y)+\sqrt{o_xo_y}.
$$

Jeśli akceptacja jest zależna od próbki, nie można traktować tych jąder jako jednego estymandu. Nawet gdy $a_x=a$ jest stałe, dostajemy $ak_{\mathrm{cond}}+(1-a)$, co może zmienić rozwiązanie przy danej regularyzacji i sposobie centrowania.

Obie ścieżki są jawne w [[code:photonic_kernel/core.py#L392-L423]]; domyślne `include_overflow=True` oraz momenty znajdują się w [[code:photonic_kernel/core.py#L437-L476]]. Historyczny audyt [[code:audits/photonic_kernel_audit.py#L54-L96]] dzieli przez `accepted`, a jego część idealna przez $a_x$ w [[code:audits/photonic_kernel_audit.py#L187-L205]]. Wynik tego audytu dotyczy historycznej definicji warunkowej; nie zastępuje walidacji obecnego wariantu overflow.

Overflow nie wystarcza też do późniejszej symulacji strat. Zdarzenia $n=(L+1,0,\ldots)$ i $n=(100L,0,\ldots)$ trafiają do tego samego binu, lecz mają zupełnie różne prawdopodobieństwo powrotu do okna po thinning. `sample_distribution` zachowuje tylko masę tego binu [[code:photonic_kernel/core.py#L299-L322]], natomiast `sample_record_from_array` może zachować także histogram rzeczywistych wzorców overflow [[code:photonic_kernel/core.py#L325-L351]]. Sweep strat wymaga pełnych próbek PNR albo kontrolowanego modelu ogona.

## 5.7. Iloczyny cech i dowód PSD

Definiujemy $\phi(x)_z=\sqrt{\bar p_x(z)}$. Wtedy

$$
k_H(x,y)=\langle\phi(x),\phi(y)\rangle
=\sum_z\sqrt{\bar p_x(z)\bar p_y(z)},\qquad
\|\phi(x)\|_2=1.
$$

Jest to współczynnik Bhattacharyyi, nazywany tutaj jądrem Hellingera. Dla konwencji $H^2(p,q)=\frac12\sum_z(\sqrt{p_z}-\sqrt{q_z})^2$ mamy $H^2=1-k_H$. W szczególności $0\le k_H\le1$ i $k_H(x,x)=1$.

**Twierdzenie 5.1.** Dla dowolnych poprawnych rozkładów empirycznych lub idealnych macierz $K_{ij}=k_H(x_i,x_j)$ jest dodatnio półokreślona.

**Dowód.** Dla $c\in\mathbb C^n$:

$$
c^\dagger Kc=\sum_z\left|\sum_ic_i\phi(x_i)_z\right|^2\ge0.
$$

Nie potrzeba założenia o kwantowym pochodzeniu rozkładów. Ta sama własność obowiązuje dla klasycznego generatora próbek. Implementacja jest zwykłym iloczynem macierzy w [[code:photonic_kernel/core.py#L579-L580]]. Konstrukcja z jednej wspólnej macierzy cech zachowuje PSD także przy skończonej liczbie pomiarów; niezależna estymacja każdej pary wpisów nie miałaby takiej automatycznej gwarancji.

Event i orbit są deterministycznymi agregacjami: $g_{\mathrm{event}}(n)=(|n|,\#\{j:n_j>0\})$, a $g_{\mathrm{orbit}}(n)$ sortuje obsadzenia malejąco. Dla każdego obrazu $u$ definiujemy $p^g(u)=\sum_{n:g(n)=u}p(n)$. Dowód PSD jest identyczny po zastąpieniu alfabetu. Kod: [[code:photonic_kernel/core.py#L479-L565]].

Z nierówności Cauchy'ego–Schwarza wynika ponadto

$$
\sum_{n:g(n)=u}\sqrt{p_nq_n}
\le\sqrt{\left(\sum_{n:g(n)=u}p_n\right)\left(\sum_{n:g(n)=u}q_n\right)}.
$$

Sumując, otrzymujemy $k_H(p^g,q^g)\ge k_H(p,q)$: agregacja zmniejsza odległość Hellingera i usuwa część rozróżnialności. Może redukować wariancję estymacji, ale nie tworzy informacji. W każdym wykresie degradacji trzeba odróżnić kompresję alfabetu od odporności samego stanu fizycznego.

## 5.8. Momenty i poprawnie znormalizowana reprezentacja Gaussa

Wektor $b(n)$ w projekcie zawiera osiem $n_j$ oraz $36$ składników $n_jn_k$ dla $j\le k$. Bieżące cechy są obciętymi momentami bezwarunkowymi:

$$
m(x)=\left(\sum_{n\in\Omega_L}p_x(n)b(n),a_x,o_x\right)\in\mathbb R^{46}.
$$

Pierwsze $44$ współrzędne nie są pełnymi momentami $\mathbb E b(N)$ ani momentami warunkowymi. Pomijają wkład ogona. Ponadto współrzędne diagonalne drugiego rzędu to $\mathbb E[N_j^2\mathbf1_{\Omega_L}]$, nie momenty silniowe $\mathbb E[N_j(N_j-1)\mathbf1_{\Omega_L}]$ używane czasem w optyce.

Normalizacja wykorzystuje wyłącznie zbiór treningowy:

$$
z_j(x)=\frac{m_j(x)-\mu_j^{\mathrm{train}}}{s_j^{\mathrm{train}}},\qquad
k_\gamma(x,y)=\exp[-\gamma\|z(x)-z(y)\|_2^2],\quad\gamma>0.
$$

Kod: [[code:photonic_kernel/core.py#L426-L453]] i [[code:photonic_kernel/core.py#L568-L587]]. Przy $s_j<10^{-10}$ kod używa skali $1$. Dwie cechy $a_x$ i $o_x=1-a_x$ są redundantne; po standaryzacji zmiennej akceptacji wnoszą dwa identyczne składniki do odległości. W modelu idealnym akceptacja jest stała, lecz jej szum pomiarowy może zostać wystandaryzowany do wariancji jeden. Dlatego warto z góry ustalić politykę usuwania stałych idealnych cech oraz świadomie wybrać wagę akceptacji.

**Twierdzenie 5.2.** Jądro $e^{-\gamma\|u-v\|^2}$ jest PSD i ma przekątną równą jeden.

**Dowód przez funkcję charakterystyczną.** Dla $\omega\sim\mathcal N(0,2\gamma I_d)$ zachodzi

$$
\mathbb E e^{i\omega\cdot(u-v)}=e^{-\gamma\|u-v\|^2}.
$$

Miara częstotliwości ma znormalizowaną gęstość

$$
d\mu_\gamma(\omega)=(4\pi\gamma)^{-d/2}
\exp[-\|\omega\|^2/(4\gamma)]\,d\omega.
$$

Stąd $c^\dagger Kc=\int|\sum_jc_je^{i\omega\cdot u_j}|^2d\mu_\gamma(\omega)\ge0$. RBF jako jądro podobieństwa nie wymaga prefaktora gęstości $ (\gamma/\pi)^{d/2}$ w przestrzeni $u-v$; taki prefaktor byłby właściwy przy interpretacji jako gęstość względem Lebesgue'a, a zmieniałby przekątną kernela. W kodzie brak tego prefaktora jest poprawny.

Warto odróżnić jeszcze jądro funkcji charakterystycznych rozkładów:

$$
k_{\Phi}(x,y)=\int\overline{\Phi_x(t)}\Phi_y(t)\,d\mu(t).
$$

Dla skończonej nieujemnej miary $\mu$ także jest PSD, a po zamianie kolejności sum i całki równa się $\mathbb E_{N\sim p_x,M\sim p_y}\widehat\mu(M-N)$. Projekt nie implementuje tego jądra. Podajemy je, aby umiejscowić podobieństwo rozkładów w jednej przestrzeni funkcji, bez błędnego utożsamiania go z istniejącym $k_H$ czy RBF na momentach.

## 5.9. PNR, straty, dark counts i threshold

Idealny PNR ma elementy POVM $\Pi_n=|n\rangle\langle n|$. Detektor progowy rozróżnia tylko

$$
\Pi_0=|0\rangle\langle0|,\qquad\Pi_1=I-|0\rangle\langle0|.
$$

Taką semantykę ma [MeasureThreshold](https://strawberryfields.readthedocs.io/en/latest/code/api/strawberryfields.ops.MeasureThreshold.html). Suma kliknięć nie jest sumą fotonów: wzorzec $(4,0,\ldots)$ zawiera cztery fotony i jedno kliknięcie.

Kanał czystych strat o transmisyjności $T$ można modelować dzielnikiem wiązki z próżnią środowiska: $a_{\mathrm{out}}=\sqrt T a+\sqrt{1-T}e$. Na stanie $|n\rangle$ rozkład wykrytej liczby wynosi

$$
\Pr(M=k\mid N=n)=\binom nkT^k(1-T)^{n-k},\quad0\le k\le n.
$$

Dla wielu modów niezależne straty dają jądro Markowa będące iloczynem tych rozkładów. Jest to dokładne przekształcenie statystyki końcowego PNR, nie pełna symulacja wszystkich koherencji stanu. Kod thinning znajduje się w [[code:photonic_kernel/core.py#L354-L371]]. Dla funkcji tworzącej zachodzi

$$
G_M(z_1,\ldots,z_m)=G_N(1-T_1+T_1z_1,\ldots,1-T_m+T_mz_m).
$$

Dwa niezależne thinning o parametrach $T$ i $\eta$ składają się do thinning $T\eta$, co widać przez podstawienie do $G$. Po dodaniu niezależnych zliczeń ciemnych $D_j\sim\operatorname{Poisson}(\nu_j)$ funkcja tworząca mnoży się przez $\exp[\sum_j\nu_j(z_j-1)]$. Dla jednego modu po threshold otrzymujemy

$$
\Pr(C=1\mid N=n)=1-e^{-\nu}(1-T\eta)^n.
$$

Poprawna kolejność to strata kanału, sprawność detektora, dark counts, a na końcu threshold lub saturacja. `apply_detector_model` stosuje taką kolejność do próbek PNR [[code:photonic_kernel/core.py#L374-L389]], podobnie ścieżka `process_sample_batches` [[code:photonic_kernel/robustness.py#L45-L77]]. Nieuprawnione jest stosowanie sprawności fotonowej do bitów idealnego threshold.

**Kontrprzykład 5.3.** Dla $|2\rangle$, $T=1$, $\eta=1/2$, $\nu=0$ fizyczne prawdopodobieństwo kliknięcia to $1-(1-\eta)^2=3/4$. Idealny threshold daje najpierw zawsze $1$; thinning tej jedynki zachowuje ją z prawdopodobieństwem $1/2$. Operacje nie komutują.

Aktualny `run_strawberry_fields_samples` wybiera natywny threshold, a potem wykonuje właśnie ten drugi schemat dla `quantum_efficiency<1` [[code:photonic_kernel/strawberry_fields_robustness.py#L70-L98]]. Błąd dotyczy tej ścieżki SF; nie dotyczy thinning surowego PNR. Poprawna konstrukcja powinna albo wstawić $T\eta$ przed `MeasureThreshold` i nie stosować drugi raz sprawności, albo zachować PNR aż do ostatniego etapu. Przy bezpośrednim threshold zliczenia ciemne można dodać jako niezależne kliknięcie o prawdopodobieństwie $1-e^{-\nu}$.

Równomierną stratę można przesunąć przez pasywny interferometr; strata zależna od modu nie ma takiej ogólnej własności. Postprocessing końcowego PNR nie jest zatem uniwersalnym zastępstwem wszystkich strat wewnątrz rzeczywistego układu.

## 5.10. Skończona liczba pomiarów

Dla zamrożonego $x$ i $S$ niezależnych pomiarów liczności na alfabecie zawierającym overflow spełniają

$$
(C_1,\ldots,C_D)\sim\operatorname{Multinomial}(S,\bar p_x),\qquad
\widehat p_j=C_j/S.
$$

Z sumy niezależnych wskaźników otrzymujemy

$$
\mathbb E\widehat p_j=p_j,\quad
\operatorname{Var}(\widehat p_j)=\frac{p_j(1-p_j)}S,\quad
\operatorname{Cov}(\widehat p_j,\widehat p_k)=-\frac{p_jp_k}S\ (j\ne k).
$$

Macierz kowariancji to $(\operatorname{diag}p-pp^T)/S$, osobliwa z powodu $\sum_j\widehat p_j=1$. Multinomial w [[code:photonic_kernel/core.py#L299-L322]] symuluje dokładnie ten model przy założonych idealnych prawdopodobieństwach.

Pierwiastek w cechach wprowadza bias: z wklęsłości $\mathbb E\sqrt{\widehat p_j}\le\sqrt{p_j}$. Dla niezależnych zestawów pomiarów $x$ i $y$ off-diagonal estymata $\sum_j\sqrt{\widehat p_{xj}\widehat p_{yj}}$ jest obciążona w dół względem idealnego podobieństwa. Przekątna obliczona z tego samego rekordu wynosi dokładnie jeden, więc niezależne powtórne pomiary tego samego fizycznego $x$ nie są tym samym co ponowne użycie jego zapisanej cechy.

Dla $Sp_j\gg1$ rozwinięcie Taylora daje przybliżenie

$$
\mathbb E\sqrt{\widehat p_j}
\approx\sqrt{p_j}-\frac{1-p_j}{8S\sqrt{p_j}}.
$$

Nie wolno używać go dla zerowych lub bardzo rzadkich binów. Właśnie wysoki wymiar alfabetu Focka może powodować znaczny bias przy umiarkowanym $S$, mimo poprawnego PSD. Agregacja event/orbit zmniejsza liczbę rzadkich binów kosztem utraty informacji.

Dla dowolnej cechy $b(N)$ o skończonej wariancji $\widehat m=S^{-1}\sum_sb(N_s)$ jest nieobciążona i ma kowariancję $\operatorname{Cov}(b(N))/S$. Dla obciętych momentów trzeba w tym zdaniu użyć $b(N)\mathbf1_{\Omega_L}$; „bez obciążenia” dotyczy wtedy obciętego estymandu.

Przy postselekcji liczba zaakceptowanych pomiarów $A\sim\operatorname{Binomial}(S,a_x)$. Warunkowo względem $A>0$ częstości mają efektywny budżet $A$, a nie $S$. Prawdopodobieństwo braku zaakceptowanego wyniku wynosi $(1-a_x)^S$. Próba wymuszenia dokładnie $S_{\mathrm{accepted}}$ zaakceptowanych zdarzeń wymaga średnio $S_{\mathrm{accepted}}/a_x$ surowych pomiarów. Projekt słusznie nie uzupełnia odrzuconych zdarzeń, ale raportowanie musi zawsze wskazywać, który budżet jest ustalony.

## 5.11. Co porównuje sweep i ile kosztuje

`cutoff_loss_detector_sweep` używa tych samych wejściowych próbek i tego samego ziarna dla różnych cutoffów przy ustalonej parze straty–detektor [[code:photonic_kernel/robustness.py#L92-L143]]. Pozwala to oddzielić wpływ cutoffu od nowej realizacji thinning. Ziarno zmienia się jednak z indeksem transmisyjności i detektora: nie ma gwarancji wspólnego sprzężenia zdarzeń dla wszystkich poziomów strat. „Te same surowe próbki” nie oznacza „ten sam szum detekcyjny”.

RBF w samym sweepie używa surowych momentów [[code:photonic_kernel/robustness.py#L80-L89]], podczas gdy klasyfikacyjny eksperyment standaryzuje je na train [[code:photonic_kernel/experiment.py#L578-L585]]. Wyników tych dwóch macierzy nie należy porównywać jako identycznych definicji kernela bez ustalenia skalowania.

Liczba enumerowanych wzorców do cutoffu $L$ w $m$ modach wynosi

$$
D_L=\sum_{k=0}^L\binom{k+m-1}{m-1}=\binom{L+m}{m}.
$$

Dla $m=8$ jest to $D_4=495$, $D_6=3003$, $D_8=12870$, jeszcze przed dodatkowym binem overflow. Reprezentacja dense ma koszt pamięci $O(nD_L)$, a pełny Gram koszt $O(n^2D_L)$. Własna rekurencja hafnianu używa podproblemów indeksowanych maskami; jej bezpieczne oszacowanie górne dla macierzy $k\times k$ to $O(k^22^k)$ czasu i $O(2^k)$ pamięci. Wiele wzorców wymaga osobnych wywołań. To mały kontrolny symulator, nie skalowalny algorytm klasyczny ani dowód złożoności GBS.

Przy $n$ zapisanych wejściach optycznych i budżecie $B$ kod dzieli shots jako $\lfloor B/n\rfloor$ lub $\lceil B/n\rceil$ [[code:photonic_kernel/core.py#L273-L285]]. Jedno próbkowanie na wejście wystarcza do utworzenia czterech rodzin cech; nie potrzeba osobnego obwodu dla każdej pary jądra. Nadal trzeba zapłacić za przygotowanie, detekcję, strojenie konfiguracji, klasyczną konstrukcję Gram i uczenie. Budżet końcowych PNR nie obejmuje symulacyjnego przeszukiwania siatki w [[code:photonic_kernel/experiment.py#L161-L328]].

Aktualnie można uzasadnić poprawność idealnego wzoru hafnianowego, konstrukcji PSD oraz jawnego rozliczenia shots. Nie można na tej podstawie uzasadnić przewagi nad klasycznym RBF, poprawności modelu wszystkich strat sprzętowych ani gotowości ścieżki threshold ze sprawnością mniejszą od jedności. Kolejny kontrolowany eksperyment powinien zamrozić definicję cech, naprawić kolejność detekcji, niezależnie sprawdzić normalizację ogona i raportować powtórzenia dla wielu ziaren wraz z niepewnością predykcji.


# 6. Atlas dziewiętnastu rodzin algorytmów: równania, założenia i granice

## 6.1. Jak czytać atlas

Katalog `qml_model_modules` jest atlasem teorii. Obecność karty, przykładu Python w `qml_algorithms_data.js` lub krawędzi na grafie nie oznacza istnienia przebadanego algorytmu sprzętowego. Aktywne eksperymenty projektu dotyczą głównie jąder Hamiltonianowych, fotoniki oraz reservoir computing; kod QSVM i ansatzów VQE w `experiments/legacy` ma osobny status. W poniższych sekcjach określenie „teoria atlasu” oznacza właśnie brak takiej deklaracji implementacyjnej.

W całym rozdziale $\rho\succeq0$, $\operatorname{Tr}\rho=1$. Obserwable są hermitowskie, a pomiar o wyniku $y$ opisuje POVM $E_y\succeq0$, $\sum_yE_y=I$. Prawdopodobieństwo wyniku to $p(y)=\operatorname{Tr}(E_y\rho)$. Dla pomiaru projektorowego dodatkowo $E_yE_z=\delta_{yz}E_y$. Nie każdy zbiór etykiet klas jest pełną bazą obliczeniową: klasie może odpowiadać wiele bitstringów albo jeden zredukowany rejestr.

„Przewaga” wymaga określenia zadania wejścia–wyjścia i wszystkich kosztów. Mapa o $2^n$ amplitudach nie daje bezpłatnie $2^n$ dostępnych cech klasycznych. Przyspieszenie liczby zapytań do oracle nie jest tym samym co przyspieszenie czasu zbudowania tego oracle. Wzory i krótkie dowody poniżej są rozwinięciem matematycznym kart; nie są nowymi wynikami badawczymi projektu.

## 6.2. QSVM: jądro stanów i wypukły problem SVM

**Karta i status.** [[file:qml_model_modules/01_QSVM.md]]. Teoria metod jądrowych ma bezpośredni związek z eksperymentami projektu, ale klasyczny solver KRR w aktywnych gałęziach nie staje się SVM przez samą zmianę nazwy. Historyczny eksperyment QSVM znajduje się w [[file:experiments/legacy/qsvm_hypothesis_experiment.py]].

Niech $x\mapsto\rho(x)$ będzie dowolną ustaloną mapą do operatorów gęstości. Przestrzeń operatorów Hilberta–Schmidta daje jądro

$$
k(x,x')=\operatorname{Tr}[\rho(x)\rho(x')].
$$

Dla stanów czystych jest to $|\langle\phi(x)|\phi(x')\rangle|^2$. Dla mieszanych przekątna wynosi czystość $\operatorname{Tr}\rho(x)^2$, nie automatycznie jeden. Dodatnia półokreśloność wynika z

$$
\sum_{i,j}\overline c_ic_jk(x_i,x_j)
=\left\|\sum_ic_i\rho(x_i)\right\|_{\mathrm{HS}}^2\ge0.
$$

Dla etykiet $y_i\in\{-1,+1\}$ i $C>0$ prymalny soft-margin SVM rozwiązuje

$$
\min_{w,b,\xi\ge0}\frac12\|w\|^2+C\sum_i\xi_i,
\qquad y_i(\langle w,\rho(x_i)\rangle+b)\ge1-\xi_i.
$$

Mnożniki Lagrange'a $\alpha_i\ge0$ dla marginesów dają po zróżniczkowaniu względem $w$ i $b$ warunki $w=\sum_i\alpha_iy_i\rho(x_i)$ i $\sum_i\alpha_iy_i=0$. Minimalizacja po $\xi$ daje $\alpha_i\le C$. Po podstawieniu otrzymujemy

$$
\max_\alpha\sum_i\alpha_i-\frac12\sum_{i,j}\alpha_i\alpha_jy_iy_jK_{ij},
\quad0\le\alpha_i\le C,\quad\sum_i\alpha_iy_i=0.
$$

Funkcja decyzyjna to $f(x)=\sum_i\alpha_iy_i k(x_i,x)+b$. QPU może estymować elementy $K$, a optymalizacja pozostaje klasyczna. Dla $|\phi(x)\rangle=U_x|0\rangle$ obwód $U_{x'}^\dagger U_x$ daje $\Pr(0)=k(x,x')$. Sam Hadamard test daje część rzeczywistą lub urojoną amplitudowego overlapu, a nie od razu jego moduł do kwadratu; to różne procedury pomiarowe.

Znaczenie feature map i quantum-kernel learning ilustruje [@havlicek2019]; rama modeli jako metod jądrowych jest omówiona w [@schuld2021]. Użycie niezmiennego kernela, jego trenowanie przez alignment oraz FTQC least-squares SVM są różnymi algorytmami. Poprawny Gram ani duża przestrzeń Hilberta nie wystarczą do uzyskania dobrego marginesu i małego błędu generalizacji.

## 6.3. VQC i dokładny dowód parameter-shift

**Karta i status.** [[file:qml_model_modules/02_VQC.md]]. VQC jest w atlasie modelem nadzorowanym z trenowanym obwodem; nie jest synonimem zamrożonej mapy jądrowej.

Stan $\rho_\theta(x)=U(x,\theta)\rho_0U(x,\theta)^\dagger$ daje $p_\theta(y\mid x)=\operatorname{Tr}[E_y\rho_\theta(x)]$. Naturalna strata to

$$
\mathcal L(\theta)=-\frac1N\sum_{i=1}^N\log p_\theta(y_i\mid x_i),
$$

przy $p_\theta(y_i\mid x_i)>0$. Dla binarnego pomiaru $Z$ zachodzi $p(0\mid x)=(1+f_\theta(x))/2$, $p(1\mid x)=(1-f_\theta(x))/2$, gdzie $f_\theta(x)=\operatorname{Tr}[Z\rho_\theta(x)]$. Ten związek jest poprawny przy pomiarze konkretnego kubitu, z tożsamością na pozostałych.

**Twierdzenie 6.1 — przesunięcie jednej bramki.** Niech pojedyncze wystąpienie parametru ma postać $e^{-i\theta G}$, $G=G^\dagger$, $\operatorname{spec}G=\{-r,+r\}$, $r>0$. Pozostałe operacje i obserwabla nie zależą od tej współrzędnej. Wtedy

$$
\frac{df}{d\theta}
=r\left[f\left(\theta+\frac\pi{4r}\right)-f\left(\theta-\frac\pi{4r}\right)\right].
$$

**Dowód.** Ponieważ $G^2=r^2I$,

$$
e^{-i\theta G}=\cos(r\theta)I-i\sin(r\theta)G/r.
$$

Po wstawieniu do oczekiwanej wartości otrzymujemy rzeczywistą funkcję $f(\theta)=a+b\cos(2r\theta)+c\sin(2r\theta)$. Dla dowolnego przesunięcia $s$:

$$
f(\theta+s)-f(\theta-s)
=2\sin(2rs)[-b\sin(2r\theta)+c\cos(2r\theta)].
$$

Pochodna to $2r[-b\sin(2r\theta)+c\cos(2r\theta)]$. Wybór $s=\pi/(4r)$ kończy dowód. Dla $G=P/2$, $P^2=I$, mamy $r=1/2$, stąd współczynnik $1/2$ i przesunięcia $\pm\pi/2$. Dla $G=P$ współczynnik to $1$, a przesunięcia $\pm\pi/4$. Ogólnie dla $\sin(2rs)\ne0$ współczynnik wynosi $r/\sin(2rs)$.

Wynik dotyczy oczekiwanej wartości lub prawdopodobieństwa, nie automatycznie nieliniowej straty. Dla cross-entropy:

$$
\partial_\theta\mathcal L
=-\frac1N\sum_i\frac{\partial_\theta p_\theta(y_i\mid x_i)}{p_\theta(y_i\mid x_i)}.
$$

Jeśli ten sam parametr steruje wieloma bramkami, najpierw różniczkuje się po niezależnych wystąpieniach i sumuje po regule łańcuchowej. Generator o więcej niż dwóch wartościach własnych wymaga ogólnie innej reguły. Uogólnienia i kontekst estymacji gradientów zawiera [@schuld2019shift]. W finite-shot estymata gradientu jest losowa; dla niezależnych estymat dwóch przesunięć o wariancjach $v_\pm/S_\pm$ jej wariancja wynosi $r^2(v_+/S_++v_-/S_-)$. Dokładna tożsamość analityczna nie eliminuje kosztu pomiaru.

## 6.4. QNN/PQC: rodzina funkcji, a nie jeden algorytm

**Karta i status.** [[file:qml_model_modules/03_QNN_PQC.md]]. PQC jest obiektem obwodowym; QNN to rodzina modeli korzystająca z obwodów, kanałów i pomiarów. W atlasie nie zdefiniowano jednego uniwersalnego benchmarku QNN.

Typowy model ma postać

$$
f_\theta(x)=\operatorname{Tr}\left[M V_\theta E_x\rho_0E_x^\dagger V_\theta^\dagger\right]
=\operatorname{Tr}[M_\theta\rho(x)],\qquad M_\theta=V_\theta^\dagger MV_\theta.
$$

Drugi zapis wyjaśnia liniowość względem zakodowanego stanu i nieliniowość względem danych oraz parametrów. Zbiór dopuszczalnych $M_\theta$ jest ograniczony przez ansatz; nie obejmuje dowolnego hiperpłaszczyznowego klasyfikatora w przestrzeni operatorów. Jeśli dane są ponownie kodowane między warstwami, proste rozdzielenie na jeden $E_x$ i jeden $V_\theta$ nie jest dosłownie właściwym opisem obwodu, choć można skonstruować odpowiednią bogatszą reprezentację funkcji.

Dla $M=M^\dagger$, $\|M\|\le1$, oczekiwana wartość jest deterministyczną liczbą z $[-1,1]$, natomiast średnia z $S$ pomiarów ma wariancję co najwyżej $1/S$. Nie należy z losowości odczytu wnosić, że sama funkcja $f_\theta$ nie jest dobrze określona.

Lokalna linearyzacja przy $\theta_0$ daje

$$
f_{\theta_0+\delta}(x)\approx f_{\theta_0}(x)+J(x)\delta,
\quad K_{\mathrm{tan}}(x,x')=J(x)J(x')^T.
$$

$K_{\mathrm{tan}}$ jest PSD jako Gram gradientów. Dla straty kwadratowej i przybliżenia stałego Jacobianu ciągły gradient descent daje $\dot e=-K_{\mathrm{tan}}e$ z odpowiednim czynnikiem normalizacji próbek. Małe wartości własne powodują wolne uczenie określonych kierunków. Jest to lokalna analiza, nie dowód, że każdy QNN zawsze zachowuje się jak stały kernel.

Przegląd modeli PQC podaje [@benedetti2019]. Trzy osobne pytania to: co ansatz potrafi reprezentować, czy da się znaleźć parametry i czy znaleziony model generalizuje. Test ekspresywności losowych stanów odpowiada tylko części pierwszego pytania.

## 6.5. Hybrid QNN: gradient musi przejść także przez wejście QPU

**Karta i status.** [[file:qml_model_modules/04_HYBRID_QNN.md]]. Teoria atlasu opisuje kompozycję klasycznego encodera, pomiarów kwantowych i klasycznej głowicy.

Niech $z=h_\varphi(x)$, $q_a(z,\theta)=\operatorname{Tr}[M_a\rho_\theta(z)]$, $F(x)=g_w(q(h_\varphi(x),\theta))$. Reguła łańcuchowa daje

$$
\frac{\partial\ell}{\partial\varphi_j}
=\sum_{a,b}\frac{\partial\ell}{\partial q_a}
\frac{\partial q_a}{\partial z_b}\frac{\partial h_b}{\partial\varphi_j},
\qquad
\frac{\partial\ell}{\partial\theta_j}
=\sum_a\frac{\partial\ell}{\partial q_a}\frac{\partial q_a}{\partial\theta_j}.
$$

Gdy $z_b$ jest kątem bramki $e^{-iz_bP/2}$, pochodna po $z_b$ może wymagać dwóch dodatkowych ocen obwodu, tak samo jak po $\theta_j$. Stwierdzenie „encoder uczy się klasycznym backpropagation” jest niepełne, jeśli pomija koszt Jacobianu warstwy kwantowej. Liczba parametrów encodera i liczba kątów QPU są przy tym różnymi zasobami.

Dla gładkiej głowicy średni wynik finite-shot nie spełnia na ogół $\mathbb E g(\widehat q)=g(q)$. Rozwinięcie drugiego rzędu wskazuje składnik biasu $\frac12\operatorname{Tr}[\nabla^2g(q)\operatorname{Cov}(\widehat q)]$. Dlatego porównanie treningu exact-statevector z treningiem pomiarowym wymaga jawnego protokołu.

Warianty koherentnego uczenia parametrów, np. Baqprop [@verdon2018], są odrębnymi propozycjami od zwykłej klasycznej optymalizacji kątów. W projekcie nie należy przedstawiać ich jako użytego mechanizmu. Właściwe ablacje obejmują zamrożenie warstwy kwantowej, zastąpienie jej klasyczną mapą oraz porównanie przy podobnym koszcie danych, strojenia i pomiarów.

## 6.6. QGAN: rozkłady klasyczne i stany kwantowe to różne gry

**Karta i status.** [[file:qml_model_modules/05_QGAN.md]]. Teoria atlasu; karta nie stanowi implementacji zakończonego treningu generatora.

Dla rozkładów klasycznych $p$ i $q_\theta$ gra GAN to

$$
\min_\theta\max_{0<D<1}
V(D,\theta)=\mathbb E_{z\sim p}\log D(z)+\mathbb E_{z\sim q_\theta}\log(1-D(z)).
$$

Przy nieograniczonym dyskryminatorze optimum punktowe otrzymujemy z $p/D-q/(1-D)=0$: $D^*(z)=p(z)/(p(z)+q(z))$. Po podstawieniu:

$$
V(D^*,\theta)=-\log4+2\operatorname{JS}(p\|q_\theta).
$$

To dowód właściwości idealnego celu, nie zbieżności naprzemiennego gradientu dla ograniczonych sieci. Używana często strata generatora $-\mathbb E_{q_\theta}\log D$ jest wariantem non-saturating: ma podobną motywację, ale nie jest dosłownie minimalizacją tej samej funkcji $V$ przy każdym kroku.

Dla danych będących stanami $\rho$ i $\sigma_\theta$ fizyczny dyskryminator jest efektem POVM $0\le E\le I$. Przy równych priorach jego sukces wynosi

$$
P_{\mathrm{succ}}(E)=\frac12\operatorname{Tr}(E\rho)+\frac12\operatorname{Tr}[(I-E)\sigma_\theta]
=\frac12+\frac12\operatorname{Tr}[E(\rho-\sigma_\theta)].
$$

Diagonalizacja hermitowskiej różnicy o śladzie zero pokazuje, że maksimum osiąga projekcja na jej dodatnie widmo, dając $P^*_{\mathrm{succ}}=1/2+\|\rho-\sigma_\theta\|_1/4$. Nierozróżnialność przez wszystkie pomiary oznacza zatem równość stanów; nierozróżnialność przez ograniczoną rodzinę obwodów nie daje takiej gwarancji. Ramę kwantowej gry przedstawia [@lloyd2018]. Uczenie generatora z wielu kopii danych nie klonuje nieznanej pojedynczej kopii: wykorzystuje kolejne przygotowania i ich pomiary.

## 6.7. QCBM: strata dostępna z próbek

**Karta i status.** [[file:qml_model_modules/06_QCBM.md]]. Teoria atlasu. Samo próbkowanie bezparametrycznego fotonicznego GBS w innym rozdziale nie oznacza treningu QCBM.

Born machine definiuje $p_\theta(z)=|\langle z|U_\theta|0\rangle|^2$. Cel KL,

$$
\operatorname{KL}(q\|p_\theta)=\sum_zq(z)\log\frac{q(z)}{p_\theta(z)},
$$

wymaga kontroli prawdopodobieństw na nośniku danych; ma nieskończoną wartość, jeżeli $q(z)>0$, lecz $p_\theta(z)=0$. Dostęp tylko do próbek nie daje automatycznie taniej estymaty każdego logarytmu. Alternatywą jest kwadrat MMD dla ustalonego PSD jądra $\kappa$ na bitstringach:

$$
\operatorname{MMD}^2(p_\theta,q)
=\mathbb E_{z,z'\sim p_\theta}\kappa(z,z')
-2\mathbb E_{z\sim p_\theta,w\sim q}\kappa(z,w)
+\mathbb E_{w,w'\sim q}\kappa(w,w').
$$

Każdy składnik można oszacować z niezależnych par; estymator U-statystyczny pomija przekątną dla par z tego samego zestawu. Ponieważ jest to $\|\mathbb E_p\phi_\kappa-\mathbb E_q\phi_\kappa\|^2$, cel jest nieujemny. Równość zero oznacza równość rozkładów tylko przy odpowiednio rozróżniającym jądrze; na skończonym alfabecie wystarczy jądro o ściśle dodatnio określonym pełnym Gram.

Dla jednej bramki z generatorem $\pm r$ zachodzi $\partial_\theta p_\theta(z)=r[p_+(z)-p_-(z)]$. Symetria $\kappa$ daje

$$
\partial_\theta\operatorname{MMD}^2
=2r\big(\mathbb E_{p_+,p_\theta}\kappa-\mathbb E_{p_-,p_\theta}\kappa
-\mathbb E_{p_+,q}\kappa+\mathbb E_{p_-,q}\kappa\big).
$$

To procedura gradientowa możliwa do próbkowania, a nie potrzeba wypisania $2^n$ prawdopodobieństw. Koszt i wariancja zależą od jądra i liczby próbek. Rodzinę modeli opisuje [@benedetti2019]; nie wynika z niej automatyczna przewaga nad klasycznymi modelami rozkładów.

## 6.8. QBM: stan Gibbsa i niekomutujący gradient

**Karta i status.** [[file:qml_model_modules/07_QBM.md]]. Teoria atlasu. Próbki annealera nie są z definicji próbkami konkretnego modelu Gibbsa.

Dla skończeniewymiarowego hermitowskiego $H_\theta$ oraz $\beta>0$:

$$
\rho_\theta=\frac{e^{-\beta H_\theta}}{Z_\theta},\quad
Z_\theta=\operatorname{Tr}e^{-\beta H_\theta}>0,\quad
p_\theta(v)=\operatorname{Tr}[(|v\rangle\langle v|\otimes I_h)\rho_\theta].
$$

Model Isinga z polem poprzecznym może mieć $H_\theta=-\sum_{i<j}J_{ij}Z_iZ_j-\sum_ih_iZ_i-\sum_i\Gamma_iX_i$. Gdy wszystkie $\Gamma_i=0$, model jest diagonalny i statystyka widzialnych zmiennych redukuje się do klasycznej marginalizacji rozkładu Boltzmanna. Niekomutujące składniki zmieniają zarówno stan, jak i gradient uczenia; pierwotny model QBM przedstawia [Quantum Boltzmann Machine](https://arxiv.org/abs/1601.02036).

Niech $H'=\partial_\theta H$. Tożsamość Duhamela wynosi

$$
\partial_\theta e^{-\beta H}
=-\beta\int_0^1e^{-(1-s)\beta H}H'e^{-s\beta H}\,ds.
$$

Można ją uzyskać przez różniczkowanie szeregu wykładniczego i grupowanie wszystkich pozycji $H'$ w iloczynach. Cykliczność śladu daje $\partial_\theta\log Z=-\beta\operatorname{Tr}(\rho H')$. Dla $\Pi_v=|v\rangle\langle v|\otimes I_h$:

$$
\partial_\theta\log p_\theta(v)
=-\beta\frac{\int_0^1\operatorname{Tr}[\Pi_ve^{-(1-s)\beta H}H'e^{-s\beta H}]\,ds}
{\operatorname{Tr}(\Pi_ve^{-\beta H})}
+\beta\operatorname{Tr}(\rho H').
$$

Klasyczna „faza dodatnia minus ujemna” upraszcza się dopiero przy odpowiedniej komutacji. Zastąpienie całki przez zwykłą warunkową średnią $H'$ bez takiego założenia jest na ogół błędne. Cel maximum likelihood wymaga ponadto przygotowania lub przybliżenia stanu termicznego, oszacowania temperatury efektywnej i kontroli błędów samplera; karta nie zawiera wykonania tych kroków.

## 6.9. QCNN: pooling jest kanałem

**Karta i status.** [[file:qml_model_modules/08_QCNN.md]]. Teoria atlasu. QCNN dla stanów kwantowych i quanvolution stosowana osobno do klasycznych patchy nie są synonimami. Przykład pierwotnej architektury QCNN podaje [@cong2019].

Niech $C_\ell$ będzie unitarną lokalną warstwą konwolucyjną, a rejestr $B$ podlega pomiarowi w bazie $|s\rangle$. Po wyniku $s$ wykonujemy $V_s$ na zachowanym rejestrze $A$. Operator Krausa

$$
K_s=V_s(I_A\otimes\langle s|_B)C_\ell
$$

prowadzi do kanału $\mathcal E_\ell(\rho)=\sum_sK_s\rho K_s^\dagger$. Ponieważ $\sum_sK_s^\dagger K_s=C_\ell^\dagger IC_\ell=I$, kanał zachowuje ślad i jest całkowicie dodatni. Pełna sieć daje

$$
\rho_{\mathrm{out}}=\mathcal E_L\circ\cdots\circ\mathcal E_1(\rho_{\mathrm{in}}),
\quad f_\theta=\operatorname{Tr}(M\rho_{\mathrm{out}}).
$$

Przy odrzucaniu kubitów bez pomiaru warstwa ma postać $\operatorname{Tr}_B[C_\ell\rho C_\ell^\dagger]$. Nie można zapisać ogólnego pooling jako jednej mniejszej unitarnej macierzy $U\rho U^\dagger$. Unitarna dylatacja wymaga zachowania środowiska, po czym częściowego śladu. Przy postselekcji jednego wyniku mapę trzeba dodatkowo znormalizować przez $\operatorname{Tr}(K_s\rho K_s^\dagger)$ i rozliczyć prawdopodobieństwo sukcesu.

Lokalność oraz współdzielenie parametrów mogą ograniczyć liczbę parametrów; nie gwarantują jednak braku barren plateaus dla dowolnego ansatzu i dowolnej straty. Quanvolution wykonująca obwód na każdym patchu ma inną strukturę wejścia, koszt pomiarów i sposób agregacji. Poprawka formalna karty polega na zastąpieniu jej symbolu $U_{\mathrm{QCNN}}$ kompozycją kanałów tam, gdzie opisano pomiar i redukcję rejestru.

## 6.10. Quantum autoencoder: kompresja rodziny stanów

**Karta i status.** [[file:qml_model_modules/09_QUANTUM_AUTOENCODER.md]]. Teoria atlasu. Projekt nie dokumentuje tu wyuczonego kompresora z oceną na nowych stanach. Oryginalny model opisuje [@romero2017].

Dla czystych danych $|\psi_i\rangle\in\mathcal H_A\otimes\mathcal H_B$ encoder powinien spełniać $U_\theta|\psi_i\rangle\approx|z_i\rangle_A|0\rangle_B$. Strata trash-register:

$$
\mathcal L=1-\sum_iw_i\operatorname{Tr}[(I_A\otimes|0\rangle\langle0|)U_\theta|\psi_i\rangle\langle\psi_i|U_\theta^\dagger],
\quad w_i\ge0,\quad\sum_iw_i=1.
$$

**Warunek dokładnej kompresji.** Istnieje unitarny encoder dokładny dla wszystkich stanów w podprzestrzeni $\mathcal S$ wtedy i tylko wtedy, gdy $\dim\mathcal S\le\dim\mathcal H_A$. Konieczność wynika z zachowania iloczynów skalarnych i wymiaru przez unitarność. Dla dostateczności wybieramy ortonormalną bazę $\mathcal S$, mapujemy ją izometrycznie do $\mathcal H_A\otimes|0\rangle_B$, a izometrię rozszerzamy do bazy całej przestrzeni. Dla zbioru treningowego właściwym wymiarem jest wymiar jego liniowej rozpiętości, nie sama liczba przykładów.

Dla przybliżenia niech $|\Psi\rangle=U|\psi\rangle$ i $p_0=\|(I\otimes\langle0|)|\Psi\rangle\|^2$. Rzeczywisty decoder po odrzuceniu trash odtwarza

$$
\rho_{\mathrm{rec}}=U^\dagger[\operatorname{Tr}_B|\Psi\rangle\langle\Psi|\otimes|0\rangle\langle0|]U.
$$

Po zapisaniu $|\Psi\rangle=\sum_b|v_b\rangle_A|b\rangle_B$ fidelity z wejściem wynosi $\sum_b|\langle v_b|v_0\rangle|^2\ge\|v_0\|^4=p_0^2$. Zatem $p_0\ge1-\epsilon$ zapewnia $F(\rho_{\mathrm{rec}},|\psi\rangle)\ge(1-\epsilon)^2$ w konwencji fidelity z kwadratem. Jest to konkretna gwarancja dla rozpatrywanego stanu. Mała średnia strata na train nie daje sama gwarancji dla dowolnego nowego stanu, a latent stanu mieszanego nie musi być czysty.

## 6.11. Quantum transformer: amplitudy wyjścia nie są softmaxem tokenów

**Karta i status.** [[file:qml_model_modules/10_QUANTUM_TRANSFORMER.md]]. Teoria atlasu dotyczy przede wszystkim FTQC inferencji przez block encoding. Odmienne modele parametrów ortogonalnych i płytkich obwodów w pracy Quantum Vision Transformers [@kerenidis2022] nie są tym samym twierdzeniem.

Dla sekwencji $S\in\mathbb R^{N\times d}$ definiujemy $Q=SW_Q$, $K=SW_K$, $V=SW_V$ oraz

$$
A_{ij}=\frac{e^{Q_i\cdot K_j/\sqrt{d_k}}}{\sum_\ell e^{Q_i\cdot K_\ell/\sqrt{d_k}}},
\qquad G=AV.
$$

Residual daje $h_i=S_i+G_i$, a layer normalization, z pominięciem uczonych skali i przesunięcia dla przejrzystości, wynosi

$$
\operatorname{LN}(h_i)_a=\frac{h_{ia}-\mu_i}{\sqrt{d^{-1}\sum_b(h_{ib}-\mu_i)^2+\epsilon_{\mathrm{LN}}}}.
$$

Produkty macierzy można składać z block encodings przy kontroli ich skal. Softmax działa elementowo i wierszowo; nie jest po prostu funkcją wartości singularnych $QK^T$. Potrzebne są dodatkowe procedury elementowych funkcji, normalizacji i przygotowania stanów. FTQC konstrukcję takiego rodzaju opisuje [@transformer2024]. Koszt zależy m.in. od norm macierzy, skal block encoding, precyzji, normy docelowego wiersza i prawdopodobieństwa przygotowania; samo $N$ i $d$ nie wystarczają do poprawnego twierdzenia o czasie.

Jeśli procedura przygotowała $|o_i\rangle=\sum_ao_{ia}|a\rangle/\|o_i\|$, pomiar daje $\Pr(a)=|o_{ia}|^2/\|o_i\|^2$. Tymczasem językowa głowica z logitami $\ell=W_{\mathrm{out}}o_i+b$ wymaga $\Pr(\text{token}=t)=e^{\ell_t}/\sum_ue^{\ell_u}$. Nawet dla $\ell=(0,1)$ te rozkłady są różne: pomiar stanu proporcjonalnego do logitów zawsze wybierze drugą współrzędną, a softmax nie. Aby próbkować softmax przez pomiar, należałoby przygotować amplitudy proporcjonalne do $e^{\ell_t/2}$ i uwzględnić koszt tego kroku.

Karta poprawnie wskazuje potrzebę ograniczonego odczytu, ale zdanie o automatycznej predykcji tokenu przez pomiar amplitud wymaga tego uzupełnienia. Rozdział nie przypisuje ogólnego kwadratowego przyspieszenia każdemu transformerowi: bez pełnych warunków konkretnego twierdzenia byłaby to nadinterpretacja.

## 6.12. HHL: stan rozwiązania i uwarunkowanie

**Karta i status.** [[file:qml_model_modules/11_HHL.md]]. Teoria atlasu; klasyczne `numpy.linalg.solve` i testy kondycji nie wykonują HHL. Algorytm źródłowy: [@harrow2009].

Zakładamy $A=A^\dagger$ oraz, po przeskalowaniu, $1/\kappa\le|\lambda_j|\le1$ na rozpatrywanym nośniku. Potrzebne są efektywne przygotowanie $|b\rangle=\sum_j\beta_j|u_j\rangle$ i kontrolowana symulacja $e^{iAt}$ z określonym błędem. W oryginalnym modelu zapewnia to dostęp do rzadkiej macierzy przez odpowiednie oracle; nowoczesny block encoding jest alternatywnym modelem dostępu, nie bezpłatnym założeniem.

Idealne QPE i kontrolowana rotacja ancilli dają

$$
\sum_j\beta_j|u_j\rangle|\widetilde\lambda_j\rangle
\left(\sqrt{1-C^2/\widetilde\lambda_j^2}|0\rangle
+\frac{C}{\widetilde\lambda_j}|1\rangle\right),\quad
C\le\min_j|\widetilde\lambda_j|.
$$

Odwrócenie QPE i postselekcja ancilli $1$ prowadzą w idealnej granicy do

$$
|x\rangle=\frac{A^{-1}|b\rangle}{\|A^{-1}b\|},\qquad
p_{\mathrm{succ}}=C^2\sum_j\frac{|\beta_j|^2}{|\lambda_j|^2}.
$$

Dla $C=1/\kappa$ sukces może być rzędu $1/\kappa^2$, więc postselekcja i jej amplification są istotną częścią kosztu. Ponadto $|1/\lambda-1/\widetilde\lambda|=|\lambda-\widetilde\lambda|/(|\lambda\widetilde\lambda|)$: dokładność estymacji widma musi poprawiać się wraz z kondycją. Pełne twierdzenie o czasie zawiera też rzadkość, błąd symulacji i dokładność wyjścia.

Dla macierzy niehermitowskiej można rozważyć osadzenie $\mathcal A=\begin{pmatrix}0&A\\A^\dagger&0\end{pmatrix}$, lecz trzeba zdefiniować osadzony prawy bok oraz blok wyniku. Przy zerowych wartościach singularnych konieczna jest pseudoodwrotność i ograniczenie nośnika albo regularyzacja.

Wyjście nie jest klasycznym wektorem wszystkich współrzędnych. Dostępny jest stan i np. oszacowanie $\langle x|M|x\rangle$. Wypisanie $N$ współrzędnych z określoną dokładnością wymaga osobnego odczytu i nie może kosztować mniej niż rozmiar wypisywanego wyniku. HHL nie jest koniecznym podprogramem wszystkich kwantowych jąder ani qPCA.

## 6.13. QSVT: parzystość i przestrzenie lewych/prawych wektorów

**Karta i status.** [[file:qml_model_modules/12_QSVT.md]]. Teoria atlasu; demonstrator z klasycznym SVD w [[code:qml_algorithms_data.js#L1043-L1054]] nie jest obwodem QSVT. Warunki konstrukcji pochodzą z [@gilyen2019].

Niech $A:\mathcal H_R\to\mathcal H_L$. Projected unitary encoding oznacza dostęp do unitarnego $U$ i projektorów $\Pi$, $\widetilde\Pi$ takich, że kodowany blok $\widetilde\Pi U\Pi$ identyfikujemy z $A/\alpha$, gdzie $\alpha\ge\|A\|$. W wersji przybliżonej wymagamy $\|A-\alpha\widetilde\Pi U\Pi\|\le\epsilon$. Dla $A=\sum_j\sigma_j|u_j\rangle\langle v_j|$ para lewego i prawego wektora definiuje dwuwymiarową strukturę, w której naprzemienne użycie $U$, $U^\dagger$ i faz projektorów realizuje przekształcenie wielomianowe.

Użyteczna postać twierdzenia jest następująca: rzeczywisty wielomian $P$ stopnia $d$, o parzystości $d\bmod2$ i $|P(t)|\le1$ na $[-1,1]$, można zrealizować jako odpowiedni blok QSVT, z liczbą zapytań do $U,U^\dagger$ rzędu $d$ i ewentualnym stałym narzutem ancilli do wyodrębnienia rzeczywistej części. Implementacja musi kontrolować błędy wejściowego bloku oraz syntezy faz. Nie twierdzimy, że dowolny nieograniczony wielomian można umieścić jako blok unitarnego operatora.

Dla **nieparzystego** $P$ otrzymujemy mapę między przestrzeniami

$$
P^{\mathrm{SV}}(A/\alpha)=\sum_jP(\sigma_j/\alpha)|u_j\rangle\langle v_j|:
\mathcal H_R\to\mathcal H_L.
$$

Dla **parzystego** $P$ właściwa konstrukcja działa na jednej stronie, np.

$$
P^{\mathrm{SV}}_R(A/\alpha)=\sum_{j:\sigma_j>0}P(\sigma_j/\alpha)|v_j\rangle\langle v_j|
+P(0)\Pi_{\ker A},
$$

z odpowiednim analogiem lewostronnym. Suma obejmuje wyłącznie dodatnie wartości singularne. Projektor na jądro występuje osobno, aby nie policzyć zerowych kierunków dwukrotnie. Dla pełnej bazy prawej nullspace trzeba uwzględnić. Przykładowo parzyste $P(t)=t^2$ daje $A^\dagger A/\alpha^2$ po stronie prawej, a nie $U_{\mathrm{SVD}}\Sigma^2V_{\mathrm{SVD}}^\dagger$. To prosty kontrprzykład dla zbyt ogólnej definicji z karty.

Przy inwersji na $|t|\in[1/\kappa,1]$ przybliżamy ograniczoną nieparzystą funkcję $c/t$, z $c=O(1/\kappa)$, zamiast nieograniczonego $1/t$ na całym $[-1,1]$. Trzeba też pilnować orientacji: pseudoodwrotność $A^+=\sum_j\sigma_j^{-1}|v_j\rangle\langle u_j|$ działa odwrotnie niż nieparzysta transformacja $A$. Dlatego stosuje się odpowiedni blok dla $A^\dagger$ lub odwraca orientację kodowania. Dla macierzy hermitowskich ten aspekt upraszcza się, ale nie wolno przenosić uproszczenia na dowolne prostokątne $A$.

Funkcja `s/(s*s+ridge)` w demonstratorze jest funkcją wymierną, mimo nazwy `ridge_inverse_polynomial`. Zwrócenie przez SVD przefiltrowanej macierzy jest poprawnym klasycznym filtrem, lecz nie dostarcza wielomianu, faz QSP, block encoding ani oszacowania błędu obwodu.

## 6.14. qPCA: relacja gęstości, kowariancji i Gram

**Karta i status.** [[file:qml_model_modules/13_QPCA.md]]. Teoria atlasu. Przykład `np.linalg.eigh` w [[code:qml_algorithms_data.js#L1063-L1075]] jest klasycznym rozwiązaniem celu PCA, co należy utrzymać w opisie.

Dla wycentrowanej rzeczywistej macierzy $X\in\mathbb R^{N\times d}$, $X\ne0$, definiujemy

$$
\rho=\frac{X^TX}{\|X\|_F^2},\quad
G=\frac{XX^T}{\|X\|_F^2},\quad
X=U\Sigma V^T.
$$

Wtedy $\rho=V\Sigma^2V^T/\|X\|_F^2$ i $G=U\Sigma^2U^T/\|X\|_F^2$. Niezerowe wartości własne są takie same, lecz wektory własne żyją odpowiednio w przestrzeni cech i próbek. Główne kierunki PCA to prawe wektory singularne $X$. Jeśli wszystkie wycentrowane dane są zerowe, normalizacja przez ślad jest niezdefiniowana i wymaga osobnego przypadku.

Można przygotować $\rho$ jako mieszaninę wierszy:

$$
\rho=\sum_{i:x_i\ne0}\frac{\|x_i\|^2}{\|X\|_F^2}|x_i\rangle\langle x_i|,
\qquad |x_i\rangle=x_i/\|x_i\|.
$$

Jednakowe wagi znormalizowanych wierszy na ogół dają inną macierz. Centrowanie i wagi norm są zatem częścią zadania, nie nieistotnym preprocessingiem.

Oryginalne density-matrix exponentiation [@lloyd2014] korzysta z kopii $\rho$. Dla operatora SWAP $S$ rozwinięcie do pierwszego rzędu daje

$$
\operatorname{Tr}_1[e^{-i\delta S}(\rho\otimes\sigma)e^{i\delta S}]
=\sigma-i\delta[\rho,\sigma]+O(\delta^2).
$$

Po $n$ krokach z nowymi kopiami i $\delta=t/n$ otrzymujemy przybliżenie $e^{-it\rho}\sigma e^{it\rho}$ z błędem rzędu $t^2/n$ w prostym oszacowaniu. QPE wymaga odpowiedniej kontrolowanej wersji tych operacji. Przy wejściu będącym kopią $\rho=\sum_j\lambda_j|u_j\rangle\langle u_j|$ komponent $j$ jest próbkowany z wagą $\lambda_j$, co sprzyja dominującym składowym; dla arbitralnego $|b\rangle$ wagi to $|\langle u_j|b\rangle|^2$.

Rozdzielenie bliskich wartości własnych wymaga odpowiedniej precyzji faz i czasu ewolucji. Pełne wypisanie wektorów głównych kosztuje odczyt. qPCA nie wymaga z definicji wywołania HHL: wspólna dziedzina algebry liniowej nie jest zależnością implementacyjną.

## 6.15. Quantum clustering: jaka odległość i jaki centroid

**Karta i status.** [[file:qml_model_modules/14_QUANTUM_CLUSTERING.md]]. Teoria atlasu; karta szkicuje rodzinę procedur, nie jeden kanoniczny algorytm.

Dla rzeczywistych niezerowych wektorów $x,c$:

$$
\|x-c\|^2=\|x\|^2+\|c\|^2-2\|x\|\|c\|\operatorname{Re}\langle\widehat x|\widehat c\rangle.
$$

Dopiero dla obu norm równych jeden wzór redukuje się do $2-2\operatorname{Re}\langle\widehat x|\widehat c\rangle$. SWAP test daje $|\langle\widehat x|\widehat c\rangle|^2$, co nie wyznacza znaku części rzeczywistej. Interferencyjne porównanie przygotowań wymaga spójnej konwencji faz. Odległość między fizycznymi promieniami stanów i euklidesowa odległość zakodowanych wektorów nie są tym samym obiektem.

Jeżeli cechy są dowolną nieliniową mapą $\phi(x)$ z jądrem $k$, właściwy centroid klastra $C$ leży w przestrzeni cech:

$$
\mu_C=\frac1{|C|}\sum_{i\in C}\phi(x_i).
$$

Odległość możliwa do obliczenia wyłącznie przez jądro wynosi

$$
\|\phi(x)-\mu_C\|^2
=k(x,x)-\frac2{|C|}\sum_{i\in C}k(x,x_i)
+\frac1{|C|^2}\sum_{i,j\in C}k(x_i,x_j).
$$

Wynika to bezpośrednio z rozwinięcia normy kwadratu. Zwykle $\phi(\operatorname{mean}x_i)\ne\mu_C$, więc klasyczna aktualizacja centroidu w przestrzeni danych nie jest dokładnym krokiem kernel k-means. Dla normalizowanych liniowych reprezentacji można zamiast tego rozważyć spherical k-means i jawnie normalizować centroid, ale jest to inne zadanie niż zwykłe euklidesowe k-means.

Koszt ładowania danych, estymacji podobieństw oraz iteracji przypisań musi zostać porównany z klasycznym baseline. Nieliniowe jądro może zmienić jakość grupowania bez jakiegokolwiek przyspieszenia obliczeń; tych tez nie należy łączyć.

## 6.16. QRL: kwantowa polityka i klasyczne trajektorie

**Karta i status.** [[file:qml_model_modules/15_QRL.md]]. Teoria atlasu; bez zdefiniowanego środowiska, horyzontu, nagrody i treningu nie ma kompletnego eksperymentu RL.

Dla klasycznego MDP polityka może być generowana przez pomiar

$$
\pi_\theta(a\mid s)=\operatorname{Tr}[E_a\rho_\theta(s)],\qquad
J(\theta)=\mathbb E_{\tau\sim P_\theta}\sum_{t=0}^{T-1}\gamma^tr_t.
$$

Przy nieskończonym horyzoncie wystarczy $0\le\gamma<1$ i ograniczone nagrody. Jeśli dynamika środowiska nie zależy od $\theta$, to $P_\theta(\tau)=\mu(s_0)\prod_t\pi_\theta(a_t\mid s_t)P(s_{t+1}\mid s_t,a_t)$. Zakładamy różniczkowalną politykę o dodatnich prawdopodobieństwach na ustalonym nośniku trajektorii; w przeciwnym razie zapis logarytmiczny wymaga oddzielnej analizy punktów zerowych. Różniczkując sumę po trajektoriach:

$$
\nabla J=\mathbb E\left[R(\tau)\sum_t\nabla\log\pi_\theta(a_t\mid s_t)\right],
\quad R(\tau)=\sum_t\gamma^tr_t.
$$

Przy odpowiednich warunkach wymiany różniczkowania z wartością oczekiwaną można zastąpić $R$ zdyskontowanym przyszłym zwrotem w każdym kroku i odjąć baseline niezależny od akcji. Ponieważ $\nabla\log\pi=(\nabla\pi)/\pi$, reguła przesunięcia dla prawdopodobieństw nie usuwa problemu małych $\pi$ i wariancji policy gradient.

Model z kwantową polityką w klasycznym środowisku wykonuje klasyczne przejście stan–akcja–nagroda po każdym pomiarze. Jest inny niż koherentny dostęp do środowiska jako oracle. Przyspieszenia analizowane w [@dunjko2016] wymagają wskazanego tam modelu interakcji; nie przechodzą automatycznie na dowolny PQC sterujący grą. Grover może być podprogramem przeszukiwania tylko wtedy, gdy da się koherentnie i odwracalnie sprawdzić jakość kandydatów, a koszt tego sprawdzenia jest policzony.

## 6.17. QAOA: naprzemienna ewolucja i znak funkcji celu

**Karta i status.** [[file:qml_model_modules/16_QAOA.md]]. Teoria atlasu; aktywny kernel Hamiltonianowy nie jest QAOA tylko dlatego, że używa ewolucji Isinga. Źródło pierwotne: [@farhi2014].

Dla maksymalizacji funkcji diagonalnej $C(z)$ definiujemy $H_C=\sum_zC(z)|z\rangle\langle z|$, $H_B=\sum_jX_j$, $|s\rangle=|+\rangle^{\otimes n}$ i

$$
|\psi_p\rangle=e^{-i\beta_pH_B}e^{-i\gamma_pH_C}\cdots
e^{-i\beta_1H_B}e^{-i\gamma_1H_C}|s\rangle,
\quad F_p=\langle\psi_p|H_C|\psi_p\rangle.
$$

Maksymalizujemy $F_p$ albo minimalizujemy $-F_p$. Dla Max-Cut bit $z_i$ odpowiada spinowi $s_i=(-1)^{z_i}$, a wskaźnik przecięcia krawędzi to $(1-s_is_j)/2$, stąd

$$
H_C=\sum_{(i,j)\in E}\frac{I-Z_iZ_j}{2}.
$$

Sama diagonalna ewolucja kosztu zmienia fazy, lecz nie zmienia częstości pomiaru w bazie obliczeniowej. Mixer pozwala zamienić różnice faz w różnice amplitud. Jego wybór jest częścią algorytmu; dla twardych ograniczeń można wymagać zachowania dopuszczalnej podprzestrzeni zamiast standardowego $\sum X_j$.

Przy bezbłędnej globalnej optymalizacji najlepsza wartość $F_{p+1}^*\ge F_p^*$ dla maksymalizacji, ponieważ dodatkową warstwę można wyzerować. Nie mówi to nic o tym, czy lokalny optimizer znajdzie tę wartość ani czy koszt szumu i pomiaru pozostanie akceptowalny. Ponadto dobra wartość oczekiwana nie daje bez dodatkowej analizy konkretnego prawdopodobieństwa znalezienia optimum.

QAOA można motywować dyskretyzacją harmonogramu adiabatycznego, ale dowolne optymalne kąty nie muszą odpowiadać monotonicznej ewolucji adiabatycznej. Krawędź relacji QAOA–annealing oznacza wspólną motywację i operatory, nie ścisłą równoważność algorytmów.

## 6.18. Quantum annealing i właściwa treść założenia adiabatycznego

**Karta i status.** [[file:qml_model_modules/17_QUANTUM_ANNEALING.md]]. Teoria atlasu; bez modelu urządzenia i temperatury nie ma uzasadnienia utożsamienia pomiaru annealera z minimum ani z dokładnym Gibbsem. Historyczne zastosowanie pola poprzecznego opisuje [@kadowaki1998].

Dla minimalizacji wygodna konwencja to

$$
H(s)=A(s)H_D+B(s)H_P,\quad H_D=-\sum_iX_i,
\quad H_P=\sum_ih_iZ_i+\sum_{i<j}J_{ij}Z_iZ_j,
\quad s=t/T.
$$

Początkowy stan podstawowy $H_D$ to $|+\rangle^{\otimes n}$. Dla QUBO $f(z)=\sum_ia_iz_i+\sum_{i<j}b_{ij}z_iz_j$ podstawienie $z_i=(1-Z_i)/2$ daje

$$
J_{ij}=b_{ij}/4,\qquad h_i=-a_i/2-\frac14\sum_{j\ne i}b_{\min(i,j),\max(i,j)},
$$

oraz nieistotną dla minimum stałą. Znaki mogą być zdefiniowane inaczej, lecz mapowanie musi zgadzać się z przyjętym Hamiltonianem.

Precyzyjna jakościowa wersja twierdzenia adiabatycznego zakłada skończeniewymiarowe, dostatecznie gładkie $H(s)$, izolowaną podprzestrzeń własną oddzieloną na całym $[0,1]$ dodatnią luką $\Delta_{\min}$ oraz stan początkowy w tej podprzestrzeni. Wtedy dla $T\to\infty$ ewolucja pozostaje blisko transportowanej podprzestrzeni; przy odpowiedniej regularności błąd jest $O(1/T)$, ze stałą zależną od pochodnych $H$ oraz odwrotnych potęg luki. Sam warunek „wolno” bez tych danych nie jest ilościową gwarancją.

Z różniczkowania $H(s)|0(s)\rangle=E_0(s)|0(s)\rangle$ i projekcji na $\langle m(s)|$, $m\ne0$, otrzymujemy

$$
\langle m|\partial_s0\rangle=\frac{\langle m|\partial_sH|0\rangle}{E_0-E_m}.
$$

Po uwzględnieniu oscylującej fazy dynamicznej typowym lokalnym wskaźnikiem jest $|\langle m|\partial_sH|0\rangle|/(T|E_m-E_0|^2)$. Nie jest on samodzielnym, uniwersalnym twierdzeniem wystarczającym bez kontroli całego harmonogramu i jego pochodnych.

Rzeczywisty układ otwarty może wymagać równania $\dot\rho=-i[H(t),\rho]+\mathcal L_t(\rho)$. Relaksacja, wzbudzenia termiczne, freeze-out i embedding zmieniają eksperyment. Dla porównania optymalizatorów trzeba mierzyć np. czas do rozwiązania przy zadanym prawdopodobieństwie, wraz z kosztem programowania i odczytu, zamiast utożsamiać liczbę kubitów fizycznych z rozmiarem efektywnego zadania.

## 6.19. VQE: zasada wariacyjna, pomiary i status SCAR

**Karta i status.** [[file:qml_model_modules/18_VQE.md]]. Teoria VQE oraz historyczny eksperyment ekspresywności ansatzu SCAR. Ten ostatni nie jest kompletnym eksperymentem minimalizacji energii. W [[code:experiments/legacy/vqe_scar_ansatz_experiment.py#L145-L199]] analizuje się próbki stanów, rozkłady fidelity i splątanie. Źródło VQE: [@peruzzo2014].

Dla hermitowskiego $H=\sum_jE_j|E_j\rangle\langle E_j|$ i $\|\psi\|=1$:

$$
\langle\psi|H|\psi\rangle=\sum_j|c_j|^2E_j\ge E_0,
\qquad E_0=\min_{\|\psi\|=1}\langle\psi|H|\psi\rangle.
$$

Ograniczenie do $|\psi_\theta\rangle=U_\theta|0\rangle$ daje minimum wariacyjne nie mniejsze niż $E_0$. Normalizacja jest konieczna: bez niej minimum kwadratowej formy nie ma tej interpretacji. Dla niezdegenerowanego ground state i luki $\Delta=E_1-E_0>0$:

$$
E(\theta)-E_0\ge\Delta(1-|\langle E_0|\psi_\theta\rangle|^2).
$$

Mały błąd energii implikuje zatem dużą fidelity dopiero po uwzględnieniu luki. Przy zdegenerowanym minimum właściwa jest projekcja na całą podprzestrzeń ground state.

Rozkład Pauliego $H=\sum_\ell c_\ell P_\ell$ daje $E=\sum_\ell c_\ell\langle P_\ell\rangle$. Dla niezależnych pomiarów poszczególnych terminów:

$$
\operatorname{Var}(\widehat E)=\sum_\ell\frac{c_\ell^2(1-\langle P_\ell\rangle^2)}{S_\ell}.
$$

Przy stałym budżecie $S=\sum_\ell S_\ell$ mnożnik Lagrange'a daje optimum $S_\ell\propto|c_\ell|\sqrt{1-\langle P_\ell\rangle^2}$, gdy wariancje są znane. Grupowanie wspólnie mierzalnych terminów wprowadza kowariancje; nie wolno wtedy bez zmian użyć powyższej sumy niezależnych wariancji.

Na czystej rozmaitości stanów $n$ kubitów jest $2^{n+1}-2$ rzeczywistych stopni swobody: $2\cdot2^n$ współrzędnych minus normalizacja i faza globalna. Gładki ansatz o $p$ parametrach ma lokalną rangę Jacobianu co najwyżej $p$. Mały $p$ nie może pokrywać otwartego obszaru wszystkich stanów, ale może wystarczyć dla wąskiej rodziny stanów podstawowych. SCAR-ring wymaga zatem oceny energii, kosztu bramek i trenowalności dla konkretnych Hamiltonianów. Niskie KL względem rozkładu fidelity Haar nie dowodzi dobrego VQE, a większa ekspresywność może pogarszać gradienty.

## 6.20. GAS: skąd bierze się pierwiastek w Groverze

**Karta i status.** [[file:qml_model_modules/19_GAS.md]]. Teoria atlasu. Grover Adaptive Search wymaga oracle kosztu, strategii dla nieznanej liczby dobrych kandydatów i kryterium zakończenia; nie jest samą pętlą zmniejszania progu.

Niech $N$ kandydatów zawiera $M\in\{1,\ldots,N-1\}$ zaznaczonych. Definiujemy unormowane superpozycje $|g\rangle$, $|b\rangle$ dobrych i złych stanów oraz

$$
|s\rangle=\sin\theta|g\rangle+\cos\theta|b\rangle,
\qquad\sin^2\theta=M/N.
$$

Oracle fazowy $O=I-2|g\rangle\langle g|$ w tej dwuwymiarowej podprzestrzeni oraz dyfuzor $D=2|s\rangle\langle s|-I$ są odbiciami. Ich iloczyn $G=DO$ jest obrotem o $2\theta$, co można sprawdzić mnożeniem macierzy $2\times2$. Po $k$ iteracjach:

$$
G^k|s\rangle=\sin((2k+1)\theta)|g\rangle+\cos((2k+1)\theta)|b\rangle,
\quad P_k=\sin^2((2k+1)\theta).
$$

Dla $M\ll N$, $\theta\approx\sqrt{M/N}$; wybór $k\approx\pi/(4\theta)-1/2$ daje stałe wysokie prawdopodobieństwo sukcesu i $O(\sqrt{N/M})$ zapytań. Zbyt wiele iteracji obniża sukces, bo obrót trwa dalej. Dla nieznanego $M$ nie wolno użyć tego wzoru jak znanej optymalnej liczby iteracji; potrzebna jest strategia losowania/rozszerzania liczby kroków albo inna wersja amplification. Podstawa: [@grover1996].

W GAS próg $y$ definiuje $g_y(x)=\mathbf1[f(x)<y]$. Rewersyjne obliczenie $f$ i porównanie z progiem powinno po phase kickback zostać odwrócone, aby usunąć rejestry robocze. Następnie mierzymy kandydata i aktualizujemy $y\leftarrow f(x)$ tylko po klasycznym sprawdzeniu poprawy. Idealny schemat szukania minimum z odpowiednią strategią osiąga oczekiwane $O(\sqrt N)$ zapytań; jest to wynik [@durr1996], a nie bezpośrednia konsekwencja dowolnej implementacji pętli GAS.

W rzeczywistym koszcie jedno zapytanie obejmuje arytmetykę funkcji, porównanie, odwrócenie i odbicia. Jeśli koszt oracle to $C_f$, czas jest co najmniej rzędu $C_f\sqrt{N/M}$ dla pojedynczego etapu, plus przygotowanie i odczyt. Precyzja wartości kosztu, liczba ancilli i błędy logiczne także należą do budżetu. To przyspieszenie nieustrukturyzowanego przeszukiwania, nie ogólna wygrana nad każdym klasycznym solverem wykorzystującym strukturę QUBO.

## 6.21. Relacje zbiorcze bez fałszywych równoważności

Dziewiętnaście kart opisuje różne poziomy abstrakcji. VQC jest zadaniem klasyfikacji w rodzinie QNN; QCBM jest generatorem rozkładu Borna; QGAN definiuje grę uczenia, której komponenty mogą być QNN. QCNN ogranicza architekturę kanałów, autoencoder definiuje kompresję rodziny stanów, a hybryda określa sposób połączenia części klasycznej i kwantowej. QBM wymaga stanu termicznego, który nie musi być przygotowywany przez PQC ani annealer.

HHL, QSVT i qPCA są procedurami algebry liniowej, ale qPCA nie jest definicyjnie instancją HHL. QSVT może zbudować nowoczesny solver układu liniowego, lecz nie jest historycznym obwodem HHL. QAOA, annealing i GAS są alternatywnymi narzędziami optymalizacji o różnych modelach dostępu; wspólny QUBO nie czyni ich tym samym algorytmem. VQE dzieli z wariacyjnym QML optymalizator i pomiary, ale jego celem jest energia, nie błąd klasyfikacji. Quantum transformer wymaga wskazania konkretnej rodziny: FTQC algebra liniowa i parametryczny model vision mają różne założenia.

Wagi podobieństw z [[file:qml_relation_metrics.md]] są heurystycznym podobieństwem opisów, nie metryką odległości spełniającą aksjomaty i nie miarą siły dowodu. Sumy $\sum_{v\in V_A\cap V_B}1/df(v)$ nie mierzą kosztu, trafności ani przewagi. Relacje w grafie należy typować jako „jest wariantem”, „może korzystać”, „dzieli aparat”, „alternatywa dla zadania” lub „zaimplementowano w”, zamiast nadawać wszystkim krawędziom sens logicznej zależności.

Przy dalszym rozwijaniu atlasu każda nowa teza o przewadze powinna zawierać: model wejścia, wymagany wynik, błąd i prawdopodobieństwo sukcesu, zasoby kwantowe, koszty klasyczne oraz uczciwy klasyczny punkt odniesienia. To warunki pozwalające przejść od mapy pojęć do weryfikowalnego projektu badawczego.


# 7. Historyczne hipotezy QSVM, SCAR i przenoszenie modeli na sprzęt

## 7.1 LEG-H2: precyzyjna rekonstrukcja reguły

Historyczny opis H2 miesza trzy własności: PSD idealnego kernela, wymiar statevectoru i jakość predykcji. Pierwsze dwie mają dowody algebraiczne przy odpowiednich założeniach. Trzecia wymaga testu. Plik źródłowy pierwotnego argumentu: [[file:analysis_output/h2_mathematical_description_proof.md]]. Faktyczna reguła wyboru znajduje się w [[code:experiments/legacy/qml_iterative_hypothesis_experiment.py#L29-L81]].

Niech C₄ będzie zbiorem kandydatów z q≥4, dopuszczonych przez rozmiar danych. Niech A_max=max_{c∈C₄}A(c) i C_near={c:A(c)≥0.95A_max}. Kod sortuje C_near leksykograficznie po (q,entanglement,−alignment,angle_scale). Zatem:

```math
c^*=\operatorname{lexmin}_{c\in C_{\mathrm{near}}}
(q_c,e_c,-A_c,\alpha_c),\qquad A(c^*)\ge0.95A_{\max}.
```

**Dowód poprawionej tezy.** Maksymalizator A należy do C_near, gdy A_max≥0, więc zbiór jest niepusty. Sortowanie wybiera element tego zbioru. Pierwsza współrzędna zapewnia najmniejsze q w C_near, a kolejne współrzędne ustalają tie-break. Nie wynika stąd maksymalizacja samego A. Przykład: A₄=0.96, A₆=1.00, próg 0.95. Reguła wybiera 4q, mimo że maksimum leży przy 6q. Jest to zamierzony kompromis koszt–alignment, wymagający właściwej nazwy.

Istnieje jeszcze przypadek brzegowy kodu: przy zbyt małym max_qubits siatka z min_qubits może być pusta, a fallback wybiera max_qubits, potencjalnie <4. Twierdzenie z twardym q≥4 wymaga precondition max_qubits≥4 albo odrzucenia takiej instancji. W zachowanych trzech datasetach nie oznacza to wykrytej zmiany wyników, ale formalna gwarancja ogólna musi uwzględniać gałąź fallback.

## 7.2 Wymiar i koszt: dowód oraz kontrprzykład

Wymiar stanu n kubitów wynosi 2^n z definicji iloczynu tensorowego. Zatem stosunek do 6q to 2^{q−6}: dla q=4 wynosi 1/4, dla q=6 jeden, a dla q=8 cztery. Warunek q≥4 obejmuje wszystkie te przypadki. Poprawna teza ma postać warunkową „jeżeli wybrano q*=4, liczba amplitud jest czterokrotnie mniejsza”.

Na symulatorze overlap dwóch zapisanych statevectorów o wymiarze d wymaga O(d) operacji, a N² par O(N²d). Przy koszcie przygotowania M bramek na stan całkowita część symulacyjna ma rząd O(NMd+N²d). Dochodzi strojenie C kandydatów i rozwiązanie układu O(N³) dla gęstej macierzy. Czterokrotna zmiana d nie gwarantuje czterokrotnie krótszego całego pipeline'u.

Na QPU reprezentacji nie zapisuje się jako tablicy 2^q amplitud. Koszt obejmuje przygotowanie, pomiary, routing, shots i ewentualne kalibracje. Relacja między d i czasem QPU nie jest tą samą relacją co dla klasycznej symulacji.

## 7.3 PCA: pełny dowód rekonstrukcji i granica interpretacji

Niech x∈R^p będzie wycentrowane, a Σ=E[xxᵀ] z wartościami λ₁≥…≥λ_p≥0. Dla ortogonalnego projektora P rzędu q:

```math
\mathbb E\|x-Px\|^2
=\operatorname{Tr}[(I-P)\Sigma]
=\operatorname{Tr}\Sigma-\operatorname{Tr}(P\Sigma).
```

W bazie własnej Σ, a_j=v_jᵀPv_j spełnia 0≤a_j≤1 i Σa_j=q. Maksymalizacja Σλ_ja_j osiąga wartość Σ_{j≤q}λ_j: przenoszenie masy z indeksu o mniejszej λ do wolnego indeksu o większej λ nigdy nie pogarsza sumy. Projektor na q pierwszych wektorów własnych osiąga tę granicę. Minimum błędu to Σ_{j>q}λ_j; stąd E₄≤E₂. To dowód rekonstrukcji, zgodny z klasycznym twierdzeniem o aproksymacji niskiego rzędu. [@eckart1936]

**Kontrprzykład predykcyjny również po standaryzacji.** Niech Z i Y będą niezależne, Z ma rozkład normalny o wariancji jeden, Y∈{−1,+1} ma równe prawdopodobieństwa. Ustal x₁=(Z+εY)/√(1+ε²), x₂=(Z−εY)/√(1+ε²). Obie cechy mają wariancję jeden. Główna składowa (x₁+x₂)/√2 zależy wyłącznie od Z i jest niezależna od etykiety. Druga (x₁−x₂)/√2 jednoznacznie określa Y. Wartości własne to 2/(1+ε²) i 2ε²/(1+ε²). Przy ε=0.1 pierwsza PCA zachowuje około 99% wariancji, lecz najlepsza klasyfikacja tylko z tej składowej ma accuracy 1/2; dwie składowe umożliwiają accuracy jeden w modelu idealnym. Zachowana wariancja nie jest zachowaną informacją o etykiecie.

Dodając niezależne kierunki o większych wartościach własnych, można umieścić sygnał etykiety poniżej dowolnego progu q. Nie istnieje ogólna gwarancja, że „cztery kubity wystarczają”, wynikająca z samej liczby kubitów.

## 7.4 Norma RKHS i pojemność nie wynikają z wymiaru rejestru

Dla klasy funkcji f_w(x)=⟨w,Φ(x)⟩, ||w||≤B, empiryczna złożoność Rademachera na N próbkach spełnia:

```math
\widehat{\mathfrak R}_N
=\frac{B}{N}\mathbb E_\sigma\left\|\sum_i\sigma_i\Phi(x_i)\right\|
\le\frac{B}{N}\sqrt{\mathbb E_\sigma\left\|\sum_i\sigma_i\Phi(x_i)\right\|^2}
=\frac{B}{N}\sqrt{\operatorname{Tr}K}.
```

**Dowód.** Supremum iloczynu skalarnego nad kulą normy B wynosi B razy norma sumy. Jensen dla pierwiastka daje nierówność. Niezależne losowe znaki mają E[σ_iσ_j]=δ_ij, więc pozostaje suma K_ii. Dla znormalizowanego kernela K_ii=1 granica to B/√N, bez bezpośredniego czynnika 2^q. Nie oznacza to niezależności całego uczenia od q: zmienia się geometria, wyuczona norma, margines i efektywne widmo. Wskazuje natomiast błąd utożsamiania Hilbert-space dimension z gotową miarą generalizacji. Kontekst teorii: [@bartlett2002].

## 7.5 SCAR: dokładny Hamiltonian i unitarność

Macierz implementacji SCAR ma blok jednowzbudzeniowy na {|01⟩,|10⟩}. Fragment: [[code:experiments/legacy/vqe_scar_ansatz_experiment.py#L51-L74]]. Zdefiniujmy:

```math
H_\delta=\tfrac12[\cos\delta(X\otimes X+Y\otimes Y)
+\sin\delta(Y\otimes X-X\otimes Y)],\qquad
U_{\mathrm{SCAR}}=e^{-i(\phi/2)Z\otimes Z}e^{-i\theta H_\delta}.
```

Na {|00⟩,|11⟩} H_δ działa jako zero. Na podprzestrzeni jednowzbudzeniowej ma macierz [[0,e^{−iδ}],[e^{iδ},0]], której kwadrat jest I. Stąd exp(−iθH_δ)=cosθ I−i sinθ H_δ na tym bloku. ZZ ma wartość −1 na bloku, więc dodaje fazę e^{iφ/2}; poza nim daje e^{−iφ/2}. Otrzymujemy dokładnie cztery wiersze kodu. Ponieważ oba generatory są hermitowskie, iloczyn jest unitarny dla wszystkich rzeczywistych θ,δ,φ.

H_δ komutuje z ZZ, więc można też zapisać pojedynczą wykładniczą exp[−i(θH_δ+(φ/2)ZZ)]. Jest lokalnie sprzężony z wymianą XY: dla D=R_z(δ/2)⊗R_z(−δ/2) mamy H_δ=D H₀D†. Tożsamość wynika z diagonalnych faz D na |01⟩,|10⟩. Parametr chiralny ma konkretną rolę, ale ta lokalna równoważność wymaga ostrożności przy roszczeniu nowości makrobramki.

Sprzętowa dekompozycja i kontrola równoważności znajdują się w [[code:tools/scar_wine_ibm_qpu.py#L57-L72]] i [[code:tools/scar_wine_ibm_qpu.py#L117-L132]]. Poprawny rozkład algebraiczny nie gwarantuje małego błędu po routingu.

## 7.6 Deskryptory ansatzu i brak dowodu VQE

Meyer–Wallach Q=2[1−n^{-1}Σ_iTr(ρ_i²)] leży w [0,1] dla stanów czystych n kubitów: czystość pojedynczego kubitu leży w [1/2,1]. Q=0 dla produktu stanów czystych; wartości wysokie wskazują mieszanie lokalnych redukcji wskutek splątania. Nie ocenia dopasowania do konkretnej funkcji celu.

Dla dwóch niezależnych stanów Haar w C^d fidelity F ma gęstość (d−1)(1−F)^{d−2}. Ustalając pierwszy wektor bazowy przez symetrię Haar, F jest pierwszą składową wektora prawdopodobieństw o rozkładzie Dirichleta(1,…,1); jego marginalny rozkład to Beta(1,d−1). Stąd prawdopodobieństwo koszyka [a,b] wynosi (1−a)^{d−1}−(1−b)^{d−1}. Implementacja deskryptora: [[code:experiments/legacy/vqe_scar_ansatz_experiment.py#L133-L174]]. Kontekst: [@sim2019].

KL między histogramem overlapów a rozkładem Haar zależy od liczby próbek, koszyków i smoothingu. Małe KL nie dowodzi uniwersalności ograniczonej rodziny parametrów. Skrypt o nazwie vqe_scar_ansatz_experiment nie minimalizuje energii konkretnego Hamiltonianu; jego wyniki dotyczą deskryptorów ansatzu. Właściwe VQE wymaga celu E(θ)=⟨ψ(θ)|H_target|ψ(θ)⟩ i optymalizacji. [@peruzzo2014]

## 7.7 Głowica, softmax i gradient

W QNN z cechami f_θ(x)∈R^m logity wynoszą z=Wf+b. Softmax p_c=e^{z_c}/Σ_ke^{z_k}; strata cross-entropy pojedynczej próbki −log p_y. Różniczkując logsumexp otrzymujemy ∂L/∂z_c=p_c−1_{c=y}, ∂L/∂W=(p−e_y)fᵀ i ∂L/∂θ=Σ_j[Wᵀ(p−e_y)]_j ∂f_j/∂θ. Jest to dokładne połączenie kwantowego estimatoru oczekiwań i klasycznej optymalizacji.

Gradient różnic skończonych (f(θ+h)−f(θ−h))/(2h) ma błąd O(h²) dla odpowiednio gładkiej funkcji. Przy niezależnym szumie pomiarowym wariancja skaluje się jak 1/(Sh²), więc bardzo małe h może pogorszyć estymację. Parameter shift daje tożsamość dla określonych generatorów; rozdział algorytmiczny wyprowadza warunki. SPSA zastępuje gradient przez (L(θ+cΔ)−L(θ−cΔ))/(2cΔ_j) z losowymi znakami Δ. Nie jest to ten sam budżet ani ten sam protokół co analityczne gradienty statevectorowe.

## 7.8 Profile urządzeń i mitygacja odczytu

Skalarny model a=F₁^{G₁}F₂^{G₂}(1−2p_readout) opisuje efektywne tłumienie oczekiwań. Nie rekonstruuje ogólnego kanału na n kubitach. Nawet przy tym samym average gate fidelity koherentna rotacja i kanał depolaryzujący mogą inaczej działać na obserwable i kolejne warstwy. Założenie niezależnego mnożenia fidelities wymaga osobnego modelu błędu.

Dla klasycznej macierzy przypisania M, M_ab=P(odczyt=a|przygotowano=b), rozkład obserwowany q=Mp. Jeśli M jest odwracalna, formalnie p=M^{-1}q. Błąd Δq przechodzi w Δp=M^{-1}Δq, więc ||Δp||≤||M^{-1}||||Δq||. Estimator może mieć ujemne składowe i wzmacniać wariancję. Tikhonov daje R_λ=(MᵀM+λI)^{-1}Mᵀ, kompromis bias–variance. W kodzie: [[code:tools/scar_measurement_mitigation.py#L8-L38]]. Kalibracja M ma własny koszt i niepewność; mitygacja nie usuwa błędów bramek.

## 7.9 Selekcja po teście i właściwy status archiwum

Funkcja wybierająca przypadek do QPU sortuje według test_balanced_accuracy_profile_shots: [[code:tools/run_best_hpo_ibm_qpu.py#L184-L225]]. Poprawne HPO po validation wewnątrz przypadku nie naprawia późniejszej selekcji datasetu i architektury według testu. Wybrany test staje się kryterium development. Potwierdzenie wybranego zwycięzcy wymaga nowego holdoutu. [@cawley2010]

Archiwum ibm_fez zawiera confusion matrix [[0,11,1],[1,13,0],[0,8,1]]: suma 35, przekątna 14, accuracy=14/35=0.400. Wynik MLP to 34/35≈0.9714. Idealny QNN miał odmienny trening 160 epok, a sprzętowy 12 epok SPSA. Rozdział wykresów pokaże oba jako odmienne procedury, bez przypisywania całej różnicy szumowi. Źródło lokalne: [[file:analysis_output/scar_wine_ibm_qpu_report.md]].

OptDigits w części starszych skryptów łączy oficjalne train i test, a potem losuje nowe splity. Oryginalny test UCI obejmuje innych autorów pisma. Nowy split definiuje inne zadanie generalizacji. To nie to samo co powielenie identycznego indeksu, ale ma znaczenie dla estymandu i porównań. [@ucioptdigits]


# 8. Analiza porównawcza i poprawne wnioskowanie

## 8.1 Miary: co dokładnie jest porównywane

Accuracy to odsetek wszystkich poprawnych predykcji. Balanced accuracy dla C klas to średnia recall: BA=C^{-1}Σ_c TP_c/(TP_c+FN_c). Macro F1 uśrednia 2TP_c/(2TP_c+FP_c+FN_c) po klasach; nie jest F1 obliczonym z uśrednionych precision i recall. Jeżeli klasa nie występuje w danym segmencie, potrzebna jest jawna konwencja, a nie milcząca zamiana braku informacji na zero.

NRMSE=sqrt(N^{-1}Σ(y_i−ŷ_i)²)/σ_y, gdzie σ_y jest populacyjnym odchyleniem w segmencie oceny zgodnie z kodem. Jednostki licznika i mianownika skracają się. NRMSE jest niezdefiniowane dla stałego celu. Nie wolno porównywać bez zastrzeżenia różnych definicji normalizacji: przez rozstęp, średnią lub odchylenie train.

R²=1−SSE/SST może być ujemne na teście. Nie jest kwadratem korelacji, chyba że zachodzą odpowiednie warunki regresji z interceptem i oceny na dopasowanej próbie. Ujemne testowe R² lub ujemne pamięci C(d) są ważną informacją o gorszej predykcji niż średnia, nie błędem do obcięcia.

## 8.2 Wykres HK: budżet pomiarowy i jakość

Wykres porównuje cztery grupy finite-shot: fidelity i projected przy 200 tys. oraz 1 mln circuit-shots. Zachowane średnie BA wynoszą odpowiednio 0.805260, 0.873357, 0.931008 i 0.958920. Przy milionie różnica projected−fidelity to 0.0855633, czyli 8.556 punktu procentowego. Przy 200 tys. wynosi 12.5748 punktu. Referencja klasyczna SVM-RBF ma 0.977539, więc projected przy milionie pozostaje niżej o 1.8618 punktu.

Źródło: [[file:results/hamiltonian/publication_summary.csv]]. Finite-shot ma 375 wierszy na grupę, ideal i klasyczne 75. SD w tej tabeli opisuje rozrzut tych wierszy. **Nie jest 95% CI ani błędem standardowym niezależnych eksperymentów.** Splity, noise replicates i warunki współdzielą informacje. Wykres średnich pokazuje rozmiar efektu, a tabela ujawnia SD i liczności bez nadawania fałszywej niezależności.

Budżet historycznego publication_benchmark dotyczy końcowej estymacji po strojeniu na idealnych statevectors. Oznacza to inne rozliczenie niż pełny koszt shotowego HPO. Tę interpretację trzeba zachować w porównaniu do v3 i QPU.

## 8.3 Wykres LEG-H2: wynik kontra wymiar

Trzy historyczne datasety pokazujemy oddzielnie dla H0 6q, agresywnego H1 i H2 z floor4. Dane pochodzą z [[file:results/legacy/iterative_qsvm_summary.csv]]. Każda średnia dotyczy dziesięciu losowych podziałów tej samej bazy. Wykres BA ujawnia wynik, a odrębny wykres stosunku amplitud pokazuje zasób statevectorowy. Oś zasobowa nie oznacza czasu QPU.

Pokazywanie obu wielkości zapobiega logicznemu skrótowi „mniej amplitud, więc lepsze uczenie”. Tabela może potwierdzać konkretne średnie archiwalne. Nie potwierdza twierdzenia o wszystkich datasetach ani niezależnej replikacji po adaptacji hipotezy do wcześniejszych wyników.

## 8.4 Wykresy QRC: miary bez mieszania estymandów

W badaniu spektralnym wyświetlamy geometryczny iloraz NRMSE i zapisane CI osobno dla przypadku oraz H1/H2. Referencją jest iloraz jeden, margines H1 to 1.02, a H2 to 0.98. Źródło: [[file:analysis_output/qrc_spectral_h1_h2/qubit_summary.csv]]. Liczba bloków wynosi osiem, więc jest to osobne badanie stresowe, a nie zakończenie protokołu z dwudziestoma blokami.

Badanie szumu zawiera kontrasty o dwóch jednostkach. BAB: finite shots−ideal i mild−ideal są różnicami wskaźnika pamięci, podczas gdy NARMA10 i MG5 podają ilorazy NRMSE. Dlatego trafiają na dwa odrębne wykresy. Źródło: [[file:results/qrc/noise_paired_contrasts.csv]]. Wspólna oś dla różnicy −8.868 i ilorazu 0.921 byłaby matematycznie myląca.

Zmiany T z H3 wyświetlamy wraz z trzema reżimami i oryginalnymi CI: [[file:analysis_output/qrc_h3_memory/h3_contrasts.csv]]. Dodatnia zmiana różnicy product−linear sama nie dowodzi wzrostu nieliniowości: może wynikać ze spadku linear. Z tego powodu drugi wykres przedstawia obie składowe pamięci na podstawie [[file:analysis_output/qrc_h3_memory/profile_summaries.csv]], rozdzielając reżim i view.

## 8.5 Dlaczego log-iloraz i geometryczna średnia

Dla dodatnich błędów E_candidate,E_ref definiujemy d_b=log(E_candidate/E_ref). Przy dwóch ustalonych zadaniach kontrast blokowy jest średnią ich log-ilorazów. Wtedy exp(mean d_b) jest geometryczną średnią ilorazów, która traktuje mnożnik 2 i 1/2 symetrycznie.

```math
R=\exp\left(\frac1B\sum_{b=1}^B d_b\right)
=\left(\prod_{b=1}^B\frac{E_{b,c}}{E_{b,r}}\right)^{1/B}.
```

Średnia ilorazów nie jest ilorazem średnich. Przykład błędów referencji (1,100) i kandydata (2,50): średnia ilorazów=1.25, geometryczna=1, iloraz średnich=52/101≈0.515. Każdy estymand odpowiada innemu pytaniu. Projekt protokołu stosuje średnie log-ilorazy na poziomie bloków; trzeba zachować tę definicję.

## 8.6 Non-inferiority i brak istotności

Dla marginesu m=log1.02 test jakości ma H0:μ≥m i H1:μ<m. Przy niezależnych blokach, modelu normalnym kontrastów i nieznanej wariancji statystyka t=(d̄−m)/(s_d/√B) ma rozkład t_{B−1} na granicy hipotezy zerowej. Odrzucamy w lewym ogonie. Wniosek równoważny kontrolowanej jednostronnej górnej granicy dla μ poniżej m.

Test H0:μ=0 kontra μ≠0 odpowiada na inne pytanie. P>0.05 w tym teście nie daje non-inferiority: szeroki CI może obejmować zarówno duże pogorszenie, jak i poprawę. Nierówność praktyczna oraz istotność statystyczna muszą być sprawdzane w tym samym kierunku. Normalność nie wynika z małej liczby bloków; kontrole leave-one-block-out i wykres wszystkich efektów służą ocenie stabilności.

## 8.7 Intersection–union: dowód reguły maksimum

H5 wymaga jednocześnie jakości i oszczędności. Zerowa hipoteza jest sumą zbiorów H0_quality ∪ H0_cost. Niech każda składowa ma prawidłowy jednostronny p-value p_Q,p_C. Odrzucenie złożonej H0 następuje, gdy oba p≤α, równoważnie max(p_Q,p_C)≤α.

**Dowód kontroli błędu.** Jeżeli H0_quality jest prawdziwa, prawdopodobieństwo odrzucenia obu jest najwyżej prawdopodobieństwo odrzucenia quality≤α. Analogicznie dla cost. Gdy obie są prawdziwe, ta sama granica pozostaje. Nie potrzeba niezależności obu p-values. Natomiast min(p_Q,p_C) potwierdzałoby tylko jeden warunek i byłoby błędne dla tezy „oba”.

## 8.8 Holm: dowód kontroli FWER

Dla m zarejestrowanych hipotez sortujemy p_(1)≤…≤p_(m), porównujemy kolejno z α/(m−j+1) i zatrzymujemy odrzucenia przy pierwszej porażce. Skorygowane p-value ma postać min[1,max_{i≤j}(m−i+1)p_(i)].

**Dowód bez wymogu niezależności.** Niech m₀ hipotez zerowych jest prawdziwych, a j oznacza pierwszy prawdziwy element w sortowaniu. Jeśli odrzucono jakąś prawdziwą H0, musiano odrzucić ten element. Ponieważ pozostało co najmniej m₀ hipotez, próg jest ≤α/m₀. Zatem wystąpiło zdarzenie min_{true}p≤α/m₀. Union bound ogranicza jego prawdopodobieństwo przez m₀(α/m₀)=α. [@holm1979]

Niewykonanych hipotez nie usuwa się z zaplanowanej rodziny w celu korzystniejszej korekty. Lokalny protokół QRC przyjmuje dla nich p=1. Korekty różnych rodzin z archiwów nie można zlać w jedną rodzinę po obejrzeniu wyników bez nowej deklaracji.

## 8.9 Bootstrap i pseudoreplikacja

Bootstrap blokowy losuje całe bloki, zachowując metody, zadania i repliki pomiarowe. Nie losuje niezależnie każdej chwili czasu, folda i seeda shots. Szereg z autokorelacją i współdzielone splity nie są iid obserwacjami.

Przy B niezależnych blokach zapisujemy wektor kontrastów d i losujemy B indeksów z powtórzeniem. W każdej replice przeliczamy tę samą średnią i ewentualną eksponentę. Percentyle 2.5% i 97.5% dają opisowy CI. Małe B i silna asymetria mogą osłabić dokładność tej procedury; nie należy uznawać jej za dokładny finite-sample test. Podstawy metody: [@efron1993].

## 8.10 Niepewność wyniku SCAR

Dla 14 poprawnych na 35 próbkach estymata accuracy wynosi 0.4. Wilson CI dla dwumianu ma środek (p̂+z²/(2N))/(1+z²/N) i półszerokość z√[p̂(1−p̂)/N+z²/(4N²)]/(1+z²/N). Przy z≈1.96 wynosi około [0.256,0.564]. To obliczenie opisowe zakłada niezależne próby o wspólnej szansie sukcesu; test Wine nie jest losową próbą całej populacji problemów. [@wilson1927]

Wykres trzech procedur pokazuje QPU 12 epok, idealny QNN 160 epok i klasyczny MLP. Różnica jakości nie izoluje jednej przyczyny. Ponadto wyniki modeli na tych samych próbkach są sparowane: formalne porównanie dwóch klasyfikatorów wymaga wyników discordant, nie tylko dwóch marginalnych accuracy.

## 8.11 Jak interpretować wykresy teorii

Krzywe kontrakcji, błędu Trottera lub progowania detektora mogą być wyliczone z wzoru. Raport oznacza je jako **model matematyczny / przykład ilustracyjny**, z podanymi parametrami, bez przedstawiania jako nowy pomiar projektu. Porównanie n=2,η=0.5 dla strat pokazuje 0.75 prawdopodobieństwa click przy loss→threshold i 0.5 przy błędnym threshold→Bernoulli. Taka ilustracja jest kontrprzykładem algebraicznym, nie walidacją całego urządzenia.


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


# 10. Kod, odtwarzalność, bibliografia i plan poprawek

## 10.1 Zakres przeglądarki kodu

Raport zawiera snapshot publicznych plików Python z pakietów hamiltonian_kernel, quantum_reservoir, photonic_kernel, experiments/legacy, tools, scripts, audits i tests oraz kart atlasu i jego demonstratora JavaScript. Dla plików Python indeks AST identyfikuje funkcje i klasy najwyższego poziomu oraz zakresy linii. Fragmenty odsyłane w wyprowadzeniach są walidowane: plik musi istnieć, a obie granice mieścić się w jego długości.

Indeks funkcji nie jest dowodem, że każda funkcja implementuje twierdzenie. Moduły danych, konfiguracji, serializacji, dostawców, raportowania i wykresów pełnią role pomocnicze. Nie przypisujemy im sztucznych hipotez. Przy węzłach naukowych wskazujemy dokładne fragmenty obliczeń; przeglądarka umożliwia odczyt pełnego pliku i jego funkcji. Archiwalne wyniki zachowują daty źródłowe. Snapshot kodu i narzędzi odświeżono po korekcie 9 października 2026; manifest wskazuje dokładną wersję każdego pliku.

Adresy w HTML otwierają wewnętrzną przeglądarkę kodu. Zapisana ścieżka bezwzględna ułatwia odnalezienie oryginału w obecnym komputerze, a kopia kodu w pakiecie i SHA-256 zapewniają działanie po przeniesieniu. Lokalny snapshot kodu nie obejmuje prywatnych profili kont, sekretów, środowisk ani zawartości folderów konfiguracyjnych użytkownika.

## 10.2 Baza i klucze cytowań

Baza report.sqlite ma tabele sources, citations, code_refs, glossary, graph_edges i hypotheses. Klucz sources.id odpowiada identyfikatorowi cytowania w HTML i BibTeX. Citations łączy go z rozdziałem. Code_refs zapisuje ścieżkę, zakres linii i hash. Graph_edges przechowuje równanie oraz warunki relacji. Hypotheses zapisuje tezę, status, założenia, uzasadnienie i proponowaną poprawkę. Dzięki temu można sprawdzić, gdzie użyto danej pracy, a nie tylko przeglądać płaską listę publikacji.

Metadane zawierają poziom inspekcji źródła. Odczyt abstraktu i potwierdzenie autorów nie jest oznaczane jako pełna lektura dowodu. Tam, gdzie raport podaje własny dowód, jego poprawność można sprawdzić lokalnie bez traktowania cytowania jako argumentu z autorytetu. Przy twierdzeniach zaawansowanych z literatury wskazujemy właściwy zakres i ograniczenia, nie obiecujemy własnego odtworzenia całej konstrukcji fault-tolerant z setek stron.

## 10.3 Odtwarzanie artefaktu

Źródła monografii znajdują się w docs/mathematical_report/chapters. Narzędzie tools/build_mathematical_report.py tworzy snapshot danych, bibliografię, indeks kodu, słownik i graf. tools/render_report_math.cjs renderuje wzory przez lokalnie zapisany KaTeX. Wersja KaTeX i jego licencja są zapisane w vendor; fonty są osadzone, więc raport nie odwołuje się do CDN.

Wersja interaktywna korzysta ze wspólnego runtime raportów. Offline export zawiera kompletny snapshot oraz renderowane wzory. Nie jest zależny od 127.0.0.1. Do weryfikacji używa się HTTP preview, natomiast oddzielny test offline blokuje zewnętrzne żądania i sprawdza nawigację, wykresy, definicje i źródła. Weryfikacja browser nie stanowi replikacji eksperymentu naukowego.

## 10.4 Kontrole matematyczne wykonane przy opracowaniu

Małe kontrole sprawdzają: unitarność SCAR dla różnych parametrów i jego lokalną równoważność XY, normowe oszacowanie Trottera na macierzach 2×2, znak nieokreślonego celu KRR, spektralną niestabilność CV przy kroku3, błędną kolejność strat detektora oraz kontrprzykład PCA. Wyniki mają etykietę „kontrola algebraiczna”; nie mieszają się z danymi BA/NRMSE zachowanych benchmarków.

Automatyczne kontrole integralności raportu weryfikują brak nieistniejących kluczy bibliograficznych, poprawne zakresy odnośników, brak błędów renderowania TeX, zachowanie wartości wykresów oraz spójność bazy. Numeryczne zgodności są porównywane z tolerancją dopasowaną do arytmetyki, a nie z arbitralnym wymaganiem bitowej równości macierzy po różnych algorytmach.

## 10.5 Priorytet poprawek naukowych

**Jądra Hamiltonowskie.** Zadeklarować estymator v3 oraz faktyczne użycie raw lub PSD naprawionego kernela, zapewnić wspólną geometrię train/cross w każdym inner fold, rozdzielić reserved i actual gate-shots oraz nazwać widmo przed i po normalizacji. Rozdział 3 podaje matematyczne uzasadnienia i doprecyzowanie kosztu strojenia dawnego benchmarku.

**QRC.** Do prób potwierdzających stosować train-only skalowanie, temporal gaps i zablokowany test. Sprawdzać rzeczywiste replay okna, współdzielone grupy pomiarowe i koszt całej historii. Warunków ESP nie zastępować washout. H1–H5 interpretować w ich własnej rodzinie; stresowe n=8 zachować jako osobne archiwum.

**Fotonika.** Sprawność detektora implementować przed threshold; overflow i postselekcję rozdzielić jako inne cechy. Przy stratach nie traktować czystego hafnianowego stanu jak ogólnego stanu mieszanego. Sprawdzać zbieżność cutoffu i masę ogona, a strojenie liczyć oddzielnie od końcowych shots.

**Legacy i sprzęt.** Poprawić tezę floor4 na warunkową o q*=4, ujawnić kompromis 95% alignmentu i fallback małej siatki. Nazwać ridge i LS-SVM zgodnie z rzeczywistym celem. Po wyborze przypadku według testu wykonać nowy holdout. Równa liczba parametrów nie wyrównuje epok, gradientów ani budżetu. Mitygację raportować z kalibracją i conditioning.

**Atlas.** Rozdzielić implementowane, projektowane i czysto teoretyczne metody. Poprawić pooling QCNN, parzystość/przestrzenie QSVT, rozkład pomiaru transformera, nieliniowe centroidy i współczynniki parameter shift. Relacje podobieństwa opisów zachować jako heurystykę organizacyjną.

## 10.6 Granice kompletności naukowej

Dokument pokrywa obecne gałęzie i karty metod, ich centralne konstrukcje, wyprowadzenia oraz ustalenia audytu. Nie zmienia faktu, że część pełnych planów eksperymentalnych nie została wykonana. Pełny dowód nowej przewagi, uniwersalności ansatzu lub jednostajnej stabilności wymagałby osobnego wyniku badawczego; brakujący dowód jest w raporcie jawnym problemem, a nie pominiętym krokiem.

Zaawansowane twierdzenia QSVT, HHL i adiabatyczne podajemy ze zdefiniowanymi warunkami oraz wyprowadzeniem mechanizmu używanego w atlasie. Kompletny konstruktywny dowód wszystkich źródłowych twierdzeń tych teorii wykracza poza matematykę implementowanego projektu i jest dostępny w cytowanych pracach. Dzięki temu czytelnik może odróżnić dowód lokalnego elementu od formalnego wyniku literaturowego, na którym opiera się dalszy projekt.
