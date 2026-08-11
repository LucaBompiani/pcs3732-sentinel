"""Fator 1 — reconhecimento facial.

Dois reconhecedores com o mesmo contrato:

``identify(conn, frame) -> username | None``
    Quem está diante da câmera, ou ``None`` se ninguém for reconhecido.
``encode(frame, username) -> bytes | None``
    Vetor de características a persistir no cadastro, ou ``None`` se o quadro
    não contiver rosto utilizável.

O backend ``mock`` resolve por rótulo (usado nos testes, roda em qualquer PC);
o ``real`` detecta o rosto com Haar e compara histogramas LBPH. Ver
:mod:`sentinel.services.face_encoding` para o algoritmo e o motivo de ele ser
próprio em vez do ``cv2.face``.
"""

from sentinel.infra.users_repository import get_embeddings, user_exists
from sentinel.services import face_encoding, face_preview


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

    def encode(self, frame, username):
        """Devolve um vetor simbólico: o rótulo do quadro, ou o nome cadastrado."""
        label = getattr(frame, "label", None)
        return (label or username).encode("utf-8")


class RealRecognizer:
    """Reconhecimento facial por LBPH sobre os rostos detectados na câmera.

    O cadastro guarda um vetor de características por amostra
    (:meth:`encode`); a identificação calcula o vetor do quadro atual e procura
    a amostra mais próxima em distância qui-quadrado (:meth:`identify`). Não há
    etapa de "treino" com estado: a base de amostras É o modelo, o que faz um
    novo cadastro valer imediatamente, sem retreinar.

    Somente vetores trafegam e são persistidos; a imagem do rosto é descartada
    ao fim de :meth:`encode` (RNF04/LGPD).
    """

    def __init__(self, threshold, detector=None, preview=None):
        """
        Args:
            threshold: Distância qui-quadrado máxima para aceitar uma
                identidade. Ver ``SENTINEL_FACE_THRESHOLD``.
            detector: Detector de rosto; ``None`` constrói o Haar/OpenCV sob
                demanda. Injetável para teste sem câmera nem OpenCV.
            preview: ``callable(rosto, rotulo)`` para exibir o recorte, ou
                ``None``. Ver :mod:`sentinel.services.face_preview`.
        """
        self._threshold = threshold
        self._detector = detector
        self._preview = preview

    def _get_detector(self):
        """Constrói o detector na primeira utilização (import tardio de cv2)."""
        if self._detector is None:
            from sentinel.services import face_detector

            self._detector = face_detector.make()
        return self._detector

    def encode(self, frame, username=None):
        """Extrai o vetor de características do rosto no quadro.

        Args:
            frame: Quadro cru da câmera.
            username: Ignorado; existe para igualar a assinatura do mock.

        Returns:
            ``bytes`` com o vetor LBPH, ou ``None`` se não houver rosto.
        """
        detector = self._get_detector()
        # ``detect`` devolve também a caixa do rosto, para a pré-visualização
        # desenhar o retângulo sobre a foto. Detectores que só implementam
        # ``extract`` (como os usados nos testes) continuam funcionando.
        if hasattr(detector, "detect"):
            rosto, caixa = detector.detect(frame)
        else:
            rosto, caixa = detector.extract(frame), None

        if rosto is None:
            return None
        if self._preview is not None:
            # O rótulo distingue as capturas do cadastro (nome do usuário) da
            # verificação de acesso, que ainda não sabe quem é.
            self._preview(frame, rosto, caixa, username or "verificacao")
        return face_encoding.encode(rosto)

    def identify(self, conn, frame):
        """Identifica quem está no quadro, ou ``None``.

        Devolve ``None`` tanto quando não há rosto quanto quando o rosto não se
        parece o bastante com nenhuma amostra cadastrada — os dois casos levam
        ao mesmo desfecho (acesso negado no Fator 1).
        """
        blob = self.encode(frame)
        if blob is None:
            return None
        sonda = face_encoding.decode(blob)

        melhor_usuario = None
        melhor_distancia = None
        for username, amostra in get_embeddings(conn):
            vetor = face_encoding.decode(amostra)
            if vetor is None:
                # Amostra de uma base anterior a esta implementação (guardava
                # texto). Ignorar em vez de falhar mantém a base utilizável.
                continue
            distancia = face_encoding.chi_square(sonda, vetor)
            if melhor_distancia is None or distancia < melhor_distancia:
                melhor_distancia = distancia
                melhor_usuario = username

        if melhor_usuario is None or melhor_distancia > self._threshold:
            return None
        return melhor_usuario


def get_recognizer(cfg):
    """Devolve o reconhecedor apropriado para o backend em ``cfg``."""
    if cfg.backend == "real":
        return RealRecognizer(
            threshold=cfg.face_threshold,
            preview=face_preview.make(cfg),
        )
    return MockRecognizer()
