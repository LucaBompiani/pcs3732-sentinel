"""Driver real de LED e buzzer (gpiozero).

Pinos fixos da Freenove Projects Board (Tutorial, cap. 1 e cap. 6). A placa tem
um ÚNICO LED monocromático (GPIO 17), não um par verde/vermelho. O contrato de
:mod:`sentinel.hal.interfaces` é preservado, mas a negação é sinalizada por
piscada em vez de cor: ``led_red(True)`` pisca o mesmo LED.

O buzzer ativo (GPIO 12) é compartilhado com o relé da placa (Tutorial, pág. 41,
nota 3: "Active buzzer and relay must NOT be used at the same time"). Como o
atuador em uso é o servomotor (GPIO 18), não há conflito — ver
:mod:`sentinel.hal.real.lock` antes de trocar para a fechadura solenoide.
"""

import time

# Pinos BCM da Projects Board (não ajustáveis: componentes soldados).
LED_PIN = 17
BUZZER_PIN = 12

# Piscadas que representam o estado "vermelho" no LED único.
DENY_BLINKS = 3
BLINK_SECONDS = 0.15


class RealIndicators:
    """LED de status e buzzer ativo via ``gpiozero`` (import tardio)."""

    def __init__(self, led=LED_PIN, buzzer=BUZZER_PIN):
        from gpiozero import LED, Buzzer

        self._led = LED(led)
        self._buzzer = Buzzer(buzzer)

    def led_green(self, on):
        """Acende o LED de forma contínua (estado de sucesso)."""
        self._led.on() if on else self._led.off()

    def led_red(self, on):
        """Pisca o LED (estado de falha); ``on=False`` apenas apaga.

        A placa não tem LED vermelho, então a distinção visual entre concedido
        e negado é contínuo vs. intermitente.
        """
        if not on:
            self._led.off()
            return
        for _ in range(DENY_BLINKS):
            self._led.on()
            time.sleep(BLINK_SECONDS)
            self._led.off()
            time.sleep(BLINK_SECONDS)

    def beep(self, pattern="ok"):
        beeps = 1 if pattern == "ok" else 3
        for _ in range(beeps):
            self._buzzer.on()
            time.sleep(0.1)
            self._buzzer.off()
            time.sleep(0.1)

    def signal_granted(self):
        self.beep("ok")
        self.led_green(True)

    def signal_denied(self):
        self.led_green(False)
        self.beep("fail")
        self.led_red(True)


def make(cfg):
    """Instancia o driver real dos indicadores."""
    return RealIndicators()
