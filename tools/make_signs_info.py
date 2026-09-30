"""
Genera assets/senas_info.json: como se hace cada sena (lo usan la PC y el celular).

Fuentes:
  - "keysita": instrucciones que escribio Keysita (se dejan tal cual).
  - "sep": redactadas a partir del Diccionario de Lengua de Senas Mexicana
    "Manos con Voz" (SEP / CONAPRED).
  - "pendiente": todavia no hay descripcion confiable; la app muestra la
    animacion grabada y pide confirmar con alguien que sepa LSM.

Para corregir o agregar una instruccion, editen este archivo y vuelvan a correrlo:
    python tools/make_signs_info.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

KEYSITA = {
    "gracias": "Coloca tu mano base plana con la palma hacia arriba y toca la palma con el dedo medio de tu otra "
               "mano haciendo un leve movimiento hacia arriba.",
    "por_favor": "Junta tus dos manos 🙏 a la altura de tu pecho.",
    "familia": "Se realiza configurando la mano dominante en la letra F (con el dedo índice y el pulgar tocándose "
               "por las puntas formando un círculo, y los otros tres dedos extendidos hacia arriba). La mano base se "
               "coloca al frente, usualmente en forma de puño cerrado o extendida boca abajo; posteriormente, la "
               "punta de los dedos de la mano en \"F\" hace un movimiento deslizándose a lo largo del brazo base, "
               "recorriéndolo desde el antebrazo o codo hacia la muñeca.",
    "si": "Cierra tu mano en puño y levanta únicamente el pulgar, haciendo movimientos con él de arriba a abajo.",
    "ayuda": "Mano base: coloca tu mano no dominante frente a ti, extendida y con la palma mirando hacia arriba. "
             "Mano dominante: configura tu mano dominante haciendo el puño en forma de la letra A (el puño cerrado "
             "con el pulgar apoyado a un lado). Colocación: apoya la parte lateral de la mano en \"A\" (el lado del "
             "dedo meñique) sobre la palma abierta de tu mano base.",
    "bano": "Configura tu mano con la letra B y después llévala a tu pecho; levemente muévela de arriba hacia abajo.",
    "te_quiero": "Coloca tu mano dominante en forma de letra \"C\" (con los dedos curvados hacia el frente) y tócala "
                 "suavemente contra el pecho, del lado del corazón.",
    "agua": "Extiende el dedo índice de tu mano dominante y mantén los demás dedos doblados formando un puño suelto. "
            "Coloca tu mano cerca de la barbilla o a la altura de la boca y realiza un movimiento repetitivo con el "
            "dedo índice de arriba hacia abajo.",
    "comida": "Junta las yemas de todos los dedos de tu mano dominante con el pulgar, formando una especie de "
              "\"conito\" o \"pinza\" con la mano. Llévala hacia la altura de la boca y haz un movimiento leve de "
              "adentro hacia afuera.",
}
KEYSITA_ALT = {
    "familia": "Opción dos (si conoces el abecedario): pon tu mano dominante en forma de letra \"F\" (índice y "
               "pulgar tocándose) y deslízala sobre tu otro brazo, avanzando desde el codo hacia la muñeca.",
}

SEP = {
    # Palabras
    "no": "Con el índice, el medio y el pulgar estirados, júntalos hasta que se toquen por las yemas.",
    "amigo": "Coloca la palma de una mano sobre el dorso de la otra.",
    # Abecedario
    "letra_a": "Cierra la mano mostrando las uñas y deja el pulgar estirado a un lado. La palma mira al frente.",
    "letra_b": "Estira los dedos índice, medio, anular y meñique bien juntos y dobla el pulgar hacia la palma. "
               "La palma mira al frente.",
    "letra_c": "Junta los cuatro dedos y cúrvalos, junto con el pulgar, como formando una C. La palma mira a un lado.",
    "letra_d": "Une por las puntas los dedos medio, anular y meñique con el pulgar, y deja el índice estirado. "
               "La palma mira al frente.",
    "letra_e": "Dobla todos los dedos por completo, mostrando las uñas. La palma mira al frente.",
    "letra_f": "Con la mano abierta y los dedos juntos, dobla el índice hasta que su costado toque la yema del "
               "pulgar. La palma mira a un lado.",
    "letra_g": "Cierra la mano y estira el índice y el pulgar. La palma mira hacia ti.",
    "letra_h": "Cierra la mano y estira juntos el índice y el medio; el pulgar señala hacia arriba. "
               "La palma mira hacia ti.",
    "letra_i": "Cierra la mano y estira el meñique señalando hacia arriba. La palma mira a un lado.",
    "letra_j": "Con la mano cerrada y el meñique estirado hacia arriba, dibuja una J en el aire. "
               "La palma mira a un lado.",
    "letra_k": "Cierra la mano estirando el índice, el medio y el pulgar, con la yema del pulgar entre el índice "
               "y el medio. Mueve la muñeca hacia arriba.",
    "letra_l": "Cierra la mano y estira el índice y el pulgar formando una L. La palma mira al frente.",
    "letra_m": "Cierra la mano y coloca los dedos índice, medio y anular sobre el pulgar.",
    "letra_n": "Cierra la mano y coloca los dedos índice y medio sobre el pulgar.",
    "letra_enie": "Haz la N (índice y medio sobre el pulgar) y mueve la muñeca de un lado a otro.",
    "letra_o": "Forma una O con la mano: todos los dedos se tocan por las puntas.",
    "letra_p": "Cierra la mano estirando el índice, el medio y el pulgar, con la yema del pulgar entre el índice "
               "y el medio (como la K, pero sin movimiento).",
    "letra_q": "Cierra la mano y pon el índice y el pulgar en forma de garra, con la palma hacia abajo. "
               "Mueve la muñeca de un lado a otro.",
    "letra_r": "Cierra la mano y estira el índice y el medio entrelazados (cruzados). La palma mira al frente.",
    "letra_s": "Cierra la mano con el pulgar sobre los demás dedos. La palma mira al frente.",
    "letra_t": "Cierra la mano con el pulgar metido entre el índice y el medio. La palma mira al frente.",
    "letra_u": "Cierra la mano y estira el índice y el medio juntos. La palma mira al frente.",
    "letra_v": "Cierra la mano y estira el índice y el medio separados. La palma mira al frente.",
    "letra_w": "Cierra la mano y estira el índice, el medio y el anular separados. La palma mira al frente.",
    "letra_x": "Cierra la mano con el índice y el pulgar en forma de garra y la palma hacia un lado; "
               "muévela hacia el frente y regresa.",
    "letra_y": "Cierra la mano y estira el meñique y el pulgar. La palma mira hacia ti.",
    "letra_z": "Con la mano cerrada, el índice estirado y la palma al frente, dibuja una Z en el aire.",
    # Numeros
    "num_1": "Estira el índice con la palma al frente.",
    "num_2": "Estira el índice y el medio.",
    "num_3": "Estira el índice, el medio y el anular, con la palma al frente.",
    "num_4": "Estira el índice, el medio, el anular y el meñique.",
    "num_5": "Abre la mano con la palma al frente y los dedos separados.",
    "num_6": "Haz la letra A con el pulgar hacia arriba.",
    "num_7": "Haz la letra G un poco inclinada.",
    "num_8": "Estira el pulgar, el índice y el medio separados, con la palma hacia ti.",
    "num_9": "Haz la letra B con la palma hacia ti y luego cierra los dedos alrededor del pulgar.",
    "num_10": "Haz el 5 con la palma hacia arriba y gira la mano rápidamente hacia abajo.",
    "num_11": "Haz la letra A con la palma hacia ti y el pulgar hacia arriba, y gira la mano hacia arriba y a un lado.",
    "num_12": "Haz el 7 y mueve la mano hacia arriba y a un lado.",
    "num_13": "Haz el 8 y gira la mano hacia arriba y a un lado.",
    "num_14": "Estira el índice, el medio, el anular y el meñique, y mueve la mano hacia arriba y a un lado.",
    "num_15": "Con las dos manos abiertas y las palmas hacia ti, una delante de la otra, muévelas alternadamente "
              "hacia arriba y a un lado.",
    "num_16": "Haz el 6 con la palma hacia abajo y muévelo hacia adelante.",
    "num_17": "Haz el 7 con la palma hacia abajo y muévelo hacia adelante.",
    "num_18": "Haz el 8 con las puntas de los dedos hacia el frente y muévelo hacia adelante.",
    "num_19": "Haz el 4 con las puntas de los dedos hacia el frente y muévelo hacia adelante.",
    "num_20": "Con la mano cerrada, junta y separa las puntas del índice y el pulgar.",
    "num_30": "Toca la punta del pulgar con la punta del dedo medio, dejando el índice un poco levantado.",
    "num_40": "Con la mano abierta, junta y separa las yemas del índice y el pulgar.",
    "num_50": "Abre la mano con la palma hacia ti y los dedos separados, y mueve los dedos uno por uno hacia "
              "adelante y atrás.",
    "num_60": "Haz la letra S e intenta abrir y cerrar la mano varias veces.",
    "num_70": "Haz el 7 y junta y separa el pulgar y el índice varias veces.",
    "num_80": "Estira el índice, el medio y el pulgar señalando al frente, y júntalos y sepáralos varias veces.",
    "num_90": "Con los dedos juntos y la palma al frente, sepáralos y júntalos varias veces.",
    "num_100": "Estira el índice y muévelo hacia un lado hasta formar una C.",
}
SEP_ALT = {
    "num_15": "Otra forma: haz el 5 y gira la mano hacia arriba y a un lado.",
}
OWN = {
    "nada": "No hagas ninguna seña: baja las manos, ráscate o acomódate el pelo. Así la app aprende cuándo NO "
            "estás haciendo una seña.",
}
PENDING = {"hola", "doctor", "disculpa", "num_0"}

SOURCES = {
    "keysita": "Instrucciones de Keysita",
    "sep": "Basado en el Diccionario de Lengua de Señas Mexicana «Manos con Voz» (SEP/CONAPRED)",
    "mira": "Mira&Tek",
    "pendiente": "Descripción pendiente: imita la animación y confírmala con alguien que sepa LSM",
}


def main():
    import sys
    sys.path.insert(0, str(ROOT))
    from miratek import config

    signs = {}
    for sign in config.SIGNS:
        sid = sign.id
        if sid in KEYSITA:
            entry = {"text": KEYSITA[sid], "source": "keysita"}
            if sid in KEYSITA_ALT:
                entry["alt"] = KEYSITA_ALT[sid]
        elif sid in SEP:
            entry = {"text": SEP[sid], "source": "sep"}
            if sid in SEP_ALT:
                entry["alt"] = SEP_ALT[sid]
        elif sid in OWN:
            entry = {"text": OWN[sid], "source": "mira"}
        else:
            entry = {"text": "", "source": "pendiente"}
        entry.update({"name": sign.name, "category": sign.category})
        signs[sid] = entry
    missing = [s for s, e in signs.items() if e["source"] == "pendiente"]
    assert set(missing) <= PENDING, f"faltan instrucciones: {missing}"
    out = {"version": 1, "sources": SOURCES, "signs": signs}
    path = ROOT / "assets" / "senas_info.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(signs)} señas -> {path} (pendientes: {', '.join(missing) or 'ninguna'})")


if __name__ == "__main__":
    main()
