"""
Construye dist/MiraTek.exe (un solo archivo) con PyInstaller.

    python tools/build_exe.py

Despues corre MiraTek.exe --autoprueba para confirmar que todo lo
empaquetado funciona (detector de manos, entrenamiento e interfaz).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEP = ";" if os.name == "nt" else ":"


def _qt_translations():
    """Botones de Qt en espanol dentro del .exe (si PySide6 trae las traducciones)."""
    import PySide6
    folder = Path(PySide6.__file__).parent / "translations"
    args = []
    for name in ("qtbase_es.qm", "qt_es.qm"):
        if (folder / name).exists():
            args += ["--add-data", f"{folder / name}{SEP}assets/traducciones"]
    return args


def main():
    os.chdir(ROOT)
    assets = ROOT / "assets"
    if not (assets / "icon.ico").exists() or not (assets / "splash.png").exists():
        subprocess.run([sys.executable, "tools/make_assets.py"], check=True)

    import PyInstaller.__main__
    PyInstaller.__main__.run([
        "app.py",
        "--name", "MiraTek",
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--icon", str(assets / "icon.ico"),
        "--splash", str(assets / "splash.png"),
        "--add-data", f"{assets / 'hand_landmarker.task'}{SEP}assets",
        "--add-data", f"{assets / 'icon.png'}{SEP}assets",
        "--add-data", f"{assets / 'logo.png'}{SEP}assets",
        "--add-data", f"{assets / 'senas_info.json'}{SEP}assets",
        *_qt_translations(),
        "--collect-binaries", "mediapipe",
        "--collect-data", "mediapipe",
        "--exclude-module", "pytest",
        "--exclude-module", "IPython",
    ])

    exe = ROOT / "dist" / ("MiraTek.exe" if os.name == "nt" else "MiraTek")
    print(f"\nListo: {exe} ({exe.stat().st_size / 1e6:.0f} MB)")
    print("Revisando que funcione (autoprueba)…")
    code = subprocess.run([str(exe), "--autoprueba"]).returncode
    report = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "MiraTek" / "autoprueba.txt"
    if report.exists():
        print(report.read_text(encoding="utf-8"))
    if code != 0:
        sys.exit("La autoprueba falló: revisa el reporte de arriba.")
    shutil.rmtree(ROOT / "build", ignore_errors=True)


if __name__ == "__main__":
    main()
