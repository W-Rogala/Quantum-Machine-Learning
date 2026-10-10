# Protokół badawczy QRC–Trotter, wersja 1.0

Data: 6 września 2026 r.

Temat: **Zadaniowo optymalna trotteryzacja rezerwuarów kwantowych: wpływ dyskretyzacji na pamięć, nieliniowość i koszt predykcji szeregów czasowych.**

Status: kompletny projekt protokołu do implementacji i zamrożenia. Nie jest jeszcze prerejestracją wykonanego eksperymentu. Hipotezy, progi i liczebności poniżej są propozycjami badawczymi, nie wynikami literatury. Istniejące wyniki projektu są eksploracyjne; nie mogą zostać ponownie nazwane niezależnym potwierdzeniem.

## 1. Cel, zakres i kryterium ukończenia

Celem jest ustalenie, jak schemat Suzuki–Trottera zmienia pamięć dostępną dla ustalonego odczytu, nieliniowe przetwarzanie oraz jakość predykcji przy określonych zasobach. Nie zakładamy, że niedokładna dynamika pomaga. Rozdzielamy zachowanie jakości przy oszczędności zasobów od poprawy jakości wynikającej ze zmiany dynamiki.

Rezerwuar ma stałe parametry wewnętrzne. Uczenie obejmuje klasyczny odczyt ridge; dobór schematu i regularyzacji odbywa się wyłącznie na walidacji. Bez VQA, QAOA, VQE i bez zadania energii stanu podstawowego. Nie deklarujemy przewagi kwantowej na podstawie symulacji małych układów ani czasu działania symulatora.

Minimalny wynik magisterski: zakończone H1–H3, kontrole poprawności, klasyczne modele odniesienia i odtwarzalny raport także przy niepotwierdzonych hipotezach. H4–H5 tworzą zaplanowane rozszerzenie zasobowe. Jeśli nie zostaną wykonane, raport musi to jednoznacznie stwierdzać. QPU jest opcjonalną walidacją, nie warunkiem obrony.

## 2. Model i konwencje

Model zgodny z `core.py`:

\[
A=\sum_i h_i Z_i+J\sum_{(i,j)\in E}Z_iZ_j,\qquad B=g\sum_iX_i,
\quad H=A+B.
\]

Parametry główne: topologia ring, J=0.7, g=0.9, h_i losowane niezależnie z U[-0.5,0.5], czas między wejściami tau=0.8. Seed dotyczy pól lokalnych, nie losowania J. Dla każdego bloku pola są identyczne we wszystkich porównywanych metodach.

\[
\mathcal R_u(\rho)=|\psi(u)\rangle\langle\psi(u)|\otimes\operatorname{Tr}_0\rho,
\quad |\psi(u)\rangle=\sqrt{1-u}|0\rangle+\sqrt u|1\rangle,
\]
\[
\rho_t=U_{p,r}\mathcal R_{u_t}(\rho_{t-1})U_{p,r}^\dagger.
\]

Stan początkowy: |0...0><0...0|. Exact: U=exp[-i(A+B)tau]. Zapis macierzowy zgodny z kodem:

\[
U_{1,r}=(e^{-iB\Delta t}e^{-iA\Delta t})^r,\quad
U_{2,r}=(e^{-iA\Delta t/2}e^{-iB\Delta t}e^{-iA\Delta t/2})^r,
\quad\Delta t=\tau/r.
\]

Prawy operator działa pierwszy. Wejście jest wprowadzane raz na tau, nie między podkrokami Trottera. Zwiększanie r przy stałym tau nie zmienia liczby wejść, obserwabli ani momentów odczytu. Nie stosujemy temporal multiplexing w eksperymencie głównym.

Cechy: X_i, Z_i oraz Z_iZ_j dla krawędzi rezerwuaru, jak w kodzie. W predykcji dodajemy bieżące u_t, jak w `evaluate_configuration`; diagnostyka pamięci korzysta tylko z obserwabli, aby nie dodawać jawnej pamięci klasycznej. Każda metoda otrzymuje własny odczyt ridge. Przenoszenie tego samego odczytu między exact a Trotterem to wyłącznie dodatkowa ablacja.

## 3. Zadania i izolacja danych

### 3.1 Zestaw podstawowy

1. **Diagnostyka pamięci:** niezależne u_t ~ U[0,1], cele opisane w sekcji 4. Jedna trajektoria cech obsługuje wiele odczytów.
2. **NARMA10:** równanie zgodne z `benchmarks.py`; fizyczne wymuszenie U[0,0.5] jest kodowane jako u_t w [0,1]. Cel dostępny po kroku odpowiada konwencji indeksów generatora. Raportować identyfikację wymuszanego układu, nie autonomiczną prognozę.
3. **Mackey–Glass, h=5:** predykcja bezpośrednia x_(t+5) z historii dostępnej do t. Brak autonomicznego rollout w analizie głównej. Zachowujemy beta=0.2, gamma=0.1, wykładnik=10, opóźnienie=17 i krok Eulera=1. Wyniki dotyczą tej dyskretyzacji generatora; kontrola drobniejszego kroku to analiza czułości.

Mackey–Glass wymaga rozszerzenia generatora: niezależne początkowe historie z wartościami U[1.1,1.3] i burn-in 1000 kroków. Są to realizacje tego samego układu, nie niezależne rodziny zadań. Należy sprawdzić różność hashy trajektorii.

### 3.2 Chronologia

Każda realizacja ma 2010 indeksów wejścia, plus wymagany ogon celów i historia opóźnień:

| Indeksy t, liczone od 0 | Rola |
|---|---|
| 0–199 | washout; bez dopasowania i oceny |
| 200–1199 | train: 1000 punktów |
| 1200–1204 | przerwa: 5 punktów |
| 1205–1604 | validation: 400 punktów |
| 1605–1609 | przerwa: 5 punktów |
| 1610–2009 | test: 400 punktów |

Przerwy zapobiegają nakładaniu celów przyszłościowych h=5 na następny oceniany segment. Rezerwuar nadal przetwarza wejścia w przerwach; nie korzysta z przyszłych etykiet. Stan jest kontynuowany przez granice segmentów: to jawnie zdefiniowany scenariusz przetwarzania jednego strumienia. Nie tasujemy czasu.

Skalowanie wejść Mackey–Glass: min/max wyłącznie z train, następnie ten sam transform na wszystkich segmentach. Wartości spoza [0,1] przycinamy i raportujemy częstość clippingu osobno dla segmentów. Cele pozostają w oryginalnych jednostkach. Washout również używa skalera wyznaczonego offline na train. Standardyzacja cech ridge jest dopasowywana wyłącznie na aktualnym zbiorze dopasowania.

Po wyborze schematu i alpha dopasowujemy finalny odczyt na train+validation, bez punktów przerw. Nie przeliczamy wejściowego skalera ani dynamiki. Test jest wczytywany do oceny dopiero po zapisaniu i zahashowaniu wyborów. Nie wybieramy najlepszego seeda rezerwuaru.

### 3.3 Replikacja i seedy

Pilotaż techniczny: 4 oddzielne bloki, nieobecne w próbie potwierdzającej. Próba główna: 20 niezależnych bloków b=0,...,19. Każdy blok zawiera jedną realizację każdego zadania i jeden zestaw pól rezerwuaru, wspólne dla metod. Deterministycznie wyprowadzić seedy przez `numpy.random.SeedSequence([20260906, phase_id, b, stream_id])`; phase_id=0 dla pilota, 1 dla głównej próby; stream_id rozdziela pola, diagnostykę, NARMA, MG, pomiary i modele klasyczne. Zapisać pełny manifest i wersję NumPy.

20 bloków to budżet projektu, nie obietnica mocy. Przed zamrożeniem policzyć z pilota oczekiwaną szerokość przedziału dla głównego kontrastu. Jeśli jest zbyt duża względem marginesu 2%, przed testem wydać v1.1 z większą liczebnością albo jawnie zaakceptować ryzyko wyniku nierozstrzygającego. Nie zwiększać liczebności na podstawie istotności wyników testowych.

## 4. Metryki

### 4.1 Predykcja

Główna: NRMSE = sqrt(mean[(y-yhat)^2]) / std(y), odchylenie populacyjne jak w kodzie. Pomocniczo MAE i R²; nie zastępują głównej po obejrzeniu wyniku. Stały cel oznacza nieważną instancję generatora, którą trzeba zgłosić, nie normalizować arbitralnie.

Kontrast jakości:
\[
d_b=\tfrac12\sum_{q\in\{\mathrm{NARMA},\mathrm{MG}\}}
\log\frac{E_{b,q,\mathrm{candidate}}+10^{-12}}{E_{b,q,\mathrm{reference}}+10^{-12}}.
\]

E oznacza testowy NRMSE. exp(mean_b d_b) jest równoważonym po zadaniach geometrycznym ilorazem błędów. Raportować również oba zadania osobno. Stała 1e-12 służy tylko stabilności; jej istotny udział wymaga oznaczenia wyniku jako numerycznie zdegenerowanego.

### 4.2 Pamięć dostępna dla odczytu

Dla opóźnień d=1,...,20 uczymy osobne readouty celu v_(t-d), gdzie v=sqrt(3)(2u-1). Definiujemy:
\[
C_L(d)=1-\frac{\sum_t(v_{t-d}-\hat v_{t-d})^2}{\sum_t(v_{t-d}-\bar v_d)^2}.
\]

Wartości testowe mogą być ujemne; nie obcinamy ich przed analizą. Pokazujemy cały profil oraz sumę MC20. Jest to skończonopróbkowa zdolność rekonstrukcji konkretnego readoutu, nie pojemność całej przestrzeni Hilberta.

Nieliniowość: 10 celów v_(t-d)v_(t-d-1), d=1,...,10. Analogiczna metryka C_NL(d). Pomocniczo cele kwadratowe P2(2u_(t-d)-1), z P2(x)=(3x²-1)/2. Nie nazywamy tej ograniczonej rodziny pełną information processing capacity.

Główny skalar dla H3:
\[
T=\frac1{10}\sum_{d=1}^{10}C_{NL}(d)-\frac1{10}\sum_{d=1}^{10}C_L(d).
\]

Zmiana T nie wystarcza do wykazania kompromisu: raportować obie składowe. Sformułowanie „kompromis pamięć–nieliniowość” wymaga przeciwnych kierunków zmian, a nie tylko pogorszenia jednego zadania.

### 4.3 Dynamika i zapominanie

Infidelity procesu jak w kodzie: I=1-|Tr(U_exact† U_pr)/2^n|². To diagnostyka jednego kroku, nie funkcja celu selektora zadaniowego.

Dodatkowo odległość śladowa D_t=0.5||rho_t-rho'_t||_1 dla dwóch stanów początkowych przy identycznym wejściu. Użyć stanu |0...0> i stanu maksymalnie mieszanego; dodatkowe losowe pary w analizie czułości. Zanik D_t na skończonej próbie nie jest dowodem echo state property dla wszystkich wejść.

Odległość trajektorii exact–Trotter oraz błąd cech mierzymy na tych samych wejściach. W przypadku obcięcia historii osobno liczymy różnicę full–window. Nie utożsamiamy obcięcia z naturalnym zapominaniem.

### 4.4 Zasoby

Podawać osobno liczbę obwodów, shots, sumę circuit-shots, liczbę bramek 2Q, głębokość logiczną i ISA, oraz:
\[
C_{2Q}=\sum_c S_c G_{2Q,c}.
\]

Główne porównanie kosztu symulacyjnego: logiczne 2Q-gate-shots w tej samej dekompozycji. Nie oznacza ono równego czasu QPU. Reset, bramki 1Q i odczyt raportujemy dodatkowo. Przy urządzeniu rzeczywistym podajemy czas/zasoby z metadanych, bez zastępowania ich proxy.

Exact jest referencją numeryczną: koszt sprzętowy = NA, nigdy zero. Oszczędność bramek mierzymy względem p=2,r=16, nie względem exact. Czas NumPy nie jest przyspieszeniem kwantowym. Koszt poszukiwania schematu, finalnego treningu i inferencji zapisujemy oddzielnie i sumarycznie; H5 dotyczy kosztu wdrożonego schematu.

## 5. Hipotezy H1–H5

Analiza potwierdzająca dotyczy n=4. n=3 i n=5 służą replikacji i analizie skalowania, bez wybierania korzystnego n do głównego testu. Progi 2% i 25% poniżej są ustalonymi kryteriami praktycznej użyteczności.

### H1 — Zachowanie jakości przy tańszej dynamice

Ustalony schemat p=2,r=2 zachowuje jakość względem exact: iloraz błędów <1.02, a koszt logicznych bramek 2Q na wejście jest co najmniej 25% mniejszy niż p=2,r=16. Bez szumu, pełna historia.

H0 jakości: mean(d)>=log(1.02); H1: mean(d)<log(1.02). Test jednostronny non-inferiority. Koszt jest deterministycznym warunkiem konstrukcji, weryfikowanym z obwodów. Sukces H1 wymaga obu warunków. Brak istotnej różnicy nie dowodzi non-inferiority.

### H2 — Poprawa predykcji przez dobór dyskretnej dynamiki

Schemat wybrany na walidacji z p∈{1,2}, r∈{1,2,4,8}, bez ograniczenia infidelity, daje testowy iloraz błędów względem exact <0.98. Oddzielny wybór dla zadania i bloku; alpha dobierana każdej metodzie. Exact nie jest kandydatem selektora, lecz referencją. Tie-break: NRMSE walidacji, koszt 2Q, mniejszy p, mniejsze r.

H0: mean(d)>=log(0.98); H2: mean(d)<log(0.98). To mocna hipoteza poprawy o co najmniej 2%, a nie założony efekt. Wynik między 0.98 i 1.00 można opisać jako niewielką poprawę, lecz nie jako potwierdzenie H2. Test H2 nie dowodzi mechanizmu pamięciowego.

### H3 — Zmiana profilu przetwarzania pamięci

Ustalony p=1,r=1 zmienia T względem exact na diagnostycznym strumieniu iid. H0: mean(T_trotter-T_exact)=0; H3: różnica niezerowa, test dwustronny.

Raportować efekt i profile C_L/C_NL. Związek między zmianą profilu a NRMSE na zadaniach jest analizą eksploracyjną, nie mediacją przyczynową. H3 można potwierdzić przy pogorszeniu obu typów pamięci; wtedy nie wolno pisać o korzystnym kompromisie.

### H4 — Budżet pomiarowy zmienia względną użyteczność schematów

Porównujemy p=2,r=2 z p=2,r=16 przy wspólnym budżecie C_2Q, pełnym cofaniu historii i dwóch budżetach z sekcji 6. Główny kontrast to różnica log-ilorazów NRMSE: d_low-d_high. H0: średni kontrast=0; H4: różnica niezerowa, test dwustronny. Odniesieniem w ilorazach jest r=16 w tym samym budżecie.

H4 obejmuje szum statystyczny odczytu, bez szumu bramek. Nie izoluje wyłącznie wpływu liczby shots, bo budżet celowo sprzęga shots z głębokością. Kontrola przy równych shots rozdziela te czynniki. Syntetyczny szum bramek stanowi dodatkowe rozszerzenie, nie drugi zamienny test H4.

### H5 — Wspólny dobór historii i trotteryzacji oszczędza zasoby

Na walidacji dobieramy (p,r,W) z p∈{1,2}, r∈{1,2,4,8,16}, W∈{8,16,32}, przy S=1024 shots na grupę. Odniesienie: p=2,r=16,W=32,S=1024. Dozwolone konfiguracje mają walidacyjny NRMSE <=1.02 razy NRMSE odniesienia. Wybieramy najtańszą, potem najmniejszy błąd, p,r,W. Odniesienie należy do kandydatów, więc zbiór nigdy nie jest pusty.

Potwierdzenie wymaga testowego ilorazu błędów <1.02 oraz geometrycznego ilorazu kosztów wdrożenia <0.75. Dwa testy jednostronne tworzą test intersection–union: p_H5=max(p_jakość,p_koszt). Koszt obejmuje wszystkie odtworzenia okna i shots. Koszt wyboru polityki raportujemy osobno; nie deklarujemy oszczędności całego badania.

## 6. Macierz eksperymentów i budżet wykonania

| Etap | Rozmiary i konfiguracje | Bloki i dane | Przeznaczenie |
|---|---|---|---|
| P0 pilot | n=3,4; exact i p=1/2,r=1/2/4/8 | 4 nowe bloki; skrócone dane do kontroli, pełne do oceny wariancji | QA, czas i wykonalność; bez potwierdzania H |
| E1 główny | n=3,4,5; exact + p=1/2,r=1/2/4/8 | 20 bloków × 3 strumienie | H1–H3; 1620 trajektorii cech |
| E1-R referencja | n=4; p=2,r=16 | 20 bloków × 3 strumienie | 60 trajektorii; referencja kosztu i zbieżności |
| E2 pomiary | n=4; p=2,r=2/16; full history | 20 bloków × 2 zadania; 2 budżety; 5 replik pomiarowych | H4; 800 realizacji pomiarowych |
| E3 okno | n=4; p=1/2,r=1/2/4/8/16; W=8/16/32 | 20 bloków × 2 zadania; 5 replik pomiarowych | H5; 6000 realizacji pomiarowych |
| E4 opcjonalny | chain, inne tau, n=6 lub model szumu | z góry zapisany aneks | odporność wniosków; eksploracyjne |

E1 nie generuje osobnej trajektorii dla każdego opóźnienia; odczyty używają wspólnych cech. Liczby nie obejmują dopasowań ridge i klasycznych baseline'ów. Repliki pomiarowe współdzielą dynamikę, lecz mają niezależne zliczenia.

E2: dla każdego bloku i zadania obliczyć koszt pełnego harmonogramu odczytów r=16 przy 1024 shots na grupę: B_high. B_low=B_high/8. To identyczny budżet dla obu schematów w danym porównaniu. Liczba shots na każdą z dwóch grup jest stała w obrębie schematu: floor(B/sum_c G_2Q,c). Niewykorzystaną resztę budżetu raportować; nie rozdzielać zależnie od wyniku. Wymagane S>=1. Liczyć także osobno koszt odczytów train/validation/test. Full history znaczy od początku t=0, nie od początku segmentu.

Główne pomiary można generować na symulatorze z rozkładów Bornowskich stanów końcowych: wspólna baza Z dla Z_i i ZZ, wspólna baza X dla X_i. Używać tych samych bitstringów dla obserwabli z grupy, zachowując kowariancję. Nie losować niezależnych binomiali dla każdego ZZ. Nie oznacza to wykonania obwodów QPU. W E3 stany końcowe muszą zostać obliczone po rzeczywistym odtworzeniu okna, nie uzyskane przez odcięcie tabeli cech pełnej historii.

W E2 i E3 readout jest dopasowany i oceniany na zaszumionych cechach tej samej procedury. W każdej replice wybór na validation poprzedza test; uśrednianie replik następuje dopiero podczas analizy bloków. Nie uśredniamy cech z 5 replik, bo zwiększyłoby to faktyczny budżet pomiarowy.

E3 jest najdroższy: obowiązuje pilot czasu i pamięci. Redukcja siatki wymaga nowej wersji przed odblokowaniem testów E3. Nie wybieramy podzbioru bloków lub konfiguracji według wyniku. Opcjonalny QPU ograniczyć do zamrożonych konfiguracji i oceny zgodności estymatora, jeśli budżet nie pozwala na pełny benchmark.

## 7. Readout i modele klasyczne

Ridge alpha∈{1e-8,1e-6,1e-4,1e-2,1,100}; funkcja celu sum[(y-Xw)^2]+alpha||w||², intercept bez kary, jak w kodzie. Przy równym wyniku numerycznym (różnica <=1e-12) wybieramy większe alpha. Reguła musi być wspólna dla QRC i ridge klasycznego.

Modele odniesienia:

- Ridge z bieżącym wejściem i opóźnieniami 0,...,L-1, L∈{8,16,32}.
- Nieliniowy model opóźnień: te same wejścia, kwadraty i wszystkie unikalne iloczyny stopnia 2, ridge z tą samą siatką alpha.
- ESN: 100 jednostek, tanh, sparsity=0.1, input_scale=0.5, spectral_radius∈{0.5,0.9,1.1}, leak∈{0.2,0.5,1}; ta sama siatka alpha. Seed przypisany do bloku; zapisać dokładną konwencję macierzy i biasu przed uruchomieniem. Brak wyboru najlepszego seeda.
- Predykcja persistence dla MG, a dla NARMA średnia train jako kontrola sanity.

Nie twierdzimy, że liczba parametrów, czas lub budżet strojenia jest równy między rodzinami. Raportujemy te wielkości; baseline'y klasyczne mają własne odpowiednie reprezentacje, bez sztucznego ograniczania ich do n cech. Porównania z nimi są pomocnicze, poza pięcioma głównymi testami.

## 8. Analiza statystyczna

Jednostka replikacji: blok obejmujący strumienie i realizację rezerwuaru. Pojedyncze momenty czasu, opóźnienia, kubity, zadania ani repliki shots nie są niezależnymi obserwacjami. Zadania NARMA i MG traktujemy jako dwie ustalone rodziny. Wnioski uśrednione nie obejmują populacji wszystkich szeregów czasowych.

1. Wyliczyć sparowany kontrast na poziomie bloku; repliki shots uśrednić wewnątrz bloku, po obliczeniu log-ilorazów.
2. Główne p-values: jednopróbkowy test t kontrastów blokowych, z przesunięciem o odpowiedni margines dla non-inferiority/superiority; H3 i H4 dwustronne. Test ma przybliżoną zasadność przy niezależnych blokach i braku dominujących odstających efektów; n=20 nie gwarantuje odporności.
3. Przedziały: sparowany bootstrap blokowy 10 000 resampli, zachowujący wszystkie metody, zadania i repliki w bloku. Raportować 95% przedziały percentylowe efektów oraz jednostronne granice t odpowiadające głównym testom. Seed analizy zapisany w manifeście.
4. Korekta Holma dla dokładnie pięciu p-values H1,...,H5, family-wise alpha=0.05. H5 używa maksimum dwóch p-values. Niewykonane H traktujemy w zaplanowanej rodzinie jako p=1; nie usuwamy ich dla zwiększenia mocy.
5. Surowe 95% CI są opisowe i nie są jednoczesnymi granicami po korekcie. Potwierdzenie opiera się na skorygowanym p-value oraz kierunku efektu i warunkach praktycznych. Raportować wszystkie surowe i skorygowane p-values.
6. Wrażliwość: wykres wszystkich kontrastów, mediana, leave-one-block-out i bootstrap. Rozbieżności metod oznaczyć jako niestabilność; nie zastępować testu głównego korzystniejszym testem post hoc. Nie odrzucać obserwacji jako outlierów bez obiektywnego błędu wykonania.

Eksploracyjnie: zależność błędu predykcji od infidelity, profilu pamięci i n, z efektami bloku. Nie traktować każdego punktu siatki jako niezależnego pomiaru. Nie wyciągać wniosku o mechanizmie z samej korelacji. Krzywe testowe wszystkich schematów ujawnić dopiero po zamrożeniu wyborów; ich późniejsza interpretacja nie tworzy nowej hipotezy potwierdzającej.

## 9. Kontrole i kryteria poprawności

| Kontrola | Wymaganie |
|---|---|
| Ewolucja | U†U bliskie I, ślad rho=1, hermitowskość i dodatniość w tolerancji 1e-10 dla małych układów |
| Granica przemienna | B=0: exact i Trotter zgodne numerycznie |
| Zbieżność | kontrola na r=8,16,32; brak wymogu monotoniczności w każdym punkcie, ale raport błędu i reżimu asymptotycznego |
| Chronologia | test jednostkowy mapowania t na cel i luk dla h=5; żadna cecha nie używa przyszłego wejścia |
| Skalowanie | zmiana ogona testowego nie zmienia skalera ani wyborów walidacyjnych |
| Odczyt | test zerowego sygnału i opóźnionego sygnału o znanej zależności |
| Pamięć | reset całego rezerwuaru przy każdym wejściu jako kontrola bez pamięci; nie dodawać opóźnień klasycznych |
| Pomiar | suma prawdopodobieństw=1; korelacje ZZ liczone ze wspólnych bitstringów |
| Koszt | przeliczenie liczników z wygenerowanych obwodów; zerowe kąty nie mogą tworzyć fikcyjnych bramek |
| Selekcja | plik wyborów bez metryk testowych, hash zapisany przed oceną testu |
| Okno | W obejmuje bieżące wejście i W-1 poprzednich; przy W>=t+1 zgodność z pełną historią |

Washout=200 nie jest założeniem dowiedzionego zapominania. Jeśli pilot wskazuje istotną zależność od inicjalizacji, ustalić dłuższy washout przed zamrożeniem albo jawnie badać rezerwuar z ustaloną inicjalizacją. Nie ukrywać tego przez nazwanie go echo-state reservoir.

Kontrola J=0 oraz wyłączonych cech ZZ sprawdza rolę sprzężeń i odczytu. Nie dowodzi kwantowego pochodzenia ewentualnej korzyści. Dodatkowo tau∈{0.4,1.6} przy stałym r służy rozróżnieniu efektu czasu ewolucji od samej dyskretyzacji; poza główną rodziną H1–H5.

## 10. Odniesienie do istniejącego kodu i wymagane zmiany

Przegląd plików na dzień protokołu, bez audytu całego repozytorium:

| Element | Stan | Działanie przed próbą potwierdzającą |
|---|---|---|
| `core.py`: reset-injection, exact, Trotter 1/2 | istnieje | zachować konwencję kolejności i testować zgodność |
| `core.py`: cechy X,Z,ZZ | istnieją | dodać diagnostykę pamięci i trace distance |
| `experiment.py`: ridge i NRMSE | istnieją | ujednolicić tie-break, seedy i przerwy czasowe |
| `evaluate_configuration` | liczy test każdemu kandydatowi przed wyborem schematu | rozdzielić tuning, zapis wyborów i final evaluation; obecny wybór korzysta z validation, lecz bariera testu jest za słaba |
| `select_trotter_configuration` | narzuca infidelity<=0.01 | zachować jako historyczne ramię; dodać jawne selektory H2 i H5 bez tego progu |
| `_candidate_statistics` | agreguje zadania i seedy w jeden wybór | zastąpić wyborem per zadanie/blok zgodnie z hipotezą |
| `benchmarks.py`: MG | min/max z całej trajektorii; stała historia początkowa | usunąć przeciek testu; train-only scaler, niezależne historie i burn-in |
| `benchmarks.py`: MG nazwa | stałe h5 niezależnie od argumentu | generować nazwę z rzeczywistego h |
| `SplitConfig` | domyślnie 50/450/150/300, bez luk | nowy jawny układ z sekcji 3 |
| `ibm_hardware.py` | replay i history_window istnieją | wykorzystać jako definicję odtwarzania; dodać wspólny licznik całkowitego kosztu |
| Pomiary, statystyka, baseline'y | nie są kompletne w przejrzanej ścieżce | dodać moduły i niezależne testy przed uruchomieniem |

Zapisane wcześniej dane MG z globalnym skalowaniem pozostają wyłącznie pilotażowe. Naprawa wymaga regeneracji danych i wyników, nie korekty samej tabeli. Ten dokument nie modyfikuje jeszcze implementacji.

## 11. Artefakty i zamrożenie

Wymagane pliki dla każdego uruchomienia:

- `protocol.json`: wersja, pełne siatki, progi, seedy, koszty i status etapu.
- `manifest.json`: SHA-256 protokołu, kodu, danych, wersje bibliotek i środowisko.
- `splits.csv`, `data_manifest.json`, `hamiltonians/`: indeksy, seedy i współczynniki.
- `validation_candidates.csv`, `selections.json`: wybory bez testu, reguły tie-break.
- `test_metrics.csv`, `predictions/`, `memory_profiles.csv`, `resource_costs.csv`.
- `hypothesis_tests.csv`: kontrasty blokowe, progi, p raw/Holm, CI i status każdej H.
- `failures.json`: wszystkie niepowodzenia, brakujące bloki i powody ponowień.
- `report.md` oraz wykresy: profile pamięci, NRMSE vs infidelity, Pareto koszt–NRMSE, porównania sparowane i analiza okna.

Kolejność: implementacja → testy → pilot → ewentualna jawna rewizja → hash protokołu → trening/walidacja → hash wyborów → odblokowanie testu → analiza całej rodziny hipotez. Techniczne niepowodzenia wolno ponawiać na identycznym seedzie; selektywne usuwanie bloków zabronione. Brak pełnej próby oznacza raport niekompletności, a nie zastąpienie danych wygodniejszymi seedami.

## 12. Kryterium wartości naukowej i kontynuacja

Potencjalny rezultat publikacyjny: powtarzalna reguła ograniczania kosztu (H1/H5), poprawa zadaniowa (H2) albo wyjaśniona zmiana profilu pamięci (H3), wraz z kontrolami, rzetelnym kosztem i porównaniami klasycznymi. Żadne p-value samo nie gwarantuje publikowalności; konieczne są nowość względem literatury i odporność wyniku.

Wynik negatywny jest pełnoprawnym rezultatem: można określić zakres stabilności QRC na dyskretyzację i ograniczenia tanich realizacji. Nie nazywać błędu Trottera regularyzacją bez odpowiednich dowodów generalizacji.

Doktorat: teoria propagacji błędu w kanałach z pamięcią, projektowanie profili pamięci, adaptacyjny podział zasobów i pomiary online z backaction. Podstawowa ścieżka magisterska nie wymaga rozwiązania tych problemów ani wprowadzenia QHD.

## 13. Literatura kierunkowa

Poniższe źródła uzasadniają kontekst, nie nowość proponowanych hipotez ani wybrane progi:

1. [Memory–Nonlinearity Trade-off across Quantum Reservoir Computing Frameworks, preprint 2026](https://arxiv.org/abs/2603.21371).
2. [Fisher-Orthogonal Memory in Quantum Reservoir Computing, preprint 2026](https://arxiv.org/abs/2607.29219).
3. [Quantum reservoir computing induced by controllable damping, 2026](https://doi.org/10.1038/s41534-026-01229-8).
4. [Predicting chaotic dynamics on NISQ hardware with quantum reservoir networks, 2026](https://www.nature.com/articles/s42005-026-02652-1).
5. [Mitigating algorithmic errors in Hamiltonian simulation, 2018](https://arxiv.org/abs/1808.03623).
6. [Efficient and practical Hamiltonian simulation from time-dependent product formulas, 2025](https://www.nature.com/articles/s41467-025-57580-5).

Przed zgłoszeniem publikacji wymagany jest osobny, ukierunkowany przegląd prac o dyskretyzacji QRC. Ten protokół nie stanowi dowodu pierwszeństwa.
