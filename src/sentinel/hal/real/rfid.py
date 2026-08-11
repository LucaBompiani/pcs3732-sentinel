"""Driver real do leitor RFID MFRC522 (SPI)."""

import time


class RealRfid:
    """Leitor MFRC522 via ``mfrc522.SimpleMFRC522`` (import tardio)."""

    def __init__(self):
        from mfrc522 import SimpleMFRC522

        self._reader = SimpleMFRC522()

    def read_uid(self, timeout=None):
        """Aguarda um cartão e retorna o UID em hexadecimal, ou ``None``.

        Faz sempre ao menos uma leitura, mesmo com ``timeout=0``: o ciclo de
        acesso alterna teclado e RFID com timeout zero, e sair sem consultar o
        leitor faria o cartão nunca ser detectado.
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        primeira_leitura = True
        while primeira_leitura or deadline is None or time.monotonic() < deadline:
            primeira_leitura = False
            uid = self._reader.read_id_no_block()
            if uid is not None:
                return format(uid, "x")
            if deadline is not None and time.monotonic() >= deadline:
                break
            time.sleep(0.1)
        return None


def make(cfg):
    """Instancia o driver real do leitor RFID."""
    return RealRfid()
