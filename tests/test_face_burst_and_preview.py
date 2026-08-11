"""Rajada de captura no acesso e pre-visualizacao do rosto.

A rajada existe para derrubar o falso negativo do detector Haar, que perde o
rosto por piscada ou micro-movimento. A pre-visualizacao mostra o recorte que
de fato alimenta o reconhecimento, para conferir enquadramento.
"""

import dataclasses

import pytest

from src.sentinel.app.state_machine import identify_with_retries, run_access_cycle
from src.sentinel.config import load_config
from src.sentinel.hal.factory import build_hal
from src.sentinel.infra.db import connect
from src.sentinel.infra.users_repository import create_user
from src.sentinel.services import face_preview
from src.sentinel.services.face_recognition import RealRecognizer

from tests.test_face_recognition_real import DetectorFake, Quadro, _cadastra


def _cfg(**kw):
    return dataclasses.replace(load_config(), **kw)


@pytest.fixture
def conn():
    return connect(":memory:")


class CameraSequencia:
    """Camera que entrega quadros programados, contando as capturas."""

    def __init__(self, *pessoas):
        self.pessoas = list(pessoas)
        self.capturas = 0

    def start(self):
        pass

    def stop(self):
        pass

    def capture(self):
        i = min(self.capturas, len(self.pessoas) - 1)
        self.capturas += 1
        return Quadro(self.pessoas[i], variacao=100 + self.capturas)


# ------------------------------------------------------------------- rajada

def test_para_na_primeira_captura_reconhecida(conn):
    cfg = _cfg(face_attempts=10, face_interval=0)
    rec = RealRecognizer(threshold=cfg.face_threshold, detector=DetectorFake())
    _cadastra(conn, rec, pessoa=1, username="joao")

    hal = dataclasses.replace(build_hal(cfg), camera=CameraSequencia(1))

    assert identify_with_retries(conn, hal, cfg, rec) == "joao"
    # Reconheceu de primeira: nao pode gastar os 10 quadros.
    assert hal.camera.capturas == 1


def test_recupera_quando_os_primeiros_quadros_falham(conn):
    # O caso que motiva a feature: a pessoa esta la, mas os primeiros quadros
    # nao rendem rosto (piscada, movimento). Antes isso era acesso negado.
    cfg = _cfg(face_attempts=10, face_interval=0)
    rec = RealRecognizer(threshold=cfg.face_threshold, detector=DetectorFake())
    _cadastra(conn, rec, pessoa=1, username="joao")

    hal = dataclasses.replace(
        build_hal(cfg), camera=CameraSequencia(None, None, None, 1)
    )

    assert identify_with_retries(conn, hal, cfg, rec) == "joao"
    assert hal.camera.capturas == 4


def test_esgota_as_tentativas_quando_ninguem_e_reconhecido(conn):
    cfg = _cfg(face_attempts=5, face_interval=0)
    rec = RealRecognizer(threshold=cfg.face_threshold, detector=DetectorFake())
    _cadastra(conn, rec, pessoa=1, username="joao")

    hal = dataclasses.replace(build_hal(cfg), camera=CameraSequencia(None))

    assert identify_with_retries(conn, hal, cfg, rec) is None
    assert hal.camera.capturas == 5


def test_rajada_nao_aceita_quem_nao_esta_cadastrado(conn):
    # Mais tentativas NAO podem virar permissividade: o criterio de cada quadro
    # segue o mesmo, entao um estranho continua sendo recusado nas 10.
    cfg = _cfg(face_attempts=10, face_interval=0)
    rec = RealRecognizer(threshold=cfg.face_threshold, detector=DetectorFake())
    _cadastra(conn, rec, pessoa=1, username="joao")

    hal = dataclasses.replace(build_hal(cfg), camera=CameraSequencia(2))

    assert identify_with_retries(conn, hal, cfg, rec) is None
    assert hal.camera.capturas == 10


def test_uma_tentativa_e_o_comportamento_antigo(conn):
    cfg = _cfg(face_attempts=1, face_interval=0)
    rec = RealRecognizer(threshold=cfg.face_threshold, detector=DetectorFake())
    _cadastra(conn, rec, pessoa=1, username="joao")

    hal = dataclasses.replace(build_hal(cfg), camera=CameraSequencia(None, 1))

    assert identify_with_retries(conn, hal, cfg, rec) is None
    assert hal.camera.capturas == 1


def test_ciclo_completo_autoriza_apos_quadros_falhos(conn):
    cfg = _cfg(face_attempts=10, face_interval=0)
    rec = RealRecognizer(threshold=cfg.face_threshold, detector=DetectorFake())
    _cadastra(conn, rec, pessoa=1, username="joao")
    create_user(conn, "joao", "1234")

    hal = dataclasses.replace(
        build_hal(cfg), camera=CameraSequencia(None, None, 1)
    )
    hal.keypad.feed("1234")

    autorizado, f1, f2 = run_access_cycle(conn, hal, cfg, recognizer=rec)

    assert (autorizado, f1, f2) == (True, True, True)
    assert hal.lock.unlocks == [cfg.relay_seconds]


def test_config_le_os_parametros_da_rajada(monkeypatch):
    monkeypatch.setenv("SENTINEL_FACE_ATTEMPTS", "7")
    monkeypatch.setenv("SENTINEL_FACE_INTERVAL", "0.45")
    cfg = load_config()
    assert cfg.face_attempts == 7
    assert cfg.face_interval == 0.45


# ------------------------------------------------------------ visualizacao

def _quadrado(valor, lado=8):
    return [[valor] * lado for _ in range(lado)]


def test_desenho_tem_o_tamanho_pedido():
    linhas = face_preview.render_ascii(_quadrado(128), largura=20, altura=10)
    assert len(linhas) == 10
    assert all(len(linha) == 20 for linha in linhas)


def test_preto_e_branco_usam_as_pontas_da_rampa():
    escuro = face_preview.render_ascii(_quadrado(0), largura=4, altura=2)
    claro = face_preview.render_ascii(_quadrado(255), largura=4, altura=2)
    assert escuro[0] == face_preview.RAMPA[0] * 4
    assert claro[0] == face_preview.RAMPA[-1] * 4


def test_imagem_vazia_nao_quebra():
    assert face_preview.render_ascii([]) == []
    assert face_preview.format_ascii([]) == ""


def test_moldura_inclui_o_titulo():
    texto = face_preview.format_ascii(_quadrado(128), titulo="joao", largura=8, altura=4)
    assert "joao" in texto.splitlines()[0]
    assert len(texto.splitlines()) == 6  # topo + 4 linhas + base


def test_preview_desligado_nao_devolve_callback():
    assert face_preview.make(_cfg(face_preview="off")) is None


def test_preview_ascii_escreve_na_saida():
    escrito = []
    mostrar = face_preview.make(_cfg(face_preview="ascii"), saida=escrito.append)

    mostrar(None, _quadrado(200), None, "joao")

    assert len(escrito) == 1
    assert "joao" in escrito[0]


def test_reconhecedor_exibe_o_rosto_capturado():
    vistos = []
    rec = RealRecognizer(
        threshold=0.5,
        detector=DetectorFake(),
        preview=lambda frame, rosto, caixa, rotulo: vistos.append((len(rosto), rotulo)),
    )

    rec.encode(Quadro(1), "joao")   # cadastro: rotulo e o usuario
    rec.encode(Quadro(1))           # verificacao: ainda nao se sabe quem e

    assert [rotulo for _, rotulo in vistos] == ["joao", "verificacao"]


def test_sem_rosto_nao_exibe_nada():
    vistos = []
    rec = RealRecognizer(
        threshold=0.5,
        detector=DetectorFake(),
        preview=lambda frame, rosto, caixa, rotulo: vistos.append(rotulo),
    )

    assert rec.encode(Quadro(None), "joao") is None
    assert vistos == []
