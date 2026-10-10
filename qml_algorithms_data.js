window.QML_DATA = {
  documents: {
    lecture_notes_2025_26: "2025/26 Quantum Machine Learning Lecture Notes",
    practical_guide_qml_qo: "A Practical Guide to Quantum Machine Learning and Quantum Optimization",
    quantum_machine_learning_book: "Quantum Machine Learning",
    algorithms_applications_limitations: "Quantum Machine Learning: Algorithms, Applications, and Limitations"
  },
  nodes: [
    {
      id: "quantum_kernels",
      label: "Quantum Kernel Methods",
      short: "Mapowanie danych do stanu kwantowego i estymacja jadra k(x,x').",
      family: ["Metody jadrowe", "NISQ"],
      learning: ["nadzorowane", "regresja"],
      era: ["NISQ", "FTQC"],
      computing: ["model bramkowy", "hybrydowy"],
      encoding: ["feature map", "angle encoding", "amplitude encoding", "basis encoding"],
      training: ["klasyczny solver jadrowy", "estymacja overlapu"],
      advantage: ["ekspresyjne przestrzenie cech", "naturalne jadra kwantowe", "mozliwa przewaga na danych sztucznie dopasowanych"],
      limitations: ["koszt przygotowania danych", "liczba pomiarow", "ryzyko jadra latwo symulowalnego klasycznie", "trudne benchmarki"],
      applications: ["klasyfikacja", "regresja", "obrazy", "male dane wysokowymiarowe"],
      maturity: "wysoka jako prototyp NISQ, umiarkowana jako praktyczna przewaga",
      specs: [
        "Jadro zwykle ma postac |<phi(x)|phi(x')>|^2.",
        "Mozna trenowac klasyczny SVM lub regresje jadrowa na macierzy KQ.",
        "Kluczowy projektowy wybor to feature map: zbyt prosta bywa klasycznie symulowalna, zbyt losowa moze slabiej generalizowac."
      ],
      strengths: [
        "Dobrze oddziela czesc kwantowa od klasycznego uczenia: QPU liczy jadro, solver pozostaje klasyczny.",
        "Naturalna droga do wykorzystania ograniczonych urzadzen NISQ.",
        "Latwo porownac z klasycznymi jadrami, o ile benchmark jest uczciwy."
      ],
      weaknesses: [
        "Sama wysoka wymiarowosc Hilberta nie daje automatycznie lepszego modelu.",
        "Koszt macierzy jadra rosnie kwadratowo z liczba probek.",
        "Przewaga znika, gdy feature map lub dane maja skuteczny opis klasyczny."
      ],
      critical: "Najbardziej sensowny kandydat NISQ do malych zadan klasyfikacyjnych, ale wymagajacy rygorystycznego benchmarku przeciw dobrze dobranym klasycznym jadrom.",
      sources: ["Lecture Notes PDF p. 53-64", "Quantum Machine Learning PDF p. 77-120", "Practical Guide PDF p. 386-421", "Algorithms paper printed p. 61"]
    },
    {
      id: "qsvm",
      label: "QSVM",
      short: "SVM z jadrem estymowanym przez obwod kwantowy.",
      family: ["Metody jadrowe", "Klasyfikatory"],
      learning: ["nadzorowane", "klasyfikacja"],
      era: ["NISQ", "FTQC"],
      computing: ["model bramkowy", "hybrydowy"],
      encoding: ["feature map", "angle encoding", "amplitude encoding"],
      training: ["klasyczny SVM", "dual SVM", "kernel estimation"],
      advantage: ["nieliniowa separacja", "mozliwy speedup jadra", "teoretyczna przewaga dla specjalnych dystrybucji"],
      limitations: ["macierz jadra O(n^2)", "szum pomiarowy", "dobor feature map", "brak szerokiej przewagi empirycznej"],
      applications: ["klasyfikacja binarna", "diagnostyka", "finanse", "obrazy po redukcji wymiaru", "cyberbezpieczenstwo"],
      maturity: "dojrzaly edukacyjnie, eksperymentalny produkcyjnie",
      specs: [
        "Praktyczne pipeline'y czesto redukuja wymiar danych PCA, potem koduja cechy w rotacjach.",
        "Model klasyfikacyjny jest klasyczny, ale wartosci jadra pochodza z QPU lub symulatora.",
        "Wersje FTQC moga uzywac HHL/linear algebra, lecz wtedy dochodza mocne zalozenia o dostepie do danych."
      ],
      strengths: [
        "Czytelna interpretacja przez margines i jadra.",
        "Latwa integracja z narzedziami typu scikit-learn, Qiskit i PennyLane.",
        "Dobra baza do naukowych benchmarkow QML."
      ],
      weaknesses: [
        "Dla duzych zbiorow pomiar calej macierzy jadra jest waskim gardlem.",
        "Kwantowy koszt kodowania moze przewyzszyc korzysc z estymacji jadra.",
        "Wyniki zalezne od skalowania cech, redukcji wymiaru i liczby shotow."
      ],
      critical: "QSVM jest atrakcyjny dydaktycznie i badawczo, lecz w realnych danych trzeba udowodnic nie tylko dokladnosc, ale przewage nad RBF, polynomial i dobrze strojona klasyczna metoda.",
      sources: ["Practical Guide PDF p. 386-421", "Lecture Notes PDF p. 57-64", "Quantum Machine Learning PDF p. 86-120", "Algorithms paper printed p. 61"]
    },
    {
      id: "vqc",
      label: "VQC",
      short: "Wariacyjny klasyfikator kwantowy trenowany klasycznym optymalizatorem.",
      family: ["QNN", "VQA", "Klasyfikatory"],
      learning: ["nadzorowane", "klasyfikacja"],
      era: ["NISQ"],
      computing: ["model bramkowy", "hybrydowy"],
      encoding: ["angle encoding", "data re-uploading", "feature map"],
      training: ["klasyczny optimizer", "parameter shift", "gradient-free"],
      advantage: ["kompatybilnosc z NISQ", "elastyczny ansatz", "integracja z ML"],
      limitations: ["barren plateaus", "szum bramek", "duzo hiperparametrow", "lokalne minima"],
      applications: ["klasyfikacja binarna", "klasyfikacja wieloklasowa", "male zbiory danych", "prototypy medyczne i finansowe"],
      maturity: "wysoka jako wzorzec NISQ, ograniczona skala praktyczna",
      specs: [
        "Obwod ma warstwe kodowania danych oraz trainable ansatz.",
        "Wynik pochodzi z pomiaru obserwabli, np. Pauli Z, a strata moze byc MSE lub cross-entropy.",
        "Gradienty czesto liczy sie regula przesuniecia parametru."
      ],
      strengths: [
        "Dziala na plytkich obwodach i pasuje do obecnych platform.",
        "Daje modulowy most miedzy klasycznym preprocessingiem a QPU.",
        "Mozna stosowac strategie data re-uploading dla dodatkowej nieliniowosci."
      ],
      weaknesses: [
        "Trenowalnosc pogarsza sie wraz z liczba kubitow i glebokoscia.",
        "Brak gwarancji, ze ansatz reprezentuje wlasciwa hipoteze.",
        "Pomiar i szum wprowadzaja koszt statystyczny nieobecny w klasycznej sieci."
      ],
      critical: "VQC to roboczy kon QML NISQ: najlatwiej go uruchomic, ale najlatwiej tez przecenic, jesli nie kontroluje sie ansatzu, danych i kosztu pomiarow.",
      sources: ["Lecture Notes PDF p. 47-52", "Practical Guide PDF p. 424-464", "Algorithms paper printed p. 61-62", "Quantum Machine Learning PDF p. 123-181"]
    },
    {
      id: "qnn",
      label: "QNN / PQC",
      short: "Parametryzowany obwod kwantowy jako model uczacy.",
      family: ["QNN", "VQA"],
      learning: ["nadzorowane", "generatywne", "regresja"],
      era: ["NISQ", "FTQC"],
      computing: ["model bramkowy", "hybrydowy"],
      encoding: ["angle encoding", "amplitude encoding", "data re-uploading", "quantum data"],
      training: ["parameter shift", "gradient descent", "Adam", "pomiar obserwabli"],
      advantage: ["ekspresyjnosc obwodow", "uczenie na danych kwantowych", "mniejsza liczba probek w wybranych rezyimach"],
      limitations: ["barren plateaus", "koszt pomiarow", "szum", "interpretowalnosc", "dobor ansatzu"],
      applications: ["klasyfikacja", "regresja", "generowanie danych", "kwantowa chemia", "obrazy", "finanse"],
      maturity: "centralny paradygmat badawczy, nadal bez ogolnej przewagi praktycznej",
      specs: [
        "QNN zwykle laczy encoder danych, warstwy trainable oraz pomiar.",
        "Deterministyczne modele zwracaja wartosci oczekiwane, probabilistyczne modele zwracaja rozklady.",
        "Warianty obejmuja MLP-like QNN, QCNN, QGAN, QCBM, QBM i autoenkodery."
      ],
      strengths: [
        "Jedna rama opisuje klasyfikatory, regresory i generatory.",
        "Mozna ja osadzic w TensorFlow, PyTorch, PennyLane lub Qiskit.",
        "Naturalna dla danych kwantowych, gdzie klasyczne odczytanie pelnego stanu jest drogie."
      ],
      weaknesses: [
        "Wzrost ekspresyjnosci nie zawsze idzie z trenowalnoscia.",
        "Plytkie obwody moga byc zbyt slabe, glebokie moga byc zbyt zaszumione.",
        "Wyniki sa bardzo wrazliwe na inicjalizacje, architekture i pomiary."
      ],
      critical: "QNN to szeroka rodzina, nie pojedynczy algorytm; krytyczna ocena musi zawsze pytac o ansatz, encoding, loss, pomiary i uczciwy klasyczny baseline.",
      sources: ["Lecture Notes PDF p. 47-52", "Practical Guide PDF p. 424-516", "Quantum Machine Learning PDF p. 123-181", "Algorithms paper printed p. 62"]
    },
    {
      id: "hybrid_qnn",
      label: "Hybrid QNN",
      short: "Klasyczna siec z warstwa kwantowa lub QNN z klasycznym preprocessingiem.",
      family: ["QNN", "Hybrydowe"],
      learning: ["nadzorowane", "klasyfikacja", "regresja"],
      era: ["NISQ"],
      computing: ["hybrydowy", "model bramkowy"],
      encoding: ["angle encoding", "feature reduction", "classical preprocessing"],
      training: ["backprop przez interfejs QNode", "parameter shift", "classical optimizer"],
      advantage: ["praktyczna integracja", "modularnosc", "wykorzystanie klasycznych bibliotek"],
      limitations: ["latencja QPU-CPU", "szum", "trudny podzial pracy", "koszt treningu"],
      applications: ["klasyfikacja obrazow", "finanse", "medycyna", "prototypy end-to-end"],
      maturity: "praktyczny wzorzec prototypowania",
      specs: [
        "Warstwa kwantowa moze zastapic czesc cech, klasyfikator lub blok modelu.",
        "W praktyce laczy sie ja z PyTorch, TensorFlow, PennyLane lub Qiskit Runtime.",
        "Najczesciej testowana na malych lub zredukowanych zbiorach danych."
      ],
      strengths: [
        "Pozwala uzyc QPU tylko tam, gdzie moze wniesc wartosc.",
        "Zachowuje klasyczne narzedzia walidacji, preprocessing i deployment.",
        "Jest najbardziej realistyczna sciezka dla NISQ."
      ],
      weaknesses: [
        "Trudno wykazac, ze poprawa pochodzi z warstwy kwantowej, a nie z preprocessingu.",
        "Kolejki, shoty i komunikacja moga zabic przepustowosc.",
        "Strojeniem hiperparametrow latwo ukryc brak przewagi."
      ],
      critical: "Najbardziej uzyteczny wzorzec inzynierski dzisiaj, ale wymaga ablation studies: model bez warstwy kwantowej, model z losowym jadrem i model klasyczny o podobnej liczbie parametrow.",
      sources: ["Practical Guide PDF p. 466-516", "Algorithms paper printed p. 62-63", "Quantum Machine Learning PDF p. 104-116"]
    },
    {
      id: "qgan",
      label: "QGAN",
      short: "Kwantowy generator i/lub dyskryminator uczacy rozkladu danych.",
      family: ["QNN", "Generatywne"],
      learning: ["generatywne", "nienadzorowane"],
      era: ["NISQ", "FTQC"],
      computing: ["hybrydowy", "model bramkowy"],
      encoding: ["latent state", "amplitude encoding", "partial measurement"],
      training: ["minimax", "classical optimizer", "parameter shift"],
      advantage: ["modelowanie rozkladow", "probkowanie", "generowanie danych syntetycznych"],
      limitations: ["niestabilnosc treningu", "barren plateaus", "ocena jakosci probek", "koszt state preparation"],
      applications: ["generowanie obrazow", "finanse", "symulacje rozkladow", "chemia", "dane syntetyczne"],
      maturity: "demonstracje malej skali",
      specs: [
        "Generator przygotowuje rozklad pomiarow; dyskryminator moze byc klasyczny lub kwantowy.",
        "Modele patch/batch dziela obraz lub batch na rejestry, aby obejsc ograniczona liczbe kubitow.",
        "Metryki obejmuja straty generatora/dyskryminatora, KL divergence lub MMD."
      ],
      strengths: [
        "Bezposrednio wykorzystuje probabilistyczna nature pomiaru.",
        "Moze generowac dyskretne rozklady przy malej liczbie kubitow.",
        "Dobrze laczy sie z klasycznymi GAN i hybrydowym treningiem."
      ],
      weaknesses: [
        "Dziedziczy niestabilnosc klasycznych GAN i doklada szum kwantowy.",
        "Skalowanie do obrazow wysokiej rozdzielczosci pozostaje dalekie.",
        "Czesto trudno odroznic przewage modelu od efektu malego, sztucznego problemu."
      ],
      critical: "QGAN jest ciekawy tam, gdzie celem jest probkowanie rozkladu, ale na dzis ma status obiecujacego laboratorium, nie zamiennika klasycznych modeli generatywnych.",
      sources: ["Practical Guide PDF p. 518-553", "Quantum Machine Learning PDF p. 580-596 and p. 744", "Algorithms paper printed p. 62-63"]
    },
    {
      id: "qcbm",
      label: "QCBM",
      short: "Quantum Circuit Born Machine: obwod uczy jawnego rozkladu Bornowskiego.",
      family: ["QNN", "Generatywne"],
      learning: ["generatywne", "nienadzorowane"],
      era: ["NISQ"],
      computing: ["model bramkowy", "sampling"],
      encoding: ["basis samples", "latent circuit"],
      training: ["MMD", "KL divergence", "gradient-based"],
      advantage: ["naturalne probkowanie", "model dyskretnych rozkladow", "niskopoziomowa architektura"],
      limitations: ["barren plateaus", "tryb ograniczony do dyskretnych probek", "duzo shotow"],
      applications: ["modelowanie rozkladow", "syntetyczne dane finansowe", "obrazy binarne", "quantum state modeling"],
      maturity: "badawcza",
      specs: [
        "Prawdopodobienstwo probki wynika z reguly Borna po pomiarze obwodu.",
        "Nie wymaga dyskryminatora, w przeciwienstwie do QGAN.",
        "Czesto uzywa MMD, KL albo innych miar odleglosci rozkladow."
      ],
      strengths: [
        "Prostszy cel treningowy niz adversarial minimax.",
        "Dobra rama do badania ekspresyjnosci generatywnych obwodow.",
        "Moze modelowac korelacje przez splatanie."
      ],
      weaknesses: [
        "Trudny wybior miary straty i liczby probek.",
        "Skalowanie klasycznej oceny rozkladu moze byc kosztowne.",
        "Przewaga generatywna jest silnie zalezne od klasy porownawczej."
      ],
      critical: "QCBM ma czystsza matematyke niz QGAN, ale praktycznie nadal rozbija sie o trenowalnosc i liczbe pomiarow.",
      sources: ["Quantum Machine Learning PDF p. 744-748"]
    },
    {
      id: "qbm",
      label: "Quantum Boltzmann Machine",
      short: "Energetyczny model probabilistyczny z kwantowym Hamiltonianem.",
      family: ["Energetyczne", "Generatywne"],
      learning: ["generatywne", "nienadzorowane"],
      era: ["NISQ", "annealing"],
      computing: ["annealer", "model bramkowy", "sampling"],
      encoding: ["Hamiltonian", "Gibbs state", "Ising/QUBO"],
      training: ["maximum likelihood", "sampling", "contrastive divergence"],
      advantage: ["modelowanie rozkladow energetycznych", "wykorzystanie annealerow", "naturalne polaczenie z fizyka"],
      limitations: ["trudne probkowanie termiczne", "ograniczona topologia sprzetu", "szum i temperatura", "trudny gradient"],
      applications: ["generowanie rozkladow", "rekomendacje", "fizyka statystyczna", "modelowanie danych binarnych"],
      maturity: "niszowa i badawcza",
      specs: [
        "Rozklad jest zwiazany z energia Hamiltonianu, czesto w formie Isinga.",
        "Moze korzystac z annealerow lub obwodow do przygotowania stanow termicznych.",
        "Najwieksza trudnosc to wiarygodne probkowanie i estymacja gradientow."
      ],
      strengths: [
        "Dobrze pasuje do problemow energetycznych i binarnych.",
        "Moze korzystac ze sprzetu wyspecjalizowanego do Isinga.",
        "Jest blisko klasycznych RBM, wiec ma punkt odniesienia."
      ],
      weaknesses: [
        "Realne urzadzenia annealingowe sa ograniczone sprzetowo.",
        "Efekt temperatury i embeddingu utrudnia interpretacje wynikow.",
        "W porownaniu z klasycznymi generatywnymi modelami ma mala dojrzalosc narzedzi."
      ],
      critical: "QBM jest konceptualnie naturalny, lecz obecnie bardziej interesuje badaczy fizycznych modeli energii niz praktykow glownego nurtu ML.",
      sources: ["Algorithms paper printed p. 62", "Quantum Machine Learning PDF p. 744-748"]
    },
    {
      id: "qcnn",
      label: "QCNN / Quanvolution",
      short: "Kwantowe odpowiedniki konwolucji i ekstrakcji cech.",
      family: ["QNN", "Architektury glebokie"],
      learning: ["nadzorowane", "klasyfikacja"],
      era: ["NISQ"],
      computing: ["model bramkowy", "hybrydowy"],
      encoding: ["patch encoding", "angle encoding", "quantum data"],
      training: ["parameter shift", "hybrid backprop", "fixed random circuits"],
      advantage: ["lokalne cechy", "redukcja wymiaru", "splatanie jako filtr"],
      limitations: ["mala liczba kubitow", "koszt wielu patchy", "brak jasnej przewagi nad CNN"],
      applications: ["obrazy", "rozpoznawanie wzorcow", "klasyfikacja stanow kwantowych"],
      maturity: "badawcza z prototypami",
      specs: [
        "Dane moga byc dzielone na patche przetwarzane przez ten sam lub podobny obwod.",
        "Pooling bywa realizowany przez pomiar, odrzucanie kubitow lub redukcje rejestrow.",
        "Quanvolution czesto uzywa kwantowych filtrow jako feature extractor przed klasyczna siecia."
      ],
      strengths: [
        "Naturalnie ogranicza zasieg obwodow do lokalnych korelacji.",
        "Moze lepiej pasowac do danych przestrzennych niz pelny ansatz.",
        "Latwiejsze skalowanie eksperymentalne niz globalne obwody na wielu kubitach."
      ],
      weaknesses: [
        "Obrobka wielu patchy mnozy liczbe uruchomien obwodu.",
        "Klasyczne CNN sa bardzo mocnym baseline.",
        "Kwantowe filtry losowe moga nie uczyc nic istotnie nowego."
      ],
      critical: "QCNN ma sens jako architektura strukturalna QNN, ale musi byc oceniany przeciw CNN o porownywalnym budzecie i z ablacjami filtrow.",
      sources: ["Quantum Machine Learning PDF p. 104 and p. 564", "Practical Guide bibliography PDF p. 624"]
    },
    {
      id: "qae",
      label: "Quantum Autoencoder",
      short: "Model kompresji stanow kwantowych lub cech do mniejszego rejestru.",
      family: ["QNN", "Kompresja"],
      learning: ["nienadzorowane", "reprezentacja"],
      era: ["NISQ", "FTQC"],
      computing: ["model bramkowy", "hybrydowy"],
      encoding: ["quantum data", "amplitude encoding"],
      training: ["fidelity loss", "classical optimizer"],
      advantage: ["kompresja danych kwantowych", "redukcja wymiaru", "denoising"],
      limitations: ["wymaga danych kwantowych lub kosztownego encodingu", "pomiar fidelity", "skala demonstracyjna"],
      applications: ["kompresja stanow", "chemia kwantowa", "redukcja wymiaru", "denoising"],
      maturity: "specjalistyczna i badawcza",
      specs: [
        "Trenuje obwod, aby przeniesc informacyjna czesc stanu do mniejszego rejestru.",
        "W QML dla klasycznych danych sens zalezy od kosztu przygotowania stanow.",
        "Najbardziej naturalny dla danych juz kwantowych."
      ],
      strengths: [
        "Atakuje realny problem odczytu i reprezentacji danych kwantowych.",
        "Moze zmniejszac zasoby kolejnych algorytmow.",
        "Daje mechanizm uczenia latentnej reprezentacji."
      ],
      weaknesses: [
        "Dla klasycznych danych koszt wejscia moze dominowac.",
        "Ocena jakosci kompresji wymaga dodatkowych pomiarow.",
        "Nie jest ogolnym autoenkoderem dla duzych danych klasycznych."
      ],
      critical: "Quantum autoencoder jest najbardziej przekonujacy w sektorze Q-for-Q, czyli gdy dane sa juz kwantowe; dla klasycznego ML jest bardziej ostroznym narzedziem reprezentacji niz gotowym przyspieszeniem.",
      sources: ["Quantum Machine Learning PDF p. 744-748"]
    },
    {
      id: "q_transformer",
      label: "Quantum Transformer",
      short: "FTQC-propozycja kwantowej inferencji transformera przez block encoding.",
      family: ["Architektury glebokie", "FTQC"],
      learning: ["nadzorowane", "generatywne", "inferencja"],
      era: ["FTQC"],
      computing: ["block encoding", "model bramkowy", "QSVT"],
      encoding: ["block encoding", "amplitude encoding", "oracles"],
      training: ["zwykle klasycznie wytrenowany model", "kwantowa inferencja"],
      advantage: ["kwadratowe speedupy inferencji", "akceleracja self-attention", "duze modele sekwencyjne"],
      limitations: ["mocne zalozenia o oracle", "FTQC wymagane", "read-in/read-out", "brak NISQ praktycznosci"],
      applications: ["NLP", "modele foundation", "sekwencje", "wizja", "robotyka"],
      maturity: "teoretyczna / wczesna FTQC",
      specs: [
        "Zaklada dostep block-encoding do macierzy Wq, Wk, Wv, M1, M2 i sekwencji S.",
        "Koncentruje sie na inferencji pojedynczego kroku po klasycznym treningu modelu.",
        "Tutorial raportuje kwadratowe, nie wykladnicze, speedupy w analizowanym ustawieniu."
      ],
      strengths: [
        "Adresuje prawdziwy koszt wspolczesnej AI: inferencje duzych modeli.",
        "Jasno laczy QSVT/block encoding z architektura transformera.",
        "Daje bardziej realistyczna narracje niz ogolne haslo o wykladniczej przewadze."
      ],
      weaknesses: [
        "Wymaga fault-tolerant quantum computer i kosztownych oracles.",
        "Przygotowanie i odczyt klasycznych wektorow moga zniwelowac zysk.",
        "Nie jest obecnie implementowalny na typowym NISQ."
      ],
      critical: "To wazny kierunek strategiczny, ale nie narzedzie na teraz: najwiekszy ciezar krytyczny lezy w realistycznym koszcie block encoding i odczytu wyniku.",
      sources: ["Quantum Machine Learning PDF p. 189-205"]
    },
    {
      id: "hhl_qla",
      label: "HHL / Quantum Linear Algebra",
      short: "Rozwiazywanie ukladow liniowych i operacje macierzowe jako podprogramy QML.",
      family: ["Linear algebra", "FTQC"],
      learning: ["subroutine", "nadzorowane", "regresja"],
      era: ["FTQC"],
      computing: ["model bramkowy", "QPE", "block encoding"],
      encoding: ["amplitude encoding", "qRAM", "block encoding"],
      training: ["nie trening, podprogram", "phase estimation"],
      advantage: ["polylog scaling w idealnych zalozeniach", "akceleracja regresji i SVM", "podstawa qPCA/QSVM FTQC"],
      limitations: ["read-in/read-out", "warunek macierzy", "sparsity", "qRAM", "wynik jako stan kwantowy"],
      applications: ["least squares", "SVM", "PCA", "rekomendacje", "uklady liniowe"],
      maturity: "teoretycznie fundamentalna, praktycznie zalezy od FTQC",
      specs: [
        "HHL zwraca stan proporcjonalny do rozwiazania |x>, nie pelny klasyczny wektor.",
        "Warunki przewagi obejmuja rzadkosc, dobre uwarunkowanie i efektywne przygotowanie danych.",
        "Nowsze podejscia QSVT poprawiaja czesc skalowan i uogolniaja podprogramy liniowo-algebraiczne."
      ],
      strengths: [
        "Wyjasnia, skad historycznie wziely sie obietnice wykladniczych speedupow w QML.",
        "Jest fundamentem wielu algorytmow FTQC.",
        "Przy danych kwantowych lub czesciowym odczycie moze byc bardzo mocne."
      ],
      weaknesses: [
        "Dla klasycznych danych zalozenie szybkiego wejscia jest najczesciej zbyt silne.",
        "Pelne odczytanie wektora niszczy przewage.",
        "Wymaga duzo bardziej dojrzalego sprzetu niz NISQ."
      ],
      critical: "HHL jest matematycznie piekny, ale w QML trzeba go traktowac jak warunkowa obietnice: bez uczciwego rachunku read-in/read-out latwo sprzedac iluzje speedupu.",
      sources: ["Quantum Machine Learning PDF p. 92-100 and p. 248-296", "Practical Guide PDF p. 160 and p. 1040"]
    },
    {
      id: "qsvt",
      label: "QSVT",
      short: "Quantum Singular Value Transformation jako nowoczesny parasol dla algebry liniowej.",
      family: ["Linear algebra", "FTQC"],
      learning: ["subroutine"],
      era: ["FTQC"],
      computing: ["block encoding", "model bramkowy"],
      encoding: ["block encoding"],
      training: ["nie trening", "polynomial transformation"],
      advantage: ["lepsze skalowanie precyzji", "unifikacja algorytmow", "funkcje wartosci singularnych"],
      limitations: ["wymaga block encoding", "FTQC", "trudny dostep do danych", "nie jest samodzielnym modelem ML"],
      applications: ["linear systems", "PCA", "quantum transformer", "symulacje", "amplitude amplification"],
      maturity: "silna teoria, praktyka zalezy od FTQC",
      specs: [
        "Dziala na wartosciach singularnych macierzy osadzonej w unitary.",
        "Uogolnia wiele podprogramow, w tym rozwiazywanie ukladow liniowych i amplitude amplification.",
        "W QML jest infrastruktura, a nie klasyfikator lub generator."
      ],
      strengths: [
        "Porzadkuje fragmentaryczne algorytmy FTQC w jedna technike.",
        "Daje lepsze zaleznosci od precyzji niz starsze podejscia.",
        "Jest kluczowe dla ambitnych algorytmow, jak quantum transformer."
      ],
      weaknesses: [
        "Przesuwa problem do implementacji block encoding.",
        "Nie usuwa waskich gardel danych.",
        "Dla uzytkownika NISQ pozostaje glownie teoria."
      ],
      critical: "QSVT jest jednym z najwazniejszych narzedzi przyszlego QML, ale jako relacja w grafie powinno byc traktowane jako podprogram, nie jako model uczacy.",
      sources: ["Quantum Machine Learning PDF p. 96 and p. 248-296"]
    },
    {
      id: "qpca",
      label: "qPCA",
      short: "Estymacja glownych skladowych stanu/density matrix przez procedury kwantowe.",
      family: ["Linear algebra", "Redukcja wymiaru"],
      learning: ["nienadzorowane", "reprezentacja"],
      era: ["FTQC"],
      computing: ["QPE", "density matrix exponentiation", "block encoding"],
      encoding: ["density matrix", "qRAM", "amplitude encoding"],
      training: ["eigenvalue estimation", "nie trening"],
      advantage: ["potencjalny speedup dla PCA", "analiza danych kwantowych", "redukcja wymiaru"],
      limitations: ["dostep do density matrix", "qRAM", "readout", "idealizowane zalozenia"],
      applications: ["redukcja wymiaru", "analiza korelacji", "preprocessing", "quantum data analysis"],
      maturity: "teoretyczna / niszowa",
      specs: [
        "Cel to znalezienie dominujacych wartosci i wektorow wlasnych macierzy gestosci lub kowariancji.",
        "Czesto laczy sie z phase estimation albo nowsza algebra liniowa.",
        "Najbardziej naturalna dla danych kwantowych lub danych z juz przygotowanym stanem gestosci."
      ],
      strengths: [
        "Dobrze wpisuje sie w pipeline redukcji wymiaru przed QML.",
        "Moze miec sens, gdy wynik potrzebny jest jako stan, nie pelna klasyczna macierz.",
        "Jest klasycznym przykladem FTQC-QML."
      ],
      weaknesses: [
        "Wymaga bardzo mocnego modelu dostepu do danych.",
        "Odczyt wielu skladowych klasycznie moze byc kosztowny.",
        "Dla zwyklych tabel danych klasyczne randomized PCA jest trudnym baseline."
      ],
      critical: "qPCA brzmi jak wykladniczy skok, ale tylko w scenariuszach, w ktorych dane i wynik pozostaja kwantowe lub odczyt jest bardzo ograniczony.",
      sources: ["Algorithms paper printed p. 61-62", "Quantum Machine Learning PDF p. 96"]
    },
    {
      id: "q_clustering",
      label: "Quantum Clustering / q-k-means",
      short: "Kwantowe miary odleglosci lub przyspieszone obliczanie podobienstwa dla grupowania.",
      family: ["Clustering", "Metody odleglosciowe"],
      learning: ["nienadzorowane", "clustering"],
      era: ["NISQ", "FTQC"],
      computing: ["model bramkowy", "hybrydowy"],
      encoding: ["amplitude encoding", "feature map", "distance estimation"],
      training: ["iteracyjne centroidy", "quantum distance estimation"],
      advantage: ["potencjalne przyspieszenie odleglosci", "wysokowymiarowe podobienstwa"],
      limitations: ["state preparation", "odczyt centroidow", "iteracyjny koszt klasyczny", "slabe dowody przewagi"],
      applications: ["segmentacja", "analiza wzorcow", "bioinformatyka", "anomaly detection"],
      maturity: "wczesna / teoretyczna",
      specs: [
        "Najczesciej kwantowy jest podprogram liczacy odleglosc lub podobienstwo.",
        "Reszta algorytmu k-means moze pozostac klasyczna i iteracyjna.",
        "Zysk zalezy od tego, czy kodowanie danych i aktualizacja centroidow nie dominuja kosztu."
      ],
      strengths: [
        "Dobrze laczy sie z jadrami i estymacja overlapu.",
        "Moze byc uzyteczne dla danych, ktore naturalnie sa stanami kwantowymi.",
        "Pasuje do nienadzorowanego odkrywania struktur."
      ],
      weaknesses: [
        "Dla danych klasycznych koszt wejscia jest szczegolnie problematyczny.",
        "Klasyczne przyblizone metody nearest-neighbor sa bardzo szybkie.",
        "W dokumentach pojawia sie raczej jako kierunek niz dojrzaly algorytm."
      ],
      critical: "Quantum clustering nalezy traktowac ostroznie: wiele obietnic dotyczy podprogramu odleglosci, a nie pelnego kosztu uczenia.",
      sources: ["Algorithms paper printed p. 61-62", "Practical Guide PDF p. 1412"]
    },
    {
      id: "qrl",
      label: "Quantum Reinforcement Learning",
      short: "Kwantowe podprogramy dla agenta, polityki lub optymalizacji akcji.",
      family: ["RL", "Emerging"],
      learning: ["reinforcement", "sekwencyjne decyzje"],
      era: ["teoretyczne", "NISQ"],
      computing: ["model bramkowy", "hybrydowy"],
      encoding: ["quantum state value", "Grover-like search"],
      training: ["policy update", "amplitude amplification", "hybrid optimization"],
      advantage: ["przeszukiwanie akcji", "reprezentacja stanow", "potencjalne speedupy eksploracji"],
      limitations: ["bardzo wczesny etap", "brak standardowych benchmarkow", "integracja z klasycznym srodowiskiem", "pomiar i feedback"],
      applications: ["robotyka", "systemy adaptacyjne", "sterowanie", "gry"],
      maturity: "w duzej mierze teoretyczna",
      specs: [
        "Mozliwe role QPU: reprezentacja polityki, wartosci, srodowiska lub przyspieszenie wyboru akcji.",
        "Dokumenty podkreslaja, ze RL jest slabiej rozwiniety niz klasyfikacja i generowanie.",
        "Czesto przywolywane sa Grover-like mechanizmy optymalizacji wyboru."
      ],
      strengths: [
        "Dotyka problemow, gdzie eksploracja i optymalizacja sa kosztowne.",
        "Moze byc naturalna dla kwantowych srodowisk sterowania.",
        "Ma ciekawy potencjal w robotyce kwantowej i adaptive systems."
      ],
      weaknesses: [
        "Najmniej dojrzala galez w analizowanych materialach.",
        "Trudno zdefiniowac uczciwe porownanie z nowoczesnym deep RL.",
        "Pomiary moga zaburzac petle uczenia."
      ],
      critical: "QRL jest perspektywiczne, ale w tej chwili bardziej mapa badan niz gotowa rodzina praktycznych algorytmow.",
      sources: ["Algorithms paper printed p. 62-63", "Practical Guide PDF p. 1416"]
    },
    {
      id: "qaoa",
      label: "QAOA",
      short: "Wariacyjny algorytm optymalizacji dla Hamiltonianow kosztu, zwlaszcza QUBO/Ising.",
      family: ["Optymalizacja", "VQA"],
      learning: ["optymalizacja", "hybrydowe"],
      era: ["NISQ"],
      computing: ["model bramkowy", "hybrydowy"],
      encoding: ["QUBO", "Ising", "Hamiltonian"],
      training: ["classical optimizer", "energy estimation", "warstwy p"],
      advantage: ["naturalny dla kombinatoryki", "plytkie obwody", "pomost z annealingiem"],
      limitations: ["dobor p", "landscape optymalizacji", "szum", "brak gwarancji przewagi ogolnej"],
      applications: ["MaxCut", "QUBO", "logistyka", "portfolio", "scheduling", "feature selection"],
      maturity: "dojrzaly badawczo, eksperymentalny praktycznie",
      specs: [
        "Naprzemiennie stosuje unitarne ewolucje od Hamiltonianu kosztu i miksera.",
        "Parametry katow sa trenowane klasycznie na podstawie energii oczekiwanej.",
        "Jest obwodowym kuzynem idei adiabatic/annealing."
      ],
      strengths: [
        "Dobrze pasuje do obecnych urzadzen bramkowych.",
        "Latwo koduje wiele problemow przez QUBO/Ising.",
        "Moze byc uzywany jako komponent QML, np. do doboru cech lub optymalizacji hiperparametrow."
      ],
      weaknesses: [
        "Dla trudnych instancji moze wymagac duzego p.",
        "Klasyczna optymalizacja parametrow bywa kosztowna.",
        "Najlepsze heurystyki klasyczne sa bardzo mocnym punktem odniesienia."
      ],
      critical: "QAOA jest wazny w grafie QML jako silnik optymalizacji, ale nie powinien byc mylony z modelem uczacym, chyba ze pelni konkretna role w pipeline ML.",
      sources: ["Lecture Notes PDF p. 21-24", "Practical Guide PDF p. 206-243"]
    },
    {
      id: "annealing",
      label: "Quantum Annealing",
      short: "Ewolucja do stanu niskoenergetycznego Hamiltonianu Isinga/QUBO.",
      family: ["Optymalizacja", "Annealing"],
      learning: ["optymalizacja", "sampling"],
      era: ["NISQ-like", "annealing"],
      computing: ["adiabatyczny", "annealer"],
      encoding: ["Ising", "QUBO", "Hamiltonian"],
      training: ["annealing schedule", "sampling", "hybrid solvers"],
      advantage: ["wyspecjalizowany sprzet", "duza liczba kubitow fizycznych", "naturalne QUBO"],
      limitations: ["embedding topologii", "brak uniwersalnosci", "spectral gap", "brak gwarancji optimum", "szum termiczny"],
      applications: ["portfolio", "routing", "scheduling", "logistyka", "feature selection", "Boltzmann sampling"],
      maturity: "praktycznie dostepny, przewaga problemowo zalezne",
      specs: [
        "Problem musi zostac sprowadzony do Isinga lub QUBO.",
        "Urzadzenie zwraca probki; zwykle uruchamia sie wiele odczytow i wybiera najlepsze energie.",
        "Hardware embedding i coupling strengths sa czescia realnego kosztu."
      ],
      strengths: [
        "Najbardziej namacalna sciezka do duzych problemow binarnych na specjalnym sprzecie.",
        "Dobrze wspierany przez narzedzia Ocean i hybrydowe solvery.",
        "Naturalnie laczy optymalizacje i sampling."
      ],
      weaknesses: [
        "Nie jest uniwersalnym komputerem kwantowym.",
        "Mapowanie problemu i embedding moga zwiekszyc rozmiar dramatycznie.",
        "Czesto konkuruje z bardzo dobrymi heurystykami klasycznymi."
      ],
      critical: "Quantum annealing jest praktyczny, ale przewaga nie wynika z samej liczby kubitow; trzeba liczyc koszt formulacji, embeddingu i porownania z klasycznymi solverami.",
      sources: ["Lecture Notes PDF p. 25-30", "Practical Guide PDF p. 160-203"]
    },
    {
      id: "vqe",
      label: "VQE",
      short: "Wariacyjny eigensolver minimalizujacy wartosc oczekiwana Hamiltonianu.",
      family: ["Optymalizacja", "VQA", "Chemia"],
      learning: ["optymalizacja", "subroutine"],
      era: ["NISQ"],
      computing: ["model bramkowy", "hybrydowy"],
      encoding: ["Hamiltonian", "Pauli terms", "second quantization"],
      training: ["classical optimizer", "expectation estimation", "measurement grouping"],
      advantage: ["chemia NISQ", "plytkie ansatze", "ogolny schemat wariacyjny"],
      limitations: ["duzo pomiarow", "ansatz problem", "szum", "barren plateaus", "dokladnosc chemiczna"],
      applications: ["chemia kwantowa", "materialy", "molecular simulation", "feature Hamiltonians"],
      maturity: "bardzo dojrzaly badawczo",
      specs: [
        "Minimalizuje <psi(theta)|H|psi(theta)>.",
        "Hamiltonian rozklada sie na sumy obserwabli Pauli; koszt pomiarow jest krytyczny.",
        "Moze korzystac z error mitigation i grouping pomiarow."
      ],
      strengths: [
        "Jedna z najlepiej zbadanych rodzin VQA.",
        "Bezposrednio powiazana z chemia i materialami.",
        "Uczy praktycznych technik pomiaru, ansatzu i optymalizacji dla calego QML."
      ],
      weaknesses: [
        "Nie jest klasycznym algorytmem ML, lecz waznym podprogramem/analogiem treningu.",
        "Liczba pomiarow moze dominowac koszt.",
        "Znalezienie dobrego ansatzu jest nietrywialne."
      ],
      critical: "VQE warto pokazac w grafie, bo dzieli z QNN cala infrastrukture wariacyjna, ale jego glownym polem jest chemia i wartosci wlasne, nie klasyfikacja danych.",
      sources: ["Lecture Notes PDF p. 17-20", "Practical Guide PDF p. 280-335", "Quantum Machine Learning PDF p. 296"]
    },
    {
      id: "gas",
      label: "GAS / Grover Adaptive Search",
      short: "Adaptacyjne uzycie Grovera do szukania minimum funkcji kosztu.",
      family: ["Optymalizacja", "Grover"],
      learning: ["optymalizacja", "search"],
      era: ["FTQC", "NISQ eksperymentalnie mala skala"],
      computing: ["model bramkowy", "oracle"],
      encoding: ["oracle", "QUBO/HOBO", "QFT arithmetic"],
      training: ["amplitude amplification", "adaptive threshold"],
      advantage: ["kwadratowe przyspieszenie przeszukiwania", "minima dyskretne"],
      limitations: ["koszt konstrukcji oracle", "glebokie obwody", "fault tolerance dla skali", "tylko speedup kwadratowy"],
      applications: ["combinatorial optimization", "feature selection", "hyperparameter search", "QUBO/HOBO"],
      maturity: "edukacyjna / specjalistyczna",
      specs: [
        "Buduje oracle oznaczajacy rozwiazania lepsze niz aktualny prog.",
        "Wymaga kwantowej arytmetyki do obliczania funkcji kosztu.",
        "Adaptacyjnie obniza prog po znalezieniu lepszego kandydata."
      ],
      strengths: [
        "Daje jasna, teoretyczna przewage Grovera.",
        "Mozna go powiazac z optymalizacja dyskretna w QML.",
        "Uczy roli oracle i QFT w algorytmach kwantowych."
      ],
      weaknesses: [
        "Oracle moze byc drozszy niz samo przeszukiwanie.",
        "Duze instancje wymagaja glebokich, odpornych na bledy obwodow.",
        "W praktyce QAOA/annealing sa dzis czesciej testowane."
      ],
      critical: "GAS jest wazny jako wzorcowy kwantowy mechanizm search, ale w praktycznym QML trzeba najpierw policzyc koszt oracle.",
      sources: ["Practical Guide PDF p. 246-277"]
    }
  ],
  relationFacets: [
    { key: "curated", label: "relacje eksperckie" },
    { key: "family", label: "rodzina algorytmiczna" },
    { key: "learning", label: "typ uczenia" },
    { key: "era", label: "era/sprzet" },
    { key: "computing", label: "model obliczen" },
    { key: "encoding", label: "kodowanie danych" },
    { key: "training", label: "trening/optymalizacja" },
    { key: "advantage", label: "zrodlo potencjalnej przewagi" },
    { key: "limitations", label: "wspolne ograniczenia" },
    { key: "applications", label: "zastosowania" }
  ],
  curatedEdges: [
    { source: "qsvm", target: "quantum_kernels", label: "QSVM uzywa jadra kwantowego", weight: 5 },
    { source: "vqc", target: "qnn", label: "VQC jest wariantem QNN", weight: 5 },
    { source: "hybrid_qnn", target: "qnn", label: "warstwa kwantowa w modelu hybrydowym", weight: 4 },
    { source: "qgan", target: "qnn", label: "generator/dyskryminator jako QNN", weight: 4 },
    { source: "qcbm", target: "qnn", label: "generatywny obwod parametryczny", weight: 3 },
    { source: "qbm", target: "annealing", label: "probkowanie energetyczne/Ising", weight: 3 },
    { source: "qcnn", target: "qnn", label: "architektura QNN dla danych lokalnych", weight: 3 },
    { source: "qae", target: "qnn", label: "autoenkoder jako trainable circuit", weight: 3 },
    { source: "q_transformer", target: "qsvt", label: "block encoding i transformacje singularne", weight: 5 },
    { source: "hhl_qla", target: "qsvt", label: "nowoczesna algebra liniowa", weight: 4 },
    { source: "qpca", target: "hhl_qla", label: "FTQC linear algebra", weight: 4 },
    { source: "qsvm", target: "hhl_qla", label: "warianty FTQC QSVM", weight: 2 },
    { source: "q_clustering", target: "quantum_kernels", label: "odleglosc/overlap jako podobienstwo", weight: 3 },
    { source: "qaoa", target: "annealing", label: "obwodowa wersja intuicji adiabatycznej", weight: 5 },
    { source: "qaoa", target: "vqe", label: "wspolna rama wariacyjna", weight: 4 },
    { source: "gas", target: "qaoa", label: "alternatywne QUBO/search", weight: 2 },
    { source: "gas", target: "hhl_qla", label: "wymaga glebokich podprogramow/oracle", weight: 1 },
    { source: "vqe", target: "qnn", label: "shared ansatz, pomiary i optimizer", weight: 3 },
    { source: "qrl", target: "gas", label: "Grover-like action search", weight: 2 }
  ]
};

window.QML_DATA.algorithmDetails = {
  quantum_kernels: {
    theoryExtended: [
      "Metody jadrowe zakladaja, ze klasyczny wektor x jest mapowany przez obwod U_phi(x) do stanu |phi(x)>. Jadro jest wtedy iloczynem skalarnym stanow, najczesciej K(x, x') = |<phi(x)|phi(x')>|^2, estymowanym przez overlap, swap test albo odwracanie feature mapy.",
      "Teoretyczna przewaga moze pojawic sie tylko wtedy, gdy feature map tworzy podobienstwo trudne do efektywnej klasycznej symulacji i jednoczesnie dopasowane do struktury danych. Zbyt losowe mapy moga prowadzic do koncentracji jadra, a zbyt proste do braku przewagi nad RBF lub jadrem wielomianowym."
    ],
    pythonImplementation: String.raw`import pennylane as qml
import numpy as np

n_qubits = 4
dev = qml.device("default.qubit", wires=n_qubits)

def feature_map(x):
    for wire, value in enumerate(x[:n_qubits]):
        qml.RY(value, wires=wire)
    for wire in range(n_qubits - 1):
        qml.CNOT(wires=[wire, wire + 1])

@qml.qnode(dev)
def overlap_circuit(x1, x2):
    feature_map(x1)
    qml.adjoint(feature_map)(x2)
    return qml.probs(wires=range(n_qubits))

def quantum_kernel(x1, x2):
    # Probability of measuring |00...0> after U(x2)^dagger U(x1).
    return float(overlap_circuit(x1, x2)[0])

def kernel_matrix(X, Y=None):
    Y = X if Y is None else Y
    return np.array([[quantum_kernel(a, b) for b in Y] for a in X])`
  },
  qsvm: {
    theoryExtended: [
      "QSVM jest klasycznym SVM, w ktorym macierz jadra nie pochodzi z formuly RBF/polynomial, lecz z obwodu kwantowego. Problem optymalizacji marginesu pozostaje klasyczny, a QPU pelni role koprocesora obliczajacego podobienstwa.",
      "Najwiekszy koszt praktyczny wynika z koniecznosci estymacji O(n^2) elementow macierzy jadra oraz z propagacji szumu pomiarowego do solvera SVM. Dlatego uczciwy eksperyment powinien raportowac liczbe shotow, wariancje jadra, preprocessing i baselines klasyczne."
    ],
    pythonImplementation: String.raw`from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

# Wymaga funkcji kernel_matrix z przykladu Quantum Kernel Methods.
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

K_train = kernel_matrix(X_train_scaled)
model = SVC(kernel="precomputed", C=1.0)
model.fit(K_train, y_train)

K_test = kernel_matrix(X_test_scaled, X_train_scaled)
y_pred = model.predict(K_test)`
  },
  vqc: {
    theoryExtended: [
      "VQC modeluje funkcje decyzyjna przez parametryzowany obwod U(x, theta). Dane sa kodowane w bramkach zaleznch od x, parametry theta tworza ansatz, a wynik klasyfikacji powstaje z wartosci oczekiwanej obserwabli lub z rozkladu pomiarow.",
      "Uczenie jest hybrydowe: komputer klasyczny aktualizuje theta na podstawie strat estymowanych przez symulator albo QPU. Ograniczeniem jest jednoczesna walka z szumem, liczba pomiarow i zjawiskiem barren plateaus, szczegolnie dla glebokich, losowych ansatzy."
    ],
    pythonImplementation: String.raw`import pennylane as qml
from pennylane import numpy as np

n_qubits = 4
n_layers = 2
dev = qml.device("default.qubit", wires=n_qubits)

@qml.qnode(dev)
def classifier(x, weights):
    qml.AngleEmbedding(x[:n_qubits], wires=range(n_qubits))
    qml.BasicEntanglerLayers(weights, wires=range(n_qubits))
    return qml.expval(qml.PauliZ(0))

def predict(x, weights):
    return 1 if classifier(x, weights) >= 0 else -1

def loss(weights, X, y):
    preds = np.array([classifier(x, weights) for x in X])
    return np.mean((preds - y) ** 2)

weights = np.random.normal(0, 0.1, (n_layers, n_qubits), requires_grad=True)
opt = qml.AdamOptimizer(stepsize=0.05)
for _ in range(100):
    weights = opt.step(lambda w: loss(w, X_train, y_train), weights)`
  },
  qnn: {
    theoryExtended: [
      "QNN/PQC to ogolna klasa modeli, w ktorych obwod parametryczny jest odpowiednikiem warstwy neuronowej. Architektura obejmuje kodowanie danych, bloki splatajace, rotacje uczone oraz pomiar przeksztalcany na predykcje.",
      "Ekspresyjnosc QNN rosnie z liczba kubitow, splatania i warstw, ale trenowalnosc moze malec przez plaskie krajobrazy straty. Najwazniejsze decyzje projektowe to ansatz, inicjalizacja, obserwable, liczba shotow i sposob laczenia z klasycznym optymalizatorem."
    ],
    pythonImplementation: String.raw`import pennylane as qml
import numpy as np

n_qubits = 4
n_layers = 3
dev = qml.device("default.qubit", wires=n_qubits)

@qml.qnode(dev)
def qnn_forward(x, weights):
    qml.AngleEmbedding(x[:n_qubits], wires=range(n_qubits), rotation="Y")
    qml.StronglyEntanglingLayers(weights, wires=range(n_qubits))
    return [qml.expval(qml.PauliZ(i)) for i in range(n_qubits)]

weights = np.random.normal(0, 0.2, (n_layers, n_qubits, 3))
features = qnn_forward(np.array([0.1, 0.4, -0.2, 0.7]), weights)
print(features)`
  },
  hybrid_qnn: {
    theoryExtended: [
      "Hybrydowa QNN traktuje obwod kwantowy jako jedna z warstw klasycznej architektury. Klasyczna czesc moze redukowac wymiar, normalizowac dane albo wykonywac koncowa klasyfikacje, a warstwa kwantowa dostarcza nieliniowych cech lub malego modelu decyzyjnego.",
      "To najbardziej inzynierski wariant NISQ, ale wymaga ablation study: model bez QPU, model z losowa warstwa kwantowa, model z klasyczna warstwa o tej samej liczbie parametrow. Bez tego trudno stwierdzic, czy zysk pochodzi z kwantowosci."
    ],
    pythonImplementation: String.raw`import pennylane as qml
import torch

n_qubits = 4
dev = qml.device("default.qubit", wires=n_qubits)

@qml.qnode(dev, interface="torch")
def quantum_layer(inputs, weights):
    qml.AngleEmbedding(inputs, wires=range(n_qubits))
    qml.StronglyEntanglingLayers(weights, wires=range(n_qubits))
    return [qml.expval(qml.PauliZ(i)) for i in range(n_qubits)]

weight_shapes = {"weights": (2, n_qubits, 3)}
qlayer = qml.qnn.TorchLayer(quantum_layer, weight_shapes)

model = torch.nn.Sequential(
    torch.nn.Linear(16, n_qubits),
    torch.nn.Tanh(),
    qlayer,
    torch.nn.Linear(n_qubits, 2)
)`
  },
  qgan: {
    theoryExtended: [
      "QGAN przenosi logike GAN do ukladu, w ktorym generator, dyskryminator albo oba bloki moga byc kwantowe. Generator przygotowuje rozklad pomiarow zalezy od parametrow, a dyskryminator uczy sie odrozniac probki prawdziwe od wygenerowanych.",
      "Trening jest niestabilny z tych samych powodow co w klasycznym GAN, ale dodatkowo dochodza shot noise, ograniczona liczba kubitow i koszt probkowania. QGAN jest najrozsadniejszy dla malych rozkladow dyskretnych albo jako komponent hybrydowy."
    ],
    pythonImplementation: String.raw`import pennylane as qml
import torch

n_qubits = 3
dev = qml.device("default.qubit", wires=n_qubits)

@qml.qnode(dev, interface="torch")
def quantum_generator(z, weights):
    for i in range(n_qubits):
        qml.RY(z[i], wires=i)
    qml.StronglyEntanglingLayers(weights, wires=range(n_qubits))
    return qml.probs(wires=range(n_qubits))

discriminator = torch.nn.Sequential(
    torch.nn.Linear(2 ** n_qubits, 16),
    torch.nn.LeakyReLU(0.2),
    torch.nn.Linear(16, 1),
    torch.nn.Sigmoid()
)

gen_weights = torch.randn((2, n_qubits, 3), requires_grad=True)
opt_g = torch.optim.Adam([gen_weights], lr=0.03)
opt_d = torch.optim.Adam(discriminator.parameters(), lr=0.01)

def train_step(real_distribution):
    z = torch.rand(n_qubits)
    fake_distribution = quantum_generator(z, gen_weights).float()

    opt_d.zero_grad()
    d_real = discriminator(real_distribution.float())
    d_fake = discriminator(fake_distribution.detach())
    loss_d = -(torch.log(d_real + 1e-8) + torch.log(1 - d_fake + 1e-8))
    loss_d.backward()
    opt_d.step()

    opt_g.zero_grad()
    d_fake_for_g = discriminator(quantum_generator(z, gen_weights).float())
    loss_g = -torch.log(d_fake_for_g + 1e-8)
    loss_g.backward()
    opt_g.step()`
  },
  qcbm: {
    theoryExtended: [
      "QCBM uczy rozkladu bez dyskryminatora: prawdopodobienstwa probek wynikaja bezposrednio z reguly Borna po pomiarze obwodu. Model jest generatywny, bo po treningu wystarczy wielokrotnie mierzyc obwod, aby otrzymywac probki.",
      "Kluczowe jest dobranie funkcji straty porownujacej rozklady, np. MMD, KL divergence albo prostego MSE dla malych przestrzeni bitowych. W praktyce problemem jest liczba shotow oraz fakt, ze pelny rozklad ma rozmiar wykladniczy."
    ],
    pythonImplementation: String.raw`import pennylane as qml
from pennylane import numpy as np

n_qubits = 3
dev = qml.device("default.qubit", wires=n_qubits)

@qml.qnode(dev)
def born_machine(weights):
    qml.StronglyEntanglingLayers(weights, wires=range(n_qubits))
    return qml.probs(wires=range(n_qubits))

target = np.array([0.35, 0.10, 0.10, 0.05, 0.15, 0.10, 0.10, 0.05])

def loss(weights):
    probs = born_machine(weights)
    return np.mean((probs - target) ** 2)

weights = np.random.normal(0, 0.1, (2, n_qubits, 3), requires_grad=True)
opt = qml.AdamOptimizer(0.05)
for _ in range(150):
    weights = opt.step(loss, weights)

learned_distribution = born_machine(weights)`
  },
  qbm: {
    theoryExtended: [
      "Quantum Boltzmann Machine opisuje dane przez rozklad energetyczny wyznaczony Hamiltonianem. W klasycznym RBM energia jest funkcja binarnych zmiennych, a w QBM pojawiaja sie skladniki niekomutujace, ktore moga reprezentowac korelacje kwantowe.",
      "Pelny trening wymaga estymacji wartosci oczekiwanych w stanie termicznym, co jest trudne obliczeniowo i eksperymentalnie. Dlatego prototypy czesto korzystaja z annealerow, symulowanego annealingu albo malych dokladnych symulacji."
    ],
    pythonImplementation: String.raw`import itertools
import numpy as np
from scipy.optimize import minimize

def energy(bits, h, J):
    e = sum(h[i] * bits[i] for i in range(len(bits)))
    e += sum(J.get((i, j), 0.0) * bits[i] * bits[j] for i in range(len(bits)) for j in range(i + 1, len(bits)))
    return e

def boltzmann_distribution(h, J, beta=1.0):
    n = len(h)
    states = np.array(list(itertools.product([0, 1], repeat=n)))
    energies = np.array([energy(s, h, J) for s in states])
    weights = np.exp(-beta * energies)
    return states, weights / weights.sum()

def negative_log_likelihood(params, data):
    n = data.shape[1]
    h = params[:n]
    J = {(i, j): params[n + k] for k, (i, j) in enumerate((i, j) for i in range(n) for j in range(i + 1, n))}
    states, probs = boltzmann_distribution(h, J)
    lookup = {tuple(s): p for s, p in zip(states, probs)}
    return -np.mean([np.log(lookup[tuple(row)] + 1e-12) for row in data])

# Dla prawdziwego QBM probki z rozkladu zastapilby annealer lub obwod termiczny.
result = minimize(lambda p: negative_log_likelihood(p, binary_data), np.zeros(6))`
  },
  qcnn: {
    theoryExtended: [
      "QCNN wykorzystuje lokalnosc podobna do klasycznych CNN: male rejestry obrobiaja fragment danych, a pooling zmniejsza liczbe aktywnych kubitow lub cech. Quanvolution jest lzejszym wariantem, w ktorym obwody dzialaja jako filtry cech dla klasycznej sieci.",
      "Przewaga nad CNN nie wynika automatycznie z uzycia obwodu. Trzeba sprawdzic, czy kwantowe filtry ucza cech lepszych niz losowe cechy klasyczne, male MLP albo konwolucje o podobnym koszcie."
    ],
    pythonImplementation: String.raw`import pennylane as qml
import numpy as np

n_qubits = 4
dev = qml.device("default.qubit", wires=n_qubits)

@qml.qnode(dev)
def quantum_filter(patch, weights):
    qml.AngleEmbedding(patch.flatten(), wires=range(n_qubits))
    qml.BasicEntanglerLayers(weights, wires=range(n_qubits))
    return [qml.expval(qml.PauliZ(i)) for i in range(n_qubits)]

def quanvolution(image, weights, patch_size=2):
    h, w = image.shape
    features = []
    for row in range(0, h - patch_size + 1, patch_size):
        line = []
        for col in range(0, w - patch_size + 1, patch_size):
            patch = image[row:row + patch_size, col:col + patch_size]
            line.append(quantum_filter(patch, weights))
        features.append(line)
    return np.array(features)

weights = np.random.normal(0, 0.1, (2, n_qubits))
q_features = quanvolution(image_8x8, weights)`
  },
  qae: {
    theoryExtended: [
      "Quantum Autoencoder uczy unitarnej kompresji: informacja istotna ma zostac przeniesiona do mniejszego rejestru latentnego, a rejestr trash powinien konczyc w znanym stanie odniesienia. Strata mierzy zwykle fidelity albo prawdopodobienstwo poprawnego stanu trash.",
      "Najbardziej naturalnym zastosowaniem sa dane kwantowe, np. stany chemiczne albo symulacyjne. Dla danych klasycznych koszt amplitude encoding i pomiar fidelity moze przewyzszyc korzysc z kompresji."
    ],
    pythonImplementation: String.raw`import pennylane as qml
from pennylane import numpy as np

n_qubits = 4
trash_wire = 3
dev = qml.device("default.qubit", wires=n_qubits)

@qml.qnode(dev)
def autoencoder(features, weights):
    qml.AmplitudeEmbedding(features, wires=range(n_qubits), normalize=True)
    qml.StronglyEntanglingLayers(weights, wires=range(n_qubits))
    return qml.expval(qml.PauliZ(trash_wire))

def trash_probability_one(z_expectation):
    return (1 - z_expectation) / 2

def loss(weights, batch):
    trash_probs = [trash_probability_one(autoencoder(x, weights)) for x in batch]
    return np.mean(trash_probs)

weights = np.random.normal(0, 0.1, (2, n_qubits, 3), requires_grad=True)
opt = qml.AdamOptimizer(0.05)
for _ in range(100):
    weights = opt.step(lambda w: loss(w, training_states), weights)`
  },
  q_transformer: {
    theoryExtended: [
      "Quantum Transformer jest przede wszystkim propozycja FTQC: macierze projekcji i operacje attention sa reprezentowane przez block encoding, a podprogramy algebry kwantowej przyspieszaja czesc mnozen i normalizacji. Nie jest to obecnie typowy model NISQ do trenowania na laptopie.",
      "Najbardziej realistyczna interpretacja implementacyjna to rozdzielenie klasycznego transformera od przyszlego backendu kwantowego dla wybranych operacji liniowych. Krytyczny koszt lezy w przygotowaniu danych, oracle/block encoding i odczycie wyniku."
    ],
    pythonImplementation: String.raw`import numpy as np

def softmax(x, axis=-1):
    shifted = x - np.max(x, axis=axis, keepdims=True)
    exp = np.exp(shifted)
    return exp / exp.sum(axis=axis, keepdims=True)

def classical_attention(tokens, Wq, Wk, Wv):
    Q = tokens @ Wq
    K = tokens @ Wk
    V = tokens @ Wv
    scores = Q @ K.T / np.sqrt(K.shape[-1])
    return softmax(scores) @ V

class QuantumAttentionBackend:
    """Szkielet miejsca, w ktorym FTQC backend wykonalby block-encoded attention."""

    def block_encode(self, matrix):
        raise NotImplementedError("Wymaga fault-tolerant block encoding.")

    def attention(self, tokens, Wq, Wk, Wv):
        # Referencja klasyczna do testow poprawnosci przyszlego backendu.
        return classical_attention(tokens, Wq, Wk, Wv)`
  },
  hhl_qla: {
    theoryExtended: [
      "HHL rozwiazuje uklad A x = b, ale wynikiem jest stan kwantowy |x>, a nie wypisany wektor. Przewaga skaluje sie korzystnie tylko przy zalozeniach o rzadkosci, uwarunkowaniu macierzy, efektywnym przygotowaniu |b> i ograniczonym odczycie.",
      "W QML HHL dziala zwykle jako podprogram: regresja least squares, SVM, rekomendacje albo qPCA. Jesli koncowy pipeline wymaga pelnego klasycznego x, koszt tomografii moze usunac teoretyczny zysk."
    ],
    pythonImplementation: String.raw`import numpy as np

def hhl_reference_solution(A, b):
    """Klasyczna referencja: HHL zwracalby stan proporcjonalny do tego wektora."""
    x = np.linalg.solve(A, b)
    return x / np.linalg.norm(x)

def check_hhl_conditions(A):
    sparsity = max(np.count_nonzero(row) for row in A)
    condition = np.linalg.cond(A)
    hermitian = np.allclose(A, A.conj().T)
    return {"sparsity": sparsity, "condition_number": condition, "hermitian": hermitian}

A = np.array([[1.0, 0.25], [0.25, 1.0]])
b = np.array([1.0, 0.0])
state_x = hhl_reference_solution(A, b)
diagnostics = check_hhl_conditions(A)`
  },
  qsvt: {
    theoryExtended: [
      "QSVT przeksztalca wartosci singularne macierzy osadzonej w unitary block encoding. Zamiast projektowac osobny algorytm dla kazdej funkcji macierzy, buduje sie wielomian przyblizajacy pozadana transformacje singular values.",
      "W QML QSVT jest infrastruktura dla FTQC: moze implementowac odwrotnosc macierzy, progi spektralne, filtry PCA albo elementy attention. Samo QSVT nie rozwiazuje problemu dostepu do danych; wymaga dobrego block encoding."
    ],
    pythonImplementation: String.raw`import numpy as np

def qsvt_classical_emulator(A, polynomial):
    """Emuluje efekt QSVT na wartosciach singularnych macierzy A."""
    U, singular_values, Vh = np.linalg.svd(A, full_matrices=False)
    transformed = np.array([polynomial(s) for s in singular_values])
    return U @ np.diag(transformed) @ Vh

def ridge_inverse_polynomial(s, ridge=0.05):
    # Stabilna wersja funkcji 1/s uzywana jako filtr spektralny.
    return s / (s * s + ridge)

A = np.array([[0.8, 0.2], [0.1, 0.6]])
A_filtered = qsvt_classical_emulator(A, ridge_inverse_polynomial)`
  },
  qpca: {
    theoryExtended: [
      "qPCA ma estymowac dominujace wartosci i wektory wlasne macierzy gestosci lub kowariancji przy uzyciu procedur takich jak phase estimation albo density matrix exponentiation. Najsilniejszy sens ma wtedy, gdy dane sa juz stanami kwantowymi.",
      "Dla danych klasycznych krytyczne jest przygotowanie macierzy gestosci i odczyt skladowych. Jesli potrzebujemy duzej liczby klasycznych komponentow, klasyczne randomized PCA jest bardzo trudnym baseline do pobicia."
    ],
    pythonImplementation: String.raw`import numpy as np

def density_matrix_from_data(X):
    X = X - X.mean(axis=0, keepdims=True)
    covariance = X.T @ X
    return covariance / np.trace(covariance)

def qpca_reference(X, n_components=2):
    """Klasyczna referencja celu qPCA: dominujace pary wlasne density matrix."""
    rho = density_matrix_from_data(X)
    values, vectors = np.linalg.eigh(rho)
    order = np.argsort(values)[::-1]
    return values[order[:n_components]], vectors[:, order[:n_components]]

eigenvalues, eigenvectors = qpca_reference(X_train, n_components=2)`
  },
  q_clustering: {
    theoryExtended: [
      "Quantum clustering najczesciej kwantyzuje tylko miary podobienstwa: overlap, kernel albo dystans miedzy stanami zakodowanymi przez dane. Iteracyjny szkielet k-means, aktualizacja centroidow i walidacja moga pozostac klasyczne.",
      "Potencjalny zysk zalezy od tego, czy estymacja podobienstwa jest szybsza lub informacyjnie lepsza niz klasyczne odleglosci. Jesli kodowanie i odczyt centroidow sa drogie, caly pipeline moze byc wolniejszy mimo szybkiego podprogramu."
    ],
    pythonImplementation: String.raw`import numpy as np

# Wymaga funkcji quantum_kernel z przykladu Quantum Kernel Methods.
def quantum_distance(x, y):
    return np.sqrt(max(0.0, 2.0 - 2.0 * quantum_kernel(x, y)))

def quantum_kmeans(X, k=2, steps=10, seed=0):
    rng = np.random.default_rng(seed)
    centroids = X[rng.choice(len(X), size=k, replace=False)].copy()
    for _ in range(steps):
        distances = np.array([[quantum_distance(x, c) for c in centroids] for x in X])
        labels = distances.argmin(axis=1)
        for cluster in range(k):
            members = X[labels == cluster]
            if len(members):
                centroids[cluster] = members.mean(axis=0)
    return labels, centroids`
  },
  qrl: {
    theoryExtended: [
      "Quantum Reinforcement Learning moze uzyc QPU jako polityki, estymatora wartosci, modelu srodowiska albo akceleratora wyboru akcji. W wariancie NISQ najprostszy jest policy gradient, gdzie obwod zwraca rozklad prawdopodobienstwa akcji.",
      "Najtrudniejsza czesc nie lezy w pojedynczym obwodzie, lecz w petli interakcji: srodowisko jest zwykle klasyczne, feedback jest sekwencyjny, a pomiary wprowadzaja wariancje. Dlatego QRL potrzebuje bardzo ostroznych benchmarkow."
    ],
    pythonImplementation: String.raw`import pennylane as qml
import torch

n_state = 4
n_actions = 2
dev = qml.device("default.qubit", wires=n_state)

@qml.qnode(dev, interface="torch")
def quantum_policy(state, weights):
    qml.AngleEmbedding(state, wires=range(n_state))
    qml.BasicEntanglerLayers(weights, wires=range(n_state))
    return qml.probs(wires=[0])

weights = torch.randn((2, n_state), requires_grad=True)
optimizer = torch.optim.Adam([weights], lr=0.02)

def policy_gradient_step(states, actions, returns):
    optimizer.zero_grad()
    losses = []
    for s, a, g in zip(states, actions, returns):
        probs = quantum_policy(torch.tensor(s, dtype=torch.float32), weights)
        losses.append(-torch.log(probs[a] + 1e-8) * g)
    loss = torch.stack(losses).mean()
    loss.backward()
    optimizer.step()`
  },
  qaoa: {
    theoryExtended: [
      "QAOA przygotowuje stan przez naprzemienne dzialanie Hamiltonianu kosztu i Hamiltonianu miksera. Dla problemu QUBO/Ising parametry gamma i beta sa dobierane klasycznie tak, aby minimalizowac energie oczekiwana.",
      "Glebokosc p kontroluje kompromis miedzy jakoscia rozwiazan a podatnoscia na szum. Dla malych p QAOA jest atrakcyjny dla NISQ, ale dla trudnych instancji potrzebuje dobrego strojenia, warm-startow albo strategii layerwise."
    ],
    pythonImplementation: String.raw`import pennylane as qml
from pennylane import numpy as np

edges = [(0, 1), (1, 2), (2, 3), (3, 0)]
n_qubits = 4
p = 2
dev = qml.device("default.qubit", wires=n_qubits)

def cost_layer(gamma):
    for i, j in edges:
        qml.CNOT(wires=[i, j])
        qml.RZ(2 * gamma, wires=j)
        qml.CNOT(wires=[i, j])

def mixer_layer(beta):
    for wire in range(n_qubits):
        qml.RX(2 * beta, wires=wire)

@qml.qnode(dev)
def circuit(params):
    gammas, betas = params[0], params[1]
    for wire in range(n_qubits):
        qml.Hadamard(wires=wire)
    for layer in range(p):
        cost_layer(gammas[layer])
        mixer_layer(betas[layer])
    return [qml.expval(qml.PauliZ(i) @ qml.PauliZ(j)) for i, j in edges]

def objective(params):
    zz = circuit(params)
    maxcut_value = sum(0.5 * (1 - value) for value in zz)
    return -maxcut_value

params = np.random.uniform(0, np.pi, (2, p), requires_grad=True)
opt = qml.AdamOptimizer(0.05)
for _ in range(100):
    params = opt.step(objective, params)`
  },
  annealing: {
    theoryExtended: [
      "Quantum annealing koduje problem jako energie Isinga lub QUBO i pozwala ukladowi ewoluowac ku stanom niskoenergetycznym. Wynikiem nie jest pojedyncza gwarantowana odpowiedz, lecz zbior probek, ktore trzeba analizowac statystycznie.",
      "W praktyce koszt obejmuje formulacje QUBO, skalowanie wag, minor embedding na topologie sprzetu, liczbe odczytow i postprocessing. Dla oceny trzeba porownac caly pipeline z klasycznym simulated annealingiem, tabu search albo MILP."
    ],
    pythonImplementation: String.raw`import dimod

# Minimalny QUBO: minimalizuj -x0 - x1 + 2*x0*x1.
Q = {
    ("x0", "x0"): -1.0,
    ("x1", "x1"): -1.0,
    ("x0", "x1"): 2.0
}

bqm = dimod.BinaryQuadraticModel.from_qubo(Q)

try:
    from dwave.system import LeapHybridSampler
    sampler = LeapHybridSampler()  # wymaga konfiguracji D-Wave
except Exception:
    sampler = dimod.ExactSolver()  # lokalna referencja dla testu QUBO

sampleset = sampler.sample(bqm)
best = sampleset.first
print(best.sample, best.energy)`
  },
  vqe: {
    theoryExtended: [
      "VQE minimalizuje wartosc oczekiwana Hamiltonianu H dla stanu przygotowanego przez ansatz |psi(theta)>. Jest formalnie optymalizacja wariacyjna, a jej infrastruktura jest wspolna z QNN: pomiary, optymalizator, ansatz i error mitigation.",
      "Najwiekszym waskim gardlem jest liczba pomiarow skladnikow Pauliego oraz dobor ansatzu. W chemii kwantowej liczy sie nie tylko niska energia, ale dokladnosc chemiczna i stabilnosc wobec szumu."
    ],
    pythonImplementation: String.raw`import pennylane as qml
from pennylane import numpy as np

n_qubits = 2
dev = qml.device("default.qubit", wires=n_qubits)

H = qml.Hamiltonian(
    coeffs=[-1.05, 0.39, -0.39, 0.18],
    observables=[
        qml.Identity(0),
        qml.PauliZ(0),
        qml.PauliZ(1),
        qml.PauliX(0) @ qml.PauliX(1)
    ]
)

@qml.qnode(dev)
def energy(theta):
    qml.RY(theta[0], wires=0)
    qml.CNOT(wires=[0, 1])
    qml.RY(theta[1], wires=1)
    return qml.expval(H)

theta = np.array([0.1, 0.1], requires_grad=True)
opt = qml.AdamOptimizer(0.05)
for _ in range(100):
    theta = opt.step(energy, theta)

ground_energy = energy(theta)`
  },
  gas: {
    theoryExtended: [
      "Grover Adaptive Search laczy amplitude amplification z adaptacyjnie obnizanym progiem kosztu. Oracle oznacza rozwiazania lepsze niz aktualny prog, a po znalezieniu kandydata prog jest aktualizowany.",
      "Teoretycznie dostajemy kwadratowe przyspieszenie przeszukiwania, ale tylko wzgledem kosztu oracle. Dla realnych problemow QUBO/HOBO najtrudniejsze jest odwracalne obliczenie funkcji kosztu i porownania z progiem."
    ],
    pythonImplementation: String.raw`import random

def grover_oracle_placeholder(candidate, threshold, cost_fn):
    # W obwodzie kwantowym bylby to odwracalny oracle oznaczajacy dobre stany.
    return cost_fn(candidate) < threshold

def grover_sample_placeholder(candidates, threshold, cost_fn):
    marked = [x for x in candidates if grover_oracle_placeholder(x, threshold, cost_fn)]
    return random.choice(marked) if marked else None

def grover_adaptive_search(candidates, cost_fn, rounds=20):
    best = random.choice(candidates)
    threshold = cost_fn(best)
    for _ in range(rounds):
        candidate = grover_sample_placeholder(candidates, threshold, cost_fn)
        if candidate is not None:
            best = candidate
            threshold = cost_fn(best)
    return best, threshold

solutions = [(0, 0), (0, 1), (1, 0), (1, 1)]
best_solution, best_cost = grover_adaptive_search(solutions, lambda x: 3*x[0] + x[1])`
  }
};

window.QML_DATA.nodes.forEach(node => {
  Object.assign(node, window.QML_DATA.algorithmDetails[node.id] || {});
});

window.QML_DATA.derivationModules = {
  qsvm: "qml_model_modules/01_QSVM.md",
  vqc: "qml_model_modules/02_VQC.md",
  qnn: "qml_model_modules/03_QNN_PQC.md",
  hybrid_qnn: "qml_model_modules/04_HYBRID_QNN.md",
  qgan: "qml_model_modules/05_QGAN.md",
  qcbm: "qml_model_modules/06_QCBM.md",
  qbm: "qml_model_modules/07_QBM.md",
  qcnn: "qml_model_modules/08_QCNN.md",
  qae: "qml_model_modules/09_QUANTUM_AUTOENCODER.md",
  q_transformer: "qml_model_modules/10_QUANTUM_TRANSFORMER.md",
  hhl_qla: "qml_model_modules/11_HHL.md",
  qsvt: "qml_model_modules/12_QSVT.md",
  qpca: "qml_model_modules/13_QPCA.md",
  q_clustering: "qml_model_modules/14_QUANTUM_CLUSTERING.md",
  qrl: "qml_model_modules/15_QRL.md",
  qaoa: "qml_model_modules/16_QAOA.md",
  annealing: "qml_model_modules/17_QUANTUM_ANNEALING.md",
  vqe: "qml_model_modules/18_VQE.md",
  gas: "qml_model_modules/19_GAS.md"
};

window.QML_DATA.nodes.forEach(node => {
  if (window.QML_DATA.derivationModules[node.id]) {
    node.derivationModule = window.QML_DATA.derivationModules[node.id];
  }
});
