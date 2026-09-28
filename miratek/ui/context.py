"""Estado compartido por todas las pantallas (datos, ajustes, camara, modelo)."""

import logging

from PySide6.QtCore import QObject, Signal

from .. import config
from ..training import ModelError, TrainedModel

log = logging.getLogger(__name__)


class AppContext(QObject):
    data_changed = Signal()    # se grabaron, borraron o importaron clips
    model_changed = Signal()   # hay un modelo nuevo

    def __init__(self, settings, store, camera, demo=False):
        super().__init__()
        self.settings = settings
        self.store = store
        self.camera = camera
        self.demo = demo
        self.models_dir = config.user_data_dir() / "modelos"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.model_path = self.models_dir / "modelo_actual.npz"
        self.log_path = config.user_data_dir() / "logs" / "miratek.log"
        self._model = None
        self._model_stamp = None
        self.toast = lambda text, kind="info": None      # lo conecta la ventana principal
        self.navigate = lambda key, **kwargs: None

    def model(self):
        """El modelo actual (o None si todavia no hay)."""
        try:
            stamp = self.model_path.stat().st_mtime_ns
        except FileNotFoundError:
            self._model = self._model_stamp = None
            return None
        if stamp != self._model_stamp:
            try:
                self._model = TrainedModel.load(self.model_path)
            except ModelError as exc:
                log.warning("Modelo no valido: %s", exc)
                self._model = None
            self._model_stamp = stamp
        return self._model

    def use_model_file(self, path):
        """Convierte un modelo recibido en el modelo actual."""
        TrainedModel.load(path)  # valida antes de reemplazar
        if self.model_path.exists():
            self.model_path.replace(self.model_path.with_name("modelo_anterior.npz"))
        path.replace(self.model_path)
        self.model_changed.emit()

    def signer_counts(self):
        return self.store.counts(self.settings.signer_id)
