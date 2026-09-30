"""
Configuracion central: que senas reconocemos, cuanto dura cada grabacion
y donde se guardan los archivos.

Si quieren agregar una sena nueva, solo agreguenla a la lista SIGNS.
"""

import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "Mira&Tek"
APP_ID = "MiraTek"  # Sin '&' para nombres de archivos y carpetas


# ============================================================
# SENAS
# ============================================================
# 'id' se usa en archivos (sin acentos ni espacios).
# 'name' es lo que se ve en pantalla (con acentos).

WORDS = "palabras"
LETTERS = "abecedario"
NUMBERS = "numeros"
CATEGORIES = (WORDS, LETTERS, NUMBERS)
CATEGORY_NAMES = {WORDS: "Palabras", LETTERS: "Abecedario", NUMBERS: "Números"}

WORD_HINT = "Haz la seña una sola vez, completa, y regresa las manos a reposo."
LETTER_HINT = ("Forma la letra y mantenla quieta hasta que se llene la barra. "
               "Si la letra lleva movimiento, hazlo una vez.")
NUMBER_HINT = ("Haz el número y mantenlo quieto hasta que se llene la barra. "
               "Si lleva movimiento, hazlo una vez.")


@dataclass(frozen=True)
class Sign:
    id: str
    name: str
    category: str = WORDS
    hint: str = WORD_HINT


NOTHING_ID = "nada"  # Clase especial: "no estoy haciendo ninguna sena"

_WORDS = (
    Sign("hola", "Hola"),
    Sign("gracias", "Gracias"),
    Sign("por_favor", "Por favor"),
    Sign("si", "Sí"),
    Sign("no", "No"),
    Sign("ayuda", "Ayuda"),
    Sign("agua", "Agua"),
    Sign("comida", "Comida"),
    Sign("bano", "Baño"),
    Sign("doctor", "Doctor"),
    Sign("familia", "Familia"),
    Sign("amigo", "Amigo"),
    Sign("disculpa", "Disculpa"),
    Sign("te_quiero", "Te quiero"),
)

# Abecedario manual de LSM. Para agregar CH, LL o RR basta con sumarlas aqui
# (ej: Sign("letra_ll", "LL", LETTERS, LETTER_HINT)).
_LETTERS = tuple(
    Sign("letra_enie" if ch == "Ñ" else f"letra_{ch.lower()}", ch, LETTERS, LETTER_HINT)
    for ch in "ABCDEFGHIJKLMNÑOPQRSTUVWXYZ"
)

# Numeros: en LSM del 0 al 19, las decenas y el 100 tienen su propia sena. El resto
# se arma como en el diccionario de LSM: decena + unidad (20 y 3 = 23) y
# 100 + lo que sigue (100 y 25 = 125). Senas sin grabar no entran al modelo.
NUMBER_VALUES = tuple(range(0, 20)) + tuple(range(20, 100, 10)) + (100,)
_NUMBERS = tuple(Sign(f"num_{v}", str(v), NUMBERS, NUMBER_HINT) for v in NUMBER_VALUES)

NOTHING = Sign(NOTHING_ID, "Nada", WORDS,
               "No hagas ninguna seña: baja las manos, ráscate, acomódate el pelo. "
               "Así el modelo aprende cuándo NO estás haciendo una seña.")

SIGNS = _WORDS + _LETTERS + _NUMBERS + (NOTHING,)
SIGN_BY_ID = {s.id: s for s in SIGNS}


def signs_in(category):
    """Senas de una categoria. 'Nada' aparece en todas porque sirve para todas."""
    return [s for s in SIGNS if s.category == category and s.id != NOTHING_ID] + [NOTHING]


def category_of(sign_id):
    sign = SIGN_BY_ID.get(sign_id)
    return sign.category if sign else WORDS


def is_letter(sign_id):
    return category_of(sign_id) == LETTERS


def number_value(sign_id):
    """El valor de una sena de numero (ej: 'num_20' -> 20), o None."""
    if category_of(sign_id) != NUMBERS:
        return None
    return int(SIGN_BY_ID[sign_id].name)


_INSTRUCTIONS = None


def sign_instructions(sign_id):
    """Como se hace una sena (assets/senas_info.json, compartido con el celular)."""
    global _INSTRUCTIONS
    if _INSTRUCTIONS is None:
        try:
            data = json.loads(resource_path("assets", "senas_info.json").read_text(encoding="utf-8"))
            _INSTRUCTIONS = {k: v.get("text", "") for k, v in data.get("signs", {}).items()}
        except (OSError, ValueError):
            _INSTRUCTIONS = {}
    return _INSTRUCTIONS.get(sign_id, "")


def sign_name(sign_id):
    """Nombre bonito de una sena (o el id si no la conocemos)."""
    sign = SIGN_BY_ID.get(sign_id)
    return sign.name if sign else sign_id.replace("_", " ").capitalize()


# ============================================================
# GRABACION
# ============================================================
CLIP_SECONDS = 2.0             # Duracion de cada clip (una repeticion de la sena)
FIRST_COUNTDOWN_SECONDS = 3.0  # Cuenta regresiva antes del primer clip
BETWEEN_CLIPS_SECONDS = 1.4    # Pausa entre clips para regresar a reposo
CLIPS_PER_SIGN = 15            # Meta de clips por sena y por persona
MIN_HAND_FRACTION = 0.5        # Un clip necesita manos en al menos la mitad de los frames
MIN_CLIPS_PER_CLASS = 3        # Menos que esto y la sena no entra al modelo

CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480


# ============================================================
# RUTAS
# ============================================================

def resource_path(*parts):
    """Ruta a un archivo que viaja DENTRO de la app (ej: el modelo de MediaPipe).

    Cuando la app corre como .exe, PyInstaller descomprime todo en una carpeta
    temporal (sys._MEIPASS). Cuando corre desde el codigo, es la raiz del repo.
    """
    base = getattr(sys, "_MEIPASS", None)
    root = Path(base) if base else Path(__file__).resolve().parent.parent
    return root.joinpath(*parts)


def user_data_dir():
    """Carpeta donde guardamos grabaciones, modelos y ajustes de la persona.

    En Windows: %LOCALAPPDATA%\\MiraTek. Se puede cambiar con la variable
    de entorno MIRATEK_DATA (util para pruebas).
    """
    override = os.environ.get("MIRATEK_DATA")
    if override:
        path = Path(override)
    elif sys.platform == "win32" and os.environ.get("LOCALAPPDATA"):
        path = Path(os.environ["LOCALAPPDATA"]) / APP_ID
    else:
        path = Path.home() / f".{APP_ID.lower()}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _windows_known_folder(guid_str):
    """Pregunta a Windows por una carpeta especial (respeta OneDrive)."""
    import ctypes
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD), ("Data4", wintypes.BYTE * 8)]

    import uuid
    u = uuid.UUID(guid_str)
    guid = GUID(u.fields[0], u.fields[1], u.fields[2],
                (wintypes.BYTE * 8).from_buffer_copy(u.bytes[8:]))
    out = ctypes.c_wchar_p()
    shell32 = ctypes.windll.shell32
    if shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(out)) != 0:
        return None
    try:
        return Path(out.value)
    finally:
        ctypes.windll.ole32.CoTaskMemFree(out)


def desktop_dir():
    """El Escritorio de la persona (ahi dejamos los archivos para enviar)."""
    if sys.platform == "win32":
        try:
            path = _windows_known_folder("B4BFCC3A-DB2C-424C-B029-7FE99A87C641")
            if path and path.exists():
                return path
        except Exception:
            pass
    for candidate in (Path.home() / "Desktop", Path.home() / "Escritorio"):
        if candidate.exists():
            return candidate
    return Path.home()


def slugify(text, fallback="persona"):
    """Convierte 'Maria Jose Pena' en 'maria-jose-pena' (seguro para archivos)."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug[:24] or fallback
