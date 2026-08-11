"""Driver real de LEDs e buzzer (gpiozero)."""

import time

# Pinos BCM (ajustar conforme a montagem física).
GREEN_PIN = 17
RED_PIN = 27
BUZZER_PIN = 22


class RealIndicators:
    """LEDs verde/vermelho e buzzer via ``gpiozero`` (import tardio)."""

    def __init__(self, green=GREEN_PIN, red=RED_PIN, buzzer=BUZZER_PIN):
        from gpiozero import LED, Buzzer

        self._green = LED(green)
        self._red = LED(red)
        self._buzzer = Buzzer(buzzer)

    def led_green(self, on):
        self._green.on() if on else self._green.off()

    def led_red(self, on):
        self._red.on() if on else self._red.off()

    def beep(self, pattern="ok"):
        beeps = 1 if pattern == "ok" else 3
        for _ in range(beeps):
            self._buzzer.on()
            time.sleep(0.1)
            self._buzzer.off()
            time.sleep(0.1)

    def signal_granted(self):
        self.led_red(False)
        self.led_green(True)
        self.beep("ok")

    def signal_denied(self):
        self.led_green(False)
        self.led_red(True)
        self.beep("fail")


def make(cfg):
    """Instancia o driver real dos indicadores."""
    return RealIndicators()
