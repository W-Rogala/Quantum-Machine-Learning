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
