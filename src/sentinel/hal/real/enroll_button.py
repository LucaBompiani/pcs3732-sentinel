"""Driver real do botão físico de cadastro (gpiozero)."""

# Pino BCM do botão (ajustar conforme a montagem física).
BUTTON_PIN = 23


class RealEnrollButton:
    """Botão de enrolamento via ``gpiozero.Button`` (import tardio)."""

    def __init__(self, pin=BUTTON_PIN):
        from gpiozero import Button

        self._button = Button(pin)

    def wait_for_press(self, timeout=None):
        return self._button.wait_for_press(timeout=timeout)


def make(cfg):
    """Instancia o driver real do botão de cadastro."""
    return RealEnrollButton()
