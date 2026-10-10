# 8. Analiza porównawcza i poprawne wnioskowanie

## 8.1 Miary: co dokładnie jest porównywane

Accuracy to odsetek wszystkich poprawnych predykcji. Balanced accuracy dla C klas to średnia recall: BA=C^{-1}Σ_c TP_c/(TP_c+FN_c). Macro F1 uśrednia 2TP_c/(2TP_c+FP_c+FN_c) po klasach; nie jest F1 obliczonym z uśrednionych precision i recall. Jeżeli klasa nie występuje w danym segmencie, potrzebna jest jawna konwencja, a nie milcząca zamiana braku informacji na zero.

NRMSE=sqrt(N^{-1}Σ(y_i−ŷ_i)²)/σ_y, gdzie σ_y jest populacyjnym odchyleniem w segmencie oceny zgodnie z kodem. Jednostki licznika i mianownika skracają się. NRMSE jest niezdefiniowane dla stałego celu. Nie wolno porównywać bez zastrzeżenia różnych definicji normalizacji: przez rozstęp, średnią lub odchylenie train.

R²=1−SSE/SST może być ujemne na teście. Nie jest kwadratem korelacji, chyba że zachodzą odpowiednie warunki regresji z interceptem i oceny na dopasowanej próbie. Ujemne testowe R² lub ujemne pamięci C(d) są ważną informacją o gorszej predykcji niż średnia, nie błędem do obcięcia.

## 8.2 Wykres HK: budżet pomiarowy i jakość

Wykres porównuje cztery grupy finite-shot: fidelity i projected przy 200 tys. oraz 1 mln circuit-shots. Zachowane średnie BA wynoszą odpowiednio 0.805260, 0.873357, 0.931008 i 0.958920. Przy milionie różnica projected−fidelity to 0.0855633, czyli 8.556 punktu procentowego. Przy 200 tys. wynosi 12.5748 punktu. Referencja klasyczna SVM-RBF ma 0.977539, więc projected przy milionie pozostaje niżej o 1.8618 punktu.

Źródło: [[file:results/hamiltonian/publication_summary.csv]]. Finite-shot ma 375 wierszy na grupę, ideal i klasyczne 75. SD w tej tabeli opisuje rozrzut tych wierszy. **Nie jest 95% CI ani błędem standardowym niezależnych eksperymentów.** Splity, noise replicates i warunki współdzielą informacje. Wykres średnich pokazuje rozmiar efektu, a tabela ujawnia SD i liczności bez nadawania fałszywej niezależności.

Budżet historycznego publication_benchmark dotyczy końcowej estymacji po strojeniu na idealnych statevectors. Oznacza to inne rozliczenie niż pełny koszt shotowego HPO. Tę interpretację trzeba zachować w porównaniu do v3 i QPU.

## 8.3 Wykres LEG-H2: wynik kontra wymiar

Trzy historyczne datasety pokazujemy oddzielnie dla H0 6q, agresywnego H1 i H2 z floor4. Dane pochodzą z [[file:results/legacy/iterative_qsvm_summary.csv]]. Każda średnia dotyczy dziesięciu losowych podziałów tej samej bazy. Wykres BA ujawnia wynik, a odrębny wykres stosunku amplitud pokazuje zasób statevectorowy. Oś zasobowa nie oznacza czasu QPU.

Pokazywanie obu wielkości zapobiega logicznemu skrótowi „mniej amplitud, więc lepsze uczenie”. Tabela może potwierdzać konkretne średnie archiwalne. Nie potwierdza twierdzenia o wszystkich datasetach ani niezależnej replikacji po adaptacji hipotezy do wcześniejszych wyników.

## 8.4 Wykresy QRC: miary bez mieszania estymandów

W badaniu spektralnym wyświetlamy geometryczny iloraz NRMSE i zapisane CI osobno dla przypadku oraz H1/H2. Referencją jest iloraz jeden, margines H1 to 1.02, a H2 to 0.98. Źródło: [[file:analysis_output/qrc_spectral_h1_h2/qubit_summary.csv]]. Liczba bloków wynosi osiem, więc jest to osobne badanie stresowe, a nie zakończenie protokołu z dwudziestoma blokami.

Badanie szumu zawiera kontrasty o dwóch jednostkach. BAB: finite shots−ideal i mild−ideal są różnicami wskaźnika pamięci, podczas gdy NARMA10 i MG5 podają ilorazy NRMSE. Dlatego trafiają na dwa odrębne wykresy. Źródło: [[file:results/qrc/noise_paired_contrasts.csv]]. Wspólna oś dla różnicy −8.868 i ilorazu 0.921 byłaby matematycznie myląca.

Zmiany T z H3 wyświetlamy wraz z trzema reżimami i oryginalnymi CI: [[file:analysis_output/qrc_h3_memory/h3_contrasts.csv]]. Dodatnia zmiana różnicy product−linear sama nie dowodzi wzrostu nieliniowości: może wynikać ze spadku linear. Z tego powodu drugi wykres przedstawia obie składowe pamięci na podstawie [[file:analysis_output/qrc_h3_memory/profile_summaries.csv]], rozdzielając reżim i view.

## 8.5 Dlaczego log-iloraz i geometryczna średnia

Dla dodatnich błędów E_candidate,E_ref definiujemy d_b=log(E_candidate/E_ref). Przy dwóch ustalonych zadaniach kontrast blokowy jest średnią ich log-ilorazów. Wtedy exp(mean d_b) jest geometryczną średnią ilorazów, która traktuje mnożnik 2 i 1/2 symetrycznie.

```math
R=\exp\left(\frac1B\sum_{b=1}^B d_b\right)
=\left(\prod_{b=1}^B\frac{E_{b,c}}{E_{b,r}}\right)^{1/B}.
```

Średnia ilorazów nie jest ilorazem średnich. Przykład błędów referencji (1,100) i kandydata (2,50): średnia ilorazów=1.25, geometryczna=1, iloraz średnich=52/101≈0.515. Każdy estymand odpowiada innemu pytaniu. Projekt protokołu stosuje średnie log-ilorazy na poziomie bloków; trzeba zachować tę definicję.

## 8.6 Non-inferiority i brak istotności

Dla marginesu m=log1.02 test jakości ma H0:μ≥m i H1:μ<m. Przy niezależnych blokach, modelu normalnym kontrastów i nieznanej wariancji statystyka t=(d̄−m)/(s_d/√B) ma rozkład t_{B−1} na granicy hipotezy zerowej. Odrzucamy w lewym ogonie. Wniosek równoważny kontrolowanej jednostronnej górnej granicy dla μ poniżej m.

Test H0:μ=0 kontra μ≠0 odpowiada na inne pytanie. P>0.05 w tym teście nie daje non-inferiority: szeroki CI może obejmować zarówno duże pogorszenie, jak i poprawę. Nierówność praktyczna oraz istotność statystyczna muszą być sprawdzane w tym samym kierunku. Normalność nie wynika z małej liczby bloków; kontrole leave-one-block-out i wykres wszystkich efektów służą ocenie stabilności.

## 8.7 Intersection–union: dowód reguły maksimum

H5 wymaga jednocześnie jakości i oszczędności. Zerowa hipoteza jest sumą zbiorów H0_quality ∪ H0_cost. Niech każda składowa ma prawidłowy jednostronny p-value p_Q,p_C. Odrzucenie złożonej H0 następuje, gdy oba p≤α, równoważnie max(p_Q,p_C)≤α.

**Dowód kontroli błędu.** Jeżeli H0_quality jest prawdziwa, prawdopodobieństwo odrzucenia obu jest najwyżej prawdopodobieństwo odrzucenia quality≤α. Analogicznie dla cost. Gdy obie są prawdziwe, ta sama granica pozostaje. Nie potrzeba niezależności obu p-values. Natomiast min(p_Q,p_C) potwierdzałoby tylko jeden warunek i byłoby błędne dla tezy „oba”.

## 8.8 Holm: dowód kontroli FWER

Dla m zarejestrowanych hipotez sortujemy p_(1)≤…≤p_(m), porównujemy kolejno z α/(m−j+1) i zatrzymujemy odrzucenia przy pierwszej porażce. Skorygowane p-value ma postać min[1,max_{i≤j}(m−i+1)p_(i)].

**Dowód bez wymogu niezależności.** Niech m₀ hipotez zerowych jest prawdziwych, a j oznacza pierwszy prawdziwy element w sortowaniu. Jeśli odrzucono jakąś prawdziwą H0, musiano odrzucić ten element. Ponieważ pozostało co najmniej m₀ hipotez, próg jest ≤α/m₀. Zatem wystąpiło zdarzenie min_{true}p≤α/m₀. Union bound ogranicza jego prawdopodobieństwo przez m₀(α/m₀)=α. [@holm1979]

Niewykonanych hipotez nie usuwa się z zaplanowanej rodziny w celu korzystniejszej korekty. Lokalny protokół QRC przyjmuje dla nich p=1. Korekty różnych rodzin z archiwów nie można zlać w jedną rodzinę po obejrzeniu wyników bez nowej deklaracji.

## 8.9 Bootstrap i pseudoreplikacja

Bootstrap blokowy losuje całe bloki, zachowując metody, zadania i repliki pomiarowe. Nie losuje niezależnie każdej chwili czasu, folda i seeda shots. Szereg z autokorelacją i współdzielone splity nie są iid obserwacjami.

Przy B niezależnych blokach zapisujemy wektor kontrastów d i losujemy B indeksów z powtórzeniem. W każdej replice przeliczamy tę samą średnią i ewentualną eksponentę. Percentyle 2.5% i 97.5% dają opisowy CI. Małe B i silna asymetria mogą osłabić dokładność tej procedury; nie należy uznawać jej za dokładny finite-sample test. Podstawy metody: [@efron1993].

## 8.10 Niepewność wyniku SCAR

Dla 14 poprawnych na 35 próbkach estymata accuracy wynosi 0.4. Wilson CI dla dwumianu ma środek (p̂+z²/(2N))/(1+z²/N) i półszerokość z√[p̂(1−p̂)/N+z²/(4N²)]/(1+z²/N). Przy z≈1.96 wynosi około [0.256,0.564]. To obliczenie opisowe zakłada niezależne próby o wspólnej szansie sukcesu; test Wine nie jest losową próbą całej populacji problemów. [@wilson1927]

Wykres trzech procedur pokazuje QPU 12 epok, idealny QNN 160 epok i klasyczny MLP. Różnica jakości nie izoluje jednej przyczyny. Ponadto wyniki modeli na tych samych próbkach są sparowane: formalne porównanie dwóch klasyfikatorów wymaga wyników discordant, nie tylko dwóch marginalnych accuracy.

## 8.11 Jak interpretować wykresy teorii

Krzywe kontrakcji, błędu Trottera lub progowania detektora mogą być wyliczone z wzoru. Raport oznacza je jako **model matematyczny / przykład ilustracyjny**, z podanymi parametrami, bez przedstawiania jako nowy pomiar projektu. Porównanie n=2,η=0.5 dla strat pokazuje 0.75 prawdopodobieństwa click przy loss→threshold i 0.5 przy błędnym threshold→Bernoulli. Taka ilustracja jest kontrprzykładem algebraicznym, nie walidacją całego urządzenia.
