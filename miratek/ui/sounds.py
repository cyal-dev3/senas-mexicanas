"""
Sonidos suaves para la grabacion (cuenta regresiva, guardado, error).

Los generamos con matematicas la primera vez (ondas senoidales) y los
reproducimos con winsound, que ya viene con Python en Windows.
"""

import math
import struct
import sys
import wave

from .. import config

RATE = 44100
_TONES = {
    "tick": [(660, 0.07)],
    "go": [(988, 0.14)],
    "saved": [(880, 0.08), (1320, 0.12)],
    "error": [(330, 0.12), (262, 0.16)],
    "done": [(784, 0.1), (988, 0.1), (1319, 0.2)],
}
enabled = True


def _write_tone(path, notes, volume=0.22):
    frames = bytearray()
    for freq, dur in notes:
        n = int(RATE * dur)
        for i in range(n):
            env = min(1.0, i / (0.006 * RATE)) * min(1.0, (n - i) / (0.03 * RATE))
            sample = volume * env * (math.sin(2 * math.pi * freq * i / RATE)
                                     + 0.25 * math.sin(4 * math.pi * freq * i / RATE))
            frames += struct.pack("<h", int(max(-1.0, min(1.0, sample)) * 32767))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))


def _path(name):
    folder = config.user_data_dir() / "sonidos"
    folder.mkdir(exist_ok=True)
    path = folder / f"{name}.wav"
    if not path.exists():
        _write_tone(path, _TONES[name])
    return path


def prepare():
    for name in _TONES:
        try:
            _path(name)
        except OSError:
            pass


def play(name):
    if not enabled or sys.platform != "win32":
        return
    try:
        import winsound
        winsound.PlaySound(str(_path(name)), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:
        pass
