from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "pdf" / "raport_dotychczasowych_osiagniec_QML.pdf"
CHARTS = ROOT / "tmp" / "pdfs" / "qml_achievements"

NAVY = colors.HexColor("#17324D")
TEAL = colors.HexColor("#0D7C7B")
ORANGE = colors.HexColor("#D97706")
RED = colors.HexColor("#B42318")
GREEN = colors.HexColor("#3F7D57")
INK = colors.HexColor("#20262E")
MID = colors.HexColor("#5E6875")
LIGHT = colors.HexColor("#F2F5F7")
LINE = colors.HexColor("#D6DCE1")
WHITE = colors.white


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def register_fonts() -> None:
    font_dir = (
        ROOT
        / ".venv_qml"
        / "Lib"
        / "site-packages"
        / "matplotlib"
        / "mpl-data"
        / "fonts"
        / "ttf"
    )
    pdfmetrics.registerFont(TTFont("Arial", font_dir / "DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont("Arial-Bold", font_dir / "DejaVuSans-Bold.ttf"))
    pdfmetrics.registerFont(TTFont("Arial-Italic", font_dir / "DejaVuSans-Oblique.ttf"))
    pdfmetrics.registerFont(
        TTFont("Arial-BoldItalic", font_dir / "DejaVuSans-BoldOblique.ttf")
    )
    pdfmetrics.registerFontFamily(
        "Arial",
        normal="Arial",
        bold="Arial-Bold",
        italic="Arial-Italic",
        boldItalic="Arial-BoldItalic",
    )


def make_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    styles: dict[str, ParagraphStyle] = {}
    styles["body"] = ParagraphStyle(
        "BodyPL",
        parent=base["BodyText"],
        fontName="Arial",
        fontSize=9.2,
        leading=13.5,
        textColor=INK,
        alignment=TA_JUSTIFY,
        spaceAfter=5.5,
        splitLongWords=True,
    )
    styles["small"] = ParagraphStyle(
        "SmallPL",
        parent=styles["body"],
        fontSize=7.7,
        leading=10.5,
        textColor=MID,
        alignment=TA_LEFT,
    )
    styles["caption"] = ParagraphStyle(
        "CaptionPL",
        parent=styles["small"],
        fontSize=7.5,
        leading=10.2,
        alignment=TA_CENTER,
        spaceBefore=2,
        spaceAfter=8,
    )
    styles["h1"] = ParagraphStyle(
        "Heading1PL",
        parent=base["Heading1"],
        fontName="Arial-Bold",
        fontSize=19,
        leading=23,
        textColor=NAVY,
        spaceBefore=4,
        spaceAfter=10,
        keepWithNext=True,
    )
    styles["h2"] = ParagraphStyle(
        "Heading2PL",
        parent=base["Heading2"],
        fontName="Arial-Bold",
        fontSize=13,
        leading=16,
        textColor=TEAL,
        spaceBefore=9,
        spaceAfter=5,
        keepWithNext=True,
    )
    styles["h3"] = ParagraphStyle(
        "Heading3PL",
        parent=base["Heading3"],
        fontName="Arial-Bold",
        fontSize=10.4,
        leading=13,
        textColor=NAVY,
        spaceBefore=7,
        spaceAfter=3,
        keepWithNext=True,
    )
    styles["title"] = ParagraphStyle(
        "TitlePL",
        parent=base["Title"],
        fontName="Arial-Bold",
        fontSize=30,
        leading=34,
        textColor=WHITE,
        alignment=TA_LEFT,
        spaceAfter=12,
    )
    styles["subtitle"] = ParagraphStyle(
        "SubtitlePL",
        parent=styles["body"],
        fontName="Arial",
        fontSize=13,
        leading=18,
        textColor=colors.HexColor("#E7F1F3"),
        alignment=TA_LEFT,
    )
    styles["cover_meta"] = ParagraphStyle(
        "CoverMeta",
        parent=styles["small"],
        fontSize=9,
        leading=14,
        textColor=WHITE,
        alignment=TA_LEFT,
    )
    styles["equation"] = ParagraphStyle(
        "EquationPL",
        parent=styles["body"],
        fontSize=10.1,
        leading=16,
        alignment=TA_CENTER,
        textColor=NAVY,
        backColor=LIGHT,
        borderColor=LINE,
        borderWidth=0.6,
        borderPadding=(7, 10, 7, 10),
        spaceBefore=5,
        spaceAfter=7,
    )
    styles["callout"] = ParagraphStyle(
        "CalloutPL",
        parent=styles["body"],
        fontSize=8.8,
        leading=13,
        backColor=colors.HexColor("#EAF5F4"),
        borderColor=TEAL,
        borderWidth=0.8,
        borderPadding=(7, 9, 7, 9),
        spaceBefore=5,
        spaceAfter=8,
    )
    styles["warning"] = ParagraphStyle(
        "WarningPL",
        parent=styles["callout"],
        backColor=colors.HexColor("#FFF5E8"),
        borderColor=ORANGE,
    )
    styles["bullet"] = ParagraphStyle(
        "BulletPL",
        parent=styles["body"],
        leftIndent=13,
        firstLineIndent=-7,
        bulletIndent=2,
        spaceAfter=3,
    )
    styles["toc"] = ParagraphStyle(
        "TocPL",
        parent=styles["body"],
        fontSize=10,
        leading=15,
        leftIndent=8,
        firstLineIndent=-8,
        spaceAfter=3,
    )
    styles["table"] = ParagraphStyle(
        "TablePL",
        parent=styles["small"],
        fontSize=7.4,
        leading=9.5,
        textColor=INK,
    )
    styles["table_head"] = ParagraphStyle(
        "TableHeadPL",
        parent=styles["table"],
        fontName="Arial-Bold",
        textColor=WHITE,
        alignment=TA_CENTER,
    )
    styles["ref"] = ParagraphStyle(
        "ReferencePL",
        parent=styles["small"],
        fontSize=7.5,
        leading=10.4,
        leftIndent=13,
        firstLineIndent=-13,
        spaceAfter=4,
    )
    return styles


class CoverBand(Flowable):
    def __init__(self, width: float, height: float):
        super().__init__()
        self.width = width
        self.height = height

    def draw(self) -> None:
        canvas = self.canv
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.roundRect(0, 0, self.width, self.height, 5 * mm, fill=1, stroke=0)
        canvas.setFillColor(TEAL)
        canvas.rect(0, 0, 10 * mm, self.height, fill=1, stroke=0)
        canvas.setFillColor(ORANGE)
        canvas.rect(10 * mm, 0, 2.4 * mm, self.height, fill=1, stroke=0)
        canvas.restoreState()


def on_page(canvas, doc) -> None:
    canvas.saveState()
    width, height = A4
    if doc.page == 1:
        canvas.setFillColor(NAVY)
        canvas.rect(0, 0, width, height, fill=1, stroke=0)
        canvas.setFillColor(TEAL)
        canvas.rect(0, 0, 14 * mm, height, fill=1, stroke=0)
        canvas.setFillColor(ORANGE)
        canvas.rect(14 * mm, 0, 3 * mm, height, fill=1, stroke=0)
    else:
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(18 * mm, height - 14 * mm, width - 18 * mm, height - 14 * mm)
        canvas.setFont("Arial", 7.2)
        canvas.setFillColor(MID)
        canvas.drawString(18 * mm, height - 10.5 * mm, "RESOURCE-AWARE HAMILTONIAN QUANTUM KERNELS")
        canvas.drawRightString(width - 18 * mm, 10 * mm, f"{doc.page}")
        canvas.drawString(18 * mm, 10 * mm, "Raport stanu realizacji | 11 września 2026")
    canvas.restoreState()


def p(styles, text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, styles[style])


def bullet(styles, text: str) -> Paragraph:
    return Paragraph(text, styles["bullet"], bulletText="•")


def eq(styles, text: str) -> Paragraph:
    return Paragraph(text, styles["equation"])


def callout(styles, title: str, text: str, warning: bool = False) -> Paragraph:
    style = "warning" if warning else "callout"
    return Paragraph(f"<b>{title}</b><br/>{text}", styles[style])


def section(styles, number: str, title: str) -> list:
    return [Spacer(1, 2 * mm), p(styles, f"{number}. {title}", "h1"), HRFlowable(width="100%", thickness=1.1, color=TEAL, spaceAfter=7)]


def make_table(styles, rows, widths, header=True, font_size=7.4) -> Table:
    converted = []
    for row_index, row in enumerate(rows):
        converted.append(
            [
                p(styles, str(cell), "table_head" if header and row_index == 0 else "table")
                for cell in row
            ]
        )
    table = Table(converted, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY if header else WHITE),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        for row in range(1, len(rows)):
            if row % 2 == 0:
                commands.append(("BACKGROUND", (0, row), (-1, row), LIGHT))
    table.setStyle(TableStyle(commands))
    return table


def chart(styles, filename: str, width_mm: float, caption: str) -> list:
    path = CHARTS / filename
    image = Image(str(path))
    aspect_ratio = image.imageHeight / image.imageWidth
    image.drawWidth = width_mm * mm
    image.drawHeight = image.drawWidth * aspect_ratio
    if image.drawHeight > 155 * mm:
        scale = (155 * mm) / image.drawHeight
        image.drawWidth *= scale
        image.drawHeight *= scale
    return [image, p(styles, caption, "caption")]


def build_story(styles: dict[str, ParagraphStyle]) -> list:
    full = load_json(
        ROOT
        / "analysis_output"
        / "resource_aware_hamiltonian_benchmark"
        / "full_results"
        / "completion.json"
    )
    grid_audit = load_json(
        ROOT / "analysis_output" / "hamiltonian_kernel_grid_full_spectral" / "independent_audit.json"
    )
    trotter = load_json(ROOT / "analysis_output" / "trotter_scaling_smoke" / "completion.json")
    trotter_analysis = load_json(
        ROOT / "analysis_output" / "trotter_scaling_smoke" / "hypothesis_analysis.json"
    )
    trotter_audit = load_json(
        ROOT / "analysis_output" / "trotter_scaling_smoke" / "independent_audit.json"
    )
    hardware_audit = load_json(
        ROOT
        / "analysis_output"
        / "ibm_validation_audit_layout_89_90_91_98_20260825"
        / "independent_audit.json"
    )
    photonic_audit = load_json(
        ROOT / "analysis_output" / "photonic_kernel_x8_audit" / "audit.json"
    )
    ibm_fid_dir = (
        ROOT
        / "analysis_output"
        / "ibm_validation_fidelity_v2"
        / "ibm_kingston_qpu_layout_89_90_91_98_20260825"
    )
    ibm_proj_dir = (
        ROOT
        / "analysis_output"
        / "ibm_validation_projected_v2"
        / "ibm_kingston_qpu_layout_89_90_91_98_20260825"
    )
    ibm_fid = load_json(ibm_fid_dir / "analysis.json")
    ibm_proj = load_json(ibm_proj_dir / "analysis.json")
    ibm_fid_exec = load_json(ibm_fid_dir / "execution.json")
    ibm_proj_exec = load_json(ibm_proj_dir / "execution.json")

    story: list = []

    story.extend(
        [
            Spacer(1, 28 * mm),
            p(styles, "RESOURCE-AWARE<br/>HAMILTONIAN<br/>QUANTUM KERNELS", "title"),
            Spacer(1, 4 * mm),
            p(
                styles,
                "Raport dotychczasowych osiągnięć: Hamiltonian kernels, Trotter, walidacja IBM QPU, CV/GBS oraz rozszerzenie badawcze o QuanONet",
                "subtitle",
            ),
            Spacer(1, 60 * mm),
            p(styles, "Projekt QML", "cover_meta"),
            p(styles, "Stan artefaktów: 11 września 2026", "cover_meta"),
            p(styles, "Dokument techniczny i naukowy | wersja 1.1", "cover_meta"),
            PageBreak(),
        ]
    )

    story.extend(section(styles, "0", "Jak czytać ten raport"))
    story.append(
        p(
            styles,
            "Raport prowadzi od intuicji do formalizmu bez przeskoków. Każdy etap odpowiada na sześć pytań: <b>po co</b> go wykonano, <b>co</b> dokładnie zdefiniowano, <b>jak</b> wynika to matematycznie, <b>jak</b> zostało zaimplementowane, <b>co</b> zmierzono oraz <b>czego wynik nie dowodzi</b>. Język jest celowo precyzyjny: rozróżniamy wynik idealnego statevectora, finite-shot simulatora, kompilację do ISA, wykonanie na fizycznym QPU oraz propozycję badawczą, która nie ma jeszcze wyniku lokalnego.",
        )
    )
    status_rows = [
        ["Oznaczenie", "Znaczenie w raporcie"],
        ["Zrealizowano", "Kod i artefakty istnieją, a ścieżka została uruchomiona."],
        ["Zwalidowano", "Testy lub niezależny audyt odtworzyły kluczowe własności."],
        ["Wynik opisowy", "Pipeline działa, lecz próba nie ma mocy do testu hipotezy."],
        ["Wynik potwierdzający", "Hipoteza, budżet i test były zamrożone przed analizą testu."],
        ["Nie wykonano", "Element jest przygotowany, ale brak uczciwego wyniku sprzętowego."],
    ]
    story.append(make_table(styles, status_rows, [32 * mm, 137 * mm]))
    story.append(p(styles, "Mapa dokumentu", "h2"))
    toc = [
        "1. Wybór problemu i powstanie wariantu B",
        "2. Mapa cech generowana przez Hamiltonian",
        "3. Ewolucja dokładna i formuły Suzuki-Trottera",
        "4. Fidelity, projected i klasyczny RBF",
        "5. Skończona liczba pomiarów i naprawa PSD",
        "6. Uczciwy protokół model selection i nested repeated CV",
        "7. Siatka t, J, g i topologii przy równym budżecie",
        "8. Pełny benchmark resource-aware i wynik potwierdzający",
        "9. Warstwa sprzętowa oraz pilot IBM Quantum",
        "10. Osobny kernel fotoniczny CV/GBS",
        "11. Hipoteza skalowania optymalnej polityki Trottera",
        "12. QuanONet: quantum neural operator jako kierunek komplementarny",
        "13. Audyty, ograniczenia i dalsza ścieżka publikacyjna",
    ]
    for item in toc:
        story.append(p(styles, item, "toc"))
    story.append(PageBreak())

    story.extend(section(styles, "1", "Wybór problemu i powstanie wariantu B"))
    story.append(
        p(
            styles,
            "Punktem wyjścia były trzy potencjalne kierunki: optymalizacja modeli QML bez klasycznego schematu VQA, regularizacja modeli kwantowych oraz klasyczne przygotowanie dobrego stanu początkowego dla optymalizacji kwantowej. Audyt wykazał, że pierwszy kierunek daje najbardziej zwartą ścieżkę badawczą: można połączyć fizyczny błąd symulacji Hamiltonianu, jakość kernela i rzeczywisty koszt obwodu w jednej falsyfikowalnej analizie.",
        )
    )
    choice_rows = [
        ["Kierunek", "Co trzeba rozwiązać", "Trudność", "Decyzja"],
        ["QML bez VQA", "Mapa cech z e<super>-itH(x)</super>, Trotter, pomiar kernela, koszt", "Wysoka, ale mierzalna", "Główna praca"],
        ["Regularizacja", "Kontrola ekspresyjności, widma kernela, szumu i generalizacji", "Wysoka metodologicznie", "Włączona jako PSD/spectral i budżet"],
        ["Dobry stan początkowy", "Klasyczne heurystyki, chemia, warm-start i zależność od problemu", "Bardzo zależna od domeny", "Ścieżka późniejsza"],
    ]
    story.append(make_table(styles, choice_rows, [35 * mm, 72 * mm, 31 * mm, 31 * mm]))
    story.append(
        callout(
            styles,
            "Najprostsza intuicja",
            "Zamiast trenować setki parametrów obwodu, dane sterują Hamiltonianem. Komputer kwantowy wykonuje ustaloną ewolucję, a uczenie klasyfikatora odbywa się klasycznie na macierzy podobieństw. Badamy więc nie „czy obwód się wytrenuje”, lecz „jak dokładność fizycznej ewolucji zamienia się w jakość i koszt kernela”.",
        )
    )
    story.append(p(styles, "Wariant B został rozwinięty w czterech warstwach:", "h3"))
    for text in [
        "warstwa matematyczna: dokładna ewolucja, Trotter pierwszego i drugiego rzędu oraz diagnostyka błędu stanu;",
        "warstwa uczenia: fidelity kernel, projected kernel i klasyczne baseline'y;",
        "warstwa zasobów: shots, wykonania mapy cech, bramki 2Q ważone shots oraz czas QPU;",
        "warstwa reprodukowalności: zamrożone protokoły, hashe, nested CV, QPY/ISA, layout i snapshot kalibracji.",
    ]:
        story.append(bullet(styles, text))

    story.extend(section(styles, "2", "Mapa cech generowana przez Hamiltonian"))
    story.append(p(styles, "2.1. Dlaczego baza Pauliego jest uniwersalna", "h2"))
    story.append(
        p(
            styles,
            "Dla jednego kubitu macierze I, X, Y, Z tworzą ortogonalną bazę operatorów względem iloczynu Hilberta-Schmidta. Dla n kubitów bierzemy wszystkie iloczyny tensorowe. Zbiór ma 4<super>n</super> elementów i rozpiętość równą przestrzeni wszystkich macierzy 2<super>n</super> × 2<super>n</super>. Każdy hermitowski Hamiltonian można więc zapisać jednoznacznie jako rozwinięcie Pauliego [1,3].",
        )
    )
    story.append(eq(styles, "H = Σ<sub>P∈{I,X,Y,Z}<super>⊗n</super></sub> h<sub>P</sub>P, &nbsp;&nbsp; h<sub>P</sub> = 2<super>-n</super> Tr(PH) ∈ ℝ."))
    story.append(
        p(
            styles,
            "Składnik proporcjonalny do I daje wyłącznie globalną fazę e<super>-ith<sub>I</sub></super>, która znika z wartości |⟨ψ|φ⟩|<super>2</super>. Dlatego w mapie cech można pominąć operator czysto identycznościowy i zachować 4<super>n</super>-1 kierunków.",
        )
    )
    story.append(p(styles, "2.2. Dane jako współczynniki Hamiltonianu", "h2"))
    story.append(eq(styles, "H(x) = Σ<sub>P∈𝒫<sub>k</sub></sub> [b<sub>P</sub> + w<sub>P</sub><super>T</super>x] P."))
    story.append(
        p(
            styles,
            "Współczynniki b<sub>P</sub> są częścią statyczną, a w<sub>P</sub><super>T</super>x wprowadza dane. Wszystkie współczynniki są rzeczywiste, więc H(x)=H(x)<super>†</super>. Dla k=n otrzymujemy pełną rodzinę n-lokalną; dla k&lt;n albo limitu liczby składników powstaje jawna aproksymacja rzadka. Ostatni profil smoke użył pełnej bazy: 15 składników dla n=2 oraz 63 dla n=3.",
        )
    )
    story.append(eq(styles, "|ψ(x)⟩ = U(x)|+⟩<super>⊗n</super>, &nbsp;&nbsp; U(x)=e<super>-itH(x)</super>."))
    story.append(
        callout(
            styles,
            "Co tu jest cechą?",
            "Klasyczny wektor x nie jest bezpośrednio klasyfikowany. Najpierw wybiera Hamiltonian, Hamiltonian obraca stan |+⟩<super>⊗n</super>, a dopiero otrzymany stan |ψ(x)⟩ jest reprezentacją próbki w przestrzeni Hilberta.",
        )
    )

    story.extend(section(styles, "3", "Ewolucja dokładna i formuły Suzuki-Trottera"))
    story.append(p(styles, "3.1. Ewolucja dokładna jako punkt odniesienia", "h2"))
    story.append(
        p(
            styles,
            "Ponieważ H jest hermitowski, istnieje rozkład H=VΛV<super>†</super>, gdzie Λ jest rzeczywistą macierzą diagonalną. Funkcja macierzy działa na wartości własne. To daje dokładny statevector dla małej liczby kubitów i służy jako standard, względem którego mierzymy błąd Trottera.",
        )
    )
    story.append(eq(styles, "e<super>-itH</super> = V diag(e<super>-itλ<sub>1</sub></super>,…,e<super>-itλ<sub>2<super>n</super></sub></super>) V<super>†</super>."))
    story.append(
        p(
            styles,
            "Koszt klasycznej diagonalizacji rośnie zasadniczo jak O(2<super>3n</super>) w gęstym przypadku. Metoda dokładna jest więc referencją dla małego n, a nie skalowalnym algorytmem kwantowym.",
        )
    )
    story.append(p(styles, "3.2. Skąd bierze się Trotter pierwszego rzędu", "h2"))
    story.append(p(styles, "Niech H=A+B oraz Δ=t/r. Gdy A i B komutują, e<super>-iΔ(A+B)</super>=e<super>-iΔA</super>e<super>-iΔB</super>. Gdy nie komutują, rozwinięcie Baker-Campbell-Hausdorffa daje:"))
    story.append(eq(styles, "e<super>ΔA</super>e<super>ΔB</super> = exp[Δ(A+B) + (Δ<super>2</super>/2)[A,B] + O(Δ<super>3</super>)]."))
    story.append(
        p(
            styles,
            "Błąd pojedynczego kroku jest więc drugiego rzędu w Δ. Wykonujemy r kroków, dlatego akumulacja prowadzi do globalnego skalowania O(rΔ<super>2</super>)=O(t<super>2</super>/r), z prefaktorem kontrolowanym przez komutatory [2,3].",
        )
    )
    story.append(eq(styles, "S<sub>1</sub>(Δ)=∏<sub>ℓ=1</sub><super>L</super> e<super>-iΔH<sub>ℓ</sub></super>, &nbsp;&nbsp; U(t)≈[S<sub>1</sub>(t/r)]<super>r</super>."))
    story.append(p(styles, "3.3. Dlaczego symetryzacja daje drugi rząd", "h2"))
    story.append(
        p(
            styles,
            "W formule symetrycznej wykonujemy połowę ewolucji w kolejności H<sub>1</sub>,…,H<sub>L</sub>, a potem połowę w kolejności odwrotnej. Symetria czasowa usuwa parzysty składnik lokalnego błędu. Pozostaje O(Δ<super>3</super>) na krok i O(t<super>3</super>/r<super>2</super>) globalnie.",
        )
    )
    story.append(eq(styles, "S<sub>2</sub>(Δ)= [∏<sub>ℓ=1</sub><super>L</super> e<super>-iΔH<sub>ℓ</sub>/2</super>] [∏<sub>ℓ=L</sub><super>1</super> e<super>-iΔH<sub>ℓ</sub>/2</super>]."))
    story.append(
        p(
            styles,
            "Implementacja obsługuje także rekurencyjną formułę Suzuki czwartego rzędu. W aktualnych eksperymentach potwierdzających zamrożono jednak rzędy 1 i 2, ponieważ rząd 4 mnoży liczbę eksponent Pauliego i jest trudniejszy dla NISQ.",
        )
    )
    story.append(p(styles, "3.4. Siatka co 0,01 a całkowita liczba kroków", "h2"))
    story.append(
        p(
            styles,
            "Nominalny krok Δt jest przeszukiwany co 0,01. Jeśli t/Δt nie jest całkowite, ostatni krok jest dodatnią resztą, tak aby czasy sumowały się dokładnie do t. To ważne: nie porównujemy obwodów o różnych czasach fizycznych. Jednocześnie głębokość jest schodkowa, bo liczba kroków zmienia się tylko po przekroczeniu kolejnego progu całkowitego.",
        )
    )
    story.extend(chart(styles, "trotter_scaling.png", 168, "Rysunek 1. Rzeczywista siatka profilu smoke. Funkcja celu zmienia się ciągle z nominalnym krokiem, ale proxy-depth pozostaje funkcją schodkową liczby slice'ów."))
    story.append(
        callout(
            styles,
            "Najważniejszy kompromis",
            "Mniejsze Δt zwykle zmniejsza błąd formuły iloczynowej, lecz zwiększa liczbę bramek. Na zaszumionym urządzeniu dokładniejsza matematycznie symulacja może dać gorszy model, ponieważ dodatkowe bramki zwiększają błąd sprzętowy i zmniejszają liczbę shots przypadającą na ustawienie.",
            warning=True,
        )
    )

    story.extend(section(styles, "4", "Fidelity, projected i klasyczny RBF"))
    story.append(p(styles, "4.1. Fidelity kernel", "h2"))
    story.append(eq(styles, "K<sub>F</sub>(x,z)=|⟨ψ(x)|ψ(z)⟩|<super>2</super>=Tr[ρ(x)ρ(z)], &nbsp; ρ(x)=|ψ(x)⟩⟨ψ(x)|."))
    story.append(
        p(
            styles,
            "Równość po prawej pokazuje dodatnią półokreśloność: K<sub>F</sub> jest zwykłym iloczynem skalarnym operatorów gęstości w przestrzeni Hilberta-Schmidta. Jest to dokładnie mechanizm kwantowej mapy cech opisany w pracach Schuld-Killoran i Havlíčka i współautorów [4,5].",
        )
    )
    story.append(
        p(
            styles,
            "Na obwodzie bramkowym stosujemy compute-uncompute: przygotowujemy U(x), następnie U(z)<super>†</super> i mierzymy prawdopodobieństwo samych zer. To prawdopodobieństwo jest równe fidelity. Cena: każdy circuit-shot zawiera dwie mapy cech.",
        )
    )
    story.append(p(styles, "4.2. Projected kernel", "h2"))
    story.append(eq(styles, "m(x)=(⟨X<sub>1</sub>⟩,⟨Y<sub>1</sub>⟩,⟨Z<sub>1</sub>⟩,…,⟨Z<sub>n</sub>⟩),"))
    story.append(eq(styles, "K<sub>P</sub>(x,z)=exp[-γ · ½‖m(x)-m(z)‖<sub>2</sub><super>2</super>]."))
    story.append(
        p(
            styles,
            "Projected kernel celowo wyrzuca korelacje wyższych rzędów i zachowuje jedynie lokalne zredukowane stany jednokubitowe. To jest regularizacja informacyjna: przestrzeń cech jest mniejsza, ale każdą próbkę mierzymy w trzech bazach X/Y/Z i wykorzystujemy wspólne bitstringi do wszystkich kubitów. Koszt obwodów rośnie liniowo z liczbą próbek, a nie kwadratowo z liczbą par.",
        )
    )
    story.append(p(styles, "4.3. Klasyczny RBF", "h2"))
    story.append(eq(styles, "K<sub>RBF</sub>(x,z)=exp[-γ‖x-z‖<sub>2</sub><super>2</super>]."))
    story.append(
        p(
            styles,
            "RBF nie jest dodatkiem kosmetycznym. Jest obowiązkowym testem, czy złożona mapa kwantowa wnosi coś ponad dobrze znaną nieliniową mapę klasyczną. W benchmarku dodano również modele liniowe, boosting i random Fourier features [8], przy identycznym budżecie 12 konfiguracji strojenia.",
        )
    )

    story.extend(section(styles, "5", "Skończona liczba pomiarów i naprawa PSD"))
    story.append(p(styles, "5.1. Shot noise", "h2"))
    story.append(
        p(
            styles,
            "Pojedynczy wpis fidelity jest prawdopodobieństwem p wyniku 0…0. Dla s shots estymator jest średnią zmiennych Bernoulliego. Jest nieobciążony, ale jego wariancja nie znika bez zwiększania budżetu.",
        )
    )
    story.append(eq(styles, "K̂<sub>ij</sub>=C<sub>ij</sub>/s<sub>ij</sub>, &nbsp;&nbsp; Var(K̂<sub>ij</sub>)=K<sub>ij</sub>(1-K<sub>ij</sub>)/s<sub>ij</sub>."))
    story.append(
        p(
            styles,
            "Dla projected kernel wynik pomiaru obserwabli Pauliego przyjmuje wartości ±1. Jeżeli średnia wynosi m, wariancja średniej z s shots wynosi (1-m<super>2</super>)/s. W implementacji wszystkie lokalne obserwable danej bazy są wyznaczane ze wspólnych surowych bitstringów, więc zachowane są ich korelacje pomiarowe.",
        )
    )
    story.append(p(styles, "5.2. Dlaczego surowa macierz może przestać być PSD", "h2"))
    story.append(
        p(
            styles,
            "Idealna macierz Grama jest PSD, lecz każdy jej element jest szacowany z osobnego eksperymentu. Niezależne odchylenia mogą utworzyć ujemne wartości własne. Pipeline publikuje trzy poziomy zamiast ukrywać problem:",
        )
    )
    story.append(eq(styles, "K<sub>raw</sub>=QΛQ<super>T</super>, &nbsp; K<sub>PSD</sub>=Q max(Λ,0) Q<super>T</super>,"))
    story.append(eq(styles, "K<sub>spectral</sub>=Q diag[λ<sub>i</sub>·1(λ<sub>i</sub>&gt;τλ<sub>max</sub>)] Q<super>T</super>."))
    for text in [
        "raw: to, co faktycznie zmierzono; może być nie-PSD;",
        "PSD: ujemne kierunki są obcięte do zera;",
        "spectral: dodatkowo usuwane są bardzo małe dodatnie kierunki, które wzmacniają szum przy odwracaniu macierzy.",
    ]:
        story.append(bullet(styles, text))
    story.append(
        callout(
            styles,
            "Mierzona diagonala",
            "Nie zakładamy automatycznie K(x,x)=1. Diagonala fidelity jest osobno mierzona i zapisywana. Dzięki temu błędy przygotowania stanu i odczytu nie są ukrywane przez ręczne wpisanie jedynek.",
        )
    )

    story.extend(section(styles, "6", "Uczciwy model selection i nested repeated CV"))
    story.append(p(styles, "6.1. Dlaczego zwykłe CV nie wystarcza", "h2"))
    story.append(
        p(
            styles,
            "Jeżeli ten sam fold służy do wyboru konfiguracji i raportowania jej wyniku, maksymalizacja po wielu konfiguracjach wybiera również przypadkowo korzystny szum. Nested CV oddziela te zadania: inner folds wybierają hiperparametry, outer fold ocenia już zamrożony wybór [7].",
        )
    )
    story.append(eq(styles, "θ̂<sub>r,f</sub>=argmin<sub>θ∈Θ</sub> L<sub>inner</sub>(θ), &nbsp;&nbsp; score<sub>r,f</sub>=BA<sub>outer-test</sub>(θ̂<sub>r,f</sub>)."))
    protocol_rows = [
        ["Element", "Zamrożona wartość"],
        ["Zbiory", "moons, WDBC, wine"],
        ["Outer CV", "5 powtórzeń × 5 foldów = 75 splitów"],
        ["Inner CV", "3 foldy"],
        ["Szum pomiarowy", "5 replik na split i budżet"],
        ["Budżety", "200 000 i 1 000 000 circuit-shots"],
        ["Strojenie", "12 konfiguracji na każdą rodzinę"],
        ["Test główny", "jednostronny sign-flip, klaster dataset-powtórzenie"],
        ["Przedział", "hierarchiczny bootstrap percentylowy, 10 000 replik"],
    ]
    story.append(make_table(styles, protocol_rows, [48 * mm, 121 * mm]))
    story.append(p(styles, "6.2. Cztery osie kosztu", "h2"))
    story.append(eq(styles, "B<sub>shots</sub>=Σ<sub>c</sub>s<sub>c</sub>, &nbsp; B<sub>maps</sub>=Σ<sub>c</sub>s<sub>c</sub>m<sub>c</sub>, &nbsp; B<sub>2Q</sub>=Σ<sub>c</sub>s<sub>c</sub>g<sub>2Q,c</sub>."))
    for text in [
        "circuit-shots: liczba wszystkich pojedynczych wykonań obwodów;",
        "map executions: fidelity ma dwie mapy na shot, projected jedną;",
        "2Q-gate-shots: liczba bramek splatających pomnożona przez shots;",
        "QPU time/credits: rzeczywista telemetria backendu, a nie symulacyjny proxy.",
    ]:
        story.append(bullet(styles, text))
    story.append(
        callout(
            styles,
            "Równość nie jest jedna",
            "Dwa modele mogą dostać dokładnie 1 000 000 circuit-shots, lecz wykonywać różną liczbę map cech, bramek 2Q i sekund QPU. Dlatego uczciwy benchmark raportuje wszystkie cztery osie, zamiast utożsamiać shots z całym kosztem.",
            warning=True,
        )
    )

    story.extend(section(styles, "7", "Siatka t, J, g i topologii"))
    story.append(
        p(
            styles,
            "Pierwszy rozbudowany eksperyment badał 63 unikalne konfiguracje Hamiltonianu Isinga określone przez czas t, siłę oddziaływania J, pole poprzeczne g oraz topologię chain/ring/all-to-all. Alignment liczono na train, najlepsi kandydaci przechodzili do validation, a test wykonywano jednokrotnie po wyborze.",
        )
    )
    grid_rows = [
        ["Zakres", "Wartość zweryfikowana audytem"],
        ["Kandydaci", "63"],
        ["Screening", "3780 unikalnych wierszy"],
        ["Finaliści validation", "480"],
        ["Idealne oceny testowe", "90"],
        ["Finite-shot przy równym budżecie", "360 wierszy, 180 par fidelity/projected"],
        ["Audyt", f"{grid_audit['passed']}/{grid_audit['total']} PASS"],
    ]
    story.append(make_table(styles, grid_rows, [60 * mm, 109 * mm]))
    story.extend(chart(styles, "equal_budget.png", 166, "Rysunek 2. Wynik etapu siatkowego: projected jest szczególnie odporny na ograniczony budżet dla moons; dla WDBC przy 200 tys. shots przewaga nie występuje."))
    story.append(
        p(
            styles,
            "Najważniejszy wynik tego etapu nie brzmi „projected zawsze wygrywa”. Brzmi: koszt par fidelity rośnie szybko, przez co przy wspólnym budżecie na pojedynczy obwód przypada mało shots. Projected wykorzystuje mniej ustawień i może oszacować stabilniejsze cechy. Efekt zależy jednak od datasetu i budżetu.",
        )
    )

    story.extend(section(styles, "8", "Pełny benchmark resource-aware"))
    story.append(p(styles, "8.1. Wynik potwierdzający", "h2"))
    primary = full["primary_inference"]
    interval = primary["interval"]
    test = primary["test"]
    story.append(eq(styles, "Δ = BA<sub>projected</sub> - BA<sub>fidelity</sub>, &nbsp; H<sub>0</sub>:E[Δ]≤0, &nbsp; H<sub>1</sub>:E[Δ]&gt;0."))
    story.append(
        p(
            styles,
            f"Dla zamrożonego budżetu 1 000 000 circuit-shots średnia sparowana różnica wyniosła <b>{test['estimate']:.5f}</b>. Hierarchiczny 95% przedział wyniósł [{interval['ci_lower']:.5f}; {interval['ci_upper']:.5f}], a jednostronny test sign-flip dał p={test['p_value_one_sided']:.7f}. W ramach zamrożonego protokołu odrzucono H<sub>0</sub>.",
        )
    )
    story.append(
        callout(
            styles,
            "Dokładne znaczenie wyniku",
            "Projected kernel był średnio bardziej odporny na skończony budżet pomiarowy niż fidelity kernel dla trzech ustalonych zadań i tego pipeline'u. Nie jest to dowód przewagi kwantowej ani twierdzenie o populacji wszystkich datasetów.",
        )
    )
    story.append(p(styles, "8.2. Baseline'y zmieniają interpretację", "h2"))
    story.extend(chart(styles, "model_accuracy.png", 168, "Rysunek 3. Średnia balanced accuracy pełnego benchmarku. Klasyczny SVM-RBF osiąga najwyższy wynik; projected 1 mln shots jest lepszy od fidelity 1 mln, lecz słabszy od najmocniejszych baseline'ów."))
    summary_rows = [
        ["Model", "Średnia BA"],
        ["SVM-RBF", "0,97754"],
        ["Random Fourier features", "0,97321"],
        ["Ideal fidelity", "0,97398"],
        ["Ideal projected", "0,97385"],
        ["Projected, 1 mln shots", "0,95892"],
        ["Fidelity, 1 mln shots", "0,87336"],
    ]
    story.append(make_table(styles, summary_rows, [90 * mm, 40 * mm]))
    story.append(
        p(
            styles,
            "To rozróżnienie jest centralne. Projekt wykazał przewagę <i>estymacyjną</i> projected nad fidelity przy równym budżecie. Nie wykazał lepszej granicy decyzyjnej niż klasyczne RBF. Taka ostrożność jest zgodna z aktualnymi standardami benchmarkowania QML [9].",
        )
    )
    story.append(p(styles, "8.3. Skala artefaktów", "h2"))
    artifact_rows = [
        ["Artefakt", "Liczba/status"],
        ["Outer splity", str(full["outer_split_artifact_count"])],
        ["Wiersze strojenia", str(full["tuning_row_count"])],
        ["Wiersze wynikowe", str(full["row_count"])],
        ["Macierze raw/PSD/spectral", "1500, po 750 dla fidelity i projected"],
        ["Hash protokołu", full["protocol_hash"]],
        ["Audyt pełny", "PASS po korekcie licznika kosztu 2Q"],
    ]
    story.append(make_table(styles, artifact_rows, [58 * mm, 111 * mm]))
    story.append(
        p(
            styles,
            "Audyt wykrył błąd czysto księgowy: konfiguracjom J=0 przypisano koszt bramek 2Q, mimo że generator ich nie emitował. Skorygowano 264 wiersze kosztowe bez zmiany splitów, macierzy i metryk. To przykład, dlaczego audyt ma być niezależny od autora pipeline'u.",
        )
    )

    story.extend(section(styles, "9", "Warstwa sprzętowa i pilot IBM Quantum"))
    story.append(p(styles, "9.1. Od macierzy do rzeczywistego urządzenia", "h2"))
    story.append(
        p(
            styles,
            "Wersja sprzętowa nie wysyła macierzy H do chmury. Każdy eksponent Pauliego jest rozkładany na bramki bazowe, obwód logiczny jest transpilowany do ISA backendu, a wynik jest mierzony przez SamplerV2. Warstwa providerów obejmuje IBM, IonQ, Amazon Braket, Aer, PennyLane i Braket Local. IonQ native został sprawdzony pod kątem operacji ZZ; Xanadu został jawnie odrzucony jako backend dla obwodu kubitowego.",
        )
    )
    flow_rows = [
        ["Krok", "Co jest zapisywane"],
        ["1. Zamrożenie workloadu", "ID, próbki, etykiety, konfiguracja i budżet"],
        ["2. Obwód logiczny", "OpenQASM 3 oraz logical QPY"],
        ["3. Transpilacja", "ISA QPY, seed 20260903, optimization level 1"],
        ["4. Mapowanie", "wspólny layout fizyczny (89, 90, 91, 98)"],
        ["5. Kontekst backendu", "snapshot Target/kalibracji i SHA-256"],
        ["6. Wykonanie", "job IDs, surowe counts, quantum seconds"],
        ["7. Analiza", "raw/PSD/spectral, widma, BA i błąd kernela"],
    ]
    story.append(make_table(styles, flow_rows, [46 * mm, 123 * mm]))
    story.append(p(styles, "9.2. Zrealizowany pilot IBM Kingston", "h2"))
    fid_axes = ibm_fid_exec["resource_axes"]
    proj_axes = ibm_proj_exec["resource_axes"]
    ibm_rows = [
        ["Wielkość", "Fidelity", "Projected"],
        ["Circuit-shots", f"{fid_axes['circuit_shots']:,}".replace(",", " "), f"{proj_axes['circuit_shots']:,}".replace(",", " ")],
        ["Map executions", f"{fid_axes['map_executions']:,}".replace(",", " "), f"{proj_axes['map_executions']:,}".replace(",", " ")],
        ["2Q-gate-shots", f"{fid_axes['two_qubit_gate_shots']:,}".replace(",", " "), f"{proj_axes['two_qubit_gate_shots']:,}".replace(",", " ")],
        ["QPU seconds", f"{fid_axes['qpu_time_seconds']:.3f}", f"{proj_axes['qpu_time_seconds']:.3f}"],
        ["Balanced accuracy", f"{ibm_fid['classification']['test_balanced_accuracy']:.3f}", f"{ibm_proj['classification']['test_balanced_accuracy']:.3f}"],
        ["Idealna BA", f"{ibm_fid['classification']['ideal_test_balanced_accuracy']:.3f}", f"{ibm_proj['classification']['ideal_test_balanced_accuracy']:.3f}"],
        ["Test kernel error", f"{ibm_fid['kernel_error']['test_relative_frobenius']:.3f}", f"{ibm_proj['kernel_error']['test_relative_frobenius']:.3f}"],
    ]
    story.append(make_table(styles, ibm_rows, [62 * mm, 53 * mm, 53 * mm]))
    story.extend(chart(styles, "ibm_pilot.png", 165, "Rysunek 4. Wspólny layout IBM Kingston. Projected zachował wynik idealny na czterech próbkach testowych; fidelity spadł do 0,5. Próba jest zbyt mała do wnioskowania statystycznego."))
    story.append(
        callout(
            styles,
            "Dlaczego fidelity ma 0 bramek 2Q w tym pilocie?",
            "Zamrożona konfiguracja fidelity miała J=0. To nie jest błąd licznika, lecz słabość pilota: nie testuje on splątującej dynamiki. Projected użył J≠0 i wykonał 480 000 2Q-gate-shots. Pilot waliduje estymatory i reprodukowalność, nie porównuje dwóch identycznych obwodów fizycznych.",
            warning=True,
        )
    )
    story.append(
        p(
            styles,
            f"Niezależny audyt wspólnego layoutu zakończył się wynikiem <b>{hardware_audit['passed']}/{hardware_audit['total']} PASS</b>. Audyt potwierdził mierzoną diagonalę fidelity, budżety po 20 000 shots, QPY/ISA, wspólny layout, cztery osie kosztu oraz brak danych uwierzytelniających w manifestach.",
        )
    )

    story.extend(section(styles, "10", "Osobny kernel fotoniczny CV/GBS"))
    story.append(p(styles, "10.1. Dlaczego X8 nie jest zamiennikiem czterech kubitów", "h2"))
    story.append(
        p(
            styles,
            "Xanadu X8 jest ośmiomodowym układem fotonicznym Gaussian Boson Sampling. Jego naturalną przestrzenią jest baza Focka |n<sub>1</sub>,…,n<sub>8</sub>⟩ o nieograniczonej liczbie fotonów, a nie 2<super>n</super>-wymiarowa przestrzeń kubitowa. Przeniesienie RX/RZ/RZZ na X8 i nazwanie wyniku tym samym kernelem byłoby niepoprawne. Zbudowano więc osobną hipotezę metodyczną CV/GBS [10,11].",
        )
    )
    story.append(p(styles, "10.2. Od stanu Gaussowskiego do prawdopodobieństwa PNR", "h2"))
    story.append(
        p(
            styles,
            "Cztery pary two-mode squeezed vacuum są mieszane przez interferometr. Dla wzorca photon-number-resolving n prawdopodobieństwo idealne jest związane z hafnianem macierzy otrzymanej przez powtórzenie wierszy i kolumn zgodnie z obsadzeniami fotonowymi [10]. Schematycznie:",
        )
    )
    story.append(eq(styles, "Pr(n) ∝ |Haf(A<sub>n</sub>)|<super>2</super> / [n<sub>1</sub>!⋯n<sub>m</sub>!]."))
    story.append(
        p(
            styles,
            "Kernel Hellingera używa amplitud √p<sub>n</sub>, natomiast moment-RBF używa momentów liczby fotonów. Oba są budowane z tych samych surowych rekordów PNR. Jawny bin overflow przechowuje zdarzenia powyżej cutoff, zamiast wyrzucać je i renormalizować rozkład w sposób ukrywający straty informacji.",
        )
    )
    photonic_rows = [
        ["Element", "Wynik smoke"],
        ["Obwody / budżet", "18 / 12 000 raw PNR shots"],
        ["Zaakceptowane zdarzenia", "11 703; odrzucone 297"],
        ["Hellinger BA", "ideal 1,000; finite-shot 0,667"],
        ["Moment-RBF BA", "ideal 1,000; finite-shot 0,333"],
        ["Klasyczny RBF BA", "1,000"],
        ["Audyt", f"{photonic_audit['summary']['passed']}/{photonic_audit['summary']['total']} PASS"],
    ]
    story.append(make_table(styles, photonic_rows, [65 * mm, 104 * mm]))
    story.extend(chart(styles, "photonic.png", 155, "Rysunek 5. Lokalny eksperyment finite-shot CV/GBS. Wynik nie pochodzi z QPU Xanadu; publiczna chmura X8 jest wycofana."))
    story.append(p(styles, "10.3. Odporność: co zostało przygotowane", "h2"))
    for text in [
        "cutoff sweep i jawny overflow;",
        "straty kanału oraz sprawność kwantowa detektora;",
        "detektory PNR, threshold, saturation i dark counts;",
        "pattern, moment, event i orbit features na wspólnych zdarzeniach;",
        "adapter Strawberry Fields 0.23 w izolowanym środowisku Python 3.10.",
    ]:
        story.append(bullet(styles, text))
    story.append(
        callout(
            styles,
            "Granica wyniku",
            "Audyt 10/10 potwierdził matematykę hafnianową, unitarność interferometrów, wspólny budżet i brak fałszywego oznaczenia QPU. Nie potwierdził odporności na realnym urządzeniu fotonicznym.",
            warning=True,
        )
    )

    story.extend(section(styles, "11", "Skalowanie optymalnej polityki Trottera"))
    story.append(p(styles, "11.1. Zamrożona hipoteza", "h2"))
    story.append(eq(styles, "π<super>*</super>(n,D<sub>max</sub>) = argmin<sub>(p,Δt): D(p,Δt,n)≤D<sub>max</sub></sub> J(p,Δt;n,D<sub>max</sub>)."))
    story.append(
        p(
            styles,
            "Polityka π<super>*</super> wybiera rząd p i nominalny krok Δt. Hipoteza mówi, że wybór zależy od liczby kubitów n i zewnętrznego budżetu głębokości D<sub>max</sub>. Nie badamy przyczynowego wpływu głębokości, ponieważ sama trotteryzacja generuje głębokość.",
        )
    )
    story.append(eq(styles, "J = 0,55(1-BA<sub>val</sub>) + 0,15I<sub>state</sub> + 0,20E<sub>kernel</sub> + 0,10D/D<sub>max</sub>."))
    story.append(p(styles, "11.2. Dane i optymalizatory", "h2"))
    story.append(
        p(
            styles,
            "Założenie idealnych anotacji zrealizowano przez deterministycznego nauczyciela, brak szumu etykiet, balans klas i minimalny margines 0,3053. Hash danych i Hamiltonianów jest zamrożony. Kandydaci nie zawierają metryki testowej.",
        )
    )
    optimizer_rows = [
        ["Ramię", "Rola"],
        ["Exhaustive grid", "Dokładne minimum referencyjne siatki 0,01"],
        ["Quadratic surrogate", "a+bΔt+cΔt² uczone wyłącznie na pilocie"],
        ["Exact shortlist QUBO", "Dokładne rozwiązanie one-hot QUBO"],
        ["Simulated annealing", "Klasyczna kontrola Metropolisa"],
        ["QAOA p=1", "Dokładna symulacja statevector tego samego QUBO"],
    ]
    story.append(make_table(styles, optimizer_rows, [57 * mm, 112 * mm]))
    story.append(eq(styles, "E(z)=Σ<sub>i</sub>s<sub>i</sub>z<sub>i</sub> + λ(Σ<sub>i</sub>z<sub>i</sub>-1)<super>2</super>."))
    story.append(
        p(
            styles,
            "QAOA stosuje naprzemiennie Hamiltonian kosztu i mikser X, zgodnie ze schematem Farhiego, Goldstone'a i Gutmanna [6]. W tym projekcie jest to ramię metodologiczne na statevectorze, nie wynik z QPU i nie dowód przewagi dla trywialnego one-hot selection.",
        )
    )
    story.append(eq(styles, "|γ,β⟩ = e<super>-iβΣX<sub>j</sub></super> e<super>-iγH<sub>C</sub></super>|+⟩<super>⊗q</super>."))
    story.append(p(styles, "11.3. Wynik smoke", "h2"))
    scale_rows = [
        ["n", "Składniki", "D<sub>max</sub>", "Wybrane p", "Wybrane Δt", "Proxy-depth"],
        ["2", "15", "900", "2", "1,00", "127"],
        ["2", "15", "1800", "2", "1,00", "127"],
        ["3", "63", "900", "1", "1,00", "417"],
        ["3", "63", "1800", "1", "1,00", "417"],
    ]
    story.append(make_table(styles, scale_rows, [16 * mm, 28 * mm, 27 * mm, 27 * mm, 34 * mm, 37 * mm]))
    story.append(
        p(
            styles,
            f"Pipeline wygenerował {trotter['candidate_rows']} wierszy kandydatów i {trotter['selection_rows']} wyborów. Test permutacyjny dał p={trotter_analysis['permutation_p_value']:.3f}. Status jest <b>descriptive_only</b>, a hipoteza nie została potwierdzona. Audyt przeszedł {trotter_audit['passed']}/{trotter_audit['total']} kontroli.",
        )
    )
    story.append(
        callout(
            styles,
            "Co rzeczywiście zaobserwowano",
            "W smoke optymalny rząd zmienił się między n=2 i n=3, ale Δt=1,00 oraz wybór nie zależały od dwóch badanych budżetów. Cztery warunki to za mało, aby testować zależność skalowania. Poprawny wniosek: framework działa i jest gotowy do profilu full; hipoteza pozostaje otwarta.",
            warning=True,
        )
    )

    story.append(PageBreak())
    story.extend(section(styles, "12", "QuanONet: quantum neural operator jako kierunek komplementarny"))
    story.append(
        callout(
            styles,
            "Status tej części",
            "QuanONet nie został jeszcze zaimplementowany ani uruchomiony w projekcie QML. Poniższy rozdział jest zweryfikowaną analizą publikacji oraz projektem eksperymentu. Nie należy go mylić z dotychczasowymi wynikami Hamiltonian kernels, IBM QPU ani CV/GBS.",
            warning=True,
        )
    )
    story.append(p(styles, "12.1. Od funkcji do operatora", "h2"))
    story.append(
        p(
            styles,
            "Dotychczasowy benchmark rozwiązuje zadanie skończenie wymiarowe: próbka x otrzymuje etykietę y. Neural operator rozwiązuje problem wyższego poziomu. Jego argumentem jest cała funkcja u, a wynikiem inna funkcja G(u). W obliczeniach funkcję wejściową obserwuje się w sensorach X={x<sub>1</sub>,...,x<sub>m</sub>}, lecz model powinien zwracać wartość w dowolnym punkcie zapytania y i zachować sens po zmianie dyskretyzacji [13,15].",
        )
    )
    story.append(eq(styles, "G: V⊂C(D<sub>u</sub>) → C(D<sub>y</sub>), &nbsp;&nbsp; (u,y) ↦ G(u)(y)."))
    story.append(
        p(
            styles,
            "Klasyczny DeepONet koduje próbki u|<sub>X</sub> siecią branch, współrzędną y siecią trunk, a wynik tworzy przez iloczyn skalarny dwóch reprezentacji. QuanONet autorstwa Wanga i współautorów zastępuje obie reprezentacje stanami kwantowymi. Praca konferencyjna z 2025 r. wprowadziła architekturę i twierdzenie aproksymacyjne, a artykuł w Nature Machine Intelligence z 2026 r. rozwinął interpretację gęstościową i analizę ekspresyjności [13,14].",
        )
    )

    story.append(p(styles, "12.2. Obwód branch-trunk i obserwabla wyjściowa", "h2"))
    story.append(eq(styles, "|b<sub>θb</sub>(u)⟩=U<sub>B</sub>(θ<sub>b</sub>,u)|0⟩, &nbsp;&nbsp; |t<sub>θt</sub>(y)⟩=U<sub>T</sub><super>†</super>(θ<sub>t</sub>,y)|0⟩."))
    story.append(
        p(
            styles,
            "W wersji sprzętowo efektywnej bloki kodowania danych, warstwy splątujące i trenowalne ansatze tworzą dwa odcinki tego samego obwodu. Najpierw branch koduje wartości funkcji w sensorach, następnie trunk koduje współrzędną wyjściową. Odczyt jest wartością oczekiwaną hermitowskiej obserwabli H<sub>out</sub>:",
        )
    )
    story.append(eq(styles, "Ĝ<sub>θ</sub>(u)(y)=⟨0|U<sub>B</sub><super>†</super>U<sub>T</sub><super>†</super>H<sub>out</sub>U<sub>T</sub>U<sub>B</sub>|0⟩."))
    story.append(
        p(
            styles,
            "Dla H<sub>out</sub>=|0⟩⟨0| otrzymujemy |⟨t<sub>θt</sub>(y)|b<sub>θb</sub>(u)⟩|<super>2</super>. Dla H<sub>out</sub>=aΣ<sub>i</sub>Z<sub>i</sub>+bI zakres predykcji jest kontrolowany przez [b-na,b+na]. To ważne rozróżnienie: Hamiltonian kodujący dane generuje częstotliwości modelu, natomiast H<sub>out</sub> definiuje skalę odczytu.",
        )
    )

    story.append(p(styles, "12.3. Skąd bierze się implicit quadratic frame", "h2"))
    story.append(
        p(
            styles,
            "Niech p=2<super>n</super> będzie wymiarem stanu, b<sub>i</sub> amplitudami branch, a t<sub>i</sub> amplitudami trunk. Kwadrat nakładania rozwija się w pary indeksów:",
        )
    )
    story.append(eq(styles, "|⟨t|b⟩|<super>2</super>=|Σ<sub>i=1</sub><super>p</super> t<sub>i</sub><super>*</super>b<sub>i</sub>|<super>2</super>=Σ<sub>i,j=1</sub><super>p</super>(t<sub>i</sub><super>*</super>t<sub>j</sub>)(b<sub>i</sub>b<sub>j</sub><super>*</super>)=Tr(ρ<sub>t</sub>ρ<sub>b</sub>)."))
    story.append(
        p(
            styles,
            "Macierz gęstości zawiera zatem do p<super>2</super> elementów i tworzy niejawny kwadratowy układ cech. Artykuł z 2026 r. formułuje dla operatorów granicę ekspresyjności O(p<super>2</super>), przewyższającą liniową pojemność O(p) porównywanych modeli klasycznych przy dopasowanej liczbie parametrów [13]. Jest to twierdzenie o klasie reprezentowanych operatorów, nie dowód przyspieszenia obliczeniowego: odczyt wszystkich p<super>2</super> współczynników tomograficznie byłby kosztowny, a pojedyncza obserwabla daje tylko ich określoną kombinację.",
        )
    )
    story.append(
        callout(
            styles,
            "Powiązanie z fidelity kernel",
            "Równość Tr(ρ<sub>t</sub>ρ<sub>b</sub>) jest algebraicznie tą samą strukturą Hilberta-Schmidta, która stoi za fidelity kernelem. Różni się rola uczenia: kernel pozostawia obwód stały i uczy współczynniki klasyczne, QuanONet iteracyjnie uczy parametry obwodów branch i trunk.",
        )
    )

    story.append(p(styles, "12.4. Trainable frequency i nowa rola Trottera", "h2"))
    story.append(
        p(
            styles,
            "Widmo funkcji realizowanej przez obwód zależy od różnic wartości własnych generatora kodowania. W modelu fixed-frequency generator jest ustalony. TF-QuanONet uczy mnożniki częstotliwości ω, dzięki czemu może nieregularnie rozmieścić częstotliwości i uchwycić składniki wysoko-częstotliwościowe bez mechanicznego zwiększania liczby powtórzeń obwodu [13,16].",
        )
    )
    story.append(eq(styles, "S<sub>ω</sub>(x)=e<super>-ixωH</super>, &nbsp;&nbsp; Ω<sub>ω</sub>={ω(λ<sub>j</sub>-λ<sub>k</sub>)}<sub>j,k</sub>."))
    story.append(
        p(
            styles,
            "Po włączeniu niekomutujących składników do uniwersalnego Hamiltonianu częstotliwości przestają być neutralne dla błędu cyfrowej symulacji. Dla H(x,ω)=Σ<sub>a</sub>ω<sub>a</sub>x<sub>a</sub>H<sub>a</sub> oszacowanie pierwszego rzędu ma postać:",
        )
    )
    story.append(eq(styles, "||U-S<sub>1</sub>|| ≲ (t<super>2</super>/2r) Σ<sub>a&lt;b</sub>|ω<sub>a</sub>x<sub>a</sub>ω<sub>b</sub>x<sub>b</sub>| ||[H<sub>a</sub>,H<sub>b</sub>]||."))
    story.append(
        p(
            styles,
            "Uczenie większych |ω<sub>a</sub>| może więc poprawić dopasowanie widma, ale jednocześnie zwiększyć prefaktor błędu Trottera i wymagany r. To bezpośrednio rozszerza obecną hipotezę projektu: optymalna polityka (rząd, Δt) powinna zależeć nie tylko od n i D<sub>max</sub>, lecz także od wyuczonego promienia widmowego, rozkładu częstotliwości i norm komutatorów.",
        )
    )

    story.append(p(styles, "12.5. Co jest wspólne, a co zasadniczo różne", "h2"))
    comparison_rows = [
        ["Kryterium", "Hamiltonian kernel", "QuanONet / TF-QuanONet"],
        ["Zadanie", "Klasyfikacja/regresja punktów x", "Operator u ↦ G(u), odczyt w y"],
        ["Trening QPU", "Brak; obwód jest mapą cech", "Iteracyjny; parametry branch/trunk i ω"],
        ["Wyjście", "Para próbek: K(x,z)", "Jedna funkcja i punkt: Ĝ(u)(y)"],
        ["Główny koszt", "O(N²) elementów macierzy Grama", "Forward i gradienty przez wiele epok"],
        ["Wspólna fizyka", "Widmo H, topologia, Trotter, shots, ISA", "Te same osie oraz koszt optymalizacji"],
        ["Stan dowodów QML", "Wynik lokalny i pilot IBM", "Publikacja zewnętrzna; brak replikacji lokalnej"],
    ]
    story.append(make_table(styles, comparison_rows, [35 * mm, 64 * mm, 70 * mm]))

    story.append(p(styles, "12.6. Proponowany eksperyment: Hamiltonian Kernel Operator", "h2"))
    story.append(
        p(
            styles,
            "Najbardziej informacyjny test nie polega na samym skopiowaniu QuanONet. Należy zbudować bezwariacyjny odpowiednik operatorowy. Dla pary z=(u|<sub>X</sub>,y) konstruujemy stan Hamiltonianowy ρ<sub>H</sub>(z), a następnie kernel na parach funkcja-punkt:",
        )
    )
    story.append(eq(styles, "K<sub>HKO</sub>((u,y),(v,z))=Tr[ρ<sub>H</sub>(u,y)ρ<sub>H</sub>(v,z)]."))
    story.append(eq(styles, "Ĝ(u)(y)=Σ<sub>i=1</sub><super>N</super>α<sub>i</sub>K<sub>HKO</sub>((u,y),(u<sub>i</sub>,y<sub>i</sub>))+b, &nbsp;&nbsp; α=(K+λI)<super>-1</super>g."))
    story.append(
        p(
            styles,
            "HKO zachowuje ideę uczenia operatora, ale nie wymaga gradientowego strojenia obwodu. Dzięki temu umożliwia bezpośrednią odpowiedź na pytanie, czy przewaga TF-QuanONet wynika z trenowanych częstotliwości i kwadratowej ramy, czy po prostu z bogatej nieliniowej reprezentacji funkcja-punkt.",
        )
    )
    arms_rows = [
        ["Rodzina", "Ramiona", "Cel porównania"],
        ["Klasyczna", "DeepONet, FNO", "Standard operator learning"],
        ["Kernelowa", "HKO exact; Trotter 1/2; fidelity/projected", "Kontrola bez treningu QPU"],
        ["Wariacyjna", "FF-QuanONet, TF-QuanONet", "Wpływ uczonych częstotliwości"],
    ]
    story.append(make_table(styles, arms_rows, [31 * mm, 70 * mm, 68 * mm]))
    story.append(
        p(
            styles,
            "Zbiory treningowy, walidacyjny i testowy muszą być dzielone po całych funkcjach u, nigdy po punktach y tej samej funkcji. Test powinien dodatkowo zawierać niewidzianą rozdzielczość siatki. Zadania startowe to operator antypochodnej, diffusion-reaction, adwekcja i Darcy flow, czyli rodziny obecne w publicznym kodzie QuanONet [14]. Metryki: względny błąd L<sub>2</sub>, MSE, błąd rezydualny PDE, stabilność między seedami oraz generalizacja między rozdzielczościami.",
        )
    )
    story.append(
        p(
            styles,
            "Należy raportować dwa osobne reżimy uczciwości. Pierwszy dopasowuje liczbę parametrów, aby odtworzyć logikę publikacji [13]. Drugi dopasowuje circuit-shots, map executions, 2Q-gate-shots i QPU time/credits. Dla QuanONet budżet obejmuje forwardy i wszystkie obwody gradientu parameter-shift; sama równość parametrów nie oznacza równości kosztu sprzętowego.",
        )
    )
    story.append(eq(styles, "J<sub>op</sub>=E<sub>rel-L2</sub>+λ<sub>s</sub>B<sub>shots</sub>/B<sub>0</sub>+λ<sub>2Q</sub>B<sub>2Q</sub>/B<sub>2Q,0</sub>+λ<sub>t</sub>T<sub>QPU</sub>/T<sub>0</sub>+λ<sub>v</sub>Var<sub>seed</sub>."))
    story.append(
        callout(
            styles,
            "Hipotezy do prerejestracji",
            "H-QNO-1: TF-QuanONet zmniejsza błąd względem FF-QuanONet przy tym samym całkowitym budżecie QPU. H-QNO-2: HKO ma mniejszy spadek jakości finite-shot, lecz wyższy koszt par próbek. H-QNO-3: po włączeniu uczonych częstotliwości optimum Trottera zależy od n, D<sub>max</sub> i norm ważonych komutatorów. Żadna z tych hipotez nie ma obecnie wyniku w projekcie.",
            warning=True,
        )
    )

    story.extend(section(styles, "13", "Audyty, ograniczenia i dalsza ścieżka"))
    story.append(p(styles, "13.1. Bilans niezależnych kontroli", "h2"))
    audit_rows = [
        ["Warstwa", "Wynik", "Co odtworzono niezależnie"],
        ["Siatka t,J,g", f"{grid_audit['passed']}/{grid_audit['total']} PASS", "siatka, budżety, PSD, test isolation"],
        ["Pełny resource-aware", "PASS", "75 splitów, 1950 wyników, 1500 macierzy"],
        ["IBM wspólny layout", f"{hardware_audit['passed']}/{hardware_audit['total']} PASS", "QPY/ISA, layout, shots, QPU time"],
        ["Fotoniczny CV/GBS", f"{photonic_audit['summary']['passed']}/{photonic_audit['summary']['total']} PASS", "hafniany, unitarność, wspólne PNR"],
        ["Skalowanie Trottera", f"{trotter_audit['passed']}/{trotter_audit['total']} PASS", "siatka 0,01, cel, QUBO, brak leakage"],
        ["Regresja repozytorium", "84/84 PASS", "kernel, hardware, fotonika, QRC, Trotter"],
    ]
    story.append(make_table(styles, audit_rows, [42 * mm, 31 * mm, 96 * mm]))
    story.append(p(styles, "13.2. Najważniejsze ograniczenia", "h2"))
    for text in [
        "Pełny wynik potwierdzający obejmuje trzy ustalone datasety; repeated CV nie tworzy nowych niezależnych problemów uczenia.",
        "Klasyczne baseline'y miały równy budżet strojenia, ale wspólny PCA do czterech wymiarów może je ograniczać.",
        "Pilot IBM ma tylko sześć próbek treningowych i cztery testowe na kernel; BA=1,0 nie ma mocy statystycznej.",
        "Fidelity pilot z J=0 nie bada błędów splątujących, więc porównanie QPU nie jest fizycznie symetryczne.",
        "One-hot QUBO jest mały i klasycznie łatwy; QAOA jest demonstracją integracji, nie przewagi.",
        "CV/GBS jest wynikiem lokalnego symulatora finite-shot; brak aktywnego publicznego X8 uniemożliwia uczciwe oznaczenie QPU.",
        "Pełna baza Pauliego rośnie jak 4<super>n</super>-1. Profil full wymaga jawnego capu składników i nie reprezentuje pełnej gęstej rodziny.",
        "QuanONet jest na tym etapie analizą publikacji zewnętrznej. Nie wykonano lokalnej replikacji, a granica O(p<super>2</super>) nie jest sama w sobie dowodem przewagi czasowej ani pomiarowej.",
    ]:
        story.append(bullet(styles, text))
    story.append(p(styles, "13.3. Najsilniejsza ścieżka publikacyjna", "h2"))
    roadmap_rows = [
        ["Priorytet", "Praca"],
        ["1", "Publikacyjny benchmark resource-aware Hamiltonian kernels z większą liczbą niezależnych datasetów."],
        ["2", "Pełny profil hipotezy skalowania Trottera: n=2…6, D<sub>max</sub>, wiele seedów Hamiltonianu i transpilowany depth."],
        ["3", "Osobny benchmark operatorowy: HKO exact/Trotter kontra FF/TF-QuanONet, DeepONet i FNO przy równych zasobach."],
        ["4", "Symetryczny pilot IBM: fidelity i projected z porównywalną dynamiką splątującą oraz snapshotami czasu."],
        ["5", "Osobna praca CV/GBS: factorial loss/cutoff/detector sweep i stabilność event/orbit features."],
        ["6", "Analiza klasycznych baseline'ów z natywnym preprocessingiem i pełnym wymiarem danych."],
    ]
    story.append(make_table(styles, roadmap_rows, [21 * mm, 148 * mm]))
    story.append(
        p(
            styles,
            "Najmocniejsze obecne twierdzenie jest wąskie, ale rzetelne: <b>dla zamrożonego protokołu i tych trzech zadań projected Hamiltonian kernel wykorzystuje skończony budżet pomiarowy skuteczniej niż fidelity kernel</b>. Jednocześnie klasyczny SVM-RBF pozostaje silniejszym predyktorem. To nie osłabia pracy; precyzyjnie lokuje jej wkład w analizie zasobów i odporności estymatora.",
        )
    )

    story.extend(section(styles, "A", "Inwentarz reprodukowalności"))
    inventory_rows = [
        ["Artefakt", "Identyfikator"],
        ["Pełny protokół resource-aware", full["protocol_hash"]],
        ["Protokół skalowania Trottera", trotter["protocol_hash"]],
        ["Workload IBM fidelity", ibm_fid["workload_id"]],
        ["Workload IBM projected", ibm_proj["workload_id"]],
        ["IBM backend/layout", "ibm_kingston / (89, 90, 91, 98)"],
        ["Seed transpile", str(ibm_fid_exec["transpile_seed"])],
        ["Workload fotoniczny", photonic_audit["checks"][0]["detail"].split()[3]],
    ]
    story.append(make_table(styles, inventory_rows, [59 * mm, 110 * mm]))
    story.append(p(styles, "Kluczowe katalogi projektu", "h2"))
    for text in [
        "hamiltonian_kernel/: ewolucja, estymatory, protokoły, benchmark i providery;",
        "photonic_kernel/: model CV/GBS, hafniany, cechy i odporność;",
        "analysis_output/resource_aware_hamiltonian_benchmark/: pełny wynik i macierze;",
        "analysis_output/ibm_validation_*_v2/: workloady, QPY/ISA, counts i wyniki IBM;",
        "analysis_output/trotter_scaling_smoke/: siatka 0,01, QUBO i audyt;",
        "audits/: niezależne rekonstrukcje i bramki integralności.",
    ]:
        story.append(bullet(styles, text))

    story.extend(section(styles, "B", "Słownik pojęć"))
    glossary_rows = [
        ["Pojęcie", "Znaczenie"],
        ["Hamiltonian", "Hermitowski generator ewolucji U(t)=e<super>-itH</super>."],
        ["Trotteryzacja", "Zastąpienie eksponenty sumy iloczynem prostszych eksponent."],
        ["Kernel", "Funkcja podobieństwa będąca macierzą Grama mapy cech."],
        ["Fidelity", "Kwadrat modułu nakładania dwóch stanów czystych."],
        ["Projected", "Kernel zbudowany z lokalnych obserwabli zredukowanego stanu."],
        ["PSD", "Macierz dodatnio półokreślona: v<super>T</super>Kv≥0."],
        ["Shot", "Pojedyncze przygotowanie, wykonanie i pomiar obwodu."],
        ["ISA", "Zestaw instrukcji i ograniczeń konkretnego backendu."],
        ["QUBO", "Quadratic Unconstrained Binary Optimization."],
        ["QAOA", "Naprzemienny obwód koszt-mikser dla problemu kombinatorycznego."],
        ["GBS", "Gaussian Boson Sampling z wejściami Gaussowskimi i detekcją fotonów."],
        ["Hafnian", "Funkcja macierzowa wyznaczająca amplitudy wzorców GBS."],
        ["Neural operator", "Model uczący odwzorowanie między przestrzeniami funkcji, a nie pojedynczą funkcję."],
        ["QuanONet", "Kwantowy neural operator z obwodami branch/trunk i odczytem obserwabli."],
        ["TF", "Trainable frequency: uczenie widma generatorów kodowania danych."],
    ]
    story.append(make_table(styles, glossary_rows, [39 * mm, 130 * mm]))

    story.extend(section(styles, "C", "Bibliografia"))
    references = [
        "[1] S. Lloyd, <i>Universal Quantum Simulators</i>, Science 273, 1073-1078 (1996). DOI: <link href='https://doi.org/10.1126/science.273.5278.1073'>10.1126/science.273.5278.1073</link>.",
        "[2] M. Suzuki, <i>Fractal decomposition of exponential operators with applications to many-body theories and Monte Carlo simulations</i>, Physics Letters A 146, 319-323 (1990). DOI: <link href='https://doi.org/10.1016/0375-9601(90)90962-N'>10.1016/0375-9601(90)90962-N</link>.",
        "[3] A. M. Childs, Y. Su, M. C. Tran, N. Wiebe, S. Zhu, <i>Theory of Trotter Error with Commutator Scaling</i>, Physical Review X 11, 011020 (2021). DOI: <link href='https://doi.org/10.1103/PhysRevX.11.011020'>10.1103/PhysRevX.11.011020</link>.",
        "[4] M. Schuld, N. Killoran, <i>Quantum Machine Learning in Feature Hilbert Spaces</i>, Physical Review Letters 122, 040504 (2019). DOI: <link href='https://doi.org/10.1103/PhysRevLett.122.040504'>10.1103/PhysRevLett.122.040504</link>.",
        "[5] V. Havlíček et al., <i>Supervised learning with quantum-enhanced feature spaces</i>, Nature 567, 209-212 (2019). DOI: <link href='https://doi.org/10.1038/s41586-019-0980-2'>10.1038/s41586-019-0980-2</link>.",
        "[6] E. Farhi, J. Goldstone, S. Gutmann, <i>A Quantum Approximate Optimization Algorithm</i>, arXiv:1411.4028 (2014). <link href='https://arxiv.org/abs/1411.4028'>arxiv.org/abs/1411.4028</link>.",
        "[7] S. Varma, R. Simon, <i>Bias in error estimation when using cross-validation for model selection</i>, BMC Bioinformatics 7, 91 (2006). DOI: <link href='https://doi.org/10.1186/1471-2105-7-91'>10.1186/1471-2105-7-91</link>.",
        "[8] A. Rahimi, B. Recht, <i>Random Features for Large-Scale Kernel Machines</i>, Advances in Neural Information Processing Systems 20 (2007). <link href='https://papers.nips.cc/paper/3182-random-features-for-large-scale-kernel-machines'>paper</link>.",
        "[9] J. Bowles, S. Ahmed, M. Schuld, <i>Better than classical? The subtle art of benchmarking quantum machine learning models</i>, arXiv:2403.07059 (2024). <link href='https://arxiv.org/abs/2403.07059'>arxiv.org/abs/2403.07059</link>.",
        "[10] C. S. Hamilton et al., <i>Gaussian Boson Sampling</i>, Physical Review Letters 119, 170501 (2017). DOI: <link href='https://doi.org/10.1103/PhysRevLett.119.170501'>10.1103/PhysRevLett.119.170501</link>.",
        "[11] A. P. Lund et al., <i>Boson Sampling from a Gaussian State</i>, Physical Review Letters 113, 100502 (2014). DOI: <link href='https://doi.org/10.1103/PhysRevLett.113.100502'>10.1103/PhysRevLett.113.100502</link>.",
        "[12] J. Preskill, <i>Quantum Computing in the NISQ era and beyond</i>, Quantum 2, 79 (2018). DOI: <link href='https://doi.org/10.22331/q-2018-08-06-79'>10.22331/q-2018-08-06-79</link>.",
        "[13] R. Wang, X. Zhong, Z. Xia, J. Yan, <i>Quantum neural operators with implicit quadratic frame and expressivity advantages</i>, Nature Machine Intelligence (2026). DOI: <link href='https://doi.org/10.1038/s42256-026-01289-7'>10.1038/s42256-026-01289-7</link>.",
        "[14] R. Wang, Z. Xia, G. Yan, J. Yan, <i>QuanONet: Quantum Neural Operator with Application to Differential Equation</i>, Proceedings of the 42nd International Conference on Machine Learning, PMLR 267, 64955-64975 (2025). <link href='https://proceedings.mlr.press/v267/wang25dq.html'>proceedings.mlr.press/v267/wang25dq.html</link>.",
        "[15] L. Lu, P. Jin, G. Pang, Z. Zhang, G. E. Karniadakis, <i>Learning nonlinear operators via DeepONet based on the universal approximation theorem of operators</i>, Nature Machine Intelligence 3, 218-229 (2021). DOI: <link href='https://doi.org/10.1038/s42256-021-00302-5'>10.1038/s42256-021-00302-5</link>.",
        "[16] B. Jaderberg, A. A. Gentile, Y. A. Berrada, E. Shishenina, V. E. Elfving, <i>Let quantum neural networks choose their own frequencies</i>, Physical Review A 109, 042421 (2024). DOI: <link href='https://doi.org/10.1103/PhysRevA.109.042421'>10.1103/PhysRevA.109.042421</link>.",
    ]
    for reference in references:
        story.append(p(styles, reference, "ref"))
    story.append(Spacer(1, 5 * mm))
    story.append(
        p(
            styles,
            "Koniec raportu. Wszystkie liczby empiryczne pochodzą z artefaktów projektu QML wskazanych w dodatku A. Bibliografia służy zakotwiczeniu definicji i metod w publikacjach, a nie zastępuje audytu lokalnych wyników.",
            "small",
        )
    )
    return story


def main() -> None:
    register_fonts()
    styles = make_styles()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    document = BaseDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=19 * mm,
        rightMargin=19 * mm,
        topMargin=19 * mm,
        bottomMargin=17 * mm,
        title="Resource-aware Hamiltonian Quantum Kernels - raport dotychczasowych osiągnięć",
        author="Projekt QML",
        subject="Hamiltonian quantum kernels, Trotterization, QML benchmarking, IBM QPU, CV/GBS, QuanONet",
    )
    frame = Frame(
        document.leftMargin,
        document.bottomMargin,
        document.width,
        document.height,
        id="main",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    document.addPageTemplates(PageTemplate(id="report", frames=[frame], onPage=on_page))
    document.build(build_story(styles))
    print(json.dumps({"output": str(OUT), "bytes": OUT.stat().st_size}, ensure_ascii=False))


if __name__ == "__main__":
    main()
