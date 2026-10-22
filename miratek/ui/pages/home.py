"""Pantalla de inicio: saludo, progreso y el siguiente paso recomendado."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from ... import config
from .. import theme
from ..widgets import Card, IconBadge, ProgressRing, button, label
from .base import Page


class HeroCard(QFrame):
    """Tarjeta principal con un brillo de color de fondo."""

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(r, 24, 24)
        p.fillPath(path, QColor(theme.SURFACE))
        glow = QLinearGradient(r.topLeft(), r.bottomRight())
        c1 = QColor(theme.ACCENT_2)
        c1.setAlpha(40)
        c2 = QColor(theme.WARM)
        c2.setAlpha(34)
        glow.setColorAt(0, c1)
        glow.setColorAt(0.55, c2)
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillPath(path, glow)
        p.setPen(QPen(QColor(theme.BORDER), 1))
        p.drawPath(path)


class StepCard(QFrame):
    clicked = Signal()

    def __init__(self, number, icon, title, text):
        super().__init__()
        self.setProperty("card", "true")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(190)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 22, 22, 22)
        lay.setSpacing(10)
        top = QHBoxLayout()
        self._icon = icon
        self.badge = IconBadge(icon, theme.ACCENT, 44)
        top.addWidget(self.badge)
        top.addStretch()
        self.step = label(f"PASO {number}", "overline")
        top.addWidget(self.step, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(top)
        lay.addSpacing(4)
        lay.addWidget(label(title, "h2"))
        self.text = label(text, "body", wrap=True)
        lay.addWidget(self.text)
        lay.addStretch()
        self.status = label("", "muted", wrap=True)
        lay.addWidget(self.status)

    def set_status(self, text, done=False, current=False):
        self.status.setText(text)
        color = theme.GREEN if done else (theme.ACCENT if current else theme.TEXT_3)
        self.badge.set_icon("check" if done else self._icon, color)
        self.status.setStyleSheet(f"color: {theme.GREEN if done else theme.TEXT_2}; font-size: 13px;")
        border = theme.ACCENT if current else theme.BORDER
        self.setStyleSheet(f"StepCard, QFrame[card='true'] {{ border: 1px solid {border}; }}")

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


class HomePage(Page):
    title = "Hola"
    subtitle = "Enseñémosle a la computadora a entender la Lengua de Señas Mexicana."

    def __init__(self, ctx):
        super().__init__(ctx)

        # ---- Tarjeta principal ----
        hero = HeroCard()
        hl = QHBoxLayout(hero)
        hl.setContentsMargins(34, 30, 34, 30)
        hl.setSpacing(30)
        self.ring = ProgressRing(150, 13)
        hl.addWidget(self.ring)
        texts = QVBoxLayout()
        texts.setSpacing(8)
        texts.addWidget(label("TU PROGRESO", "overline"))
        self.hero_title = label("", "h2", wrap=True)
        self.hero_title.setStyleSheet("font-size: 24px;")
        texts.addWidget(self.hero_title)
        self.hero_text = label("", "body", wrap=True)
        texts.addWidget(self.hero_text)
        texts.addSpacing(8)
        cta_row = QHBoxLayout()
        cta_row.setSpacing(10)
        self.cta = button("Empezar a grabar", "primary", "next")
        self.cta.clicked.connect(self._on_cta)
        cta_row.addWidget(self.cta)
        self.cta_record = button("Seguir grabando", "secondary", "record")
        self.cta_record.clicked.connect(lambda: self.ctx.navigate("record"))
        self.cta_record.hide()
        cta_row.addWidget(self.cta_record)
        cta_row.addStretch()
        texts.addLayout(cta_row)
        hl.addLayout(texts, 1)
        self.body.addWidget(hero)

        # ---- Los 4 pasos ----
        grid = QGridLayout()
        grid.setSpacing(16)
        goal = ctx.settings.clips_per_sign
        self.steps = {
            "record": StepCard(1, "record", "Graba", f"Haz cada seña {goal} veces frente a la cámara."),
            "train": StepCard(2, "train", "Entrena", "Un botón y la computadora aprende tus señas."),
            "live": StepCard(3, "live", "Prueba", "Haz señas y mira cómo las reconoce en vivo."),
            "share": StepCard(4, "share", "Envía", "Manda tu archivo a quien coordina el proyecto."),
        }
        for key, card in self.steps.items():
            card.clicked.connect(lambda k=key: self.ctx.navigate(k))
        self.steps_grid = grid
        self._step_cols = 0
        self._place_steps()
        self.body.addLayout(grid)

        # ---- Consejos ----
        tips = Card(padding=26)
        tips.body.addWidget(label("Consejos para grabar bien", "h2"))
        row = QHBoxLayout()
        row.setSpacing(24)
        for icon, title, text in (
            ("light", "Buena luz", "Que la luz te dé de frente, no detrás."),
            ("person", "A un brazo de distancia", "Tus manos y tu cara deben verse completas."),
            ("hand", "Señas completas", "Empieza con las manos abajo y regresa a reposo."),
        ):
            col = QHBoxLayout()
            col.setSpacing(12)
            col.addWidget(IconBadge(icon, theme.ACCENT, 40), 0, Qt.AlignmentFlag.AlignTop)
            txt = QVBoxLayout()
            txt.setSpacing(2)
            t = label(title, wrap=True)
            t.setStyleSheet("font-weight: 600;")
            txt.addWidget(t)
            txt.addWidget(label(text, "body", wrap=True))
            col.addLayout(txt, 1)
            row.addLayout(col, 1)
        tips.body.addLayout(row)
        privacy = label(f'<span style="font-family:\'{theme.icon_family()}\'">{theme.ICONS["lock"]}</span>'
                        "&nbsp;&nbsp;Solo guardamos la posición de tus manos, nunca video ni fotos.", "muted")
        privacy.setTextFormat(Qt.TextFormat.RichText)
        tips.body.addSpacing(4)
        tips.body.addWidget(privacy)
        self.body.addWidget(tips)
        self.body.addStretch()

        ctx.data_changed.connect(self.refresh)
        ctx.model_changed.connect(self.refresh)
        ctx.settings_changed.connect(self.refresh)
        self._next = "record"

    def on_enter(self, **kwargs):
        self.refresh()

    def _place_steps(self):
        """Los 4 pasos en una fila; en ventanas angostas, en dos filas de dos."""
        cols = 4 if self.width() - 90 >= 4 * 190 + 3 * 16 else 2
        if cols == self._step_cols:
            return
        self._step_cols = cols
        for i, card in enumerate(self.steps.values()):
            self.steps_grid.removeWidget(card)
            self.steps_grid.addWidget(card, i // cols, i % cols)
        for c in range(4):
            self.steps_grid.setColumnStretch(c, 1 if c < cols else 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_steps()

    def refresh(self):
        s = self.ctx.settings
        first = s.signer_name.split()[0] if s.signer_name else ""
        self.set_titles(f"Hola, {first}" if first else "Hola")
        goal = s.clips_per_sign
        self.steps["record"].text.setText(f"Haz cada seña {goal} veces frente a la cámara.")
        counts = self.ctx.signer_counts()
        signs = list(config.SIGNS)
        total = goal * len(signs)
        done_clips = sum(min(counts.get(sg.id, 0), goal) for sg in signs)
        frac = done_clips / total if total else 0
        self.ring.set_value(frac)
        self.ring.set_text(f"{round(frac * 100)}%", "grabado")

        per_cat = {}
        for cat in config.CATEGORIES:
            cat_signs = [sg for sg in config.signs_in(cat) if sg.id != config.NOTHING_ID]
            complete = sum(1 for sg in cat_signs if counts.get(sg.id, 0) >= goal)
            per_cat[cat] = (complete, len(cat_signs))
        complete_signs = sum(1 for sg in signs if counts.get(sg.id, 0) >= goal)

        model = self.ctx.model()
        new_clips = self.ctx.clips_since_model()
        needs_training = model is None or new_clips > 0
        any_ready = any(done >= n * 0.5 for done, n in per_cat.values())
        # Para entrenar cuentan las grabaciones de TODAS las personas: quien coordina
        # quiza no grabo nada, pero recibio las de su equipo.
        all_counts = self.ctx.store.counts()
        trainable = sum(1 for n in all_counts.values() if n >= config.MIN_CLIPS_PER_CLASS)
        team_ready = any(
            sum(1 for sg in config.signs_in(cat) if sg.id != config.NOTHING_ID and all_counts.get(sg.id, 0) >= goal)
            >= n * 0.5 for cat, (_, n) in per_cat.items() if n)

        if needs_training and trainable >= 2 and (any_ready or team_ready):
            self._next = "train"
            self.hero_title.setText("Ya puedes entrenar el modelo" if model is None else
                                    "Hay grabaciones nuevas para entrenar")
            self.cta.setText("Entrenar ahora")
        elif not any_ready:
            self._next = "record"
            self.hero_title.setText("Empecemos a grabar" if done_clips == 0 else "¡Vas muy bien! Sigue grabando")
            self.cta.setText("Empezar a grabar" if done_clips == 0 else "Seguir grabando")
        else:
            self._next = "live"
            self.hero_title.setText("Tu modelo está listo")
            self.cta.setText("Probar en vivo")
        self.cta_record.setVisible(self._next == "train" and done_clips < total)
        self.cta_record.setText("Empezar a grabar" if done_clips == 0 else "Seguir grabando")

        parts = " · ".join(f"{config.CATEGORY_NAMES[c]}: {d} de {n}" for c, (d, n) in per_cat.items())
        mine = f"Llevas {done_clips} de {total} clips. Señas completas → {parts}."
        if self._next == "train":
            team = (f"Hay {new_clips} {'grabación nueva' if new_clips == 1 else 'grabaciones nuevas'} desde el "
                    "último entrenamiento." if model is not None else
                    f"Entre todas las personas ya hay {sum(all_counts.values())} grabaciones para entrenar.")
            self.hero_text.setText(f"{team} {mine}")
        elif self._next == "record":
            self.hero_text.setText(f"{mine} Puedes grabar por partes: tu avance se guarda solo.")
        else:
            self.hero_text.setText(mine)

        self.steps["record"].set_status(f"{complete_signs} de {len(signs)} señas completas",
                                        done=done_clips >= total, current=self._next == "record")
        if model and model.report:
            acc = round(model.report.accuracy * 100)
            extra = (f" · {new_clips} {'grabación nueva' if new_clips == 1 else 'grabaciones nuevas'}"
                     if new_clips else "")
            self.steps["train"].set_status(f"Último examen: {acc}% de aciertos{extra}", done=not needs_training,
                                           current=self._next == "train")
        else:
            self.steps["train"].set_status("Todavía no has entrenado", current=self._next == "train")
        self.steps["live"].set_status("Listo para probar" if model else "Primero entrena el modelo",
                                      done=False, current=self._next == "live")
        self.steps["share"].set_status("Crea un archivo y mándalo por WhatsApp o correo")

    def _on_cta(self):
        self.ctx.navigate(self._next)
