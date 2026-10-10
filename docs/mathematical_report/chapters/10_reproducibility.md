# 10. Kod, odtwarzalność, bibliografia i plan poprawek

## 10.1 Zakres przeglądarki kodu

Raport zawiera snapshot publicznych plików Python z pakietów hamiltonian_kernel, quantum_reservoir, photonic_kernel, experiments/legacy, tools, scripts, audits i tests oraz kart atlasu i jego demonstratora JavaScript. Dla plików Python indeks AST identyfikuje funkcje i klasy najwyższego poziomu oraz zakresy linii. Fragmenty odsyłane w wyprowadzeniach są walidowane: plik musi istnieć, a obie granice mieścić się w jego długości.

Indeks funkcji nie jest dowodem, że każda funkcja implementuje twierdzenie. Moduły danych, konfiguracji, serializacji, dostawców, raportowania i wykresów pełnią role pomocnicze. Nie przypisujemy im sztucznych hipotez. Przy węzłach naukowych wskazujemy dokładne fragmenty obliczeń; przeglądarka umożliwia odczyt pełnego pliku i jego funkcji. Archiwalne wyniki zachowują daty źródłowe. Snapshot kodu i narzędzi odświeżono po korekcie 9 października 2026; manifest wskazuje dokładną wersję każdego pliku.

Adresy w HTML otwierają wewnętrzną przeglądarkę kodu. Zapisana ścieżka bezwzględna ułatwia odnalezienie oryginału w obecnym komputerze, a kopia kodu w pakiecie i SHA-256 zapewniają działanie po przeniesieniu. Lokalny snapshot kodu nie obejmuje prywatnych profili kont, sekretów, środowisk ani zawartości folderów konfiguracyjnych użytkownika.

## 10.2 Baza i klucze cytowań

Baza report.sqlite ma tabele sources, citations, code_refs, glossary, graph_edges i hypotheses. Klucz sources.id odpowiada identyfikatorowi cytowania w HTML i BibTeX. Citations łączy go z rozdziałem. Code_refs zapisuje ścieżkę, zakres linii i hash. Graph_edges przechowuje równanie oraz warunki relacji. Hypotheses zapisuje tezę, status, założenia, uzasadnienie i proponowaną poprawkę. Dzięki temu można sprawdzić, gdzie użyto danej pracy, a nie tylko przeglądać płaską listę publikacji.

Metadane zawierają poziom inspekcji źródła. Odczyt abstraktu i potwierdzenie autorów nie jest oznaczane jako pełna lektura dowodu. Tam, gdzie raport podaje własny dowód, jego poprawność można sprawdzić lokalnie bez traktowania cytowania jako argumentu z autorytetu. Przy twierdzeniach zaawansowanych z literatury wskazujemy właściwy zakres i ograniczenia, nie obiecujemy własnego odtworzenia całej konstrukcji fault-tolerant z setek stron.

## 10.3 Odtwarzanie artefaktu

Źródła monografii znajdują się w docs/mathematical_report/chapters. Narzędzie tools/build_mathematical_report.py tworzy snapshot danych, bibliografię, indeks kodu, słownik i graf. tools/render_report_math.cjs renderuje wzory przez lokalnie zapisany KaTeX. Wersja KaTeX i jego licencja są zapisane w vendor; fonty są osadzone, więc raport nie odwołuje się do CDN.

Wersja interaktywna korzysta ze wspólnego runtime raportów. Offline export zawiera kompletny snapshot oraz renderowane wzory. Nie jest zależny od 127.0.0.1. Do weryfikacji używa się HTTP preview, natomiast oddzielny test offline blokuje zewnętrzne żądania i sprawdza nawigację, wykresy, definicje i źródła. Weryfikacja browser nie stanowi replikacji eksperymentu naukowego.

## 10.4 Kontrole matematyczne wykonane przy opracowaniu

Małe kontrole sprawdzają: unitarność SCAR dla różnych parametrów i jego lokalną równoważność XY, normowe oszacowanie Trottera na macierzach 2×2, znak nieokreślonego celu KRR, spektralną niestabilność CV przy kroku3, błędną kolejność strat detektora oraz kontrprzykład PCA. Wyniki mają etykietę „kontrola algebraiczna”; nie mieszają się z danymi BA/NRMSE zachowanych benchmarków.

Automatyczne kontrole integralności raportu weryfikują brak nieistniejących kluczy bibliograficznych, poprawne zakresy odnośników, brak błędów renderowania TeX, zachowanie wartości wykresów oraz spójność bazy. Numeryczne zgodności są porównywane z tolerancją dopasowaną do arytmetyki, a nie z arbitralnym wymaganiem bitowej równości macierzy po różnych algorytmach.

## 10.5 Priorytet poprawek naukowych

**Jądra Hamiltonowskie.** Zadeklarować estymator v3 oraz faktyczne użycie raw lub PSD naprawionego kernela, zapewnić wspólną geometrię train/cross w każdym inner fold, rozdzielić reserved i actual gate-shots oraz nazwać widmo przed i po normalizacji. Rozdział 3 podaje matematyczne uzasadnienia i doprecyzowanie kosztu strojenia dawnego benchmarku.

**QRC.** Do prób potwierdzających stosować train-only skalowanie, temporal gaps i zablokowany test. Sprawdzać rzeczywiste replay okna, współdzielone grupy pomiarowe i koszt całej historii. Warunków ESP nie zastępować washout. H1–H5 interpretować w ich własnej rodzinie; stresowe n=8 zachować jako osobne archiwum.

**Fotonika.** Sprawność detektora implementować przed threshold; overflow i postselekcję rozdzielić jako inne cechy. Przy stratach nie traktować czystego hafnianowego stanu jak ogólnego stanu mieszanego. Sprawdzać zbieżność cutoffu i masę ogona, a strojenie liczyć oddzielnie od końcowych shots.

**Legacy i sprzęt.** Poprawić tezę floor4 na warunkową o q*=4, ujawnić kompromis 95% alignmentu i fallback małej siatki. Nazwać ridge i LS-SVM zgodnie z rzeczywistym celem. Po wyborze przypadku według testu wykonać nowy holdout. Równa liczba parametrów nie wyrównuje epok, gradientów ani budżetu. Mitygację raportować z kalibracją i conditioning.

**Atlas.** Rozdzielić implementowane, projektowane i czysto teoretyczne metody. Poprawić pooling QCNN, parzystość/przestrzenie QSVT, rozkład pomiaru transformera, nieliniowe centroidy i współczynniki parameter shift. Relacje podobieństwa opisów zachować jako heurystykę organizacyjną.

## 10.6 Granice kompletności naukowej

Dokument pokrywa obecne gałęzie i karty metod, ich centralne konstrukcje, wyprowadzenia oraz ustalenia audytu. Nie zmienia faktu, że część pełnych planów eksperymentalnych nie została wykonana. Pełny dowód nowej przewagi, uniwersalności ansatzu lub jednostajnej stabilności wymagałby osobnego wyniku badawczego; brakujący dowód jest w raporcie jawnym problemem, a nie pominiętym krokiem.

Zaawansowane twierdzenia QSVT, HHL i adiabatyczne podajemy ze zdefiniowanymi warunkami oraz wyprowadzeniem mechanizmu używanego w atlasie. Kompletny konstruktywny dowód wszystkich źródłowych twierdzeń tych teorii wykracza poza matematykę implementowanego projektu i jest dostępny w cytowanych pracach. Dzięki temu czytelnik może odróżnić dowód lokalnego elementu od formalnego wyniku literaturowego, na którym opiera się dalszy projekt.
