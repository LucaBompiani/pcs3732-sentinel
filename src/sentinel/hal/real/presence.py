"""Driver real do sensor de presença PIR (gpiozero)."""

# Pino BCM do sensor PIR HC-SR501 (Tutorial, cap. 22 "Infrared Motion Sensor").
# O PIR não é soldado na Projects Board: é módulo externo, ligado ao External
# Port. GPIO 4 NÃO serve — é o buzzer passivo da placa (Tutorial, cap. 6).
PIR_PIN = 24


class RealPresence:
    """Sensor PIR via ``gpiozero.MotionSensor`` (import tardio)."""

    def __init__(self, pin=PIR_PIN):
        from gpiozero import MotionSensor

        self._sensor = MotionSensor(pin)

    def wait_for_presence(self, timeout=None):
        return self._sensor.wait_for_motion(timeout=timeout)

    def is_present(self):
        return bool(self._sensor.motion_detected)


def make(cfg):
    """Instancia o driver real do PIR."""
    return RealPresence()
