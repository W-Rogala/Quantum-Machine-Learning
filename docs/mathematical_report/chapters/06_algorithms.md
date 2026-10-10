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
