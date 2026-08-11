"""Sensor de presença simulado."""


class MockPresence:
    """Sensor PIR simulado, programável via :meth:`feed`.

    Por padrão reporta presença imediatamente, o que mantém os testes
    determinísticos sem espera real.
    """

    def __init__(self, default=True):
        self.default = default
        self.queue = []

    def feed(self, *values):
        """Enfileira respostas de presença a serem retornadas em ordem."""
        self.queue.extend(values)

    def wait_for_presence(self, timeout=None):
        """Retorna a próxima resposta enfileirada, ou o valor padrão."""
        if self.queue:
            return self.queue.pop(0)
        return self.default

    def is_present(self):
        """Leitura instantânea (usa a mesma fonte de dados programada)."""
        return self.wait_for_presence(0)


def make(cfg):
    """Cria o sensor de presença simulado."""
    return MockPresence()
