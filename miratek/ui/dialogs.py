"""Ventanas pequenas: bienvenida (nombre) y ajustes."""

import os
import subprocess
import sys
import threading

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLineEdit,
                               QSpinBox, QVBoxLayout)

from .. import __version__, config
from . import theme
from .widgets import Logo, button, label


class WelcomeDialog(QDialog):
    """Primera vez: pide el nombre de la persona que va a grabar."""

    def __init__(self, parent=None, title="Te damos la bienvenida a Mira&Tek"):
        super().__init__(parent)
        self.setWindowTitle(config.APP_NAME)
        self.setModal(True)
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 36, 40, 32)
        lay.setSpacing(14)
        lay.addWidget(Logo(64), 0, Qt.AlignmentFlag.AlignLeft)
        lay.addSpacing(6)
        lay.addWidget(label(title, "title", wrap=True))
        lay.addWidget(label("Vamos a enseñarle a la computadora la Lengua de Señas Mexicana. "
                            "¿Cómo te llamas?", "subtitle", wrap=True))
        lay.addSpacing(6)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Tu nombre")
        self.name.setMaxLength(40)
        self.name.textChanged.connect(self._validate)
        self.name.returnPressed.connect(self._accept)
        lay.addWidget(self.name)
        lay.addWidget(label("Tu nombre solo sirve para saber de quién es cada grabación.", "muted"))
        lay.addSpacing(10)
        self.ok = button("Empezar", "primary", "next")
        self.ok.setEnabled(False)
        self.ok.clicked.connect(self._accept)
        lay.addWidget(self.ok, 0, Qt.AlignmentFlag.AlignRight)

    def showEvent(self, e):
        theme.apply_title_bar(self)
        super().showEvent(e)

    def _validate(self):
        self.ok.setEnabled(len(self.name.text().strip()) >= 2)

    def _accept(self):
        if self.ok.isEnabled():
            self.accept()

    def value(self):
        return " ".join(self.name.text().split())


class SettingsDialog(QDialog):
    cameras_found = Signal(list)

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Ajustes")
        self.setMinimumWidth(560)
        s = ctx.settings
        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 30, 36, 28)
        lay.setSpacing(16)
        lay.addWidget(label("Ajustes", "title"))

        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        name_row = QHBoxLayout()
        self.name = QLineEdit(s.signer_name)
        self.name.setMaxLength(40)
        name_row.addWidget(self.name, 1)
        other = button("Soy otra persona", "secondary")
        other.setToolTip("Para que otra persona grabe en esta computadora con su propio nombre.")
        other.clicked.connect(self._other_person)
        name_row.addWidget(other)
        form.addRow(label("Nombre", "body"), name_row)

        self.camera = QComboBox()
        self.camera.addItem(f"Cámara {s.camera_index + 1}", s.camera_index)
        self.camera.setEnabled(False)
        self.camera_note = label("Buscando cámaras…", "muted")
        cam_col = QVBoxLayout()
        cam_col.setSpacing(4)
        cam_col.addWidget(self.camera)
        cam_col.addWidget(self.camera_note)
        form.addRow(label("Cámara", "body"), cam_col)

        self.goal = QSpinBox()
        self.goal.setRange(5, 60)
        self.goal.setValue(s.clips_per_sign)
        self.goal.setSuffix(" clips por seña")
        form.addRow(label("Meta", "body"), self.goal)

        self.sounds = QCheckBox("Sonidos durante la grabación")
        self.sounds.setChecked(s.sounds)
        form.addRow(label("Sonido", "body"), self.sounds)
        lay.addLayout(form)

        folder = button("Abrir carpeta de datos", "ghost", "folder")
        folder.clicked.connect(self._open_folder)
        lay.addWidget(folder, 0, Qt.AlignmentFlag.AlignLeft)

        bottom = QHBoxLayout()
        bottom.addWidget(label(f"{config.APP_NAME} {__version__} · funciona sin internet", "muted"))
        bottom.addStretch()
        cancel = button("Cancelar", "ghost")
        cancel.clicked.connect(self.reject)
        bottom.addWidget(cancel)
        save = button("Guardar", "primary")
        save.clicked.connect(self._save)
        bottom.addWidget(save)
        lay.addLayout(bottom)

        self.cameras_found.connect(self._fill_cameras)
        if ctx.demo:
            QTimer.singleShot(0, lambda: self._fill_cameras([0]))
        else:
            threading.Thread(target=self._probe, daemon=True).start()

    def showEvent(self, e):
        theme.apply_title_bar(self)
        super().showEvent(e)

    def _probe(self):
        try:
            from ..camera import probe_cameras
            if self.ctx.camera.state == "running":
                found = [self.ctx.settings.camera_index]  # no molestar a la camara en uso
            else:
                found = probe_cameras()
        except Exception:
            found = []
        self.cameras_found.emit(found)

    def _fill_cameras(self, found):
        current = self.ctx.settings.camera_index
        self.camera.clear()
        for i in sorted(set(found) | {current}):
            self.camera.addItem(f"Cámara {i + 1}" + ("" if i in found else " (no responde)"), i)
        self.camera.setCurrentIndex(self.camera.findData(current))
        self.camera.setEnabled(True)
        self.camera_note.setText("Si no ves tu imagen, prueba con otra cámara." if len(found) > 1 else
                                 "Solo encontré una cámara." if found else
                                 "No encontré cámaras conectadas.")

    def _other_person(self):
        dialog = WelcomeDialog(self, "¿Quién va a grabar ahora?")
        if dialog.exec():
            self.ctx.settings.new_signer(dialog.value())
            self.ctx.store.set_signer_name(self.ctx.settings.signer_id, self.ctx.settings.signer_name)
            self.name.setText(self.ctx.settings.signer_name)
            self.ctx.data_changed.emit()

    def _open_folder(self):
        path = config.user_data_dir()
        if sys.platform == "win32":
            os.startfile(path)  # noqa: S606 (abre el Explorador)
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _save(self):
        s = self.ctx.settings
        name = " ".join(self.name.text().split())
        if len(name) >= 2 and name != s.signer_name:
            s.signer_name = name
            self.ctx.store.set_signer_name(s.signer_id, name)
        camera = self.camera.currentData()
        camera_changed = camera is not None and camera != s.camera_index
        if camera is not None:
            s.camera_index = int(camera)
        s.clips_per_sign = self.goal.value()
        s.sounds = self.sounds.isChecked()
        s.save()
        from . import sounds
        sounds.enabled = s.sounds
        if camera_changed:
            self.ctx.camera.restart()
        self.ctx.data_changed.emit()
        self.accept()
