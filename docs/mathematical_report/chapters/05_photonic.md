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
