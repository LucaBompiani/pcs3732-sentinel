"""Detecção e normalização do rosto no quadro da câmera (OpenCV).

Etapa anterior ao :mod:`sentinel.services.face_encoding`: recebe o quadro cru
da câmera e devolve APENAS a região do rosto, em tons de cinza, equalizada e
reamostrada para um tamanho fixo. A imagem nunca é persistida — segue direto
para virar histograma (RNF04/LGPD).

Usa o classificador Haar em cascata que acompanha o OpenCV base
(``haarcascade_frontalface_default.xml``), não os módulos *contrib*.
"""

from sentinel.services.face_encoding import FACE_SIZE

# Parâmetros do detector Haar.
#   scale_factor: quanto a janela cresce a cada passagem. 1.1 é o compromisso
#     usual entre custo e chance de perder rostos entre escalas.
#   min_neighbors: quantas detecções vizinhas confirmam uma região. Valores
#     baixos geram falsos positivos; 5 é o padrão recomendado.
SCALE_FACTOR = 1.1
MIN_NEIGHBORS = 5

# Rosto menor que isto é ruído ou alguém longe demais para autenticar.
MIN_FACE_PIXELS = 60


class HaarFaceDetector:
    """Detector de rosto frontal via cascata de Haar (import tardio de ``cv2``)."""

    def __init__(self, size=FACE_SIZE):
        import cv2  # import tardio: só no backend real

        self._cv2 = cv2
        self._size = size
        caminho = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self._cascade = cv2.CascadeClassifier(caminho)
        if self._cascade.empty():
            raise RuntimeError(
                f"Não foi possível carregar a cascata de Haar em {caminho}. "
                "Instale o pacote python3-opencv completo."
            )

    def _to_gray(self, frame):
        """Converte o quadro para tons de cinza, seja ele RGB, RGBA ou já cinza.

        A picamera2 entrega RGB (3 canais) ou XRGB8888 (4 canais) conforme a
        configuração, então os dois casos precisam ser aceitos.
        """
        cv2 = self._cv2
        canais = frame.shape[2] if getattr(frame, "ndim", 0) == 3 else 1
        if canais == 1:
            return frame
        if canais == 4:
            return cv2.cvtColor(frame, cv2.COLOR_RGBA2GRAY)
        return cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

    def extract(self, frame):
        """Recorta e normaliza o maior rosto do quadro.

        Args:
            frame: Quadro da câmera (array numpy da picamera2).

        Returns:
            Lista de linhas de inteiros 0..255, ``FACE_SIZE`` x ``FACE_SIZE``,
            ou ``None`` se nenhum rosto for encontrado.
        """
        cv2 = self._cv2
        gray = self._to_gray(frame)

        faces = self._cascade.detectMultiScale(
            gray,
            scaleFactor=SCALE_FACTOR,
            minNeighbors=MIN_NEIGHBORS,
            minSize=(MIN_FACE_PIXELS, MIN_FACE_PIXELS),
        )
        if len(faces) == 0:
            return None

        # Com mais de uma pessoa no quadro, o maior rosto é o mais próximo da
        # câmera — quem está de fato tentando entrar.
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        recorte = gray[y : y + h, x : x + w]

        recorte = cv2.resize(recorte, (self._size, self._size))
        # Equalizar o histograma reduz o efeito de iluminação frontal forte ou
        # fraca antes de extrair as texturas.
        recorte = cv2.equalizeHist(recorte)

        return recorte.tolist()


def make(cfg=None):
    """Instancia o detector real."""
    return HaarFaceDetector()
