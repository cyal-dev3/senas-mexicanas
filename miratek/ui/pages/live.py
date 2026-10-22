"""
Prueba en vivo: la camara reconoce senas y arma frases.

Tres modos (cada uno solo "compite" contra su categoria):
  - Palabras: cada sena reconocida se agrega como una palabra.
  - Deletreo: las letras se juntan en una palabra (H-O-L-A -> HOLA).
  - Numeros: como en LSM (20 y 3 = 23; 100, 20 y 5 = 125).
Bajar las manos (o hacer "Nada") medio segundo termina la palabra o el numero:
una sola prediccion de "Nada" o un frame sin manos no la corta.
"""

from PySide6.QtCore import Qt, QVariantAnimation
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ... import config
from ...phrase import PhraseBuilder
from ...recognizer import LiveRecognizer
from .. import sounds, theme
from ..widgets import (BarRow, Card, FlowLayout, IconBadge, ProgressRing, Segmented, VideoView, button,
                       chip, label, side_scroll)
from .base import Page


class LivePage(Page):
    title = "Probar en vivo"
    subtitle = "Haz señas frente a la cámara. Cuando la app está segura, las agrega a la frase."

    def __init__(self, ctx):
        super().__init__(ctx, scroll=False)
        self.recognizer = None
        self.mode = config.WORDS
        self.phrase = PhraseBuilder()
        self._model_ref = None
        self._suspended = False  # Ajustes abierto, otra ventana activa o app minimizada

        self.empty = self._build_empty()
        self.main = self._build_main()
        self.body.addWidget(self.empty, 1)
        self.body.addWidget(self.main, 1)
        ctx.camera.frame.connect(self._on_frame)
        ctx.camera.status.connect(self._on_camera_status)
        ctx.model_changed.connect(self._reset_recognizer)
        ctx.settings_changed.connect(self._apply_hand)

    def _build_empty(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(14)
        lay.addWidget(IconBadge("train", theme.ACCENT, 76), 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(label("Todavía no hay un modelo", "h2", align=Qt.AlignmentFlag.AlignCenter))
        lay.addWidget(label("Graba algunas señas y entrena el modelo para poder probarlo aquí.", "body",
                            align=Qt.AlignmentFlag.AlignCenter))
        go = button("Ir a entrenar", "primary", "next")
        go.clicked.connect(lambda: self.ctx.navigate("train"))
        lay.addWidget(go, 0, Qt.AlignmentFlag.AlignHCenter)
        return w

    def _build_main(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(20)
        self.video = VideoView()
        self.video.retry.connect(self.ctx.camera.restart)
        lay.addWidget(self.video, 1)

        side_holder = QWidget()
        side = QVBoxLayout(side_holder)
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(16)
        # --- Lo que esta viendo ---
        seeing = Card(padding=24, spacing=8)
        self.mode_switch = Segmented([(config.WORDS, "Palabras"), (config.LETTERS, "Deletreo"),
                                      (config.NUMBERS, "Números")], self.mode)
        self.mode_switch.changed.connect(self._set_mode)
        seeing.body.addWidget(self.mode_switch)
        seeing.body.addSpacing(6)
        seeing.body.addWidget(label("ESTOY VIENDO", "overline"))
        row = QHBoxLayout()
        self.current = label("—")
        self.current.setStyleSheet("font-size: 46px; font-weight: 800; font-family: 'Segoe UI Variable Display';")
        row.addWidget(self.current, 1)
        self.conf_ring = ProgressRing(78, 8)
        row.addWidget(self.conf_ring)
        seeing.body.addLayout(row)
        self.hint = label("", "muted", wrap=True)
        seeing.body.addWidget(self.hint)
        self.top_rows = [BarRow("", label_width=110) for _ in range(3)]
        for r in self.top_rows:
            seeing.body.addWidget(r)
        side.addWidget(seeing)

        # --- Frase ---
        phrase = Card(padding=24, spacing=12)
        ph = QHBoxLayout()
        ph.addWidget(label("FRASE", "overline"))
        ph.addStretch()
        back = button("", "ghost", "undo")
        back.setToolTip("Borrar lo último")
        back.clicked.connect(self._delete_last)
        ph.addWidget(back)
        clear = button("Borrar todo", "ghost", "clear")
        clear.clicked.connect(self._clear)
        ph.addWidget(clear)
        phrase.body.addLayout(ph)
        holder = QWidget()
        holder.setMinimumHeight(90)
        self.flow = FlowLayout(holder, spacing=8)
        phrase.body.addWidget(holder)
        self.phrase_hint = label("Las señas que reconozca aparecerán aquí.", "muted", wrap=True)
        phrase.body.addWidget(self.phrase_hint)
        side.addWidget(phrase, 1)

        # --- Sensibilidad ---
        sens = Card(soft=True, padding=18, spacing=8)
        sr = QHBoxLayout()
        sr.addWidget(label("Sensibilidad", "body"))
        sr.addStretch()
        seg = Segmented([("baja", "Baja"), ("media", "Media"), ("alta", "Alta")], self.ctx.settings.sensitivity)
        seg.changed.connect(self._set_sensitivity)
        sr.addWidget(seg)
        sens.body.addLayout(sr)
        side.addWidget(sens)
        lay.addWidget(side_scroll(side_holder, 310, 380))  # en pantallas chicas se desplaza

        self._fade = QVariantAnimation(self, duration=260, startValue=0.35, endValue=1.0)
        self._fade.valueChanged.connect(
            lambda v: self.current.setStyleSheet(
                f"font-size: 46px; font-weight: 800; font-family: 'Segoe UI Variable Display';"
                f"color: rgba(10,37,48,{float(v):.2f});"))
        return w

    # ---------------- Ciclo de vida ----------------
    def on_enter(self, **kwargs):
        model = self.ctx.model()
        self.empty.setVisible(model is None)
        self.main.setVisible(model is not None)
        if model is None:
            return
        if model is not self._model_ref:
            self._reset_recognizer()
        self.ctx.camera.acquire(self)
        if self.ctx.camera.state != "running":
            self.video.set_state("starting", self.ctx.camera.message or "Encendiendo la cámara…")

    def on_leave(self):
        self.ctx.camera.release(self)
        if self.recognizer:
            self.recognizer.reset()

    def on_pause(self):
        """Mientras la persona no esta en la app no se agregan senas a la frase."""
        self._suspended = True
        self.video.set_overlay({"type": "paused", "caption": "En pausa mientras no estás en la app."})
        self._close_spelling()
        if self.recognizer:
            self.recognizer.reset()

    def on_resume(self):
        self._suspended = False
        self.video.set_overlay(None)
        if self.recognizer:
            self.recognizer.reset()

    def _reset_recognizer(self):
        model = self.ctx.model()
        self._model_ref = model
        if model is None:
            self.recognizer = None
            return
        self.recognizer = LiveRecognizer(model, sensitivity=self.ctx.settings.sensitivity,
                                         mirror=self.ctx.settings.mirror)
        self._apply_mode()

    def _apply_hand(self):
        """La persona cambio (o cambio su mano): las senas se leen con su lateralidad."""
        if self.recognizer and self.recognizer.mirror != self.ctx.settings.mirror:
            self.recognizer.mirror = self.ctx.settings.mirror
            self.recognizer.reset()

    def _set_mode(self, mode):
        self.mode = mode
        self._close_spelling()
        self._apply_mode()

    def _apply_mode(self):
        model = self.ctx.model()
        if not self.recognizer or model is None:
            return
        wanted = [c for c in model.classes
                  if config.category_of(c) == self.mode and c != config.NOTHING_ID]
        if not wanted:
            name = config.CATEGORY_NAMES[self.mode].lower()
            self.hint.setText(f"El modelo todavía no conoce {name}: grábalos y vuelve a entrenar.")
            self.recognizer.set_allowed(None)
        else:
            self.hint.setText({
                config.WORDS: "Haz la seña completa y regresa las manos a reposo.",
                config.LETTERS: "Mantén cada letra un segundo. Baja las manos para terminar la palabra.",
                config.NUMBERS: "Para 23 haz 20 y luego 3; para 125, haz 100, 20 y 5. Baja las manos al terminar.",
            }[self.mode])
            self.recognizer.set_allowed(wanted)

    def _set_sensitivity(self, level):
        self.ctx.settings.sensitivity = level
        self.ctx.settings.save()
        if self.recognizer:
            self.recognizer.set_sensitivity(level)

    # ---------------- Camara ----------------
    def _on_camera_status(self, state, message):
        if self.isVisible() and state in ("starting", "error"):
            self.video.set_state(state, message)

    def _on_frame(self, packet):
        if not self.isVisible() or self.recognizer is None:
            return
        self.video.set_frame(packet)
        if self._suspended:
            return
        self.recognizer.aspect = packet.aspect
        prediction, event = self.recognizer.push(packet.t, packet.hands)
        if prediction is not None:
            self._show_prediction(prediction)
        if event is not None:
            self._add_event(event)

    def _show_prediction(self, pred):
        if pred.word_break:
            # Ya lleva medio segundo sin sena (manos abajo o "Nada"): termina la palabra o el numero
            self._close_spelling()
        if not pred.hands_visible:
            self._set_current("—")
            self.conf_ring.set_value(0)
            self.conf_ring.set_text("")
            for r in self.top_rows:
                r.name.setText("")
                r.set(0, "")
            return
        is_nothing = pred.sign_id == config.NOTHING_ID
        self._set_current("…" if is_nothing else config.sign_name(pred.sign_id))
        self.conf_ring.set_value(pred.confidence)
        self.conf_ring.set_text(f"{round(pred.confidence * 100)}%")
        self.conf_ring.set_color(theme.GREEN if pred.confidence >= self.recognizer.threshold else theme.AMBER)
        for r, (sid, p) in zip(self.top_rows, pred.top + [(None, 0.0)] * 3):
            r.name.setText(config.sign_name(sid) if sid else "")
            r.set(p, f"{round(p * 100)}%" if sid else "", theme.ACCENT if r is self.top_rows[0] else theme.ACCENT_2)

    def _set_current(self, text):
        if self.current.text() != text:
            self.current.setText(text)
            self._fade.start()

    # ---------------- Frase ----------------
    def _add_event(self, event):
        sounds.play("tick")
        self.video.flash(theme.ACCENT)
        self.phrase.add(event.sign_id)
        self._render_phrase()

    def _close_spelling(self):
        self.phrase.close()

    def _delete_last(self):
        self.phrase.delete_last()
        self._render_phrase()

    def _clear(self):
        self.phrase.clear()
        self._render_phrase()

    def _render_phrase(self):
        while self.flow.count():
            item = self.flow.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        texts = self.phrase.texts[-24:]
        for i, text in enumerate(texts):
            self.flow.addWidget(chip(text, highlight=(i == len(texts) - 1)))
        self.phrase_hint.setVisible(not texts)
        self.flow.invalidate()
