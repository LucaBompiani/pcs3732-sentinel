"""Teclado matricial simulado."""


class MockKeypad:
    """Teclado 4x4 simulado, programável via :meth:`feed`.

    Sem entradas enfileiradas, :meth:`read_pin` devolve ``None`` — simulando
    timeout (nenhuma tecla digitada).
    """

    def __init__(self):
        self.queue = []

    def feed(self, *pins):
        """Enfileira PINs a serem retornados por leituras sucessivas."""
        self.queue.extend(pins)

    def read_pin(self, timeout=None):
        """Retorna o próximo PIN enfileirado, ou ``None`` no timeout."""
        if self.queue:
            return self.queue.pop(0)
        return None


def make(cfg):
    """Cria o teclado simulado."""
    return MockKeypad()
