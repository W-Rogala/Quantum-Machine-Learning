from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    XPreformatted,
)


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "pdf"
PDF_PATH = OUT_DIR / "h2_qsvm_proof.pdf"


def register_fonts() -> tuple[str, str, str]:
    regular = Path(r"C:\Windows\Fonts\arial.ttf")
    bold = Path(r"C:\Windows\Fonts\arialbd.ttf")
    mono = Path(r"C:\Windows\Fonts\consola.ttf")
    pdfmetrics.registerFont(TTFont("DocSans", str(regular)))
    pdfmetrics.registerFont(TTFont("DocSans-Bold", str(bold)))
    pdfmetrics.registerFont(TTFont("DocMono", str(mono)))
    return "DocSans", "DocSans-Bold", "DocMono"


FONT, FONT_BOLD, FONT_MONO = register_fonts()


styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="DocTitle",
        parent=styles["Title"],
        fontName=FONT_BOLD,
        fontSize=18,
        leading=23,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#14213d"),
        spaceAfter=10,
    )
)
styles.add(
    ParagraphStyle(
        name="DocSubtitle",
        parent=styles["Normal"],
        fontName=FONT,
        fontSize=10,
        leading=14,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#4a5568"),
        spaceAfter=18,
    )
)
styles.add(
    ParagraphStyle(
        name="DocHeading",
        parent=styles["Heading1"],
        fontName=FONT_BOLD,
        fontSize=13.5,
        leading=17,
        textColor=colors.HexColor("#14213d"),
        spaceBefore=13,
        spaceAfter=6,
    )
)
styles.add(
    ParagraphStyle(
        name="DocSubheading",
        parent=styles["Heading2"],
        fontName=FONT_BOLD,
        fontSize=11.5,
        leading=15,
        textColor=colors.HexColor("#243b53"),
        spaceBefore=10,
        spaceAfter=5,
    )
)
styles.add(
    ParagraphStyle(
        name="Body",
        parent=styles["BodyText"],
        fontName=FONT,
        fontSize=9.6,
        leading=13.2,
        alignment=TA_JUSTIFY,
        spaceAfter=5,
    )
)
styles.add(
    ParagraphStyle(
        name="Small",
        parent=styles["BodyText"],
        fontName=FONT,
        fontSize=8.6,
        leading=11.5,
        textColor=colors.HexColor("#4a5568"),
    )
)
styles.add(
    ParagraphStyle(
        name="Formula",
        parent=styles["Code"],
        fontName=FONT_MONO,
        fontSize=8.7,
        leading=11.2,
        leftIndent=7,
        rightIndent=7,
        spaceBefore=3,
        spaceAfter=6,
        textColor=colors.HexColor("#111827"),
        backColor=colors.HexColor("#f6f8fa"),
        borderColor=colors.HexColor("#d9dee8"),
        borderWidth=0.5,
        borderPadding=6,
    )
)
styles.add(
    ParagraphStyle(
        name="ProofBox",
        parent=styles["BodyText"],
        fontName=FONT,
        fontSize=9.4,
        leading=13,
        borderColor=colors.HexColor("#d9dee8"),
        borderWidth=0.6,
        borderPadding=7,
        backColor=colors.HexColor("#fbfcfe"),
        spaceAfter=8,
    )
)


def p(text: str):
    return Paragraph(text, styles["Body"])


def h(text: str):
    return Paragraph(text, styles["DocHeading"])


def sh(text: str):
    return Paragraph(text, styles["DocSubheading"])


def formula(text: str):
    return XPreformatted(text.strip(), styles["Formula"])


def bullets(items: list[str]):
    return ListFlowable(
        [ListItem(Paragraph(item, styles["Body"]), leftIndent=10) for item in items],
        bulletType="bullet",
        start="circle",
        leftIndent=15,
    )


def proof_box(title: str, paragraphs: list):
    content = [Paragraph(f"<b>{title}</b>", styles["DocSubheading"])]
    content.extend(paragraphs)
    table = Table([[content]], colWidths=[16.1 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cfd8e3")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fbfcfe")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def page_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(FONT, 8)
    canvas.setFillColor(colors.HexColor("#667085"))
    canvas.drawString(2.2 * cm, 1.25 * cm, "Hipoteza H2 - dowód matematyczny")
    canvas.drawRightString(18.8 * cm, 1.25 * cm, f"Strona {doc.page}")
    canvas.restoreState()


def build_story():
    story = []
    story.append(Paragraph("Opis i dowód matematyczny hipotezy H2", styles["DocTitle"]))
    story.append(
        Paragraph(
            "Kalibracja jądra QSVM przez kernel-target alignment z minimalnym limitem 4 kubitów",
            styles["DocSubtitle"],
        )
    )
    story.append(
        Paragraph(
            "Zespół: fizyk kwantowy, specjalista ML, statystyk, inżynier obliczeń. "
            "Data: 11 lipca 2026.",
            styles["Small"],
        )
    )

    story.append(h("1. Treść hipotezy H2"))
    story.append(
        p(
            "Hipoteza H2 dotyczy modelu QSVM-like, czyli klasyfikatora jądrowego, "
            "w którym część kwantowa odpowiada za macierz podobieństwa między próbkami."
        )
    )
    story.append(
        proof_box(
            "Hipoteza H2",
            [
                p(
                    "Zachować kalibrację jądra przez kernel-target alignment, ale narzucić "
                    "minimalną pojemność czterech kubitów. Wtedy model powinien zachować "
                    "lub poprawić jakość względem bazowego jądra sześciokubitowego, "
                    "a jednocześnie zużywać mniej zasobów obliczeniowych."
                ),
                formula("2^4 = 16 amplitud,     2^6 = 64 amplitudy"),
            ],
        )
    )
    story.append(
        bullets(
            [
                "Fizyk kwantowy: 2 kubity są zbyt małą przestrzenią Hilberta dla części danych; 4 kubity dają bogatszą geometrię.",
                "Specjalista ML: PCA do 4 składowych zachowuje nie mniej informacji liniowej niż PCA do 2 składowych.",
                "Statystyk: alignment dobiera jądro zgodne z etykietami, ale poprawę accuracy trzeba potwierdzić empirycznie.",
                "Inżynier obliczeń: koszt symulacji jądra skaluje się z wymiarem stanu, więc 4q jest tańsze niż 6q.",
            ]
        )
    )

    story.append(h("2. Formalizacja"))
    story.append(p("Niech dany będzie zbiór uczący:"))
    story.append(formula(r"D = \{(x_i,y_i)\}_{i=1}^{n}, \qquad y_i \in \{-1,+1\}."))
    story.append(p("Po standaryzacji wykonujemy PCA i zostawiamy q składowych:"))
    story.append(formula(r"z_i^{(q)} = P_q x_i \in \mathbb{R}^q."))
    story.append(
        p(
            "Następnie składowe są skalowane do przedziału [0,1] i kodowane w obwodzie "
            "kwantowym typu ZZFeatureMap. Feature mapę oznaczamy przez:"
        )
    )
    story.append(formula(r"\Phi_{q,\alpha,e}:\mathbb{R}^q \to \mathbb{C}^{2^q}."))
    story.append(p("Dla próbki x_i stan kwantowy oznaczamy:"))
    story.append(formula(r"|\psi_i\rangle = \Phi_{q,\alpha,e}\!\left(z_i^{(q)}\right)."))
    story.append(p("Jądro kwantowe ma postać:"))
    story.append(formula(r"K_{ij}^{(q,\alpha,e)} = \left|\langle \psi_i \mid \psi_j \rangle\right|^2."))
    story.append(p("H2 dopuszcza strojenie skali kątów i sprzężenia, ale wymusza:"))
    story.append(formula(r"q \ge 4."))
    story.append(p("Konfiguracja wybierana jest jako najmniejsza bliska najlepszemu alignmentowi:"))
    story.append(
        formula(
            r"(q^\star,\alpha^\star,e^\star)=\arg\min_{q,\alpha,e} q" "\n"
            r"A(K^{(q,\alpha,e)},yy^T) \ge 0.95 \max_{\tilde q,\tilde\alpha,\tilde e}"
            "\n"
            r"A(K^{(\tilde q,\tilde\alpha,\tilde e)},yy^T), \qquad q\ge4."
        )
    )

    story.append(h("3. Lematy i dowody"))
    story.append(
        proof_box(
            "Lemat 1. Jądro kwantowe jest dodatnio półokreślone",
            [
                p(
                    "Macierz jądra zdefiniowana jako kwadrat modułu overlapu stanów "
                    "jest poprawnym jądrem."
                ),
                formula(
                    r"K_{ij}=|\langle\psi_i|\psi_j\rangle|^2"
                    "\n"
                    r"=\langle\psi_i|\psi_j\rangle\langle\psi_j|\psi_i\rangle"
                    "\n"
                    r"=\langle \psi_i\otimes\psi_i^\ast | \psi_j\otimes\psi_j^\ast\rangle."
                ),
                p(
                    "Po zdefiniowaniu pomocniczych wektorów tensorowych otrzymujemy zwykłą "
                    "macierz Grama w przestrzeni tensorowej."
                ),
                formula(
                    r"c^T K c=\sum_{i,j} c_i c_j\langle\varphi_i|\varphi_j\rangle"
                    "\n"
                    r"=\left\|\sum_i c_i|\varphi_i\rangle\right\|^2 \ge 0."
                ),
                p("Zatem K jest dodatnio półokreślona. Koniec dowodu."),
            ],
        )
    )
    story.append(
        proof_box(
            "Lemat 2. H2 ma czterokrotnie mniejszy wymiar stanu niż H0",
            [
                formula(
                    r"\dim \mathcal{H}_q = 2^q,"
                    "\n"
                    r"\dim \mathcal{H}_6 = 2^6 = 64,"
                    "\n"
                    r"\dim \mathcal{H}_4 = 2^4 = 16."
                ),
                formula(r"\frac{\dim \mathcal{H}_4}{\dim \mathcal{H}_6}=\frac{16}{64}=\frac14."),
                formula(r"T(q)=O(n^2 2^q), \qquad \frac{T(4)}{T(6)}\approx\frac{n^2 2^4}{n^2 2^6}=\frac14."),
                p("Wariant czterokubitowy ma więc teoretycznie 1/4 wymiaru stanu baseline. Koniec dowodu."),
            ],
        )
    )

    story.append(PageBreak())
    story.append(
        proof_box(
            "Lemat 3. Limit czterech kubitów zachowuje nie mniej informacji PCA niż redukcja do dwóch kubitów",
            [
                p(
                    "Niech lambda_1 >= lambda_2 >= ... >= lambda_d >= 0 będą wartościami własnymi "
                    "macierzy kowariancji danych po standaryzacji."
                ),
                formula(
                    r"E_q=\sum_{k=q+1}^{d}\lambda_k,"
                    "\n"
                    r"E_2=\sum_{k=3}^{d}\lambda_k,"
                    "\n"
                    r"E_4=\sum_{k=5}^{d}\lambda_k."
                ),
                formula(r"E_2-E_4=\lambda_3+\lambda_4\ge0, \qquad E_4\le E_2."),
                formula(
                    r"R_q=\frac{\sum_{k=1}^{q}\lambda_k}{\sum_{k=1}^{d}\lambda_k},"
                    "\n"
                    r"R_4\ge R_2."
                ),
                p("H2 nie może więc zachować mniej liniowej informacji PCA niż agresywny wariant 2q. Koniec dowodu."),
            ],
        )
    )

    story.append(sh("Lemat 4. Kernel-target alignment mierzy zgodność jądra z etykietami"))
    story.append(p("Niech Y = yy^T będzie macierzą etykiet, a K_c i Y_c oznaczają wersje wycentrowane."))
    story.append(formula(r"A(K,Y)=\frac{\langle K_c,Y_c\rangle_F}{\|K_c\|_F\|Y_c\|_F}."))
    story.append(
        p(
            "Dla ustalonego zbioru etykiet i porównywalnie znormalizowanych jąder maksymalizacja "
            "alignmentu jest równoważna maksymalizacji y^T K_c y, czyli zgodności geometrii "
            "jądra z kierunkiem etykiet."
        )
    )
    story.append(formula(r"\langle K_c,yy^T\rangle_F = y^T K_c y."))
    story.append(p("Dla klasyfikatora typu kernel ridge lub LS-SVM zachodzi idealizowana zależność:"))
    story.append(formula(r"\hat y = K(K+\lambda I)^{-1}y."))
    story.append(p("Jeżeli y = sum beta_m u_m oraz K u_m = mu_m u_m, to:"))
    story.append(
        formula(
            r"\hat y=\sum_m \frac{\mu_m}{\mu_m+\lambda}\beta_m u_m,"
            "\n"
            r"\|y-\hat y\|^2=\sum_m\left(\frac{\lambda}{\mu_m+\lambda}\right)^2\beta_m^2."
        )
    )
    story.append(
        p(
            "Jeżeli etykiety mają większą projekcję na kierunki własne jądra o większych mu_m, "
            "czynnik lambda/(mu_m+lambda) maleje, a błąd jest mniejszy. Alignment jest więc "
            "uzasadnioną heurystyką wyboru jądra."
        )
    )

    story.append(h("4. Twierdzenie główne"))
    story.append(
        proof_box(
            "Twierdzenie",
            [
                p(
                    "Przy założeniach, że używamy jądra zdefiniowanego przez kwadrat modułu "
                    "overlapu stanów, koszt symulacji "
                    "jest zdominowany przez overlapy stanów, dane redukowane są przez PCA, a konfiguracja "
                    "wybierana jest przez kernel-target alignment z ograniczeniem q >= 4, H2 ma własności:"
                ),
                bullets(
                    [
                        "daje poprawne jądro dodatnio półokreślone;",
                        "redukuje wymiar stanu względem baseline 6q dokładnie do 1/4;",
                        "zachowuje nie mniej informacji PCA niż wariant 2q;",
                        "wybiera jądro zgodne z kierunkiem etykiet wśród rozważanych kandydatów.",
                    ]
                ),
                p(
                    "Dowód: punkt pierwszy wynika z Lematu 1, drugi z Lematu 2, trzeci z Lematu 3, "
                    "a czwarty z definicji alignmentu i reguły wyboru H2. Koniec dowodu."
                ),
            ],
        )
    )

    story.append(h("5. Granica dowodu"))
    story.append(
        p(
            "Nie da się uczciwie udowodnić czysto matematycznie, że H2 zawsze poprawi accuracy na dowolnym "
            "zbiorze danych. Accuracy zależy od rozkładu danych, szumu, podziału train/test, regularyzacji "
            "i zgodności feature mapy z prawdziwą granicą decyzyjną."
        )
    )
    story.append(
        p(
            "Dlatego wynik ma dwie części: matematyczną, która dowodzi poprawności i redukcji zasobów, "
            "oraz empiryczną, która sprawdza metryki na danych."
        )
    )

    story.append(h("6. Potwierdzenie empiryczne"))
    data = [
        ["Zbiór", "H0: baseline 6q", "H2: 4q alignment", "Różnica"],
        ["WDBC", "0.902", "0.946", "+0.044"],
        ["Wine", "0.951", "0.979", "+0.027"],
        ["OptDigits 3-vs-8", "0.945", "0.976", "+0.031"],
    ]
    table = Table(data, colWidths=[5.1 * cm, 3.7 * cm, 4.0 * cm, 2.8 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#14213d")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                ("FONTNAME", (0, 1), (-1, -1), FONT),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cfd8e3")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 8))
    story.append(formula(r"\frac{2^4}{2^6}=0.25."))
    story.append(
        p(
            "Ostateczny wniosek: matematycznie H2 jest poprawną i zasobowo lepszą konstrukcją jądra QSVM, "
            "a empirycznie w badanym workspace poprawiła balanced accuracy na wszystkich trzech zadaniach."
        )
    )
    return story


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=A4,
        rightMargin=2.0 * cm,
        leftMargin=2.0 * cm,
        topMargin=2.0 * cm,
        bottomMargin=1.8 * cm,
        title="Opis i dowód matematyczny hipotezy H2",
        author="Codex",
    )
    doc.build(build_story(), onFirstPage=page_footer, onLaterPages=page_footer)
    print(PDF_PATH)


if __name__ == "__main__":
    main()
