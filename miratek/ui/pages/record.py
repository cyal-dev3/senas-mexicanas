"""
Grabacion guiada.

La persona elige una sena (o presiona "Continuar grabando") y la app hace
todo sola: cuenta regresiva, graba 2 segundos, revisa que se vieran las manos,
guarda y pasa al siguiente clip. Al completar la meta, sugiere la siguiente sena.
"""

import time

import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from ... import config
from .. import sounds, theme
from ..widgets import (Card, DotsProgress, FadeStack, FlowLayout, IconBadge, ProgressRing, Segmented,
                       VideoView, button, label, side_scroll)
from .base import Page

IDLE, WAIT_CAMERA, COUNTDOWN, RECORDING, PAUSED, SIGN_DONE = range(6)


class SignTile(QFrame):
    clicked = Signal(str)

    def __init__(self, sign):
        super().__init__()
        self.sign = sign
        self.setProperty("card", "true")
        self.setFixedHeight(118)
        self.setMinimumWidth(168)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 16, 14)
        top = QHBoxLayout()
        name = label(sign.name)
        big = sign.category != config.WORDS
        name.setStyleSheet(f"font-size: {30 if big else 16}px; font-weight: {700 if big else 600};"
                           "font-family: 'Segoe UI Variable Display', 'Segoe UI';")
        name.setWordWrap(True)
        top.addWidget(name, 1, Qt.AlignmentFlag.AlignTop)
        self.ring = ProgressRing(40, 5)
        top.addWidget(self.ring, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(top)
        lay.addStretch()
        self.count = label("", "muted")
        lay.addWidget(self.count)
        self._hover = False

    def set_count(self, n, goal):
        self.ring.set_value(min(1.0, n / goal), animate=False)
        done = n >= goal
        self.ring.set_color(theme.GREEN if done else None)
        self.ring.set_text("✓" if done else "")
        self.count.setText(f"{n} de {goal} clips" if n else "Sin grabar")
        self.count.setStyleSheet(f"color: {theme.GREEN if done else theme.TEXT_3}; font-size: 12px;")

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        if self._hover:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            c = QColor(theme.ACCENT)
            c.setAlpha(150)
            p.setPen(c)
            p.drawRoundedRect(self.rect().adjusted(1, 1, -2, -2), 20, 20)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.sign.id)


class RecordPage(Page):
    title = "Grabar señas"
    subtitle = "Elige una seña o presiona «Continuar grabando». La app te guía clip por clip."

    def __init__(self, ctx):
        super().__init__(ctx, scroll=False)
        self.category = config.WORDS
        self.state = IDLE
        self.sign = None
        self.frames = []
        self.session_saved = []
        self._aspect = 4 / 3
        self._deadline = 0.0
        self._first = True
        self._last_beep = None
        self._rec_start = 0.0
        self._status_text = ""
        self._session_signer = ""
        self._auto_paused = False    # la pausa la puso la app (Ajustes, otra ventana), no la persona
        self._pause_caption = ""

        self.stack = FadeStack()
        self.stack.addWidget(self._build_overview())
        self.stack.addWidget(self._build_session())
        self.body.addWidget(self.stack, 1)

        self.timer = QTimer(self, interval=33)
        self.timer.timeout.connect(self._tick)
        ctx.camera.frame.connect(self._on_frame)
        ctx.camera.status.connect(self._on_camera_status)
        ctx.data_changed.connect(self._refresh_tiles)
        ctx.settings_changed.connect(self._on_settings_changed)

        for key, handler in ((Qt.Key.Key_Space, self._toggle_pause),
                             (Qt.Key.Key_Backspace, self._undo),
                             (Qt.Key.Key_Escape, self._finish_session)):
            sc = QShortcut(QKeySequence(key), self.session)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(handler)

    # ============================================================
    # Vista general (lista de senas)
    # ============================================================

    def _build_overview(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(18)

        top = Card(padding=24)
        row = QHBoxLayout()
        row.setSpacing(24)
        self.cat_ring = ProgressRing(96, 9)
        row.addWidget(self.cat_ring)
        texts = QVBoxLayout()
        texts.setSpacing(6)
        self.cat_title = label("", "h2")
        self.cat_text = label("", "body", wrap=True)
        texts.addWidget(self.cat_title)
        texts.addWidget(self.cat_text)
        row.addLayout(texts, 1)
        side = QVBoxLayout()
        side.setSpacing(12)
        self.segment = Segmented([(c, config.CATEGORY_NAMES[c]) for c in config.CATEGORIES], self.category)
        self.segment.changed.connect(self._set_category)
        side.addWidget(self.segment, 0, Qt.AlignmentFlag.AlignRight)
        self.continue_btn = button("Continuar grabando", "primary", "record")
        self.continue_btn.clicked.connect(self._continue)
        side.addWidget(self.continue_btn, 0, Qt.AlignmentFlag.AlignRight)
        row.addLayout(side)
        top.body.addLayout(row)
        lay.addWidget(top)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        holder = QWidget()
        self.flow = FlowLayout(holder, spacing=14, justify=True)
        scroll.setWidget(holder)
        lay.addWidget(scroll, 1)

        self.tiles = {}
        for sign in config.SIGNS:
            tile = SignTile(sign)
            tile.clicked.connect(self.start_session)
            self.tiles[sign.id] = tile
        self._fill_flow()
        return page

    def _fill_flow(self):
        while self.flow.count():
            item = self.flow.takeAt(0)
            if item.widget():
                item.widget().hide()
        for sign in config.signs_in(self.category):
            tile = self.tiles[sign.id]
            self.flow.addWidget(tile)
            tile.show()
        self.flow.invalidate()

    def _set_category(self, category):
        self.category = category
        self._fill_flow()
        self._refresh_tiles()

    def _refresh_tiles(self):
        goal = self.ctx.settings.clips_per_sign
        counts = self.ctx.signer_counts()
        for sign_id, tile in self.tiles.items():
            tile.set_count(counts.get(sign_id, 0), goal)
        signs = config.signs_in(self.category)
        done = sum(min(counts.get(s.id, 0), goal) for s in signs)
        total = goal * len(signs)
        complete = sum(1 for s in signs if counts.get(s.id, 0) >= goal)
        self.cat_ring.set_value(done / total if total else 0)
        self.cat_ring.set_text(f"{complete}/{len(signs)}")
        name = config.CATEGORY_NAMES[self.category]
        remaining = sum(max(0, goal - counts.get(s.id, 0)) for s in signs)
        minutes = max(1, round(remaining * (config.CLIP_SECONDS + config.BETWEEN_CLIPS_SECONDS + 0.4) / 60))
        self.cat_title.setText(f"{name}: {complete} de {len(signs)} completas")
        if remaining:
            self.cat_text.setText(f"Te faltan {remaining} clips (unos {minutes} min). "
                                  "Puedes grabar por partes: tu avance se guarda solo.")
            self.continue_btn.setText("Continuar grabando" if done else "Empezar a grabar")
        else:
            self.cat_text.setText("¡Completaste esta categoría! Grabar más clips siempre ayuda.")
            self.continue_btn.setText("Grabar más")

    def _continue(self):
        goal = self.ctx.settings.clips_per_sign
        counts = self.ctx.signer_counts()
        signs = config.signs_in(self.category)
        pending = [s for s in signs if counts.get(s.id, 0) < goal]
        self.start_session((pending or signs)[0].id)

    # ============================================================
    # Sesion de grabacion
    # ============================================================

    def _build_session(self):
        self.session = QWidget()
        self.session.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        lay = QHBoxLayout(self.session)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(20)
        self.video = VideoView()
        self.video.retry.connect(self._retry_camera)
        lay.addWidget(self.video, 1)

        panel = Card(padding=26, spacing=10)
        self.s_over = label("", "overline")
        panel.body.addWidget(self.s_over)
        self.s_name = label("")
        self.s_name.setWordWrap(True)
        panel.body.addWidget(self.s_name)
        self.s_hint = label("", "body", wrap=True)
        panel.body.addWidget(self.s_hint)
        panel.body.addSpacing(10)
        self.s_clips = label("", "muted")
        panel.body.addWidget(self.s_clips)
        self.dots = DotsProgress()
        panel.body.addWidget(self.dots)
        panel.body.addSpacing(8)
        self.s_status = label("", wrap=True)
        panel.body.addWidget(self.s_status)
        panel.body.addStretch()
        tip = Card(soft=True, padding=16, spacing=6)
        tip_row = QHBoxLayout()
        tip_row.setSpacing(12)
        tip_row.addWidget(IconBadge("light", theme.WARM_2, 36), 0, Qt.AlignmentFlag.AlignTop)
        self.s_tip = label("", "body", wrap=True)
        tip_row.addWidget(self.s_tip, 1)
        tip.body.addLayout(tip_row)
        panel.body.addWidget(tip)
        panel.body.addSpacing(8)

        # Botones durante la grabacion
        self.rec_buttons = QWidget()
        rb = QVBoxLayout(self.rec_buttons)
        rb.setContentsMargins(0, 0, 0, 0)
        rb.setSpacing(8)
        self.pause_btn = button("Pausar", "secondary", "pause")
        self.pause_btn.clicked.connect(self._toggle_pause)
        rb.addWidget(self.pause_btn)
        row = QHBoxLayout()
        self.undo_btn = button("Borrar último", "ghost", "undo")
        self.undo_btn.clicked.connect(self._undo)
        row.addWidget(self.undo_btn)
        stop_btn = button("Terminar", "ghost", "back")
        stop_btn.clicked.connect(self._finish_session)
        row.addWidget(stop_btn)
        rb.addLayout(row)
        keys = label("Espacio: pausar · Retroceso: borrar último · Esc: terminar", "muted", wrap=True)
        rb.addWidget(keys)
        panel.body.addWidget(self.rec_buttons)

        # Botones al terminar una sena
        self.done_buttons = QWidget()
        db = QVBoxLayout(self.done_buttons)
        db.setContentsMargins(0, 0, 0, 0)
        db.setSpacing(8)
        self.next_btn = button("Siguiente seña", "primary", "next")
        self.next_btn.clicked.connect(self._next_sign)
        db.addWidget(self.next_btn)
        more_btn = button("Grabar 5 más de esta", "secondary", "record")
        more_btn.clicked.connect(self._record_more)
        db.addWidget(more_btn)
        back_btn = button("Volver a la lista", "ghost", "back")
        back_btn.clicked.connect(self._finish_session)
        db.addWidget(back_btn)
        panel.body.addWidget(self.done_buttons)
        self.done_buttons.hide()

        for b in (self.pause_btn, self.undo_btn, stop_btn, self.next_btn, more_btn, back_btn):
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        lay.addWidget(side_scroll(panel, 290, 380))  # en pantallas chicas el panel se desplaza
        return self.session

    def start_session(self, sign_id):
        self.sign = config.SIGN_BY_ID[sign_id]
        if self.sign.category != self.category and sign_id != config.NOTHING_ID:
            self.category = self.sign.category
        self.session_saved = []
        self._session_signer = self.ctx.settings.signer_id
        self._auto_paused = False
        self._goal = self.ctx.settings.clips_per_sign
        self._count = self.ctx.signer_counts().get(sign_id, 0)
        if self._count >= self._goal:
            self._goal = self._count + 5  # ya estaba completa: grabar 5 extra
        self._update_panel()
        self.stack.fade_to(1)
        self.session.setFocus()
        self.set_titles(f"Grabando: {self.sign.name}",
                        "Colócate a un brazo de distancia, con tus manos y tu cara dentro del cuadro.")
        self.ctx.camera.acquire(self)
        self.timer.start()
        if self.ctx.camera.state == "running":
            self._begin_countdown(first=True)
        else:
            self.state = WAIT_CAMERA
            self.video.set_state("starting", self.ctx.camera.message or "Encendiendo la cámara…")

    def _update_panel(self):
        signs = config.signs_in(self.category)
        pos = next((i for i, s in enumerate(signs) if s.id == self.sign.id), 0) + 1
        cat = config.CATEGORY_NAMES[self.category].upper()
        self.s_over.setText(f"{cat} · SEÑA {pos} DE {len(signs)}")
        big = self.sign.category != config.WORDS
        self.s_name.setStyleSheet(f"font-size: {72 if big else 40}px; font-weight: 700;"
                                  "font-family: 'Segoe UI Variable Display', 'Segoe UI';")
        self.s_name.setText(self.sign.name)
        how = config.sign_instructions(self.sign.id)
        self.s_hint.setText(how + "\n\n" + self.sign.hint if how else self.sign.hint)
        self.s_tip.setText(self._tip())
        self.s_clips.setText(f"CLIP {min(self._count + 1, self._goal)} DE {self._goal}")
        self.dots.set(self._count, self._goal)

    def _tip(self):
        if self.sign.id == config.NOTHING_ID:
            return "Muévete con naturalidad: así el modelo aprende a ignorar lo que no es una seña."
        if self._count < 3:
            return "Empieza con las manos abajo, haz la seña completa y regresa a reposo."
        if self._count < self._goal // 2:
            return "Varía un poco: más cerca, más lejos, un poco de lado. Eso ayuda mucho al modelo."
        return "¡Ya casi! Si un clip salió mal, bórralo con «Borrar último» (o Retroceso)."

    def _set_status(self, text, color=theme.TEXT):
        if text != self._status_text:
            self._status_text = text
            self.s_status.setText(text)
            self.s_status.setStyleSheet(f"color: {color}; font-size: 17px; font-weight: 600;")

    def _countdown_when_ready(self, first=True):
        """Empieza la cuenta regresiva, o espera si la camara no esta lista."""
        if self.ctx.camera.state == "running":
            self._begin_countdown(first)
        else:
            self.state = WAIT_CAMERA
            self.pause_btn.setText("Pausar")
            self.pause_btn.setIcon(theme.glyph_icon("pause", theme.TEXT_2, 18))
            self.rec_buttons.show()
            self.done_buttons.hide()
            self.video.set_state("error" if self.ctx.camera.state == "error" else "starting",
                                 self.ctx.camera.message or "Encendiendo la cámara…")
            if self.ctx.camera.state in ("error", "stopped"):
                self.ctx.camera.restart()

    def _begin_countdown(self, first):
        self.state = COUNTDOWN
        self._first = first
        self._deadline = time.monotonic() + (config.FIRST_COUNTDOWN_SECONDS if first
                                             else config.BETWEEN_CLIPS_SECONDS)
        self._last_beep = None
        self.pause_btn.setText("Pausar")
        self.pause_btn.setIcon(theme.glyph_icon("pause", theme.TEXT_2, 18))
        self.rec_buttons.show()
        self.done_buttons.hide()

    def _begin_recording(self):
        self.state = RECORDING
        self._rec_start = time.monotonic()
        self.frames = []
        sounds.play("go")
        if self.ctx.demo:
            self.ctx.camera.perform_demo(self.sign.id)

    def _tick(self):
        now = time.monotonic()
        if self.state == COUNTDOWN:
            remaining = self._deadline - now
            if self._first:
                beep = int(np.ceil(remaining))
                if beep != self._last_beep and 0 < beep <= 3:
                    self._last_beep = beep
                    sounds.play("tick")
                self.video.set_overlay({"type": "countdown", "remaining": remaining,
                                        "total": config.FIRST_COUNTDOWN_SECONDS, "title": self.sign.name})
                self._set_status("Prepárate…", theme.TEXT_2)
            else:
                self.video.set_overlay({"type": "countdown", "small": True, "remaining": remaining,
                                        "total": config.BETWEEN_CLIPS_SECONDS,
                                        "caption": "Regresa las manos a reposo…"})
                self._set_status("Regresa las manos a reposo…", theme.TEXT_2)
            if remaining <= 0:
                self._begin_recording()
        elif self.state == RECORDING:
            progress = (now - self._rec_start) / config.CLIP_SECONDS
            self.video.set_overlay({"type": "recording", "progress": progress, "title": self.sign.name})
            self._set_status("¡Ahora! Haz la seña", theme.ACCENT_DEEP)
            if progress >= 1.0:
                self._finish_clip()
        elif self.state == PAUSED:
            self.video.set_overlay({"type": "paused", "caption": self._pause_caption})
            self._set_status("En pausa", theme.TEXT_2)
        elif self.state == SIGN_DONE:
            self.video.set_overlay({"type": "done", "caption": f"¡Terminaste «{self.sign.name}»!"})
        elif self.state == WAIT_CAMERA:
            self.video.set_overlay(None)

    def _on_frame(self, packet):
        if self.state == IDLE:
            return
        self.video.set_frame(packet)
        self._aspect = packet.aspect
        if self.state == RECORDING:
            self.frames.append((packet.t, packet.hands.image.copy(), packet.hands.world.copy()))

    def _on_camera_status(self, state, message):
        if self.state == IDLE:
            return
        if state in ("starting", "error"):
            self.video.set_state(state, message)
            if self.state in (COUNTDOWN, RECORDING):
                self.state = WAIT_CAMERA
            if state == "error":
                self._set_status("Revisa la cámara", theme.AMBER)
        elif state == "running" and self.state == WAIT_CAMERA:
            self._begin_countdown(first=True)

    def _finish_clip(self):
        frames = self.frames
        self.frames = []
        present = [bool(np.isfinite(img[:, 0, 0]).any()) for _, img, _ in frames]
        needs_hands = self.sign.id != config.NOTHING_ID
        if len(frames) < 8:
            self._reject("La cámara va muy lenta. Cierra otras apps e intenta de nuevo.")
            return
        if needs_hands and np.mean(present) < config.MIN_HAND_FRACTION:
            self._reject("No vi bien tus manos. Repitamos este clip.")
            return
        t = np.array([f[0] for f in frames], np.float64)
        image = np.stack([f[1] for f in frames])
        world = np.stack([f[2] for f in frames])
        try:
            ref = self.ctx.store.save_clip(self.sign.id, self.ctx.settings.signer_id, image, world,
                                           (t - t[0]).astype(np.float32), self._aspect,
                                           mirror=self.ctx.settings.mirror)
        except OSError:
            self._reject("No pude guardar el clip. ¿Está llena la computadora?")
            return
        self.session_saved.append(ref)
        self._count += 1
        self.video.flash(theme.GREEN)
        self._update_panel()
        if self._count >= self._goal:
            self.state = SIGN_DONE
            sounds.play("done")
            self._show_done()
        else:
            sounds.play("saved")
            self._set_status("¡Guardado!", theme.GREEN)
            self._begin_countdown(first=False)

    def _reject(self, message):
        sounds.play("error")
        self.video.flash(theme.RED)
        self.ctx.toast(message, "warning")
        self._begin_countdown(first=False)

    def _show_done(self):
        nxt = self._next_pending()
        self.next_btn.setText(f"Siguiente: {nxt.name}" if nxt else "Volver a la lista")
        self._set_status(f"¡Terminaste «{self.sign.name}»! 🎉", theme.GREEN)
        self.rec_buttons.hide()
        self.done_buttons.show()

    def _next_pending(self):
        goal = self.ctx.settings.clips_per_sign
        counts = self.ctx.signer_counts()
        signs = config.signs_in(self.category)
        idx = next((i for i, s in enumerate(signs) if s.id == self.sign.id), -1)
        ordered = signs[idx + 1:] + signs[:idx + 1]
        return next((s for s in ordered if counts.get(s.id, 0) < goal and s.id != self.sign.id), None)

    def _next_sign(self):
        nxt = self._next_pending()
        if nxt is None:
            self._finish_session()
            self.ctx.toast(f"¡Completaste {config.CATEGORY_NAMES[self.category]}!", "success")
            return
        self.sign = nxt
        self.session_saved = []
        self._goal = self.ctx.settings.clips_per_sign
        self._count = self.ctx.signer_counts().get(nxt.id, 0)
        self._update_panel()
        self.set_titles(f"Grabando: {nxt.name}")
        self._countdown_when_ready(first=True)

    def _record_more(self):
        self._goal = self._count + 5
        self._update_panel()
        self._countdown_when_ready(first=True)

    def _toggle_pause(self):
        if self.state in (COUNTDOWN, RECORDING, WAIT_CAMERA):
            self._pause()
        elif self.state == PAUSED:
            self._auto_paused = False
            self._countdown_when_ready(first=True)

    def _pause(self, auto=False):
        self.state = PAUSED
        self.frames = []
        self._auto_paused = auto
        self._pause_caption = ("En pausa mientras no estás en la app. Al regresar seguimos." if auto else
                               "En pausa. Presiona Continuar (o Espacio).")
        self.pause_btn.setText("Continuar")
        self.pause_btn.setIcon(theme.glyph_icon("play", theme.TEXT_2, 18))

    def _retry_camera(self):
        """Boton «Intentar de nuevo» del video despues de un error de camara."""
        if self.state == IDLE:
            return
        if self.state != PAUSED:
            self.state = WAIT_CAMERA
        self.video.set_state("starting", "Encendiendo la cámara…")
        self._set_status("Encendiendo la cámara…", theme.TEXT_2)
        self.ctx.camera.restart()

    def on_pause(self):
        if self.state in (COUNTDOWN, RECORDING, WAIT_CAMERA):
            self._pause(auto=True)  # el clip a medias se descarta

    def on_resume(self):
        if self.state == PAUSED and self._auto_paused:
            self._auto_paused = False
            self._countdown_when_ready(first=True)  # cuenta completa para volver a acomodarse

    def _on_settings_changed(self):
        if self.state != IDLE and self.ctx.settings.signer_id != self._session_signer:
            # Otra persona: lo que siga no debe quedar a nombre de la anterior
            self._finish_session()
            self.ctx.toast("Cambiaste de persona: terminé la sesión de grabación anterior.")

    def _undo(self):
        if self.state == IDLE or not self.session_saved:
            self.ctx.toast("No hay clips de esta sesión para borrar.")
            return
        ref = self.session_saved.pop()
        self.ctx.store.delete(ref)
        self._count = max(0, self._count - 1)
        self._update_panel()
        self.ctx.toast("Borré el último clip.", "info")
        if self.state == SIGN_DONE:
            self._pause()
            self.rec_buttons.show()
            self.done_buttons.hide()
        elif self.state in (COUNTDOWN, RECORDING):
            self.frames = []
            self._begin_countdown(first=True)

    def _finish_session(self):
        if self.state == IDLE:
            return
        self.state = IDLE
        self._auto_paused = False
        self.timer.stop()
        self.frames = []
        self.video.set_overlay(None)
        self.ctx.camera.release(self)
        self.video.set_state("starting")
        self.stack.fade_to(0)
        self.set_titles(self.title, self.subtitle)
        self.ctx.data_changed.emit()

    # ============================================================

    def on_enter(self, sign_id=None, **kwargs):
        self._refresh_tiles()
        if sign_id:
            self.start_session(sign_id)

    def on_leave(self):
        self._finish_session()
