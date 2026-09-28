"""Compartir: crear el archivo para enviar y abrir archivos de otras personas."""

import logging
import os
import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QMessageBox, QVBoxLayout, QWidget

from ... import config
from ...export_android import export_for_phone
from ...package import PackageError, export_package, import_package
from ...training import ModelError
from .. import theme
from ..widgets import Avatar, Card, IconBadge, button, label
from .base import Page


def show_in_folder(path):
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path.parent)])


class SharePage(Page):
    title = "Compartir"
    subtitle = "Manda tus grabaciones a quien coordina, o junta las de varias personas para entrenar con todas."

    def __init__(self, ctx):
        super().__init__(ctx)
        self._last_export = None

        row = QHBoxLayout()
        row.setSpacing(18)

        # ---- Enviar ----
        send = Card(padding=28, spacing=12)
        send.body.addWidget(IconBadge("send", theme.ACCENT, 52))
        send.body.addWidget(label("Enviar mis grabaciones", "h2"))
        self.send_text = label("", "body", wrap=True)
        send.body.addWidget(self.send_text)
        send.body.addStretch()
        self.export_btn = button("Crear archivo para enviar", "primary", "send")
        self.export_btn.clicked.connect(lambda: self._export(include_clips=True))
        send.body.addWidget(self.export_btn)
        self.export_result = QWidget()
        er = QVBoxLayout(self.export_result)
        er.setContentsMargins(0, 6, 0, 0)
        er.setSpacing(8)
        self.export_label = label("", wrap=True)
        self.export_label.setStyleSheet(f"color: {theme.GREEN};")
        er.addWidget(self.export_label)
        open_btn = button("Mostrar en la carpeta", "secondary", "folder")
        open_btn.clicked.connect(lambda: self._last_export and show_in_folder(self._last_export))
        er.addWidget(open_btn)
        self.export_result.hide()
        send.body.addWidget(self.export_result)
        row.addWidget(send, 1)

        # ---- Recibir ----
        receive = Card(padding=28, spacing=12)
        receive.body.addWidget(IconBadge("download", theme.ACCENT_2, 52))
        receive.body.addWidget(label("Recibir archivos", "h2"))
        receive.body.addWidget(label(
            "¿Te mandaron archivos de otras personas? Ábrelos aquí: sus grabaciones se juntan con las "
            "tuyas (sin duplicados) y luego entrenas con todas. Si el archivo trae un modelo, "
            "puedes usarlo para probar.", "body", wrap=True))
        receive.body.addStretch()
        import_btn = button("Abrir archivos recibidos…", "secondary", "folder")
        import_btn.clicked.connect(self._import)
        receive.body.addWidget(import_btn)
        row.addWidget(receive, 1)
        self.body.addLayout(row)

        # ---- Modelo para el celular ----
        phone = Card(padding=28, spacing=12)
        ph = QHBoxLayout()
        ph.setSpacing(20)
        ph.addWidget(IconBadge("phone", theme.WARM_2, 52), 0, Qt.AlignmentFlag.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(6)
        texts.addWidget(label("Modelo para el celular", "h2"))
        self.phone_text = label("", "body", wrap=True)
        texts.addWidget(self.phone_text)
        ph.addLayout(texts, 1)
        self.phone_btn = button("Crear archivo para el celular", "primary", "phone")
        self.phone_btn.clicked.connect(self._export_phone)
        ph.addWidget(self.phone_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        phone.body.addLayout(ph)
        self.phone_result = label("", wrap=True)
        self.phone_result.setStyleSheet(f"color: {theme.GREEN};")
        self.phone_result.hide()
        phone.body.addWidget(self.phone_result)
        self.body.addWidget(phone)

        # ---- Personas ----
        people = Card(padding=28, spacing=12)
        people.body.addWidget(label("Personas en tus datos", "h2"))
        self.people_box = QVBoxLayout()
        self.people_box.setSpacing(10)
        people.body.addLayout(self.people_box)
        self.body.addWidget(people)
        self.body.addStretch()
        ctx.data_changed.connect(self.refresh)

    def on_enter(self, **kwargs):
        self.refresh()

    def refresh(self):
        counts = self.ctx.store.counts_by_signer()
        total = sum(sum(v.values()) for v in counts.values())
        has_model = self.ctx.model() is not None
        extra = " y tu modelo entrenado" if has_model else ""
        self.send_text.setText(
            f"Crea un solo archivo con tus {total} grabaciones{extra}. Queda en tu Escritorio: mándalo "
            "por WhatsApp, correo o USB a quien coordina el proyecto.")
        self.export_btn.setEnabled(total > 0 or has_model)
        self.phone_btn.setEnabled(has_model)
        self.phone_text.setText(
            "Crea el archivo del modelo para la app de Android. Mándalo al celular (WhatsApp, correo o "
            "USB) y ábrelo desde la app: Ajustes › Cargar modelo. Todo funciona sin internet."
            if has_model else "Primero entrena un modelo en la pestaña «Entrenar».")

        while self.people_box.count():
            item = self.people_box.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        names = self.ctx.store.signer_names()
        if not counts:
            self.people_box.addWidget(label("Todavía no hay grabaciones.", "body"))
        for signer_id, per_sign in sorted(counts.items(), key=lambda kv: -sum(kv[1].values())):
            name = names.get(signer_id, signer_id)
            if signer_id == self.ctx.settings.signer_id:
                name = f"{self.ctx.settings.signer_name} (tú)"
            rw = QWidget()
            r = QHBoxLayout(rw)
            r.setContentsMargins(0, 0, 0, 0)
            r.setSpacing(12)
            r.addWidget(Avatar(name, 38))
            col = QVBoxLayout()
            col.setSpacing(0)
            col.addWidget(label(name))
            by_cat = {c: sum(1 for s in per_sign if config.category_of(s) == c and s != config.NOTHING_ID)
                      for c in config.CATEGORIES}
            col.addWidget(label(f"{sum(per_sign.values())} clips · {by_cat[config.WORDS]} palabras · "
                                f"{by_cat[config.LETTERS]} letras · {by_cat[config.NUMBERS]} números", "muted"))
            r.addLayout(col, 1)
            delete = button("Borrar", "danger", "delete", theme.RED)
            delete.clicked.connect(lambda _=False, s=signer_id, n=name: self._delete_signer(s, n))
            r.addWidget(delete)
            self.people_box.addWidget(rw)

    def _export(self, include_clips):
        self.setCursor(Qt.CursorShape.WaitCursor)
        try:
            model = self.ctx.model_path if self.ctx.model() is not None else None
            path = export_package(self.ctx.store, config.desktop_dir(), self.ctx.settings.signer_name or "persona",
                                  model_path=model, log_path=self.ctx.log_path, include_clips=include_clips)
        except (PackageError, OSError) as exc:
            self.ctx.toast(str(exc) if isinstance(exc, PackageError) else "No pude crear el archivo.", "error")
            return
        finally:
            self.unsetCursor()
        self._last_export = path
        size = path.stat().st_size / 1e6
        self.export_label.setText(f"✓ Listo: «{path.name}» ({size:.1f} MB) está en tu Escritorio.")
        self.export_result.show()
        self.ctx.toast("Archivo creado en tu Escritorio.", "success")

    def _export_phone(self):
        model = self.ctx.model()
        if model is None:
            return
        try:
            path = export_for_phone(model, config.desktop_dir())
        except OSError:
            self.ctx.toast("No pude crear el archivo.", "error")
            return
        self._last_export = path
        self.phone_result.setText(f"✓ Listo: «{path.name}» está en tu Escritorio.")
        self.phone_result.show()
        show_in_folder(path)
        self.ctx.toast("Archivo para el celular creado.", "success")

    def _import(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Abrir archivos de Mira&Tek", str(config.desktop_dir()),
                                                "Archivos de Mira&Tek (*.zip)")
        if not files:
            return
        added = skipped = 0
        people = set()
        models = []
        for f in files:
            try:
                result = import_package(self.ctx.store, f, self.ctx.models_dir)
            except PackageError as exc:
                self.ctx.toast(f"{os.path.basename(f)}: {exc}", "error")
                self.ctx.data_changed.emit()  # pudo agregar algunas antes del error
                continue
            except Exception:
                logging.getLogger(__name__).exception("No se pudo importar %s", f)
                self.ctx.toast(f"{os.path.basename(f)}: no pude abrir este archivo.", "error")
                continue
            added += result.added
            skipped += result.skipped
            people.update(result.signers)
            if result.model_path:
                models.append((result.model_path, result.manifest.get("author", "alguien")))
        if added or skipped:
            msg = f"Se agregaron {added} grabaciones de {len(people)} persona(s)."
            if skipped:
                msg += f" {skipped} ya las tenías."
            self.ctx.toast(msg, "success")
            self.ctx.data_changed.emit()
        if models:
            path, author = models[-1]
            answer = QMessageBox.question(
                self, "Modelo recibido",
                f"El archivo de {author} trae un modelo entrenado.\n¿Quieres usarlo para «Probar en vivo»?")
            if answer == QMessageBox.StandardButton.Yes:
                try:
                    self.ctx.use_model_file(path)
                    self.ctx.toast("Ahora usas el modelo que te enviaron.", "success")
                except ModelError as exc:
                    self.ctx.toast(str(exc), "error")
        self.refresh()

    def _delete_signer(self, signer_id, name):
        answer = QMessageBox.warning(
            self, "Borrar grabaciones",
            f"¿Borrar todas las grabaciones de {name}?\nEsto no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self.ctx.store.delete_signer(signer_id)
            self.ctx.data_changed.emit()
            self.ctx.toast(f"Se borraron las grabaciones de {name}.")
