"""Teclado matricial simulado."""


class MockKeypad:
    """Teclado 4x4 simulado, programável via :meth:`feed`.

    Sem entradas enfileiradas, :meth:`read_pin` devolve ``None`` — simulando
    timeout (nenhuma tecla digitada).
    """

    def __init__(self):
        self.queue = []
        self.echoes = []  # progresso reportado via ``on_change``, para inspeção

    def feed(self, *pins):
        """Enfileira PINs a serem retornados por leituras sucessivas."""
        self.queue.extend(pins)

    def reset(self):
        """Sem buffer parcial no mock; existe para igualar o driver real."""

    def read_pin(self, timeout=None, on_change=None):
        """Retorna o próximo PIN enfileirado, ou ``None`` no timeout.

        Quando há ``on_change``, reporta a digitação dígito a dígito como o
        teclado real faria, o que permite testar o eco no display sem hardware.
        """
        if not self.queue:
            return None
        pin = self.queue.pop(0)
        if on_change is not None:
            for i in range(1, len(pin) + 1):
                parcial = pin[:i]
                self.echoes.append(parcial)
                on_change(parcial)
            on_change("")  # confirmação com '#' limpa a linha
        return pin


def make(cfg):
    """Cria o teclado simulado."""
    return MockKeypad()
