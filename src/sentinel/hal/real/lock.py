"""Driver real da fechadura solenoide via relé (gpiozero)."""

import time

# Pino BCM do relé (ajustar conforme a montagem física).
RELAY_PIN = 26


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
