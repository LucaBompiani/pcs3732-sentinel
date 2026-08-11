"""Driver real da câmera CSI (picamera2)."""


class RealCamera:
    """Câmera Raspberry Pi via ``picamera2`` (import tardio)."""

    def __init__(self):
        from picamera2 import Picamera2

        self._cam = Picamera2()
        self._started = False

    def start(self):
        if not self._started:
            self._cam.start()
            self._started = True

    def stop(self):
        if self._started:
            self._cam.stop()
            self._started = False

    def capture(self):
        """Captura um quadro como array numpy (RGB)."""
        self.start()
        return self._cam.capture_array()


def make(cfg):
    """Instancia o driver real da câmera."""
    return RealCamera()
