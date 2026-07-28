"""Fator 2 (mock): verificação de PIN.

POC da Semana 1 — teclado/RFID real ainda não escolhido (ver docs/relatorio.md
seção 3). PIN digitado via CLI simula a leitura de infra/gpio.
"""

from sentinel.infra.users_repository import verify_pin


def verify(conn, username, pin):
    return verify_pin(conn, username, pin)
