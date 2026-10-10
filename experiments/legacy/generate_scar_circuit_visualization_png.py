from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis_output"

W, H = 1200, 760
SCALE = 2


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size * SCALE)
        except OSError:
            pass
    return ImageFont.load_default()


def xy(v: float) -> int:
    return int(round(v * SCALE))


def box(draw: ImageDraw.ImageDraw, rect, fill, outline, width=2, radius=8):
    draw.rounded_rectangle(
        tuple(xy(v) for v in rect),
        radius=xy(radius),
        fill=fill,
        outline=outline,
        width=xy(width),
    )


def text(draw: ImageDraw.ImageDraw, pos, msg, size=16, fill="#0f172a", bold=False, anchor=None):
    draw.text((xy(pos[0]), xy(pos[1])), msg, font=font(size, bold), fill=fill, anchor=anchor)


def line(draw: ImageDraw.ImageDraw, points, fill="#334155", width=2):
    draw.line([(xy(x), xy(y)) for x, y in points], fill=fill, width=xy(width))


def gate(draw: ImageDraw.ImageDraw, x, y, w, h, label, sub=None, fill="#e0f2fe", stroke="#0284c7"):
    box(draw, (x, y, x + w, y + h), fill, stroke, width=2, radius=7)
    text(draw, (x + w / 2, y + h / 2 - (8 if sub else 0)), label, size=15, bold=True, anchor="mm")
    if sub:
        text(draw, (x + w / 2, y + h / 2 + 18), sub, size=12, fill="#7f1d1d", anchor="mm")


def arrow(draw: ImageDraw.ImageDraw, start, end, fill="#dc2626", width=2):
    line(draw, [start, end], fill=fill, width=width)
    x0, y0 = start
    x1, y1 = end
    if x1 >= x0:
        tri = [(x1, y1), (x1 - 10, y1 - 5), (x1 - 10, y1 + 5)]
    else:
        tri = [(x1, y1), (x1 + 10, y1 - 5), (x1 + 10, y1 + 5)]
    draw.polygon([(xy(x), xy(y)) for x, y in tri], fill=fill)


def draw_scar_pair(draw: ImageDraw.ImageDraw, x, y_top, y_bottom, label, sub):
    gate(draw, x, y_top - 21, 92, y_bottom - y_top + 42, label, sub, fill="#fee2e2", stroke="#dc2626")
    for yy in [y_top, y_bottom]:
        draw.ellipse((xy(x - 5), xy(yy - 5), xy(x + 5), xy(yy + 5)), fill="#dc2626")
    line(draw, [(x, y_top), (x, y_bottom)], fill="#dc2626", width=2)


def main() -> None:
    img = Image.new("RGB", (W * SCALE, H * SCALE), "#f8fafc")
    draw = ImageDraw.Draw(img)

    text(draw, (60, 48), "SCAR gate in a VQE quantum circuit", size=24, bold=True)
    text(
        draw,
        (60, 78),
        "Skew-Chiral Amplitude Router: amplitude exchange + chiral phase + ZZ-like correlation phase",
        size=15,
        fill="#475569",
    )

    box(draw, (50, 120, 570, 370), "#ffffff", "#cbd5e1")
    text(draw, (80, 152), "Two-qubit SCAR block", size=21, bold=True)
    text(draw, (80, 181), "A compact entangler acting on neighboring qubits", size=15, fill="#475569")

    for label, y in [("q_i", 238), ("q_j", 304)]:
        text(draw, (115, y), label, size=17, bold=True, anchor="rm")
        line(draw, [(135, y), (505, y)], width=2)
    draw_scar_pair(draw, 250, 238, 304, "SCAR", "(theta, delta, phi)")
    for x in [250, 400]:
        for y in [238, 304]:
            draw.ellipse((xy(x - 5), xy(y - 5), xy(x + 5), xy(y + 5)), fill="#dc2626")
        line(draw, [(x, 238), (x, 304)], fill="#dc2626", width=2)

    chip_items = [("mixes |01> <-> |10>", 92, 340, 155), ("phase phi", 260, 340, 110), ("chirality delta", 384, 340, 135)]
    for msg, x, y, w in chip_items:
        box(draw, (x, y, x + w, y + 26), "#eff6ff", "#60a5fa", width=1, radius=7)
        text(draw, (x + w / 2, y + 13), msg, size=12, fill="#1e3a8a", bold=True, anchor="mm")

    box(draw, (630, 120, 1150, 370), "#ffffff", "#cbd5e1")
    text(draw, (660, 152), "SCAR matrix action", size=21, bold=True)
    text(draw, (660, 181), "Basis: |00>, |01>, |10>, |11>", size=15, fill="#475569")
    matrix_lines = [
        "SCAR(theta,delta,phi) =",
        "[ exp(-i phi/2)       0                    0              0 ]",
        "[      0        exp(i phi/2)cos(theta)  -i exp(i phi/2-i delta)sin(theta)  0 ]",
        "[      0       -i exp(i phi/2+i delta)sin(theta)   exp(i phi/2)cos(theta) 0 ]",
        "[      0             0                    0        exp(-i phi/2) ]",
    ]
    for i, msg in enumerate(matrix_lines):
        text(draw, (660 if i == 0 else 690, 222 + 28 * i), msg, size=13, fill="#0f172a")

    box(draw, (50, 420, 1150, 730), "#ffffff", "#cbd5e1")
    text(draw, (80, 454), "One SCAR-ring ansatz layer for 4 qubits", size=21, bold=True)
    text(
        draw,
        (80, 482),
        "Local RY/RZ rotations create single-qubit freedom; SCAR gates spread amplitude and entanglement around the ring.",
        size=15,
        fill="#475569",
    )

    text(draw, (80, 516), "Per layer: p = 3n + 2 parameters, G_2q = n two-qubit gates", size=13)

    ys = [560, 610, 660, 710]
    for i, y in enumerate(ys):
        text(draw, (110, y), f"q{i}", size=17, bold=True, anchor="rm")
        line(draw, [(130, y), (1085, y)], width=2)
        gate(draw, 160, y - 21, 58, 42, "RY")
        gate(draw, 230, y - 21, 58, 42, "RZ", fill="#fef3c7", stroke="#d97706")

    draw_scar_pair(draw, 360, ys[0], ys[1], "SCAR", "theta01")
    draw_scar_pair(draw, 520, ys[1], ys[2], "SCAR", "theta12")
    draw_scar_pair(draw, 680, ys[2], ys[3], "SCAR", "theta23")

    # Wrap-around edge q3-q0.
    line(draw, [(862, ys[0]), (1010, ys[0]), (1010, ys[3]), (862, ys[3])], fill="#dc2626", width=2)
    arrow(draw, (1010, ys[3]), (930, ys[3]), fill="#dc2626", width=2)
    gate(draw, 815, 599, 92, 42, "SCAR", None, fill="#fee2e2", stroke="#dc2626")
    text(draw, (861, 663), "theta30", size=12, fill="#7f1d1d", anchor="mm")
    for y in [ys[0], ys[3]]:
        draw.ellipse((xy(862 - 5), xy(y - 5), xy(862 + 5), xy(y + 5)), fill="#dc2626")

    img = img.resize((W, H), Image.Resampling.LANCZOS)
    out = OUT / "scar_gate_circuit_visualization.png"
    img.save(out)
    print(out)


if __name__ == "__main__":
    main()
