"""Verificação do segundo fator: PIN ou cartão RFID (alternativos)."""

from sentinel.infra.users_repository import verify_card, verify_pin


def verify(conn, username, pin=None, *, card_uid=None):
    """Valida o segundo fator do usuário identificado no Fator 1.

    Aceita QUALQUER um dos dois fatores possuídos/conhecidos: PIN ou UID de
    cartão RFID. Ambos são checados contra o cadastro do MESMO ``username``,
    preservando o RF05 (um fator de outro usuário não é aceito).

    Args:
        conn: Conexão SQLite.
        username: Usuário identificado pelo Fator 1.
        pin: PIN informado, ou ``None`` se não apresentado.
        card_uid: UID de cartão lido, ou ``None`` se não apresentado.

    Returns:
        ``True`` se o PIN OU o cartão apresentado for válido para o usuário.
    """
    # Testes de verdade (``if pin``), não ``is not None``: no teclado matricial,
    # confirmar com ``#`` sem digitar nada devolve string vazia. Tratá-la como
    # fator apresentado permitiria autenticar com "PIN vazio" caso o usuário
    # tivesse sido cadastrado assim — um segundo fator que não é segredo algum.
    ok = False
    if pin:
        ok = ok or verify_pin(conn, username, pin)
    if card_uid:
        ok = ok or verify_card(conn, username, card_uid)
    return ok
