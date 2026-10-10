# Odtwarzanie warstwy interaktywnej

Ten katalog zachowuje autorskie komponenty i style raportu (również poprawki
nawigacji i typografii). Dane i źródła treści pochodzą z katalogu nadrzędnego.
Nie zawiera chronionego runtime aplikacji ani konfiguracji kont.

Aby odtworzyć edytowalną aplikację, przygotuj aplikację raportową przez
zainstalowany plugin Data Analytics, skopiuj te pliki do jej `src/content/report/`,
a następnie uruchom z głównego katalogu projektu:

```sh
python tools/build_mathematical_report.py --app /path/to/prepared/app --node /path/to/node --complete
```

Użyj oficjalnego budowania `data-app.mjs build --separate-data` i eksportu
`export-offline` z pluginu. Generator uzupełni pliki JSON i zachowa istniejący
identyfikator aplikacji. Do czytania HTML udostępnionego z wydaniem plugin
nie jest potrzebny. Do samego renderowania wzorów wystarczy lokalny Node i
zapisany KaTeX; zależności przeglądarkowej kontroli opisano w README monografii.
