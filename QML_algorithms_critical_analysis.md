# Krytyczna analiza algorytmów kwantowego uczenia maszynowego

## Zakres źródeł

Analiza obejmuje 1021 stron z czterech dokumentów:

- `2025/26 Quantum Machine Learning Lecture Notes` - 67 stron; najmocniejsze źródło dla VQE, QAOA, annealingu, kodowania danych, barren plateaus, QNN i metod jądrowych.
- `A Practical Guide to Quantum Machine Learning and Quantum Optimization` - 680 stron; źródło implementacyjne dla QAOA, GAS, VQE, QSVM, QNN, hybryd i QGAN.
- `Quantum Machine Learning` - 260 stron; źródło teoretyczne dla FTQC vs NISQ, quantum kernels, QNN, quantum transformer, HHL/QSVT, read-in/read-out.
- `Quantum Machine Learning: Algorithms, Applications, and Limitations` - 14 stron; syntetyczne źródło dla zastosowań, ograniczeń i mniej dojrzałych kierunków: qPCA, quantum clustering, QRL, QBM.

## Najważniejsze wnioski krytyczne

1. Najbardziej realistyczne algorytmy NISQ to dziś metody hybrydowe: quantum kernels/QSVM, VQC/QNN, QGAN/QCBM oraz QAOA/VQE jako optymalizacyjne podprogramy. Są uruchamialne, ale ich praktyczna przewaga nad klasycznymi metodami pozostaje silnie zależna od danych, encodingu i benchmarku.
2. Najmocniejsze obietnice asymptotyczne pochodzą z FTQC: HHL, qPCA, QSVT i quantum transformer. Dokumenty same wskazują jednak, że read-in/read-out, qRAM, block encoding i odczyt wyniku mogą skasować deklarowany speedup.
3. Kodowanie danych jest centralnym wąskim gardłem QML. Amplitude encoding oszczędza kubity, ale kosztuje przygotowanie stanu; angle encoding jest praktyczne na NISQ, ale bywa łatwe do klasycznej symulacji; basis encoding jest proste, lecz kubitochłonne.
4. Wariacyjne modele QML dzielą te same ryzyka: barren plateaus, koszt pomiarów, szum, dobór ansatzu, hiperparametry i niestabilność optymalizacji.
5. Algorytmy optymalizacyjne, takie jak QAOA, annealing, VQE i GAS, nie są same w sobie klasyfikatorami ML, ale są ważne dla QML jako mechanizmy doboru cech, trenowania, symulacji, chemii, generowania próbek i rozwiązywania podproblemów.
6. Zastosowania w finansach, chemii, logistyce, cyberbezpieczeństwie, obrazach i klimacie są w dokumentach dobrze motywowane, lecz najczęściej na poziomie prototypów, małych zbiorów, symulacji albo przypadków o specjalnej strukturze.

## Wyodrębnione algorytmy i charakterystyki

### 1. Quantum Kernel Methods

Specyfikacja: dane są mapowane przez kwantową feature map do stanu `|phi(x)>`, a jądro ma zwykle postać overlapu `|<phi(x)|phi(x')>|^2`. Solver może pozostać klasyczny.

Zalety: klarowny podział pracy QPU/CPU, dobra rama dla NISQ, naturalne zastosowanie w klasyfikacji i regresji.

Ograniczenia: koszt macierzy jądra rośnie jak `O(n^2)`, pomiary są zaszumione, a prosta feature map może być klasycznie symulowalna.

Zastosowania: klasyfikacja, regresja jądrowa, obrazy po redukcji wymiaru, małe dane wysokowymiarowe.

Ocena: jeden z najpoważniejszych kandydatów NISQ, ale tylko przy uczciwym porównaniu z dobrze dobranymi klasycznymi jądrami.

Źródła: Lecture Notes PDF p. 53-64; Quantum Machine Learning PDF p. 77-120; Practical Guide PDF p. 386-421.

### 2. QSVM

Specyfikacja: SVM używa jądra estymowanego obwodem kwantowym. W praktyce pipeline często obejmuje PCA, normalizację, feature map i klasyczny trening SVM.

Zalety: dobra interpretowalność przez margines, łatwa integracja z Qiskit/PennyLane/scikit-learn, czytelny benchmark.

Ograniczenia: koszt pełnej macierzy jądra, shot noise, wrażliwość na skalowanie cech, brak szerokiej przewagi empirycznej.

Zastosowania: klasyfikacja binarna, diagnostyka, finanse, cyberbezpieczeństwo, obrazy o zredukowanym wymiarze.

Ocena: dobry model do badań i demonstracji, ale nie wolno utożsamiać "kwantowego jądra" z automatyczną przewagą.

Źródła: Practical Guide PDF p. 386-421; Lecture Notes PDF p. 57-64; Algorithms paper printed p. 61.

### 3. VQC

Specyfikacja: variational quantum classifier łączy kodowanie danych, parametryzowany ansatz, pomiar obserwabli i klasyczny optimizer.

Zalety: kompatybilność z NISQ, elastyczna architektura, łatwa integracja z klasycznymi workflow ML.

Ograniczenia: barren plateaus, szum bramek, lokalne minima, duża liczba decyzji projektowych.

Zastosowania: małe klasyfikacje binarne i wieloklasowe, prototypy medyczne i finansowe.

Ocena: praktyczny standard NISQ, ale wymaga kontroli ansatzu, encodingu i baseline'ów.

Źródła: Lecture Notes PDF p. 47-52; Practical Guide PDF p. 424-464; Quantum Machine Learning PDF p. 123-181.

### 4. QNN / PQC

Specyfikacja: parametryzowany obwód kwantowy pełni rolę modelu uczącego; może być klasyfikatorem, regresorem, generatorem albo blokiem modelu hybrydowego.

Zalety: ogólna rama dla wielu modeli QML, naturalna dla danych kwantowych, kompatybilna z gradientami typu parameter-shift.

Ograniczenia: trudna trenowalność, koszt pomiarów, szum, interpretowalność, silna zależność od architektury.

Zastosowania: klasyfikacja, regresja, generowanie danych, obrazy, finanse, chemia, quantum data analysis.

Ocena: QNN to rodzina modeli, nie pojedynczy algorytm; każdą pracę trzeba oceniać przez ansatz, encoding, loss i koszt pomiarów.

Źródła: Lecture Notes PDF p. 47-52; Practical Guide PDF p. 424-516; Quantum Machine Learning PDF p. 123-181.

### 5. Hybrid QNN

Specyfikacja: klasyczny model zawiera warstwę kwantową albo QNN korzysta z klasycznego preprocessingu i klasycznego optimizera.

Zalety: najbardziej realistyczna ścieżka NISQ, zachowuje klasyczne narzędzia walidacji i wdrażania, pozwala używać QPU punktowo.

Ograniczenia: latencja QPU-CPU, kolejki, koszt shotów, trudność wykazania, że poprawa pochodzi z części kwantowej.

Zastosowania: klasyfikacja obrazów, finanse, medycyna, modele prototypowe end-to-end.

Ocena: wymaga ablation studies: model bez QPU, model z losową warstwą i model klasyczny o podobnej liczbie parametrów.

Źródła: Practical Guide PDF p. 466-516; Algorithms paper printed p. 62-63.

### 6. QGAN

Specyfikacja: generator i/lub dyskryminator jest kwantowy; model uczy rozkładu przez grę minimax. Warianty mogą generować rozkłady, stany lub obrazy w patchach.

Zalety: wykorzystuje probabilistyczny charakter pomiaru, dobrze nadaje się do dyskretnych rozkładów i małych modeli generatywnych.

Ograniczenia: niestabilność treningu GAN, barren plateaus, koszt oceny jakości próbek, trudne skalowanie.

Zastosowania: dane syntetyczne, finanse, generowanie obrazów, rozkłady losowe, chemia.

Ocena: obiecujące laboratorium generatywnego QML, ale dalekie od zastąpienia klasycznych modeli generatywnych.

Źródła: Practical Guide PDF p. 518-553; Quantum Machine Learning PDF p. 580-596 and p. 744.

### 7. QCBM

Specyfikacja: Quantum Circuit Born Machine uczy rozkładu pomiarów obwodu zgodnie z regułą Borna, bez dyskryminatora.

Zalety: prostszy cel niż adversarial minimax, naturalne próbkowanie, dobra rama do badania ekspresyjności obwodów.

Ograniczenia: dużo shotów, trudny dobór straty, problemy barren plateaus i skalowania.

Zastosowania: modelowanie rozkładów, dane binarne, syntetyczne dane finansowe, quantum state modeling.

Ocena: matematycznie czystszy niż QGAN, ale nadal ograniczony przez trenowalność i pomiary.

Źródła: Quantum Machine Learning PDF p. 744-748.

### 8. Quantum Boltzmann Machine

Specyfikacja: energetyczny model probabilistyczny oparty o Hamiltonian, często bliski Ising/QUBO lub Gibbs state.

Zalety: naturalny dla rozkładów energetycznych, można łączyć z annealingiem, ma klasyczny punkt odniesienia w RBM.

Ograniczenia: trudne próbkowanie termiczne, topologia sprzętu, temperatura i szum, trudna estymacja gradientów.

Zastosowania: dane binarne, rekomendacje, fizyka statystyczna, generowanie rozkładów.

Ocena: niszowy, bardziej naturalny w problemach fizyczno-energetycznych niż w mainstream ML.

Źródła: Algorithms paper printed p. 62; Quantum Machine Learning PDF p. 744-748.

### 9. QCNN / Quanvolution

Specyfikacja: kwantowe filtry/obwody przetwarzają lokalne patche danych lub quantum data; pooling bywa realizowany przez pomiary lub redukcję rejestru.

Zalety: strukturalnie pasuje do obrazów i lokalnych korelacji, może działać jako feature extractor.

Ograniczenia: wiele patchy oznacza wiele uruchomień obwodu, klasyczne CNN są bardzo mocnym baseline'em, przewaga nie jest jasna.

Zastosowania: obrazy, rozpoznawanie wzorców, klasyfikacja stanów kwantowych.

Ocena: sensowna architektura QNN, lecz wymaga porównań z CNN o podobnym budżecie.

Źródła: Quantum Machine Learning PDF p. 104 and p. 564; Practical Guide bibliography PDF p. 624.

### 10. Quantum Autoencoder

Specyfikacja: model uczy kompresji stanów kwantowych lub cech do mniejszego rejestru.

Zalety: naturalny dla danych kwantowych, może redukować zasoby kolejnych algorytmów.

Ograniczenia: dla danych klasycznych koszt encodingu może dominować, a ocena fidelity wymaga dodatkowych pomiarów.

Zastosowania: kompresja stanów, chemia kwantowa, denoising, redukcja wymiaru.

Ocena: najbardziej przekonujący w sektorze Q-for-Q, gdy dane są już kwantowe.

Źródła: Quantum Machine Learning PDF p. 744-748.

### 11. Quantum Transformer

Specyfikacja: FTQC-propozycja przyspieszenia inferencji transformera przez block encoding macierzy wag i sekwencji oraz procedury QSVT/linear algebra.

Zalety: adresuje realny koszt inferencji dużych modeli, daje bardziej realistyczny typ przewagi - zwykle kwadratowy, nie magicznie wykladniczy.

Ograniczenia: wymaga fault-tolerant hardware, oracles/block encoding, oraz rozliczenia read-in/read-out.

Zastosowania: NLP, modele foundation, sekwencje, wizja, robotyka.

Ocena: ważny strategicznie kierunek FTQC, ale nie narzędzie dla obecnych urządzeń NISQ.

Źródła: Quantum Machine Learning PDF p. 189-205.

### 12. HHL / Quantum Linear Algebra

Specyfikacja: HHL rozwiązuje układy liniowe i zwraca stan proporcjonalny do rozwiązania; QML używa tego jako podprogramu dla regresji, SVM, PCA i innych metod.

Zalety: źródło historycznych obietnic dużych speedupów, fundamentalny podprogram FTQC.

Ograniczenia: wymaga rzadkich i dobrze uwarunkowanych macierzy, efektywnego przygotowania danych, qRAM/block encoding i ograniczonego odczytu.

Zastosowania: least squares, SVM, PCA, rekomendacje, układy liniowe.

Ocena: bez uczciwego rachunku read-in/read-out HHL łatwo prowadzi do pozornej przewagi.

Źródła: Quantum Machine Learning PDF p. 92-100 and p. 248-296; Practical Guide PDF p. 160 and p. 1040.

### 13. QSVT

Specyfikacja: Quantum Singular Value Transformation wykonuje funkcje wartości singularnych macierzy osadzonej w unitary przez block encoding.

Zalety: porządkuje nowoczesną algebrę liniową FTQC, poprawia zależności od precyzji, wspiera HHL-like algorithms i quantum transformer.

Ograniczenia: nie jest samodzielnym modelem ML, wymaga block encoding i FTQC.

Zastosowania: linear systems, qPCA, quantum transformer, symulacje, amplitude amplification.

Ocena: kluczowa infrastruktura przyszłego QML, ale jako podprogram, nie jako klasyfikator.

Źródła: Quantum Machine Learning PDF p. 96 and p. 248-296.

### 14. qPCA

Specyfikacja: estymacja dominujących składowych macierzy gęstości lub kowariancji z użyciem procedur kwantowych, często QPE/linear algebra.

Zalety: potencjalny speedup redukcji wymiaru, naturalny dla danych kwantowych.

Ograniczenia: wymaga dostępu do density matrix/qRAM, a odczyt wielu komponentów może zniszczyć przewagę.

Zastosowania: redukcja wymiaru, analiza korelacji, preprocessing, quantum data analysis.

Ocena: obietnica sensowna głównie wtedy, gdy dane i wynik pozostają kwantowe albo odczyt jest ograniczony.

Źródła: Algorithms paper printed p. 61-62; Quantum Machine Learning PDF p. 96.

### 15. Quantum Clustering / q-k-means

Specyfikacja: kwantowy podprogram liczy odległość, podobieństwo lub overlap, a reszta algorytmu grupowania może pozostać klasyczna.

Zalety: potencjalne przyspieszenie podobieństw w danych wysokowymiarowych, naturalne dla danych kwantowych.

Ograniczenia: state preparation, odczyt centroidów, iteracyjny koszt klasyczny i silne klasyczne baseline'y nearest-neighbor.

Zastosowania: segmentacja, anomalie, bioinformatyka, analiza wzorców.

Ocena: w analizowanych źródłach raczej kierunek badawczy niż dojrzała rodzina praktycznych algorytmów.

Źródła: Algorithms paper printed p. 61-62; Practical Guide PDF p. 1412.

### 16. Quantum Reinforcement Learning

Specyfikacja: QPU może reprezentować politykę, wartość, środowisko lub przyspieszać wybór akcji przez Grover-like search.

Zalety: potencjał w eksploracji, sterowaniu i kwantowych środowiskach.

Ograniczenia: najmniej rozwinięta gałąź w dokumentach, brak standardowych benchmarków, trudna pętla pomiar-feedback.

Zastosowania: robotyka, systemy adaptacyjne, sterowanie, gry.

Ocena: mapa badań, nie gotowa praktyczna rodzina algorytmów.

Źródła: Algorithms paper printed p. 62-63; Practical Guide PDF p. 1416.

### 17. QAOA

Specyfikacja: naprzemienne warstwy Hamiltonianu kosztu i miksera, parametry optymalizowane klasycznie; szczególnie dla QUBO/Ising.

Zalety: naturalny dla optymalizacji kombinatorycznej, pasuje do NISQ, bliski annealingowi.

Ograniczenia: dobór głębokości `p`, landscape, szum, brak ogólnej gwarancji przewagi.

Zastosowania: MaxCut, QUBO, portfolio, scheduling, routing, feature selection.

Ocena: ważny silnik optymalizacji w QML, ale nie model uczący sam z siebie.

Źródła: Lecture Notes PDF p. 21-24; Practical Guide PDF p. 206-243.

### 18. Quantum Annealing

Specyfikacja: problem jest mapowany do Ising/QUBO, a annealer próbuje znaleźć stan niskoenergetyczny przez harmonogram annealingu.

Zalety: dostępny wyspecjalizowany sprzęt, duża liczba kubitów fizycznych, naturalny sampling i QUBO.

Ograniczenia: embedding topologii, brak uniwersalności, spectral gap, temperatura, brak gwarancji optimum.

Zastosowania: routing, logistyka, portfolio, scheduling, feature selection, sampling energetyczny.

Ocena: praktyczny, ale przewaga zależy od kosztu formulacji i porównania z hybrydowymi/klasycznymi solverami.

Źródła: Lecture Notes PDF p. 25-30; Practical Guide PDF p. 160-203.

### 19. VQE

Specyfikacja: minimalizacja wartości oczekiwanej Hamiltonianu przez parametryzowany ansatz i klasyczny optimizer.

Zalety: najlepiej zbadany wariacyjny wzorzec, mocny związek z chemią i materiałami, uczy technik pomiarowych ważnych dla QML.

Ograniczenia: koszt pomiarów, dobór ansatzu, szum, barren plateaus, dokładność chemiczna.

Zastosowania: chemia kwantowa, materiały, molecular simulation, optymalizacja parametrów.

Ocena: ważny dla QML jako infrastruktura wariacyjna i podprogram, nie jako klasyczny algorytm ML.

Źródła: Lecture Notes PDF p. 17-20; Practical Guide PDF p. 280-335; Quantum Machine Learning PDF p. 296.

### 20. GAS / Grover Adaptive Search

Specyfikacja: adaptacyjne użycie Grovera do znajdowania minimum, z oracle oznaczającym rozwiązania lepsze niż aktualny próg.

Zalety: jasna kwadratowa przewaga przeszukiwania, sensowny dla dyskretnej optymalizacji.

Ograniczenia: koszt konstrukcji oracle, głębokie obwody, fault tolerance dla większej skali.

Zastosowania: QUBO/HOBO, feature selection, hyperparameter search, kombinatoryka.

Ocena: ważny mechanizm search, ale w praktyce trzeba najpierw policzyć koszt oracle.

Źródła: Practical Guide PDF p. 246-277.

## Jak czytać interaktywny graf

Graf ma 20 węzłów algorytmów. Przełącznik "Cecha relacji" zmienia znaczenie krawędzi:

- `relacje eksperckie` - ręcznie kuratorowane zależności, np. QSVM -> quantum kernels, QGAN -> QNN, quantum transformer -> QSVT.
- `rodzina algorytmiczna` - łączy algorytmy należące do tej samej rodziny.
- `typ uczenia` - łączy algorytmy przez supervised, generative, optimization, reinforcement itd.
- `era/sprzęt` - pokazuje NISQ, FTQC, annealing.
- `kodowanie danych` - eksponuje wspólne zależności od angle/amplitude/feature map/QUBO/block encoding.
- `wspólne ograniczenia` - pokazuje, które algorytmy cierpią na te same bottlenecki.
- `zastosowania` - łączy algorytmy przez podobne obszary użycia.

Najbardziej pouczające widoki krytyczne to `wspólne ograniczenia`, `kodowanie danych` i `era/sprzęt`, bo szybko pokazują, że wiele pozornie różnych algorytmów dzieli te same realne bariery: przygotowanie danych, pomiary, szum i brak fault tolerance.
