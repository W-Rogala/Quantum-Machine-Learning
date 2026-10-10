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
