# Fotonika oraz przegląd 19 modułów teorii

## Fotonika: poprawny rdzeń i zakres

`photonic_kernel/core.py` opisuje cztery pary TMSV, identyczne interferometry
na dwóch połówkach ośmiomodowego układu, B=W B0 Wᵀ oraz prawdopodobieństwa
PNR przez hafnian. Mały enumerator jest kontrolą matematyczną; jego koszt
wykładniczy nie jest algorytmem przewagi obliczeniowej. Kernel Hellingera jest
iloczynem pierwiastków prawdopodobieństw, a moment RBF jest klasycznym PSD
kernelem na cechach wyprowadzonych z próbek. PSD nie dowodzi informatywności.

`experiment.py` używa wspólnego strumienia próbek do porównania estymatorów.
Wybór jednej konfiguracji optycznej przez wspólną walidację jest uczciwym testem
ustalonego pomiaru, ale nie odpowiada pytaniu o najlepszy niezależnie dostrojony
kernel każdej rodziny. Oba estymandy należy rozróżnić.

`robustness.py` rozdziela cutoff, straty, detektory i event/orbit features.
Jawny overflow zmniejsza bias postselekcji. Zgrubny bin nie zawiera jednak
rozkładu wysokich obsadzeń: nie da się z samej masy overflow dokładnie wyznaczyć
powrotu zdarzeń poniżej cutoff po stratach. Do ilościowego sweepu potrzebne są
surowe PNR z odpowiednio kontrolowanym ogonem albo bezpośrednia symulacja strat.

Historyczny audyt X8 ma 10/10 pozytywnych kontroli, w tym hafnian i topologię.
To audyt lokalnego pilota 18 obwodów/12000 shots, nie wykonania fotonicznego QPU.
`xanadu_x8.py` oddziela walidację kompilatora i endpoint sprzętowy. Brak zgodnego
Strawberry Fields w bieżącym Pythonie pozostaje jawnym ograniczeniem wykonania.

## P-01 — sprawność detektora po threshold (P1)

`photonic_kernel/strawberry_fields_robustness.py:70–98` wybiera natywne
`MeasureThreshold`, a następnie dla jego bitów wywołuje detektor PNR ze
sprawnością η. Operacja progowania gubi liczbę fotonów. Dla wejścia |2> i η=1/2
kod po idealnym kliknięciu zachowuje je z prawdopodobieństwem 0.5, podczas gdy
fizyczny model niezależnych strat daje 1−(1−η)²=0.75.

To błąd fizyczny ścieżki SF z η<1, a nie błąd `apply_detector_model` na surowym PNR.
Sama definicja threshold to pomiar zero/nonzero, zgodnie z
[dokumentacją Strawberry Fields](https://strawberryfields.readthedocs.io/en/latest/code/api/strawberryfields.ops.MeasureThreshold.html).

Poprawka A: w programie przed threshold użyć transmisyjności T·η, po pomiarze
nie stosować ponownie thinning. Dla dark counts dodać niezależną zmienną
kliknięcia o prawdopodobieństwie 1−exp(−μ). Poprawka B: zawsze pobierać PNR,
potem wykonać thinning i na końcu threshold; sprawdzić wsparcie backendu i cutoff.
Regresje: stany n=0,1,2,5, granice η=0/1, zgodność modelu PNR i threshold.

## P-02 — opis histogramu sprzed zmiany overflow (P2)

`photonic_kernel/README.md` ma na początku aktualną uwagę o overflow, ale dalej
mówi o warunkowych histogramach i odrzuconych zdarzeniach. `core.features_from_records`
domyślnie `include_overflow=True`, normalizuje przez raw shots i dołącza acceptance
oraz overflow do momentów. `ROBUSTNESS.md` opisuje to lepiej. Poprawka: usunąć
sprzeczny opis, nadać wersję schematowi cech; nie zmieniać po cichu interpretacji
historycznych tabel.

## Osobna ocena wszystkich kart

Ścieżki w tej tabeli odnoszą się do `qml_model_modules/`. Ocena „poprawny szkic”
nie oznacza pełnego dowodu złożoności ani certyfikacji wszystkich cytowań.

| Nr / plik | Ocena formalizmu | Konkretna poprawka lub warunek |
|---|---|---|
| 01 QSVM | poprawny HS kernel i dual SVM | oddzielić quantum-kernel SVM od FTQC LS-SVM; overlap amplitudowy i jego moduł² wymagają odmiennych estymacji |
| 02 VQC | poprawny model Bornowski; T-05 | wzór shift 1/2[f(θ+π/2)−f(θ−π/2)] zakłada exp(−iθP/2); dla generatora ±r współczynnik r i shift π/(4r). Projektory klas muszą sumować się do I |
| 03 QNN/PQC | poprawny schemat encoder–unitary–measurement | oczekiwana wartość jest deterministyczną funkcją; jej estymata finite-shot jest losowa. QNN jest rodziną modeli, PQC obiektem obwodowym |
| 04 Hybrid QNN | poprawna kompozycja i potrzeba ablacji | dodać gradient po wejściach warstwy kwantowej; konieczne koszty uczenia klasycznego encodera |
| 05 QGAN | sensowny wariant non-saturating loss | podać model danych: klasyczne próbki czy stany; nie każda wspólna funkcja celu jest dosłownie grą minimax |
| 06 QCBM | poprawny szkic rozkładu Borna | określić estymowalną stratę, np. MMD; dokładny KL nie jest automatycznie dostępny z samych próbek |
| 07 QBM | poprawna postać Gibbsa | H hermitowski, β i partycja skończone; annealer nie przygotowuje automatycznie docelowego Gibbsa. Gradient klasyczny nie przenosi się bez zmian na niekomutujące operatory |
| 08 QCNN | T-01: formalizm nie zgadza się z poolingiem | użyć kanału; rozdzielić QCNN i quanvolution, które nie są synonimami |
| 09 Quantum autoencoder | poprawny ideał trash-register | gwarancję rekonstrukcji ograniczyć do rodziny stanów i osiągniętej fidelity. Dla ogólnych stanów mieszanych latent nie musi być czysty |
| 10 Quantum transformer | poprawny kierunek block encoding FTQC; T-03 | pomiar amplitud wyjścia daje kwadraty modułów współrzędnych, nie automatycznie softmax po tokenach |
| 11 HHL | poprawny zarys stanu rozwiązania | jawnie założyć hermitowskość A lub hermitowskie osadzenie, odwracalność na nośniku, κ, model dostępu i koszt postselekcji |
| 12 QSVT | T-02: zbyt ogólne twierdzenie | parzystość P, norma na [-1,1], domena i kodowany blok; lewy/prawy operator zależy od parzystości |
| 13 qPCA | poprawny szkic QPE na spektrum | potrzebna implementacja exp(−iρt), dostęp do kopii ρ albo block encoding; HHL nie jest obowiązkowym podprogramem qPCA |
| 14 Quantum clustering | poprawna odległość wektorów unormowanych; T-04 | centroid średniej w danych nie minimalizuje ogólnie odległości dowolnej mapy φ; uwzględnić normy, fazy i kernel k-means |
| 15 QRL | poprawna polityka przez POVM | wymaga skończonego horyzontu lub γ<1 i kontroli nagród; nie jest pojedynczym kanonicznym algorytmem |
| 16 QAOA | poprawne naprzemienne unitarności i Max-Cut | kierunek min/max zależy od problemu; małe p nie daje ogólnej gwarancji przybliżenia ani klasyfikacji |
| 17 Quantum annealing | użyteczny szkic | twierdzenie adiabatyczne wymaga luki, gładkości i warunków początkowych; otwarty skończenie temperaturowy annealer wymaga osobnego modelu |
| 18 VQE | poprawna zasada wariacyjna po normalizacji ψ | dodać ||ψ||=1 do minimum. SCAR to propozycja ansatzu, nie zakończony test energii VQE; zweryfikować cytowanie QMLB s.296 |
| 19 GAS | poprawna idea adaptacyjnego progu | oracle musi być odwracalny z uncompute; koszt arytmetyki i obsługa nieznanej liczby zaznaczonych stanów należą do algorytmu |

## T-01 — poprawny zapis QCNN (P1)

`08_QCNN.md` zapisuje U=P_L C_L…P_1 C_1 E, mimo że P obejmuje pomiar lub
odrzucenie kubitów. Ogólny pooling jest kanałem, nie operatorem unitarnym:

ρ_out = (P_L ∘ Ad_C_L ∘ … ∘ P_1 ∘ Ad_C_1)(ρ_in),
P(ρ)=Σ_m K_m ρ K_m†, Σ_m K_m†K_m=I.

Przy feed-forward trzeba włączyć operację zależną od m do K_m. Alternatywą jest
dylatacja unitarna na większej przestrzeni i końcowy partial trace. Dopiero
takie doprecyzowanie daje poprawną normalizację predykcji.

## T-02 — parzystość QSVT (P1)

`12_QSVT.md` dla każdego P używa Σ_i P(σ_i)|u_i><v_i|. Ta postać odpowiada
nieparzystemu przekształceniu między prawą a lewą przestrzenią osobliwą.
Parzyste przekształcenie działa w jednej przestrzeni, np. Σ_i P(σ_i)|v_i><v_i|,
z odpowiednim uwzględnieniem jądra operatora i wybranego bloku.

Kontrprzykład: A=diag(1,−1), P=1. Zapis karty daje polarną część A, natomiast
parzysta stała transformacja w pełnej przestrzeni jest I. Różnica normy Frobeniusa
wynosi 2. Należy odwołać się do konkretnej wersji twierdzenia, uwzględniając
parzystość i ewentualne dodatkowe ancille/łączenie wielomianów:
[Gilyén i in.](https://arxiv.org/abs/1806.01838).

## T-03 — amplitudy a tokeny (P1)

`10_QUANTUM_TRANSFORMER.md`, sekcja fizyczna i ograniczenia: ze stanu
|v>/||v|| pomiar w bazie daje |v_k|²/||v||². Nie daje exp(z_k)/Σ_j exp(z_j).
Ponadto wymiar hidden state nie musi być rozmiarem słownika. Potrzebne są
LM head, zdefiniowana transformacja logits→prawdopodobieństwa i jej koszt.
Poprawka: nazwać wynik stanem reprezentacji wyjściowej; usuwać obietnicę
bezpośredniego próbkowania tokenu bez dodatkowej konstrukcji.

## T-06 — cytowania i graf taksonomii (P2)

Manifest źródeł podaje LN=67 stron PDF, PG=680, QMLB=260, AAL=14. Starszy
`QML_algorithms_critical_analysis.md` zawiera np. „QML PDF p.744” i „PG PDF p.1416”.
Takie oznaczenia nie wskazują fizycznej strony tych PDF-ów. AAL może mieć
numerację drukowaną od ok. 59, więc samo s.61 nie jest dowodem błędu. W całym
projekcie wprowadzić dwa pola: `pdf_page` i `printed_page`, plus wersja/DOI źródła.
Nie zastępować błędnych numerów zgadywanymi.

`qml_relation_metrics.md` uczciwie definiuje similarity score, ale słowo „metryka”
nie oznacza tutaj metryki matematycznej: score nie spełnia aksjomatów odległości.
Manualne wagi 1–5 są oceną kuratorską, a top-k filtrem widoku. Graf HTML/JS jest
przydatnym atlasem teorii, lecz nie grafem zależności implementacji. Nowa mapa
projektu te znaczenia rozdziela. Etykiety dojrzałości technologicznej wymagają daty
i podstawy; nie są wynikami benchmarku.
