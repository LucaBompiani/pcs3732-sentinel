"""Painel web: estado compartilhado, rotas e espelho do LCD.

O servidor sobe numa thread daemon com porta efemera, entao os testes exercitam
o mesmo caminho usado no Raspberry Pi, sem depender da porta 8080 estar livre.
"""

import dataclasses
import urllib.error
import urllib.request

import pytest

from src.sentinel.app import webui
from src.sentinel.app.webui import PainelState, PreviewServer
from src.sentinel.config import load_config
from src.sentinel.hal.factory import build_hal
from src.sentinel.hal.web_display import WebDisplay

# JPEG 1x1 valido, suficiente para verificar o transporte dos bytes.
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"


# ------------------------------------------------------------------- estado

def test_primeira_captura_vira_a_atual():
    st = PainelState()
    assert st.status()["versao"] == -1
    assert st.image() is None

    st.publish_image(JPEG, "joao")

    assert st.status()["versao"] == 0
    assert st.status()["rotulo"] == "joao"
    assert st.image() == JPEG


def test_status_espelha_as_duas_linhas_do_lcd():
    st = PainelState()
    st.publish_status("Fator 2", "PIN ou cartao")

    s = st.status()
    assert (s["linha1"], s["linha2"]) == ("Fator 2", "PIN ou cartao")


def test_historico_exclui_a_captura_atual():
    st = PainelState()
    for i in range(3):
        st.publish_image(JPEG, f"c{i}")

    s = st.status()
    assert s["versao"] == 2
    assert s["historico"] == [1, 0]  # mais recentes primeiro, sem a atual


def test_buffer_tem_teto_e_descarta_as_antigas():
    # Um cadastro gera 5 capturas e um acesso ate 10: sem teto, um processo de
    # longa vida acumularia imagens indefinidamente na memoria.
    st = PainelState(historico=3)
    for i in range(6):
        st.publish_image(JPEG, f"c{i}")

    assert st.image(0) is None
    assert st.image(5) == JPEG
    assert len(st.status()["historico"]) == 2


def test_rotulo_amigavel_distingue_cadastro_de_acesso():
    assert webui._rotulo_amigavel("verificacao") == "Verificação de acesso"
    assert webui._rotulo_amigavel("ana") == "Cadastro: ana"
    assert webui._rotulo_amigavel("") == "—"


# ------------------------------------------------------------------- rotas

@pytest.fixture(scope="module")
def servidor():
    srv = PreviewServer(port=0).start()
    yield srv
    srv.stop()


def _get(srv, caminho):
    url = f"http://127.0.0.1:{srv.port}{caminho}"
    with urllib.request.urlopen(url, timeout=10) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


def test_servidor_sobe_em_thread_e_resolve_a_porta(servidor):
    # Porta 0 pede uma efemera ao SO; o servidor precisa descobrir qual saiu,
    # senao o link mostrado ao usuario estaria errado.
    assert servidor.port > 0


def test_pagina_inicial_responde_html(servidor):
    status, tipo, corpo = _get(servidor, "/")
    assert status == 200
    assert "text/html" in tipo
    assert b"nicegui" in corpo.lower()


def test_captura_inexistente_devolve_404(servidor):
    with pytest.raises(urllib.error.HTTPError) as erro:
        _get(servidor, "/captura/999.jpg")
    assert erro.value.code == 404


def test_captura_publicada_e_servida_intacta(servidor):
    servidor.publish_image(JPEG, "joao")
    versao = servidor.status()["versao"]

    status, tipo, corpo = _get(servidor, f"/captura/{versao}.jpg")

    assert status == 200
    assert tipo == "image/jpeg"
    assert corpo == JPEG


def test_imagem_nao_pode_ser_cacheada(servidor):
    # A URL muda de versao a cada captura, mas o navegador reaproveitaria a
    # resposta anterior se pudesse — e o painel mostraria a foto errada.
    servidor.publish_image(JPEG, "joao")
    versao = servidor.status()["versao"]
    url = f"http://127.0.0.1:{servidor.port}/captura/{versao}.jpg"
    with urllib.request.urlopen(url, timeout=10) as r:
        assert "no-store" in r.headers.get("Cache-Control", "")


# ------------------------------------------------------- espelho do display

class DisplayFalso:
    def __init__(self):
        self.linhas = []
        self.limpezas = 0

    def show(self, line1, line2=""):
        self.linhas.append((line1, line2))

    def clear(self):
        self.limpezas += 1


def test_web_display_encaminha_para_o_lcd_e_para_o_painel():
    lcd = DisplayFalso()
    estado = PainelState()
    disp = WebDisplay(lcd, estado)

    disp.show("Bem-vindo", "ana")

    assert lcd.linhas == [("Bem-vindo", "ana")]
    s = estado.status()
    assert (s["linha1"], s["linha2"]) == ("Bem-vindo", "ana")


def test_web_display_limpa_os_dois():
    lcd = DisplayFalso()
    estado = PainelState()
    disp = WebDisplay(lcd, estado)
    disp.show("Fator 2", "PIN")

    disp.clear()

    assert lcd.limpezas == 1
    assert estado.status()["linha1"] == ""


def test_web_display_repassa_atributos_do_display_embrulhado():
    # O mock expoe ``buffer``, usado em testes de fluxo; embrulhar nao pode
    # esconder isso.
    hal = build_hal(load_config())
    disp = WebDisplay(hal.display, PainelState())
    disp.show("oi", "mundo")

    assert disp.buffer[-1] == ("oi", "mundo")


def test_ciclo_de_acesso_atualiza_o_painel():
    from src.sentinel.app.state_machine import run_access_cycle
    from src.sentinel.infra.db import connect
    from src.sentinel.infra.users_repository import create_user

    cfg = load_config()
    conn = connect(":memory:")
    create_user(conn, "joao", "1234")

    estado = PainelState()
    hal = build_hal(cfg)
    hal = dataclasses.replace(hal, display=WebDisplay(hal.display, estado))
    hal.camera.see("joao")
    hal.keypad.feed("1234")

    autorizado, _, _ = run_access_cycle(conn, hal, cfg)

    assert autorizado is True
    assert estado.status()["linha1"] == "Bem-vindo"
    assert estado.status()["linha2"] == "joao"
