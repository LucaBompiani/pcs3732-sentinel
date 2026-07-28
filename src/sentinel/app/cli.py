from sentinel.infra.db import connect
from sentinel.infra.users_repository import create_user, user_exists
from sentinel.app.state_machine import run_access_attempt

DB_PATH = "sentinel.db"

MENU = """
1) Cadastrar usuario (Fator 1 + Fator 2)
2) Simular tentativa de acesso
3) Sair
"""


def cadastrar(conn):
    username = input("Nome do usuario: ").strip()
    if user_exists(conn, username):
        print(f"Usuario '{username}' ja cadastrado.")
        return
    pin = input("PIN (Fator 2): ").strip()
    create_user(conn, username, pin)
    print(f"Usuario '{username}' cadastrado.")


def simular_acesso(conn):
    presented_name = input(
        "Nome reconhecido pela camera (Fator 1, mock - vazio = ninguem reconhecido): "
    ).strip() or None
    pin = input("PIN informado (Fator 2): ").strip()

    autorizado, fator1_ok, fator2_ok = run_access_attempt(conn, presented_name, pin)

    print(f"Fator 1 (facial): {'OK' if fator1_ok else 'FALHOU'}")
    print(f"Fator 2 (PIN): {'OK' if fator2_ok else 'FALHOU'}")
    print("ACESSO AUTORIZADO" if autorizado else "ACESSO NEGADO")


def main():
    conn = connect(DB_PATH)
    while True:
        print(MENU)
        opcao = input("Escolha: ").strip()
        if opcao == "1":
            cadastrar(conn)
        elif opcao == "2":
            simular_acesso(conn)
        elif opcao == "3":
            break
        else:
            print("Opcao invalida.")
    conn.close()


if __name__ == "__main__":
    main()
