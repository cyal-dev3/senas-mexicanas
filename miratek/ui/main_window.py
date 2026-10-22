"""Ventana principal: barra lateral con los pasos y el area de contenido."""

import logging
import os
import time

from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QButtonGroup, QHBoxLayout, QMainWindow, QPushButton, QVBoxLayout, QWidget

from .. import config
from . import theme
from .dialogs import SettingsDialog, ask
from .pages.home import HomePage
from .pages.live import LivePage
from .pages.record import RecordPage
from .pages.share import SharePage
from .pages.train import TrainPage
from .widgets import Avatar, FadeStack, Logo, Toast, button, label

log = logging.getLogger(__name__)

NAV = (
    ("home", "Inicio", "home"),
    ("record", "Grabar", "record"),
    ("train", "Entrenar", "train"),
    ("live", "Probar", "live"),
    ("share", "Compartir", "share"),
)

PREFERRED_SIZE = (1360, 860)
CLOSE_WAIT_MS = 4000      # cuanto esperamos a los hilos al cerrar, con la ventana abierta
FORCE_EXIT_MS = 15000     # y despues, ya sin ventana, antes de forzar la salida


class MainWindow(QMainWindow):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(config.APP_NAME + (" · demostración" if ctx.demo else ""))
        self.resize(*PREFERRED_SIZE)
        self.setMinimumSize(960, 600)

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
        ctx.settings_changed.connect(self._refresh_user)
        self._current = None
        self._styled = False
        self._pause_reasons = set()   # ajustes abiertos, app inactiva o minimizada
        self._closing = False
        self._waiting = []            # hilos que esperamos al cerrar (guardamos la referencia)
        app = QGuiApplication.instance()
        if app is not None:
            app.applicationStateChanged.connect(self._on_app_state)
        self.navigate("home")

    def show_initial(self):
        """Abre la ventana; en pantallas chicas (o con zoom de Windows) la maximiza."""
        screen = self.screen() or QGuiApplication.primaryScreen()
        avail = screen.availableGeometry() if screen is not None else None
        if avail is not None and (avail.width() < PREFERRED_SIZE[0] or avail.height() < PREFERRED_SIZE[1]):
            self.resize(min(PREFERRED_SIZE[0], avail.width()), min(PREFERRED_SIZE[1], avail.height()))
            self.showMaximized()
        else:
            self.show()

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
        if self._pause_reasons:
            page.on_pause()

    # ---------------- Pausa automatica ----------------
    # Grabar y Probar no deben seguir solos mientras la persona esta en Ajustes,
    # en otra ventana o con la app minimizada.

    def _pause(self, reason):
        first = not self._pause_reasons
        self._pause_reasons.add(reason)
        if first and self._current is not None:
            self._current.on_pause()

    def _resume(self, reason):
        if reason not in self._pause_reasons:
            return
        self._pause_reasons.discard(reason)
        if not self._pause_reasons and self._current is not None and not self._closing:
            self._current.on_resume()

    def _on_app_state(self, state):
        if state == Qt.ApplicationState.ApplicationActive:
            self._resume("inactiva")
        else:
            self._pause("inactiva")

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized():
                self._pause("minimizada")
            else:
                self._resume("minimizada")

    def _open_settings(self):
        self._pause("ajustes")
        try:
            SettingsDialog(self.ctx, self).exec()
        finally:
            self._resume("ajustes")

    def showEvent(self, event):
        if not self._styled:
            theme.apply_title_bar(self)
            self._styled = True
        super().showEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.toast.reposition()

    # ---------------- Cerrar sin tronar ----------------

    def _alive_threads(self):
        threads = list(self.ctx.camera.alive_threads())
        for worker in (self.pages["train"].worker, self.pages["share"].worker):
            if worker is not None and not worker.isFinished():
                threads.append(worker)
        return threads

    def closeEvent(self, event):
        if self._closing:  # ya estamos esperando a que terminen los hilos
            event.ignore()
            return
        train = self.pages["train"]
        if train.worker is not None:
            if not ask(self, "Entrenando", "El modelo se está entrenando. ¿Salir de todos modos?",
                       yes="Salir", no="Seguir entrenando"):
                event.ignore()
                return
            train.worker.cancel()
        if self._current is not None:
            self._current.on_leave()
        self.ctx.camera.shutdown(CLOSE_WAIT_MS)
        deadline = time.monotonic() + CLOSE_WAIT_MS / 1000
        for worker in self._alive_threads():
            worker.wait(max(0, int((deadline - time.monotonic()) * 1000)))
        alive = self._alive_threads()
        if not alive:
            super().closeEvent(event)
            return
        # Un hilo vivo al salir hace tronar la app: esperamos a que termine sin ventana
        log.warning("Esperando %d hilo(s) antes de salir", len(alive))
        event.ignore()
        self._closing = True
        self._waiting = alive
        app = QApplication.instance()
        app.setQuitOnLastWindowClosed(False)
        self.hide()
        for worker in alive:
            worker.finished.connect(self._finish_closing)
        self._close_poll = QTimer(self, interval=250)
        self._close_poll.timeout.connect(self._finish_closing)
        self._close_poll.start()
        QTimer.singleShot(FORCE_EXIT_MS, self._force_exit)

    def _finish_closing(self):
        if not any(not w.isFinished() for w in self._waiting):
            self._close_poll.stop()
            QApplication.instance().quit()

    def _force_exit(self):
        """Ultimo recurso: un hilo no termino a tiempo. Los datos ya estan guardados."""
        log.error("Un hilo no termino a tiempo: salida forzada")
        logging.shutdown()
        os._exit(0)
