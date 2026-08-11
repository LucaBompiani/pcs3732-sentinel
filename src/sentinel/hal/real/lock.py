"""Driver real da fechadura solenoide via relé (gpiozero)."""

import time

# Pino BCM do relé da Freenove Projects Board (Tutorial, cap. 12 "Relay & LED").
#
# CONFLITO: este pino é compartilhado com o buzzer ativo (Tutorial, pág. 41,
# nota 3: "Active buzzer and relay must NOT be used at the same time"). Usar
# SENTINEL_LOCK_TYPE=solenoid exige mover o buzzer para o passivo (GPIO 4) em
# :mod:`sentinel.hal.real.indicators`. Com o atuador padrão da montagem atual
# (servo, GPIO 18) não há conflito.
RELAY_PIN = 12


class RealLock:
    """Fechadura via ``gpiozero.OutputDevice`` em modo fail-secure (RNF03).

    ``active_high=False`` e ``initial_value=False`` garantem que, na energização
    e após falta de energia, o relé fique desacionado — fechadura TRAVADA.
    """

    def __init__(self, pin=RELAY_PIN):
        from gpiozero import OutputDevice

        self._relay = OutputDevice(pin, active_high=False, initial_value=False)

    def unlock(self, seconds):
        """Libera a fechadura por ``seconds`` e retorna ao estado travado."""
        self._relay.on()
        time.sleep(seconds)
        self._relay.off()

    def lock(self):
        self._relay.off()

    def is_locked(self):
        return not self._relay.value


def make(cfg):
    """Instancia o driver real da fechadura."""
    return RealLock()
