# Szczegółowy raport całego projektu QML

Opracowanie z 23.09.2026 rozwija audyt z 22.09.2026. Nie zawiera nowych treningów
ani nowych zadań QPU. Zmiany dotyczą raportowania i objaśnień, a nie algorytmów.

1. [Raport główny — 18 rozdziałów](QML_REPORT.md): modele matematyczne, implementacje,
   wyniki, 19 kart teorii, statystyka, błędy, plan napraw, repozytorium i diagramy.
2. [Wszystkie relacje mapy i taksonomii](GRAPH_RELATIONS.md): 49 + 30 krawędzi.
3. [Wszystkie relacje kuratorskie](CURATED_RELATIONS.md): 19 połączeń oryginalnego atlasu,
   z oceną znaczenia ręcznych wag i granic interpretacji.
4. [Graf importów](IMPORT_RELATIONS.md): 137 krawędzi snapshotu audytu, z symbolami i liniami.
5. [Podobieństwo opisów — CSV](similarity_relations.csv): 506 wpisów para×cecha.
6. [Pełne dane grafów](graph_relations.json): źródła, hashe, objaśnienia, wspólne etykiety,
   składniki score, wagi i rangi; [zliczenia](graph_counts.json).

Graf importów dotyczy 112 plików snapshotu audytu. Nowe narzędzia generowania tego
raportu nie są dopisywane wstecz do starego snapshotu.

Wersja przeglądarkowa powstaje lokalnie w `output/detailed_report_app_20260923`.
Jej przenośna wersja HTML jest eksportem tej samej aplikacji, z pełną treścią i danymi.
Podgląd HTTP wymaga działającego lokalnego serwera. Niczego nie opublikowano zdalnie.

## Odtworzenie

```sh
python tools/build_report_relations.py --node /path/to/node
python tools/build_report_view.py --app output/detailed_report_app_20260923 --complete
```

Drugi krok wymaga wcześniej przygotowanego szkieletu Data report i zachowuje jego
tożsamość. Budowę HTML wykonuje skrypt `data-app.mjs build --separate-data` z pluginu
Data. Do czytania Markdown, CSV i JSON nie jest potrzebna aplikacja ani plugin.

Oryginalna funkcja JavaScript `makeEdges` została porównana z odtworzonymi wartościami
score i weight dla wszystkich krawędzi dostępnych przy maksymalnym limicie 100
w każdej cesze: 417 zgodnych porównań. Pełny katalog obejmuje także pozostałe 89
krawędzi poza tym limitem, obliczone tą samą regułą.
