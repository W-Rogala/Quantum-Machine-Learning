# Rezerwuary kwantowe, pamięć i analiza operatorowa

## Konstrukcja i elementy poprawne

`core.py` opisuje macierz gęstości, zastąpienie kubitu wejściowego stanem zależnym
od u, ewolucję exact/Trotter oraz odczyt X, Z i ZZ. Kanał wejściowy ma postać
R_u(ρ)=ρ_in(u)⊗Tr_in(ρ), więc jest CPTP. Późniejsza ewolucja unitarna zachowuje
ślad i dodatniość. Testy sprawdzają tę konstrukcję, a IBM adapter porównuje
konwencje kolejności kubitów z referencją gęstościową.

`H1_H2_SPECTRAL_ANALYSIS.md` jest szczególnie wartościową częścią: prawidłowo
rozróżnia widmo Hamiltonianu, fazy U, widmo kanału i obserwowalność. Rozróżnia też
ciągłe zmienne, ciągły czas i ciągłe widmo. Oscylator ma dyskretne energie mimo
CV, a truncacja Focka nie dowodzi własności operatora nieskończenie wymiarowego.

## R-01 — przeciek skalowania w starszym Mackey–Glass (P1)

`quantum_reservoir/benchmarks.py:63–70` oblicza min/max po całej serii obejmującej
test i przyszłe wartości targetu. Parametry kodowania wejścia zawierają więc
informację o przyszłości. To leakage preprocessingu; jego ilościowego wpływu
na opublikowane NRMSE nie oszacowano bez nowego uruchomienia.

Dotyczy starszych ścieżek `experiment.py` oraz adaptera IBM korzystających
z tego generatora. Nowsze `spectral_h1_h2_study.mg_data` używa min/max z `TRAIN`,
stosuje clipping na wejściu i zachowuje target w skali surowej. H3 dziedziczy
tę nowszą ścieżkę. Nie należy przenosić zarzutu na wszystkie wyniki QRC.

Poprawka: generator zwraca surową serię, preprocessing przyjmuje train indices,
a manifest zapisuje lo/hi i clipping rate. Test przyczynowości: zmiana przyszłego
ogona danych nie może zmienić wejść treningowych. Stare wyniki zostają archiwum.

## R-02 — dostępność etykiet przy horyzoncie 5 (P1)

`experiment.py:89–108` tnie kolejne bloki bez gap. Przy y_t=x_(t+5) ostatnie
etykiety treningowe wykorzystują okres początku walidacji; analogicznie przy
refit train+validation część etykiet pochodzi z okresu testowego. Trzeba zdefiniować
moment treningu: dla oceny zamrożonego predyktora na granicy czasu jest to
naruszenie dostępności etykiet. Kontynuacja stanu rezerwuaru z samych znanych
wejść nie jest sama w sobie leakage.

Nowa ścieżka ma TRAIN=200..799, VAL=805..1054, TEST=1060..1359, co daje przerwy
pięciu kroków dla MG5. Poprawka legacy: ten sam protokół dostępności, osobne
timestampy input/target, jawne zasady aktualizacji modelu. Test musi sprawdzać
indeksy targetów, nie tylko brak wspólnych indeksów x.

## Kontrakcja, ESP i stabilność Trottera

Reset jednego kubitu nie daje ścisłej kontrakcji całego stanu w jednym kroku.
Weź ρ=|00><00| i σ=|01><01| przy wejściu na pierwszym kubicie. Po resecie
pozostałe stany są nadal ortogonalne; wspólne U zachowuje normę śladową.
Reprodukcja zwraca współczynnik 1. To potwierdza poprawne zastrzeżenie w nowszym
dokumencie, a nie nowy błąd tej części projektu.

Warunkowe ograniczenie błędu blokowego
q^k D_0 + L ε(1−q^k)/(1−q) wymaga wspólnego q<1 dla wszystkich dozwolonych
sekwencji wejść w bloku. Widmo kanału przy u=0.5 tego nie dowodzi. Nie-normalne
kanały mogą mieć przejściowe wzmocnienie w nieodpowiedniej normie; skończona
symulacja washout nie zastępuje jednostajnej kontroli. W CV potrzeba dodatkowo
dziedziny operatorów, ograniczeń energii i kontroli zbieżności truncacji.

## Osobna ocena podbadań

| Część | Ocena | Wymagana interpretacja / poprawka |
|---|---|---|
| `benchmarks.py`, `experiment.py` | poprawny prototyp dynamiki, historyczne problemy splitu | R-01/R-02; wyników MG5 nie używać jako finalnego testu |
| `spectral_h1_h2_study.py`, raport | użyteczne kontrole przemienności, braku sprzężeń i rezonansu | standardowy H1/H2 nie jest rozstrzygnięty przez małą próbę |
| `h3_memory_study.py` | rozdziela cele pamięci i różne readouty | sumy 1−NRMSE² to zdolność wybranego dekodera; dopuszczalne ujemne wyniki |
| `h3_readout_controls.py` | istotna kontrola informacji dostępnej pomiarowo | 255 oczekiwań nie jest tanim odczytem na QPU |
| `h3_washout_check.py`, `h3_stationary_check.py` | kontrole numeryczne pamięci początkowej i reżimu | nie certyfikat ESP dla wszystkich wejść |
| `h3_noise_study.py` | jawny model kanałów, czasu i pomiaru | scenariusze syntetyczne, nie kalibracja urządzenia; T2≤2T1 |
| `h3_noise_diagnostics.py`, `h3_noise_report.py` | potrzebne rozdzielenie zaniku sygnału i wariancji readoutu | zmiana siatki ridge po eksploracji wymaga nowej replikacji |
| `ibm_hardware.py`, `tools/qrc_ibm_hardware.py` | okno historii i grupowanie X/Z są implementowalne | porównać z pełną historią, policzyć koszt rewind i resetów |
| raporty, notebook, `tools/audit_qrc_results.py` | zawierają sprawdzenia niezależnych wzorów i hashe | wygenerowany notebook jest innym widokiem istniejącego kodu, nie replikacją |

Dodatnia różnica T=(C_product−C_linear)/10 może wynikać z utraty C_linear;
nie dowodzi wzrostu nieliniowej pamięci. Nowy raport H3 uczciwie to zaznacza.
Większa liczba cech zawierająca poprzedni zbiór nie gwarantuje mniejszego błędu
testowego ridge: zmienia wariancję i regularizację. Nieliniowy dekoder może
ujawnić inną informację niż badany odczyt liniowy.

## Werdykt hipotez

H1–H5 to protokół, a nie lista pięciu potwierdzonych twierdzeń. Dostępne H1/H2
i H3 są eksperymentami eksploracyjnymi i kontrolami mechanizmów. Nie znaleziono
kompletnego wykonania pierwotnego testu potwierdzającego H1–H5. Rezonans obala
bezwarunkowe użycie p=2,r=2. Poprawa względem fixed exact nie utrzymuje się
jednoznacznie względem tuned exact i mocnych klasycznych opóźnień.

W raporcie spektralnym deterministyczny przypadek commuting ma p=0 opisane jako
konwencję kodu. W nowej wersji zapisywać `p=null`, `test_type=analytic_equality`,
aby agregator nie potraktował tego jako pomiaru ekstremalnej istotności.
Szum może poprawiać zapominanie, jednocześnie usuwając użyteczny sygnał:
potrzebna jest wspólna analiza pamięci, jakości i kosztu, nie samo widmo.
