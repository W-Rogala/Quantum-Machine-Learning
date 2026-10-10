# Główne osiągnięcia pracy i ich uzasadnienie

Ocena stanu opublikowanego 10 października 2026. Podstawą są zachowane wyniki,
implementacje, monografia i audyt. Nie jest to nowa replikacja eksperymentów
ani ocena pierwszeństwa w literaturze. Znane konstrukcje matematyczne wskazujemy
jako wykorzystany i wyjaśniony fundament, bez przypisywania projektowi ich odkrycia.

## 1. Wynik porównawczy: sposób odczytu ma znaczenie przy ograniczonym budżecie

Najmocniej udokumentowany wynik empiryczny dotyczy Hamiltonian kernels:
porównania estymatora wierności (`fidelity`) z kernelem na lokalnych cechach
(`projected`) w benchmarku symulowanych pomiarów. Balanced accuracy (BA) jest
średnią czułości po klasach; różnice poniżej podano w punktach procentowych.

| Budżet circuit-shots | Fidelity: średnia BA | Projected: średnia BA | Projected − fidelity |
|---|---:|---:|---:|
| 200 000 | 80,53% | 93,10% | +12,57 p.p. |
| 1 000 000 | 87,34% | 95,89% | +8,56 p.p. |
| Idealna symulacja stanu, bez pomiarów losowych | 97,40% | 97,38% | −0,01 p.p. |

Liczby pochodzą z [publication_summary.csv](../results/hamiltonian/publication_summary.csv).
Różnice policzono z niezaokrąglonych średnich; dlatego różnica zaokrąglonych
komórek tabeli może odbiegać o 0,01 p.p. Dane sparowane dla największego budżetu
są w [primary_paired_deltas.csv](../results/hamiltonian/primary_paired_deltas.csv).

**Dlaczego to osiągnięcie:** wynik pokazuje praktyczne znaczenie wyboru
reprezentacji pomiarowej. Sama dobra jakość idealnej mapy stanów nie wystarcza:
trzeba jeszcze oszacować użyteczny kernel w dostępnym budżecie. Dla analizowanych
warunków projected zachowuje większą średnią jakość przy finite-shot.
Kontrast z idealną symulacją pomaga postawić pytanie o odporność estymatora,
choć sam w sobie nie jest izolowaną identyfikacją przyczyny efektu.

**Granice:** trzy ustalone zbiory (`moons`, WDBC, wine), mały układ i wspólny
preprocessing PCA(4). 375 obserwacji w każdym wierszu finite-shot to zależne
wyniki foldów, powtórzeń i realizacji pomiarów, a nie 375 niezależnych zadań.
Klasyczny SVM-RBF ma średnią BA 97,75%; wynik nie dowodzi przewagi kwantowej.
Nie utożsamiamy opisowej różnicy średnich z niezależnie potwierdzonym efektem
w populacji wszystkich zadań ML. Ograniczenia inferencji opisuje
[audyt Hamiltonian kernels](audit/hamiltonian_review.md).

Kod: [estymacja projected](../hamiltonian_kernel/estimation.py#L289),
[estymacja fidelity](../hamiltonian_kernel/estimation.py#L139),
[wykonanie benchmarku](../hamiltonian_kernel/publication_benchmark.py#L664).

## 2. Wspólny opis matematyczny kernelów i rezerwuarów

Monografia porządkuje ciąg:

\[
\text{dane lub historia wejść}\longrightarrow\rho
\longrightarrow\phi_j=\operatorname{Tr}(O_j\rho)
\longrightarrow K_{ab}=\phi_a^\mathsf{T}\phi_b
\longrightarrow\text{odczyt ridge}.
\]

Dla pełnej bazy Pauliego, przy \(d=2^n\),
\(\operatorname{Tr}(\rho\sigma)=d^{-1}\sum_P
\operatorname{Tr}(P\rho)\operatorname{Tr}(P\sigma)\).
Ograniczony zestaw obserwabli daje inną reprezentację; nie wolno automatycznie
utożsamiać jej z pełnym iloczynem Hilberta–Schmidta.
Przy zgodnym centrowaniu i tej samej konwencji regularyzacji odczyt ridge
w przestrzeni cech ma równoważną postać dualną na macierzy Grama.

**Dlaczego to osiągnięcie:** daje wspólny język porównania różnych gałęzi
projektu i wyjaśnia, co dokładnie łączy je w grafie. Wspólna ewolucja unitarna
zachowuje pełny iloczyn Hilberta–Schmidta; odczyt ograniczony, reset i kodowanie
zależne od danych mogą zmieniać dostępne cechy. Relacje grafowe mają więc
konkretne transformacje i warunki, zamiast sugerować równoważność wszystkich modeli.

Materiał: [most kernelowy](mathematical_report/chapters/02_kernel_bridge.md),
[transformacje](mathematical_report/chapters/09_transformations.md),
[graf z warunkami relacji](mathematical_report/graph.json).
Kontrole: [kod](../tools/check_kernel_reservoir_comparison.py),
[zapis wyników](../results/qrc/kernel_reservoir_checks.json).
Zapisana rozbieżność primal–dual wynosi około \(4{,}27\cdot10^{-15}\);
jest to kontrola numeryczna, uzupełniająca wyprowadzenie, a nie nowy benchmark.

## 3. Metodologia łącząca jakość z kosztem całej procedury

Benchmark obejmuje zagnieżdżoną walidację krzyżową, preprocessing dopasowywany
wewnątrz foldów i po 12 konfiguracji dla każdej porównywanej rodziny.
Oddzielnie raportuje circuit-shots, wykonania mapy i koszt bramek dwukubitowych
ważony liczbą pomiarów:

\[
C_{2Q}=\sum_c S_cG_{2Q,c}.
\]

Estymator projected wykorzystuje wspólne bitstringi dla obserwabli w danej bazie,
zachowując ich korelacje. Adaptery sprzętowe rozdzielają obwód logiczny,
kompilację i wykonanie; przewidują zapis QPY, layoutów, hashy i kalibracji.

**Dlaczego to osiągnięcie:** porównanie ma kontrolować również koszt uzyskania
modelu i danych pomiarowych. Równa liczba shots nie zawsze oznacza równy koszt
wykonania mapy ani równą liczbę bramek. Jawne osie kosztu pozwalają tę różnicę
zobaczyć i ograniczają ryzyko korzystnego, lecz nieporównywalnego benchmarku.

Źródła projektu: [protokół benchmarku](../hamiltonian_kernel/PUBLICATION_BENCHMARK.md),
[selekcja wewnętrzna](../hamiltonian_kernel/publication_benchmark.py#L268),
[rachunek zasobów](../hamiltonian_kernel/estimation.py#L73).
**Granice:** części v3 nadal mają ustalenia H-01–H-03; tych zalet nie należy
przenosić bezwarunkowo na każdą wersję historycznych eksperymentów.
Pełny plan Trotter v3 ma wykonany 1 z 1600 warunków.

## 4. Rozdzielenie dynamiki, pamięci i informacji dostępnej dla odczytu

Analiza QRC rozróżnia widmo Hamiltonianu, fazy ewolucji, widmo kanału wejściowego
oraz obserwowalność przez wybrane cechy. Badania obejmują cele pamięci liniowej
i nieliniowej, kontrole readoutu, washout, rezonans i szum.

**Dlaczego to osiągnięcie:** precyzuje mechanizm, który należy sprawdzić, zanim
przypisze się poprawę predykcji „większej pamięci kwantowej”. Reset jednego kubitu
nie gwarantuje ścisłej kontrakcji całego stanu w jednym kroku. Wykazany
kontrprzykład zawęża założenia potrzebne do stabilności. Dodatnia zmiana różnicy
pamięci nieliniowej i liniowej może wynikać z pogorszenia tej drugiej, więc
konieczne jest raportowanie obu składowych.

Materiał: [analiza spektralna i warunkowy lemat stabilności](../quantum_reservoir/H1_H2_SPECTRAL_ANALYSIS.md),
[wyprowadzenia QRC](mathematical_report/chapters/04_reservoir.md),
[definicje celów pamięci](../quantum_reservoir/h3_memory_study.py#L75),
[audyt rezerwuarów](audit/reservoir_review.md).
**Status:** osiągnięcie analityczne i eksploracyjne. Nie jest ukończonym
potwierdzeniem H1–H5 ani dowodem korzystności Trottera dla wszystkich rezerwuarów.

## 5. Kontrolowane porównanie reprezentacji fotonicznych

Implementacja GBS (Gaussian Boson Sampling) tworzy z tych samych zdarzeń cechy
wzorców, momentów, klas zdarzeń i orbit. Sweep bada cutoff, straty i detektory;
zdarzenia poza cutoffem mają jawny bin overflow.

Dla znormalizowanych histogramów cechy \(\sqrt{p_k(x)}\) dają
\(K(x,x')=\sum_k\sqrt{p_k(x)p_k(x')}\), dodatnio półokreślony kernel
z konstrukcji jako iloczyn skalarny.

**Dlaczego to osiągnięcie:** ponowne użycie tych samych zdarzeń pozwala ograniczyć
mieszanie wpływu reprezentacji z wpływem innej realizacji losowej. Overflow
ujawnia masę pomijaną przez cutoff i pomaga uniknąć ukrytej postselekcji.
Jest to osiągnięcie implementacyjne i metodologiczne; opis nie przypisuje
mu wykazanej przewagi predykcyjnej.

Materiał: [protokół odporności](../photonic_kernel/ROBUSTNESS.md),
[budowa kernelów](../photonic_kernel/robustness.py#L80),
[wyprowadzenia fotoniczne](mathematical_report/chapters/05_photonic.md).
**Granice:** brak deklarowanego wykonania na fotonicznym QPU; adapter SF ma
otwarty problem P-01 dotyczący kolejności sprawności detekcji i progowania.

## 6. Powiązanie wyprowadzeń, kodu, danych i bibliografii

Źródła monografii obejmują 12 rozdziałów, 42 źródła bibliograficzne, 21 hipotez
i 21 relacji w grafie matematycznym. Bibliografia jest dostępna w BibTeX,
CSL JSON i SQLite; manifest wiąże odnośniki kodu z jego treścią.
Interaktywna wersja offline zawiera nawigację, słownik, równania, wykresy
i przeglądarkę kodu. Gotowy HTML/ZIP jest lokalnym produktem wydania;
w repozytorium zachowano jego źródła i zasoby.

**Dlaczego to osiągnięcie:** czytelnik może przejść od twierdzenia do warunków,
publikacji, implementacji i danych. Rejestr hipotez odróżnia dowód warunkowy,
kontrprzykład, wynik eksploracyjny i plan badania. Audyt ujawnia także błędy,
co czyni wnioski łatwiejszymi do oceny i dalszego rozwijania.

Walidacja aktualizacji: 109/109 testów kodu oraz 22/22 kontroli matematycznych
i integralności; browser QA sprawdził 1075 odnośników wewnętrznych.
Są to kontrole poprawności technicznej i wybranych tożsamości, a nie
certyfikacja wszystkich twierdzeń lub empirycznych hipotez.
Materiał: [monografia i instrukcja](mathematical_report/README.md),
[rejestr korekty i kontroli](mathematical_report/REVIEW_2026-10-09.md),
[audyt](audit/README.md).

## Jak sformułować wkład pracy

> Praca rozwija odtwarzalny warsztat badania kwantowych map cech i rezerwuarów,
> łącząc analizę matematyczną z porównaniem jakości predykcji przy ograniczonych
> zasobach pomiarowych. Najmocniejszym zapisanym wynikiem empirycznym jest wyższa
> średnia balanced accuracy estymatora projected względem fidelity w określonym
> benchmarku finite-shot. Wkład obejmuje też wyjaśnienie relacji między modelami,
> analizę warunków stabilności i pamięci oraz kontrolę metodologii i odtwarzalności.

Projekt dostarcza podstaw do dalszej pracy publikacyjnej. Twierdzenie o nowości
względem całej literatury wymaga osobnego przeglądu, a przewaga kwantowa i hipotezy
potwierdzające wymagają nowych, kompletnych eksperymentów.
