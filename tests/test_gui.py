"""Janela do aplicativo (Tkinter).

Exercita a interface de verdade — constroi widgets, publica capturas e drena a
fila — mas so quando ha servidor grafico. Em maquina sem display (CI, Pi
headless) os testes sao pulados: sem DISPLAY o proprio ``tkinter.Tk()`` falha, e
isso nao e defeito do codigo.
"""

import dataclasses
import struct
import time
import zlib

import pytest

tk = pytest.importorskip("tkinter", reason="python3-tk nao instalado")

from src.sentinel.app.gui import SentinelApp
from src.sentinel.config import load_config


def _tem_display():
    try:
        raiz = tk.Tk()
    except Exception:
        return False
    raiz.destroy()
    return True


pytestmark = pytest.mark.skipif(
    not _tem_display(), reason="sem servidor grafico para abrir janela"
)


def png(largura, altura, cor=(200, 120, 60)):
    """PNG minimo valido, sem depender de Pillow nem OpenCV."""
    linhas = b"".join(b"\x00" + bytes(cor) * largura for _ in range(altura))

    def chunk(tipo, dados):
        return (
            struct.pack(">I", len(dados))
            + tipo
            + dados
            + struct.pack(">I", zlib.crc32(tipo + dados) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", largura, altura, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(linhas))
        + chunk(b"IEND", b"")
    )


@pytest.fixture
def app(tmp_path):
    raiz = tk.Tk()
    raiz.withdraw()  # nao piscar janela durante a suite
    cfg = dataclasses.replace(load_config(), db_path=str(tmp_path / "gui.db"))
    aplicacao = SentinelApp(cfg, conn=None, root=raiz)
    yield aplicacao
    raiz.destroy()


def _processar(app, ciclos=3):
    """Deixa o Tk drenar a fila de atualizacoes."""
    for _ in range(ciclos):
        app.root.update()
        time.sleep(0.12)


# ------------------------------------------------------------------ montagem

def test_janela_tem_os_botoes_que_substituem_a_cli(app):
    # Acesso, cadastro por hardware, cadastro manual, simulacao e sair.
    assert len(app._botoes) == 5
    rotulos = {b.cget("text") for b in app._botoes}
    assert rotulos == {
        "Ciclo de acesso", "Cadastrar usuário",
        "Cadastro manual", "Simular tentativa", "Sair",
    }


def test_comeca_sem_captura(app):
    assert app._imagem_atual is None
    assert app.canvas.find_withtag("captura") == ()


# -------------------------------------------------------------------- imagem

def test_captura_aparece_no_canvas(app):
    app.publish_image(png(320, 240), "ana")
    _processar(app)

    assert app._imagem_atual is not None
    assert app.canvas.find_withtag("captura") != ()


def test_imagem_grande_e_reduzida_para_caber(app):
    # A foto da camera (por exemplo 1640x1232) nao pode estourar a area.
    app.publish_image(png(960, 720), "ana")
    _processar(app)

    assert app._imagem_atual.width() <= 480
    assert app._imagem_atual.height() <= 360


def test_rotulo_distingue_cadastro_de_acesso(app):
    app.publish_image(png(64, 64), "ana")
    _processar(app)
    assert app.lbl_rotulo.cget("text") == "Cadastro: ana"

    app.publish_image(png(64, 64), "verificacao")
    _processar(app)
    assert app.lbl_rotulo.cget("text") == "Verificação de acesso"


def test_referencia_da_imagem_e_mantida(app):
    # Sem guardar a PhotoImage, o coletor do Tk a descarta e o canvas some.
    app.publish_image(png(64, 64), "ana")
    _processar(app)
    assert app._imagem_atual is not None


# ----------------------------------------------------------- espelho do LCD

def test_display_do_hal_espelha_na_janela(app):
    app.hal.display.show("Fator 2", "PIN ou cartao")
    _processar(app)

    assert app.lcd.cget("text") == "Fator 2\nPIN ou cartao"


def test_display_embrulhado_continua_escrevendo_no_dispositivo(app):
    app.hal.display.show("Bem-vindo", "ana")
    _processar(app)

    # ``buffer`` e do display simulado por baixo do espelho.
    assert app.hal.display.buffer[-1] == ("Bem-vindo", "ana")


def test_limpar_display_limpa_as_duas_linhas(app):
    app.hal.display.show("Fator 2", "PIN")
    _processar(app)
    app.hal.display.clear()
    _processar(app)

    assert app.lcd.cget("text").strip() == ""


# ---------------------------------------------------------------------- log

def test_log_registra_mensagens(app):
    app.log_line("primeira", "ok")
    app.log_line("segunda", "erro")
    _processar(app)

    conteudo = app.log.get("1.0", "end")
    assert "primeira" in conteudo and "segunda" in conteudo


def test_log_nao_cresce_sem_limite(app):
    from src.sentinel.app.gui import LOG_MAX

    for i in range(LOG_MAX + 60):
        app.log_line(f"linha {i}")
    _processar(app, ciclos=5)

    linhas = int(app.log.index("end-1c").split(".")[0])
    assert linhas <= LOG_MAX + 10


# ------------------------------------------------------------ concorrencia

def test_botoes_travam_durante_uma_operacao(app):
    app._fila.put(("ocupado", True))
    _processar(app)
    assert all(str(b["state"]) == "disabled" for b in app._botoes)

    app._fila.put(("ocupado", False))
    _processar(app)
    assert all(str(b["state"]) == "normal" for b in app._botoes)


def test_segunda_acao_e_recusada_enquanto_a_primeira_roda(app):
    # O hardware e unico: duas operacoes simultaneas disputariam camera e
    # teclado.
    app._ocupado = True
    app._executar("nao deve rodar", lambda: pytest.fail("executou apesar de ocupado"))
    _processar(app)

    assert "Aguarde" in app.log.get("1.0", "end")


def test_erro_na_acao_vai_para_o_log_sem_derrubar_a_janela(app):
    def explode():
        raise RuntimeError("falha simulada")

    app._executar("acao que falha", explode)
    _processar(app, ciclos=6)

    conteudo = app.log.get("1.0", "end")
    assert "RuntimeError" in conteudo and "falha simulada" in conteudo
    assert all(str(b["state"]) == "normal" for b in app._botoes)  # destravou


# --------------------------------------------------------- SQLite entre threads

def test_banco_pode_ser_usado_na_thread_de_trabalho(app):
    # Regressao de "SQLite objects created in a thread can only be used in that
    # same thread": a conexao nasce na thread do Tk e as acoes rodam noutra.
    from src.sentinel.infra.users_repository import create_user, user_exists

    resultado = {}

    def corpo():
        create_user(app.conn, "ana", "1234")
        resultado["existe"] = user_exists(app.conn, "ana")

    app._executar("gravar no banco", corpo)
    _processar(app, ciclos=8)

    assert resultado.get("existe") is True
    conteudo = app.log.get("1.0", "end")
    assert "ProgrammingError" not in conteudo
    assert "same thread" not in conteudo


def test_simular_tentativa_consulta_o_banco_de_outra_thread(app, monkeypatch):
    from src.sentinel.infra.users_repository import create_user

    create_user(app.conn, "joao", "1234")
    monkeypatch.setattr(app, "_perguntar", lambda titulo, msg:
                        {"Nome": "joao", "PIN": "1234"}.get(msg.split()[0], ""))

    app.acao_simular()
    _processar(app, ciclos=8)

    conteudo = app.log.get("1.0", "end")
    assert "same thread" not in conteudo
    assert "ACESSO" in conteudo


def test_cadastro_manual_verifica_duplicata_na_thread_de_trabalho(app, monkeypatch):
    from src.sentinel.infra.users_repository import create_user

    create_user(app.conn, "ana", "1111")
    monkeypatch.setattr(app, "_perguntar", lambda titulo, msg: "ana" if "Nome" in msg else "2222")

    app.acao_cadastro_manual()
    _processar(app, ciclos=8)

    conteudo = app.log.get("1.0", "end")
    assert "já existe" in conteudo
    assert "same thread" not in conteudo


# ------------------------------------------------- captura chegando na janela

def test_captura_da_camera_aparece_na_janela(app):
    """Caminho real: quadro numpy -> deteccao -> anotacao -> PNG -> canvas.

    Regressao de "a captura nao aparece": cada elo desse caminho ja falhou em
    silencio alguma vez (janela fechada, cv2 ausente, quadro em formato errado).
    """
    cv2 = pytest.importorskip("cv2", reason="OpenCV so existe no Raspberry Pi")
    np = pytest.importorskip("numpy")

    # O registro fica em sentinel.app.panel, que nunca e ponto de entrada e
    # por isso existe uma vez so (ver o docstring daquele modulo).
    from sentinel.app import panel as registro
    from src.sentinel.services import face_preview
    from src.sentinel.services.face_recognition import RealRecognizer

    class DetectorFixo:
        """Devolve recorte e caixa, como o Haar faz num rosto encontrado."""

        def detect(self, frame):
            return [[128] * 64 for _ in range(64)], (40, 30, 120, 120)

    anterior = registro.current_panel()
    registro.set_panel(app)
    try:
        cfg = dataclasses.replace(app.cfg, face_preview="gui")
        rec = RealRecognizer(
            threshold=0.5, detector=DetectorFixo(), preview=face_preview.make(cfg)
        )
        # Quadro como a picamera2 entrega: numpy RGB de 3 canais.
        quadro = np.zeros((480, 640, 3), dtype=np.uint8)

        assert rec.encode(quadro, "ana") is not None
        _processar(app, ciclos=6)
    finally:
        registro.set_panel(anterior)

    assert app.canvas.find_withtag("captura") != ()
    assert app.lbl_rotulo.cget("text") == "Cadastro: ana"
    assert "falhou" not in app.log.get("1.0", "end")


def test_sem_janela_aberta_o_preview_avisa_em_vez_de_sumir(app):
    # Rodando pela CLI o painel nao existe. Antes o preview simplesmente nao
    # publicava nada, e parecia que a captura nao tinha acontecido.
    from sentinel.app import panel as registro
    from src.sentinel.services import face_preview

    anterior = registro.current_panel()
    registro.set_panel(None)
    escrito = []
    try:
        cfg = dataclasses.replace(app.cfg, face_preview="gui")
        callback = face_preview.make(cfg, saida=escrito.append)
    finally:
        registro.set_panel(anterior)

    assert callback is not None  # cai para ascii, nao vira None
    assert any("janela" in linha for linha in escrito)


def test_janela_iniciada_como_script_fica_visivel_para_o_preview(app):
    """Regressao de "a imagem nao aparece na GUI".

    ``run-pi.sh`` executa ``python src/sentinel/app/gui.py``, o que carrega o
    arquivo com o nome ``__main__``. Um ``import sentinel.app.gui`` posterior
    carrega o MESMO arquivo de novo, sob o nome real: dois modulos, duas
    globais. Com o registro dentro de gui.py, a janela ficava no ``__main__`` e
    o preview procurava no outro, achava None e nao exibia nada.
    """
    import runpy

    from sentinel.app import panel as registro

    # Garante o cenario: o modulo canonico existe e esta vazio.
    assert registro.current_panel() is None

    import sentinel.app.gui as gui_canonico

    caminho = gui_canonico.__file__
    modulo_script = runpy.run_path(caminho, run_name="__main__")

    # O arquivo carregado como script e um objeto diferente...
    assert modulo_script["SentinelApp"] is not gui_canonico.SentinelApp
    # ...mas o registro que os dois enxergam e o mesmo.
    assert modulo_script["panel"] is registro

    registro.set_panel(app)
    try:
        assert modulo_script["current_panel"]() is app
    finally:
        registro.set_panel(None)
