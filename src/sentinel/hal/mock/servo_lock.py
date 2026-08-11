"""Trava por servomotor simulada (modo de demonstração)."""

LOCKED_ANGLE = 0
UNLOCKED_ANGLE = 90


class MockServoLock:
    """Servo simulado, iniciando TRAVADO.

    Mantém a mesma superfície da fechadura solenoide simulada — inclusive a
    lista ``unlocks`` — para que o restante do sistema e os testes não precisem
    saber qual atuador está montado. Além disso registra em ``angles`` a
    sequência de ângulos comandados.
    """

    def __init__(self):
        self.locked = True
        self.unlocks = []
        self.angles = [LOCKED_ANGLE]

    def unlock(self, seconds):
        """Registra a liberação por ``seconds`` e retorna ao ângulo travado."""
        self.unlocks.append(seconds)
        self.angles.append(UNLOCKED_ANGLE)
        self.angles.append(LOCKED_ANGLE)
        self.locked = True

    def lock(self):
        self.angles.append(LOCKED_ANGLE)
        self.locked = True

    def is_locked(self):
        return self.locked


def make(cfg):
    """Cria o servo simulado."""
    return MockServoLock()
