"""Câmera simulada."""


class MockFrame:
    """Quadro simulado que carrega apenas a identidade (rótulo) capturada."""

    def __init__(self, label=None):
        self.label = label


class MockCamera:
    """Câmera simulada, programável via :meth:`see`.

    Em vez de pixels, produz um :class:`MockFrame` cujo ``label`` representa
    quem está diante da câmera — consumido pelo reconhecedor mock.
    """

    def __init__(self):
        self.next_label = None
        self.started = False

    def see(self, label):
        """Define a identidade que o próximo :meth:`capture` irá reportar."""
        self.next_label = label

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def capture(self):
        """Retorna um :class:`MockFrame` com o rótulo programado."""
        return MockFrame(label=self.next_label)


def make(cfg):
    """Cria a câmera simulada."""
    return MockCamera()
