"""Compartir: crear el archivo para enviar y abrir archivos de otras personas."""

import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QVBoxLayout, QWidget

from ... import config
from ...export_android import export_for_phone
from ...training import ModelError
from .. import theme
from ..dialogs import ask, inform
from ..widgets import Avatar, Bar, BusyBar, Card, IconBadge, button, label
from ..workers import ExportWorker, ImportWorker
from .base import Page

MAX_SUMMARY_LINES = 12


def show_in_folder(path):
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path.parent)])


def _plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


class SharePage(Page):
    title = "Compartir"
    subtitle = "Manda tus grabaciones a quien coordina, o junta las de varias personas para entrenar con todas."

    def __init__(self, ctx):
        super().__init__(ctx)
        self._last_export = None
        self.worker = None  # importacion o exportacion en curso

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
        self.model_btn = button("Enviar solo el modelo", "secondary", "train")
        self.model_btn.setToolTip("Un archivo pequeño solo con el modelo entrenado, sin grabaciones.")
        self.model_btn.clicked.connect(lambda: self._export(include_clips=False))
        send.body.addWidget(self.model_btn)
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
        self.import_btn = button("Abrir archivos recibidos…", "secondary", "folder")
        self.import_btn.clicked.connect(self._import)
        receive.body.addWidget(self.import_btn)
        row.addWidget(receive, 1)
        self.body.addLayout(row)

        # ---- Resumen de lo recibido (por archivo) ----
        self.import_card = Card(padding=24, spacing=8)
        ih = QHBoxLayout()
        ih.addWidget(label("Lo que se recibió", "h2"))
        ih.addStretch()
        hide_btn = button("Ocultar", "ghost", "clear")
        hide_btn.clicked.connect(lambda: self.import_card.hide())
        ih.addWidget(hide_btn)
        self.import_card.body.addLayout(ih)
        self.import_headline = label("", wrap=True)
        self.import_headline.setStyleSheet("font-weight: 600;")
        self.import_card.body.addWidget(self.import_headline)
        self.import_result = label("", "body", wrap=True)
        self.import_card.body.addWidget(self.import_result)
        self.import_card.hide()
        self.body.addWidget(self.import_card)

        # ---- Trabajando (importar / exportar sin congelar la ventana) ----
        self.busy_card = Card(soft=True, padding=20, spacing=10)
        self.busy_text = label("", "body", wrap=True)
        self.busy_text.setStyleSheet(f"color: {theme.TEXT}; font-weight: 600;")
        self.busy_card.body.addWidget(self.busy_text)
        self.busy_bar = Bar(8)
        self.busy_card.body.addWidget(self.busy_bar)
        self.busy_spin = BusyBar(8)
        self.busy_card.body.addWidget(self.busy_spin)
        self.busy_card.hide()
        self.body.addWidget(self.busy_card)

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
        self.people = Card(padding=28, spacing=12)
        self.people.body.addWidget(label("Personas en tus datos", "h2"))
        self.people_box = QVBoxLayout()
        self.people_box.setSpacing(10)
        self.people.body.addLayout(self.people_box)
        self.body.addWidget(self.people)
        self.body.addStretch()
        ctx.data_changed.connect(self.refresh)
        ctx.model_changed.connect(self.refresh)

    def on_enter(self, **kwargs):
        self.refresh()

    def refresh(self):
        counts = self.ctx.store.counts_by_signer()
        total = sum(sum(v.values()) for v in counts.values())
        has_model = self.ctx.model() is not None
        busy = self.worker is not None
        extra = " y tu modelo entrenado" if has_model else ""
        self.send_text.setText(
            f"Crea un solo archivo con tus {total} grabaciones{extra}. Queda en tu Escritorio: mándalo "
            "por WhatsApp, correo o USB a quien coordina el proyecto.")
        self.export_btn.setEnabled((total > 0 or has_model) and not busy)
        self.model_btn.setVisible(has_model)
        self.model_btn.setEnabled(not busy)
        self.import_btn.setEnabled(not busy)
        self.phone_btn.setEnabled(has_model and not busy)
        self.people.setEnabled(not busy)
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

    # ---------------- Trabajando ----------------
    def _set_busy(self, text, fraction=None):
        self.busy_text.setText(text)
        self.busy_bar.setVisible(fraction is not None)
        self.busy_spin.setVisible(fraction is None)
        if fraction is not None:
            self.busy_bar.set_value(fraction)
        self.busy_card.show()
        for b in (self.export_btn, self.model_btn, self.import_btn, self.phone_btn):
            b.setEnabled(False)
        self.people.setEnabled(False)

    def _on_worker_finished(self):
        self.worker = None
        self.busy_card.hide()
        self.refresh()

    # ---------------- Enviar ----------------
    def _export(self, include_clips):
        if self.worker is not None:
            return
        model = self.ctx.model_path if self.ctx.model() is not None else None
        self.worker = ExportWorker(self.ctx.store, config.desktop_dir(), self.ctx.settings.signer_name or "persona",
                                   model_path=model, log_path=self.ctx.log_path, include_clips=include_clips)
        self.worker.done.connect(self._on_exported)
        self.worker.failed.connect(lambda message: self.ctx.toast(message, "error"))
        self.worker.finished.connect(self._on_worker_finished)
        self._set_busy("Creando el archivo con tus grabaciones…" if include_clips else
                       "Creando el archivo con tu modelo…")
        self.worker.start()

    def _on_exported(self, path):
        self._last_export = path
        try:
            size = f" ({path.stat().st_size / 1e6:.1f} MB)"
        except OSError:
            size = ""
        self.export_label.setText(f"✓ Listo: «{path.name}»{size} está en tu Escritorio.")
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

    # ---------------- Recibir ----------------
    def _import(self):
        if self.worker is not None:
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Abrir archivos de Mira&Tek", str(config.desktop_dir()),
                                                "Archivos de Mira&Tek (*.zip)")
        if not files:
            return
        self.worker = ImportWorker(self.ctx.store, files, self.ctx.models_dir)
        self.worker.progress.connect(self._on_import_progress)
        self.worker.done.connect(self._on_imported)
        self.worker.finished.connect(self._on_worker_finished)
        self._set_busy(f"Abriendo {_plural(len(files), 'archivo', 'archivos')}…", 0.0)
        self.worker.start()

    def _on_import_progress(self, done, total, name):
        text = f"Abriendo archivo {done + 1} de {total}: «{name}»…" if name else "Terminando…"
        self._set_busy(text, done / max(1, total))

    def _on_imported(self, results):
        self.ctx.data_changed.emit()  # aunque algun archivo falle, pudo agregar grabaciones antes del error
        names = self.ctx.store.signer_names()
        added = skipped = invalid = failed = 0
        people = set()
        models = []
        lines = []
        for item in results:
            if item.error:
                failed += 1
                lines.append(f"• {item.name}: no se pudo abrir. {item.error}")
                continue
            r = item.result
            added += r.added
            skipped += r.skipped
            invalid += r.invalid
            people.update(r.signers)
            parts = []
            if r.added:
                who = ", ".join(f"{names.get(s, s)} ({n})" for s, n in
                                sorted(r.signers.items(), key=lambda kv: -kv[1]))
                parts.append(f"{_plural(r.added, 'grabación nueva', 'grabaciones nuevas')} de {who}")
            if r.skipped:
                parts.append(f"{r.skipped} ya {'la tenías' if r.skipped == 1 else 'las tenías'}")
            if r.invalid:
                parts.append(f"{r.invalid} no se {'pudo' if r.invalid == 1 else 'pudieron'} leer")
            if r.model_path:
                parts.append("trae un modelo entrenado")
                models.append((r.model_path, str(r.manifest.get("author", "alguien"))[:40]))
            if not parts:
                parts.append("no traía grabaciones")
            lines.append(f"• {item.name}: " + "; ".join(parts) + ".")

        if added:
            headline = (f"Se {'agregó' if added == 1 else 'agregaron'} {_plural(added, 'grabación', 'grabaciones')} de "
                        f"{_plural(len(people), 'persona', 'personas')}.")
        elif failed == len(results):
            headline = "No se pudo abrir ningún archivo."
        else:
            headline = "No había grabaciones nuevas."
        extras = []
        if skipped:
            extras.append(f"{skipped} ya las tenías")
        if invalid:
            extras.append(f"{invalid} no se pudieron leer (quizá el archivo está dañado)")
        if failed:
            extras.append(f"{_plural(failed, 'archivo', 'archivos')} no se {'pudo' if failed == 1 else 'pudieron'} abrir")
        if extras:
            more = "; ".join(extras)
            headline += " " + more[:1].upper() + more[1:] + "."
        shown = lines[:MAX_SUMMARY_LINES]
        if len(lines) > MAX_SUMMARY_LINES:
            shown.append(f"… y {len(lines) - MAX_SUMMARY_LINES} archivos más.")
        details = "\n".join(shown)

        self.import_headline.setText(headline)
        self.import_result.setText(details)
        self.import_card.show()
        if failed or invalid:
            inform(self, "Archivos recibidos", headline, details, warning=True)
        elif added:
            self.ctx.toast(headline, "success")
        else:
            self.ctx.toast(headline)

        if models:
            path, author = models[-1]
            if ask(self, "Modelo recibido",
                   f"El archivo de {author} trae un modelo entrenado.\n¿Quieres usarlo para «Probar en vivo»?",
                   yes="Sí, usarlo", no="No, gracias"):
                try:
                    self.ctx.use_model_file(path)
                    self.ctx.toast("Ahora usas el modelo que te enviaron.", "success")
                except ModelError as exc:
                    self.ctx.toast(str(exc), "error")
        self.refresh()

    def _delete_signer(self, signer_id, name):
        if ask(self, "Borrar grabaciones", f"¿Borrar todas las grabaciones de {name}?\nEsto no se puede deshacer.",
               yes="Borrar", no="Cancelar", danger=True):
            self.ctx.store.delete_signer(signer_id)
            self.ctx.data_changed.emit()
            self.ctx.toast(f"Se borraron las grabaciones de {name}.")
