"""Display LCD simulado."""


class MockDisplay:
    """LCD1602 simulado que acumula as mensagens exibidas em ``buffer``."""

    def __init__(self):
        self.buffer = []

    def show(self, line1, line2=""):
        """Registra um par de linhas exibidas."""
        self.buffer.append((line1, line2))

    def clear(self):
        """Registra uma limpeza de tela."""
        self.buffer.append(("", ""))


def make(cfg):
    """Cria o display simulado."""
    return MockDisplay()
