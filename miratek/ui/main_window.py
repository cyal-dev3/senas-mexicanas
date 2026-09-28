"""Ventana principal: barra lateral con los pasos y el area de contenido."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (QButtonGroup, QHBoxLayout, QMainWindow, QMessageBox, QPushButton,
                               QVBoxLayout, QWidget)

from .. import config
from . import theme
from .dialogs import SettingsDialog
from .pages.home import HomePage
from .pages.live import LivePage
from .pages.record import RecordPage
from .pages.share import SharePage
from .pages.train import TrainPage
from .widgets import Avatar, FadeStack, Logo, Toast, button, label

NAV = (
    ("home", "Inicio", "home"),
    ("record", "Grabar", "record"),
    ("train", "Entrenar", "train"),
    ("live", "Probar", "live"),
    ("share", "Compartir", "share"),
)


class MainWindow(QMainWindow):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(config.APP_NAME + (" · demostración" if ctx.demo else ""))
        self.resize(1360, 860)
        self.setMinimumSize(1100, 720)

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._build_sidebar())

        self.stack = FadeStack()
        self.pages = {
            "home": HomePage(ctx),
            "record": RecordPage(ctx),
            "train": TrainPage(ctx),
            "live": LivePage(ctx),
            "share": SharePage(ctx),
        }
        for page in self.pages.values():
            self.stack.addWidget(page)
        lay.addWidget(self.stack, 1)

        self.toast = Toast(root)
        ctx.toast = self.toast.show_message
        ctx.navigate = self.navigate
        ctx.data_changed.connect(self._refresh_user)
        self._current = None
        self._styled = False
        self.navigate("home")

    def _build_sidebar(self):
        side = QWidget()
        side.setObjectName("Sidebar")
        side.setFixedWidth(248)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(18, 26, 18, 20)
        lay.setSpacing(6)

        brand = QHBoxLayout()
        brand.setSpacing(12)
        brand.addWidget(Logo(40))
        names = QVBoxLayout()
        names.setSpacing(0)
        title = label(config.APP_NAME)
        title.setStyleSheet("font-size: 19px; font-weight: 700; font-family: 'Segoe UI Variable Display';")
        names.addWidget(title)
        names.addWidget(label("Lengua de Señas Mexicana", "muted"))
        brand.addLayout(names)
        lay.addLayout(brand)
        lay.addSpacing(28)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = {}
        for key, text, icon in NAV:
            b = QPushButton(f"  {text}")
            b.setObjectName("NavButton")
            b.setCheckable(True)
            b.setIcon(theme.glyph_icon(icon, theme.TEXT_2, 20))
            b.setIconSize(QSize(20, 20))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.navigate(k))
            self.nav_group.addButton(b)
            self.nav_buttons[key] = b
            lay.addWidget(b)
        lay.addStretch()

        if self.ctx.demo:
            demo = label("Modo demostración: cámara simulada", "muted", wrap=True)
            demo.setStyleSheet(f"color: {theme.AMBER}; font-size: 12px;")
            lay.addWidget(demo)
            lay.addSpacing(8)

        user = QWidget()
        user.setObjectName("UserChip")
        user.setStyleSheet(f"#UserChip {{ background: {theme.SURFACE_2}; border-radius: 16px; }}")
        ul = QHBoxLayout(user)
        ul.setContentsMargins(12, 10, 8, 10)
        ul.setSpacing(10)
        self.avatar = Avatar(self.ctx.settings.signer_name, 36)
        ul.addWidget(self.avatar)
        col = QVBoxLayout()
        col.setSpacing(0)
        self.user_name = label(self.ctx.settings.signer_name)
        self.user_name.setStyleSheet("font-weight: 600;")
        col.addWidget(self.user_name)
        col.addWidget(label("Grabando como", "muted"))
        ul.addLayout(col, 1)
        gear = button("", "ghost", "settings")
        gear.setToolTip("Ajustes")
        gear.clicked.connect(self._open_settings)
        ul.addWidget(gear)
        lay.addWidget(user)
        return side

    def _refresh_user(self):
        name = self.ctx.settings.signer_name
        self.avatar.set_name(name)
        self.user_name.setText(name)

    def navigate(self, key, **kwargs):
        page = self.pages[key]
        if self._current is not None and self._current is not page:
            self._current.on_leave()
        self._current = page
        for k, b in self.nav_buttons.items():
            b.setChecked(k == key)
            b.setIcon(theme.glyph_icon(dict((n[0], n[2]) for n in NAV)[k],
                                       theme.ACCENT_DEEP if k == key else theme.TEXT_2, 20))
        self.stack.fade_to(self.stack.indexOf(page))
        page.on_enter(**kwargs)

    def _open_settings(self):
        SettingsDialog(self.ctx, self).exec()

    def showEvent(self, event):
        if not self._styled:
            theme.apply_title_bar(self)
            self._styled = True
        super().showEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.toast.reposition()

    def closeEvent(self, event):
        train = self.pages["train"]
        if train.worker is not None:
            answer = QMessageBox.question(self, "Entrenando", "El modelo se está entrenando. ¿Salir de todos modos?")
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            train.worker.cancel()
            train.worker.wait(5000)
        if self._current is not None:
            self._current.on_leave()
        self.ctx.camera.shutdown()
        super().closeEvent(event)
