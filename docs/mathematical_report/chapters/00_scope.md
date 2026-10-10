# 0. Zakres, sposób czytania i status dowodów

Raport matematyczny projektu QML łączy formalne wyprowadzenia, sprawdzalne odwołania do kodu i analizę zachowanych wyników. Opracowanie powstało 5 października 2026; oznacza datę inspekcji materiału, a nie datę wykonania dawnych eksperymentów. Nie wykonano nowych treningów ani zadań QPU. Nowe obliczenia weryfikacyjne to małe przykłady algebraiczne, kontrprzykłady i kontrole integralności dokumentu. Ich rola jest inna niż rola benchmarku.

Korekta redakcyjna i techniczna: **9 października 2026**. Doprecyzowano kierunki zerowe QSVT, intercept ridge i nośnik polityki QRL, sprawdzono nawigację i uzupełniono eksport GitHub. Daty oraz wyniki archiwalnych eksperymentów pozostają bez zmian.

## 0.1 Co stanowi przedmiot oceny

Trzy implementowane gałęzie to jądra Hamiltonowskie, rezerwuary kwantowe i jądra fotoniczne. Odrębny materiał obejmuje historyczne klasyfikatory QSVM, ansatze SCAR, strojenie HPO, integracje sprzętowe oraz atlas dziewiętnastu rodzin algorytmów. Atlas jest dokumentacją koncepcji: obecność karty HHL, QSVT czy QPCA nie oznacza implementacji pełnego algorytmu. W każdym przypadku wskazujemy, gdzie kończy się matematyczna definicja, a zaczyna rzeczywisty kod.

Stan zachowanych danych obejmuje m.in. benchmark Hamiltonowski, eksperymenty spektralne QRC, badania pamięci H3 i szumu oraz wcześniejsze doświadczenia SCAR. Różne daty i jednostki replikacji nie pozwalają nadać wszystkim wynikom jednej wspólnej daty eksperymentu. Każdy wykres podaje plik źródłowy, poziom agregacji i ograniczenie interpretacji.

## 0.2 Pięć klas stwierdzeń

**Twierdzenie matematyczne** ma jednoznaczne założenia i dowód. Przykład: macierz iloczynów Hilberta–Schmidta stanów jest PSD. Dowód obowiązuje dla dowolnego skończonego zbioru stanów; nie jest statystycznym potwierdzeniem przewagi klasyfikatora.

**Twierdzenie warunkowe** wymaga założenia, którego projekt nie wykazał. Przykład: geometryczna granica błędu obcięcia historii zakłada wspólny współczynnik kontrakcji mniejszy od jedności. Sam reset jednego kubitu nie wystarcza, aby takie założenie uzyskać.

**Hipoteza empiryczna** dotyczy jakości, kosztu lub mechanizmu w określonej populacji eksperymentów. Przykład: wybrany schemat Trottera obniża NRMSE o przynajmniej 2%. Wymaga niezależnych jednostek replikacji i procedury selekcji zamrożonej przed testem.

**Diagnostyka numeryczna** potwierdza określoną tożsamość albo niezmiennik dla sprawdzonych przypadków. Mały błąd unitarności macierzy jest kontrolą implementacji. Nie zastępuje dowodu dla wszystkich parametrów ani badania błędów urządzenia.

**Projekt lub materiał teoretyczny** opisuje rodzinę metod bez uruchomionej implementacji. Jej przewagi z literatury obowiązują przy założeniach tej literatury; nie przechodzą automatycznie na lokalny projekt.

## 0.3 Dlaczego oznaczenia hipotez muszą mieć przestrzeń nazw

W projekcie symbol H2 oznacza kilka różnych pytań: ograniczenie liczby kubitów w historycznym QSVM, walidacyjny wybór schematu w QRC, spektralną możliwość poprawy predykcji, a w kolejnych protokołach inne kontrasty. Raport stosuje identyfikatory LEG-H2, QRC-H1–H5, SPEC-H1/H2 i HK-V3. Zgodność nazw nie jest zależnością logiczną.

Dowody autorskie w raporcie są rekonstrukcjami matematycznymi standardowych konstrukcji lub analizą lokalnego kodu. Nie oznaczają roszczenia o nowe odkrycie. Przy źródłach wskazujemy zakres wsparcia: definicja, kontekst, twierdzenie lub metoda analizy. Literatura nie potwierdza lokalnej jakości modelu bez danych.

## 0.4 Jak sprawdzać argument

Czytanie pojedynczego zagadnienia zaczyna się od definicji dziedziny i założeń. Następnie przechodzi przez wyprowadzenie, wniosek i ograniczenia. Odnośnik „kod” otwiera lokalnie zapisaną wersję pliku z numerami linii oraz wyróżnieniem konkretnego fragmentu. Hash SHA-256 określa, do której wersji odnoszą się linie. Kod w raporcie pozostaje dostępny po przeniesieniu samego pliku HTML na inny komputer.

Wzory są renderowane lokalnie. Skróty i pojęcia w tekście mają krótką definicję po najechaniu lub skupieniu klawiaturą; kliknięcie prowadzi do rozwiniętego słownika. Wzory używają notacji z kolejnego rozdziału. Symbole wyjaśnia się bezpośrednio przy ich pierwszym zastosowaniu, gdy mają znaczenie zależne od rozdziału.

Bibliografia w HTML jest dostępna offline, podobnie jak metadane w BibTeX, JSON i SQLite. Kliknięcie DOI lub adresu publikacji otwiera źródło zewnętrzne i wymaga internetu. Pakiet nie zawiera nieuprawnionych kopii podręczników. Odnośniki do rozdziałów i tematów wewnątrz raportu działają bez internetu.

## 0.5 Najważniejszy wniosek metodologiczny

Formalna poprawność reprezentacji, poprawność algorytmu numerycznego i przewaga predykcyjna są trzema osobnymi tezami. Projekt ma poprawne podstawy wielu konstrukcji i wartościowe kontrole, ale część zapisów zbyt silnie przechodzi między tymi poziomami. Raport pokaże dokładne przejścia, których można dowieść, oraz pytania wymagające nowych prób. Zapisane wyniki nie dowodzą uniwersalnej przewagi kwantowej ani zakończenia wszystkich zaplanowanych hipotez.

Poprawki opisane w tej monografii są propozycjami dla kolejnej wersji naukowej. Nie zmieniają archiwalnych eksperymentów ani nie przypisują im retrospektywnie nowego protokołu.
