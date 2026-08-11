"""Botão de cadastro simulado."""


class MockEnrollButton:
    """Botão físico de enrolamento simulado, programável via :meth:`feed`."""

    def __init__(self, default=True):
        self.default = default
        self.queue = []

    def feed(self, *values):
        """Enfileira respostas de pressionamento a retornar em ordem."""
        self.queue.extend(values)

    def wait_for_press(self, timeout=None):
        """Retorna a próxima resposta enfileirada, ou o valor padrão."""
        if self.queue:
            return self.queue.pop(0)
        return self.default


def make(cfg):
    """Cria o botão de cadastro simulado."""
    return MockEnrollButton()
