"""Interface de linha de comando do Sentinel.

Com backend ``mock`` (padrão) roda em qualquer PC; com ``SENTINEL_BACKEND=real``
aciona os drivers do Raspberry Pi. A opção de ciclo por hardware exercita o
mesmo fluxo em ambos os casos.
"""

from sentinel.app.state_machine import (
    run_access_attempt,
    run_access_cycle,
    run_enrollment,
)
from sentinel.config import load_config
from sentinel.hal.factory import build_hal
from sentinel.infra.db import connect
from sentinel.infra.users_repository import create_user, user_exists

MENU = """
1) Cadastrar usuario (Fator 1 + Fator 2)
2) Simular tentativa de acesso (entrada manual)
3) Ciclo de acesso via hardware (HAL)
4) Cadastro via hardware (HAL)
5) Sair
"""


def cadastrar(conn):
    """Cadastro simples por teclado (nome + PIN + cartão opcional)."""
    username = input("Nome do usuario: ").strip()
    if user_exists(conn, username):
        print(f"Usuario '{username}' ja cadastrado.")
        return
    pin = input("PIN (Fator 2): ").strip()
    card_uid = input("UID do cartao RFID (Fator 2, vazio = sem cartao): ").strip() or None
    create_user(conn, username, pin, card_uid=card_uid)
    print(f"Usuario '{username}' cadastrado.")


def simular_acesso(conn):
    """Simula uma tentativa fornecendo os fatores manualmente."""
    presented_name = input(
        "Nome reconhecido pela camera (Fator 1, mock - vazio = ninguem): "
    ).strip() or None
    pin = input("PIN informado (Fator 2, vazio = nenhum): ").strip() or None
    card_uid = input("UID do cartao (Fator 2, vazio = nenhum): ").strip() or None

    autorizado, fator1_ok, fator2_ok = run_access_attempt(
        conn, presented_name, pin, card_uid=card_uid
    )

    print(f"Fator 1 (facial): {'OK' if fator1_ok else 'FALHOU'}")
    print(f"Fator 2 (PIN/RFID): {'OK' if fator2_ok else 'FALHOU'}")
    print("ACESSO AUTORIZADO" if autorizado else "ACESSO NEGADO")


def ciclo_hardware(conn, hal, cfg):
    """Executa o fluxo de acesso dirigido pelo HAL."""
    autorizado, _, _ = run_access_cycle(conn, hal, cfg)
    print("ACESSO AUTORIZADO" if autorizado else "ACESSO NEGADO")


def cadastro_hardware(conn, hal, cfg):
    """Executa o fluxo de enrolamento dirigido pelo HAL."""
    username = input("Nome do novo usuario: ").strip()
    ok = run_enrollment(conn, hal, cfg, username)
    print("CADASTRO CONCLUIDO" if ok else "CADASTRO ABORTADO")


def main():
    cfg = load_config()
    conn = connect(cfg.db_path)
    hal = build_hal(cfg)
    try:
        while True:
            print(MENU)
            opcao = input("Escolha: ").strip()
            if opcao == "1":
                cadastrar(conn)
            elif opcao == "2":
                simular_acesso(conn)
            elif opcao == "3":
                ciclo_hardware(conn, hal, cfg)
            elif opcao == "4":
                cadastro_hardware(conn, hal, cfg)
            elif opcao == "5":
                break
            else:
                print("Opcao invalida.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
