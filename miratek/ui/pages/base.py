"""Base comun de las pantallas: encabezado con titulo y contenido con scroll."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from ..widgets import label


class Page(QWidget):
    title = ""
    subtitle = ""

    def __init__(self, ctx, scroll=True):
        super().__init__()
        self.ctx = ctx
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QWidget()
        head = QHBoxLayout(header)
        head.setContentsMargins(40, 34, 40, 18)
        titles = QVBoxLayout()
        titles.setSpacing(6)
        self.title_label = label(self.title, "title")
        self.subtitle_label = label(self.subtitle, "subtitle", wrap=True)
        titles.addWidget(self.title_label)
        titles.addWidget(self.subtitle_label)
        head.addLayout(titles, 1)
        self.header_actions = QHBoxLayout()
        self.header_actions.setSpacing(10)
        head.addLayout(self.header_actions)
        outer.addWidget(header)

        self.content = QWidget()
        self.body = QVBoxLayout(self.content)
        self.body.setContentsMargins(40, 6, 40, 36)
        self.body.setSpacing(18)
        if scroll:
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            area.setWidget(self.content)
            outer.addWidget(area, 1)
        else:
            outer.addWidget(self.content, 1)

    def set_titles(self, title, subtitle=None):
        self.title_label.setText(title)
        if subtitle is not None:
            self.subtitle_label.setText(subtitle)

    def on_enter(self, **kwargs):
        """La pantalla se muestra."""

    def on_leave(self):
        """La pantalla se oculta."""

    def on_pause(self):
        """La app quedo en pausa (Ajustes abierto, otra ventana activa o minimizada)."""

    def on_resume(self):
        """La persona regreso a la app."""
