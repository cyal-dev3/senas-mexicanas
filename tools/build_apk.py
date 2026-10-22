"""
Construye las dos APK de Android con el modelo que se entreno en ESTA computadora.

    python tools/build_apk.py            # las dos apps
    python tools/build_apk.py app        # solo Mira&Tek (traductor)
    python tools/build_apk.py trainer    # solo Mira&Tek Entrenador

Pasos:
  1. Exporta el modelo actual (para el traductor) y las animaciones de "Aprender"
     (para las dos apps). Gradle agrega el detector de manos y las instrucciones.
  2. Crea la llave de firma la primera vez (android/keystore). GUARDENLA:
     sin ella no se puede actualizar la app ya instalada en los celulares.
  3. Compila con Gradle y deja dist/MiraTek.apk y dist/MiraTek-Entrenador.apk.

Necesita un JDK 17 y el SDK de Android. Se buscan en JAVA_HOME / ANDROID_HOME,
en Android Studio y en scoop; si no estan, el script dice que falta.
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
APP_ASSETS = ANDROID / "app" / "src" / "main" / "assets"

APKS = {
    "app": ("app", "MiraTek.apk"),
    "trainer": ("trainer", "MiraTek-Entrenador.apk"),
}


def _first_existing(candidates):
    for c in candidates:
        if c and Path(c).exists():
            return str(Path(c))
    return None


def _env():
    """JAVA_HOME y ANDROID_HOME: lo que ya este configurado, o lugares comunes."""
    env = dict(os.environ)
    home = Path.home()
    local = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    java = _first_existing([
        env.get("JAVA_HOME"),
        home / "scoop" / "apps" / "temurin17-jdk" / "current",
        program_files / "Android" / "Android Studio" / "jbr",
        program_files / "Eclipse Adoptium" / "jdk-17.0.13.11-hotspot",
        "/usr/lib/jvm/java-17-openjdk-amd64",
        "/opt/homebrew/opt/openjdk@17",
    ])
    sdk = _first_existing([
        env.get("ANDROID_HOME"),
        env.get("ANDROID_SDK_ROOT"),
        home / "scoop" / "apps" / "android-clt" / "current",
        local / "Android" / "Sdk",
        home / "Android" / "Sdk",
        home / "Library" / "Android" / "sdk",
    ])
    if not java:
        sys.exit("No encontré un JDK 17. Instala Android Studio (trae uno) o pon JAVA_HOME.")
    if not sdk:
        sys.exit("No encontré el SDK de Android. Instala Android Studio o pon ANDROID_HOME.")
    env["JAVA_HOME"] = java
    env["ANDROID_HOME"] = sdk
    env["PATH"] = str(Path(java) / "bin") + os.pathsep + env.get("PATH", "")
    return env


def export_model():
    from miratek import config
    from miratek.export_android import export_android_model
    from miratek.training import TrainedModel

    APP_ASSETS.mkdir(parents=True, exist_ok=True)
    model_path = config.user_data_dir() / "modelos" / "modelo_actual.npz"
    target = APP_ASSETS / "modelo_android.json"
    if model_path.exists():
        model = TrainedModel.load(model_path)
        export_android_model(model, target)
        if model.report:
            print(f"Modelo incluido: {len(model.classes)} señas ({model.report.accuracy:.0%} en el examen)")
        else:
            print(f"Modelo incluido: {len(model.classes)} señas")
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
    print(f"Se creó la llave de firma en {folder}. Guárdala en un lugar seguro (y fuera de GitHub).")


def main(targets=("app", "trainer")):
    env = _env()
    if "app" in targets:
        export_model()
    from tools.make_learn_assets import main as make_learn_assets
    make_learn_assets()  # animaciones de "Aprender" y del Entrenador, a partir de las grabaciones de esta PC
    ensure_keystore(env)
    gradlew = ANDROID / ("gradlew.bat" if os.name == "nt" else "gradlew")
    tasks = [f":{APKS[t][0]}:assembleRelease" for t in targets]
    subprocess.run([str(gradlew), *tasks, "--console=plain"], cwd=ANDROID, env=env, check=True)
    (ROOT / "dist").mkdir(exist_ok=True)
    for t in targets:
        module, name = APKS[t]
        apk = ANDROID / module / "build" / "outputs" / "apk" / "release" / f"{module}-release.apk"
        out = ROOT / "dist" / name
        shutil.copy2(apk, out)
        print(f"\nListo: {out} ({out.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    chosen = [a for a in sys.argv[1:] if a in APKS] or list(APKS)
    main(tuple(chosen))
