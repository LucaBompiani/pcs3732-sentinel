"""Janela do aplicativo (Tkinter).

Exercita a interface de verdade — constroi widgets, publica capturas e drena a
fila — mas so quando ha servidor grafico. Em maquina sem display (CI, Pi
headless) os testes sao pulados: sem DISPLAY o proprio ``tkinter.Tk()`` falha, e
isso nao e defeito do codigo.
"""

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
def app():
    raiz = tk.Tk()
    raiz.withdraw()  # nao piscar janela durante a suite
    aplicacao = SentinelApp(load_config(), conn=None, root=raiz)
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
