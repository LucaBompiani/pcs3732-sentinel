"""Testes do reconhecedor facial real (LBPH), sem camera nem OpenCV.

O detector de rosto e injetado: `RealRecognizer` recebe um objeto com
`extract(frame)`, entao a deteccao Haar (unica parte que exige cv2) e
substituida por um gerador de faces sinteticas deterministicas. Tudo o que
importa para a decisao de acesso — extracao, comparacao, limiar, cadastro —
fica coberto e roda em qualquer PC.
"""

import dataclasses
import math
import random

import pytest

from src.sentinel.app.state_machine import run_access_cycle, run_enrollment
from src.sentinel.config import load_config
from src.sentinel.hal.factory import build_hal
from src.sentinel.infra.db import connect
from src.sentinel.infra.users_repository import add_face_embedding, get_embeddings
from src.sentinel.services import face_encoding as fe
from src.sentinel.services.face_recognition import RealRecognizer

CFG = load_config()


# Ruido aplicado a cada captura, em niveis de cinza. Sem ele duas capturas da
# mesma pessoa seriam bit a bit identicas e os testes nao provariam nada: e a
# variacao entre capturas que o reconhecedor precisa tolerar.
RUIDO = 6


def _rosto(pessoa, ruido=0, variacao=0):
    """Face sintetica deterministica: manchas gaussianas caracteristicas da pessoa.

    ``variacao`` altera apenas a realizacao do ruido, simulando duas capturas
    distintas do MESMO rosto.
    """
    lado = fe.FACE_SIZE
    rnd = random.Random(pessoa)
    centros = [(rnd.randrange(lado), rnd.randrange(lado), rnd.uniform(8, 20)) for _ in range(6)]
    img = []
    for r in range(lado):
        linha = []
        for c in range(lado):
            v = 0.0
            for cr, cc, sig in centros:
                v += 255 * math.exp(-((r - cr) ** 2 + (c - cc) ** 2) / (2 * sig * sig))
            if ruido:
                semente = (pessoa, variacao, r, c)
                v += random.Random(hash(semente)).uniform(-ruido, ruido)
            linha.append(max(0, min(255, int(v))))
        img.append(linha)
    return img


class Quadro:
    """Quadro de teste: carrega a pessoa que esta diante da camera."""

    def __init__(self, pessoa, ruido=RUIDO, variacao=0):
        self.pessoa = pessoa
        self.ruido = ruido
        self.variacao = variacao
        self.label = None  # o reconhecedor real nao deve olhar para isto


class DetectorFake:
    """Detector injetado: devolve a face da pessoa no quadro, ou None."""

    def extract(self, frame):
        if frame.pessoa is None:  # ninguem em quadro
            return None
        return _rosto(frame.pessoa, frame.ruido, frame.variacao)


class CameraFake:
    """Camera programada por sequencia de pessoas; cada captura e distinta.

    Cada elemento de ``pessoas`` e quem esta diante da camera naquela captura
    (``None`` = ninguem). A ultima se repete quando a sequencia acaba.
    """

    def __init__(self, *pessoas):
        self.pessoas = list(pessoas)
        self.n = 0
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def capture(self):
        i = min(self.n, len(self.pessoas) - 1)
        self.n += 1
        return Quadro(self.pessoas[i], variacao=self.n)


def _com_camera(hal, camera):
    """Troca a camera do HAL (``Hal`` e um dataclass congelado)."""
    return dataclasses.replace(hal, camera=camera)


@pytest.fixture
def conn():
    return connect(":memory:")


@pytest.fixture
def rec():
    return RealRecognizer(threshold=CFG.face_threshold, detector=DetectorFake())


def _cadastra(conn, rec, pessoa, username, amostras=3):
    for i in range(amostras):
        blob = rec.encode(Quadro(pessoa, variacao=i), username)
        assert blob is not None
        add_face_embedding(conn, username, blob)


# --------------------------------------------------------------- encode

def test_encode_produz_vetor_lbph_e_nao_o_nome(rec):
    blob = rec.encode(Quadro(1), "joao")
    assert len(blob) == fe.DIM * 4
    assert fe.decode(blob) is not None
    assert b"joao" not in blob  # RNF04: nenhum dado identificavel no vetor


def test_encode_sem_rosto_devolve_none(rec):
    assert rec.encode(Quadro(None), "joao") is None


# ------------------------------------------------------------- identify

def test_identifica_pessoa_cadastrada(conn, rec):
    _cadastra(conn, rec, pessoa=1, username="joao")
    assert rec.identify(conn, Quadro(1, variacao=99)) == "joao"


def test_nao_identifica_pessoa_nao_cadastrada(conn, rec):
    _cadastra(conn, rec, pessoa=1, username="joao")
    assert rec.identify(conn, Quadro(2)) is None


def test_escolhe_o_usuario_certo_entre_varios(conn, rec):
    _cadastra(conn, rec, pessoa=1, username="joao")
    _cadastra(conn, rec, pessoa=2, username="maria")
    _cadastra(conn, rec, pessoa=3, username="ana")

    assert rec.identify(conn, Quadro(2, variacao=99)) == "maria"
    assert rec.identify(conn, Quadro(3, variacao=99)) == "ana"


def test_sem_rosto_no_quadro_devolve_none(conn, rec):
    _cadastra(conn, rec, pessoa=1, username="joao")
    assert rec.identify(conn, Quadro(None)) is None


def test_base_vazia_devolve_none(conn, rec):
    assert rec.identify(conn, Quadro(1)) is None


# ------------------------------------------------------------- limiar

def test_limiar_zero_recusa_todos(conn):
    rigoroso = RealRecognizer(threshold=0.0, detector=DetectorFake())
    _cadastra(conn, rigoroso, pessoa=1, username="joao")
    assert rigoroso.identify(conn, Quadro(1, variacao=99)) is None


def test_limiar_maximo_aceita_o_mais_proximo(conn):
    # Com limiar 2.0 (maximo da metrica) nada e recusado: serve para provar que
    # a busca escolhe o vizinho mais proximo, separada da decisao do limiar.
    permissivo = RealRecognizer(threshold=2.0, detector=DetectorFake())
    _cadastra(conn, permissivo, pessoa=1, username="joao")
    assert permissivo.identify(conn, Quadro(2)) == "joao"


def test_margem_entre_mesma_pessoa_e_pessoa_diferente(conn, rec):
    # Documenta a separacao que sustenta o limiar padrao: a distancia para a
    # mesma pessoa precisa ficar bem abaixo da distancia para outra.
    _cadastra(conn, rec, pessoa=1, username="joao")
    amostras = [fe.decode(b) for _, b in get_embeddings(conn)]

    mesma = fe.decode(rec.encode(Quadro(1, variacao=99)))
    outra = fe.decode(rec.encode(Quadro(2)))

    d_mesma = min(fe.chi_square(mesma, a) for a in amostras)
    d_outra = min(fe.chi_square(outra, a) for a in amostras)

    assert d_mesma < CFG.face_threshold < d_outra


# ------------------------------------------------ compatibilidade retroativa

def test_amostras_antigas_em_texto_sao_ignoradas(conn, rec):
    # Bases criadas antes desta implementacao guardavam o nome do usuario no
    # lugar do vetor. Devem ser puladas, nao quebrar o reconhecimento.
    add_face_embedding(conn, "legado", b"legado")
    _cadastra(conn, rec, pessoa=1, username="joao")

    assert rec.identify(conn, Quadro(1, variacao=99)) == "joao"


def test_base_apenas_com_amostras_antigas_nao_reconhece(conn, rec):
    add_face_embedding(conn, "legado", b"legado")
    assert rec.identify(conn, Quadro(1)) is None


# --------------------------------------------------- cadastro e ciclo completo

def test_cadastro_grava_vetores_reais(conn, rec):
    hal = _com_camera(build_hal(CFG), CameraFake(1))
    hal.keypad.feed(CFG.master_pin, "1234")

    assert run_enrollment(conn, hal, CFG, "joao", recognizer=rec) is True

    amostras = get_embeddings(conn)
    assert len(amostras) == CFG.face_samples
    for username, blob in amostras:
        assert username == "joao"
        assert fe.decode(blob) is not None  # vetor de verdade, nao texto


def test_cadastro_sem_rosto_e_negado(conn, rec):
    hal = _com_camera(build_hal(CFG), CameraFake(None))  # ninguem diante da camera
    hal.keypad.feed(CFG.master_pin, "1234")

    assert run_enrollment(conn, hal, CFG, "joao", recognizer=rec) is False
    assert get_embeddings(conn) == []
    resultados = [r for r, _ in conn.execute("SELECT resultado, tipo FROM events")]
    assert "CADASTRO_NEGADO" in resultados


def test_cadastro_tolera_quadros_sem_rosto_no_meio(conn, rec):
    # Alterna quadros vazios e validos: a coleta descarta os vazios e ainda
    # assim junta o numero pedido de amostras, sem abortar o cadastro.
    sequencia = []
    for _ in range(CFG.face_samples):
        sequencia.extend([None, 1])
    hal = _com_camera(build_hal(CFG), CameraFake(*sequencia))
    hal.keypad.feed(CFG.master_pin, "1234")

    assert run_enrollment(conn, hal, CFG, "joao", recognizer=rec) is True
    assert len(get_embeddings(conn)) == CFG.face_samples


def test_ciclo_de_acesso_completo_com_face_real(conn, rec):
    hal = _com_camera(build_hal(CFG), CameraFake(1))
    hal.keypad.feed(CFG.master_pin, "1234")
    assert run_enrollment(conn, hal, CFG, "joao", recognizer=rec) is True

    # Mesma pessoa (outra captura) + PIN correto: autorizado, fechadura abre.
    hal2 = _com_camera(build_hal(CFG), CameraFake(1))
    hal2.keypad.feed("1234")
    autorizado, f1, f2 = run_access_cycle(conn, hal2, CFG, recognizer=rec)

    assert (autorizado, f1, f2) == (True, True, True)
    assert hal2.lock.unlocks == [CFG.relay_seconds]


def test_ciclo_de_acesso_nega_desconhecido(conn, rec):
    hal = _com_camera(build_hal(CFG), CameraFake(1))
    hal.keypad.feed(CFG.master_pin, "1234")
    assert run_enrollment(conn, hal, CFG, "joao", recognizer=rec) is True

    # Outra pessoa, mesmo sabendo o PIN: barrada ainda no Fator 1.
    hal2 = _com_camera(build_hal(CFG), CameraFake(2))
    hal2.keypad.feed("1234")
    autorizado, f1, f2 = run_access_cycle(conn, hal2, CFG, recognizer=rec)

    assert (autorizado, f1, f2) == (False, False, False)
    assert hal2.lock.unlocks == []
