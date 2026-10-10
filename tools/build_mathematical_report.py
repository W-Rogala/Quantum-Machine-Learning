"""Reproduce the reviewed mathematical monograph, evidence and offline data.

No training or QPU submissions. Source snapshots exclude credentials and caches.
Run with --app (prepared Data app) and --node (bundled Node executable).
"""
from __future__ import annotations
import argparse, ast, base64, csv, hashlib, json, math, re, sqlite3, subprocess
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/mathematical_report'

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def read_csv(path):
    with (ROOT/path).open(encoding='utf-8-sig', newline='') as h:
        out=list(csv.DictReader(h))
    for row in out:
        for key,val in row.items():
            try: row[key]=float(val) if val not in ('','None') else None
            except (ValueError,TypeError): pass
    return out

def ref(id, title, author, year, url, doi='', verification='metadata/abstract', relevance=''):
    return dict(id=id,title=title,author=author,year=year,url=url,doi=doi,verification=verification,relevance=relevance,accessed='2026-10-05')

def references():
    records=[
      ref('watrous2018','The Theory of Quantum Information','John Watrous',2018,'https://cs.uwaterloo.ca/~watrous/TQI/','', 'chapters 2–3 inspected','Stany, kanały, pomiary i normy. Dowody lokalne są wyprowadzeniami własnymi.'),
      ref('rasmussen2006','Gaussian Processes for Machine Learning','Carl Edward Rasmussen and Christopher K. I. Williams',2006,'https://gaussianprocess.org/gpml/chapters/','','chapter 6 inspected','RKHS, regularizacja i relacje metod jądrowych.'),
      ref('cortes2012','Algorithms for Learning Kernels Based on Centered Alignment','Corinna Cortes and Mehryar Mohri and Afshin Rostamizadeh',2012,'https://www.jmlr.org/papers/v13/cortes12a.html','','metadata/abstract','Alignment i zakres jego uzasadnienia.'),
      ref('cortes2010','On the Impact of Kernel Approximation on Learning Accuracy','Corinna Cortes and Mehryar Mohri and Ameet Talwalkar',2010,'https://proceedings.mlr.press/v9/cortes10a.html','','metadata/abstract','Perturbacje kernela i stabilność predykcji.'),
      ref('cawley2010','On Over-fitting in Model Selection and Subsequent Selection Bias in Performance Evaluation','Gavin C. Cawley and Nicola L. C. Talbot',2010,'https://www.jmlr.org/papers/v11/cawley10a.html','','metadata/abstract','Selekcja modelu i bias oceny.'),
      ref('bartlett2002','Rademacher and Gaussian Complexities: Risk Bounds and Structural Results','Peter L. Bartlett and Shahar Mendelson',2002,'https://jmlr.org/papers/v3/bartlett02a.html','','paper introduction inspected','Kontekst złożoności Rademachera; lokalna granica wyprowadzona niezależnie.'),
      ref('eckart1936','The approximation of one matrix by another of lower rank','Carl Eckart and Gale Young',1936,'https://link.springer.com/article/10.1007/BF02288367','10.1007/BF02288367','publisher metadata','Aproksymacja niskiego rzędu. Dowód PCA w raporcie własny.'),
      ref('sim2019','Expressibility and entangling capability of parameterized quantum circuits for hybrid quantum-classical algorithms','Sukin Sim and Peter D. Johnson and Alan Aspuru-Guzik',2019,'https://arxiv.org/abs/1905.10876','10.1002/qute.201900070','metadata/abstract','Deskryptory ansatzu, nie gwarancja jakości.'),
      ref('ucioptdigits','Optical Recognition of Handwritten Digits','E. Alpaydin and C. Kaynak',1998,'https://archive.ics.uci.edu/dataset/80/optical+recognition+of+handwritten+digits','10.24432/C50P49','dataset description inspected','Podział 30/13 różnych autorów pisma.'),
      ref('hoeffding1963','Probability Inequalities for Sums of Bounded Random Variables','Wassily Hoeffding',1963,'https://www.jstor.org/stable/2282952','10.1080/01621459.1963.10500830','bibliographic metadata; publisher full text unavailable','Koncentracja średnich ograniczonych zmiennych.'),
      ref('wilson1927','Probable Inference, the Law of Succession, and Statistical Inference','Edwin B. Wilson',1927,'https://www.tandfonline.com/doi/abs/10.1080/01621459.1927.10502953','10.1080/01621459.1927.10502953','metadata; original scan located','Przedział Wilsona dla udziału.'),
      ref('efron1993','An Introduction to the Bootstrap','Bradley Efron and Robert J. Tibshirani',1993,'https://www.routledge.com/An-Introduction-to-the-Bootstrap/Efron-Tibshirani/p/book/9780412042317','','bibliographic metadata','Resampling; lokalny bootstrap blokowy ma jawny estymand.'),
      ref('holm1979','A Simple Sequentially Rejective Multiple Test Procedure','Sture Holm',1979,'https://www.jstor.org/stable/4615733','','metadata','Step-down FWER; dowód w raporcie własny.'),
      ref('jaeger2001','The echo state approach to analysing and training recurrent neural networks','Herbert Jaeger',2001,'https://www.ai.rug.nl/minds/uploads/EchoStatesTechRep.pdf','','technical report','ESP i klasyczny reservoir.'),
      ref('dambre2012','Information Processing Capacity of Dynamical Systems','Joni Dambre and David Verstraeten and Benjamin Schrauwen and Serge Massar',2012,'https://www.nature.com/articles/srep00514','10.1038/srep00514','metadata/abstract','Ortogonalne zadania i pojemność odczytu.'),
    ]
    arxiv={
      'havlicek2019':('1804.11326','Supervised learning with quantum-enhanced feature spaces','Vojtěch Havlíček et al.',2019),
      'huang2021':('2011.01938','Power of data in quantum machine learning','Hsin-Yuan Huang et al.',2021),
      'schuld2021':('2101.11020','Supervised quantum machine learning models are kernel methods','Maria Schuld',2021),
      'higham1988':None,
      'childs2021':('1912.08854','Theory of Trotter Error with Commutator Scaling','Andrew M. Childs and Yuan Su and Minh C. Tran and Nathan Wiebe and Shuchen Zhu',2021),
      'suzuki1990':None,
      'fujii2017':('1602.08159','Harnessing disordered-ensemble quantum dynamics for machine learning','Keisuke Fujii and Kohei Nakajima',2017),
      'schuld2019shift':('1811.11184','Evaluating analytic gradients on quantum hardware','Maria Schuld and Ville Bergholm and Christian Gogolin and Josh Izaac and Nathan Killoran',2019),
      'cong2019':('1810.03787','Quantum Convolutional Neural Networks','Iris Cong and Soonwon Choi and Mikhail D. Lukin',2019),
      'harrow2009':('0811.3171','Quantum algorithm for linear systems of equations','Aram W. Harrow and Avinatan Hassidim and Seth Lloyd',2009),
      'gilyen2019':('1806.01838','Quantum singular value transformation and beyond: exponential improvements for quantum matrix arithmetics','András Gilyén and Yuan Su and Guang Hao Low and Nathan Wiebe',2019),
      'lloyd2014':('1307.0401','Quantum principal component analysis','Seth Lloyd and Masoud Mohseni and Patrick Rebentrost',2014),
      'farhi2014':('1411.4028','A Quantum Approximate Optimization Algorithm','Edward Farhi and Jeffrey Goldstone and Sam Gutmann',2014),
      'peruzzo2014':('1304.3061','A variational eigenvalue solver on a photonic quantum processor','Alberto Peruzzo et al.',2014),
      'grover1996':('quant-ph/9605043','A fast quantum mechanical algorithm for database search','Lov K. Grover',1996),
      'lloyd2018':('1804.09139','Quantum generative adversarial learning','Seth Lloyd and Christian Weedbrook',2018),
      'romero2017':('1612.02806','Quantum autoencoders for efficient compression of quantum data','Jonathan Romero and Jonathan P. Olson and Alan Aspuru-Guzik',2017),
      'kerenidis2022':('2209.08167','Quantum Vision Transformers','El Amine Cherrat et al.',2022),
      'benedetti2019':('1906.07682','Parameterized quantum circuits as machine learning models','Marcello Benedetti and Erika Lloyd and Stefan Sack and Mattia Fiorentini',2019),
      'verdon2018':('1806.09729','A universal training algorithm for quantum deep learning','Guillaume Verdon et al.',2018),
      'dunjko2016':('1610.08251','Quantum-enhanced machine learning','Vedran Dunjko and Jacob M. Taylor and Hans J. Briegel',2016),
      'kadowaki1998':('cond-mat/9804280','Quantum annealing in the transverse Ising model','Tadashi Kadowaki and Hidetoshi Nishimori',1998),
      'killoran2019':('1804.03159','Strawberry Fields: A Software Platform for Photonic Quantum Computing','Nathan Killoran et al.',2019),
      'arrazola2021':('2103.02109','Quantum circuits with many photons on a programmable nanophotonic chip','Juan Miguel Arrazola et al.',2021),
      'hamilton2017':('1612.01199','Gaussian Boson Sampling','Craig S. Hamilton et al.',2017),
      'durr1996':('quant-ph/9607014','A quantum algorithm for finding the minimum','Christoph Dürr and Peter Høyer',1996),
      'transformer2024':('2402.16714','Quantum Transformer: Accelerating model inference via quantum linear algebra','Source authors verified in metadata',2024),
    }
    for k,v in arxiv.items():
        if v: records.append(ref(k,v[1],v[2],v[3],'https://arxiv.org/abs/'+v[0],'10.48550/arXiv.'+v[0], 'arXiv metadata/abstract','Kontekst metody; lokalne wyprowadzenia mają własne założenia.'))
    records.extend([
      ref('higham1988','Computing a nearest symmetric positive semidefinite matrix','Nicholas J. Higham',1988,'https://nhigham.com/wp-content/uploads/2023/10/high88d.pdf','10.1016/0024-3795(88)90223-6','paper inspected','Projekcja PSD w normie Frobeniusa.'),
      ref('suzuki1990','Fractal decomposition of exponential operators with applications to many-body theories and Monte Carlo simulations','Masuo Suzuki',1990,'https://doi.org/10.1016/0375-9601(90)90962-N','10.1016/0375-9601(90)90962-N','metadata','Wyższe rzędy formuł produktowych.'),
    ])
    indexed={r['id']:r for r in records}
    for path in sorted((DOC/'bibliography').glob('*_verified.json')):
        for r in json.loads(path.read_text(encoding='utf-8-sig')):
            if r.get('id'): indexed[r['id']]={**indexed.get(r['id'],{}),**r}
    # Verification results from targeted primary-source metadata requests.
    checked=DOC/'bibliography/metadata_checks.json'
    if checked.exists():
        for key,v in json.loads(checked.read_text(encoding='utf-8')).items():
            if key in indexed and v.get('url')==indexed[key]['url']:
                indexed[key]['metadataCheck']=v
                if v.get('title'): indexed[key]['title']=v['title']
                if v.get('authors'): indexed[key]['author']=' and '.join(v['authors'])
    return sorted(indexed.values(),key=lambda r:r['id'])

def glossary():
    # Short explanation | expanded meaning in this project | detailed chapter.
    raw='''QML|Quantum Machine Learning: uczenie maszynowe wykorzystujące stany, obwody lub algorytmy kwantowe.|Kwantowa część może przygotowywać cechy, estymować kernel albo być modelem wariacyjnym. O przewadze decyduje cały protokół, łącznie z danymi i odczytem.|chapter-00
QPU|Quantum Processing Unit: fizyczny procesor kwantowy.|Od wykonania QPU odróżniamy statevector, symulator kanałów i scenariusz efektywnego tłumienia. Zasoby sprzętowe obejmują routing, kalibrację, czas i shots.|chapter-07
NISQ|Noisy Intermediate-Scale Quantum: urządzenia o ograniczonym rozmiarze i istotnym szumie.|Nie mają pełnej korekcji błędów logicznych. Płytki obwód może ograniczać ekspozycję na błędy, ale sam rozmiar nie gwarantuje jakości.|chapter-07
FTQC|Fault-Tolerant Quantum Computing: obliczenia z korekcją błędów.|Twierdzenia o HHL/QSVT mogą zakładać kontrolowane koherentne oracle i głębokie obwody logiczne; nie są automatycznie procedurami NISQ.|chapter-06
CPTP|Całkowicie dodatnie odwzorowanie zachowujące ślad.|Kanał musi zachować dodatniość także po dołączeniu ancilla. Przedstawienie Krausa oraz warunek sumy K†K=I dają jawny dowód. Reset i pooling są kanałami.|chapter-01
PSD|Positive Semidefinite: dodatnio półokreślona macierz.|Hermitowska K jest PSD, gdy c†Kc≥0 dla każdego c. Gram cech ma tę własność; niezależny szum wpisów może ją zniszczyć.|chapter-02
RKHS|Reproducing Kernel Hilbert Space: przestrzeń Hilberta z jądrem reprodukującym.|Norma RKHS jest karą w standardowym kernel ridge. Jej konstrukcja wymaga dodatniego kernela, a nie tylko odwracalnej macierzy.|chapter-02
KRR|Kernel Ridge Regression: regresja grzbietowa w przestrzeni kernela.|Rozwiązanie ma postać α=(K+λI)⁻¹y przy zadeklarowanym skalowaniu straty. Raw indefinite K wymaga osobnej interpretacji.|chapter-02
RBF|Radial Basis Function: tu gaussowskie jądro exp(−γ‖x−z‖²).|Parametr γ zależy od jednostki cech. PSD można wyprowadzić przez nieskończony szereg tensorowych cech. Źródło cech może być klasyczne lub kwantowe.|chapter-02
PCA|Principal Component Analysis: analiza głównych składowych.|Wybiera kierunki maksymalnej wariancji i minimalnego liniowego błędu rekonstrukcji. Zachowana wariancja nie gwarantuje zachowania informacji o etykiecie.|chapter-07
SVD|Singular Value Decomposition: rozkład na wartości singularne.|A=UΣV† określa lewe i prawe wektory singularne. Ich przestrzenie trzeba odróżniać w QSVT, a nie utożsamiać z jednym eigenbasis.|chapter-06
QSVM|Quantum Support Vector Machine: rodzina klasyfikacji z kwantowym kernelem.|W projekcie nazwa historyczna obejmuje także LS-SVM i kernel ridge classification. Cele optymalizacji tych metod są różne.|chapter-02
SVM|Support Vector Machine: klasyfikator maksymalnego marginesu.|Standardowy cel używa hinge loss i regularizacji normy. Nie jest identyczny z kwadratową stratą LS-SVM lub ridge.|chapter-06
LS-SVM|Least-Squares SVM: wariant z kwadratową stratą i układem liniowym.|Binarna wersja ma bias oraz mnożniki związane z etykietami. Wieloklasowy ridge na one-hot nie jest automatycznie tą samą konstrukcją.|chapter-02
QRC|Quantum Reservoir Computing: ustalona dynamika kwantowa i uczony odczyt.|Dynamika aktualizuje stan zależny od historii wejścia. Koszt reset-injection, replay i obserwabli jest częścią definicji eksperymentu.|chapter-04
ESP|Echo State Property: asymptotyczne zapominanie inicjalizacji przy wspólnym wejściu.|Potrzebne są warunki dla dozwolonej rodziny wejść. Skończony washout oraz promień jednego zamrożonego kanału nie dowodzą jednostajnej ESP.|chapter-04
IPC|Information Processing Capacity: zdolność rekonstrukcji ortogonalnych celów.|Populacyjna teoria obejmuje odpowiednią rodzinę funkcji i readout. Suma kilku opóźnień linear/product nie stanowi pełnej IPC.|chapter-04b
ESN|Echo State Network: klasyczny rezerwuar z uczonym readoutem.|Porównanie wymaga jawnej dynamiki, liczby jednostek, leak, radius i budżetu strojenia. Nie ma obowiązku zrównywać liczby cech do kubitów.|chapter-04b
NRMSE|Normalized Root Mean Square Error: RMSE podzielone przez określoną skalę celu.|W tym projekcie skala to populacyjne odchylenie celu w segmencie oceny. Stały cel powoduje degenerację. Niższy wynik oznacza lepszą predykcję.|chapter-08
RMSE|Root Mean Square Error: pierwiastek średniego błędu kwadratowego.|Ma jednostkę celu, w przeciwieństwie do bezwymiarowego NRMSE. Jest wrażliwy na duże błędy.|chapter-08
MSE|Mean Square Error: średni kwadrat błędu.|Konwencja sumy albo średniej zmienia liczbową interpretację regularizacji λ o czynnik liczby próbek.|chapter-02
MAE|Mean Absolute Error: średnia wartości bezwzględnych błędu.|Ma jednostkę celu i inną wrażliwość na duże odchylenia niż RMSE. Nie zastępuje zarejestrowanej głównej miary po obejrzeniu wyniku.|chapter-08
BA|Balanced Accuracy: średni recall po klasach.|Przy nierównych klasach różni się od accuracy. Różnicę 0.01 raportujemy jako jeden punkt procentowy, a nie jeden procent względny.|chapter-08
CI|Confidence Interval: przedział ufności.|W raporcie rozróżniamy percentylowy bootstrap, przedział t i Wilson. Opisowy 95% CI nie jest automatycznie jednoczesną granicą po korekcie Holma.|chapter-08
SD|Standard Deviation: odchylenie standardowe obserwacji.|Nie jest błędem standardowym średniej. Dzielenie SD przez √N wymaga właściwej jednostki niezależności, której nie spełniają wszystkie wiersze CV.|chapter-08
SE|Standard Error: błąd standardowy estymatora.|Dla średniej iid to SD/√N. Współdzielone splity i zależne chwile wymagają modelu zależności lub agregacji blokowej.|chapter-08
HPO|Hyperparameter Optimization: dobór hiperparametrów.|Powinien używać train/validation wewnątrz development. Późniejszy wybór architektury po testowym wyniku odbiera testowi niezależność.|chapter-07
CV|Cross-validation albo Continuous Variables; znaczenie zależy od miejsca.|W benchmarkach oznacza walidację krzyżową. W części optycznej i spektralnej oznacza zmienne ciągłe q,p. Każdy rozdział wskazuje właściwy sens.|chapter-04b
FWER|Family-Wise Error Rate: prawdopodobieństwo choć jednego fałszywego odrzucenia.|Korekta Holma kontroluje tę wielkość bez wymagania niezależności p-values. Rodzina testów musi być określona przed analizą.|chapter-08
IUT|Intersection–Union Test: test tezy wymagającej spełnienia wszystkich warunków.|Dla H5 sukces jakości i kosztu wymaga odrzucenia obu składowych null. Złożone p-value jest maksimum, nie minimum.|chapter-08
GBS|Gaussian Boson Sampling: próbkowanie fotonów ze stanów gaussowskich.|Dla czystych nieprzesuniętych stanów amplitudy wzorców są wyrażane przez hafnian macierzy z powtórzonymi indeksami. Straty wymagają innego modelu stanu.|chapter-05
TMSV|Two-Mode Squeezed Vacuum: dwumodowa ściśnięta próżnia.|Stan ma parzystą całkowitą liczbę fotonów i skorelowane obsadzenia obu modów. Parametr tanh(r) kontroluje geometryczny ogon.|chapter-05
PNR|Photon-Number Resolving: detektor rozróżniający liczbę fotonów.|Threshold zwraca tylko zero/click. Strata przed progowaniem nie jest równoważna odrzucaniu już uzyskanych clicków.|chapter-05
QNN|Quantum Neural Network: szeroka rodzina modeli z parametryczną częścią kwantową.|Nazwa nie określa jednoznacznie ansatzu, kodowania ani straty. W projekcie głowica softmax i parametry obwodu mają osobne gradienty.|chapter-06
PQC|Parameterized Quantum Circuit: obwód z regulowanymi parametrami.|Reprezentacja, możliwość optymalizacji i generalizacja są trzema osobnymi pytaniami. Większa ekspresywność losowego ansatzu nie dowodzi lepszego wyniku.|chapter-06
VQC|Variational Quantum Classifier: klasyfikator z optymalizowanym obwodem.|Uczy parametry pod stratę klasyfikacji. Może korzystać z parameter shift przy spełnieniu warunków generatora.|chapter-06
QGAN|Quantum Generative Adversarial Network: kwantowy model uczony w grze generator–dyskryminator.|Trzeba odróżnić grę na rozkładach klasycznych od gry rozróżniania stanów kwantowych. Ograniczony dyskryminator nie certyfikuje równości stanów.|chapter-06
QCBM|Quantum Circuit Born Machine: generator rozkładu pomiaru obwodu.|Strata może być estymowana z próbek, np. MMD. Odczyt całego rozkładu z 2^n zdarzeń jest innym kosztem niż pojedyncze próbkowanie.|chapter-06
QBM|Quantum Boltzmann Machine: model oparty na stanie termicznym.|Niekomutujący Hamiltonian wymaga odpowiedniego gradientu macierzowej wykładniczej. Przygotowanie Gibbsa jest osobnym zadaniem obliczeniowym.|chapter-06
QCNN|Quantum Convolutional Neural Network: hierarchiczna architektura lokalnych operacji.|Pooling z pomiarem lub usunięciem kubitów jest kanałem, nie odwracalnym unitary. Quanvolution na klasycznych patchach to inna konstrukcja.|chapter-06
HHL|Algorytm Harrowa–Hassidima–Lloyda dla układów liniowych.|Wyjściem jest stan proporcjonalny rozwiązaniu, nie lista wszystkich współrzędnych. Koszt zależy od oracle, uwarunkowania, dokładności i odczytu.|chapter-06
QSVT|Quantum Singular Value Transformation: transformacja wartości singularnych zakodowanego bloku.|Wymaga warunków wielomianu, normy i parzystości. Nieparzysta i parzysta transformacja działają na odpowiednich różnych przestrzeniach.|chapter-06
QPCA|Quantum Principal Component Analysis: spektralna analiza stanu danych.|Normalizacja macierzy gęstości i model dostępu do jej kopii są częścią algorytmu. Nie jest to lokalne numpy PCA.|chapter-06
QRL|Quantum Reinforcement Learning: rodzina metod uczenia ze wzmocnieniem z elementem kwantowym.|Klasyczne środowisko z mierzoną polityką i koherentny oracle środowiska mają odmienne możliwości i koszty.|chapter-06
QAOA|Quantum Approximate Optimization Algorithm: wariacyjne naprzemienne bloki cost i mixer.|Kąty są optymalizowane pod cel. To inne zadanie niż dobieranie kroku Trottera do stałego Hamiltonianu, mimo wspólnej struktury bramek.|chapter-06
VQE|Variational Quantum Eigensolver: minimalizacja oczekiwanej energii.|Zasada wariacyjna daje E(θ)≥E₀. Deskryptory ansatzu bez Hamiltonianu celu nie stanowią eksperymentu VQE.|chapter-06
GAS|Grover Adaptive Search: adaptacyjne przeszukiwanie z progiem kosztu.|Wymaga odwracalnego oracle obliczającego funkcję i porównanie. Przyspieszenie liczby zapytań nie pomija kosztu arytmetyki oracle.|chapter-06
QUBO|Quadratic Unconstrained Binary Optimization: kwadratowy cel na bitach.|Podstawienie bitu przez (1−Z)/2 daje Hamiltonian diagonalny Isinga. Nie gwarantuje łatwego znalezienia minimum na QPU.|chapter-06
SCAR|Skew-Chiral Amplitude Router: nazwa lokalnej parametrycznej bramki wymiany.|Macierz odpowiada XY z chiralną fazą i ZZ. Raport wyprowadza unitarność i lokalną równoważność fazy, bez deklaracji nowości.|chapter-07
MLP|Multi-Layer Perceptron: klasyczna sieć warstwowa.|Równość liczby parametrów MLP i QNN nie oznacza równości pojemności ani kosztu optymalizacji. Porównanie wymaga jawnego protokołu.|chapter-07
SPSA|Simultaneous Perturbation Stochastic Approximation: estymacja gradientu dwoma losowymi perturbacjami.|Oszczędza liczbę ewaluacji na krok, kosztem wariancji i błędu aproksymacji. Nie jest analitycznym parameter shift.|chapter-07
KL|Kullback–Leibler divergence: względna entropia dwóch rozkładów.|Nie jest metryką symetryczną. Przy histogramach zależy od koszyków i smoothingu; małe KL do Haar nie dowodzi generalizacji.|chapter-07
MMD|Maximum Mean Discrepancy: odległość rozkładów w przestrzeni cech kernela.|MMD²=E k(X,X′)+E k(Y,Y′)−2E k(X,Y). Rozróżnianie wszystkich rozkładów wymaga właściwego, charakterystycznego kernela.|chapter-06
BCH|Baker–Campbell–Hausdorff: rozwinięcie logarytmu iloczynu wykładniczych.|Znaki komutatorów zależą od kolejności czynników. Lokalny logarytm ma ograniczoną dziedzinę i nie jest globalnym dowodem stabilności.|chapter-03
ISA|Instruction Set Architecture: natywna reprezentacja obwodu po kompilacji.|Głębia i liczba 2Q po routingu mogą być większe niż logiczne. Koszt logiczny nie jest czasem QPU.|chapter-07
SSE|Sum of Squared Errors: suma kwadratów błędów.|Jest licznikiem R² i sumową wersją celu ridge. Podział przez N daje MSE.|chapter-08
SST|Total Sum of Squares: suma kwadratów odchyleń celu od średniej.|Jest mianownikiem R². Gdy SST=0, wynik wymaga specjalnego oznaczenia degeneracji.|chapter-08
TP|True Positive: poprawnie przewidziana klasa dodatnia.|W wieloklasowych miarach liczymy one-vs-rest osobno dla każdej klasy. TP wchodzi do recall i F1.|chapter-08
FN|False Negative: pominięta rzeczywista klasa dodatnia.|Recall=TP/(TP+FN). Brak danej klasy w teście oznacza zerowy mianownik wymagający konwencji.|chapter-08
FP|False Positive: błędnie przewidziana klasa dodatnia.|Precision=TP/(TP+FP). W Macro F1 liczymy miary osobno dla klas, nie po uśrednieniu liczników.|chapter-08
POVM|Positive Operator-Valued Measure: ogólny pomiar kwantowy.|Efekty M_a są PSD i sumują się do I. Prawdopodobieństwo wynosi Tr(M_aρ); state update wymaga dodatkowego instrumentu.|chapter-01
Hamiltonian|Hermitowski operator określający energię i generator ewolucji.|W skończonym wymiarze U(t)=exp(−itH) jest unitarny. W nieskończonej przestrzeni trzeba uwzględnić samosprzężoność i domenę.|chapter-01
Trotter|Przybliżenie ewolucji przez iloczyn ewolucji części Hamiltonianu.|Błąd zależy od komutatorów, czasu i liczby kroków. Przy częściowych generatorach komutujących rozkład jest dokładny.|chapter-03
Strang|Symetryczna formuła produktowa drugiego rzędu.|A/2–B–A/2 usuwa wyraz lokalny drugiego stopnia. Globalny błąd przy stałym czasie ma rząd r⁻² z zależną od generatorów stałą.|chapter-03
komutator|[A,B]=AB−BA: miara nieprzemienności operatorów.|Jest źródłem błędu formuł produktowych. Komutatory zagnieżdżone określają kolejne rzędy rozwinięcia.|chapter-03
fidelity|Miara podobieństwa stanów; dla czystych kwadrat modułu overlapu.|Dla stanów mieszanych trzeba rozróżnić fidelity Uhlmanna i Tr(ρσ). Ten drugi jest PSD kernelem, ale nie tą samą miarą.|chapter-02
kernel|Funkcja podobieństwa interpretowana jako iloczyn cech.|Poprawny dodatni kernel daje PSD Gram dla każdego skończonego zbioru. Symetryczna tabela podobieństwa nie musi mieć tej własności.|chapter-02
Gram|Macierz iloczynów skalarnych między reprezentacjami próbek.|Jej dodatniość wynika z normy liniowej kombinacji cech. Widmo wpływa na stabilność ridge; shot noise może wytworzyć ujemne eigenvalues.|chapter-02
alignment|Znormalizowany iloczyn Frobeniusa centrowanych kerneli.|Wyznacza zgodność geometrii treningowej z etykietami. Near-best 95% nie jest argmax i nie gwarantuje jakości holdoutu.|chapter-02
ridge|Regresja z kwadratową karą normy współczynników.|λ stabilizuje układ i zmienia bias. Intercept może pozostać bez kary; standaryzacja i konwencja sumy/średniej muszą być spójne.|chapter-02
statevector|Jednostkowy wektor amplitud stanu czystego.|Dla n kubitów ma 2^n liczb zespolonych. Zależność fazy globalnej znika w macierzy gęstości. Stan mieszany wymaga innej reprezentacji.|chapter-01
macierz gęstości|PSD hermitowski operator śladu jeden opisujący stan.|Może reprezentować stan czysty lub mieszaninę. Jest konieczna po częściowym resecie i w modelach kanałów szumu.|chapter-01
ślad częściowy|Usunięcie podukładu z opisu przez sumę po jego bazie.|Daje zredukowany stan, zachowuje ślad i dodatniość, ale jest wiele-do-jednego. Reset QRC używa go do usunięcia starego wejścia.|chapter-04
ancilla|Pomocniczy rejestr kwantowy.|Umożliwia dilatację kanału, block encoding i oracle. Jego przygotowanie, uncompute i odczyt są częścią zasobów.|chapter-06
hafnian|Suma iloczynów wag wszystkich doskonałych skojarzeń par indeksów.|Dla czystego nieprzesuniętego GBS określa amplitudę wzorca fotonowego. Nie jest determinantem ani permanentem.|chapter-05
cutoff|Granica obcięcia nieskończonej przestrzeni Focka lub alfabetu wyników.|Zmienia relacje operatorowe na granicy. Trzeba kontrolować tail mass oraz zgodność oczekiwań wraz ze zwiększaniem cutoffu.|chapter-04b
overflow|Osobny koszyk na zdarzenia poza analizowanym oknem.|Zachowuje informację o masie ogona. Renormalizacja warunkowa usuwa tę masę i definiuje inny kernel.|chapter-05
threshold|Detekcja progowa: zero fotonów albo co najmniej jeden click.|Przy sprawności η i n fotonach click ma prawdopodobieństwo 1−(1−η)^n. Strata musi poprzedzać progowanie.|chapter-05
shots|Liczba powtórzeń przygotowania i pomiaru obwodu.|Wariancja średnich maleje zwykle jak 1/S. Shots, circuit-shots i 2Q-gate-shots mają różne denominatory.|chapter-01
washout|Początkowe kroki odrzucane przed dopasowaniem readoutu.|Jest ustawieniem procedury. Samo odrzucenie 200 kroków nie dowodzi zaniku wpływu dowolnej inicjalizacji.|chapter-04
readout|Uczona głowica odczytująca cechy dynamiki.|W QRC jest zwykle ridge na oczekiwaniach obserwabli. Pamięć dostępna dla readoutu nie jest całą informacją stanu.|chapter-04
promień spektralny|Maksymalny moduł wartości własnych macierzy.|Dla stałej skończonej mapy ρ(M)<1 daje asymptotyczny zanik. Zmienne wejścia wymagają kontroli iloczynów, a nie jednego radius.|chapter-04b
symplektyczny|Zachowujący formę kanoniczną J dla kwadratur q,p.|Dla jednego modu SᵀJS=J odpowiada detS=1. Nie gwarantuje stabilności: eigenvalues mogą być wzajemnie odwrotne i rzeczywiste.|chapter-04b
bootstrap|Resampling pozwalający przybliżyć rozkład estymatora.|Blokowy bootstrap zachowuje zależności wewnątrz bloku. Losowanie każdej chwili iid przy szeregu czasowym tworzy pseudoreplikację.|chapter-08
non-inferiority|Test, czy pogorszenie jest mniejsze od ustalonego marginesu.|Odróżniamy go od braku istotnej różnicy względem zera. H1 QRC używa marginesu 2% NRMSE.|chapter-08
mitygacja|Korekcja estymat błędów bez pełnej korekcji kwantowej.|Odwracanie macierzy readout może wzmacniać wariancję i dawać ujemne quasi-prawdopodobieństwa. Kalibracja jest osobnym kosztem.|chapter-07
parameter-shift|Dokładna reguła różniczkowania oczekiwania przez przesunięcia parametru.|Dla generatora z eigenvalues ±r pochodna jest r[f(θ+π/(4r))−f(θ−π/(4r))]. Współdzielone parametry wymagają chain rule.|chapter-06
block encoding|Zakodowanie macierzy jako określonego bloku większej unitary.|Normalizacja α i projektory wejściowe/wyjściowe należą do definicji. QSVT potrzebuje dostępu do tej unitary i jej odwrotności.|chapter-06
oracle|Zadeklarowany mechanizm dostępu do danych albo sprawdzania warunku.|W algorytmie kwantowym zwykle musi być koherentny i odwracalny. Koszt oracle nie znika w złożoności liczby zapytań.|chapter-06
postselekcja|Warunkowanie na zaakceptowanym wyniku pomiaru.|Zmienia normalizację rozkładu i efektywną liczbę próbek. Przy acceptance a potrzeba średnio S/a surowych prób na S zaakceptowanych.|chapter-05
Haar|Jednostajna miara niezmiennicza na unitary lub stanach.|Daje referencyjny rozkład overlapów w deskryptorach. Zbliżenie histogramu do Haar nie jest testem generalizacji.|chapter-07
softmax|Normalizacja dodatnich exp(logit) do prawdopodobieństw klas.|Odczyt amplitud kwantowych daje Born squared amplitudes, a nie automatycznie softmax tokenów. Te mapy muszą być odróżnione.|chapter-06
cross-entropy|Strata −log prawdopodobieństwa prawidłowej klasy.|Dla softmax gradient względem logits to p−one-hot(y). Estymacja cech QPU może wprowadzać wariancję do całego gradientu.|chapter-07
uwarunkowanie|Wrażliwość rozwiązania na perturbacje danych lub macierzy.|Dla układu liniowego wiąże się z ilorazem największej i najmniejszej singular value. Regularizacja stabilizuje, ale wprowadza bias.|chapter-02
regularizacja|Dodatkowa kara lub ograniczenie stabilizujące dopasowanie.|Jej interpretacja zależy od normy, skalowania straty i preprocessingu. λ nie porównuje się bezpośrednio między odmiennymi celami.|chapter-02
estymand|Ściśle określona wielkość, którą ma szacować analiza.|Średnia ilorazów, iloraz średnich i geometryczna średnia są odmiennymi estymandami. Split definiuje populację generalizacji.|chapter-08
pseudoreplikacja|Traktowanie zależnych pomiarów jako niezależnych replik.|Shots, foldy i chwile współdzielące dynamikę nie są automatycznie osobnymi eksperymentami. Analiza ma używać właściwej jednostki blokowej.|chapter-08
DOI|Digital Object Identifier: trwały identyfikator publikacji.|Metadane DOI są offline, lecz otwarcie wydawcy wymaga sieci. Sam DOI nie dowodzi, że źródło wspiera daną tezę.|bibliography
BibTeX|Format rekordów bibliograficznych używany w LaTeX.|Pakiet zawiera klucze identyczne z cytowaniami raportu. Ułatwia ponowne użycie bibliografii bez przepisywania metadanych.|bibliography
SQLite|Lokalna relacyjna baza danych w pojedynczym pliku.|Baza łączy źródła, cytowania, fragmenty kodu, słownik, hipotezy i relacje grafowe. Nie wymaga serwera.|bibliography
SHA-256|Kryptograficzny skrót treści pliku.|Hash określa wersję źródła i pozwala wykryć zmianę. Zgodność hashy potwierdza integralność, nie prawdziwość naukową wyniku.|code-browser
HTML|Format samodzielnej strony raportu.|Wyeksportowany plik zawiera skrypt, dane, wzory i fonty lokalnie. Nie wymaga localhost ani CDN.|chapter-10
JSON|Tekstowy format danych strukturalnych.|Używany do bibliografii i metadanych. Liczby, źródła oraz statusy pozostają oddzielone od prezentacji.|chapter-10
CSV|Tekstowa tabela z kolumnami rozdzielonymi separatorem.|Źródła wykresów mają zachowane nagłówki i oryginalne wiersze. Agregacja i jednostki są udokumentowane.|chapter-08
PDF|Przenośny format dokumentu o stałym układzie.|Publikacje mogą być dostępne jako PDF, ale pakiet raportu zawiera przede wszystkim metadane i uprawnione materiały lokalne.|bibliography
API|Interfejs programistyczny udostępniający funkcje usługi.|Integracja z dostawcą może pobierać dane albo zlecać zadania. W tej pracy nie wysłano nowych zadań QPU.|chapter-10'''
    records=[]
    for line in raw.splitlines():
        key,short,long,chapter=line.split('|')
        id=re.sub(r'[^a-z0-9]+','-',key.lower()).strip('-')
        records.append(dict(id=id,term=key,short=short,long=long,chapter=chapter,aliases=[key]))
    aliases={'Hamiltonian':['Hamiltonianu','Hamiltonianem','Hamiltonowskie','Hamiltonowski'], 'Trotter':['Trottera','Trotteryzacja','Trotteryzacji'], 'Gram':['Grama','Gramach'], 'kernel':['kernela','kernele','kerneli','kernelami','kerneli'], 'readout':['readoutu','readoutem'], 'komutator':['komutatory','komutatorów'], 'statevector':['statevectors','statevectorów','statevectoru'], 'ridge':['Ridge'], 'parameter-shift':['parameter shift'], 'block encoding':['block-encoding'], 'mitygacja':['mitygacji'], 'postselekcja':['postselekcji'], 'regularizacja':['regularizacji'], 'bootstrap':['bootstrapu'], 'ancilla':['ancilli'], 'cutoff':['cutoffem','cutoffu','cutoffów'], 'alignment':['alignmentu'], 'softmax':['softmaxem'], 'symplektyczny':['symplektyczne','symplektyczna','symplektyczną'], 'estymand':['estymandu'], 'hafnian':['hafnianu','hafnianowy'], 'uwarunkowanie':['uwarunkowania'], 'macierz gęstości':['macierzy gęstości','macierzami gęstości'], 'ślad częściowy':['śladu częściowego']}
    for r in records: r['aliases']+=aliases.get(r['term'],[])
    extra=DOC/'glossary_extra.json'
    if extra.exists():
        for r in json.loads(extra.read_text(encoding='utf-8')):
            if any(x['id']==r['id'] for x in records):raise ValueError('Duplicate glossary key '+r['id'])
            records.append(r)
    return records

def sources():
    rows=[]; index=[]
    folders=['hamiltonian_kernel','quantum_reservoir','photonic_kernel','experiments/legacy','tools','scripts','audits','tests']
    files=set()
    for folder in folders:
        files.update((ROOT/folder).glob('*.py'))
    files.update((ROOT/'qml_model_modules').glob('*.md'))
    files.update([ROOT/'qml_algorithms_data.js',ROOT/'qml_relation_metrics.md'])
    for path in sorted(files):
        if not path.exists():continue
        rel=path.relative_to(ROOT).as_posix(); txt=path.read_text(encoding='utf-8-sig')
        id=hashlib.sha256(rel.encode()).hexdigest()[:12]
        r=dict(id=id,path=rel,absolute=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),sha256_lf=hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),lines=txt.splitlines())
        rows.append(r)
        if path.suffix=='.py':
            try: tree=ast.parse(txt)
            except SyntaxError: continue
            for n in tree.body:
                if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                    index.append(dict(file=rel,sourceId=id,symbol=n.name,start=n.lineno,end=n.end_lineno,doc=(ast.get_docstring(n) or '')[:500],kind=type(n).__name__))
    return rows,index

def graph():
    nodes=[('data','Dane i preprocessing','chapter-07'),('state','Stan / kanał','chapter-01'),('dynamics','Hamiltonian i Trotter','chapter-03'),('measure','Pomiar Borna','chapter-01'),('feature','Cechy / histogram','chapter-02'),('gram','Gram i PSD','chapter-02'),('ridge','Ridge / RKHS','chapter-02'),('prediction','Predykcja i metryki','chapter-08'),('reservoir','Historia QRC','chapter-04'),('photon','GBS / detektor','chapter-05'),('qsvt','QSVT / algebra liniowa','chapter-06'),('variational','PQC / VQE / QAOA','chapter-06'),('statistics','Testy hipotez','chapter-08'),('resource','Koszt zasobów','chapter-03')]
    edges=[
      ('data','state','definiuje','z=T_train(x), ρ_z=E_z(ρ₀)','T dopasowana tylko na train; rozmiary i zakres kodowania zapisane.','chapter-09'),
      ('state','dynamics','dokładna transformacja','ρ↦UρU†, U=exp(−itH)','H hermitowski; ℏ=1; dla CV wymagane warunki operatorowe.','chapter-01'),
      ('dynamics','state','warunkowe oszacowanie','D(UρU†,ŨρŨ†)≤‖U−Ũ‖₂','Wspólny stan wejściowy i unitarne U,Ũ.','chapter-03'),
      ('state','measure','definiuje','p_a=Tr(M_aρ)','M_a≥0, ΣM_a=I; Born.','chapter-01'),
      ('measure','feature','estymacja','f_j=Tr(O_jρ), Var f̂_j=(1−f_j²)/S','Wspólne bitstringi zachowują kowariancję grup.','chapter-01'),
      ('feature','gram','dokładna transformacja','K_ij=⟨Φ_i,Φ_j⟩ ⇒ c†Kc=‖Σc_iΦ_i‖²≥0','Jedna wspólna przestrzeń cech i jedna transformacja train/cross.','chapter-02'),
      ('gram','ridge','dokładna transformacja','α=(K+λI)⁻¹y','PSD, λ>0; konwencja sumy albo średniej jawna.','chapter-02'),
      ('ridge','prediction','dokładna transformacja','ŷ(x)=k(x,X)α','Test nie użyty w preprocessingu ani selekcji.','chapter-02'),
      ('reservoir','state','definiuje','ρ_t=U[η(u_t)⊗Tr₀ρ_{t−1}]U†','Reset-injection jest CPTP, nie pełnym resetem pamięci.','chapter-04'),
      ('reservoir','feature','definiuje','f_t=(Tr O_jρ_t)_j','Zależy od całej historii; okno W zmienia tę mapę.','chapter-04b'),
      ('reservoir','ridge','dokładna transformacja','w=Xᵀ(XXᵀ+λI)⁻¹y','Primal–dual tylko przy tej samej normalizacji i intercept.','chapter-09'),
      ('photon','state','definiuje','B=UB₀Uᵀ','Czysty nieprzesunięty Gaussian state i singular values <1.','chapter-05'),
      ('photon','measure','kolejność fizyczna','P(click|n)=1−(1−η)^n','Loss przed threshold; kontrprzykład dla n=2.','chapter-05'),
      ('photon','feature','projekcja','p↦Lp, ‖L(p−q)‖₁≤‖p−q‖₁','L column-stochastic; postselekcja jest odrębną nieliniową mapą.','chapter-09'),
      ('qsvt','ridge','podprogram','A⁻¹b / polynomial singular transform','Output state, condition number, oracle i odczyt należą do kosztu.','chapter-06'),
      ('variational','dynamics','wspólny aparat','exp(−iβB)exp(−iγA)','Kąty QAOA są uczone; Trotter ma zadeklarowany harmonogram czasu.','chapter-09'),
      ('variational','prediction','definiuje','p=softmax(Wf_θ+b)','Gradient głowicy i kwantowych cech muszą być rozliczone osobno.','chapter-07'),
      ('prediction','statistics','hipoteza empiryczna','d_b=log(E_candidate/E_ref)','Niezależność bloków; progi i rodzina ustalone przed testem.','chapter-08'),
      ('resource','statistics','hipoteza empiryczna','H5: quality<1.02 ∧ cost<0.75','IUT: p=max(p_quality,p_cost); koszt wdrożenia ≠ koszt całego badania.','chapter-08'),
      ('dynamics','resource','definiuje','C₂Q=Σ_c S_c G₂Q,c','Rezerwacja, koszt faktyczny, reset, routing i QPU-time oddzielne.','chapter-03'),
      ('gram','statistics','nie implikuje','PSD ⇏ lepsza BA','Dopuszczalność modelu matematycznego nie dowodzi przewagi.','chapter-08'),
    ]
    return dict(nodes=[dict(id=i,label=l,chapter=c) for i,l,c in nodes],edges=[dict(id=f'math-edge-{i+1:02}',source=a,target=b,type=t,equation=e,conditions=c,chapter=ch) for i,(a,b,t,e,c,ch) in enumerate(edges)])

def chart_queries():
    q={}
    def add(id,path,rows,definition,caveat,classification='observed'):
        q[id]=dict(rows=rows,source=dict(kind='local-files',files=[path],executedAt='2026-10-05T12:00:00+02:00',classification=classification,description=definition,caveat=caveat,evidenceFlow=[dict(title='Źródło',detail=path),dict(title='Transformacja',detail=definition)],metricDefinitions=[dict(label=id,definition=definition,componentIds=[id])]))
    path='results/hamiltonian/publication_summary.csv'
    labels={('fidelity',200000):'Fidelity · 200 tys.',('fidelity',1000000):'Fidelity · 1 mln',('projected',200000):'Projected · 200 tys.',('projected',1000000):'Projected · 1 mln'}
    rows=read_csv(path)
    for r in rows:
        r['label']=labels.get((r['family'],r['circuit_shot_budget']),r['family']+' · '+r['evaluation_regime'])
        r['BA (%)']=100*r['test_balanced_accuracy_mean']
    add('hk-comparison',path,rows,'Średnie BA z oryginalnej tabeli; BA (%)=100×mean. SD i liczność zachowane.','SD wierszy nie jest CI. Tuning idealny i końcowe shots nie oznaczają całego kosztu HPO.')
    path='results/legacy/iterative_qsvm_summary.csv';rows=read_csv(path)
    for r in rows:
        r['BA (%)']=100*r['balanced_accuracy_mean'];r['variant']=r['hypothesis'].split('_')[0]
        r['dataset_short']='OptDigits' if r['dataset'].startswith('OptDigits') else ('WDBC' if r['dataset'].startswith('WDBC') else 'Wine')
    add('legacy-comparison',path,rows,'Zapisane średnie BA dla datasetu i wariantu, 10 splitów.','Powtarzane splity tej samej bazy; hipoteza iterowana eksploracyjnie.')
    add('legacy-dimension',path,rows,'Stosunek mean_state_dimension do bazowego 6q zapisany w CSV.','Metryka pamięci statevectora, nie czasu QPU.')
    path='analysis_output/qrc_spectral_h1_h2/qubit_summary.csv';rows=read_csv(path)
    for r in rows:r['label']=str(r['case'])+' · '+str(r['hypothesis'])
    add('qrc-spectral',path,rows,'Geometryczny iloraz błędów i CI95 z analizy n=8 bloków; wartości oryginalne.','Badanie stresowe, odrębne od planu20. CI opisowe; progi1.02 i0.98 są różne.')
    path='results/qrc/noise_paired_contrasts.csv';rows=read_csv(path)
    add('noise-ratio',path,[r for r in rows if r['kind']=='ratio'],'Sparowane ilorazy NRMSE i oryginalne CI przy matched cost.','n=8 bloków; osobna rodzina testów szumu.')
    add('noise-difference',path,[r for r in rows if r['kind']=='difference'],'Sparowane różnice pamięci i oryginalne CI.','Inna jednostka niż iloraz NRMSE; osobny wykres.')
    path='analysis_output/qrc_h3_memory/h3_contrasts.csv';rows=read_csv(path)
    add('memory-contrast',path,rows,'Zmiana T w trzech reżimach z oryginalnymi CI95.','Zmiana T nie dowodzi wzrostu product memory ani mediacji NRMSE.')
    path='analysis_output/qrc_h3_memory/profile_summaries.csv';raw=read_csv(path);group=defaultdict(list)
    for r in raw:
        if r['phase']=='core' and r['view']=='local_XZ_ZZ' and r['method'] in ('fixed_exact','AB_r1','BAB_r2'):
            group[(r['regime'],r['method'])].append(r)
    rows=[]
    for (reg,method),rs in sorted(group.items()):
        rows.append(dict(regime=reg,method=method,label=reg+' · '+method,linear=sum(r['linear10'] for r in rs)/len(rs)/10,product=sum(r['product10'] for r in rs)/len(rs)/10,n=len(rs)))
    add('memory-components',path,rows,'Średnie linear10/10 i product10/10 po blokach dla local_XZ_ZZ i wybranych metod.','Dwa składniki wspólnego T; nie pełna IPC. Wybór widoku jawny.')
    rows=[dict(label='QPU · 12 epok SPSA',accuracy=14/35,n=35,regime='physical QPU'),dict(label='Ideal QNN · 160 epok',accuracy=.857,n=35,regime='archival ideal'),dict(label='MLP · klasyczny',accuracy=34/35,n=35,regime='classical')]
    for r in rows:r['Accuracy (%)']=100*r['accuracy']
    add('scar-comparison','analysis_output/scar_wine_ibm_qpu_report.md',rows,'QPU=14/35 z confusion matrix; MLP=34/35; ideal0.857 jako zaokrąglona liczba z archiwalnego raportu.','Różne procedury treningu: wykres nie izoluje wpływu szumu.')
    rows=[]
    for i in range(21):
        eta=i/20;rows.append(dict(eta=eta,correct=1-(1-eta)**2,incorrect=eta))
    add('detector-theory','photonic_kernel/core.py',rows,'Wzór dla n=2 fotonów: correct=1−(1−η)²; incorrect=η.','Przykład algebraiczny, nie pomiar urządzenia.','mathematical-illustration')
    rows=[]
    for r in [1,2,4,8,16,32]:rows.append(dict(r=r,lie_bound=1/r,strang_bound=1/r**2))
    add('trotter-theory','docs/mathematical_report/chapters/03_hamiltonian.md',rows,'Znormalizowane granice przy stałych normowych równych1: Lie1/r, Strang1/r².','Krzywe ilustracyjne, nie wyniki jakości; stałe rzeczywiste zależą od Hamiltonianu.','mathematical-illustration')
    return q

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--app',type=Path);ap.add_argument('--node');ap.add_argument('--complete',action='store_true');args=ap.parse_args()
    DOC.mkdir(exist_ok=True,parents=True)
    refs=references();gloss=glossary();src,astindex=sources();byfile={r['path']:r for r in src}
    # Include explicitly referenced local evidence files, with a bounded audit.
    chapter_paths=sorted((DOC/'chapters').glob('*.md'))
    texts=[p.read_text(encoding='utf-8-sig') for p in chapter_paths]
    for txt in texts:
        for p in re.findall(r'\[\[file:([^\]]+)\]\]',txt):
            if p in byfile:continue
            target=ROOT/p
            if target.exists() and target.stat().st_size<400000:
                r=dict(id=hashlib.sha256(p.encode()).hexdigest()[:12],path=p,absolute=str(target),sha256=hashlib.sha256(target.read_bytes()).hexdigest(),sha256_lf=hashlib.sha256(target.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),lines=target.read_text(encoding='utf-8-sig').splitlines())
                src.append(r);byfile[p]=r
    dump(DOC/'source_index.json',astindex)
    dump(DOC/'source_manifest.json',[{k:v for k,v in r.items() if k!='lines'} for r in src])
    ids={r['id'] for r in refs};citations=[];code_refs=[];unresolved=[];equations=[]
    aliases={alias.lower():r['id'] for r in gloss for alias in r['aliases']}
    termpat=re.compile(r'(?<![\w])('+ '|'.join(re.escape(a) for a in sorted(aliases,key=len,reverse=True))+r')(?![\w])',re.I)
    def decorate(text):
        def cite(m):
            keys=re.findall(r'@([\w-]+)',m.group(0))
            out=[]
            for k in keys:
                if k not in ids:unresolved.append('citation:'+k)
                citations.append(dict(key=k,chapter=current_id))
                out.append('['+k+'](#ref-'+k+')')
            return ', '.join(out)
        text=re.sub(r'\[(?:@[^\]]+)\]',cite,text)
        def code(m):
            path,start,end=m.group(1),int(m.group(2)),int(m.group(3) or m.group(2));r=byfile.get(path)
            if not r or not (1<=start<=end<=len(r['lines'])):
                unresolved.append('code:'+m.group(0));return m.group(0)
            code_refs.append(dict(chapter=current_id,path=path,sourceId=r['id'],start=start,end=end))
            return '[Kod: '+path+' · '+str(start)+'–'+str(end)+'](#code-'+r['id']+'-'+str(start)+'-'+str(end)+')'
        text=re.sub(r'\[\[code:([^#]+)#L(\d+)(?:-L(\d+))?\]\]',code,text)
        def local(m):
            path=m.group(1);r=byfile.get(path)
            if r:return '['+path+'](#code-'+r['id']+'-1-1)'
            unresolved.append('file:'+path);return path
        text=re.sub(r'\[\[file:([^\]]+)\]\]',local,text)
        # Every inline formula gets its own fully rendered equation and a local link.
        def inline(m):
            latex=m.group(1);eqid=f'eq-{current_id}-{len(equations)+1:04}'
            equations.append(dict(id=eqid,latex=latex,display=False,chapter=current_id))
            # A compact Unicode display avoids raw TeX in prose; exact formula opens locally.
            simple=re.sub(r'\\(?:mathcal|mathbb|mathrm|operatorname|text)\{([^{}]+)\}',r'\1',latex)
            syms={'\\lambda':'λ','\\alpha':'α','\\beta':'β','\\gamma':'γ','\\theta':'θ','\\rho':'ρ','\\sigma':'σ','\\psi':'ψ','\\phi':'φ','\\epsilon':'ε','\\varepsilon':'ε','\\eta':'η','\\delta':'δ','\\Delta':'Δ','\\omega':'ω','\\pi':'π','\\infty':'∞','\\leq':'≤','\\geq':'≥','\\le':'≤','\\ge':'≥','\\in':'∈','\\times':'×','\\otimes':'⊗','\\dagger':'†','\\sum':'Σ','\\sqrt':'√','\\approx':'≈','\\neq':'≠','\\to':'→','\\mapsto':'↦','\\cdot':'·','\\langle':'⟨','\\rangle':'⟩','\\Vert':'‖','\\|':'‖','\\quad':' ','\\qquad':' ','\\forall':'∀','\\exists':'∃','\\succeq':'≥','\\mathbb':'','\\left':'','\\right':''}
            for a,b in sorted(syms.items(),key=lambda kv:len(kv[0]),reverse=True):simple=simple.replace(a,b)
            simple=re.sub(r'\\[A-Za-z]+', '',simple).replace('{','').replace('}','')
            simple=simple.replace('[','(').replace(']',')').replace('\n',' ').replace('\\','')
            return '['+(simple[:120] if simple.strip() else 'wzór')+'](#'+eqid+')'
        text=re.sub(r'(?<!\$)\$([^$\n]+)\$(?!\$)|\\\((.*?)\\\)',lambda m:inline(type('M',(),{'group':lambda self,n:m.group(1) or m.group(2)})()),text)
        # Avoid changing code spans, URLs and already authored links.
        parts=re.split(r'(`[^`]*`|\[[^\]]*\]\([^)]*\))',text)
        for i,p in enumerate(parts):
            if i%2==0:parts[i]=termpat.sub(lambda m:'['+m.group(0)+'](#term-'+aliases[m.group(0).lower()]+')',p)
        return ''.join(parts)
    chapters=[]
    fence=re.compile(r'```math\s*\n(.*?)\n```|\$\$\s*(.*?)\s*\$\$|\\\[\s*(.*?)\s*\\\]',re.S)
    for path,txt in zip(chapter_paths,texts):
        prefix=path.name.split('_')[0];current_id='chapter-'+prefix; title=txt.splitlines()[0].lstrip('# ')
        blocks=[];last=0;blocknum=0
        for m in fence.finditer(txt):
            body=txt[last:m.start()].strip()
            if body:blocks.extend(split_tables(decorate(body),current_id,blocknum));blocknum+=1
            latex=next(g for g in m.groups() if g is not None).strip()
            eqid=f'eq-{current_id}-{len(equations)+1:04}'
            equations.append(dict(id=eqid,latex=latex,display=True,chapter=current_id))
            blocks.append(dict(kind='math',id=eqid,latex=latex));last=m.end()
        if txt[last:].strip():blocks.extend(split_tables(decorate(txt[last:].strip()),current_id,blocknum))
        in_place={p['id'] for b in blocks if b['kind']=='rich-math' for p in b['parts'] if p['kind']=='math'}
        inline_eq=[e for e in equations if e['chapter']==current_id and not e['display'] and e['id'] not in in_place]
        if inline_eq: blocks.append(dict(kind='inline-bank',id='bank-'+current_id,equations=[e['id'] for e in inline_eq]))
        chapters.append(dict(id=current_id,title=title,queryId=current_id,blocks=blocks,search=txt))
    # Fully typeset inline math is available in the formula bank and on hover.
    # Render server-side: no online JS, CSS or font loading in the final page.
    dump(DOC/'equations.json',equations)
    if args.node:
        renderer=ROOT/'tools/render_report_math.cjs'
        subprocess.run([args.node,str(renderer),str(DOC/'equations.json'),str(DOC/'equations_rendered.json')],check=True)
        rendered=json.loads((DOC/'equations_rendered.json').read_text(encoding='utf-8'))
    else:rendered=[]
    q=chart_queries()
    for c in chapters:q[c['queryId']]=dict(rows=[dict(path=str((DOC/'chapters').relative_to(ROOT))+'/'+next(p.name for p in chapter_paths if p.name.startswith(c['id'].replace('chapter-','')+'_')),statement='Wyprowadzenia i powiązania z kodem')],source=dict(kind='local-files',files=['docs/mathematical_report/chapters/'+next(p.name for p in chapter_paths if p.name.startswith(c['id'].replace('chapter-','')+'_'))],description='Wyprowadzenia własne, cytowania oraz aktualny kod; status twierdzeń jawny.'))
    q['bibliography']=dict(rows=refs,source=dict(kind='literature',files=['docs/mathematical_report/bibliography/references.json'],description='Sprawdzone metadane i wskazany poziom weryfikacji.'))
    q['code-index']=dict(rows=astindex,source=dict(kind='local-files',files=[r['path'] for r in src],description='AST top-level functions/classes plus source hashes; snapshot revised 9 Oct 2026.'))
    q['code-snapshot']=dict(rows=src,source=dict(kind='local-files',files=[r['path'] for r in src],description='Pełna treść plików z numerami linii i hashami; dostępna offline.'))
    q['math-equations']=dict(rows=rendered,source=dict(kind='derived',files=['docs/mathematical_report/equations_rendered.json'],description='Lokalnie renderowane wzory KaTeX z rozdziałów raportu.'))
    g=graph();q['math-relations']=dict(rows=g['edges'],source=dict(kind='derived',files=['docs/mathematical_report/chapters/09_transformations.md'],description='Typowane relacje matematyczne z warunkami i odnośnikami.'))
    archive=json.loads((ROOT/'docs/report/graph_relations.json').read_text(encoding='utf-8'))
    for name,layer in archive['graphs'].items():
        q['archive-'+name]=dict(rows=layer['edges'],source=dict(kind='local-files',files=['docs/report/graph_relations.json'],description='Zachowana mapa projektu z 23 września; typy relacji i granice są w opisie krawędzi.'))
    hypotheses=json.loads((DOC/'hypotheses.json').read_text(encoding='utf-8'))
    q['hypotheses']=dict(rows=hypotheses,source=dict(kind='derived',files=['docs/mathematical_report/hypotheses.json'],description='Rejestr wybranych centralnych twierdzeń i hipotez; kompletne argumenty są w wskazanych rozdziałach.'))
    snapshot=dict(surface='report',title='QML — monografia matematyczna, dowody i analiza implementacji',generatedAt='2026-10-05T12:00:00+02:00',revisedAt='2026-10-09',status='reviewed',buildStatus='complete' if args.complete else 'creating',filters=[],report=dict(summary='Dowody, status hipotez, wyprowadzenia, kod i porównania; daty eksperymentów właściwe dla źródeł.'),queries=q)
    old_path=(args.app/'src/data.json') if args.app else None
    if old_path and old_path.exists():
        old=json.loads(old_path.read_text(encoding='utf-8'));snapshot['id']=old['id']
    dump(DOC/'snapshot.json',snapshot)
    dump(DOC/'bibliography/references.json',refs)
    dump(DOC/'glossary.json',gloss);dump(DOC/'graph.json',g)
    dump(DOC/'citations.json',citations);dump(DOC/'code_references.json',code_refs)
    (DOC/'QML_MATHEMATICAL_REPORT.md').write_text('\n\n'.join(texts),encoding='utf-8')
    (DOC/'bibliography/references.bib').write_text('\n\n'.join('@'+('book' if r['id'] in ('watrous2018','rasmussen2006','efron1993') else 'misc')+'{'+r['id']+',\n'+',\n'.join('  '+k+' = {'+str(r[k]).replace('&','\\&')+'}' for k in ['title','author','year','url','doi'] if r.get(k))+'\n}' for r in refs),encoding='utf-8')
    csl=[dict(id=r['id'],type='book' if r['id'] in ('watrous2018','rasmussen2006','efron1993') else 'article-journal',title=r['title'],author=[{'literal':x} for x in r['author'].split(' and ')],issued={'date-parts':[[r['year']]]},URL=r['url'],DOI=r.get('doi','')) for r in refs]
    dump(DOC/'bibliography/references.csl.json',csl)
    db=DOC/'bibliography/report.sqlite'
    with sqlite3.connect(db) as con:
        con.executescript('DROP TABLE IF EXISTS sources; DROP TABLE IF EXISTS citations; DROP TABLE IF EXISTS code_refs; DROP TABLE IF EXISTS glossary; DROP TABLE IF EXISTS graph_edges; CREATE TABLE sources(id TEXT PRIMARY KEY,title TEXT,author TEXT,year INTEGER,url TEXT,doi TEXT,verification TEXT,metadata_json TEXT); CREATE TABLE citations(source_id TEXT,chapter_id TEXT); CREATE TABLE code_refs(chapter TEXT,path TEXT,start INTEGER,end INTEGER,sha256 TEXT); CREATE TABLE glossary(id TEXT PRIMARY KEY,term TEXT,short TEXT,explanation TEXT,chapter TEXT); CREATE TABLE graph_edges(id TEXT PRIMARY KEY,source TEXT,target TEXT,type TEXT,equation TEXT,conditions TEXT,chapter TEXT);')
        con.executemany('INSERT INTO sources VALUES(?,?,?,?,?,?,?,?)',[(r['id'],r['title'],r['author'],r['year'],r['url'],r.get('doi',''),r.get('verification',''),json.dumps(r,ensure_ascii=False)) for r in refs])
        con.executemany('INSERT INTO citations VALUES(?,?)',[(r['key'],r['chapter']) for r in citations])
        con.executemany('INSERT INTO code_refs VALUES(?,?,?,?,?)',[(r['chapter'],r['path'],r['start'],r['end'],byfile[r['path']]['sha256']) for r in code_refs])
        con.executemany('INSERT INTO glossary VALUES(?,?,?,?,?)',[(r['id'],r['term'],r['short'],r['long'],r['chapter']) for r in gloss])
        con.executemany('INSERT INTO graph_edges VALUES(?,?,?,?,?,?,?)',[(r['id'],r['source'],r['target'],r['type'],r['equation'],r['conditions'],r['chapter']) for r in g['edges']])
        con.executescript('DROP TABLE IF EXISTS hypotheses; CREATE TABLE hypotheses(id TEXT PRIMARY KEY,type TEXT,claim TEXT,status TEXT,assumptions TEXT,evidence TEXT,repair TEXT,chapter TEXT);')
        con.executemany('INSERT INTO hypotheses VALUES(?,?,?,?,?,?,?,?)',[(r['id'],r['type'],r['claim'],r['status'],r['assumptions'],r['evidence'],r['repair'],r['chapter']) for r in hypotheses])
    checks=dict(chapters=len(chapters),words=sum(len(t.split()) for t in texts),equations=len(equations),citations=len(citations),sources=len(refs),code_references=len(code_refs),code_files=len(src),symbols=len(astindex),glossary=len(gloss),hypotheses=len(hypotheses),graph_edges=len(g['edges']),unresolved=sorted(set(unresolved)))
    dump(DOC/'build_checks.json',checks)
    if args.app:
        target=args.app/'src/content/report';target.mkdir(exist_ok=True,parents=True)
        for name,val in [('chapters',chapters),('equations',rendered),('glossary',gloss),('sources',src),('symbol_index',astindex),('references',refs),('math_graph',g),('archive_graph',archive),('checks',checks)]:dump(target/(name+'.json'),val)
        dump(args.app/'src/data.json',snapshot)
    print(json.dumps(checks,ensure_ascii=False))
    if unresolved and args.complete:raise SystemExit('Unresolved references remain')

def split_tables(text,chapter,n):
    out=[]; lines=text.splitlines();body=[];i=0
    while i<len(lines):
        if '|' in lines[i] and i+1<len(lines) and re.match(r'^\s*\|?\s*:?-{3,}',lines[i+1]):
            if body:out.extend(split_prose('\n'.join(body),chapter,n,len(out)));body=[]
            headers=[x.strip() for x in lines[i].strip().strip('|').split('|')];i+=2;rows=[]
            while i<len(lines) and '|' in lines[i]:
                cells=[x.strip() for x in lines[i].strip().strip('|').split('|')]
                if len(cells)==len(headers):rows.append(cells)
                i+=1
            out.append(dict(kind='table',id=f'{chapter}-table{n}-{len(out)}',headers=headers,rows=rows));continue
        body.append(lines[i]);i+=1
    if body:out.extend(split_prose('\n'.join(body),chapter,n,len(out)))
    return out

def split_prose(text,chapter,n,offset):
    blocks=[]
    for i,para in enumerate(re.split(r'\n\s*\n',text)):
        id=f'{chapter}-n{n}-{offset}-{i}'
        pat=re.compile(r'\[([^\]]*)\]\(#(eq-[^)]+)\)')
        if pat.search(para) and not re.search(r'^\s*(?:#{1,6}|[-*>]|\d+\.)\s',para,re.M):
            parts=[];last=0
            for m in pat.finditer(para):
                if m.start()>last:parts.append(dict(kind='text',text=para[last:m.start()]))
                parts.append(dict(kind='math',id=m.group(2)));last=m.end()
            if para[last:]:parts.append(dict(kind='text',text=para[last:]))
            blocks.append(dict(kind='rich-math',id=id,parts=parts))
        else:blocks.append(dict(kind='narrative',id=id,text=para))
    return blocks

if __name__=='__main__':main()
