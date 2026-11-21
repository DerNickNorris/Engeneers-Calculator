"""Mini-Baukasten für Systemskizzen als SVG (wird in GUI und PDF gerendert)."""

from __future__ import annotations

from xml.sax.saxutils import escape

W, H = 360, 220
INK = "#2b3a4a"      # Linien
ACCENT = "#1f6fb2"   # Lasten / Hervorhebungen
FILL = "#dce6f1"     # Flächen
MUTED = "#6b7b8c"    # Bemaßung


class Svg:
    def __init__(self, width: int = W, height: int = H) -> None:
        self.w, self.h = width, height
        self.parts: list[str] = []

    def line(self, x1, y1, x2, y2, color=INK, width=2.0, dash: str | None = None) -> Svg:
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color}" stroke-width="{width}"{d} stroke-linecap="round"/>'
        )
        return self

    def rect(self, x, y, w, h, fill=FILL, stroke=INK, width=1.6) -> Svg:
        self.parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'
        )
        return self

    def circle(self, cx, cy, r, fill=FILL, stroke=INK, width=1.6) -> Svg:
        self.parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{width}"/>'
        )
        return self

    def polygon(self, pts, fill=FILL, stroke=INK, width=1.6) -> Svg:
        p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        self.parts.append(f'<polygon points="{p}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')
        return self

    def text(self, x, y, s, size=13, color=INK, anchor="middle", italic=False, bold=False) -> Svg:
        if "_" in s:  # "I_b" -> I mit tiefgestelltem b (zwei Textelemente, Breite geschätzt)
            main, sub = s.split("_", 1)
            w_main, w_sub = 0.62 * size * len(main), 0.62 * 0.72 * size * len(sub)
            total = w_main + w_sub
            x0 = x - total / 2 if anchor == "middle" else (x - total if anchor == "end" else x)
            self.text(x0, y, main, size, color, "start", italic, bold)
            return self.text(x0 + w_main + 1, y + size * 0.3, sub, size * 0.72, color, "start", italic, bold)
        style = ' font-style="italic"' if italic else ""
        weight = ' font-weight="bold"' if bold else ""
        self.parts.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-family="DejaVu Sans, Segoe UI, Arial" '
            f'font-size="{size}" fill="{color}" text-anchor="{anchor}"{style}{weight}>{escape(s)}</text>'
        )
        return self

    def arrow(self, x1, y1, x2, y2, color=ACCENT, width=2.2, head=8) -> Svg:
        """Pfeil von (x1,y1) nach (x2,y2), Spitze am Endpunkt."""
        import math

        self.line(x1, y1, x2, y2, color, width)
        ang = math.atan2(y2 - y1, x2 - x1)
        a1, a2 = ang + math.radians(155), ang - math.radians(155)
        self.polygon(
            [(x2, y2), (x2 + head * math.cos(a1), y2 + head * math.sin(a1)),
             (x2 + head * math.cos(a2), y2 + head * math.sin(a2))],
            fill=color, stroke=color, width=1,
        )
        return self

    def dim_h(self, x1, x2, y, label: str) -> Svg:
        """Horizontale Bemaßung mit Maßpfeilen."""
        self.line(x1, y - 6, x1, y + 6, MUTED, 1.2).line(x2, y - 6, x2, y + 6, MUTED, 1.2)
        self.arrow(x1 + (x2 - x1) / 2, y, x1, y, MUTED, 1.2, 6)
        self.arrow(x1 + (x2 - x1) / 2, y, x2, y, MUTED, 1.2, 6)
        return self.text((x1 + x2) / 2, y - 6, label, 12, MUTED)

    def dim_v(self, x, y1, y2, label: str, side: str = "right") -> Svg:
        self.line(x - 6, y1, x + 6, y1, MUTED, 1.2).line(x - 6, y2, x + 6, y2, MUTED, 1.2)
        self.arrow(x, (y1 + y2) / 2, x, y1, MUTED, 1.2, 6)
        self.arrow(x, (y1 + y2) / 2, x, y2, MUTED, 1.2, 6)
        dx, anchor = (8, "start") if side == "right" else (-8, "end")
        return self.text(x + dx, (y1 + y2) / 2 + 4, label, 12, MUTED, anchor)

    def support_pin(self, x, y) -> Svg:
        """Festlager: Dreieck mit Schraffur."""
        self.polygon([(x, y), (x - 11, y + 18), (x + 11, y + 18)], fill="#ffffff")
        return self._hatch(x, y + 18)

    def support_roller(self, x, y) -> Svg:
        """Loslager: Dreieck + Linie mit Abstand."""
        self.polygon([(x, y), (x - 11, y + 15), (x + 11, y + 15)], fill="#ffffff")
        self.line(x - 13, y + 19, x + 13, y + 19, INK, 1.6)
        return self._hatch(x, y + 21)

    def _hatch(self, x, y) -> Svg:
        self.line(x - 15, y, x + 15, y, INK, 1.6)
        for i in range(-15, 15, 6):
            self.line(x + i, y + 6, x + i + 6, y, INK, 1.0)
        return self

    def render(self) -> str:
        body = "\n  ".join(self.parts)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}">\n  {body}\n</svg>'
        )
