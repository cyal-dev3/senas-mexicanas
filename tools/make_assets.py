"""
Genera los iconos y la pantalla de carga a partir del logo (assets/logo.png):
  - assets/icon.png y assets/icon.ico (app de PC)
  - assets/splash.png (pantalla de carga del .exe)
Solo hay que correrlo si cambia el logo:  python tools/make_assets.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    from PIL import Image
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QRadialGradient
    from PySide6.QtWidgets import QApplication

    from miratek.ui import theme

    assets = ROOT / "assets"
    logo = Image.open(assets / "logo.png").convert("RGBA")
    logo.resize((256, 256), Image.LANCZOS).save(assets / "icon.png", optimize=True)
    logo.save(assets / "icon.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])

    app = QApplication.instance() or QApplication([])  # noqa: F841 (necesario para las fuentes)
    w, h = 640, 360
    splash = QImage(w, h, QImage.Format.Format_ARGB32)
    splash.fill(QColor(theme.BG))
    p = QPainter(splash)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    glow = QRadialGradient(150, 150, 360)
    c1 = QColor(theme.ACCENT_2)
    c1.setAlpha(70)
    glow.setColorAt(0, c1)
    glow.setColorAt(1, QColor(255, 255, 255, 0))
    p.fillRect(0, 0, w, h, glow)
    warm = QRadialGradient(560, 320, 300)
    c2 = QColor(theme.WARM)
    c2.setAlpha(60)
    warm.setColorAt(0, c2)
    warm.setColorAt(1, QColor(255, 255, 255, 0))
    p.fillRect(0, 0, w, h, warm)
    theme.paint_logo(p, QRectF(48, 96, 136, 136))
    p.setPen(QColor(theme.TEXT))
    p.setFont(theme.ui_font(46, QFont.Weight.Bold, display=True))
    p.drawText(QRectF(208, 100, 420, 64), Qt.AlignmentFlag.AlignVCenter, "Mira&Tek")
    p.setPen(QColor(theme.TEXT_2))
    p.setFont(theme.ui_font(19))
    p.drawText(QRectF(210, 162, 420, 36), Qt.AlignmentFlag.AlignVCenter, "Lengua de Señas Mexicana")
    bar = QLinearGradient(210, 0, 420, 0)
    bar.setColorAt(0, QColor(theme.ACCENT))
    bar.setColorAt(1, QColor(theme.WARM))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(bar)
    p.drawRoundedRect(QRectF(210, 212, 150, 6), 3, 3)
    p.setPen(QColor(theme.TEXT_3))
    p.setFont(theme.ui_font(14))
    p.drawText(QRectF(48, h - 62, w - 96, 30), Qt.AlignmentFlag.AlignVCenter, "Cargando…  ·  funciona sin internet")
    p.end()
    splash.save(str(assets / "splash.png"))
    print("Listo: icon.png, icon.ico y splash.png en", assets)


if __name__ == "__main__":
    main()
