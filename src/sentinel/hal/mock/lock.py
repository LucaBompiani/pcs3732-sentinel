"""Fechadura (relé) simulada."""


class MockLock:
    """Fechadura solenoide simulada, iniciando TRAVADA (fail-secure, RNF03).

    Cada acionamento registra em ``unlocks`` o tempo solicitado. Como os testes
    não devem depender de espera real, após registrar o pulso a fechadura
    retorna imediatamente ao estado travado — modelando o retorno automático ao
    estado seguro.
    """

    def __init__(self):
        self.locked = True
        self.unlocks = []

    def unlock(self, seconds):
        """Registra a liberação por ``seconds`` e re-trava (estado seguro)."""
        self.unlocks.append(seconds)
        self.locked = True

    def lock(self):
        """Força o travamento."""
        self.locked = True

    def is_locked(self):
        return self.locked


def make(cfg):
    """Cria a fechadura simulada."""
    return MockLock()
