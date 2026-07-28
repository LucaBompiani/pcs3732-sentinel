"""Fator 1 (mock): reconhecimento facial simulado.

POC da Semana 1 — sem câmera/dlib real. `presented_name` simula o resultado
que o pipeline de visão (infra/captura + embeddings) entregaria: o nome do
usuário identificado como mais próximo na base, ou None se ninguém bateu.
Interface pensada para ser substituída por reconhecimento real sem mudar
quem a chama (app/state_machine.py).
"""

from sentinel.infra.users_repository import user_exists


def recognize(conn, presented_name):
    if presented_name and user_exists(conn, presented_name):
        return presented_name
    return None
