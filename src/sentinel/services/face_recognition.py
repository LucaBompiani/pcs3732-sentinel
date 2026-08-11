"""Fator 1 — reconhecimento facial.

Mantém a função ``recognize`` (base para o mock e para os testes) e expõe
``get_recognizer(cfg)``, que devolve um reconhecedor com a interface
``identify(conn, frame) -> username | None`` conforme o backend selecionado.
"""

from sentinel.infra.users_repository import get_embeddings, user_exists


def recognize(conn, presented_name):
    """Reconhece um nome candidato contra a base de usuários (mock do Fator 1).

    Args:
        conn: Conexão SQLite.
        presented_name: Nome/identidade candidata (do quadro capturado).

    Returns:
        O ``presented_name`` se ele corresponder a um usuário cadastrado; caso
        contrário ``None``.
    """
    if presented_name and user_exists(conn, presented_name):
        return presented_name
    return None


class MockRecognizer:
    """Reconhecedor simulado: extrai o rótulo do quadro e consulta a base."""

    def identify(self, conn, frame):
        """Retorna o usuário reconhecido a partir de ``frame.label``, ou ``None``."""
        label = getattr(frame, "label", None)
        return recognize(conn, label)


class RealRecognizer:
    """Reconhecedor facial real via OpenCV LBPH (import tardio de ``cv2``).

    Stub estrutural: a extração/treino de embeddings LBPH exige câmera e a
    biblioteca OpenCV, executando apenas no Raspberry Pi. Mantém o mesmo
    contrato ``identify`` do mock. Armazena/consulta somente vetores de
    características (RNF04/LGPD), nunca imagens.
    """

    def __init__(self, confidence_threshold=70.0):
        import cv2  # import tardio: só no backend real

        self._model = cv2.face.LBPHFaceRecognizer_create()
        self._threshold = confidence_threshold
        self._trained = False
        self._labels = {}

    def _ensure_trained(self, conn):
        embeddings = get_embeddings(conn)
        if not embeddings:
            self._trained = False
            return
        # A implementação de treino a partir dos vetores persistidos é
        # concluída na etapa de testes experimentais no Pi (Semana 3).
        self._trained = True

    def identify(self, conn, frame):
        self._ensure_trained(conn)
        if not self._trained:
            return None
        raise NotImplementedError(
            "Reconhecimento LBPH real disponível apenas no Raspberry Pi "
            "com OpenCV e câmera."
        )


def get_recognizer(cfg):
    """Devolve o reconhecedor apropriado para o backend em ``cfg``."""
    if cfg.backend == "real":
        return RealRecognizer()
    return MockRecognizer()
