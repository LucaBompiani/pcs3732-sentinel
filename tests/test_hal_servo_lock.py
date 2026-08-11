import dataclasses

from src.sentinel.config import load_config
from src.sentinel.hal.factory import build_hal
from src.sentinel.hal.mock.servo_lock import LOCKED_ANGLE, UNLOCKED_ANGLE

CFG = load_config()
CFG_SERVO = dataclasses.replace(CFG, lock_type="servo")


def test_padrao_usa_fechadura_solenoide():
    hal = build_hal(CFG)
    assert type(hal.lock).__name__ == "MockLock"


def test_lock_type_servo_seleciona_o_servo():
    hal = build_hal(CFG_SERVO)
    assert type(hal.lock).__name__ == "MockServoLock"


def test_servo_comeca_travado():
    hal = build_hal(CFG_SERVO)
    assert hal.lock.is_locked() is True
    assert hal.lock.angles == [LOCKED_ANGLE]


def test_servo_gira_e_retorna_ao_angulo_travado():
    hal = build_hal(CFG_SERVO)

    hal.lock.unlock(CFG_SERVO.relay_seconds)

    assert hal.lock.unlocks == [CFG_SERVO.relay_seconds]
    assert hal.lock.angles == [LOCKED_ANGLE, UNLOCKED_ANGLE, LOCKED_ANGLE]
    assert hal.lock.is_locked() is True
