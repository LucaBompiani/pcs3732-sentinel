"""Leitor RFID simulado."""


class MockRfid:
    """Leitor MFRC522 simulado, programável via :meth:`feed`.

    Sem cartões enfileirados, :meth:`read_uid` devolve ``None`` — simulando
    timeout (nenhum cartão aproximado).
    """

    def __init__(self):
        self.queue = []

    def feed(self, *uids):
        """Enfileira UIDs de cartão a serem retornados em ordem."""
        self.queue.extend(uids)

    def read_uid(self, timeout=None):
        """Retorna o próximo UID enfileirado, ou ``None`` no timeout."""
        if self.queue:
            return self.queue.pop(0)
        return None


def make(cfg):
    """Cria o leitor RFID simulado."""
    return MockRfid()
