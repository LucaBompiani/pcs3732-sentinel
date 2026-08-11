import dataclasses

import pytest

from src.sentinel.app.state_machine import run_access_cycle
from src.sentinel.config import load_config
from src.sentinel.hal.factory import build_hal
from src.sentinel.infra.db import connect
from src.sentinel.infra.users_repository import create_user

CFG = load_config()


@pytest.fixture
def conn():
    c = connect(":memory:")
    create_user(c, "joao", "1234", card_uid="CARD-JOAO")
    return c


def test_granted_path_actuates_lock_and_green(conn):
    hal = build_hal(CFG)
    hal.camera.see("joao")  # Fator 1 reconhece
    hal.keypad.feed("1234")  # Fator 2 correto

    autorizado, f1, f2 = run_access_cycle(conn, hal, CFG)

    assert (autorizado, f1, f2) == (True, True, True)
    assert hal.lock.unlocks == [CFG.relay_seconds]  # RF06
    assert "granted" in hal.indicators.events
    assert any("Bem-vindo" in line for line, _ in hal.display.buffer)


def test_granted_with_rfid_card(conn):
    hal = build_hal(CFG)
    hal.camera.see("joao")
    hal.rfid.feed("CARD-JOAO")  # segundo fator via cartao

    autorizado, _, f2 = run_access_cycle(conn, hal, CFG)

    assert autorizado is True and f2 is True
    assert hal.lock.unlocks == [CFG.relay_seconds]


def test_denied_wrong_pin_keeps_locked(conn):
    hal = build_hal(CFG)
    hal.camera.see("joao")
    hal.keypad.feed("0000")  # PIN errado

    autorizado, f1, f2 = run_access_cycle(conn, hal, CFG)

    assert autorizado is False and f1 is True and f2 is False  # RF07
    assert hal.lock.unlocks == []  # fechadura permanece travada
    assert hal.lock.is_locked() is True
    assert "denied" in hal.indicators.events


def test_face_not_recognized_skips_second_factor(conn):
    hal = build_hal(CFG)
    hal.camera.see("desconhecido")  # nao cadastrado
    hal.keypad.feed("1234")  # nao deve ser consumido

    autorizado, f1, f2 = run_access_cycle(conn, hal, CFG)

    assert (autorizado, f1, f2) == (False, False, False)
    assert hal.lock.unlocks == []
    # RF04: segundo fator nao solicitado -> PIN permanece na fila
    assert hal.keypad.read_pin(0) == "1234"


def test_blocked_user_skips_second_factor(conn):
    """RF10: usuario bloqueado nem chega a ter o Fator 2 solicitado."""
    cfg = dataclasses.replace(CFG, max_failures=1, lockout_seconds=60.0)
    hal = build_hal(cfg)
    hal.camera.see("joao")
    hal.keypad.feed("0000", "1234")  # errado, depois correto

    run_access_cycle(conn, hal, cfg)  # 1a falha ja bloqueia
    autorizado, f1, f2 = run_access_cycle(conn, hal, cfg)

    assert (autorizado, f1, f2) == (False, True, False)
    assert hal.lock.unlocks == []
    assert hal.lock.is_locked() is True
    assert any("bloqueado" in line.lower() for line, _ in hal.display.buffer)
    # PIN correto permanece na fila: o Fator 2 nao foi solicitado
    assert hal.keypad.read_pin(0) == "1234"


def test_second_factor_timeout_denies(conn):
    cfg = dataclasses.replace(CFG, factor2_timeout=0.0)
    hal = build_hal(cfg)
    hal.camera.see("joao")
    # nenhum PIN/cartao apresentado -> timeout

    autorizado, f1, f2 = run_access_cycle(conn, hal, cfg)

    assert autorizado is False and f1 is True and f2 is False
    assert hal.lock.unlocks == []
