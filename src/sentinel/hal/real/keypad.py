"""Driver real do teclado matricial 4x4 (gpiozero)."""

import time

# Pinos BCM das linhas e colunas (ajustar conforme a montagem física).
ROW_PINS = [5, 6, 13, 19]
COL_PINS = [12, 16, 20, 21]
KEYS = [
    ["1", "2", "3", "A"],
    ["4", "5", "6", "B"],
    ["7", "8", "9", "C"],
    ["*", "0", "#", "D"],
]


class RealKeypad:
    """Teclado matricial via varredura de GPIO (import tardio de gpiozero).

    ``#`` confirma o PIN e ``*`` apaga o último dígito.
    """

    def __init__(self, row_pins=ROW_PINS, col_pins=COL_PINS):
        from gpiozero import DigitalInputDevice, DigitalOutputDevice

        self._rows = [DigitalOutputDevice(p) for p in row_pins]
        self._cols = [DigitalInputDevice(p, pull_up=False) for p in col_pins]

    def _scan_key(self):
        for r, row in enumerate(self._rows):
            row.on()
            for c, col in enumerate(self._cols):
                if col.value:
                    row.off()
                    return KEYS[r][c]
            row.off()
        return None

    def read_pin(self, timeout=None):
        """Lê dígitos até ``#`` (confirma) ou o timeout expirar."""
        deadline = None if timeout is None else time.monotonic() + timeout
        digits = []
        while deadline is None or time.monotonic() < deadline:
            key = self._scan_key()
            if key is None:
                time.sleep(0.05)
                continue
            if key == "#":
                return "".join(digits)
            if key == "*":
                digits = digits[:-1]
            else:
                digits.append(key)
            time.sleep(0.2)  # debounce simples
        return None


def make(cfg):
    """Instancia o driver real do teclado."""
    return RealKeypad()
