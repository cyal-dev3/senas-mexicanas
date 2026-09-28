"""Ajustes de la persona (nombre, camara, meta de clips...) guardados en JSON."""

import json
import os
import uuid
from dataclasses import asdict, dataclass

from .. import config


@dataclass
class Settings:
    signer_id: str = ""
    signer_name: str = ""
    camera_index: int = 0
    clips_per_sign: int = config.CLIPS_PER_SIGN
    sounds: bool = True
    sensitivity: str = "media"

    @property
    def path(self):
        return config.user_data_dir() / "ajustes.json"

    @classmethod
    def load(cls):
        s = cls()
        try:
            data = json.loads(s.path.read_text(encoding="utf-8"))
            for key in asdict(s):
                if key in data:
                    setattr(s, key, type(getattr(s, key))(data[key]))
        except (FileNotFoundError, ValueError, TypeError):
            pass
        s.clips_per_sign = max(5, min(60, s.clips_per_sign))
        return s

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def new_signer(self, name):
        """Registra a una persona nueva (con un id unico)."""
        self.signer_name = name.strip()
        self.signer_id = f"{config.slugify(self.signer_name)}-{uuid.uuid4().hex[:4]}"
        self.save()
