"""Máquina de estados do fluxo de autenticação: VIGIA -> FATOR1 -> FATOR2 -> ATUA/NEGA.

Ver docs/diagramas/fluxo_mfa.d2. Os dois fatores são obrigatórios em série (E).
"""

from sentinel.infra.events_repository import log_event
from sentinel.services import face_recognition, second_factor
from sentinel.services.decision import authorize


def run_access_attempt(conn, presented_name, pin):
    fator1_username = face_recognition.recognize(conn, presented_name)
    fator1_ok = fator1_username is not None

    fator2_ok = False
    if fator1_ok:
        fator2_ok = second_factor.verify(conn, fator1_username, pin)

    autorizado = authorize(fator1_username, fator2_ok)
    resultado = "AUTORIZADO" if autorizado else "NEGADO"

    log_event(
        conn,
        username=fator1_username,
        fator1_ok=fator1_ok,
        fator2_ok=fator2_ok,
        resultado=resultado,
    )

    return autorizado, fator1_ok, fator2_ok
