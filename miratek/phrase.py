"""
Arma la frase a partir de las senas reconocidas.

  - Palabras: cada sena es una palabra nueva.
  - Letras: se juntan en una palabra mientras no bajes las manos (H-O-L-A -> HOLA).
  - Numeros: como en la Lengua de Senas Mexicana, del 0 al 19, las decenas y
    el 100 tienen su propia sena; los demas se arman sumando:
        20 y luego 3        -> 23   (decena + unidad)
        100, 20 y luego 5   -> 125  (cien + lo que sigue)
    Bajar las manos (o hacer "Nada") termina la palabra o el numero.

La app de Android usa exactamente las mismas reglas (Phrase.kt).
"""

from dataclasses import dataclass

from . import config


@dataclass
class Item:
    text: str
    kind: str              # "word", "spell" o "number"
    open: bool = False     # True mientras se le pueden agregar letras o digitos
    value: int = 0         # valor del numero
    last_token: int = -1   # ultima sena de numero que se agrego


class PhraseBuilder:
    def __init__(self):
        self.items = []

    @property
    def texts(self):
        return [item.text for item in self.items]

    def add(self, sign_id):
        number = config.number_value(sign_id)
        if number is not None:
            self._add_number(number)
        elif config.is_letter(sign_id):
            self._add_letter(config.sign_name(sign_id))
        elif sign_id != config.NOTHING_ID:
            self.close()
            self.items.append(Item(config.sign_name(sign_id), "word"))

    def close(self):
        """Termina la palabra deletreada o el numero en curso."""
        if self.items:
            self.items[-1].open = False

    def _last_open(self, kind):
        if self.items and self.items[-1].open and self.items[-1].kind == kind:
            return self.items[-1]
        return None

    def _add_letter(self, letter):
        item = self._last_open("spell")
        if item:
            item.text += letter
        else:
            self.close()
            self.items.append(Item(letter, "spell", open=True))

    def _add_number(self, v):
        item = self._last_open("number")
        if item:
            prev_token = item.last_token
            new = None
            if prev_token == 100 and 1 <= v <= 99:
                new = item.value + v          # 100 y 25 = 125
            elif prev_token in range(20, 100, 10) and 1 <= v <= 9:
                new = item.value + v          # 20 y 3 = 23
            if new is not None:
                item.value, item.last_token, item.text = new, v, str(new)
                return
        self.close()
        self.items.append(Item(str(v), "number", open=True, value=v, last_token=v))

    def delete_last(self):
        if not self.items:
            return
        item = self.items[-1]
        if item.kind == "spell" and item.open and len(item.text) > 1:
            item.text = item.text[:-1]
        else:
            self.items.pop()

    def clear(self):
        self.items = []
