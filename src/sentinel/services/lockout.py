"""Bloqueio temporário por tentativas malsucedidas do Fator 2 (RF10).

Limita ataques de força bruta contra o segundo fator: após ``cfg.max_failures``
falhas seguidas, o usuário fica impedido de tentar novamente por
``cfg.lockout_seconds``, mesmo que apresente o fator correto. O bloqueio é por
usuário — os demais continuam podendo acessar.

O prazo é persistido como timestamp UTC (relógio de parede) e não como tempo
monotônico, para que o bloqueio sobreviva a um reinício do sistema (RNF03).
"""

from datetime import datetime, timedelta, timezone

from sentinel.infra.users_repository import get_lockout, set_lockout


def _now(now):
    return now or datetime.now(timezone.utc)


def is_locked(conn, username, now=None):
    """Indica se o usuário está sob bloqueio ativo neste instante.

    Args:
        conn: Conexão SQLite.
        username: Usuário identificado pelo Fator 1.
        now: Instante de referência; se ``None``, o horário atual em UTC.

    Returns:
        ``True`` enquanto houver bloqueio vigente; ``False`` se não houver ou
        se ele já tiver expirado.
    """
    state = get_lockout(conn, username)
    if state is None:
        return False
    _, locked_until = state
    if locked_until is None:
        return False
    return _now(now) < datetime.fromisoformat(locked_until)


def register_failure(conn, username, cfg, now=None):
    """Contabiliza uma falha do Fator 2, bloqueando ao atingir o limite.

    Ao atingir ``cfg.max_failures`` falhas seguidas, grava o fim do bloqueio e
    zera o contador — de modo que, expirado o prazo, o usuário recomeça com o
    orçamento completo de tentativas.

    Returns:
        ``True`` se esta falha disparou o bloqueio.
    """
    state = get_lockout(conn, username)
    if state is None:
        return False

    fail_count = state[0] + 1
    if fail_count >= cfg.max_failures:
        until = _now(now) + timedelta(seconds=cfg.lockout_seconds)
        set_lockout(conn, username, 0, until.isoformat())
        return True

    set_lockout(conn, username, fail_count, None)
    return False


def reset_failures(conn, username):
    """Limpa contador e bloqueio após uma autenticação bem-sucedida."""
    set_lockout(conn, username, 0, None)
