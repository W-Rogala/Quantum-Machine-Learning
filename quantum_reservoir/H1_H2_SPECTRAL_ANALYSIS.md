# H1 i H2: analiza spektralna, przypadki krytyczne i realizacja fizyczna

Data: 6 września 2026. Status: analiza matematyczna i eksploracyjny eksperyment stresowy, uzupełniający `RESEARCH_PROTOCOL_H1_H5.md`. Nie zastępuje zamrożonego testu 20 bloków H1–H5. Wyniki liczbowe, manifest i kod eksperymentu są w `../analysis_output/qrc_spectral_h1_h2/` oraz `spectral_h1_h2_study.py`.

## 1. Najpierw: co ma widmo dyskretne, a co ciągłe?

Nie należy utożsamiać zmiennych ciągłych (CV), ciągłego czasu i ciągłego widma energii.

| Obiekt | Model kubitowy | Model CV na L²(R) |
|---|---|---|
| Hamiltonian | skończone widmo dyskretne | może mieć widmo dyskretne, ciągłe albo mieszane |
| Przykład energii | macierz Isinga 2^n × 2^n | oscylator harmoniczny: dyskretne E_k; cząstka swobodna: ciągłe E>=0 |
| Obserwabla | skończone wartości własne | q i p mają widmo ciągłe |
| Macierz/operator gęstości | skończenie wiele wartości własnych | normalny stan opisany operatorem śladowym ma co najwyżej przeliczalne niezerowe wartości własne; zero może być punktem skupienia |
| Czas | może być ciągły mimo kubitów | może być dyskretnie próbkowany mimo CV |
| Kanał pamięci | macierz superoperatora | operator na przestrzeni operatorów; własności zależą od normy i dziedziny |

Wektory |q> są uogólnionymi wektorami własnymi, nie normalizowalnymi stanami o skończonej energii. Widmo operatora gęstości opisuje zmieszanie; nie zastępuje widma generatora lub kanału pamięci. W szczególności skończona truncacja Focka zawsze daje macierz ze skończonym widmem i sama nie dowodzi zachowania modelu z widmem ciągłym.

W QRC trzeba równolegle rozważać:

1. E_j Hamiltonianu H;
2. fazy operatora U(tau), zależne od E_j tau modulo 2pi;
3. widmo i odpowiedzi kanału wejściowego F_u=Ad_U o R_u;
4. dostępność tych odpowiedzi w konkretnych obserwablach i przy skończonej liczbie pomiarów.

Różne energie mogą mieć identyczną fazę po próbkowaniu. Duża przestrzeń Hilberta nie gwarantuje ani dostępnej pamięci, ani przewagi predykcyjnej.

## 2. H1 jako warunkowe twierdzenie o stabilności

H1 z protokołu dotyczy p=2,r=2: NRMSE nie większego niż 1.02 razy exact i redukcji logicznego kosztu względem p=2,r=16. Ten punkt siatki nie może działać jednolicie dla wszystkich Hamiltonianów i czasów.

### 2.1 Skończony wymiar i błąd jednego kroku

Dla ograniczonych A,B, przy stałym czasie tau i r rosnącym:

\[
\|U-U_{1,r}\|=O\!\left(\frac{\tau^2}{r}\|[A,B]\|\right),
\]
\[
\|U-U_{2,r}\|=O\!\left(\frac{\tau^3}{r^2}
(\|[A,[A,B]]\|+\|[B,[A,B]]\|)\right).
\]

Są to skale asymptotyczne, nie oszacowania liczbowe ze stałą równą 1. Normy i stałe mogą rosnąć z n. Protokół infidelity procesu jest inną metryką: mała średnia infidelity nie daje automatycznie małego błędu każdej istotnej cechy w każdym stanie.

Ponieważ R_u jest kanałem CPTP:
\[
\sup_\rho\|F_u(\rho)-\widetilde F_u(\rho)\|_1
\le2\min_\phi\|U-e^{i\phi}\widetilde U\|=: \varepsilon.
\]

Z samej nieekspansywności kanałów wynika jedynie błąd trajektorii <=t epsilon (i trywialnie <=2). Potrzebny jest mechanizm zapominania, aby uzyskać ograniczenie jednostajne w czasie.

### 2.2 Istotny przypadek krytyczny: reset jednego kubitu nie daje q<1 w jednym kroku

W aktualnym modelu dwa stany o identycznym kubicie wejściowym i ortogonalnych stanach reszty rezerwuaru pozostają doskonale rozróżnialne po R_u i wspólnej ewolucji unitarnej. Współczynnik kontrakcji jednego kroku w normie śladowej jest zatem równy 1.

Nie wolno bez dodatkowego założenia napisać, że reset pierwszego kubitu daje ||delta rho_t||<=q||delta rho_(t-1)|| z q<1. Kod eksperymentu sprawdza ten kontrprzykład numerycznie. Możliwa jest kontrakcja po kilku krokach, po dodatkowym tłumieniu albo na podprzestrzeni istotnej dla odczytu.

Jeżeli dla KAŻDEJ dozwolonej sekwencji wejść blok długości L dokładnej dynamiki ma współczynnik kontrakcji q<1, to przez teleskopowanie błędu przybliżonego bloku:
\[
\|\delta\rho_{kL}\|_1\le q^k\|\delta\rho_0\|_1+
L\varepsilon\frac{1-q^k}{1-q}.
\]

Dla pozostałych indeksów dolicza się najwyżej (L-1)epsilon. To warunkowy lemat stabilności, nie stwierdzenie, że aktualny rezerwuar spełnia jego założenia. Długa pamięć (q bliskie 1) zwiększa wrażliwość na zaburzenia — obiecujący temat doktorancki.

Widmo kanału przy zamrożonym u=0.5 jest diagnostyką, nie dowodem tego warunku. Dla zmiennych wejść istotne są iloczyny ograniczeń kanałów do różnic stanów, ich wspólna kontrakcja i ewentualne wzmocnienie przejściowe. Promień spektralny <1 każdego zamrożonego operatora osobno nie wystarcza w ogólności dla przełączanego układu. Przy nie-normalnych operatorach samo widmo pomija wzmocnienia przejściowe.

### 2.3 Od stanu do predykcji

Dla ograniczonych obserwabli:
\[
|\operatorname{Tr}(O_j\delta\rho)|\le\|O_j\|_\infty\|\delta\rho\|_1.
\]

Dla m obserwabli Pauliego błąd wektora cech jest <=sqrt(m)||delta rho||_1. Duży, niestabilny readout może ten mały błąd powiększyć.

Przykładowe samodzielne oszacowanie dla ridge z ustalonym skalowaniem i ustalonym lambda>0: minimalizujemy ||Xw-y||²/N+lambda||w||². Załóżmy ||x_i||<=R, ||delta x_i||<=delta, |y_i|<=Y. Wtedy
\[
\|w\|\le RY/\lambda,\qquad
\|\widetilde w-w\|\le\frac{\delta Y}{\lambda}
+\frac{(2R\delta+\delta^2)RY}{\lambda^2}.
\]

Wynika to z ||delta(XᵀX/N)||<=2R delta+delta², ||delta(Xᵀy/N)||<=delta Y oraz tożsamości resolwenty. Dla cechy testowej z takimi samymi ograniczeniami:
\[
|\widetilde y-y_{\rm pred}|\le \delta RY/\lambda
+(R+\delta)\|\widetilde w-w\|.
\]

Różnica RMSE jest nie większa od RMS różnic predykcji (nierówność trójkąta). Po podzieleniu przez odchylenie celu daje to wystarczający, zwykle konserwatywny warunek H1. Dla względnego marginesu 2% trzeba porównać granicę z 0.02 NRMSE_exact; mały błąd absolutny nie wystarcza, gdy exact przewiduje niemal idealnie.

To oszacowanie nie obejmuje zmiany alpha w selektorze ani osobno dopasowanych skalerów bez dodatkowej kontroli ich stabilności. W kodzie alpha odpowiada N lambda. Praktycznie badać uwarunkowanie macierzy cech, normę odczytu i wrażliwość na alpha, a nie tylko widmo H.

### 2.4 Koszt

Dla obecnego ring z n=4 i niezerowym J licznik logiczny daje 8(r+1) bramek CX dla kroku Stranga: r=2 →24, r=16 →136. Redukcja wynosi 82.35%, przed routingiem, resetem i odczytem. To porównanie dwóch przybliżeń cyfrowych, nie kosztu cyfrowego z „darmowym exact”. Kompilacja i sprawdzenie zgodności są częścią eksperymentu.

## 3. H2 jako projektowanie alternatywnej dynamiki

H2 mówi, że schemat wybrany na validation daje co najmniej 2% poprawy testowego błędu względem ustalonej dokładnej dynamiki. Nie wynika to z twierdzenia Trottera.

Dla konwencji kodu U_step=e^(-iB h)e^(-iA h), lokalnie wokół h=0:
\[
H_{\rm eff}=H+\frac{i h}{2}[A,B]+O(h^2).
\]

Operator i[A,B] jest hermitowski. Strang usuwa poprawkę pierwszego rzędu i zaczyna od zagnieżdżonych komutatorów rzędu h². Logarytm U jest wielowartościowy; interpretacja przez gładką gałąź H_eff i ucięcie BCH jest lokalna. Nie należy stosować jej bez kontroli do rezonansowych, grubych kroków.

Nowe człony mogą zmienić transport informacji i dostępność opóźnień dla odczytu. Możliwe są też niekorzystne rezonanse, zatrzymanie mieszania i utrata pamięci. Korzystny efekt może być zwykłym lepszym doborem architektury dla zadania, bez przewagi kwantowej i bez znaczenia „regularyzacji”.

### 3.1 Kontrole potrzebne do mocnej interpretacji

- **Przemienność:** [A,B]=0 → exact i Trotter identyczne; H2 nie może dać ścisłej poprawy poza błędem numerycznym/statystycznym.
- **Brak sprzężeń J=0:** pozostałe kubity nie otrzymują informacji o bieżącym wejściu; rezerwuar może mieć długą zależność od inicjalizacji, ale brak użytecznej pamięci wejść. Długowieczny mod nie jest automatycznie pamięcią zadania.
- **Równe shots oraz równy budżet:** rozdzielić zmianę dynamiki od korzyści płytszych obwodów.
- **Dostrojona referencja exact:** oprócz pierwotnego exact(tau=0.8,J=0.7,g=0.9) porównać exact z równym budżetem walidacyjnego strojenia tau,g,J. Poprawa nad jednym arbitralnym Hamiltonianem jest słabsza od korzyści nad dobrze dostrojoną klasą referencyjną.
- **Kontrola kolejności:** AB vs BA, Strang ABA vs BAB, przy tym samym koszcie. Pozwala powiązać zmianę z komutatorami. To rozszerzenie, nie wykonany główny test.
- **Odczyt:** osobno readout trenowany ponownie i zamrożony readout exact; rozdzielają zmianę reprezentacji od jej stabilności.
- **Generalizacja:** nowe strumienie, nowe pola, niezależny test; kilka wybranych wygranych seedów nie potwierdza H2.

Jeśli H2 działa tylko przy exact o słabym profilu pamięci, właściwy rezultat brzmi „dyskretyzacja umożliwia dostrojenie rezerwuaru”, nie „błąd symulacji poprawia każdy QRC”.

## 4. Zmienne ciągłe i operatory nieograniczone

W CV A=p²/2, B=omega² q²/2 są nieograniczone. Ich komutatory także. Skończonowymiarowa granica normowa przeniesiona bezpośrednio może być nieskończona. Zbieżność silna (dla ustalonego stanu) nie oznacza jednostajnej zbieżności w normie operatorowej na wszystkich stanach.

Potrzebne są: właściwe dziedziny i samosprzężoność, kontrola energii oraz błąd ograniczony do klasy fizycznie dostępnych stanów. Można definiować np.
\[
\varepsilon_E=\sup_{\rho:\operatorname{Tr}(G\rho)\le E}
\|F(\rho)-\widetilde F(\rho)\|_1,
\]
gdzie G jest dodatnim operatorem kontrolującym energię, np. liczbą fotonów; nie odwróconym Hamiltonianem nieograniczonym od dołu. Wzmocniona norma kanałowa uwzględnia również ancillę. Trzeba kontrolować energię także po wielu krokach i wejściach.

Dla q,p oraz q²,p² nie wolno użyć bezpośrednio skończonej normy ||O||∞. Potrzebne są ograniczenia odpowiednich momentów i ogonów; samo małe prawdopodobieństwo na brzegu obcięcia nie kontroluje automatycznie wszystkich nieograniczonych obserwabli. Gdy używa się czwartego momentu lub nierówności Cauchy'ego–Schwarza, założenia momentowe należy zapisać jawnie.

### 4.1 Kontrolowany model Gaussowski bez truncacji

Eksperyment używa jednego modu, hbar=1, wektora średnich m i kowariancji V. Przed ewolucją wprowadzamy wejście przez przesunięcie q o 0.25(2u-1), następnie stosujemy macierz symplektyczną S i kanał strat o transmisji eta:
\[
m_t=\sqrt\eta S(m_{t-1}+d(u_t)),\quad
V_t=\eta S V_{t-1}S^T+(1-\eta)I/2.
\]

Cechy to <q>,<p>,<q²>,<p²>,<(qp+pq)/2> oraz u_t. Jest to model fizycznie kwantowo dopuszczalny, ale efektywnie symulowalny klasycznie. Nie może sam dostarczyć dowodu przewagi obliczeniowej QRC. Tutaj nieliniowe cechy pochodzą z drugich momentów przesuniętego stanu; nie z dowolnej nieliniowej ewolucji Schrödingera.

Badane rodziny:

- omega²=1: oscylator o dyskretnym widmie energii; q,p ciągłe.
- omega²=0: swobodna cząstka z ciągłym widmem energii; B=0 i splitting jest dokładny — kontrola negatywna H2.
- omega²=-1: odwrócony oscylator z ciągłym widmem; test niestabilności i stabilizacji stratami. To wymagający model dynamiczny, nie pasywny oscylator w stanie równowagi.

Dla ustalonego S o zanikaniu średnich i skończonej stacjonarnej kowariancji decyduje Schur-stabilność M=sqrt(eta)S. Dla rho(M)<1 dyskretne równanie Lapunowa ma skończone rozwiązanie. Wzmocnienie przejściowe może nadal powodować duże energie. To kryterium konkretnego modelu liniowo-Gaussowskiego, nie wszystkich kanałów CV w normie śladowej.

### 4.2 Analityczny kontrprzykład dla bezwarunkowej H1

Dla oscylatora omega=1 exact jest rotacją; przy eta<1 M ma promień sqrt(eta)<1. Dla pojedynczego kroku Stranga o h=tau/r:
\[
\det S_h=1,\qquad \operatorname{Tr}S_h=2-h^2.
\]

Dla |h|>2 macierz ma rzeczywiste wzajemnie odwrotne wartości własne, z jedną o module >1. Straty mogą być zbyt słabe, aby ją ustabilizować. Dla tau=3,r=1,eta=0.8 exact jest stabilny, natomiast splitting jest niestabilny. Nie jest to „szum pomiarowy” ani błąd obcięcia Focka: kontrolujemy momenty analitycznie, bez obcięcia. Symplektyczność i unitarność kwantowa nie gwarantują ograniczenia energii.

W reżimie niestabilnym nie raportujemy NRMSE jako normalnego wyniku uczenia. Kod zatrzymuje propagację przy średniej liczbie fotonów >1e9, oznacza brak wyniku i zachowuje diagnozę. Uznanie takiego przypadku za korzystną nieliniowość byłoby błędem.

### 4.3 Kontrola Focka

Dodatkowo dla oscylatora propagujemy stany koherentne alpha=0.4 i 2.5 w wymiarach 8,16,32,64, porównując <q²> z dokładną gaussowską ewolucją tego samego schematu. Raportujemy odrzuconą masę początkową oraz końcową masę na dwóch najwyższych poziomach.

Różnica między przybliżeniem Focka a gaussowskim wynikiem splittingu jest błędem truncacji. Różnica gaussowskiego splittingu i gaussowskiego exact jest błędem dyskretyzacji. Błędy te należy zmniejszać niezależnie. Test jednego kroku nie gwarantuje zbieżności całej długiej sekwencji.

## 5. Projekt wykonanego eksperymentu eksploracyjnego

Kod jest odrębny od legacy benchmarku i nie zmienia prerejestracji H1–H5. Używa poprawionego train-only skalowania MG i niezależnych historii MG, chronologii 200 washout / 600 train / 5 gap / 250 validation / 5 gap / 300 test, 8 sparowanych bloków oraz p=1,2 i r=1,2,4,8. Exact jest numeryczną referencją.

Kubitowe przypadki: standard tau=0.8; weak tau=0.1; B=0; J=0; tau=3.2; tau=pi/0.9. Ten ostatni zeruje mieszanie od kicku X dla r=1 z dokładnością do fazy: nie należy utożsamiać go z ogólnym przejściem fazowym. Pola i dane są wspólne dla metod.

Selekcja H2 korzysta tylko z validation; wybory są zapisane przed testem danego bloku. Następnie wszystkie schematy są oceniane dla analizy stresowej. Nie wybieramy przypadków do raportu na podstawie testu. Przedziały t i p-values są eksploracyjne; Holm obejmuje 12 kontrastów (6 przypadków × H1/H2). Próba nie ma liczebności, siatki ani długości z potwierdzającego protokołu.

Diagnostyka widma zamrożonego kanału jest wykonywana dla n=3, a predykcja i profile pamięci dla n=4. Wyników tych nie łączymy w ilościową korelację „widmo wyjaśnia predykcję”; są odrębnymi kontrolami. Pomiar zaniku odległości stanów obejmuje 100 kroków i jedną ustaloną sekwencję.

Model CV ma 5 przypadków i ten sam readout oraz dane. Porównania CV są opisowe, nie podlegają kubitowym testom H1/H2. Nie porównujemy liczby modów z liczbą kubitów jako równych zasobów.

## 6. Implementacja fizyczna: co sprawdzono, a co pozostaje

### Kubity nadprzewodzące / procesory bramkowe

Wykorzystujemy istniejący `build_replay_circuit`: reset kubitu wejściowego, RY kodujące u, RZ/RZZ dla A i RX dla B. Testy sprzętowej ścieżki obejmują n=4, p=2,r=2/16, W=8/32:

1. Kompilację na jawną syntetyczną linię 4 kubitów, basis rz,sx,x,cx,reset, seed=71, optimization_level=2. Plik QPY jest artefaktem kompilacji, nie wynikiem QPU ani prawdziwym ISA konkretnego backendu.
2. Niezależną ewolucję density-matrix w Aer obwodu logicznego i porównanie z modelem macierzowym dla tego samego okna.
3. Syntetyczny depolarizing error po CX, siła 0,0.001,0.01, jako test wpływu głębokości na stan końcowy. Nie jest to kalibracja IBM ani pomiar jakości predykcji na sprzęcie. Reset i bramki 1Q pozostają idealne w tej kontroli.

Żadne zadanie nie jest wysyłane do fizycznego QPU. Pełny eksperyment fizyczny wymaga konkretnego backendu, aktualnego Target i kalibracji, harmonogramu pomiarów oraz budżetu. Wyniku kompilacji, Aer lub QPY nie wolno nazwać walidacją sprzętową.

Na QPU trzeba oddzielnie zbadać reset, readout, routing i czasy oczekiwania. Rezerwuar replay nie utrzymuje jednej fizycznej kopii stanu między wszystkimi odczytami: odtwarza historię dla każdej mierzonej chwili. Koszt rośnie z oknem. Stałe okno zmienia model pamięci. Realizacja online wymaga jawnego instrumentu pomiarowego/backaction i nie jest identyczna z bezinwazyjnym odczytem symulatora.

### Fotoniczne / mikrofalowe CV

Gaussowski S można realizować przez rotacje, squeezery i ich złożenia, straty przez sprzężenie z próżnią, wejście przez displacement. Homodyna estymuje momenty, ale pomiar i sprzężenie do odczytu trzeba uwzględnić w kanale. Fizyczny QRC z natywną pamięcią wymaga pętli opóźniającej lub zachowania modu między wejściami.

W oscillatorze harmonicznym dokładna rotacja jest natywnie prosta; splitting na ścinania może być droższy. Dlatego kubitowego twierdzenia o oszczędności CX nie przenosimy na fotonikę. CV H1 musi używać kosztu danej realizacji, np. liczby squeezers, maksymalnego squeezing, strat i shots.

Dla dalszego rozwoju nieliniowego CV można dodać Kerr chi(a†a)² i sprawdzić cutoff/energię. To dopiero propozycja: nie wykonano w tym eksperymencie nieliniowej symulacji Kerr ani fotonicznego QPU. Oscylator Kerr nadal może mieć dyskretne widmo; nie jest automatycznie modelem ciągłego widma energii.

## 7. Obiecujące rozwinięcia i kryteria falsyfikacji

1. **H1 warunkowana mieszaniem:** dobrać r do błędu bloku kanału i wrażliwości odczytu, zamiast do samego infidelity. Falsyfikacja praktyczna: reguła nie przenosi się na nowe strumienie/pola lub koszt jej oszacowania przewyższa oszczędność.
2. **H2 jako inżynieria komutatorów:** porównać ABA/BAB i dostrojone exact przy równym budżecie wyszukiwania. Korzyść znikająca po dostrojeniu exact jest wynikiem o doborze architektury, nie przewadze splittingu jako takiego.
3. **Ochrona przed rezonansem:** odrzucać kroki z zanikiem zapisu wejścia, nie tylko dużym infidelity. W CV dodać warunek Schur-stabilności, kontrolę energii i maksymalnego squeezing.
4. **Pamięć dostępna pomiarowo:** optymalizować rozróżnialność opóźnień dla konkretnych obserwabli i shots, z odniesieniem do informacji Fishera. Nie utożsamiać kwantowej informacji Fishera z informacją osiągalną przez ograniczony odczyt.
5. **Model CV poza Gaussowskim:** jako osobny etap zbadać Kerr, cutoff i porównania z klasycznymi reservoirami. Wykładniczy koszt konkretnego symulatora nie jest dowodem braku efektywnej symulacji klasycznej.

Najsilniejszy temat magisterski pozostaje kubitowym, niewariacyjnym QRC ze spektralnymi kontrolami kanału. CV stanowi wartościowy test granic i możliwe rozszerzenie doktoranckie; nie należy łączyć od razu pełnej teorii nieskończonego wymiaru, Kerr i QPU w jeden obowiązkowy zakres magisterki.

## 8. Źródła pierwotne

- Martínez-Peña i Ortega, [Quantum reservoir computing in finite dimensions](https://doi.org/10.1103/PhysRevE.107.035306), 2023 — reprezentacja kanałowa, ESP/FMP.
- Kobayashi i in., [Extending echo state property for quantum reservoir computing](https://arxiv.org/abs/2403.02686), 2024 — pamięć i uogólnienia ESP.
- [Gaussian states of continuous-variable quantum systems provide universal and versatile reservoir computing](https://www.nature.com/articles/s42005-021-00556-w), 2021 — kontrolowany punkt odniesienia Gaussowski.
- [Convergence Rates for the Trotter Splitting for Unbounded Operators](https://doi.org/10.1007/s10208-025-09730-w), 2025 — ograniczenia przenoszenia normowych oszacowań.
- [Energy-Limited Quantum Dynamics](https://doi.org/10.1007/s00220-025-05282-w), 2025 — normy ograniczone energią.
- [Quantum localization bounds Trotter errors in digital quantum simulation](https://pmc.ncbi.nlm.nih.gov/articles/6461450/), 2019 — interpretacja Floqueta i reżimy błędów.
- [Experimental memory control in continuous-variable optical quantum reservoir computing](https://www.nature.com/articles/s41566-026-01880-9), 2026 — realizacja fotoniczna z pamięcią.
- [Fisher-Orthogonal Memory in Quantum Reservoir Computing](https://arxiv.org/abs/2607.29219), preprint 2026 — dostępność pamięci przy skończonych pomiarach.
- [IBM: Execute dynamic circuits](https://quantum.cloud.ibm.com/docs/en/guides/execute-dynamic-circuits) — aktualne wymagania wykonania obwodów dynamicznych.

Własne lemmy i przykłady powyżej podano z założeniami; źródła nie są deklaracją, że te konkretne hipotezy i eksperymenty zostały już opublikowane.

## 9. Wnioski po wykonaniu testów

Pełne tabele i wykresy: [raport wyników](../analysis_output/qrc_spectral_h1_h2/RESULTS.md).

- **H1 jest warunkowa.** Dla tau=0.1 iloraz błędów wyniósł 0.9979 (95% CI [0.9964,0.9994]); dla standardowego tau=0.8: 0.9859 [0.9411,1.0327], co nie rozstrzyga marginesu 2%. Dla tau=pi/g: 1.6815 [1.5505,1.8237], czyli wyraźne pogorszenie ustalonego p=2,r=2.
- **H2 jest obiecująca jako dobór reprezentacji.** W pierwszej próbie dla tau=3.2 selektor dał 0.8568 [0.8091,0.9074] względem ustalonego exact. Na 8 nowych blokach uzyskał 0.8964 [0.8138,0.9872] względem tego samego rodzaju referencji, ale 1.0023 [0.9107,1.1032] względem walidacyjnie dostrojonego exact. Nie wykazano korzyści nad dostrojoną rodziną exact. Nowa próba wspiera kierunek poprawy nad stałym exact, lecz jej dwustronny CI nie mieści się w całości poniżej progu H2=0.98.
- **Nie wykazano przewagi nad klasycznym uczeniem.** Iloraz wobec modelu kwadratowych cech opóźnień wyniósł 2.3613 [1.1338,4.9181] w dodatkowej próbie. Porównanie wymaga interpretacji per zadanie i nie jest dowodem asymptotycznej przewagi żadnej rodziny.
- **CV wymaga bramki stabilności.** Dla tau=3,eta=0.8 exact ma rho(M)=0.8944, a Strang r=1: 6.1305. Strang r=2 przywraca rho(M)=0.8944. Odwrócony oscylator przy eta=0.8 jest niestabilny również dla exact; przy eta=0.1 stabilizuje się.
- **Realizacja cyfrowa ma duży narzut.** Dla okna W=32 kompilacja syntetyczna daje 1532 CX i depth=2714 przy r=2, wobec 8700 CX i depth=15708 przy r=16. To około 82.4% mniej CX, ale nadal głęboki obwód. Brak wykonania na QPU.

### 9.1 Dlaczego rezonans p=2,r=2 niszczy pamięć w tym modelu?

Można wyjaśnić go dokładnie, bez dopasowania do wyników. Niech D=sum h_i Z_i, C=J sum ZZ i tau=pi/g. W kroku Stranga r=2 mamy h=tau/2, a exp(-iBh) jest, z dokładnością do fazy, P=produkt_i X_i. Zachodzi PDP=-D, PCP=C oraz [D,C]=0. Zatem
\[
e^{-i(D+C)h/2}P e^{-i(D+C)h/2}=e^{-iCh}P
\]
z dokładnością do fazy. Dwa podkroki dają e^(-iC tau) razy fazę: cała ewolucja między wejściami jest diagonalna. Przy pamięci początkowej |0...0> i resecie wejścia pozostałe kubity nie zapisują historii w tym układzie. To konkretny kontrprzykład dla uniwersalności H1, a nie ogólne twierdzenie o wszystkich rezerwuarach w rezonansie.

### 9.2 Proponowana rewizja kierunku badawczego

Zachować H1/H2 oryginalnego protokołu do niezależnej próby, ale obok nich rozwinąć program **doboru dyskretyzacji z kontrolą zapisu, zapominania i stabilności odczytu**. Nie zmieniać po wyniku definicji H2 na łagodniejszą. Najważniejszy nowy benchmark powinien zawierać dostrojoną referencję exact, modele opóźnień, otoczenie rezonansu (nie tylko pojedynczy punkt) i kontrolę energii CV.
