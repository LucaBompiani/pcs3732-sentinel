"""Indicadores (LEDs/buzzer) simulados."""


class MockIndicators:
    """LEDs e buzzer simulados; cada ação é registrada em ``events``."""

    def __init__(self):
        self.events = []

    def signal_granted(self):
        """Feedback de acesso concedido: LED contínuo + um bipe curto ("pi")."""
        self.events.append("granted")
        self.beep("ok")
        self.led_green(True)

    def signal_denied(self):
        """Feedback de acesso negado: LED piscando + "pi pi piiii"."""
        self.events.append("denied")
        self.led_green(False)
        self.beep("fail")
        self.led_red(True)

    def led_green(self, on):
        self.events.append(("led_green", bool(on)))

    def led_red(self, on):
        self.events.append(("led_red", bool(on)))

    def beep(self, pattern="ok"):
        self.events.append(("beep", pattern))


def make(cfg):
    """Cria os indicadores simulados."""
    return MockIndicators()
