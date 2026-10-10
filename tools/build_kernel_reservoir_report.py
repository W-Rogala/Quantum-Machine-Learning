"""Detailed comparison report: established QRC results vs proposed kernel experiments."""
from pathlib import Path
import json,html,hashlib
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY,TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/pdf';OUT.mkdir(exist_ok=True,parents=True)
DATA=ROOT/'analysis_output/kernel_reservoir_comparison';DATA.mkdir(exist_ok=True,parents=True)
C=json.loads((DATA/'mathematical_checks.json').read_text())
for name,file in [('T','times.ttf'),('TB','timesbd.ttf'),('TI','timesi.ttf'),('TBI','timesbi.ttf')]:pdfmetrics.registerFont(TTFont(name,'C:/Windows/Fonts/'+file))
pdfmetrics.registerFontFamily('T',normal='T',bold='TB',italic='TI',boldItalic='TBI')
pdfmetrics.registerFont(TTFont('Math',str(ROOT/'.venv_qml/Lib/site-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf')))
S={
 'body':ParagraphStyle('b',fontName='T',fontSize=11,leading=15,spaceAfter=9,alignment=TA_JUSTIFY),
 'head':ParagraphStyle('h',fontName='TB',fontSize=17,leading=21,spaceAfter=15,textColor=colors.HexColor('#173d51')),
 'title':ParagraphStyle('t',fontName='TB',fontSize=25,leading=30,spaceAfter=17,textColor=colors.HexColor('#173d51')),
 'sub':ParagraphStyle('s',fontName='TB',fontSize=12,leading=16,spaceBefore=8,spaceAfter=7),
 'small':ParagraphStyle('sm',fontName='T',fontSize=9,leading=12,spaceAfter=7),
 'cell':ParagraphStyle('c',fontName='T',fontSize=9,leading=12),
 'eq':ParagraphStyle('eq',fontName='T',fontSize=10.5,leading=17,spaceBefore=3,spaceAfter=11,alignment=TA_CENTER)}
story=[];source=[];table_count=0
def clean(t):
 t=t.replace('—','-').replace('–','-').replace('\u2011','-')
 for char,plain in {'₀':'0','₁':'1','₂':'2','ₜ':'t','ₐ':'a','ᵦ':'b','ⁿ':'n'}.items():
  tag='super' if char=='ⁿ' else 'sub';t=t.replace(char,f'<{tag}>{plain}</{tag}>')
 for char in ('⊗','⟨','⟩','‖','≠','≼'):t=t.replace(char,f'<font name="Math">{char}</font>')
 return t
def p(t,style='body'):
 story.append(Paragraph(clean(t),S[style]));source.append(t+'\n')
def sub(t):p(t,'sub')
def eq(t):p(t,'eq')
def page(title):story.append(PageBreak());p(title,'head')
def table(title,heads,rows,widths):
 global table_count
 table_count+=1;p(f'Tabela {table_count}. {title}','small')
 body=[[Paragraph(clean(str(v)),S['cell']) for v in row] for row in [heads]+rows]
 tb=Table(body,colWidths=widths,repeatRows=1,hAlign='LEFT')
 tb.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8f0f3')),('VALIGN',(0,0),(-1,-1),'TOP'),
 ('LINEBELOW',(0,0),(-1,0),.7,colors.HexColor('#173d51')),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#d0d8dc')),
 ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6)]))
 story.extend([tb,Spacer(1,9)]);source.append(json.dumps([heads]+rows,ensure_ascii=False)+'\n')

p('RAPORT PORÓWNAWCZY I PROJEKT BADANIA','small');story.append(Spacer(1,20))
p('Wpływ trotteryzacji na kernele kwantowe i rezerwuary kwantowe','title')
p('Geometria cech, pamięć, generalizacja i koszt pomiaru<br/>Hipotezy H1-H3 w jednym schemacie badawczym','sub')
p('7 września 2026 r. | Projekt QML | Bez VQA i VQE','small')
sub('Streszczenie')
p('Raport porównuje dwa zastosowania przybliżonej ewolucji kwantowej: budowę funkcji podobieństwa w metodach kernelowych oraz sekwencyjne przetwarzanie danych przez rezerwuar kwantowy. W pierwszym przypadku zasadniczy jest wpływ na geometrię reprezentacji; w drugim także na przenoszenie informacji między kolejnymi wejściami. Wspólnym problemem pozostaje zachowanie cech istotnych dla zadania przy ograniczonej liczbie bramek i pomiarów.')
p('Wykazano dwa pomosty: równoważność ridge w postaci pierwotnej i dualnej oraz reprezentację kernela Hilberta-Schmidta przez pełne cechy Pauliego. Jednocześnie wskazano przypadek, w którym wspólna końcowa ewolucja nie zmienia kernela nakładania stanów. Pominięcie tej niezmienniczości prowadziłoby do eksperymentu bez idealnego efektu trotteryzacji.')
p('H1 dotyczy zachowania jakości przy niższym koszcie; H2 poprawy względem dostrojonego exact; H3 mechanizmu zmiany reprezentacji. Przedstawiono rozdzielone metryki geometrii, pamięci, szumu i zasobów oraz projekt porównania przy takim samym dostępie do historii. Najbezpieczniejszą podstawą pracy magisterskiej jest H1, a główny potencjał wyjaśniający i rozwojowy ma H3.')
sub('Status materiału')
p('<b>Wykonane:</b> wcześniejsze badania QRC i bieżące małe kontrole algebraiczne. <b>Proponowane:</b> pełne porównanie predykcyjne kerneli i rezerwuarów. Raport nie przedstawia projektu eksperymentu jako uzyskanego wyniku i nie deklaruje przewagi kwantowej. Nie wykonano zadań na fizycznym QPU.','small')

page('1. Zakres porównania i wspólny język')
p('Kernel kwantowy jest funkcją podobieństwa opartą na reprezentacji kwantowej danych. Rezerwuar kwantowy jest układem dynamicznym wytwarzającym cechy z sekwencji wejść. Kategorie te nie są rozłączne: kernel można skonstruować z trajektorii rezerwuaru. Dlatego porównanie powinno oddzielać sposób tworzenia stanu od sposobu klasycznego uczenia [1-3].')
table('Dwa poziomy projektu modelu.', ['Aspekt','Kernel kwantowy','QRC'],[
 ['Dane wejściowe','Próbka x, ewentualnie jawne okno historii','Strumień uₜ i stan odziedziczony z poprzednich kroków'],
 ['Reprezentacja','ρ(x) lub mierzone cechy z(x)','ρₜ albo obserwable zₜ'],
 ['Uczenie','Kernel ridge lub SVM','Zwykle liniowy ridge; możliwy odczyt kernelowy'],
 ['Obiekt diagnostyczny','Macierz Grama i jej zgodność z zadaniem','Kanał, pamięć i macierz Grama cech'],
 ['Typowy efekt splittingu','Zmiana podobieństw','Zmiana aktualizacji i przenoszenia historii']],[88,200,205])
p('W raporcie „exact” oznacza dokładną ewolucję badanego modelu w symulatorze. Nie oznacza bezbłędnego urządzenia ani implementacji o zerowym koszcie. „Trotter” obejmuje formułę pierwszego rzędu oraz symetryczne splittingi ABA/BAB, z jawnie podaną liczbą podkroków r.')
sub('Trzy poziomy porównywalności')
p('<b>Informacyjny:</b> obie metody otrzymują te same dane dostępne do chwili prognozy. <b>Statystyczny:</b> podziały, budżet strojenia i kryteria oceny są wspólne. <b>Zasobowy:</b> liczy się cały proces pomiaru i predykcji, a nie sam koszt pojedynczego obwodu. Nie da się na ogół wyrównać wszystkich zasobów jedną liczbą; potrzebne są krzywe jakość-koszt.')
p('Skróty: N - liczba próbek treningowych, M - testowych, n - liczba kubitów, W - długość historii, G - liczba ustawień pomiaru, S - shots na ustawienie, λ - regularyzacja, τ - czas ewolucji. Litera d użyta dla wymiaru Hilberta oznacza 2ⁿ; opóźnienia pamięci oznaczamy ℓ.','small')

page('2. Modele matematyczne')
sub('2.1. Mapa cech i kernele stanowe')
eq('ρ(x)=U(x)ρ₀U(x)<super>†</super>, &nbsp; K<sub>ij</sub>=k(x<sub>i</sub>,x<sub>j</sub>).')
p('Dla czystych stanów kernel fidelity jest kwadratem modułu ich nakładania. Dla stanów mieszanych stosujemy tu kernel Hilberta-Schmidta, a nie automatycznie wierność Uhlmanna:')
eq('k<sub>HS</sub>(x,x′)=Tr[ρ(x)ρ(x′)], &nbsp; k<sub>pure</sub>(x,x′)=|⟨ψ(x)|ψ(x′)⟩|².')
p('K<sub>HS</sub> jest dodatnio półokreślony, ponieważ jest macierzą Grama operatorów w iloczynie Hilberta-Schmidta. Dla stanów mieszanych przekątna wynosi Tr(ρ²), czyli czystość, i nie musi być równa 1. Użycie innej funkcji podobieństwa wymaga osobnego uzasadnienia dodatniej półokreśloności.')
sub('2.2. Kernel projekcyjny')
eq('z<sub>j</sub>(x)=Tr[O<sub>j</sub>ρ(x)], &nbsp; k<sub>P</sub>(x,x′)=exp[-γ‖z(x)-z(x′)‖²].')
p('Jest to klasyczny kernel RBF obliczany na cechach pochodzących z pomiarów kwantowych. Wybór obserwabli określa, którą część reprezentacji wykorzystuje uczenie. Własności tej konstrukcji nie są tożsame z własnościami pełnego nakładania stanów [2].')
sub('2.3. Rezerwuar z resetowanym wejściem')
eq('ρ<sub>t+1</sub>=E<sub>uₜ</sub>(ρ<sub>t</sub>)=U[η(u<sub>t</sub>) ⊗ Tr<sub>0</sub>ρ<sub>t</sub>]U<super>†</super>.')
p('Dla obecnego modelu η(u) koduje u w pierwszym kubicie, a pozostałe kubity przechowują pamięć. H=A+B, gdzie A obejmuje pola Z i sprzężenia ZZ, a B pola X. Ponieważ reset przeplata się z ewolucją, historia wpływa na bieżący stan. Wartość kernelową można zdefiniować także między dwiema takimi historiami.')
p('Nie każda zmiana stanu jest użyteczna dla zadania, a nie każda użyteczna zmiana jest dostępna przy skończonej precyzji pomiaru. Rozróżnienie to będzie wspólne dla obu architektur.')

page('3. Trotteryzacja: kiedy efekt istnieje?')
eq('U<sub>exact</sub>(x)=exp[-iτ(A(x)+B(x))], &nbsp; δ=τ/r,')
eq('U<sub>ABA,r</sub>(x)=[exp(-iδA(x)/2) exp(-iδB(x)) exp(-iδA(x)/2)]<super>r</super>.')
p('BAB zamienia role A i B. Dla ograniczonych operatorów i ustalonego czasu, w odpowiednim reżimie małego kroku, błędy formuł pierwszego i drugiego rzędu skalują odpowiednio jak O(τ²/r) i O(τ³/r²), ze stałymi zależnymi od komutatorów. Nie są to uniwersalne oszacowania predykcji ani kosztu pomiaru. Przy dużym kroku istotna staje się struktura dynamiki, w tym rezonanse [5].')
sub('Twierdzenie 1. Wspólna końcowa unitarność')
p('Jeśli ρ<sub>r</sub>(x)=V<sub>r</sub>ρ(x)V<sub>r</sub><super>†</super> dla tego samego V<sub>r</sub> i wszystkich x, to kernel HS nie zależy od V<sub>r</sub>. Dowód wynika z cykliczności śladu oraz V<super>†</super>V=I:')
eq('Tr[Vρ(x)V<super>†</super>Vρ(x′)V<super>†</super>]=Tr[ρ(x)ρ(x′)].')
p('Zatem pojedynczy, wspólny blok Trottera dopisany na końcu kodowania nie jest poprawnym testem H2 dla idealnego pełnego kernela. Wynik zależny od r może wtedy pochodzić z szumu, przybliżonego odczytu lub błędu implementacji.')
table('Konstrukcje i możliwość zmiany idealnego kernela.', ['Konstrukcja','Kernel HS','Ograniczony kernel projekcyjny'],[
 ['Wspólne V po kodowaniu','Niezmienny','Może się zmienić'],
 ['Ewolucja zależna od x','Może się zmienić','Może się zmienić'],
 ['Kodowanie przeplatane z ewolucją','Może się zmienić','Może się zmienić'],
 ['Historia QRC z wieloma resetami','Może się zmienić przez wcześniejsze kroki','Może się zmienić']],[220,110,163])
p('W QRC wspólny ostatni blok również znosi się w pełnym nakładaniu stanów, ale nie usuwa wpływu wcześniejszych aktualizacji. Dla kernela projekcyjnego równoważna zmiana dotyczy obserwabli: O przechodzi w V<super>†</super>OV. To wyjaśnia możliwość efektu mimo niezmienności pełnego kernela.')

page('4. Pomost pierwszy: QRC jako model kernelowy')
p('Niech Z zawiera w wierszach cechy treningowe, wycentrowane i ewentualnie wystandaryzowane wyłącznie na treningu. Dla wycentrowanych celów y i funkcji celu ‖Zw-y‖²+λ‖w‖² rozwiązanie ma dwie postacie:')
eq('w=(Z<super>T</super>Z+λI)<super>-1</super>Z<super>T</super>y, &nbsp; α=(ZZ<super>T</super>+λI)<super>-1</super>y, &nbsp; w=Z<super>T</super>α.')
eq('ŷ<sub>*</sub>=z<sub>*</sub><super>T</super>w=k<sub>*</sub><super>T</super>α, &nbsp; k<sub>*</sub>=Zz<sub>*</sub>.')
sub('Konsekwencje dla eksperymentu')
p('Liniowy readout QRC i kernel liniowy tych samych cech muszą dawać tę samą predykcję z dokładnością numeryczną. Nie są konkurencyjnymi modelami uczenia. Różnica po zmianie zapisu wskazuje najpierw na niespójne skalowanie λ, centrowanie, wyraz wolny lub cechy.')
p('Jeżeli funkcja celu jest średnią błędu, a nie sumą, w macierzy pojawia się Nλ. Konwencję należy jawnie ustalić. Średnią celu dodaje się z powrotem, a cechy testowe skaluje parametrami treningu. Dotyczy to również kerneli między treningiem a testem.')
table('Co rzeczywiście zmienia model?', ['Operacja','Interpretacja'],[
 ['Ridge → liniowy kernel identycznych cech','Zmiana algorytmu obliczenia, nie hipotezy predykcyjnej'],
 ['Kernel liniowy → RBF tych samych cech','Zmiana klasycznego dekodera i jego nieliniowości'],
 ['Lokalne cechy → pełny stan','Zmiana dostępnej reprezentacji oraz kosztu pomiaru'],
 ['QRC z historią → statyczne kodowanie okna','Zmiana sposobu kodowania danych']],[240,253])
p('Najbardziej informacyjny układ porównań rozdziela więc dwa czynniki: reprezentację i dekoder. Jeśli RBF poprawi predykcję na tych samych zmierzonych cechach, poprawy nie można przypisać wyłącznie „kwantowemu kernelowi” ani nowej dynamice rezerwuaru.')
p('Porównanie na zapisanych cechach nie wymaga ponownych pomiarów QPU. Jest to najtańszy pierwszy etap weryfikacji, o ile cechy zostały faktycznie zarchiwizowane; samo archiwum agregatów NRMSE do tego nie wystarcza.')

page('5. Pomost drugi: pełny stan i cechy Pauliego')
p('Dla n kubitów, d=2ⁿ i pełnej bazy operatorów Pauliego Pₐ, unormowanej przez Tr(PₐPᵦ)=dδₐᵦ, każdy stan można rozwinąć następująco:')
eq('ρ=(I+Σ<sub>a&gt;0</sub> z<sub>a</sub>P<sub>a</sub>)/d, &nbsp; z<sub>a</sub>=Tr(P<sub>a</sub>ρ).')
eq('k<sub>HS</sub>(x,x′)=[1+z(x)<super>T</super>z(x′)]/d.')
p('Tożsamość obowiązuje również dla stanów mieszanych. Po wycentrowaniu stała znika, więc wycentrowany kernel HS jest równy liniowemu kernelowi pełnych surowych cech Pauliego, podzielonemu przez d.')
sub('Warunki równoważności predykcji')
p('Mnożenie kernela przez c wymaga przemnożenia λ przez c dla zachowania tego samego predyktora w przyjętej konwencji. Standaryzacja każdej cechy osobno na ogół zmienia kernel na ważony iloczyn cech. Dlatego istniejący ridge QRC ze standaryzacją 255 obserwabli nie jest automatycznie identyczny z nieprzeskalowanym kernelem HS.')
p('Pełny kernel nie daje z definicji bogatszej reprezentacji niż komplet tych samych oczekiwań. Różnić się może metoda jego estymacji: pomiary parami stanów lub pomiary cech. Dla dużego n pełna baza ma 4ⁿ-1 elementów, więc równoważność algebraiczna nie gwarantuje efektywności sprzętowej.')
sub('Stany mieszane: istotna pułapka implementacyjna')
p('Reset i szum prowadzą do stanów mieszanych. Standardowy obwód compute-uncompute U(x′)<super>†</super>U(x) estymuje nakładanie idealnych czystych przygotowań; nie odwraca fizycznego resetu ani kanału relaksacji. Pomiar Tr(ρσ) wymaga odpowiedniego protokołu, np. dwóch kopii i pomiaru SWAP, albo oszacowania cech. Obejmuje to dodatkowe kubity, przygotowania i błędy.')
p('Normalizacja k(x,x′)/√[k(x,x)k(x′,x′)] daje kernel o jednostkowej przekątnej, lecz zmienia geometrię przez usunięcie skali czystości. Należy traktować ją jako jawny wariant eksperymentalny. Przy szacowanych mianownikach wzrasta znaczenie błędów i korelacji pomiarowych.')

page('6. H1: zachowanie jakości przy niższym koszcie')
p('H1 powinna być testowana osobno w każdej architekturze. Porównuje jej Trottera z jej własnym exact, a nie kernel jednej rodziny z rezerwuarem innej. Dopiero potem można porównywać wrażliwość architektur na dyskretyzację.')
eq('d<sub>b</sub>=log(NRMSE<sub>T,b</sub>/NRMSE<sub>E,b</sub>), &nbsp; H₀: E[d<sub>b</sub>]≥log(1.02).')
p('Alternatywa H1: E[d]&lt;log(1.02). Próg 2% jest propozycją zachowującą wcześniejszy protokół; przed badaniem potwierdzającym należy uzasadnić jego znaczenie praktyczne. Dodatkowy warunek: koszt jest co najmniej o ustalony procent, np. 25%, niższy niż wybrana implementacja referencyjna r=16.')
table('Operacjonalizacja H1.', ['Element','Kernel','Rezerwuar'],[
 ['Referencja jakości','Exact tej samej mapy cech','Exact tego samego kanału i odczytu'],
 ['Referencja kosztu','Jawny obwód i estymator kernela','Jawny obwód i protokół replay'],
 ['Pierwotna metryka','Testowa NRMSE dla regresji','Testowa NRMSE'],
 ['Kontrola pomocnicza','Błąd macierzy Grama','Błąd stanu i profil pamięci']],[110,191,192])
sub('Dlaczego mały błąd symulacji nie wystarcza?')
p('Dla kernela HS, jeśli ‖ρ<sub>T</sub>(x)-ρ<sub>E</sub>(x)‖₁≤ε<sub>x</sub>, to z nierówności Höldera i ‖ρ‖∞≤1 otrzymujemy:')
eq('|k<sub>T</sub>(x,x′)-k<sub>E</sub>(x,x′)|≤ε<sub>x</sub>+ε<sub>x′</sub>.')
p('Jest to kontrola pojedynczej wartości, nie bezpośredni dowód nieinferiorności predykcji. Błędy całej macierzy, mała regularyzacja i geometria danych mogą wzmacniać efekt. W rezerwuarze dochodzi propagacja perturbacji przez kolejne aktualizacje. H1 musi więc być oceniona na zadaniu, wraz z kosztem.')
p('Przy skończonych shots i szumie płytki obwód może być korzystniejszy, mimo większego błędu Trottera. Nie wynika z tego, że płytszy obwód jest lepszym symulatorem dokładnego Hamiltonianu.')

page('7. H2: czy dyskretyzacja pomaga uczeniu?')
p('H2 dotyczy poprawy zadaniowej, a nie tylko tolerowania błędu. Selekcja p,r, czasu τ i parametrów odczytu musi odbywać się na walidacji. Głównym odniesieniem powinien być dostrojony exact tej samej rodziny; fixed exact pozostaje kontrolą pomocniczą.')
eq('H₀: E[log(NRMSE<sub>selected T</sub>/NRMSE<sub>tuned E</sub>)]≥log(0.98).')
p('Alternatywa oznacza poprawę o co najmniej 2%. Wersja ta jest mocniejsza od wcześniejszej H2 względem fixed exact i nie powinna dziedziczyć jej statusu statystycznego. Dla kernela projekcyjnego stroimy również γ, a dla każdej rodziny λ.')
sub('Hipotetyczne mechanizmy')
table('Mechanizmy możliwe do rozdzielenia eksperymentalnie.', ['Mechanizm','Kernel','Rezerwuar'],[
 ['Zmiana reprezentacji','Inne podobieństwa próbek','Inny rozkład informacji o historii'],
 ['Ograniczenie złożoności','Inne widmo Grama i wymiar efektywny','Mniej dostępnych cech lub inny profil pamięci'],
 ['Korzyść sprzętowa','Tańsza lub dokładniejsza estymacja','Mniej błędów podczas przetwarzania historii'],
 ['Zmiana dekodera','RBF lub dobór cech','Kernelowy zamiast liniowego readoutu']],[110,191,192])
p('Każde z tych wyjaśnień jest hipotezą, nie domyślnym skutkiem trotteryzacji. Podobnie mniejszy wymiar efektywny może pomóc przez ograniczenie wariancji albo zaszkodzić przez usunięcie sygnału. Wysokie dopasowanie do etykiet treningowych nie dowodzi lepszej generalizacji.')
sub('Kontrole przeciwko pozornej poprawie')
p('Należy porównać oba porządki Stranga, równe shots i równy limit zasobów, ten sam dekoder oraz dekodery alternatywne na tych samych cechach. Wspólna liczba konfiguracji jest pomocna, ale nie wyrównuje automatycznie kosztu strojenia. Silne odniesienia klasyczne obejmują ridge opóźnień, kernel RBF na identycznym oknie oraz klasyczny rezerwuar.')
p('Nawet potwierdzenie H2 nie dowodzi przewagi kwantowej. Potrzebne byłyby dodatkowe wyniki dotyczące kosztu klasycznych alternatyw, skalowania, danych oraz modelu dostępu do nich.')

page('8. H3: geometria oraz pamięć jako dwa mechanizmy')
p('Pierwotna H3 QRC mierzyła zmianę profilu pamięci. Kernel statyczny nie ma takiego samego mechanizmu stanu, ale może kodować jawne opóźnienia. Wprowadzamy więc H3-R i H3-K, połączone diagnostyką cech, a nie jedną wymienną liczbą.')
table('Metryki mechanistyczne.', ['Obszar','Metryka','Interpretacja i zastrzeżenie'],[
 ['H3-R','C<sub>L</sub>(ℓ), C<sub>prod</sub>(ℓ), C<sub>quad</sub>(ℓ)','Osobne profile; ujemna estymata nie jest ujemną informacją'],
 ['H3-R','Odległość śladowa par historii','Ślad konkretnej perturbacji, nie uniwersalny certyfikat pamięci'],
 ['H3-K','Widmo wycentrowanego Grama','Geometria skończonego zbioru danych'],
 ['H3-K','Wymiar efektywny i alignment','Zależne od λ, centrowania i danych'],
 ['Wspólne','Zmiana predykcji po zmianie odczytu','Rozdziela stan od dostępnego dekodera']],[75,175,243])
eq('J=I-11<super>T</super>/N, &nbsp; K<sub>c</sub>=JKJ, &nbsp; d<sub>eff</sub>(λ)=Tr[K<sub>c</sub>(K<sub>c</sub>+λI)<super>-1</super>].')
eq('A(K,y)=⟨K<sub>c</sub>,y<sub>c</sub>y<sub>c</sub><super>T</super>⟩<sub>F</sub> / (‖K<sub>c</sub>‖<sub>F</sub>‖y<sub>c</sub>y<sub>c</sub><super>T</super>‖<sub>F</sub>).')
p('Dla zerowego mianownika alignment jest niezdefiniowany i należy raportować NA. Do selekcji nie wolno używać etykiet testowych. Większy d<sub>eff</sub> ani alignment nie stanowią samodzielnego sukcesu. Pierwotną metrykę H3-K i kierunek testu trzeba wybrać przed replikacją, zamiast wybierać korzystny wskaźnik po wynikach.')
p('Dla obu reprezentacji można dodatkowo przeprowadzić zadania rekonstrukcji przeszłych wejść przy tym samym liniowym dekoderze [7]. W statycznym modelu jest to test zachowania jawnie dostarczonej historii, a nie dowód pamięci dynamicznej. Profil otrzymany z RBF trzeba oznaczyć osobno: nieliniowość może pochodzić z dekodera.')
p('Zależność profilu lub geometrii od NRMSE jest początkowo korelacją. Mocniejsze wyjaśnienie wymaga interwencji: zmiany splittingu przy stałym kodowaniu, zmiany obserwabli na tych samych stanach i zmiany dekodera na tych samych cechach.')

page('8.1. Propagacja błędu: istotna różnica modeli')
sub('Kernel ridge: perturbacja macierzy i regularyzacja')
p('Załóżmy, że K i K̂=K+ΔK są symetryczne, dodatnio półokreślone, a λ&gt;0. Dla zgodnie wycentrowanych danych α=(K+λI)<super>-1</super>y. Tożsamość resolwent daje:')
eq('α̂-α=-(K̂+λI)<super>-1</super>ΔK(K+λI)<super>-1</super>y,')
eq('‖α̂-α‖₂ ≤ ‖ΔK‖₂ ‖y‖₂ / λ².')
p('Jeżeli wektor podobieństw nowej próbki zmienia się o δk, to konserwatywne oszacowanie predykcji wynosi:')
eq('|ŷ̂-ŷ| ≤ ‖δk‖₂ ‖y‖₂/λ + ‖k‖₂ ‖ΔK‖₂ ‖y‖₂/λ².')
p('Dowód korzysta z ‖(K+λI)<super>-1</super>‖₂≤1/λ oraz rozkładu różnicy na błąd wektora testowego i współczynników. Oszacowanie jest pesymistyczne, ale pokazuje rolę regularyzacji. Nie obowiązuje bez zmian, gdy szacowany K jest nie-PSD. Przy definicji funkcji celu jako średniej należy konsekwentnie zastąpić λ przez Nλ.')
sub('Rezerwuar: perturbacja aktualizacji przez historię')
p('Niech maksymalna różnica kanałów na stanach w normie śladowej wynosi ε, jednostajnie względem wejścia. Dla eₜ=‖ρ̂ₜ-ρₜ‖₁ kontraktywność CPTP daje e<sub>t+1</sub>≤eₜ+ε. Przy jednakowym stanie początkowym otrzymujemy eₜ≤min(2,tε).')
p('Jeżeli dodatkowo kanał dokładny ma jednolity współczynnik kontrakcji q&lt;1 na rozważanym zbiorze stanów i wejść, to:')
eq('e<sub>t+1</sub>≤q eₜ+ε, &nbsp; eₜ≤q<super>t</super>e₀+ε(1-q<super>t</super>)/(1-q).')
p('Warunek q&lt;1 jest założeniem tego oszacowania, a nie ustaloną własnością obecnego QRC. Reset jednego kubitu nie daje automatycznie ścisłej kontrakcji w jednym kroku. W praktyce potrzebna może być kontrola bloków wielu aktualizacji. Sam promień widma dla jednego zamrożonego wejścia nie wystarcza.')
p('Dla kernela z trajektorii QRC występują oba mechanizmy naraz: błąd reprezentacji historii, a następnie jego wpływ na Gram i regresję. To uzasadnia mierzenie oddzielnie dynamiki, cech, macierzy kernela i końcowej predykcji.')

page('9. Szum: podobne źródła, różne skutki')
p('Badanie powinno rozdzielić szum fizycznego kanału, skończoną liczbę pomiarów, błędy odczytu i zmianę kalibracji. Jedna skalarna „siła szumu” nie wystarcza do ustalenia mechanizmu. Dotychczasowe parametry mild/stress QRC mogą służyć pilotażowi, ale nie zastępują kalibracji urządzenia.')
table('Skutki i kontrole.', ['Źródło','Kernel','Rezerwuar'],[
 ['Depolaryzacja / T1 / T2','Zmiana podobieństw, czystości i skali sygnału','Zmiana pamięci, stanu stałego i szybkości zanikania'],
 ['Błąd koherentny','Zmiana mapy cech','Zmiana mapy i przesunięcie rezonansu'],
 ['Skończone shots','Błąd Grama lub wektorów cech','Błąd odczytu historii'],
 ['Błąd resetu','Istotny przy przygotowaniach mieszanych / sekwencyjnych','Bezpośredni element aktualizacji'],
 ['Drift','Niespójność podobieństw między seriami','Niedopasowanie readoutu do nowej dynamiki']],[110,191,192])
sub('Dodatnia półokreśloność i spójność pomiaru')
p('Dla deterministycznie przypisanych zaszumionych stanów ρ(x) kernel HS nadal jest PSD. Jednak niezależnie estymowane elementy Grama mogą tworzyć macierz nie-PSD. Ponadto zaszumiony obwód porównujący pary nie musi realizować dokładnie iloczynu Hilberta-Schmidta jednej wspólnej mapy cech.')
p('Jeśli każdą próbkę mierzymy raz i przechowujemy wektor cech ẑ(x), kernel liniowy ẐẐ<super>T</super> oraz RBF tych wektorów pozostają PSD. Należy używać tych samych zapisanych cech we wszystkich parach. Ich błędy są skorelowane pomiędzy wpisami Grama. Niezależne losowanie szumu dla każdej pary modeluje inny protokół.')
p('Ewentualną naprawę PSD należy zdefiniować z góry wraz ze zgodnym sposobem tworzenia podobieństw testowych. Samo obcięcie ujemnych wartości własnych treningowego K nie wyznacza kompletnej mapy dla nowych danych. Raportujemy skalę korekty i jej koszt, bez doboru do wyników testu.')
p('Koncentracja wartości kernela może utrudniać estymację przy rosnącym n, ale zależy od konkretnej mapy i rodzaju pomiaru [4]. Nie należy przenosić tego wyniku automatycznie na każdy kernel projekcyjny lub każdy QRC.')

page('10. Koszty pomiaru, treningu i predykcji')
p('Porównanie wymaga dwóch osobnych budżetów: zasobów kwantowych i obliczeń klasycznych. Przyjmijmy P(W) jako koszt przygotowania stanu z historii długości W, wyrażony np. w liczbie CX, wraz z odrębnym czasem resetów i pomiarów.')
table('Koszt bez przyspieszeń strukturalnych i aproksymacji niskiego rzędu.', ['Metoda','Część kwantowa','Część klasyczna'],[
 ['Kernel mierzony parami','O((N²+NM) S P(W)); protokół może wymagać dwóch kopii','Pamięć O(N²); gęste rozwiązanie zwykle O(N³)'],
 ['Kernel z m cech','O((N+M) G S P(W))','Utworzenie Grama O(N²m); solver zależny od postaci'],
 ['QRC + liniowy ridge','Taki sam koszt cech przy identycznym replay','Postać pierwotna O(Nm²+m³); predykcja O(m)'],
 ['QRC + RBF cech','Bez nowych pomiarów, jeśli cechy są zapisane','Koszt kernela i rozwiązania dualnego']],[110,200,183])
p('To orientacyjne złożoności dla implementacji gęstych. Nyström, losowe cechy, solvery iteracyjne i struktura danych mogą zmienić koszty. Należy uwzględnić te same klasy przyspieszeń po obu stronach. Porównanie czasu dwóch naiwnych implementacji nie jest dowodem przewagi algorytmicznej.')
sub('Historia i pomiar destrukcyjny')
p('Propagowanie macierzy gęstości w symulatorze pozwala odczytywać oczekiwania bez niszczenia stanu. Fizyczny pomiar nie daje tej możliwości za darmo. Dla replay pełnych prefiksów koszt historii sumuje się jak Σ<sub>t=1..L</sub>t=O(L²). Okno W ogranicza go do O(LW), ale zmienia reprezentację. Protokół pomiarów słabych wymaga jawnego modelu back-action [6].')
p('Dla pełnego odczytu n=4 mamy 255 cech i w użytym schemacie 81 ustawień, wobec dwóch dla lokalnych X/Z/ZZ. Ta różnica tłumaczy, dlaczego porównanie przy równych shots na ustawienie i przy równym całkowitym koszcie odpowiada na dwa różne pytania.')
p('Raport końcowy powinien zawierać: CX × shots, liczbę przygotowań, resetów i pomiarów, liczbę kubitów, czas urządzenia, koszt klasycznego treningu oraz koszt jednej nowej predykcji. Osobno wykazujemy koszt poszukiwania hiperparametrów.')

page('11. Wspólny protokół eksperymentalny')
p('Poniższy protokół jest propozycją do zamrożenia przed nowymi danymi. Jego celem jest porównanie sposobów reprezentowania identycznej historii i oddzielenie wpływu dekodera.')
table('Ramiona badania.', ['Ramię','Reprezentacja','Dekoder / funkcja kontrolna'],[
 ['K-S','Czysty stan kodujący jawne okno, ewolucja zależna od danych','HS/fidelity + kernel ridge'],
 ['R-L','QRC odtwarzany z tego samego okna W','Liniowy ridge'],
 ['R-Klin','Dokładnie te same cechy co R-L','Liniowy kernel; kontrola równoważności'],
 ['R-Krbf','Dokładnie te same cechy co R-L','RBF; efekt zmiany dekodera'],
 ['R-HS','Stan QRC, zwykle mieszany','HS; diagnostyka pełnego stanu'],
 ['C','To samo jawne okno wejść','Ridge, klasyczny RBF, klasyczny rezerwuar']],[65,225,203])
p('Dla porównania informacyjnego rezerwuar okienkowy jest za każdym razem inicjalizowany w tym samym stanie i przetwarza dokładnie W wejść. Ciągły QRC z pełną historią stanowi osobne ramię rozszerzone. Nie wolno przypisywać przewagi architektury samemu dostępowi do dłuższej przeszłości.')
p('Konkretny wariant K-S: czysty stan otrzymany z |0...0⟩ przez W bloków exp[-iτH(uₛ)], z H(u)=A(u)+B oraz zależnym od u polem Z. Alternatywa przeplata R<sub>y</sub>(θ(uₛ)) z tym samym U, bez resetów. Należy wybrać jeden wariant przed eksperymentem; nie mieszać ich wyników pod wspólną nazwą kernela.','small')
sub('Macierz pilotażu')
p('Proponowane n=4; W=8,16,32; τ=0.8 i 3.2; exact, ABA/BAB z r=1,2,4,8. Rezonans τ≈π/g jest kontrolą QRC; w kodowaniu zależnym od x nie musi istnieć jeden wspólny rezonans. Replikacje n=3 i n=5 oraz większe liczby kubitów uruchamiamy po ustaleniu mechanizmu, bez deklarowania skalowania na podstawie n=4.')
p('Zadania podstawowe: NARMA10, MG z horyzontem 5 i diagnostyczne rekonstrukcje opóźnień na iid. Każde ramię używa identycznych celów i informacji dostępnej do chwili t. Pilotaż idealny poprzedza shots-only, szum kanału i scenariusz dryfu. Nie ma potrzeby wykonywać całego ogromnego iloczynu konfiguracji na QPU.')
p('Selektory korzystają wyłącznie z treningu i walidacji. Skalowanie wejść i cech dopasowujemy na treningu. Dla okien stosujemy konserwatywne luki uwzględniające W i horyzont; żadna cecha nie może zawierać przyszłej obserwacji. Długość washout ustalamy lub kontrolujemy osobno.')

page('12. Statystyka i przypadki krytyczne')
p('Jednostką niezależną jest blok obejmujący losowanie danych, pól i pomiarów. Te same bloki służą sparowanym porównaniom architektur. Powtórzenia pomiarów są zagnieżdżone w bloku; nie zwiększają sztucznie liczby niezależnych prób. Liczbę bloków należy wyznaczyć dla zakładanego efektu i jego wariancji.')
sub('Testy i porównanie wrażliwości architektur')
p('H1 i H2 testujemy na logarytmach ilorazów błędu. Dla porównania samego wpływu trotteryzacji można użyć interakcji:')
eq('I<sub>b</sub>=log(E<sub>T,K,b</sub>/E<sub>E,K,b</sub>)-log(E<sub>T,R,b</sub>/E<sub>E,R,b</sub>).')
p('I&lt;0 oznacza korzystniejszy względny efekt w rodzinie kernelowej, niekoniecznie mniejszy bezwzględny błąd kernela. Porównanie ma sens przy ustalonych ramionach i dekoderach. Należy raportować jednocześnie oba błędy bezwzględne i ich ilorazy.')
p('Dla wybranych celów pierwotnych stosujemy z góry ustaloną rodzinę korekt, np. Holma. Przedziały bootstrap po blokach i usuwanie pojedynczego bloku stanowią kontrole wrażliwości. H3 ma osobny zestaw metryk mechanistycznych; nie wybieramy po fakcie tej, która daje najmniejszą p-wartość.')
table('Obowiązkowe kontrole matematyczne i implementacyjne.', ['Przypadek','Oczekiwany wynik'],[
 ['[A,B]=0 lub τ→0','Zgodność splittingu z exact w odpowiedniej granicy'],
 ['Wspólna końcowa unitarność','Niezmienność HS; dopuszczalna zmiana projekcji'],
 ['R-L wobec R-Klin','Zgodne predykcje przy zgodnej regularyzacji'],
 ['Pełne surowe cechy Pauliego','Tożsamość z HS po skali i składniku stałym'],
 ['J=0','Usunięcie zerowych bramek ze statystyki kosztu'],
 ['Macierz niemal stała / diagonalna','Jawna kontrola koncentracji, regularyzacji i baseline']],[225,268])
p('Szczególnie ważna jest kontrola dodatniości Grama, spójnego kernela trening-test, zachowania śladu i dodatniości stanów oraz zgodności kolejności bitów. Brak oczekiwanej kontroli zerowej powinien zatrzymać interpretację wyników predykcyjnych.')

page('13. Co już wiemy, a czego jeszcze nie?')
p('Wcześniejszy audyt projektu objął H1-H3 dla QRC, modele CV oraz syntetyczny szum. Wyniki te są uzasadnieniem pytań badawczych, nie porównaniem z kernelami. W tej części nie dokonuje się ekstrapolacji przewagi między architekturami.')
table('Wybrane wyniki istniejącego projektu QRC.', ['Wynik','Liczby','Znaczenie'],[
 ['H1, standard','Iloraz 0.986; 95% CI [0.941; 1.033]','Nieinferiorność 2% nierozstrzygnięta'],
 ['Trotter / tuned exact, nowe bloki','1.002; [0.911; 1.103]','Brak dowodu przewagi'],
 ['BAB2, τ=3.2, idealny odczyt','L20 około 2.94 lokalnie i 9.25 dla pełnego odczytu','Sygnał zależny od dostępnych cech'],
 ['ABA2 / ABA16, mild, równy koszt','NARMA: 0.921; MG5: 0.723','Korzyść płytkiego obwodu w tym modelu szumu']],[175,160,158])
p('H3 wykazała, że dodatnia zmiana różnicy pamięci nieliniowej i liniowej może wynikać z utraty obu składowych. Nowa seria szumowa pokazała kruchość idealnego pełnego odczytu BAB. Nie wiadomo jeszcze, czy kernel RBF na tych samych zaszumionych cechach odzyska użyteczność ani czy statyczny kernel okna zachowa się lepiej.')
sub('Bieżące kontrole algebraiczne - wykonane')
p(f"Na modelu dwóch kubitów i ustalonym ziarnie maksymalny błąd niezmienniczości HS wyniósł {C['common_unitary_HS_max_error']:.2e}, a różnica predykcji ridge w postaci pierwotnej i dualnej {C['primal_dual_prediction_max_error']:.2e}. Tożsamość pełnych cech Pauliego potwierdzono dla stanów czystych i mieszanych z błędem nie większym niż {max(C['pauli_identity_pure_max_error'],C['pauli_identity_mixed_max_error']):.2e}.")
p(f"Dla przykładowego H(x) względna różnica Grama względem exact wyniosła {C['data_dependent_encoding_relative_gram_error_r1']:.3g} przy r=1 oraz {C['data_dependent_encoding_relative_gram_error_r8']:.3g} przy r=8. Pokazuje to, że odpowiednio skonstruowany eksperyment może mieć niezerowy efekt splittingu. Nie oceniano tutaj generalizacji ani kosztu na QPU.")
p('Kontrole zapisano w analysis_output/kernel_reservoir_comparison/mathematical_checks.json. Dotychczasowe wyniki QRC pochodzą z danych lokalnych wymienionych w bibliografii materiałów projektu.','small')

page('14. Wniosek badawczy i rozwój tematu')
p('<b>Rekomendacja:</b> badać wspólnie reprezentację, dekoder i pomiar, lecz zmieniać je w kontrolowanych ramionach. Podstawowym pytaniem nie jest „czy kernel jest lepszy od rezerwuaru?”, ponieważ kernel może być odczytem rezerwuaru. Precyzyjne pytanie brzmi: która konstrukcja reprezentacji historii zachowuje użyteczne podobieństwa przy danym budżecie?')
sub('Zakres magisterski')
p('Rdzeń pracy: n=4, jeden model Hamiltonianowy, dwa zadania czasowe, exact i dwa porządki Stranga, lokalny odczyt oraz kernel liniowy/RBF tych samych cech. Dodać statyczną mapę zależną od danych jako ramię porównawcze, po kontroli niezmienniczości. H1 jest celem minimalnym; H3 dostarcza mechanizmu. H2 pozostaje ambitnym, falsyfikowalnym wynikiem dodatkowym.')
p('Pełny HS stanów QRC warto zachować jako diagnostykę małego układu. Nie należy budować planu sprzętowego na założeniu, że pełna tomografia lub porównywanie wszystkich par będzie tanie. W pierwszym etapie najwięcej informacji daje zmiana dekodera na tych samych cechach, przy zachowaniu dokładnej kontroli zasobów.')
sub('Rozwinięcie doktorskie')
p('Pierwsza ścieżka: budżetowo optymalny dobór obserwabli i przydział shots, z kontrolą błędu kernela i predykcji. Druga: warunki stabilności i zbieżności kerneli definiowanych przez kanały sekwencyjne. Trzecia: zależności pomiędzy kontrakcją kanału, geometrią Grama i pamięcią dostępną dla konkretnego zadania. Każda wymaga silnych odniesień klasycznych i badania skalowania.')
sub('Proponowany tytuł')
p('„Trotteryzacja kwantowych reprezentacji danych czasowych: porównanie geometrii kerneli, pamięci rezerwuarów i kosztu pomiaru”.','sub')
p('Twierdzenie publikacyjne powinno dotyczyć ustalonego, powtarzalnego mechanizmu lub reguły doboru zasobów. Wynik negatywny H2 może być wartościowy, jeśli wyjaśnia niezmienniczość kernela, kruchość odczytu albo brak przewagi nad odpowiednio dostrojonym odniesieniem.')
p('Raport nie dowodzi przewagi kwantowej, nie rozszerza wyników n=4 na skalę asymptotyczną i nie utożsamia ciągłego zbioru stanów z ciągłym widmem operatora. W modelu kubitowym widma Hamiltonianu i kanału są skończone; układy CV wymagają odrębnych założeń i kontroli truncacji.')

page('Bibliografia i materiały odtwarzalne')
refs=[
 ('1','V. Havlíček i in., Supervised learning with quantum-enhanced feature spaces, Nature 567, 209-212 (2019).','https://arxiv.org/abs/1804.11326'),
 ('2','H.-Y. Huang i in., Power of data in quantum machine learning, Nature Communications 12, 2631 (2021).','https://www.nature.com/articles/s41467-021-22539-9'),
 ('3','K. Fujii, K. Nakajima, Harnessing Disordered-Ensemble Quantum Dynamics for Machine Learning, Physical Review Applied 8, 024030 (2017).','https://arxiv.org/abs/1602.08159'),
 ('4','S. Thanasilp, S. Wang, M. Cerezo, Z. Holmes, Exponential concentration in quantum kernel methods, Nature Communications 15, 5200 (2024).','https://arxiv.org/abs/2208.11060'),
 ('5','M. Heyl, P. Hauke, P. Zoller, Quantum localization bounds Trotter errors in digital quantum simulation, Science Advances 5, eaau8342 (2019).','https://arxiv.org/abs/1806.11123'),
 ('6','P. Mujal i in., Time-series quantum reservoir computing with weak and projective measurements, npj Quantum Information 9, 16 (2023).','https://arxiv.org/abs/2205.06809'),
 ('7','J. Dambre, D. Verstraeten, B. Schrauwen, S. Massar, Information Processing Capacity of Dynamical Systems, Scientific Reports 2, 514 (2012).','https://www.nature.com/articles/srep00514')]
for num,title,url in refs:p(f'[{num}] {html.escape(title)}<br/><link href="{url}" color="#174f70">{url}</link>','small')
sub('Dane projektu i kontrola pochodzenia')
p('D1: analysis_output/qrc_spectral_h1_h2/ - H1/H2, odniesienia exact i modele klasyczne.<br/>D2: analysis_output/qrc_h3_memory/ - profile, kanały i odczyty.<br/>D3: analysis_output/qrc_h3_noise/ - koszty i syntetyczny szum.<br/>D4: analysis_output/qrc_independent_audit/ - odrębne przeliczenia audytowe.<br/>D5: analysis_output/kernel_reservoir_comparison/ - bieżące kontrole algebraiczne i manifest raportu.','small')
p('Ścieżki odnoszą się do D:/Projects/QML. Pełny wcześniejszy audyt: output/pdf/Audyt_QRC_H1_H3_szum_2026-09-07.pdf. Niniejszy dokument jest rozwinięciem porównania, nie ponownym audytem wszystkich eksperymentów.','small')
sub('Odtworzenie')
p('.venv_qml/Scripts/python.exe tools/check_kernel_reservoir_comparison.py<br/>python tools/build_kernel_reservoir_report.py<br/>Skład wymaga reportlab, pypdf i użytych czcionek. Kontrole wykorzystują NumPy i SciPy. Zapisane ziarno: 20260907.','small')
p('Źródła wspierają definicje i kontekst; dowody tożsamości w raporcie przedstawiono jawnie. Nie jest to systematyczny przegląd całej literatury do września 2026 ani ustalenie pierwszeństwa proponowanego tematu. Przed zgłoszeniem publikacji potrzebny jest osobny przegląd nowości.','small')

def footer(c,d):
 c.saveState();w,h=A4;c.setFont('T',8);c.setFillColor(colors.HexColor('#657985'))
 if d.page>1:c.drawString(51,h-32,'Trotteryzacja | Kernele kwantowe i rezerwuary')
 c.setStrokeColor(colors.HexColor('#ced8dd'));c.line(51,41,w-51,41)
 c.drawString(51,28,'7 września 2026 | Wyniki QRC i projekt porównania kernelowego');c.drawRightString(w-51,28,str(d.page));c.restoreState()
pdf=OUT/'Trotteryzacja_kernele_i_rezerwuary_raport_2026-09-07.pdf'
doc=SimpleDocTemplate(str(pdf),pagesize=A4,leftMargin=51,rightMargin=51,topMargin=55,bottomMargin=55,
 title='Trotteryzacja: porównanie kerneli i rezerwuarów kwantowych',author='Projekt QML - opracowanie przy wsparciu Codex')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
r=PdfReader(pdf);txt='\n'.join(p.extract_text() for p in r.pages)
assert len(r.pages)==17, f'Unexpected pages: {len(r.pages)}'
(DATA/'report_source.txt').write_text('\n'.join(source),encoding='utf-8')
(DATA/'pdf_text.txt').write_text(txt,encoding='utf-8')
paths=[pdf,Path(__file__),ROOT/'tools/check_kernel_reservoir_comparison.py',DATA/'mathematical_checks.json',ROOT/'analysis_output/qrc_independent_audit/audit.json']
(DATA/'manifest.json').write_text(json.dumps({'pages':len(r.pages),'status':'comparison report; no new predictive kernel benchmark','sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}},indent=2),encoding='utf-8')
print(f'Created {pdf}; {len(r.pages)} pages; {len(txt)} extracted characters')
