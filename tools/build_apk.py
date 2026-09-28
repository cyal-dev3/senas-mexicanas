"""
Construye la APK de Android con el modelo que se entreno en ESTA computadora.

    python tools/build_apk.py

Pasos:
  1. Exporta el modelo actual a la app (Gradle agrega el detector de manos).
  2. Crea la llave de firma la primera vez (android/keystore). GUARDENLA:
     sin ella no se puede actualizar la app ya instalada en los celulares.
  3. Compila con Gradle y deja la APK en dist/MiraTek.apk.
"""

import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
ANDROID = ROOT / "android"
ASSETS = ANDROID / "app" / "src" / "main" / "assets"


def _env():
    env = dict(os.environ)
    home = Path.home()
    env.setdefault("JAVA_HOME", str(home / "scoop" / "apps" / "temurin17-jdk" / "current"))
    env.setdefault("ANDROID_HOME", str(home / "scoop" / "apps" / "android-clt" / "current"))
    env["PATH"] = str(Path(env["JAVA_HOME"]) / "bin") + os.pathsep + env.get("PATH", "")
    return env


def export_model():
    from miratek import config
    from miratek.export_android import export_android_model
    from miratek.training import TrainedModel

    ASSETS.mkdir(parents=True, exist_ok=True)
    model_path = config.user_data_dir() / "modelos" / "modelo_actual.npz"
    target = ASSETS / "modelo_android.json"
    if model_path.exists():
        model = TrainedModel.load(model_path)
        export_android_model(model, target)
        print(f"Modelo incluido: {len(model.classes)} señas "
              f"({model.report.accuracy:.0%} en el examen)" if model.report else "Modelo incluido.")
    else:
        target.unlink(missing_ok=True)
        print("Aviso: no hay modelo entrenado en esta PC. La app pedirá cargar uno desde un archivo.")


def ensure_keystore(env):
    folder = ANDROID / "keystore"
    props = folder / "keystore.properties"
    if props.exists():
        if not (folder / "miratek.jks").exists():
            sys.exit("Falta la llave android/keystore/miratek.jks. Recupérala de tu respaldo. Si se perdió, "
                     "borra keystore.properties para crear una nueva (los celulares tendrán que "
                     "desinstalar la app anterior antes de instalar la nueva).")
        return
    folder.mkdir(exist_ok=True)
    password = secrets.token_urlsafe(18)
    keytool = Path(env["JAVA_HOME"]) / "bin" / ("keytool.exe" if os.name == "nt" else "keytool")
    subprocess.run([
        str(keytool), "-genkeypair", "-keystore", str(folder / "miratek.jks"), "-alias", "miratek",
        "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000",
        "-storepass", password, "-keypass", password,
        "-dname", "CN=Mira&Tek, O=Technovation Girls, C=MX",
    ], check=True, env=env, capture_output=True)
    props.write_text(f"storeFile=miratek.jks\nstorePassword={password}\nkeyAlias=miratek\nkeyPassword={password}\n",
                     encoding="utf-8")
    print(f"Se creó la llave de firma en {folder}. Guárdala en un lugar seguro.")


def main():
    env = _env()
    export_model()
    ensure_keystore(env)
    gradlew = ANDROID / ("gradlew.bat" if os.name == "nt" else "gradlew")
    subprocess.run([str(gradlew), "assembleRelease", "--console=plain"], cwd=ANDROID, env=env, check=True)
    apk = ANDROID / "app" / "build" / "outputs" / "apk" / "release" / "app-release.apk"
    out = ROOT / "dist" / "MiraTek.apk"
    out.parent.mkdir(exist_ok=True)
    shutil.copy2(apk, out)
    print(f"\nListo: {out} ({out.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
