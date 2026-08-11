"""Gatilho de cadastro: uma tecla do teclado matricial.

A Freenove Projects Board tem um touch button, mas ele compartilha o GPIO 26
com a linha 3 do teclado (Tutorial, pág. 41, nota 2: "Touch button and keypad
must NOT be used at the same time"). Como o teclado é indispensável (PIN do
segundo fator), o cadastro é disparado por uma tecla dedicada.

O objeto reaproveita a instância de :class:`~sentinel.hal.real.keypad.RealKeypad`
já construída pela fábrica: dois objetos gpiozero nos mesmos pinos colidiriam.
"""

# Tecla que substitui o botão físico de cadastro.
ENROLL_KEY = "A"


class RealEnrollButton:
    """Gatilho de enrolamento acionado pela tecla ``A`` do teclado."""

    def __init__(self, keypad, key=ENROLL_KEY):
        self._keypad = keypad
        self._key = key

    def wait_for_press(self, timeout=None):
        """Aguarda a tecla de cadastro; ``True`` se pressionada a tempo."""
        return self._keypad.wait_for_key({self._key}, timeout=timeout) is not None


def make(cfg, keypad=None):
    """Instancia o gatilho de cadastro sobre o teclado já construído."""
    if keypad is None:
        raise ValueError(
            "O backend real precisa do teclado para o gatilho de cadastro: "
            "a Projects Board não tem botão livre (GPIO 26 é linha do teclado)."
        )
    return RealEnrollButton(keypad)
