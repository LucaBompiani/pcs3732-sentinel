import sys

from src.sentinel.config import load_config
from src.sentinel.hal.factory import build_hal


def test_build_hal_returns_mock_devices():
    hal = build_hal(load_config())  # backend padrao = mock
    # backend mock: a fechadura simulada expõe estado inspecionável e comeca travada
    assert type(hal.lock).__name__ == "MockLock"
    assert hal.lock.is_locked() is True
    assert hal.lock.unlocks == []
    # todos os oito dispositivos presentes
    for dev in (
        hal.presence, hal.camera, hal.keypad, hal.rfid,
        hal.display, hal.indicators, hal.lock, hal.enroll_button,
    ):
        assert dev is not None


def test_importing_hal_does_not_load_pi_libraries():
    import src.sentinel.hal  # noqa: F401
    import src.sentinel.hal.factory  # noqa: F401

    build_hal(load_config())
    # Import tardio: nada de hardware do Pi deve ter sido carregado no PC.
    assert "gpiozero" not in sys.modules
    assert "picamera2" not in sys.modules
    assert "mfrc522" not in sys.modules
