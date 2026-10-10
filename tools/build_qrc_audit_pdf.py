"""Academic Polish audit report, composed from verified audit.json and source CSVs."""
from pathlib import Path
import json,csv,html
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,Image,KeepTogether
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY,TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/pdf';OUT.mkdir(parents=True,exist_ok=True)
A=json.loads((ROOT/'analysis_output/qrc_independent_audit/audit.json').read_text())
for family,file in [('T','times.ttf'),('TB','timesbd.ttf'),('TI','timesi.ttf'),('TBI','timesbi.ttf')]:pdfmetrics.registerFont(TTFont(family,'C:/Windows/Fonts/'+file))
pdfmetrics.registerFont(TTFont('Math',str(ROOT/'.venv_qml/Lib/site-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf')))
pdfmetrics.registerFontFamily('T',normal='T',bold='TB',italic='TI',boldItalic='TBI')
S=getSampleStyleSheet()
S.add(ParagraphStyle(name='BodyPL',fontName='T',fontSize=11,leading=15,spaceAfter=9,alignment=TA_JUSTIFY))
S.add(ParagraphStyle(name='HeadingPL',fontName='TB',fontSize=17,leading=21,spaceAfter=16,textColor=colors.HexColor('#15364b')))
S.add(ParagraphStyle(name='SubPL',fontName='TB',fontSize=12,leading=16,spaceBefore=9,spaceAfter=7))
S.add(ParagraphStyle(name='SmallPL',fontName='T',fontSize=9,leading=12,spaceAfter=7))
S.add(ParagraphStyle(name='CellPL',fontName='T',fontSize=9,leading=12))
S.add(ParagraphStyle(name='TitlePL',fontName='TB',fontSize=25,leading=30,spaceAfter=20,textColor=colors.HexColor('#15364b')))
S.add(ParagraphStyle(name='EquationPL',fontName='T',fontSize=11,leading=17,alignment=TA_CENTER,spaceBefore=4,spaceAfter=12))
story=[]
table_titles=['Materiał objęty audytem. Źródła: D1-D3.',
 'Wybrane ilorazy błędu wobec ustalonego exact. Źródło: D1; przeliczenie D4.',
 'Kontrola odniesień na nowych blokach. Źródło: D1; przeliczenie D4.',
 'Kontrasty H3 z zachowaną definicją T. Źródło: D2; przeliczenie D4.',
 'Parametry syntetycznego szumu. Źródło: D3.',
 'Obserwable i liczba ustawień pomiaru. Źródło: D3.',
 'Suma liniowych pojemności przy różnych warunkach odczytu. Źródła: D3-D4.',
 'ABA2 / ABA16: ilorazy NRMSE w modelu mild. Źródła: D3-D4.',
 'Odległość śladowa w rezonansie i jego otoczeniu. Źródło: D3.',
 'Wrażliwość wybranych ilorazów na resampling bloków. Źródło: D4.',
 'Synteza oceny audytowej i zalecanych działań.']
table_number=0
def para(text,style='BodyPL'):
    text=text.replace('—','-').replace('–','-').replace('\u2011','-')
    for symbol,replacement in [('〈','⟨'),('〉','⟩'),('⊗','⊗')]:text=text.replace(symbol,f'<font name="Math">{replacement}</font>')
    story.append(Paragraph(text,S[style]))
def head(text):para(text,'HeadingPL')
def sub(text):para(text,'SubPL')
def page(title):story.append(PageBreak());head(title)
def table(headers,rows,widths=None):
    global table_number
    table_number+=1
    para(f'Tabela {table_number}. '+table_titles[table_number-1],'SmallPL')
    body=[[Paragraph(str(v).replace('—','-').replace('–','-'),S['CellPL']) for v in row] for row in [headers]+rows]
    obj=Table(body,colWidths=widths,repeatRows=1,hAlign='LEFT')
    obj.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e6eef2')),
        ('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.7,colors.HexColor('#15364b')),
        ('LINEBELOW',(0,1),(-1,-1),.25,colors.HexColor('#cbd5dc')),
        ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
        ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6)]))
    story.extend([obj,Spacer(1,11)])
def fmt(x):return f'{x:.3f}'
def interval(r):return f"[{r['t_low']:.3f}; {r['t_high']:.3f}]"
def local_csv(folder,name):
    with (ROOT/'analysis_output'/folder/name).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))

para('RAPORT BADAWCZY I AUDYT METODOLOGICZNY','SmallPL')
story.append(Spacer(1,20))
para('Trotteryzacja rezerwuarów kwantowych: pamięć, odczyt i odporność na szum','TitlePL')
para('Odrębna weryfikacja dotychczasowych wyników H1-H3<br/>Stan projektu: 7 września 2026 r.','SubPL')
para('Projekt pracy magisterskiej z perspektywą rozwoju doktorskiego. Zakres: QRC z klasycznie uczonym odczytem liniowym, bez VQA i VQE.','BodyPL')
sub('Streszczenie')
para('Celem audytu była ocena poprawności obliczeń i siły wniosków dotyczących zadaniowo użytecznej trotteryzacji. Przeliczono agregaty zapisanych danych, sprawdzono spójność plików, przeprowadzono odrębne kontrole macierzowej dynamiki oraz analizę wrażliwości statystycznej. Uwzględniono modele kubitowe, gaussowskie CV i nowe eksperymenty z syntetycznymi błędami bramek, resetu, odczytu i dryfem kalibracji.')
para('<b>Wniosek główny:</b> dostępne wyniki wspierają badanie zależności między dyskretyzacją, strukturą kanału i kosztem odczytu. Nie potwierdzają ogólnej przewagi Trottera nad dostrojonym exact ani przewagi kwantowej. Silna pamięć BAB przy idealnym pełnym odczycie jest krucha pomiarowo. Przy przyjętym szumie płytszy ABA r=2 daje natomiast lepszą predykcję niż ABA r=16.')
para('<b>Status dowodów:</b> eksploracyjny. Liczba bloków wynosi zwykle osiem; siatki konfiguracji, odczyty i regularyzacja rozwijały się w toku badań. Potrzebna jest nowa, zamrożona replikacja przed formułowaniem wniosków potwierdzających.')
sub('Zakres niezależności audytu')
para('Audyt wykorzystuje osobny skrypt przeliczeniowy i odrębne kontrole algebraiczne. Został wykonany przez tego samego asystenta w innym przebiegu analitycznym; nie jest recenzją zewnętrznego eksperta ani pełną niezależną reimplementacją wszystkich eksperymentów. Nie wykonano zadań na fizycznym QPU.','SmallPL')
para('Słowa kluczowe: quantum reservoir computing; Suzuki-Trotter; pamięć opóźniona; kanały kwantowe; skończone pomiary; audyt reprodukowalności.','SmallPL')

page('1. Materiał badawczy i procedura audytu')
para('Punktem odniesienia były dane CSV, manifesty, skrypty symulacyjne i raporty projektu, a nie same wcześniejsze interpretacje. Bibliografia [1-6] dostarcza kontekstu definicji i modeli; nie zastępuje weryfikacji danych własnych.')
table(['Pakiet','Materiał','Jednostka niezależna'],[
 ['H1/H2','864 oceny kubitowe; 720 ocen CV; 24 testy cutoff; kontrola dostrojonego exact','8 bloków, następnie 8 nowych'],
 ['H3 idealne','70 740 składowych profili; 393 diagnostyki kanału; 432 oceny odczytu predykcyjnego','8 bloków głównych; 4 skanu'],
 ['H3 z szumem','2592 agregaty; 51 840 składowych; ablacje i zmiana kalibracji','8 nowych bloków 500-507']],[70,298,125])
sub('Wykonane sprawdzenia')
para('Ponownie obliczono ilorazy NRMSE H1/H2, kontrasty H3 i wybrane porównania zaszumionych obwodów. Zastosowano przedziały t, bootstrap bloków (20 000 losowań), usuwanie pojedynczego bloku oraz dokładny test znaków. Dla 864 rekordów kosztowych sprawdzono rachunek CX × shots i zaokrąglenie budżetu.')
para(f"Odrębna konstrukcja Hamiltonianu i śladu częściowego zgodziła się z implementacją dla exact, ABA i BAB z maksymalną różnicą {A['independent_dense_max_error']:.2e}. Kontrole te używały nowego ziarna pól i 30-elementowej historii. Nie są pełną replikacją wszystkich dopasowań readoutu.")
para(f"Zweryfikowano {len(A['integrity'])} wpisów sum kontrolnych. Liczba rozbieżności po interpretacji nazw-aliasów manifestu: {len(A['integrity_failures'])}. Zestaw 25 testów QRC, odczytu i adaptera sprzętowego przeszedł. Sama zgodność hashy dowodzi spójności zapisu, nie prawdziwości modelu.")
sub('Ograniczenia odtwarzalności')
para('Archiwum nie zawiera wszystkich pojedynczych wyników pomiarów ani wszystkich testowych predykcji. Możliwe jest przeliczenie agregatów i ponowne uruchomienie deterministycznie zasianych symulacji, lecz nie niezależna rekonstrukcja każdej NRMSE wyłącznie z zapisanych predykcji. Wskazane jest zamrożenie wersji kodu, zależności i surowych wyników dla kolejnej serii.')

page('2. Model matematyczny i interpretacja widma')
para('Badany rezerwuar zawiera cztery kubity. Pierwszy koduje wejście; trzy pozostałe przechowują pamięć. Dla pierścienia oddziaływań przyjęto H=A+B, gdzie A jest diagonalny w bazie Z, a B zawiera lokalne pola poprzeczne:')
para('A = Σ<sub>i</sub> h<sub>i</sub>Z<sub>i</sub> + J Σ<sub>〈i,j〉</sub>Z<sub>i</sub>Z<sub>j</sub>, &nbsp; B = g Σ<sub>i</sub>X<sub>i</sub>.','EquationPL')
para('ρ<sub>t+1</sub> = U [η(u<sub>t</sub>) ⊗ Tr<sub>0</sub>ρ<sub>t</sub>] U<super>†</super>, &nbsp; η(u)=|ψ(u)〉〈ψ(u)|,','EquationPL')
para('|ψ(u)〉 = √(1-u)|0〉 + √u|1〉, &nbsp; z<sub>j</sub>(t)=Tr(O<sub>j</sub>ρ<sub>t</sub>).','EquationPL')
para('Uczeniu podlegają wyłącznie współczynniki klasycznego odczytu ridge. Dobór hiperparametrów rezerwuaru na walidacji pozostaje optymalizacją klasyczną; nie jest treningiem obwodu wariacyjnego.')
sub('Dynamika dokładna i splitting')
para('U<sub>exact</sub>=exp[-iτ(A+B)], &nbsp; U<sub>ABA,r</sub>=[exp(-iδA/2) exp(-iδB) exp(-iδA/2)]<super>r</super>, δ=τ/r.','EquationPL')
para('BAB zamienia role A i B. Oznaczenie AB opisuje kolejność czasową A, potem B; macierzowo jest to U<sub>B</sub>U<sub>A</sub>. Dokładność symulacji jest odrębnym kryterium od jakości predykcji. Literatura o błędach Trottera uzasadnia badanie obserwabli i struktury dynamiki, ale sama nie dowodzi poprawy QRC [3].')
sub('Trzy różne pojęcia spektrum')
para('Dla czterech kubitów widmo H oraz widmo superoperatora kanału są skończone. Ciągły zbiór stanów czystych lub parametrów wejścia nie oznacza ciągłego widma energii. W CV operator położenia może mieć widmo ciągłe, podczas gdy Hamiltonian oscylatora harmonicznego ma widmo dyskretne. Kategorie te nie mogą być używane zamiennie.')
para('Macierz kanału zredukowanej pamięci ma rozmiar 64 × 64 i opisuje ten sam fizyczny układ n=4 co pełny kanał 256 × 256. Zbieżność niezerowych widm sprawdzono w testach. Promień spektralny przy zamrożonym u=0.5 nie dowodzi echo state property przy zmiennym wejściu; potrzebna jest kontrola iloczynów kanałów lub kontrakcji wielokrokowej.')

page('3. H1 i H2: co przetrwało weryfikację')
para('W H1 analizowano ustalony Strang r=2 z marginesem nieinferiorności 2%; H2 dotyczyła walidacyjnie wybranego Trottera i poprawy co najmniej 2%. Podane ilorazy są średnimi geometrycznymi na poziomie bloku, z równym udziałem NARMA10 i MG5. Dane stresowe nie realizują w całości pierwotnego protokołu 20 bloków.')
rr=[]
for case,hyp,label in [('standard','H1_fixed_p2r2','H1: standard'),('kick_resonance','H1_fixed_p2r2','H1: rezonans'),('coarse_tau','H2_val_selected','H2: τ=3.2')]:
    row=next(r for r in A['H1_H2'] if r['case']==case and r['hypothesis']==hyp)
    rr.append([label,fmt(row['estimate']),interval(row)])
table(['Porównanie z fixed exact','Iloraz NRMSE','95% CI t'],rr,[245,110,138])
para('Dla standardowego przypadku górna granica H1 przekracza 1.02: wynik pozostaje nierozstrzygnięty. Rezonans pokazuje silne pogorszenie i wyklucza bezwarunkową rekomendację r=2. Początkowa poprawa H2 przy τ=3.2 wymagała silniejszego odniesienia.')
sub('Nowe bloki 100-107: kontrola konkurencyjna')
table(['Odniesienie','Trotter / odniesienie','95% CI t'],[[r['reference'],fmt(r['estimate']),interval(r)] for r in A['followup']],[200,155,138])
para('Porównanie z dostrojonym exact daje 1.002 [0.911; 1.103]. Nie wykazano ani przewagi, ani równoważności. Równa liczba ośmiu kandydatów nie wyrównuje kosztu obliczeń i zasobów fizycznych. Klasyczny model wielomianowych opóźnień jest silnym odniesieniem; wyniki obu zadań należy pokazywać również osobno.')
para('Wniosek audytowy: można utrzymać tezę o zależności wyniku od dyskretyzacji, ale należy odrzucić sformułowanie „potwierdzona przewaga Trottera”. Dla przypadku przemiennego zapis p=0 w starej tabeli jest konwencją kodu dla zerowej wariancji; nie powinien być interpretowany jako empiryczna istotność statystyczna. Dla J=0 historyczne proxy bramek 2Q nie odzwierciedla usuwania zerowych rotacji.')

page('4. H3: pamięć, nieliniowość i dostępność odczytu')
para('Cele pamięci wykorzystują iid U[0,1] i ortogonalne wielomiany Legendre’a. Oddzielnie rekonstruowane są: opóźnione wejścia, produkty sąsiednich opóźnień oraz cele kwadratowe. Jest to ograniczony zestaw funkcji, nie pełna information processing capacity [2].')
para('C<sub>f</sub>(d)=1-MSE<sub>test</sub>/Var<sub>test</sub>(f), &nbsp; T=[Σ<sub>d=1..10</sub>C<sub>prod</sub>(d)-Σ<sub>d=1..10</sub>C<sub>lin</sub>(d)]/10.','EquationPL')
table(['H3: AB r=1 - exact','ΔT','95% CI t'],[[r['regime'],fmt(r['estimate']),interval(r)] for r in A['H3']],[240,90,163])
para('<b>Dodatnia ΔT nie dowodzi korzystnego kompromisu.</b> W standardowym reżimie suma liniowa spada z 2.995 do 0.261, a iloczynowa z 0.114 do -0.344. Zmiana T wynika głównie z większej utraty składowej liniowej. Ujemne C oznacza słabą generalizację względem testowej średniej, nie ujemną informację fizyczną.')
sub('Wynik strukturalny')
para('Dla AB/BA z pojedynczym blokiem diagonalnym zredukowany kanał pamięci jest mieszaniną sprzężeń unitarnych. W konsekwencji ma wspólny stan stały I/8. Jeśli sekwencja miesza do tego stanu, ślad historycznych wejść zanika. Sama unitalność nie gwarantuje mieszania wszystkich sekwencji. Kontrola startu w I/8 potwierdza brak użytecznej pamięci tej konfiguracji.')
sub('Stan a pomiar')
para('Dla par historii D=||ρ<sub>a</sub>-ρ<sub>b</sub>||<sub>1</sub>/2 ogranicza optymalną rozróżnialność, natomiast max<sub>j</sub>|Δ〈O<sub>j</sub>〉|/2 stanowi dolną granicę dostępną wybranemu odczytowi. Dodatnie D potwierdza ślad konkretnej perturbacji; nie dowodzi rekonstruowalności wszystkich dawnych wejść.')
para('Dla BAB r=2 przy τ=3.2 idealna suma liniowa rośnie z 2.942 (12 cech) do 9.253 (255 cech). Efekt utrzymuje się po dłuższej rozgrzewce, lecz mały sygnał stanu sugeruje dużą wrażliwość pomiarową. Rozszerzanie odczytu zmienia także wariancję estymacji i regularizację; nie jest bezkosztowym odzyskiwaniem informacji.')

page('5. Szum, niedoskonałości i model kosztowy')
para('Nowa seria obejmuje trzy warunki kanałów: idealny, mild i stress. Parametry są syntetyczne i jawnie dobrane do testu odporności. Nie pochodzą z kalibracji konkretnego procesora. Kanały relaksacji i depolaryzacji są zgodne z definicjami Qiskit Aer [5].')
table(['Składnik','mild','stress'],[
 ['Depolaryzacja po RX / CX','0.0001 / 0.001','0.001 / 0.01'],
 ['T1 / T2 [μs]','100 / 80','50 / 40'],
 ['Względny błąd kąta','+0.5%','+2%'],
 ['Populacja wzbudzona po resecie','1%','3%'],
 ['P(1 przy 0) / P(0 przy 1)','1% / 2%','3% / 5%']],[260,115,118])
para('RZZ rozłożono na CX-RZ-CX. Przyjęto szeregowe wykonanie: RX 35 ns, CX 300 ns, RZ wirtualne; pamięć relaksuje także podczas resetu wejścia 1 μs. Błąd kąta dotyczy RX, RZ i kodowania wejścia. Reset daje błędną populację, lecz nie zachowuje dawnych korelacji. Błędy rotacji baz pomiarowych, leakage i crosstalk nie są modelowane.')
table(['Odczyt','Liczba cech','Ustawienia'],[['Lokalne X/Z/ZZ',12,2],['Wszystkie wagi 1 i 2',66,9],['Pełna baza Pauliego',255,81]],[270,100,123])
para('Próbkowane są wspólne 4-bitowe wyniki dla obserwabli w tej samej bazie. Zachowuje to kowariancje, których nie odtwarza niezależny szum dodawany każdemu oczekiwaniu. Porównano dokładne oczekiwania, 4096 shots na grupę oraz wspólny budżet CX × shots.')
para('Budżet na krok wynosi B=196608. Dla lokalnego odczytu ABA2 otrzymuje 4096 shots/grupę, BAB2 6144, a ABA16 722. Pełny odczyt ma odpowiednio 101, 151 i 17 shots/grupę. Uwzględniono zaokrąglenie w dół, więc koszty są ograniczone wspólnym limitem, nie idealnie równe.')
para('Odczyt zakłada replay całej historii przed każdym pomiarem [4]. Dla długości 1360 lokalny ABA2 kosztuje około 1.82 × 10<super>11</super> CX × shots na zbiór. Same CX przy 300 ns odpowiadają około 15.2 h wykonania szeregowego. To koszt hipotetycznej realizacji, nie czas zużyty na QPU. Ograniczenie historii do W wymaga ponownego badania pamięci.')

page('6. Wyniki odporności: stan idealny nie wystarcza')
para('Tabela pokazuje średnią sumę liniowych pojemności dla d=1,...,20, osiem nowych bloków. Kolumny z pomiarami używają wspólnego limitu CX × shots. Zakres regularyzacji rozszerzono do 10<super>12</super> po rozpoznaniu przeuczenia zaszumionych cech; każdy wybór α nadal opiera się tylko na walidacji. Jest to jawna rewizja eksploracyjna.')
rr=[]
for case in ('coarse_ABA2','coarse_BAB2','coarse_ABA16','resonance_ABA2'):
    for view in ('local_XZ_ZZ','full_Pauli'):
        r=next(v for v in A['noise_memory'] if v['case']==case and v['view']==view)
        rr.append([case.replace('coarse_','').replace('resonance_','rez. ')+(' / 12' if view=='local_XZ_ZZ' else ' / 255')]+[fmt(r[k]) for k in ('ideal_expectation','shots','mild','stress')])
table(['Schemat / cechy','Ideal ∞','Shots','mild','stress'],rr,[185,77,77,77,77])
para('Wysoka pamięć idealnego BAB nie przechodzi na użyteczny pełny odczyt w rozpatrywanym budżecie. Nie jest to dowód fizycznego wymazania informacji przez sam pomiar statystyczny: stan przed pomiarem może zachować sygnał, lecz dostępny estymator nie potrafi go skutecznie wykorzystać.')
sub('Predykcja: płytszy ABA2 wobec ABA16, mild')
table(['Zadanie / budżet','Iloraz NRMSE','95% CI t'],[[r['task']+(' / shots' if r['budget']=='equal_shots' else ' / CX × shots'),fmt(r['estimate']),interval(r)] for r in A['noise_prediction']],[245,100,148])
para('Korzyść ABA2 występuje także przy równych shots, więc nie sprowadza się wyłącznie do większej liczby pomiarów w tańszym obwodzie. Dotyczy jednak konkretnego modelu szumu i pary konfiguracji. Nie jest porównaniem z dostrojonym exact, optymalnym klasycznym modelem ani dowodem skalowania przewagi.')

page('7. Pełne profile: trzy składowe pamięci')
story.append(Image(str(ROOT/'analysis_output/qrc_h3_noise/noise_memory_profiles.png'),width=493,height=352))
para('Rysunek 1. BAB r=2, τ=3.2. Wiersze: cele liniowe, iloczynowe i kwadratowe; kolumny: 12, 66 i 255 obserwabli. Ciemna linia: dokładne oczekiwania bez szumu. Pozostałe: skończone pomiary przy wspólnym limicie CX × shots, z szumem kanału lub bez niego. Cieniowanie: punktowe, niejednoczesne przedziały t 95% po ośmiu blokach. Skale pionowe paneli są różne. Źródło: profiles.csv, nowa seria szumowa.','SmallPL')
para('Utrata użyteczności obejmuje kilka rodzin celów, a nie samą różnicę pamięć liniowa minus nieliniowa. Szczególnie istotne jest załamanie odczytu 255 cech: idealna baza dobrze rozdziela historię, lecz rozdzielenie budżetu na 81 ustawień ogranicza precyzję pojedynczych cech.')
para('Nie należy interpretować niewielkich ujemnych sum jako ujemnej pojemności teoretycznej. C=1-NRMSE² jest estymatorem jakości poza próbą; przy krótkim zbiorze, regularyzacji i wyborze α może być ujemny. Raportowanie surowych wartości jest właściwe, natomiast obcięcie każdej do zera przed sumowaniem zawyżałoby ocenę.')
para('Najbardziej informacyjny kolejny test powinien mierzyć krzywą jakości względem budżetu shots oraz wybór małego podzbioru obserwabli na walidacji. Pozwoli to oddzielić niedostateczny budżet od nieefektywnej alokacji pomiarów. Obecne dwa warianty budżetowe nie wyznaczają uniwersalnego progu zasobów.')

page('8. Rezonans i układy CV: wyniki krytyczne')
para('Przy τ=π/g idealny ABA2 może tracić ślad wcześniejszego wejścia. Zaszumione perturbacje nie muszą działać monotonnie: mogą przesuwać szczególny punkt lub zmieniać strukturę kanału. Ablacje porównują identyczne historie, n=4 i ten sam moment odczytu.')
dd=local_csv('qrc_h3_noise','noise_ablation_impulses.csv')
rr=[]
for label in ('ideal','depolarization_only','thermal_only','coherent_only','reset_only','combined_mild'):
    vals=[]
    for off in (-.075,0.,.075):
        v=[float(r['trace_distance']) for r in dd if r['noise']==label and float(r['offset'])==off and r['delay']=='5']
        vals.append(f'{sum(v)/len(v):.3g}')
    rr.append([label]+vals)
table(['Składnik','δτ=-0.075','δτ=0','δτ=+0.075'],rr,[220,91,91,91])
para('Średnia odległość śladowa po pięciu kolejnych wejściach, osiem bloków. W punkcie rezonansu relaksacja oraz błąd koherentny przywracają niewielką rozróżnialność. Sama depolaryzacja i błąd populacji resetu nie dają tego efektu w badanej tolerancji. Nie wynika stąd korzystny wpływ szumu na końcową predykcję.')
sub('Ciągłe zmienne i stabilność')
para('W modelach gaussowskich propagowane są średnie m oraz kowariancja V. Dla tłumienia η warunek ρ(√η S)&lt;1 gwarantuje asymptotyczną stabilność liniowej części średnich i zbieżność kowariancji przy stałym kanale. Nie jest to własność samego widma energii. Gaussowski opis ma efektywną klasyczną reprezentację [6].')
para(f"Niezależny rachunek macierzy ścinających dla oscylatora i τ=3 odtworzył ρ(√η S)={A['CV_large_step_radius']:.4f} dla Stranga r=1, podczas gdy exact ma 0.8944. Zwiększenie kroku może więc destabilizować numeryczną dynamikę mimo stabilności modelu dokładnego.")
para('Cutoff Focka wymaga osobnej kontroli dla każdej formuły. Przy α=2.5 cutoff=8 odrzuca około 29% początkowej masy; cutoff=16 nadal może być niewystarczający dla pierwszego rzędu. Zbieżność przy cutoff=32/64 dotyczy pokazanych stanów i obserwabli, nie dowodzi globalnej kontroli operatorów nieograniczonych.')

page('9. Audyt statystyczny i zagrożenia dla wniosków')
para('Blok, a nie punkt czasu lub pojedynczy shot, jest jednostką niezależną. Główne serie zawierają n=8; skan rezonansu n=4. Przedziały t zakładają odpowiedni rozkład efektów blokowych. Bootstrap przy ośmiu blokach także ma ograniczoną wiarygodność i służy tu kontroli wrażliwości.')
table(['Efekt','95% CI bootstrap','Zakres po usunięciu bloku'],[
 [r['reference'],f"[{r['bootstrap_low']:.3f}; {r['bootstrap_high']:.3f}]",f"[{r['loo_low']:.3f}; {r['loo_high']:.3f}]"] for r in A['followup'][:2]]+[ 
 [r['task']+' ABA2/16',f"[{r['bootstrap_low']:.3f}; {r['bootstrap_high']:.3f}]",f"[{r['loo_low']:.3f}; {r['loo_high']:.3f}]"] for r in A['noise_prediction'] if r['budget']=='equal_CX_budget'],[170,155,168])
para('Kontrola znaku daje p=0.0078125, gdy wszystkie osiem efektów ma ten sam kierunek. To dokładny test mediany znaku, nie test średniej logarytmicznej użytej przez t. Bardzo małe parametryczne p nie oznaczają tysięcy niezależnych obserwacji. Wnioski powinny opierać się przede wszystkim na wielkości efektu i replikacji.')
sub('Najważniejsze ograniczenia')
para('<b>Wielokrotne decyzje.</b> Zmieniano reżimy, splitting, odczyty i zakres α. Korekty Holma w wybranych rodzinach nie obejmują całej historii eksploracji. Znanych już bloków nie można ponownie uznać za niewidziany test potwierdzający.')
para('<b>Porównywalność.</b> Idealny exact jest odniesieniem matematycznym; koszt jego realizacji nie został wyrównany w serii szumowej. Proste klasyczne modele były sprawdzone w starszej serii, ale nie ponownie pod równym budżetem strojenia w nowej.')
para('<b>Informacja a readout.</b> Zmiana profilu iid i NRMSE dla MG dotyczy różnych rozkładów wejść. Korelacja nie stanowi dowodu mediacji. Bogatszy readout zmienia wymiar modelu, regularizację i budżet pomiarowy.')
para('<b>Drift i sprzęt.</b> Zbadano jedną zadaną zmianę kalibracji między treningiem a testem. Nie jest ona modelem rozkładu dryfu konkretnego QPU. Brakuje leakage, crosstalk, routingu i skończonego okna replay. Historyczna diagnostyka H1/H2 mieszała n=3 dla widma z n=4 dla pamięci; mechanizmy należy opierać na poprawionej serii H3 o wspólnym n=4.')

page('10. Ocena końcowa i plan replikacji')
table(['Obszar','Ocena audytowa','Działanie'],[
 ['Algebra i implementacja','W sprawdzonym zakresie zgodne','Zamrozić kod i wersje zależności'],
 ['H1/H2','Brak ogólnego potwierdzenia przewagi','Nowe bloki; tuned exact i silne klasyczne odniesienia'],
 ['H3 - mechanizm','Wartościowe sygnały i kontrola unitalności','Nie utożsamiać dodatniej ΔT z korzyścią'],
 ['BAB z pełnym odczytem','Silna kruchość pomiarowa','Krzywa shots i wybór obserwabli'],
 ['ABA2 wobec ABA16','Korzyść w modelu mild','Replikacja z kalibracją backendu'],
 ['CV','Stabilność zależy od splittingu','Kontrola cutoff i ewentualna nieliniowość niegaussowska'],
 ['H4/H5','Nie rozstrzygnięte w pełnym protokole','Oddzielny test budżetu i okna W']],[98,205,190])
sub('Rekomendowana kolejność')
para('<b>1.</b> Zamrozić konfiguracje ABA2/BAB2 i kryteria wyboru odczytu. Zarejestrować cele pierwotne, marginesy efektu, rodziny porównań i zasady zatrzymania. Liczbę bloków wyznaczyć na podstawie analizy mocy dla istotnego naukowo efektu, zamiast automatycznie przyjmować osiem.')
para('<b>2.</b> Na nowych ziarnach porównać profile i predykcję przy kilku budżetach shots, z szeroką siatką α ustaloną z góry. Archiwizować y, predykcje, α, wybory walidacyjne, konfiguracje, wyniki grup pomiarowych i czas wykonania.')
para('<b>3.</b> Przejść na skalibrowany model tego samego zestawu fizycznych kubitów. Zmierzyć wpływ W=8/16/32, przygotowania, odczytu i kolejności realizacji obwodów. Wykonania metod przeplatać w blokach kalibracyjnych; koszt mitigacji włączyć do budżetu.')
para('<b>4.</b> Dopiero potem formułować twierdzenie publikacyjne: zależność użytecznej pamięci od splittingu i ograniczeń pomiaru. Przewaga kwantowa, ogólny optymalny Trotter i uniwersalna korzystność szumu pozostają poza obecnymi dowodami.')
para('Temat magisterski pozostaje zasadny jako badanie mechanizmu i ograniczeń praktycznych. Najsilniejsza oś przyszłego doktoratu to projektowanie kanału i odczytu przy zadanym budżecie, z rygorystycznym rozróżnieniem pamięci stanu, dostępnej rozróżnialności i generalizacji.')

page('Bibliografia i materiały do odtworzenia')
refs=[
 ('1','K. Fujii, K. Nakajima, Harnessing Disordered-Ensemble Quantum Dynamics for Machine Learning, Physical Review Applied 8, 024030 (2017).','https://arxiv.org/abs/1602.08159'),
 ('2','J. Dambre, D. Verstraeten, B. Schrauwen, S. Massar, Information Processing Capacity of Dynamical Systems, Scientific Reports 2, 514 (2012).','https://www.nature.com/articles/srep00514'),
 ('3','M. Heyl, P. Hauke, P. Zoller, Quantum localization bounds Trotter errors in digital quantum simulation, Science Advances 5, eaau8342 (2019).','https://arxiv.org/abs/1806.11123'),
 ('4','P. Mujal, R. Martínez-Peña, G. L. Giorgi, M. C. Soriano, R. Zambrini, Time-series quantum reservoir computing with weak and projective measurements, npj Quantum Information 9, 16 (2023). DOI: 10.1038/s41534-023-00682-z.','https://arxiv.org/abs/2205.06809'),
 ('5','Qiskit Aer, dokumentacja thermal_relaxation_error i NoiseModel. Dostęp: 7.09.2026.','https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.noise.thermal_relaxation_error.html'),
 ('6','C. Weedbrook i in., Gaussian Quantum Information, Reviews of Modern Physics 84, 621-669 (2012).','https://arxiv.org/abs/1110.3234')]
for num,title,url in refs:para(f'[{num}] {html.escape(title)}<br/><link href="{url}" color="#174c70">{html.escape(url)}</link>','SmallPL')
sub('Dane własne projektu')
para('D1: analysis_output/qrc_spectral_h1_h2/ - dane H1/H2, kontrola exact, modele CV i kompilacja.<br/>D2: analysis_output/qrc_h3_memory/ - profile, kanały, impulsy, odczyty i washout.<br/>D3: analysis_output/qrc_h3_noise/ - scenariusze szumu, koszty, dryf i ablacje.<br/>D4: analysis_output/qrc_independent_audit/audit.json - odrębnie obliczone statystyki i wyniki kontroli.','SmallPL')
para('Ścieżki względne odnoszą się do D:/Projects/QML. Główny protokół: quantum_reservoir/RESEARCH_PROTOCOL_H1_H5.md. Narzędzia audytu i składu: tools/audit_qrc_results.py oraz tools/build_qrc_audit_pdf.py.','SmallPL')
sub('Odtworzenie audytu i dokumentu')
para('.venv_qml/Scripts/python.exe tools/audit_qrc_results.py<br/>python tools/build_qrc_audit_pdf.py<br/>Skład wymaga reportlab i pypdf oraz czcionek Times New Roman. Audyt korzysta z Python 3.12.14, NumPy 2.4.6 i SciPy; kontrole modeli używają kodu QRC.','SmallPL')
para('Integralność i zakres: audit.json zapisuje SHA-256 skryptu audytu oraz wynik weryfikacji manifestów. Raport jest syntezą projektu, nie systematycznym przeglądem całej literatury QML na wrzesień 2026. Wyniki numeryczne w raporcie pochodzą z danych projektu; źródła [1-6] wspierają kontekst metodologiczny.','SmallPL')

def footer(canvas,doc):
    canvas.saveState();w,h=A4
    if doc.page>1:
        canvas.setFont('T',8);canvas.setFillColor(colors.HexColor('#647584'))
        canvas.drawString(51,h-32,'QRC | Audyt metodologiczny i wyniki badań')
    canvas.setStrokeColor(colors.HexColor('#cbd5dc'));canvas.line(51,41,w-51,41)
    canvas.setFont('T',8);canvas.setFillColor(colors.HexColor('#647584'))
    canvas.drawString(51,28,'7 września 2026 | Badanie eksploracyjne | Bez pomiarów na QPU')
    canvas.drawRightString(w-51,28,str(doc.page));canvas.restoreState()

path=OUT/'Audyt_QRC_H1_H3_szum_2026-09-07.pdf'
doc=SimpleDocTemplate(str(path),pagesize=A4,rightMargin=51,leftMargin=51,topMargin=55,bottomMargin=55,
                     title='Audyt QRC: trotteryzacja, pamięć i szum',author='Raport projektu QRC - audyt wykonany przy wsparciu Codex')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
reader=PdfReader(path)
text='\n'.join(p.extract_text() for p in reader.pages)
assert len(reader.pages)==12, f'Unexpected pagination: {len(reader.pages)}'
assert 'H3' in text and 'Bibliografia' in text and '\ufffd' not in text
(ROOT/'analysis_output/qrc_independent_audit/pdf_text.txt').write_text(text,encoding='utf-8')
print(f'PDF ready: {path}; pages={len(reader.pages)}; extracted_chars={len(text)}')
