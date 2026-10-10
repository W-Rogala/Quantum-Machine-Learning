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
