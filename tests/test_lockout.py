import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from src.sentinel.app.state_machine import run_access_attempt
from src.sentinel.config import load_config
from src.sentinel.infra.db import connect
from src.sentinel.infra.users_repository import (
    create_user,
    get_lockout,
    set_lockout,
)
from src.sentinel.services import lockout

# Duas falhas ja bloqueiam: mantem os testes curtos e explicitos.
CFG = dataclasses.replace(load_config(), max_failures=2, lockout_seconds=60.0)


@pytest.fixture
def conn():
    c = connect(":memory:")
    create_user(c, "joao", "1234")
    create_user(c, "maria", "5678")
    return c


def test_falha_do_fator2_incrementa_contador(conn):
    run_access_attempt(conn, CFG, "joao", "0000")

    fail_count, locked_until = get_lockout(conn, "joao")
    assert fail_count == 1
    assert locked_until is None
    assert lockout.is_locked(conn, "joao") is False


def test_falhas_seguidas_bloqueiam_usuario(conn):
    """RF10: atingido o limite, o usuario fica bloqueado."""
    run_access_attempt(conn, CFG, "joao", "0000")
    run_access_attempt(conn, CFG, "joao", "0000")

    assert lockout.is_locked(conn, "joao") is True


def test_usuario_bloqueado_nega_mesmo_com_pin_correto(conn):
    run_access_attempt(conn, CFG, "joao", "0000")
    run_access_attempt(conn, CFG, "joao", "0000")

    autorizado, fator1_ok, fator2_ok = run_access_attempt(conn, CFG, "joao", "1234")

    # Fator 1 identificou, mas o Fator 2 nem chegou a ser avaliado.
    assert (autorizado, fator1_ok, fator2_ok) == (False, True, False)


def test_bloqueio_registra_evento_proprio(conn):
    run_access_attempt(conn, CFG, "joao", "0000")
    run_access_attempt(conn, CFG, "joao", "0000")
    run_access_attempt(conn, CFG, "joao", "1234")

    resultados = [
        row[0] for row in conn.execute("SELECT resultado FROM events").fetchall()
    ]
    assert resultados == ["NEGADO", "NEGADO", "BLOQUEADO"]


def test_bloqueio_expira_sozinho(conn):
    """O bloqueio e temporario: vencido o prazo, o usuario volta a tentar."""
    vencido = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    set_lockout(conn, "joao", 0, vencido)

    assert lockout.is_locked(conn, "joao") is False

    autorizado, _, _ = run_access_attempt(conn, CFG, "joao", "1234")
    assert autorizado is True


def test_bloqueio_e_por_usuario(conn):
    run_access_attempt(conn, CFG, "joao", "0000")
    run_access_attempt(conn, CFG, "joao", "0000")

    assert lockout.is_locked(conn, "joao") is True
    assert lockout.is_locked(conn, "maria") is False

    autorizado, _, _ = run_access_attempt(conn, CFG, "maria", "5678")
    assert autorizado is True


def test_sucesso_zera_contador(conn):
    run_access_attempt(conn, CFG, "joao", "0000")
    run_access_attempt(conn, CFG, "joao", "1234")

    assert get_lockout(conn, "joao") == (0, None)

    # A falha seguinte recomeca a contagem, sem bloquear.
    run_access_attempt(conn, CFG, "joao", "0000")
    assert lockout.is_locked(conn, "joao") is False


def test_falha_do_fator1_nao_conta_para_bloqueio(conn):
    """Face nao reconhecida pode ser iluminacao/angulo, nao credencial errada."""
    for _ in range(5):
        run_access_attempt(conn, CFG, "fantasma", "1234")

    assert get_lockout(conn, "joao") == (0, None)
    assert get_lockout(conn, "fantasma") is None


def test_bloqueio_persiste_entre_conexoes(tmp_path):
    """RNF03: o prazo e relogio de parede, sobrevive a reinicio do sistema."""
    db = str(tmp_path / "sentinel.db")

    c1 = connect(db)
    create_user(c1, "joao", "1234")
    run_access_attempt(c1, CFG, "joao", "0000")
    run_access_attempt(c1, CFG, "joao", "0000")
    c1.close()

    c2 = connect(db)
    assert lockout.is_locked(c2, "joao") is True
