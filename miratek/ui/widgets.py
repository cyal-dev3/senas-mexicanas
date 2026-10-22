"""Piezas visuales reutilizables (tarjetas, anillos de progreso, video, avisos)."""

import html
import math
import time

from PySide6.QtCore import (QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRect, QRectF, QSize,
                            Qt, QTimer, QVariantAnimation, Signal)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QFont, QFontMetrics, QLinearGradient, QPainter,
                           QPainterPath, QPen)
from PySide6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QLayout,
                               QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from ..hands import HAND_CONNECTIONS, LEFT, RIGHT
from . import theme

# ============================================================
# Ayudantes para crear widgets con estilo
# ============================================================


def label(text="", role=None, wrap=False, align=None):
    lbl = QLabel(text)
    # Texto simple: un nombre como "<b>Ana</b>" (de un archivo recibido) no se interpreta como HTML.
    # Quien necesite formato lo pide con setTextFormat(RichText).
    lbl.setTextFormat(Qt.TextFormat.PlainText)
    if role:
        lbl.setProperty("role", role)
    lbl.setWordWrap(wrap)
    if align is not None:
        lbl.setAlignment(align)
    return lbl


def button(text, kind=None, icon=None, icon_color=None, min_width=None):
    btn = QPushButton(text)
    if kind:
        btn.setProperty("kind", kind)
    if icon:
        color = icon_color or ("white" if kind == "primary" else theme.TEXT_2)
        btn.setIcon(theme.glyph_icon(icon, color, 18))
        btn.setIconSize(QSize(18, 18))
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if min_width:
        btn.setMinimumWidth(min_width)
    return btn


def restyle(widget):
    """Vuelve a aplicar el estilo despues de cambiar una propiedad."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def side_scroll(widget, min_width=290, max_width=380):
    """Panel lateral con scroll: en pantallas chicas se desplaza en vez de cortarse."""
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidget(widget)
    # Nunca mas angosto que su contenido (no hay scroll horizontal): +12 de la barra de scroll
    min_width = max(min_width, widget.minimumSizeHint().width() + 12)
    area.setMinimumWidth(min_width)
    area.setMaximumWidth(max(min_width, max_width))
    area.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
    return area


class Card(QFrame):
    def __init__(self, parent=None, soft=False, padding=24, spacing=14):
        super().__init__(parent)
        self.setProperty("card", "soft" if soft else "true")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(padding, padding, padding, padding)
        self.body.setSpacing(spacing)


class IconBadge(QWidget):
    """Circulo de color con un icono al centro."""

    def __init__(self, icon, color=theme.ACCENT, size=44, parent=None):
        super().__init__(parent)
        self._icon = icon
        self._color = QColor(color)
        self.setFixedSize(size, size)

    def set_icon(self, icon, color=None):
        self._icon = icon
        if color:
            self._color = QColor(color)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor(self._color)
        bg.setAlpha(38)
        p.setBrush(bg)
        p.setPen(Qt.PenStyle.NoPen)
        r = QRectF(self.rect())
        p.drawRoundedRect(r, r.width() * 0.32, r.width() * 0.32)
        p.setPen(self._color)
        p.setFont(theme.icon_font(int(r.width() * 0.42)))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, theme.ICONS.get(self._icon, self._icon))


class Avatar(QWidget):
    def __init__(self, name="", size=36, parent=None):
        super().__init__(parent)
        self._name = name
        self.setFixedSize(size, size)

    def set_name(self, name):
        self._name = name
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        p.setBrush(QBrush(theme.accent_gradient(r)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(r)
        p.setPen(QColor("white"))
        p.setFont(theme.ui_font(int(r.height() * 0.42), QFont.Weight.DemiBold))
        initial = (self._name.strip()[:1] or "?").upper()
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, initial)


class Logo(QWidget):
    def __init__(self, size=38, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, _):
        p = QPainter(self)
        theme.paint_logo(p, QRectF(self.rect()))


# ============================================================
# Anillo de progreso
# ============================================================

class ProgressRing(QWidget):
    def __init__(self, size=120, thickness=10, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._value = 0.0
        self._thickness = thickness
        self._text = ""
        self._sub = ""
        self._color = None
        self._anim = QVariantAnimation(self, duration=650, easingCurve=QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)

    def _on_anim(self, v):
        self._value = float(v)
        self.update()

    def set_value(self, value, animate=True):
        value = max(0.0, min(1.0, float(value)))
        self._anim.stop()
        if animate and self.isVisible():
            self._anim.setStartValue(self._value)
            self._anim.setEndValue(value)
            self._anim.start()
        else:
            self._value = value
            self.update()

    def set_text(self, text, sub=""):
        self._text, self._sub = text, sub
        self.update()

    def set_color(self, color):
        self._color = QColor(color) if color else None
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = self._thickness
        r = QRectF(self.rect()).adjusted(t / 2 + 1, t / 2 + 1, -t / 2 - 1, -t / 2 - 1)
        pen = QPen(QColor(theme.SURFACE_3), t, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawEllipse(r)
        if self._value > 0.001:
            if self._color:
                brush = QBrush(self._color)
            else:
                grad = QConicalGradient(r.center(), 90)
                grad.setColorAt(0.0, QColor(theme.ACCENT))
                grad.setColorAt(0.5, QColor(theme.ACCENT_2))
                grad.setColorAt(1.0, QColor(theme.ACCENT))
                brush = QBrush(grad)
            pen = QPen(brush, t, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawArc(r, 90 * 16, -int(360 * 16 * self._value))
        if self._text:
            p.setPen(QColor(theme.TEXT))
            size = max(11, int(self.height() * (0.22 if not self._sub else 0.2)))
            p.setFont(theme.ui_font(size, QFont.Weight.Bold, display=True))
            text_rect = QRectF(self.rect())
            if self._sub:
                text_rect.adjust(0, -self.height() * 0.08, 0, -self.height() * 0.08)
            p.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self._text)
        if self._sub:
            p.setPen(QColor(theme.TEXT_3))
            p.setFont(theme.ui_font(max(9, int(self.height() * 0.095))))
            sub_rect = QRectF(self.rect()).adjusted(0, self.height() * 0.2, 0, self.height() * 0.2)
            p.drawText(sub_rect, Qt.AlignmentFlag.AlignCenter, self._sub)


# ============================================================
# Barras y puntos
# ============================================================

class Bar(QWidget):
    def __init__(self, height=8, parent=None):
        super().__init__(parent)
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._value = 0.0
        self._color = QColor(theme.ACCENT)

    def set_value(self, value, color=None):
        self._value = max(0.0, min(1.0, value))
        if color:
            self._color = QColor(color)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        rad = r.height() / 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.SURFACE_3))
        p.drawRoundedRect(r, rad, rad)
        if self._value > 0:
            fill = QRectF(r.left(), r.top(), max(r.height(), r.width() * self._value), r.height())
            grad = QLinearGradient(fill.topLeft(), fill.topRight())
            c2 = QColor(self._color)
            c2.setAlpha(170)
            grad.setColorAt(0, c2)
            grad.setColorAt(1, self._color)
            p.setBrush(grad)
            p.drawRoundedRect(fill, rad, rad)


class BusyBar(QWidget):
    """Barra que va y viene mientras algo trabaja (cuando no sabemos el porcentaje)."""

    def __init__(self, height=8, parent=None):
        super().__init__(parent)
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._timer = QTimer(self, interval=30)
        self._timer.timeout.connect(self.update)

    def showEvent(self, event):
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        rad = r.height() / 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.SURFACE_3))
        p.drawRoundedRect(r, rad, rad)
        seg = max(r.height(), r.width() * 0.3)
        pos = 0.5 - 0.5 * math.cos(2 * math.pi * (time.monotonic() % 1.6) / 1.6)
        fill = QRectF(r.left() + (r.width() - seg) * pos, r.top(), seg, r.height())
        grad = QLinearGradient(fill.topLeft(), fill.topRight())
        grad.setColorAt(0, QColor(theme.ACCENT))
        grad.setColorAt(1, QColor(theme.ACCENT_2))
        p.setBrush(grad)
        p.drawRoundedRect(fill, rad, rad)


class BarRow(QWidget):
    """Etiqueta + barra + valor, para porcentajes por sena."""

    def __init__(self, text, parent=None, label_width=110):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        self.name = label(text)
        self.name.setFixedWidth(label_width)
        self.bar = Bar(8)
        self.value = label("", "body")
        self.value.setFixedWidth(44)
        self.value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self.name)
        lay.addWidget(self.bar, 1)
        lay.addWidget(self.value)

    def set(self, fraction, text=None, color=None):
        self.bar.set_value(fraction, color)
        self.value.setText(text if text is not None else f"{round(fraction * 100)}%")


def quality_color(fraction):
    if fraction is None:
        return theme.TEXT_3
    if fraction >= 0.85:
        return theme.GREEN
    if fraction >= 0.6:
        return theme.AMBER
    return theme.RED


class DotsProgress(QWidget):
    """Fila de puntos: cuantos clips llevas de la meta (con metas grandes, una barra)."""

    MAX_DOTS = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self._total = 20
        self._filled = 0
        self.setFixedHeight(16)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set(self, filled, total):
        self._filled, self._total = max(0, filled), max(1, total)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        n = self._total
        gap = 5.0
        w = (self.width() - gap * (n - 1)) / n
        h = 8.0
        y = (self.height() - h) / 2
        p.setPen(Qt.PenStyle.NoPen)
        if n > self.MAX_DOTS or w < 4:
            self._paint_bar(p, y, h)  # demasiados puntos: no caben (saldrian anchos negativos)
            return
        for i in range(n):
            x = i * (w + gap)
            if i < self._filled:
                grad = QLinearGradient(QPointF(0, 0), QPointF(self.width(), 0))
                grad.setColorAt(0, QColor(theme.ACCENT))
                grad.setColorAt(1, QColor(theme.ACCENT_2))
                p.setBrush(grad)
            else:
                p.setBrush(QColor(theme.SURFACE_3))
            p.drawRoundedRect(QRectF(x, y, w, h), h / 2, h / 2)

    def _paint_bar(self, p, y, h):
        text = f"{min(self._filled, self._total)} de {self._total}"
        font = theme.ui_font(11, QFont.Weight.DemiBold)
        p.setFont(font)
        text_w = QFontMetrics(font).horizontalAdvance(text) + 10
        track = QRectF(0, y, max(h, self.width() - text_w), h)
        p.setBrush(QColor(theme.SURFACE_3))
        p.drawRoundedRect(track, h / 2, h / 2)
        frac = min(1.0, self._filled / self._total)
        if frac > 0:
            fill = QRectF(track.left(), y, max(h, track.width() * frac), h)
            grad = QLinearGradient(track.topLeft(), track.topRight())
            grad.setColorAt(0, QColor(theme.ACCENT))
            grad.setColorAt(1, QColor(theme.ACCENT_2))
            p.setBrush(grad)
            p.drawRoundedRect(fill, h / 2, h / 2)
        p.setPen(QColor(theme.TEXT_3))
        p.drawText(QRectF(track.right(), 0, text_w, self.height()),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, text)


class Segmented(QFrame):
    changed = Signal(str)

    def __init__(self, options, current, parent=None):
        super().__init__(parent)
        self.setObjectName("Segmented")
        self.setStyleSheet(f"#Segmented {{ background: {theme.SURFACE_2}; border-radius: 12px; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(2)
        self._buttons = {}
        self._current = current
        for key, text in options:
            b = button(text, "segment")
            bold = theme.ui_font(14, QFont.Weight.DemiBold)
            b.setMinimumWidth(QFontMetrics(bold).horizontalAdvance(text) + 32)
            b.setCheckable(True)
            b.setChecked(key == current)
            b.clicked.connect(lambda _=False, k=key: self._select(k))
            lay.addWidget(b)
            self._buttons[key] = b

    def value(self):
        return self._current

    def set_value(self, key):
        """Marca una opcion sin avisar (changed no se emite)."""
        self._current = key
        for k, b in self._buttons.items():
            b.setChecked(k == key)

    def _select(self, key):
        self.set_value(key)
        self.changed.emit(key)


class CountUpLabel(QLabel):
    """Numero que 'cuenta' hacia arriba al aparecer (ej: 0% -> 92%)."""

    def __init__(self, parent=None, suffix="%"):
        super().__init__(parent)
        self._suffix = suffix
        self._anim = QVariantAnimation(self, duration=1100, easingCurve=QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(lambda v: self.setText(f"{int(round(float(v)))}{self._suffix}"))

    def count_to(self, value):
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(float(value))
        self._anim.start()


# ============================================================
# Layout que acomoda "chips" en varias lineas
# ============================================================

class FlowLayout(QLayout):
    def __init__(self, parent=None, spacing=8, justify=False):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        self._justify = justify  # estira los elementos para llenar cada fila

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _layout(self, rect, test):
        if self._justify and self._items:
            return self._layout_grid(rect, test)
        x, y, line_h = rect.x(), rect.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            if x + hint.width() > rect.right() and line_h > 0:
                x = rect.x()
                y += line_h + self._spacing
                line_h = 0
            if not test:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._spacing
            line_h = max(line_h, hint.height())
        return y + line_h - rect.y()

    def _layout_grid(self, rect, test):
        base = self._items[0].sizeHint()
        cols = max(1, (rect.width() + self._spacing) // (base.width() + self._spacing))
        width = (rect.width() - self._spacing * (cols - 1)) / cols
        for i, item in enumerate(self._items):
            row, col = divmod(i, cols)
            if not test:
                item.setGeometry(QRect(int(rect.x() + col * (width + self._spacing)),
                                       rect.y() + row * (base.height() + self._spacing),
                                       int(width), base.height()))
        rows = (len(self._items) + cols - 1) // cols
        return rows * base.height() + (rows - 1) * self._spacing


def chip(text, highlight=False):
    c = QLabel(text)
    bg = theme.ACCENT if highlight else theme.SURFACE_2
    fg = "white" if highlight else theme.TEXT
    c.setStyleSheet(f"background: {bg}; color: {fg}; border-radius: 14px; padding: 5px 12px;"
                    f"font-size: 14px; font-weight: {600 if highlight else 500};")
    return c


# ============================================================
# Transiciones entre pantallas
# ============================================================

class FadeStack(QStackedWidget):
    """Pantallas que cambian con un fundido. Mide lo que mide la pantalla visible
    (no la mas grande), para no dejar espacio vacio ni ensanchar la ventana."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.currentChanged.connect(lambda _: self.updateGeometry())

    def sizeHint(self):
        w = self.currentWidget()
        return w.sizeHint() if w is not None else super().sizeHint()

    def minimumSizeHint(self):
        w = self.currentWidget()
        return w.minimumSizeHint() if w is not None else super().minimumSizeHint()

    def fade_to(self, index):
        if index == self.currentIndex():
            return
        old = self.currentWidget()
        overlay = None
        if old is not None and self.isVisible():
            overlay = QLabel(self)
            overlay.setPixmap(old.grab())
            overlay.setGeometry(self.rect())
            overlay.show()
        self.setCurrentIndex(index)
        if overlay is not None:
            overlay.raise_()
            effect = QGraphicsOpacityEffect(overlay)
            overlay.setGraphicsEffect(effect)
            anim = QPropertyAnimation(effect, b"opacity", overlay)
            anim.setDuration(200)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.finished.connect(overlay.deleteLater)
            anim.start()


# ============================================================
# Avisos flotantes ("toasts")
# ============================================================

class Toast(QLabel):
    COLORS = {"info": "#FFFFFF", "success": "#3DDC97", "error": "#FF7A7E", "warning": theme.WARM}
    ICONS = {"info": "info", "success": "check", "error": "warning", "warning": "warning"}

    def __init__(self, parent):
        super().__init__(parent)
        self.hide()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Haz clic para cerrar")
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(220)
        self._timer = QTimer(self, singleShot=True, interval=2400)
        self._timer.timeout.connect(self._fade_out)
        self._anim.finished.connect(self._on_anim_done)

    def show_message(self, text, kind="info"):
        color = self.COLORS.get(kind, "#FFFFFF")
        glyph = theme.ICONS[self.ICONS.get(kind, "info")]
        icons = theme.icon_family()
        # El texto puede traer nombres de archivo o de personas: siempre como texto, nunca HTML
        body = html.escape(text).replace("\n", "<br>")
        close = ""
        if kind == "error":  # los errores se quedan hasta que les den clic
            close = (f'&nbsp;&nbsp;&nbsp;<span style="font-family:\'{icons}\'; color:#9FB3BA;">'
                     f'{theme.ICONS["clear"]}</span>')
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setText(f'<span style="font-family:\'{icons}\'; color:{color};">{glyph}</span>'
                     f'&nbsp;&nbsp;{body}{close}')
        self.setStyleSheet(f"background: {theme.TEXT}; color: white; border-radius: 16px;"
                           "padding: 12px 20px; font-size: 14px;")
        self.setWordWrap(False)
        self.adjustSize()
        parent = self.parentWidget()
        limit = min(720, max(320, (parent.width() if parent else 900) - 120))
        if self.width() > limit:  # mensaje largo: en varias lineas
            self.setWordWrap(True)
            self.resize(limit, self.heightForWidth(limit))
        self.reposition()
        self.raise_()
        self.show()
        self._anim.stop()
        self._anim.setStartValue(self._effect.opacity() if self.isVisible() else 0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        if kind == "error":
            self._timer.stop()
        else:  # mas tiempo para leer los mensajes largos
            self._timer.start(max(2400, min(9000, 1800 + 60 * len(text))))

    def mousePressEvent(self, event):
        self._timer.stop()
        self._fade_out()

    def reposition(self):
        parent = self.parentWidget()
        if parent:
            self.move((parent.width() - self.width()) // 2, parent.height() - self.height() - 36)

    def _fade_out(self):
        self._anim.stop()
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.start()

    def _on_anim_done(self):
        if self._effect.opacity() < 0.01:
            self.hide()


# ============================================================
# Video con el esqueleto de las manos y animaciones
# ============================================================

class VideoView(QWidget):
    """Muestra la camara con esquinas redondeadas y dibuja encima las manos."""

    HAND_COLORS = {RIGHT: theme.WARM, LEFT: theme.ACCENT_2}
    retry = Signal()  # "Intentar de nuevo" despues de un error de camara

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(240, 180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._retry_btn = button("Intentar de nuevo", "primary", "refresh")
        self._retry_btn.setParent(self)
        self._retry_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # que Espacio no lo presione
        self._retry_btn.clicked.connect(self.retry)
        self._retry_btn.hide()
        self._image = None
        self._hands = None
        self._state = "starting"
        self._message = ""
        self._overlay = None
        self._flash = None
        self._last_hands_t = 0.0
        self._timer = QTimer(self, interval=33)  # anima spinner y pulsos
        self._timer.timeout.connect(self.update)

    def showEvent(self, event):
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_retry()

    # ---- API ----
    def set_frame(self, packet):
        self._image = packet.image
        self._hands = packet.hands
        self._state = "live"
        if packet.hands.any:
            self._last_hands_t = time.monotonic()
        if self._retry_btn.isVisible():
            self._retry_btn.hide()

    def set_state(self, state, message=""):
        self._state, self._message = state, message
        if state != "live":
            self._image = None
        self._retry_btn.setVisible(state == "error")
        self._place_retry()
        self.update()

    def _place_retry(self):
        if self._state != "error":
            return
        btn = self._retry_btn
        btn.resize(btn.sizeHint())
        _, _, text_rect = self._center_block(self._image_rect(), self._message, btn.height() + 18)
        btn.move(int(text_rect.center().x() - btn.width() / 2), int(text_rect.bottom() + 18))

    def set_overlay(self, overlay):
        self._overlay = overlay

    def flash(self, color):
        self._flash = (QColor(color), time.monotonic())

    def hands_visible_recently(self):
        return time.monotonic() - self._last_hands_t < 0.6

    # ---- Dibujo ----
    def _image_rect(self):
        r = QRectF(self.rect())
        if self._image is None:
            return r
        iw, ih = self._image.width(), self._image.height()
        scale = min(r.width() / iw, r.height() / ih)
        w, h = iw * scale, ih * scale
        return QRectF(r.center().x() - w / 2, r.center().y() - h / 2, w, h)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        ir = self._image_rect()
        radius = 22.0
        path = QPainterPath()
        path.addRoundedRect(ir, radius, radius)
        p.fillPath(path, QColor(theme.VIDEO_BG))

        if self._state == "live" and self._image is not None:
            p.save()
            p.setClipPath(path)
            p.drawImage(ir, self._image)
            # vineta sutil para que el texto encima se lea mejor
            grad = QLinearGradient(ir.topLeft(), ir.bottomLeft())
            grad.setColorAt(0, QColor(0, 0, 0, 70))
            grad.setColorAt(0.25, QColor(0, 0, 0, 0))
            grad.setColorAt(0.75, QColor(0, 0, 0, 0))
            grad.setColorAt(1, QColor(0, 0, 0, 90))
            p.fillRect(ir, grad)
            if self._hands is not None:
                self._draw_hands(p, ir)
            self._draw_overlay(p, ir)
            p.restore()
            self._draw_hands_chip(p, ir)
        elif self._state == "error":
            self._draw_center_icon(p, ir, "camera", theme.AMBER, self._message,
                                   extra=self._retry_btn.sizeHint().height() + 18)
        else:
            self._draw_spinner(p, ir, self._message or "Encendiendo la cámara…")

        # Borde (y destello de exito/error)
        border = QColor(theme.BORDER)
        width = 1.0
        if self._overlay and self._overlay.get("type") == "recording":
            pulse = 0.55 + 0.45 * math.sin(time.monotonic() * 6)
            border = QColor(theme.RED)
            border.setAlphaF(0.6 + 0.4 * pulse)
            width = 3.0
        if self._flash:
            color, start = self._flash
            k = 1 - (time.monotonic() - start) / 0.6
            if k > 0:
                border = QColor(color)
                border.setAlphaF(max(0.0, k))
                width = 4.0
            else:
                self._flash = None
        p.setPen(QPen(border, width))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(ir.adjusted(width / 2, width / 2, -width / 2, -width / 2), radius, radius)

    def _draw_hands(self, p, ir):
        img = self._hands.image
        for slot in (LEFT, RIGHT):
            pts = img[slot]
            if pts[0, 0] != pts[0, 0]:  # NaN: no hay mano
                continue
            color = QColor(self.HAND_COLORS[slot])
            coords = [QPointF(ir.left() + x * ir.width(), ir.top() + y * ir.height()) for x, y, _ in pts]
            glow = QColor(color)
            glow.setAlpha(70)
            p.setPen(QPen(glow, 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for a, b in HAND_CONNECTIONS:
                p.drawLine(coords[a], coords[b])
            p.setPen(QPen(color, 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for a, b in HAND_CONNECTIONS:
                p.drawLine(coords[a], coords[b])
            p.setPen(QPen(color, 1.6))
            p.setBrush(QColor("white"))
            for i, c in enumerate(coords):
                r = 4.2 if i in (4, 8, 12, 16, 20) else 2.8
                p.drawEllipse(c, r, r)

    def _draw_hands_chip(self, p, ir):
        if self._overlay and self._overlay.get("type") in ("countdown", "paused", "done"):
            return
        ok = self.hands_visible_recently()
        text = "Manos detectadas" if ok else "No veo tus manos"
        color = QColor(theme.GREEN if ok else theme.AMBER)
        font = theme.ui_font(13, QFont.Weight.DemiBold)
        p.setFont(font)
        w = p.fontMetrics().horizontalAdvance(text) + 38
        rect = QRectF(ir.right() - w - 16, ir.top() + 16, w, 30)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(12, 13, 18, 190))
        p.drawRoundedRect(rect, 15, 15)
        p.setBrush(color)
        p.drawEllipse(QPointF(rect.left() + 16, rect.center().y()), 4.5, 4.5)
        p.setPen(QColor("white"))
        p.drawText(rect.adjusted(28, 0, -10, 0), Qt.AlignmentFlag.AlignVCenter, text)

    def _veil(self, p, ir, alpha):
        p.fillRect(ir, QColor(8, 9, 13, alpha))

    def _draw_overlay(self, p, ir):
        ov = self._overlay
        if not ov:
            return
        kind = ov.get("type")
        center = ir.center()
        if kind == "countdown":
            small = ov.get("small", False)
            self._veil(p, ir, 90 if small else 150)
            total = max(0.01, ov.get("total", 3.0))
            remaining = max(0.0, ov.get("remaining", 0.0))
            k = max(0.55, min(1.0, ir.height() / 440))  # video chico (ventana chica): todo mas pequeno
            radius = (46 if small else 78) * k
            ring = QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
            p.setPen(QPen(QColor(255, 255, 255, 40), 8))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(ring)
            grad = QConicalGradient(center, 90)
            grad.setColorAt(0, QColor(theme.ACCENT_2))
            grad.setColorAt(0.5, QColor(theme.WARM))
            grad.setColorAt(1, QColor(theme.ACCENT_2))
            p.setPen(QPen(QBrush(grad), 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(ring, 90 * 16, int(360 * 16 * remaining / total))
            p.setPen(QColor("white"))
            if small:
                p.setFont(theme.ui_font(15, QFont.Weight.DemiBold))
                p.drawText(QRectF(ir.left(), ring.bottom() + 10, ir.width(), 30),
                           Qt.AlignmentFlag.AlignHCenter, ov.get("caption", "Regresa a reposo…"))
                p.setFont(theme.icon_font(30))
                p.drawText(ring, Qt.AlignmentFlag.AlignCenter, theme.ICONS["hand"])
            else:
                p.setFont(theme.ui_font(int(74 * k), QFont.Weight.Bold, display=True))
                p.drawText(ring, Qt.AlignmentFlag.AlignCenter, str(max(1, math.ceil(remaining))))
                p.setFont(theme.ui_font(int(30 * k), QFont.Weight.Bold, display=True))
                p.drawText(QRectF(ir.left(), ring.top() - 64 * k, ir.width(), 44 * k),
                           Qt.AlignmentFlag.AlignHCenter, ov.get("title", ""))
                p.setFont(theme.ui_font(15))
                p.setPen(QColor(theme.TEXT_2))
                p.drawText(QRectF(ir.left(), ring.bottom() + 14 * k, ir.width(), 30),
                           Qt.AlignmentFlag.AlignHCenter, ov.get("caption", "Prepárate"))
        elif kind == "recording":
            progress = max(0.0, min(1.0, ov.get("progress", 0.0)))
            # Chip "GRABANDO"
            pulse = 0.5 + 0.5 * math.sin(time.monotonic() * 8)
            chip_rect = QRectF(ir.left() + 16, ir.top() + 16, 128, 30)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(12, 13, 18, 200))
            p.drawRoundedRect(chip_rect, 15, 15)
            dot = QColor(theme.RED)
            dot.setAlphaF(0.55 + 0.45 * pulse)
            p.setBrush(dot)
            p.drawEllipse(QPointF(chip_rect.left() + 16, chip_rect.center().y()), 5.5, 5.5)
            p.setPen(QColor("white"))
            p.setFont(theme.ui_font(13, QFont.Weight.Bold))
            p.drawText(chip_rect.adjusted(30, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, "GRABANDO")
            # Barra de progreso del clip
            bar = QRectF(ir.left() + 24, ir.bottom() - 30, ir.width() - 48, 8)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 50))
            p.drawRoundedRect(bar, 4, 4)
            fill = QRectF(bar.left(), bar.top(), max(8.0, bar.width() * progress), bar.height())
            grad = QLinearGradient(bar.topLeft(), bar.topRight())
            grad.setColorAt(0, QColor(theme.ACCENT_2))
            grad.setColorAt(1, QColor(theme.WARM))
            p.setBrush(grad)
            p.drawRoundedRect(fill, 4, 4)
            if ov.get("title"):
                p.setPen(QColor("white"))
                p.setFont(theme.ui_font(22, QFont.Weight.Bold, display=True))
                p.drawText(QRectF(ir.left(), ir.bottom() - 76, ir.width(), 36),
                           Qt.AlignmentFlag.AlignHCenter, ov["title"])
        elif kind == "paused":
            self._veil(p, ir, 170)
            self._draw_center_icon(p, ir, "pause", "#FFFFFF", ov.get("caption", "En pausa"))
        elif kind == "done":
            self._veil(p, ir, 170)
            self._draw_center_icon(p, ir, "check", theme.GREEN, ov.get("caption", "¡Listo!"))

    @staticmethod
    def _center_block(ir, text, extra=0.0):
        """Icono + texto centrados en el video (extra: espacio de abajo para un boton)."""
        font = theme.ui_font(16, QFont.Weight.DemiBold)
        width = max(40.0, ir.width() - 80)
        flags = int(Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap)
        text_h = QFontMetrics(font).boundingRect(QRect(0, 0, int(width), 10000), flags, text).height() if text else 0
        top = ir.center().y() - (72 + 16 + text_h + extra) / 2
        badge = QRectF(ir.center().x() - 36, top, 72, 72)
        return font, badge, QRectF(ir.left() + 40, badge.bottom() + 16, width, text_h + 4)

    def _draw_center_icon(self, p, ir, icon, color, text, extra=0.0):
        font, badge, text_rect = self._center_block(ir, text, extra)
        bg = QColor(color)
        bg.setAlpha(40)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawEllipse(badge)
        p.setPen(QColor(color))
        p.setFont(theme.icon_font(30))
        p.drawText(badge, Qt.AlignmentFlag.AlignCenter, theme.ICONS[icon])
        p.setPen(QColor("white"))
        p.setFont(font)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap, text)

    def _draw_spinner(self, p, ir, text):
        c = ir.center()
        r = QRectF(c.x() - 22, c.y() - 40, 44, 44)
        p.setPen(QPen(QColor(255, 255, 255, 45), 4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(r)
        angle = int((time.monotonic() * 360) % 360)
        p.setPen(QPen(QColor(theme.ACCENT_2), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(r, -angle * 16, 100 * 16)
        p.setPen(QColor(255, 255, 255, 190))
        p.setFont(theme.ui_font(14))
        p.drawText(QRectF(ir.left(), r.bottom() + 16, ir.width(), 30), Qt.AlignmentFlag.AlignHCenter, text)
