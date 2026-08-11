"""Driver real da trava por servomotor (gpiozero), para demonstração.

Alternativa ao relé + fechadura solenoide quando não há a fechadura de 12 V e
sua fonte independente: o servo faz o papel de trancar/destrancar visivelmente.

ATENÇÃO: o servo NÃO é fail-secure. Em queda de energia ele permanece no ângulo
em que estava, enquanto o relé desacionado mantém a solenoide travada (RNF03).
Por isso este atuador é apenas para demonstração; o atuador do requisito
continua sendo :mod:`sentinel.hal.real.lock`.
"""

import time

# Pino BCM do servo: GPIO 18 é o pino de PWM por hardware e o header de servo
# da placa Freenove (Tutorial, cap. 13).
SERVO_PIN = 18

# Larguras de pulso do SG90: 0.5 ms = 0°, 2.5 ms = 180° (Tutorial, cap. 13).
MIN_PULSE_WIDTH = 0.5 / 1000
MAX_PULSE_WIDTH = 2.5 / 1000

LOCKED_ANGLE = 0
UNLOCKED_ANGLE = 90

# Tempo para o servo concluir o curso antes de soltar o sinal.
TRAVEL_SECONDS = 0.5


class RealServoLock:
    """Trava por servo via ``gpiozero.AngularServo`` (import tardio)."""

    def __init__(self, pin=SERVO_PIN):
        from gpiozero import AngularServo

        self._servo = AngularServo(
            pin,
            initial_angle=LOCKED_ANGLE,
            min_angle=0,
            max_angle=180,
            min_pulse_width=MIN_PULSE_WIDTH,
            max_pulse_width=MAX_PULSE_WIDTH,
        )
        self._locked = True
        self._settle()

    def _settle(self):
        """Aguarda o curso e solta o sinal, evitando tremor e consumo à toa."""
        time.sleep(TRAVEL_SECONDS)
        self._servo.angle = None

    def unlock(self, seconds):
        """Abre por ``seconds`` e retorna ao ângulo travado."""
        self._servo.angle = UNLOCKED_ANGLE
        self._locked = False
        self._settle()
        time.sleep(seconds)
        self.lock()

    def lock(self):
        self._servo.angle = LOCKED_ANGLE
        self._locked = True
        self._settle()

    def is_locked(self):
        return self._locked


def make(cfg):
    """Instancia o driver real da trava por servo."""
    return RealServoLock()
