"""Indicadores (LEDs/buzzer) simulados."""


class MockIndicators:
    """LEDs e buzzer simulados; cada ação é registrada em ``events``."""

    def __init__(self):
        self.events = []

    def signal_granted(self):
        """Feedback composto de acesso concedido (LED verde + bipe curto)."""
        self.events.append("granted")

    def signal_denied(self):
        """Feedback composto de acesso negado (LED vermelho + bipe longo)."""
        self.events.append("denied")

    def led_green(self, on):
        self.events.append(("led_green", bool(on)))

    def led_red(self, on):
        self.events.append(("led_red", bool(on)))

    def beep(self, pattern="ok"):
        self.events.append(("beep", pattern))


def make(cfg):
    """Cria os indicadores simulados."""
    return MockIndicators()
