"""Decisão MFA: acesso só é concedido com os dois fatores válidos (E, não OU)."""


def authorize(fator1_username, fator2_ok):
    return fator1_username is not None and fator2_ok
