"""Ventanas pequenas: bienvenida (quien graba), ajustes y preguntas."""

import os
import subprocess
import sys
import threading

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QScrollArea, QVBoxLayout, QWidget)

from .. import __version__, config
from . import theme
from .widgets import Avatar, IconBadge, Logo, Segmented, button, label

HAND_OPTIONS = [("derecha", "Derecha"), ("izquierda", "Izquierda"), ("", "No sé")]
GOAL_OPTIONS = (10, 15, 20, 30)
NEW_PERSON = ""  # clave de la fila «Soy alguien nuevo»


def ask(parent, title, text, yes="Sí", no="No", danger=False):
    """Pregunta de si o no, con los botones en espanol. True si eligen «yes»."""
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setIcon(QMessageBox.Icon.Warning if danger else QMessageBox.Icon.Question)
    box.setTextFormat(Qt.TextFormat.PlainText)
    box.setText(text)
    yes_btn = box.addButton(yes, QMessageBox.ButtonRole.YesRole)
    no_btn = box.addButton(no, QMessageBox.ButtonRole.NoRole)
    box.setDefaultButton(no_btn if danger else yes_btn)
    box.setEscapeButton(no_btn)
    box.exec()
    return box.clickedButton() is yes_btn


def inform(parent, title, text, details="", warning=False):
    """Aviso con un boton «Entendido» (los detalles van debajo, como texto simple)."""
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setIcon(QMessageBox.Icon.Warning if warning else QMessageBox.Icon.Information)
    box.setTextFormat(Qt.TextFormat.PlainText)
    box.setText(text)
    if details:
        box.setInformativeText(details)
        for lbl in box.findChildren(QLabel):
            lbl.setTextFormat(Qt.TextFormat.PlainText)  # nombres de archivo, nunca HTML
    box.addButton("Entendido", QMessageBox.ButtonRole.AcceptRole)
    box.exec()


def hand_hint():
    return label("La mano con la que haces la mayoría de las señas. Así la app te entiende igual "
                 "si usas la derecha o la izquierda.", "muted", wrap=True)


def _hand_from_clips(store, signer_id):
    """Con que mano grabo esa persona sus ultimos clips (si se guardo)."""
    try:
        refs = store.list_clips(signer_id)
        refs.sort(key=lambda r: r.path.stat().st_mtime, reverse=True)
        for ref in refs[:5]:
            mirror = store.load(ref).mirror
            if mirror is not None:
                return "izquierda" if mirror else "derecha"
    except Exception:
        pass
    return ""


class PersonRow(QFrame):
    """Una persona en la lista de «¿Quién va a grabar?» (o la fila «Soy alguien nuevo»)."""

    clicked = Signal(str)

    def __init__(self, key, name, detail, new=False):
        super().__init__()
        self.key = key
        self.setObjectName("PersonRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 9, 14, 9)
        lay.setSpacing(12)
        lay.addWidget(IconBadge("person", theme.ACCENT, 36) if new else Avatar(name, 36))
        col = QVBoxLayout()
        col.setSpacing(0)
        title = label(name)
        title.setStyleSheet("font-weight: 600;")
        col.addWidget(title)
        col.addWidget(label(detail, "muted"))
        lay.addLayout(col, 1)
        self.mark = IconBadge("check", theme.ACCENT, 26)
        lay.addWidget(self.mark)
        self.set_selected(False)

    def set_selected(self, selected):
        bg, border = ("#E1F4F7", theme.ACCENT) if selected else (theme.SURFACE, theme.BORDER)
        self.setStyleSheet(f"#PersonRow {{ background: {bg}; border: 1px solid {border}; border-radius: 14px; }}")
        self.mark.setVisible(selected)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.key)


class WelcomeDialog(QDialog):
    """
    Quien va a grabar: la primera vez pide el nombre; si en esta computadora ya
    grabo alguien, deja elegir a esa persona (para no contarla como si fueran
    varias) o registrar a alguien nuevo. Tambien pregunta con que mano hace las senas.
    """

    def __init__(self, store=None, parent=None, title="Te damos la bienvenida a Mira&Tek", current_id="",
                 hand="", current_name=""):
        super().__init__(parent)
        self.store = store
        self.current_id = current_id
        self.setWindowTitle(config.APP_NAME)
        self.setModal(True)
        self.setMinimumWidth(540)
        self._names = {}
        self._rows = {}
        self._selected = None
        self._hand_by_person = {}

        people = self._people(store, current_id, current_name)
        self._known_names = {name.casefold() for _, name, _ in people}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 34, 40, 30)
        lay.setSpacing(12)
        lay.addWidget(Logo(56), 0, Qt.AlignmentFlag.AlignLeft)
        lay.addSpacing(4)
        lay.addWidget(label(title, "title", wrap=True))
        intro = ("¿Quién va a grabar? Si ya grabaste en esta computadora, elige tu nombre para que tus "
                 "grabaciones queden juntas." if people else
                 "Vamos a enseñarle a la computadora la Lengua de Señas Mexicana. ¿Cómo te llamas?")
        lay.addWidget(label(intro, "subtitle", wrap=True))
        lay.addSpacing(4)

        if people:
            holder = QWidget()
            rows = QVBoxLayout(holder)
            rows.setContentsMargins(0, 0, 4, 0)
            rows.setSpacing(8)
            for signer_id, name, clips in people:
                you = " (tú)" if signer_id == current_id else ""
                detail = f"{clips} {'grabación' if clips == 1 else 'grabaciones'} en esta computadora"
                row = PersonRow(signer_id, name + you, detail)
                row.clicked.connect(self._select)
                rows.addWidget(row)
                self._rows[signer_id] = row
            new_row = PersonRow(NEW_PERSON, "Soy alguien nuevo", "Todavía no he grabado aquí", new=True)
            new_row.clicked.connect(self._select)
            rows.addWidget(new_row)
            self._rows[NEW_PERSON] = new_row
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setWidget(holder)
            scroll.setMaximumHeight(min(holder.sizeHint().height() + 4, 300))
            lay.addWidget(scroll)

        self.new_box = QWidget()
        nb = QVBoxLayout(self.new_box)
        nb.setContentsMargins(0, 4, 0, 0)
        nb.setSpacing(6)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Tu nombre")
        self.name.setMaxLength(40)
        self.name.textChanged.connect(self._validate)
        self.name.returnPressed.connect(self._accept)
        nb.addWidget(self.name)
        self.name_note = label("Tu nombre solo sirve para saber de quién es cada grabación.", "muted", wrap=True)
        nb.addWidget(self.name_note)
        lay.addWidget(self.new_box)

        lay.addSpacing(6)
        lay.addWidget(label("¿Con qué mano haces las señas?", "body"))
        self.hand = Segmented(HAND_OPTIONS, hand)
        self.hand.changed.connect(self._remember_hand)
        lay.addWidget(self.hand, 0, Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(hand_hint())

        lay.addSpacing(8)
        bottom = QHBoxLayout()
        bottom.addStretch()
        if parent is not None:
            cancel = button("Cancelar", "ghost")
            cancel.clicked.connect(self.reject)
            bottom.addWidget(cancel)
        self.ok = button("Empezar" if parent is None else "Listo", "primary", "next")
        self.ok.setEnabled(False)
        self.ok.clicked.connect(self._accept)
        bottom.addWidget(self.ok)
        lay.addLayout(bottom)

        if people and current_id in self._rows and current_id != NEW_PERSON:
            self._hand_by_person[current_id] = hand
            self._select(current_id)
        else:
            self._select(None)  # que la persona se elija (o se registre) a conciencia

    @staticmethod
    def _people(store, current_id, current_name=""):
        """[(id, nombre, clips)] de quienes tienen grabaciones en esta computadora."""
        if store is None:
            return []
        counts = {sid: sum(per.values()) for sid, per in store.counts_by_signer().items()}
        names = store.signer_names()
        if current_id and current_name:
            names[current_id] = current_name
        if current_id and current_id in names:
            counts.setdefault(current_id, 0)
        people = [(sid, names.get(sid, sid), n) for sid, n in counts.items()]
        people.sort(key=lambda p: (p[0] != current_id, p[1].casefold()))
        return people

    def showEvent(self, e):
        theme.apply_title_bar(self)
        super().showEvent(e)
        QTimer.singleShot(0, self._focus)

    def _focus(self):
        if self.new_box.isVisible():
            self.name.setFocus()

    def _select(self, key):
        self._selected = key
        for k, row in self._rows.items():
            row.set_selected(k == key)
        self.new_box.setVisible(key == NEW_PERSON or not self._rows)
        if key is not None:
            if key not in self._hand_by_person:
                self._hand_by_person[key] = _hand_from_clips(self.store, key) if key else ""
            self.hand.set_value(self._hand_by_person[key])
        if key == NEW_PERSON:
            self.name.setFocus()
        self._validate()
        self.adjustSize()

    def _remember_hand(self, hand):
        if self._selected is not None:
            self._hand_by_person[self._selected] = hand

    def _is_new(self):
        return not self._rows or self._selected == NEW_PERSON

    def _validate(self):
        if self._is_new():
            text = self.value()
            taken = text.casefold() in self._known_names
            self.name_note.setText("Ya hay una persona con ese nombre. Si eres tú, elige tu nombre en la lista."
                                   if taken and self._rows else
                                   "Tu nombre solo sirve para saber de quién es cada grabación.")
            self.ok.setEnabled(len(text) >= 2)
        else:
            self.ok.setEnabled(self._selected is not None)

    def _accept(self):
        if self.ok.isEnabled():
            self.accept()

    def value(self):
        """El nombre escrito (para alguien nuevo)."""
        return " ".join(self.name.text().split())

    def apply(self, settings, store):
        """Guarda la eleccion: reutiliza a la persona elegida o registra a alguien nuevo."""
        hand = self.hand.value()
        if self._is_new():
            settings.new_signer(self.value(), hand)
        else:
            sid = self._selected
            name = settings.signer_name if sid == settings.signer_id and settings.signer_name else \
                store.signer_names().get(sid, sid)
            settings.use_signer(sid, name, hand)
        store.set_signer_name(settings.signer_id, settings.signer_name)


def _probe_cameras(skip, max_index=4):
    """Indices de camaras que responden, sin tocar las que la app ya tiene abiertas."""
    import cv2
    found = []
    for i in range(max_index):
        if i in skip:
            continue
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY)
        try:
            if cap.isOpened() and cap.read()[0]:
                found.append(i)
        finally:
            cap.release()
    return found


class SettingsDialog(QDialog):
    cameras_found = Signal(list)

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Ajustes")
        self.setMinimumWidth(600)
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
        other = button("Cambiar de persona", "secondary", "person")
        other.setToolTip("Para que otra persona grabe en esta computadora con su propio nombre.")
        other.clicked.connect(self._change_person)
        name_row.addWidget(other)
        form.addRow(label("Nombre", "body"), name_row)

        hand_col = QVBoxLayout()
        hand_col.setSpacing(4)
        hand_col.addWidget(label("¿Con qué mano haces las señas?", "body"))
        self.hand = Segmented(HAND_OPTIONS, s.mano)
        hand_col.addWidget(self.hand, 0, Qt.AlignmentFlag.AlignLeft)
        hand_col.addWidget(hand_hint())
        form.addRow(label("Mano", "body"), hand_col)

        self.camera = QComboBox()
        self.camera.addItem(f"Cámara {s.camera_index + 1}", s.camera_index)
        self.camera.setEnabled(False)
        self.camera_note = label("Buscando cámaras…", "muted", wrap=True)
        cam_col = QVBoxLayout()
        cam_col.setSpacing(4)
        cam_col.addWidget(self.camera)
        cam_col.addWidget(self.camera_note)
        form.addRow(label("Cámara", "body"), cam_col)

        goal_row = QHBoxLayout()
        goal_row.setSpacing(12)
        options = sorted(set(GOAL_OPTIONS) | {s.clips_per_sign})
        self.goal = Segmented([(str(n), str(n)) for n in options], str(s.clips_per_sign))
        goal_row.addWidget(self.goal)
        goal_row.addWidget(label("clips por seña", "body"))
        goal_row.addStretch()
        form.addRow(label("Meta", "body"), goal_row)

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
        self._busy = set() if ctx.demo else ctx.camera.busy_indices()
        if ctx.demo:
            QTimer.singleShot(0, lambda: self._fill_cameras([0]))
        else:
            threading.Thread(target=self._probe, daemon=True).start()

    def showEvent(self, e):
        theme.apply_title_bar(self)
        super().showEvent(e)

    def _probe(self):
        try:
            found = _probe_cameras(self._busy)
        except Exception:
            found = []
        try:
            self.cameras_found.emit(found)
        except RuntimeError:
            pass  # cerraron la ventana antes de terminar de buscar

    def _fill_cameras(self, found):
        current = self.ctx.settings.camera_index
        busy = self._busy
        self.camera.clear()
        for i in sorted(set(found) | busy | {current}):
            extra = " (en uso)" if i in busy else "" if i in found else " (no responde)"
            self.camera.addItem(f"Cámara {i + 1}{extra}", i)
        self.camera.setCurrentIndex(self.camera.findData(current))
        self.camera.setEnabled(True)
        available = set(found) | busy
        self.camera_note.setText("Si no ves tu imagen, prueba con otra cámara." if len(available) > 1 else
                                 "Solo encontré la cámara que estás usando." if busy else
                                 "Solo encontré una cámara." if found else
                                 "No encontré cámaras conectadas.")

    def _change_person(self):
        s = self.ctx.settings
        dialog = WelcomeDialog(self.ctx.store, self, "¿Quién va a grabar ahora?", current_id=s.signer_id,
                               hand=self.hand.value(), current_name=s.signer_name)
        if dialog.exec():
            dialog.apply(s, self.ctx.store)
            self.name.setText(s.signer_name)
            self.hand.set_value(s.mano)
            self.ctx.settings_changed.emit()
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
        s.clips_per_sign = int(self.goal.value())
        s.sounds = self.sounds.isChecked()
        s.mano = self.hand.value()
        s.save()
        from . import sounds
        sounds.enabled = s.sounds
        if camera_changed:
            self.ctx.camera.restart()
        self.ctx.settings_changed.emit()
        self.ctx.data_changed.emit()
        self.accept()
