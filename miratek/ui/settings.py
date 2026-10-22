"""Ajustes de la persona (nombre, camara, meta de clips...) guardados en JSON."""

import json
import os
import uuid
from dataclasses import asdict, dataclass

from .. import config

HANDS = ("derecha", "izquierda", "")  # "" = no se sabe


@dataclass
class Settings:
    signer_id: str = ""
    signer_name: str = ""
    camera_index: int = 0
    clips_per_sign: int = config.CLIPS_PER_SIGN
    sounds: bool = True
    sensitivity: str = "media"
    mano: str = ""  # con que mano hace las senas: "derecha", "izquierda" o "" (no se sabe)

    @property
    def path(self):
        return config.user_data_dir() / "ajustes.json"

    @property
    def mirror(self):
        """True si hace las senas con la izquierda, False con la derecha, None si no se sabe."""
        return {"izquierda": True, "derecha": False}.get(self.mano)

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
        if s.mano not in HANDS:
            s.mano = ""
        return s

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def new_signer(self, name, mano=""):
        """Registra a una persona nueva (con un id unico)."""
        self.signer_name = name.strip()
        self.signer_id = f"{config.slugify(self.signer_name)}-{uuid.uuid4().hex[:4]}"
        self.mano = mano if mano in HANDS else ""
        self.save()

    def use_signer(self, signer_id, name, mano=""):
        """Vuelve a grabar como alguien que ya tiene grabaciones en esta computadora."""
        self.signer_id = signer_id
        self.signer_name = name.strip()
        self.mano = mano if mano in HANDS else ""
        self.save()
