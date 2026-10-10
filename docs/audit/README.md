# Audyt projektu QML — 22 września 2026

## Ocena całości

Projekt ma wartościowy rdzeń badawczy: porównanie jakości predykcji, błędu dynamiki
i kosztu pomiaru. Najdojrzalszy jest benchmark Hamiltonian kernels, następnie
eksploracyjne badania mechanizmu pamięci QRC. Eksperymenty SCAR/HPO i fotonika są
dobrymi prototypami, lecz nie uzasadniają twierdzenia o przewadze kwantowej.
Starsze dowody H2 oraz część kart teoretycznych wymagają korekty matematycznej.

Ocena jest analizą wspomaganą przez AI z perspektywy informacji kwantowej,
analizy operatorowej, statystyki i inżynierii. Nie jest zewnętrzną recenzją
profesorską ani certyfikacją. Równoległe przeglądy agentów zostały przerwane
limitem usługi; ich wstępne ustalenia sprawdzono lokalnie przed uwzględnieniem
w poniższych raportach. Nie przypisujemy im ukończonych, niezależnych recenzji.

## Zakres i granice sprawdzenia

- Inwentaryzacja 12 306 plików, 4 627 430 678 bajtów, z hashami SHA-256 przed
  reorganizacją. Z tego 12 126 plików znajduje się w `analysis_output`.
- Przegląd matematyki i kluczowych ścieżek implementacji każdej gałęzi; osobna
  ocena wszystkich 19 kart algorytmów. Katalog AST obejmuje każdy plik Python
  w publikowanym kodzie. Katalogowanie nie oznacza ręcznego odczytu każdej linii.
- Wykonano wszystkie 107 zastanych testów: **107 PASS**, 29,253 s w środowisku
  lokalnym Python 3.12.14. Testy nie wymagają wysłania zadań QPU.
- Powtórzono cały zestaw w wypakowanej paczce publikacyjnej: **107 PASS**, 17,991 s.
  Potwierdzono importowanie kodu z tej kopii, zgodność 8 starych wejść oraz budowę
  wheel. Wyniki i granice walidacji: [validation.json](validation.json).
- Wykonano dodatkowe reprodukcje matematyczne: [wyniki](review_checks.json),
  kod `audits/project_review_checks.py`. Są to sondy błędów, nie regresje
  dowodzące ich usunięcia.
- Przejrzano statusy aktualnych protokołów, reprezentatywne artefakty i treść
  5 PDF-ów oraz 3 prezentacji: [indeks](document_index.json). Nie wykonano
  ponownego pełnego treningu wszystkich historycznych eksperymentów, audytu
  wizualnego każdej strony ani niezależnej rekonstrukcji każdego z 12 tys. plików.
- Środowiska, cache, `tmp` i niezwiązany CRM są wyłączone z audytu naukowego.
  Drugi workspace zawiera 20 identycznych kart teorii; potwierdzono zgodność,
  bez tworzenia drugiej aktywnej kopii projektu.
- Identyfikatory zapisanych jobów nie zostały ponownie uwierzytelnione w chmurze.
  Statusy sprzętowe odnoszą się do dostępnych zapisów, nie do nowego wykonania.

## Raporty dziedzinowe

1. [Hamiltonian kernels, Trotter i estymatory](hamiltonian_review.md).
2. [Rezerwuary, analiza operatorowa i szeregi czasowe](reservoir_review.md).
3. [Fotonika i wszystkie 19 modułów teorii](photonic_theory_review.md).
4. [Starsze QSVM, HPO, SCAR, sprzęt i materiały końcowe](legacy_review.md).
5. [Mapa relacji całego projektu](../project_map.md).
6. [Katalog plików i deklaracji](source_catalog.md), [inwentarz](inventory.csv).

## Rejestr ustaleń

P1: wpływa na interpretację naukową lub może zmienić wynik. P2: wymaga korekty
metadanych, opisu albo ograniczenia zakresu. Priorytet nie oznacza, że wszystkie
historyczne wyniki danej gałęzi są błędne.

| ID | Priorytet | Potwierdzone ustalenie | Zalecane działanie |
|---|---|---|---|
| H-01 | P1 | v3 klasyfikuje na surowych, potencjalnie nieokreślonych Gramach; PSD zapisuje diagnostycznie | określić estymator i naprawę train/cross w każdym inner fold; nowy protokół |
| H-02 | P2 | `two_qubit_gate_shots_used` używa maksymalnego kosztu testowego kandydata | oddzielić rezerwację od faktycznego kosztu wybranej polityki |
| H-03 | P2 | `spectral_eigenvalues` dotyczy macierzy przed normalizacją, a publikowany kernel jest po normalizacji | zmienić nazwy i zapisać oba widma |
| R-01 | P1 | starszy Mackey–Glass skaluje wejście ekstremami całego szeregu | parametry skalowania z train; nowa wersja wyników |
| R-02 | P1 | starsze splity h=5 nie mają przerwy przy granicach | split zgodny z czasem dostępności etykiet; jawny gap |
| P-01 | P1 | adapter SF stosuje sprawność detektora po progowaniu | stratę detekcyjną zastosować przed `MeasureThreshold` |
| P-02 | P2 | fotoniczny README miesza opis warunkowego histogramu z jawnym overflow | ujednolicić opis i wersje cech |
| L-01 | P1 | twierdzenie H2 wyprowadza dokładnie 1/4 wymiaru z q≥4 | twierdzenie warunkowe q*=4 albo tabela kosztu dla q* |
| L-02 | P2 | selekcja 95% alignmentu opisana jako maksymalizacja | zastąpić argmax regułą near-optimal z tie-break |
| L-03 | P1 | przypadek HPO do QPU wybierany po wyniku testowym | osobny zbiór wyboru i nowy holdout; pilot oznaczyć post-selection |
| L-04 | P1 | OptDigits łączy oficjalne train/test przed ponownym podziałem | zachować podział według autorów pisma dla benchmarku zewnętrznego |
| L-05 | P2 | profile HPO: trening analityczny, shot noise dopiero w teście | precyzyjna nazwa scenariusza; osobny trening finite-shot |
| T-01 | P1 | QCNN z pomiarem/poolingiem zapisany jako pojedyncze UρU† | kompozycja kanałów CPTP/instrumentów |
| T-02 | P1 | QSVT pomija parzystość i przestrzenie lewych/prawych wektorów | podać odd/even SV transform oraz założenia twierdzenia |
| T-03 | P1 | amplitudowe wyjście transformera utożsamione z predykcją tokenu | oddzielić stan cech, logits i rozkład softmax |
| T-04 | P2 | średnia centroidu nie jest ogólnie optymalna dla dowolnej nieliniowej feature mapy | ograniczyć do właściwej geometrii albo użyć kernel k-means |
| T-05 | P2 | reguła shift ±π/2 podana dla dowolnego generatora dwuwartościowego | jawnie założyć generator Pauliego/2 lub podać ogólną skalę |
| T-06 | P2 | część odwołań opisanych jako strony PDF wykracza poza liczbę stron źródła | zweryfikować locator względem konkretnego PDF i numeracji drukowanej |

## Co jest ograniczeniem, a nie nowo wykrytym błędem

Pełny run Trotter v3 ma **1/1600** warunków i sam poprawnie oznacza się
`not_confirmatory`; jego `audit: passed` dotyczy integralności wykonanej części.
Nie wolno zamieniać tego statusu na potwierdzenie hipotez. Niepełność nie jest
usterką mechanizmu audytu. Podobnie nowe QRC jawnie deklaruje badania eksploracyjne,
a fotonika nie deklaruje wykonania SF/X8 w bieżącym środowisku.

Zysk projected nad fidelity przy ograniczonych pomiarach nie jest przewagą nad
klasycznym ML. Kilka urządzeń w syntetycznych profilach nie daje kilku niezależnych
eksperymentów sprzętowych. Powtarzanie splitów tego samego zbioru nie tworzy nowych
niezależnych datasetów. Testy kodu, audyty integralności i dowód matematyczny
odpowiadają na różne pytania.

## Wnioski wspólne dla gałęzi

Wspólnym obiektem jest mapa danych albo historii wejściowej do cech. Dla stanów
ρ(x) kernel Hilberta–Schmidta ma postać Tr[ρ(x)ρ(x′)], a liniowy odczyt rezerwuaru
jest równoważny regresji jądrowej na zmierzonych cechach przy zgodnym centrowaniu
i regularyzacji. Nie znaczy to, że wszystkie eksperymenty mierzą ten sam kernel.

Wspólna unitarna ewolucja zachowuje Tr[ρσ]. Hamiltonian kernel może się zmieniać,
bo U zależy od x; rezerwuar może się zmieniać, bo ma reset, historię i ograniczony
odczyt. Wniosek o wpływie Trottera wymaga zawsze wskazania, które z tych elementów
się zmienia. Dla mieszanych stanów Tr[ρσ] jest PSD kernelem, ale nie ogólnie
wiernością Uhlmanna i jego diagonala wynosi Tr[ρ²], a nie koniecznie 1.

Żadna z następujących implikacji nie jest ogólnie prawdziwa:
większa przestrzeń Hilberta ⇒ większa informacja użyteczna; mniejsza infidelity ⇒
lepsza predykcja; większa ekspresyjność ⇒ lepszy trening; niższy błąd symulatora ⇒
tańszy QPU; dodatnie Δ(nieliniowa−liniowa pamięć) ⇒ wzrost nieliniowej pamięci.

Hipotezy trzeba nazwać przestrzeniami nazw, np. `legacy-qsvm/H2`, `qrc/H2`,
`trotter-v3/effect-*`. Aktualne H1/H2/H3 z różnych katalogów nie mają wspólnej
treści i nie mogą być łączone w jedno potwierdzenie.

## Kolejność poprawek i kryteria akceptacji

1. Poprawić formalizm H2, QCNN, QSVT, wyjścia transformera i cytowania; zsynchronizować
   generatory PDF/PPT. Akceptacja: każda teza ma warunki i źródło, a stary dokument
   ma status historyczny oraz odsyłacz do erraty.
2. Naprawić P-01 oraz wybrać estymator PSD/indefinite dla v3. Akceptacja: test detekcji
   dla n=0,1,2,5 i η=0,0.5,1; train/cross z jednej mapy; brak użycia validation/test
   do fitowania mapy; stabilność regularizacji przy ujemnych wartościach własnych.
3. Wersjonować H-02/H-03 bez zmiany starych CSV. Akceptacja: rachunek kosztu odpowiada
   faktycznie wybranemu kandydatowi, a każde widmo zgadza się z nazwaną macierzą.
4. Zamrozić nowe splity czasowe i piszących OptDigits; oddzielić wybór pilota HPO
   od testu. Akceptacja: jawne identyfikatory próbek, granice czasowe i nowy holdout.
5. Dopiero potem przeprowadzić nowy pełny eksperyment potwierdzający. Dokładać
   niezależne zadania i porównania z klasycznymi modelami bez ograniczenia PCA=4.
   Zachować koszty strojenia, pomiarów, kompilacji i odczytu.

Nie zmieniono algorytmów badawczych ani historycznych wyników w ramach porządkowania.
Zmiany kodu historycznego obejmują ścieżkę ROOT i importy po wydzieleniu źródeł;
ich manifest jest w [source_migration.json](source_migration.json).

## Odtworzenie audytu

```sh
python -m unittest discover -s tests -v
python -m audits.project_review_checks
python tools/check_publication.py
python tools/build_source_catalog.py
```

`tools/project_inventory.py` liczy hashe całego lokalnego zasobu i może trwać
dłużej; nie odtwarza oryginalnego inwentarza po reorganizacji. Oryginał zachowano.
`tools/audit_documents.py` wymaga dodatkowo pypdf i zapisuje ekstrakcje w `tmp/`.

## Źródła metodologiczne

Alignment ma uzasadnienia teoretyczne przy określonych założeniach, ale sama
reguła near-best nie gwarantuje generalizacji ani maksymalnego alignmentu:
[Cortes, Mohri, Rostamizadeh (2012)](https://jmlr.csail.mit.edu/papers/v13/cortes12a.html).
Wariancja wyników CV wymaga uwzględnienia zależności między foldami:
[Bengio i Grandvalet (2004)](https://jmlr.csail.mit.edu/papers/v5/grandvalet04a.html).
Warunki QSVT i parzystość należy cytować z twierdzenia źródłowego:
[Gilyén i in.](https://arxiv.org/abs/1806.01838).
Rozdzielenie pamięci, ESP i odczytu w QRC:
[Kobayashi, Tran, Nakajima](https://arxiv.org/abs/2403.02686) oraz
[Mujal i in.](https://doi.org/10.1038/s41534-023-00682-z).
