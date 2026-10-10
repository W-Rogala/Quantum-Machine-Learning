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
