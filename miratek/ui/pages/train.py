"""Entrenar con un boton y ver los resultados explicados en palabras simples."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ... import config
from .. import sounds, theme
from ..widgets import (BarRow, Card, CountUpLabel, FadeStack, IconBadge, ProgressRing, button, label,
                       quality_color)
from ..workers import TrainWorker
from .base import Page


def _names(ids, limit=6):
    names = [config.sign_name(i) for i in ids]
    if len(names) > limit:
        return ", ".join(names[:limit]) + f" y {len(names) - limit} más"
    return ", ".join(names)


class TrainPage(Page):
    title = "Entrenar"
    subtitle = "Con un solo botón, la computadora aprende de todas las grabaciones."

    def __init__(self, ctx):
        super().__init__(ctx)
        self.worker = None
        self.stack = FadeStack()
        self.stack.addWidget(self._build_idle())
        self.stack.addWidget(self._build_training())
        self.stack.addWidget(self._build_results())
        self.body.addWidget(self.stack)
        self.body.addStretch()
        ctx.data_changed.connect(self._refresh_idle)

    # ---------------- Antes de entrenar ----------------
    def _build_idle(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(18)

        card = Card(padding=30, spacing=16)
        head = QHBoxLayout()
        head.addWidget(IconBadge("train", theme.ACCENT, 52))
        titles = QVBoxLayout()
        titles.setSpacing(4)
        self.idle_title = label("", "h2")
        self.idle_text = label("", "body", wrap=True)
        titles.addWidget(self.idle_title)
        titles.addWidget(self.idle_text)
        head.addLayout(titles, 1)
        card.body.addLayout(head)

        self.cat_rows = {}
        for cat in config.CATEGORIES:
            row = BarRow(config.CATEGORY_NAMES[cat], label_width=120)
            row.value.setFixedWidth(150)
            self.cat_rows[cat] = row
            card.body.addWidget(row)
        self.idle_warning = label("", wrap=True)
        self.idle_warning.setStyleSheet(f"color: {theme.AMBER};")
        card.body.addWidget(self.idle_warning)

        actions = QHBoxLayout()
        self.train_btn = button("Entrenar modelo", "primary", "sparkle")
        self.train_btn.setMinimumHeight(52)
        self.train_btn.clicked.connect(self.start_training)
        actions.addWidget(self.train_btn)
        self.last_btn = button("Ver último resultado", "secondary")
        self.last_btn.clicked.connect(lambda: self.stack.fade_to(2))
        actions.addWidget(self.last_btn)
        actions.addStretch()
        self.eta = label("", "muted")
        actions.addWidget(self.eta)
        card.body.addLayout(actions)
        lay.addWidget(card)

        how = Card(soft=True, padding=22)
        how.body.addWidget(label("¿Cómo sabemos si funciona?", "h2"))
        how.body.addWidget(label(
            "Antes de dar un resultado, la app se hace un examen honesto: si hay grabaciones de varias "
            "personas, aprende sin una de ellas y luego intenta reconocerla, como si fuera alguien nuevo. "
            "Así el porcentaje dice qué tan bien funcionará con otras personas.", "body", wrap=True))
        lay.addWidget(how)
        return w

    def _refresh_idle(self):
        counts_by_signer = self.ctx.store.counts_by_signer()
        totals = {}
        for per in counts_by_signer.values():
            for sid, n in per.items():
                totals[sid] = totals.get(sid, 0) + n
        n_clips = sum(totals.values())
        n_people = len(counts_by_signer)
        self.idle_title.setText("Listo para entrenar" if n_clips else "Primero graba algunas señas")
        people = "1 persona" if n_people == 1 else f"{n_people} personas"
        self.idle_text.setText(f"Tienes {n_clips} clips de {people}." if n_clips else
                               "Ve a «Grabar» y graba al menos 2 señas para poder entrenar.")
        for cat, row in self.cat_rows.items():
            signs = config.signs_in(cat)
            ready = sum(1 for s in signs if totals.get(s.id, 0) >= config.MIN_CLIPS_PER_CLASS)
            row.set(ready / len(signs), f"{ready} de {len(signs)} listas",
                    theme.GREEN if ready == len(signs) else theme.ACCENT)
        missing = [s.id for s in config.SIGNS if 0 < totals.get(s.id, 0) < config.MIN_CLIPS_PER_CLASS]
        self.idle_warning.setVisible(bool(missing))
        if missing:
            self.idle_warning.setText(f"Estas señas tienen menos de {config.MIN_CLIPS_PER_CLASS} clips y no "
                                      f"entrarán al modelo: {_names(missing)}.")
        trainable = sum(1 for n in totals.values() if n >= config.MIN_CLIPS_PER_CLASS)
        self.train_btn.setEnabled(trainable >= 2)
        eligible = sum(1 for per in counts_by_signer.values() if len(per) >= 3)
        rounds = (min(eligible, 6) if eligible >= 2 else 1) * 0.55 + 1
        seconds = max(10, int(n_clips * 0.028 * rounds))
        self.eta.setText(f"Tarda aprox. {seconds // 60} min {seconds % 60:02d} s" if seconds >= 60
                         else f"Tarda aprox. {seconds} segundos")
        self.last_btn.setVisible(self.ctx.model() is not None and self.ctx.model().report is not None)

    # ---------------- Entrenando ----------------
    def _build_training(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 30, 0, 0)
        lay.setSpacing(18)
        lay.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.t_ring = ProgressRing(200, 14)
        lay.addWidget(self.t_ring, 0, Qt.AlignmentFlag.AlignHCenter)
        self.t_phase = label("", "h2", align=Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.t_phase)
        lay.addWidget(label("Puedes dejar la app abierta y esperar. No cierres la ventana.", "body",
                            align=Qt.AlignmentFlag.AlignCenter))
        cancel = button("Cancelar", "ghost", "stop")
        cancel.clicked.connect(self._cancel)
        lay.addWidget(cancel, 0, Qt.AlignmentFlag.AlignHCenter)
        return w

    def start_training(self):
        if self.worker is not None:
            return
        self.t_ring.set_value(0, animate=False)
        self.t_ring.set_text("0%")
        self.t_phase.setText("Preparando…")
        self.stack.fade_to(1)
        self.worker = TrainWorker(self.ctx.store, self.ctx.model_path)
        self.worker.progress.connect(self._on_progress)
        self.worker.done.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, frac, message):
        self.t_ring.set_value(frac)
        self.t_ring.set_text(f"{int(frac * 100)}%")
        self.t_phase.setText(message)

    def _on_done(self, model):
        sounds.play("done")
        self.ctx.model_changed.emit()
        self._show_results(model, animate=True)
        self.ctx.toast("¡Modelo entrenado!", "success")

    def _on_failed(self, message):
        self.stack.fade_to(0)
        self.ctx.toast(message, "warning")

    def _on_finished(self):
        self.worker = None
        self._refresh_idle()

    def _cancel(self):
        if self.worker is not None:
            self.worker.cancel()
            self.t_phase.setText("Cancelando…")

    # ---------------- Resultados ----------------
    def _build_results(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(18)

        hero = Card(padding=32, spacing=6)
        row = QHBoxLayout()
        row.setSpacing(30)
        left = QVBoxLayout()
        left.setSpacing(4)
        left.addWidget(label("RESULTADO DEL EXAMEN", "overline"))
        self.r_acc = CountUpLabel()
        self.r_acc.setStyleSheet("font-size: 78px; font-weight: 800; font-family: 'Segoe UI Variable Display';")
        left.addWidget(self.r_acc)
        self.r_quality = label("", "h2")
        left.addWidget(self.r_quality)
        row.addLayout(left)
        right = QVBoxLayout()
        right.setSpacing(10)
        self.r_explain = label("", "body", wrap=True)
        right.addWidget(self.r_explain)
        self.r_meta = label("", "muted", wrap=True)
        right.addWidget(self.r_meta)
        buttons = QHBoxLayout()
        live_btn = button("Probar en vivo", "primary", "live")
        live_btn.clicked.connect(lambda: self.ctx.navigate("live"))
        buttons.addWidget(live_btn)
        again_btn = button("Entrenar de nuevo", "secondary", "refresh")
        again_btn.clicked.connect(lambda: (self._refresh_idle(), self.stack.fade_to(0)))
        buttons.addWidget(again_btn)
        share_btn = button("Enviar resultados", "ghost", "share")
        share_btn.clicked.connect(lambda: self.ctx.navigate("share"))
        buttons.addWidget(share_btn)
        buttons.addStretch()
        right.addLayout(buttons)
        row.addLayout(right, 1)
        hero.body.addLayout(row)
        lay.addWidget(hero)

        self.improve = Card(padding=26)
        self.improve.body.addWidget(label("Qué mejorar", "h2"))
        self.improve_text = label("", "body", wrap=True)
        self.improve_text.setTextFormat(Qt.TextFormat.RichText)
        self.improve.body.addWidget(self.improve_text)
        lay.addWidget(self.improve)

        self.cat_cards = QHBoxLayout()
        self.cat_cards.setSpacing(18)
        lay.addLayout(self.cat_cards)
        return w

    def _show_results(self, model, animate=False):
        r = model.report
        if r is None:
            return
        acc = r.accuracy * 100
        if animate:
            self.r_acc.count_to(acc)
        else:
            self.r_acc.setText(f"{round(acc)}%")
        self.r_acc.setStyleSheet(f"font-size: 78px; font-weight: 800; color: {quality_color(r.accuracy)};"
                                 "font-family: 'Segoe UI Variable Display', 'Segoe UI';")
        self.r_quality.setText("¡Excelente!" if r.accuracy >= 0.85 else
                               "Bien, pero puede mejorar" if r.accuracy >= 0.65 else
                               "Necesita más grabaciones")
        if r.eval_mode == "personas":
            self.r_explain.setText(f"Aciertos con personas que el modelo no conocía: se examinó a "
                                   f"{len(r.per_signer)} personas, una por una, sin haberlas visto antes.")
        else:
            self.r_explain.setText("Aciertos con grabaciones que el modelo no usó para aprender. Como "
                                   "todas son de la misma persona, con gente nueva el número puede bajar.")
        self.r_meta.setText(f"{r.n_clips} clips · {r.n_signers} "
                            f"{'persona' if r.n_signers == 1 else 'personas'} · {len(r.classes)} señas · "
                            f"entrenó en {int(r.seconds)} s")

        tips = []
        weak = [c for c in r.classes if (r.per_class[c]["recall"] or 0) < 0.7 and r.per_class[c]["support"]]
        weak.sort(key=lambda c: r.per_class[c]["recall"] or 0)
        if weak:
            tips.append(f"Graba más clips (y de más personas) de: <b>{_names(weak)}</b>.")
        for true_id, pred_id, count in r.top_confusions:
            tips.append(f"Confunde «{config.sign_name(true_id)}» con «{config.sign_name(pred_id)}» "
                        f"({count} {'vez' if count == 1 else 'veces'}). Revisa que se hagan distinto.")
        tips.extend(r.warnings)
        if r.eval_mode == "grabaciones":
            tips.append("Para medir cómo funciona con gente nueva, junta grabaciones de al menos 2 personas "
                        "(pestaña «Compartir»).")
        if not tips:
            tips.append("¡Todo se ve muy bien! Graba con más personas para que funcione con cualquiera.")
        self.improve_text.setText("<br>".join(f"•&nbsp;&nbsp;{t}" for t in tips))

        while self.cat_cards.count():
            item = self.cat_cards.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for cat in config.CATEGORIES:
            ids = [c for c in r.classes if config.category_of(c) == cat and c != config.NOTHING_ID
                   and r.per_class[c]["support"]]
            if not ids:
                continue
            card = Card(padding=24, spacing=10)
            card.body.addWidget(label(f"{config.CATEGORY_NAMES[cat]} · aciertos por seña", "h2"))
            ids.sort(key=lambda c: r.per_class[c]["recall"] or 0)
            for c in ids:
                recall = r.per_class[c]["recall"] or 0.0
                row = BarRow(config.sign_name(c), label_width=100)
                row.set(recall, color=quality_color(recall))
                card.body.addWidget(row)
            card.body.addStretch()
            self.cat_cards.addWidget(card, 1)
        self.stack.fade_to(2)

    def on_enter(self, **kwargs):
        if self.worker is not None:
            return
        self._refresh_idle()
        model = self.ctx.model()
        if model is not None and model.report is not None and self.stack.currentIndex() != 2:
            self._show_results(model)
        elif model is None:
            self.stack.fade_to(0)
