"""Driver real do teclado matricial 4x4 (gpiozero)."""

import time

# Pinos BCM das linhas e colunas, fixos na Freenove Projects Board
# (Tutorial, cap. 21 "Matrix Keypad"). Não são ajustáveis: o teclado já vem
# soldado na placa.
#
# ATENÇÃO: a linha 3 (GPIO 26) é compartilhada com o touch button da placa
# (Tutorial, pág. 41, nota 2: "Touch button and keypad must NOT be used at the
# same time"). Por isso o cadastro é disparado por uma tecla — ver
# :mod:`sentinel.hal.real.enroll_button`.
ROW_PINS = [16, 20, 21, 26]
COL_PINS = [19, 13, 6, 5]
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

    def wait_for_key(self, accept, timeout=None):
        """Aguarda uma das teclas em ``accept`` e a retorna, ou ``None``.

        Usado pelo botão de cadastro, que na Projects Board é uma tecla do
        próprio teclado em vez de um botão dedicado.
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        while deadline is None or time.monotonic() < deadline:
            key = self._scan_key()
            if key is not None and key in accept:
                time.sleep(0.2)  # debounce simples
                return key
            time.sleep(0.05)
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
