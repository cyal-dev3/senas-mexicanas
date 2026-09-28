"""
Diseno visual: colores, tipografia, iconos y logo.

La paleta sale del logo: fondo aqua claro, turquesa (la mano izquierda) como
color principal y amarillo-naranja (la mano derecha) como acento. Los iconos
salen de la fuente de iconos de Windows (Segoe Fluent Icons).
"""

import sys

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QIcon, QLinearGradient, QPainter,
                           QPainterPath, QPixmap)

# ---- Colores (del logo) ----
BG = "#F2FAFB"          # fondo aqua muy claro
SIDEBAR = "#FFFFFF"
SURFACE = "#FFFFFF"     # tarjetas
SURFACE_2 = "#EDF7F9"   # campos y fondos suaves
SURFACE_3 = "#D8EDF1"   # pistas de barras y anillos
BORDER = "#DCEBEF"
TEXT = "#0A2530"        # azul petroleo muy oscuro
TEXT_2 = "#4A6670"
TEXT_3 = "#86A0A8"
ACCENT = "#0A9CB1"      # turquesa (mano izquierda del logo)
ACCENT_DEEP = "#067488"
ACCENT_2 = "#22C3D4"    # cian
WARM = "#FFB81C"        # amarillo (mano derecha del logo)
WARM_2 = "#FF8A00"      # naranja
GREEN = "#14A865"
AMBER = "#F08C00"
RED = "#E5484D"
VIDEO_BG = "#0C2530"    # el area de la camara se queda oscura

# ---- Iconos (codigos de Segoe Fluent Icons / Segoe MDL2 Assets) ----
ICONS = {
    "home": "\uE80F",
    "record": "\uE714",
    "train": "\uE7BE",
    "live": "\uE768",
    "share": "\uE72D",
    "settings": "\uE713",
    "eye": "\uE890",
    "check": "\uE73E",
    "undo": "\uE7A7",
    "pause": "\uE769",
    "play": "\uE768",
    "stop": "\uE71A",
    "back": "\uE72B",
    "next": "\uE72A",
    "lock": "\uE72E",
    "folder": "\uE838",
    "send": "\uE724",
    "download": "\uE896",
    "person": "\uE77B",
    "warning": "\uE7BA",
    "delete": "\uE74D",
    "camera": "\uE722",
    "light": "\uE793",
    "sparkle": "\uE945",
    "trophy": "\uEC4E",
    "clear": "\uE894",
    "info": "\uE946",
    "refresh": "\uE72C",
    "hand": "\uE7C9",
    "phone": "\uE8EA",
}

_icon_family = None


def icon_family():
    """Fuente de iconos disponible (Windows 11: Fluent; Windows 10: MDL2)."""
    global _icon_family
    if _icon_family is None:
        families = set(QFontDatabase.families())
        _icon_family = next((f for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets") if f in families),
                            "Segoe UI Symbol")
    return _icon_family


def icon_font(size):
    font = QFont(icon_family())
    font.setPixelSize(size)
    return font


def ui_font(size, weight=QFont.Weight.Normal, display=False):
    font = QFont()
    font.setFamilies(["Segoe UI Variable Display" if display else "Segoe UI Variable Text",
                      "Segoe UI", "Helvetica Neue", "Arial"])
    font.setPixelSize(size)
    font.setWeight(weight)
    return font


def glyph_icon(name, color=TEXT, size=20):
    """QIcon dibujado a partir de un glifo de la fuente de iconos."""
    ratio = 2.0
    pix = QPixmap(int(size * ratio), int(size * ratio))
    pix.setDevicePixelRatio(ratio)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QColor(color))
    p.setFont(icon_font(int(size * 0.8)))
    p.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, ICONS.get(name, name))
    p.end()
    return QIcon(pix)


def accent_gradient(rect):
    grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
    grad.setColorAt(0.0, QColor(ACCENT_DEEP))
    grad.setColorAt(1.0, QColor(ACCENT_2))
    return grad


def brand_gradient(start, end):
    """Degradado turquesa -> amarillo, como la flecha del logo."""
    grad = QLinearGradient(start, end)
    grad.setColorAt(0.0, QColor(ACCENT))
    grad.setColorAt(1.0, QColor(WARM))
    return grad


_logo_cache = {}


def logo_pixmap(size, ratio=2.0):
    """El logo (assets/logo.png) escalado con buena calidad."""
    from .. import config
    key = (int(size), ratio)
    if key not in _logo_cache:
        source = QPixmap(str(config.resource_path("assets", "logo.png")))
        if source.isNull():
            return None
        px = source.scaled(int(size * ratio), int(size * ratio), Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
        px.setDevicePixelRatio(ratio)
        _logo_cache[key] = px
    return _logo_cache[key]


def paint_logo(painter, rect):
    """Dibuja el logo; si falta el archivo, un cuadro con el degradado de la marca."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    px = logo_pixmap(rect.width())
    if px is not None:
        painter.drawPixmap(rect, px, QRectF(0, 0, px.width(), px.height()))
    else:
        path = QPainterPath()
        path.addRoundedRect(rect, rect.width() * 0.25, rect.width() * 0.25)
        painter.fillPath(path, brand_gradient(rect.topLeft(), rect.bottomRight()))
    painter.restore()


def stylesheet():
    return f"""
    QWidget {{
        color: {TEXT};
        font-family: "Segoe UI Variable Text", "Segoe UI";
        font-size: 14px;
    }}
    QMainWindow, QDialog, #Root {{ background: {BG}; }}
    #Sidebar {{ background: {SIDEBAR}; border-right: 1px solid {BORDER}; }}
    QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}

    QPushButton#NavButton {{
        text-align: left; padding: 11px 14px; border: none; border-radius: 12px;
        color: {TEXT_2}; background: transparent; font-size: 14px;
    }}
    QPushButton#NavButton:hover {{ background: {SURFACE_2}; color: {TEXT}; }}
    QPushButton#NavButton:checked {{ background: #E1F4F7; color: {ACCENT_DEEP}; font-weight: 600; }}

    QFrame[card="true"] {{
        background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 20px;
    }}
    QFrame[card="soft"] {{
        background: {SURFACE_2}; border: none; border-radius: 16px;
    }}

    QPushButton {{
        border-radius: 12px; padding: 10px 18px; font-size: 14px;
        background: {SURFACE}; border: 1px solid {BORDER}; color: {TEXT};
    }}
    QPushButton:hover {{ background: {SURFACE_2}; }}
    QPushButton:disabled {{ color: {TEXT_3}; }}
    QPushButton[kind="primary"] {{
        border: none; color: white; font-weight: 600; font-size: 15px;
        padding: 13px 26px; border-radius: 24px;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {ACCENT_DEEP}, stop:1 {ACCENT_2});
    }}
    QPushButton[kind="primary"]:hover {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {ACCENT}, stop:1 #3BD3E2);
    }}
    QPushButton[kind="primary"]:pressed {{ padding-top: 14px; padding-bottom: 12px; }}
    QPushButton[kind="primary"]:disabled {{ background: {SURFACE_3}; color: {TEXT_3}; }}
    QPushButton[kind="secondary"] {{ border-radius: 22px; padding: 12px 22px; }}
    QPushButton[kind="ghost"] {{
        background: transparent; border: none; color: {TEXT_2}; padding: 8px 12px; border-radius: 10px;
    }}
    QPushButton[kind="ghost"]:hover {{ background: {SURFACE_2}; color: {TEXT}; }}
    QPushButton[kind="danger"] {{ background: transparent; border: 1px solid {BORDER}; color: {RED}; }}
    QPushButton[kind="danger"]:hover {{ background: #FDEEEE; }}
    QPushButton[kind="segment"] {{
        background: transparent; border: none; border-radius: 10px; padding: 7px 14px; color: {TEXT_2};
    }}
    QPushButton[kind="segment"]:checked {{
        background: {SURFACE}; color: {ACCENT_DEEP}; font-weight: 600; border: 1px solid {BORDER};
    }}

    QLabel {{ background: transparent; }}
    QLabel[role="title"] {{
        font-family: "Segoe UI Variable Display", "Segoe UI"; font-size: 30px; font-weight: 700;
    }}
    QLabel[role="h2"] {{
        font-family: "Segoe UI Variable Display", "Segoe UI"; font-size: 19px; font-weight: 600;
    }}
    QLabel[role="subtitle"] {{ color: {TEXT_2}; font-size: 15px; }}
    QLabel[role="body"] {{ color: {TEXT_2}; font-size: 14px; }}
    QLabel[role="muted"] {{ color: {TEXT_3}; font-size: 12px; }}
    QLabel[role="overline"] {{
        color: {TEXT_3}; font-size: 11px; font-weight: 700; letter-spacing: 1.2px;
    }}

    QLineEdit, QSpinBox, QComboBox {{
        background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px;
        padding: 10px 14px; font-size: 15px; selection-background-color: {ACCENT_2};
    }}
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border: 1px solid {ACCENT}; }}
    QComboBox::drop-down {{ border: none; width: 28px; }}
    QComboBox QAbstractItemView {{
        background: {SURFACE}; border: 1px solid {BORDER}; selection-background-color: {SURFACE_2};
        selection-color: {TEXT}; outline: none; padding: 4px;
    }}
    QSpinBox::up-button, QSpinBox::down-button {{ width: 0; border: none; }}
    QCheckBox {{ spacing: 10px; }}
    QCheckBox::indicator {{
        width: 20px; height: 20px; border-radius: 6px; border: 1px solid {BORDER}; background: {SURFACE};
    }}
    QCheckBox::indicator:checked {{ background: {ACCENT}; border: 1px solid {ACCENT}; }}

    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
    QScrollBar::handle:vertical {{ background: {SURFACE_3}; border-radius: 3px; min-height: 40px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    QScrollBar:horizontal {{ height: 0; }}

    QToolTip {{
        background: {TEXT}; color: white; border: none; padding: 6px 10px; border-radius: 8px;
    }}
    QMessageBox {{ background: {SURFACE}; }}
    QMessageBox QLabel {{ color: {TEXT}; font-size: 14px; }}
    QMessageBox QPushButton {{ min-width: 90px; }}
    """


def apply_title_bar(widget):
    """Barra de titulo del color de la app en Windows 10/11."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = int(widget.winId())
        dwm = ctypes.windll.dwmapi
        value = ctypes.c_int(0)  # tema claro
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (nuevo y viejo)
            if dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value), 4) == 0:
                break
        color = QColor(BG)
        colorref = ctypes.c_int(color.red() | (color.green() << 8) | (color.blue() << 16))
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(colorref), 4)  # DWMWA_CAPTION_COLOR
    except Exception:
        pass
