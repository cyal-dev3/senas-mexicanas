# Mira&Tek · Lengua de Señas Mexicana

<img src="assets/logo.png" width="120" align="right" alt="Logo de Mira&Tek">

Proyecto de **Technovation Girls 2026**. Una app de **Android** reconoce señas de la Lengua de Señas
Mexicana (LSM) con la cámara del celular y las convierte en texto y voz. Funciona **sin internet**.

- **Palabras:** Hola, Gracias, Por favor, Sí, No, Ayuda, Agua, Comida, Baño, Doctor, Familia, Amigo, Disculpa, Te quiero.
- **Abecedario:** A–Z y Ñ. Las letras se juntan en palabras (H-O-L-A → HOLA).
- **Números:** como en LSM, del 0 al 19, las decenas y el 100 tienen su propia seña; la app arma el
  resto (20 y luego 3 → 23; 100, 20 y 5 → 125).

Son **dos apps de Android** y una de PC, todas sin servidores:

| App | Para qué |
|---|---|
| **Mira&Tek** (`dist/MiraTek.apk`) | Traducir señas en vivo, aprenderlas y practicarlas. |
| **Mira&Tek Entrenador** (`dist/MiraTek-Entrenador.apk`) | Que muchas personas graben sus señas desde el celular, se junten las grabaciones y se entrene el modelo ahí mismo. |
| **MiraTek.exe** (PC con Windows) | Lo mismo que el Entrenador pero en computadora. Usa exactamente los mismos archivos. |

## Cómo funciona el proyecto

```
 Personas que graban                 Quien coordina                          Todas las personas
 (celular o PC)                      (celular o PC)                          (celular)
 ┌───────────────────────┐   .zip   ┌──────────────────────────────┐  .json  ┌────────────────────┐
 │ Entrenador / .exe     │ ───────▶ │ Entrenador / .exe            │ ──────▶ │ Mira&Tek (APK)     │
 │ 1. Grabar señas       │          │ 3. Abrir archivos recibidos  │  o APK  │ Reconoce en vivo,  │
 │ 2. Enviar archivo     │          │ 4. Entrenar con todas        │         │ arma frases y las  │
 │                       │          │ 5. Compartir el modelo       │         │ lee en voz alta    │
 └───────────────────────┘          └──────────────────────────────┘         └────────────────────┘
```

El modelo aprende de las manos de quienes graban. Para que reconozca bien a **cualquier** persona, hacen
falta grabaciones de **varias personas distintas** (mínimo 3, ideal 5 o más): por eso el Entrenador
existe como app de celular, para que grabar sea fácil para todo el equipo.

## Para quienes graban (sin conocimientos técnicos)

### Desde el celular (Mira&Tek Entrenador)

1. Instala `MiraTek-Entrenador.apk`, permite la cámara y escribe tu nombre.
2. Toca **Empezar a grabar**. La app te guía: cuenta regresiva, haces la seña una vez y guarda sola; luego
   pasa al siguiente clip y, al completar la meta (15 por seña), a la siguiente seña. El botón **?** te
   muestra cómo se hace cada seña con una animación y su descripción.
3. Si un clip sale mal, toca **↶** (borra la última grabación). Puedes pausar y grabar por partes: tu
   avance se guarda solo. Grabar todo (71 señas × 15) toma cerca de una hora.
4. En **Compartir → Crear archivo para enviar** se crea un `.zip` y se abre la hoja de compartir del
   teléfono: mándalo por WhatsApp, correo o Drive a quien coordina.

### Desde la PC (MiraTek.exe)

1. Abre **MiraTek.exe**. Si Windows muestra «Windows protegió su PC», elige **Más información →
   Ejecutar de todas formas** (pasa con cualquier programa nuevo sin firma).
2. Escribe tu nombre y, en **Grabar**, presiona **Empezar a grabar**. Funciona igual que en el celular.
3. En **Compartir**, presiona **Crear archivo para enviar** y manda ese archivo (queda en tu Escritorio).

Consejos: buena luz de frente, a un brazo de distancia, con las manos y la cara dentro del cuadro.
Solo se guardan las posiciones de las manos (21 puntos por mano), **nunca video ni fotos**.

Mensaje sugerido para mandar junto con la APK:

> ¡Hola! Te comparto Mira&Tek Entrenador para grabar señas. Instálalo (si el teléfono avisa, permite
> instalar apps de este origen), escribe tu nombre y sigue los pasos de «Grabar». Al terminar, en
> «Compartir» toca «Crear archivo para enviar» y mándamelo por aquí. ¡Gracias!

## Para quien coordina

1. Abre los `.zip` de todas las personas: en el celular, tócalos en WhatsApp/Archivos y elige **Mira&Tek
   Entrenador** (o **Compartir → Elegir archivo**); en la PC, **Compartir → Abrir archivos recibidos**.
   Las grabaciones se juntan sin duplicados y en **Compartir → Personas** ves quién ha grabado.
2. En **Entrenar**, entrena con todas. Con 2 o más personas se hace un **examen honesto**: el modelo
   aprende sin una persona y trata de reconocerla, como si fuera alguien nuevo. Ese es el porcentaje que
   importa (el de una sola persona sale inflado). En el celular tarda de 1 a 10 minutos; deja la app
   abierta.
3. Lleva el modelo a los celulares:
   - **Abrir en Mira&Tek:** si la app de traducción está en el mismo teléfono, el modelo se carga directo.
   - **Compartir el modelo:** manda el `.json` por WhatsApp; en el otro teléfono se abre con Mira&Tek
     (tocándolo, o en Ajustes → Cargar modelo).
   - **APK con el modelo incluido:** en la PC, doble clic en `Construir apk.bat` → `dist/MiraTek.apk`.
4. Para instalar una APK, pásala al celular y permite «instalar apps de origen desconocido».

El celular y la PC usan los **mismos archivos** (`.npz` por clip, `.zip` de paquete, modelo `.npz` y
`.json`): puedes grabar en uno, juntar en otro y entrenar donde prefieras.

> ⚠️ La primera vez, `Construir apk.bat` crea la llave de firma en `android/keystore/`. **Guárdala.**
> Sin ella no se puede actualizar la app ya instalada (habría que desinstalarla primero). No se sube a GitHub.

## App de Android (Mira&Tek)

Cuatro secciones en el menú de abajo:

- **Traductor:** la cámara ocupa casi toda la pantalla para que te veas completo. Modos **Palabras**,
  **Deletreo** y **Números** (cada modo solo compite contra su categoría: una «O» nunca se confunde con
  el «0»), frase en una barra delgada y botón **Leer en voz alta** (voz del teléfono, sin internet).
- **Aprender:** cada seña con una animación grabada por el equipo (se ve como en un espejo), cómo se hace
  y **Practicar con la cámara**: la app te dice si la hiciste bien.
- **Perfil:** nombre, nivel según las señas practicadas y los planes (Inclusión, Pro y Aliado). Por ahora
  los planes solo se muestran: no hay cobros (la app no usa internet ni servidores).
- **Ajustes:** cargar modelo, sensibilidad, cámara y lectura automática.

Ninguna de las dos apps pide permiso de internet: la cámara nunca sale del teléfono.

**Instrucciones de las señas:** están en `assets/senas_info.json` (las usan la PC y las dos apps). Se
generan con `tools/make_signs_info.py`: las de Keysita van tal cual y el resto se redactó a partir del
Diccionario de Lengua de Señas Mexicana «Manos con Voz» (SEP/CONAPRED). Faltan **Hola**, **Doctor**,
**Disculpa** y **0**, que no vienen en ese diccionario: mientras, las apps muestran su animación.

## Para desarrollar

Requisitos: Python 3.10–3.14 (Windows para el `.exe`) y, para las APK, JDK 17 y el Android SDK
(`tools/build_apk.py` los busca en `JAVA_HOME`/`ANDROID_HOME`, Android Studio o scoop). Con `scoop`:

```bash
scoop bucket add java
scoop bucket add extras
scoop install temurin17-jdk android-clt
sdkmanager --licenses
sdkmanager "platform-tools" "platforms;android-35" "build-tools;35.0.0"
```

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\python app.py --demo        # cámara simulada, útil sin webcam
.venv\Scripts\python -m pytest            # pruebas de Python
```

| Tarea | Comando |
|---|---|
| Construir `dist/MiraTek.exe` (incluye autoprueba) | `Construir exe.bat` |
| Construir las dos APK con el modelo de esta PC | `Construir apk.bat` (o `python tools/build_apk.py app` / `trainer`) |
| Pruebas de Android (paridad con Python, entrenador, formatos) | `cd android` y `gradlew testDebugUnitTest` |
| Capturas de pantalla de la PC | `.venv\Scripts\python tools\screenshots.py capturas` |
| Capturas de pantalla de Android (sin celular) | `cd android` y `gradlew recordPaparazziDebug` |
| Regenerar íconos desde `assets/logo.png` | `.venv\Scripts\python tools\make_assets.py` |

En GitHub, cada `push` corre las pruebas de Python y de Android (`.github/workflows/ci.yml`).

**Agregar una seña:** súmala a `SIGNS` en `miratek/config.py` y a `tools/make_signs_info.py`, regenera
`assets/senas_info.json`, grábala y vuelve a entrenar. Las apps toman la lista de señas de ese archivo y
del modelo.

**Paridad PC ↔ celular:** `miratek/features.py`, `recognizer.py` y `phrase.py` tienen copias exactas en
`android/core/src/main/java/mx/miratek/senas/core/`; `augment.py`, `mlp.py`, `training.py`, `dataset.py`
y `package.py` en `android/trainer/.../train` y `.../data`. Si cambias una, cambia la otra, corre
`tools/make_parity_vectors.py` y las pruebas de Android. Las pruebas fallan si los resultados no coinciden.

### Cómo reconoce las señas

1. **MediaPipe** encuentra 21 puntos por mano, en la PC y en el celular.
2. Una ventana de ~2 segundos se convierte en 728 números: la forma 3D de la mano (relativa a la muñeca y
   al tamaño de la palma), la trayectoria del movimiento y la posición. Si la seña la hace la mano
   izquierda, se refleja como espejo, así funciona para personas zurdas y diestras.
3. Una red neuronal pequeña (MLP escrita a mano, en NumPy y en Kotlin) da la probabilidad de cada seña.
   Al entrenar se generan variaciones de cada grabación (más cerca o lejos, giro, velocidad, frames
   perdidos y ventanas que empiezan con la cola de otra seña, como pasa en vivo). La confianza se calibra
   con el examen de personas nuevas, para que «80 %» signifique de verdad 80 % con gente que no grabó.
4. En vivo, las probabilidades se suavizan y una seña solo se confirma si gana varias veces seguidas.
   La clase **«Nada»** evita que «adivine» cuando no estás haciendo ninguna seña.

### Estructura

```
app.py                  arranque de la app de PC
miratek/                núcleo (características, modelo, entrenamiento) e interfaz (miratek/ui)
android/core/           lo que comparten las dos apps: características, modelo, reconocedor, cámara, tema
android/app/            Mira&Tek (traductor): Kotlin + Jetpack Compose + CameraX + MediaPipe
android/trainer/        Mira&Tek Entrenador: grabar, juntar y entrenar en el celular (.npz/.zip iguales a la PC)
assets/                 logo, íconos, el detector de manos de MediaPipe e instrucciones de las señas
tests/                  pruebas de Python
tools/                  construir .exe/.apk, íconos, capturas y datos de paridad
```

## Límites

- El modelo solo es tan bueno como sus grabaciones: graben **varias personas** (mínimo 3, ideal 5+) y
  pidan a alguien que sepa LSM que revise cómo se hace cada seña.
- Las señas se reconocen de una en una (no frases continuas rápidas). Al deletrear, mantén cada letra
  aproximadamente un segundo; para repetir una letra (LL, RR) baja la mano un momento entre las dos.
