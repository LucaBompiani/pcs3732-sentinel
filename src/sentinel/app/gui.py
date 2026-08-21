"""Aplicativo de janela do Sentinel — substitui a CLI no Raspberry Pi.

Mostra a foto de cada captura (com o retângulo do rosto detectado), espelha o
LCD e oferece em botões tudo o que a CLI faz: cadastro e acesso via hardware,
cadastro manual e simulação de tentativa.

Feito com Tkinter, da biblioteca padrão (no Raspberry Pi OS vem no pacote
``python3-tk``): nenhuma dependência nova, nenhum navegador e nenhum servidor.

As operações rodam numa thread de trabalho, porque um ciclo de acesso pode levar
segundos esperando presença, rosto e segundo fator — executá-lo na thread da
interface congelaria a janela inteira. A thread nunca toca em widgets: tudo o que
precisa aparecer na tela é enfileirado e aplicado por :meth:`_drenar_fila`, que
roda na thread do Tk.

As imagens ficam apenas em memória, nunca em disco (RNF04/LGPD).
"""

import os
import queue
import threading
import tkinter as tk
from tkinter import simpledialog, ttk

from sentinel.app import panel
from sentinel.app.state_machine import run_access_attempt, run_access_cycle, run_enrollment
from sentinel.hal.factory import build_hal
from sentinel.infra.db import connect
from sentinel.infra.users_repository import create_user, user_exists
from sentinel.services.lockout import is_locked

# Paleta escura, para a janela não ofuscar numa sala de demonstração.
FUNDO = "#12151c"
CARTAO = "#1b1f29"
BORDA = "#2c3240"
TEXTO = "#e6e9ef"
FRACO = "#98a1b2"
ACENTO = "#4c8dff"
OK = "#3fb950"
ERRO = "#f85149"
LCD_FUNDO = "#0b3d0b"
LCD_TEXTO = "#9cff9c"

# Intervalo de drenagem da fila de atualizações, em milissegundos.
TICK = 100

# Linhas mantidas no log da janela.
LOG_MAX = 200


class SentinelApp:
    """Janela principal: foto, LCD espelhado, botões de ação e log."""

    def __init__(self, cfg, conn=None, hal=None, root=None):
        self.cfg = cfg
        # check_same_thread=False: a conexão nasce aqui, na thread do Tk, mas
        # as operações rodam na thread de trabalho. É seguro porque a janela
        # serializa as ações (ver ``_executar``): nunca há duas em andamento.
        self.conn = conn if conn is not None else connect(
            cfg.db_path, check_same_thread=False
        )
        self.hal = hal if hal is not None else build_hal(cfg)

        # Fila thread-safe: a thread de trabalho publica, o Tk consome.
        self._fila = queue.Queue()
        self._imagem_atual = None  # referência viva: o Tk descarta PhotoImage sem ela
        self._ocupado = False
        self._botoes = []

        self.root = root if root is not None else tk.Tk()
        self._montar()
        self._espelhar_display()
        self.root.after(TICK, self._drenar_fila)

    # ------------------------------------------------------------- construção

    def _montar(self):
        self.root.title("Sentinel — Controle de Acesso")
        self.root.configure(bg=FUNDO)
        self.root.minsize(880, 620)

        estilo = ttk.Style(self.root)
        # 'clam' aceita as cores definidas abaixo; o tema padrão as ignora.
        if "clam" in estilo.theme_names():
            estilo.theme_use("clam")
        estilo.configure("TFrame", background=FUNDO)
        estilo.configure("Cartao.TFrame", background=CARTAO)
        estilo.configure("TLabel", background=FUNDO, foreground=TEXTO)
        estilo.configure("Fraco.TLabel", background=CARTAO, foreground=FRACO)
        estilo.configure("Cartao.TLabel", background=CARTAO, foreground=TEXTO)
        estilo.configure(
            "Acao.TButton", background=ACENTO, foreground="#ffffff",
            padding=(14, 11), borderwidth=0, font=("TkDefaultFont", 10, "bold"),
        )
        estilo.map("Acao.TButton",
                   background=[("active", "#3b7ae0"), ("disabled", BORDA)],
                   foreground=[("disabled", FRACO)])
        estilo.configure(
            "Secundaria.TButton", background=BORDA, foreground=TEXTO,
            padding=(14, 11), borderwidth=0,
        )
        estilo.map("Secundaria.TButton",
                   background=[("active", "#3a4152"), ("disabled", "#232833")],
                   foreground=[("disabled", FRACO)])

        raiz = ttk.Frame(self.root, padding=16)
        raiz.pack(fill="both", expand=True)

        self._montar_cabecalho(raiz)
        corpo = ttk.Frame(raiz)
        corpo.pack(fill="both", expand=True, pady=(14, 0))
        self._montar_coluna_foto(corpo)
        self._montar_coluna_acoes(corpo)

    def _montar_cabecalho(self, pai):
        linha = ttk.Frame(pai)
        linha.pack(fill="x")
        ttk.Label(linha, text="Sentinel", font=("TkDefaultFont", 19, "bold")).pack(side="left")
        ttk.Label(
            linha, text="  autenticação multifator · facial + PIN/RFID",
            foreground=FRACO,
        ).pack(side="left", pady=(6, 0))

        self.lbl_backend = ttk.Label(
            linha,
            text=f"backend: {self.cfg.backend} · atuador: {self.cfg.lock_type}",
            foreground=FRACO,
        )
        self.lbl_backend.pack(side="right", pady=(6, 0))

    def _montar_coluna_foto(self, pai):
        cartao = ttk.Frame(pai, style="Cartao.TFrame", padding=12)
        cartao.pack(side="left", fill="both", expand=True)

        # Canvas em vez de Label: mantém o tamanho fixo mesmo sem imagem, então
        # a janela não pula de tamanho na primeira captura.
        self.canvas = tk.Canvas(
            cartao, width=480, height=360, bg="#000000",
            highlightthickness=1, highlightbackground=BORDA,
        )
        self.canvas.pack()
        self._texto_vazio = self.canvas.create_text(
            240, 180, text="sem captura ainda", fill=FRACO, font=("TkDefaultFont", 11),
        )

        self.lbl_rotulo = ttk.Label(cartao, text="—", style="Cartao.TLabel",
                                    font=("TkDefaultFont", 11, "bold"))
        self.lbl_rotulo.pack(anchor="w", pady=(10, 0))

        # Espelho do LCD 2x16, com a cara do display verde.
        self.lcd = tk.Label(
            cartao, text=" \n ", bg=LCD_FUNDO, fg=LCD_TEXTO, justify="left",
            anchor="w", font=("TkFixedFont", 15), padx=12, pady=8, width=18, height=2,
        )
        self.lcd.pack(fill="x", pady=(10, 0))

        ttk.Label(
            cartao, text="Imagens ficam só na memória; nada é gravado em disco.",
            style="Fraco.TLabel", font=("TkDefaultFont", 8),
        ).pack(anchor="w", pady=(8, 0))

    def _montar_coluna_acoes(self, pai):
        coluna = ttk.Frame(pai)
        coluna.pack(side="left", fill="both", expand=True, padx=(14, 0))

        ttk.Label(coluna, text="Hardware", foreground=FRACO).pack(anchor="w")
        self._botao(coluna, "Ciclo de acesso", self.acao_acesso, "Acao.TButton")
        self._botao(coluna, "Cadastrar usuário", self.acao_cadastro_hw, "Acao.TButton")

        ttk.Label(coluna, text="Sem hardware", foreground=FRACO).pack(anchor="w", pady=(14, 0))
        self._botao(coluna, "Cadastro manual", self.acao_cadastro_manual, "Secundaria.TButton")
        self._botao(coluna, "Simular tentativa", self.acao_simular, "Secundaria.TButton")

        ttk.Label(coluna, text="Registro", foreground=FRACO).pack(anchor="w", pady=(14, 0))
        moldura = ttk.Frame(coluna, style="Cartao.TFrame")
        moldura.pack(fill="both", expand=True)
        self.log = tk.Text(
            moldura, height=12, bg=CARTAO, fg=TEXTO, insertbackground=TEXTO,
            relief="flat", wrap="word", font=("TkFixedFont", 9), padx=8, pady=8,
        )
        self.log.pack(side="left", fill="both", expand=True)
        barra = ttk.Scrollbar(moldura, command=self.log.yview)
        barra.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=barra.set, state="disabled")
        self.log.tag_configure("ok", foreground=OK)
        self.log.tag_configure("erro", foreground=ERRO)
        self.log.tag_configure("fraco", foreground=FRACO)

        self._botao(coluna, "Sair", self.fechar, "Secundaria.TButton")

    def _botao(self, pai, texto, comando, estilo):
        b = ttk.Button(pai, text=texto, command=comando, style=estilo)
        b.pack(fill="x", pady=4)
        self._botoes.append(b)
        return b

    # -------------------------------------------------- publicação (thread-safe)

    def publish_image(self, png, rotulo=""):
        """Recebe uma captura em PNG. Chamável de qualquer thread."""
        self._fila.put(("imagem", (png, rotulo)))

    def publish_status(self, linha1, linha2=""):
        """Espelha o LCD na janela. Chamável de qualquer thread."""
        self._fila.put(("lcd", (linha1, linha2)))

    def log_line(self, texto, tag="fraco"):
        """Escreve no registro. Chamável de qualquer thread."""
        self._fila.put(("log", (texto, tag)))

    def _espelhar_display(self):
        """Faz o display do HAL publicar também na janela.

        Embrulha o objeto em vez de mudar a máquina de estados: ela continua só
        chamando ``hal.display.show``, sem saber que existe uma interface.
        """
        import dataclasses

        painel = self

        class DisplayEspelhado:
            def __init__(self, interno):
                self._interno = interno

            def show(self, line1, line2=""):
                self._interno.show(line1, line2)
                painel.publish_status(line1, line2)

            def clear(self):
                self._interno.clear()
                painel.publish_status("", "")

            def __getattr__(self, nome):
                return getattr(self._interno, nome)

        self.hal = dataclasses.replace(
            self.hal, display=DisplayEspelhado(self.hal.display)
        )

    # ------------------------------------------------------ consumo na thread Tk

    def _drenar_fila(self):
        """Aplica na interface tudo que a thread de trabalho enfileirou."""
        try:
            while True:
                tipo, dados = self._fila.get_nowait()
                if tipo == "imagem":
                    self._aplicar_imagem(*dados)
                elif tipo == "lcd":
                    self._aplicar_lcd(*dados)
                elif tipo == "log":
                    self._aplicar_log(*dados)
                elif tipo == "ocupado":
                    self._aplicar_ocupado(dados)
        except queue.Empty:
            pass
        self.root.after(TICK, self._drenar_fila)

    def _aplicar_imagem(self, png, rotulo):
        # O Tk 8.6+ lê PNG nativamente, então não é preciso Pillow.
        imagem = tk.PhotoImage(data=png)

        largura, altura = imagem.width(), imagem.height()
        alvo_l, alvo_a = 480, 360
        # ``subsample`` só reduz por fatores inteiros — suficiente para caber na
        # área e sem custo de reamostragem fina.
        fator = max(1, -(-largura // alvo_l), -(-altura // alvo_a))
        if fator > 1:
            imagem = imagem.subsample(fator, fator)

        self._imagem_atual = imagem  # sem isto o Tk coleta a imagem e mostra vazio
        self.canvas.delete("captura")
        self.canvas.itemconfigure(self._texto_vazio, state="hidden")
        self.canvas.create_image(240, 180, image=imagem, tags="captura")
        self.lbl_rotulo.configure(text=self._rotulo_amigavel(rotulo))

    def _aplicar_lcd(self, linha1, linha2):
        self.lcd.configure(text=f"{linha1 or ' '}\n{linha2 or ' '}")

    def _aplicar_log(self, texto, tag):
        self.log.configure(state="normal")
        self.log.insert("end", texto + "\n", tag)
        # Poda o começo para o widget não crescer sem limite numa sessão longa.
        if int(self.log.index("end-1c").split(".")[0]) > LOG_MAX:
            self.log.delete("1.0", f"{LOG_MAX // 2}.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _aplicar_ocupado(self, ocupado):
        self._ocupado = ocupado
        estado = "disabled" if ocupado else "normal"
        for b in self._botoes:
            b.configure(state=estado)

    @staticmethod
    def _rotulo_amigavel(rotulo):
        if not rotulo:
            return "—"
        if rotulo == "verificacao":
            return "Verificação de acesso"
        return f"Cadastro: {rotulo}"

    # ------------------------------------------------------------------- ações

    def _executar(self, descricao, funcao):
        """Roda ``funcao`` na thread de trabalho, travando os botões enquanto isso.

        A trava evita duas operações concorrentes disputando a câmera e o
        teclado — o hardware é único.
        """
        if self._ocupado:
            self.log_line("Aguarde: já há uma operação em andamento.", "erro")
            return

        self._fila.put(("ocupado", True))
        self.log_line(f"▶ {descricao}")

        def trabalho():
            try:
                funcao()
            except Exception as erro:  # a janela não pode morrer por causa de uma ação
                self.log_line(f"✗ {type(erro).__name__}: {erro}", "erro")
            finally:
                self._fila.put(("ocupado", False))

        threading.Thread(target=trabalho, daemon=True).start()

    def acao_acesso(self):
        """Ciclo completo dirigido pelo HAL (presença, câmera, 2º fator)."""
        def corpo():
            autorizado, f1, f2 = run_access_cycle(self.conn, self.hal, self.cfg)
            self.log_line(f"  Fator 1 (facial): {'OK' if f1 else 'FALHOU'}")
            self.log_line(f"  Fator 2 (PIN/RFID): {'OK' if f2 else 'FALHOU'}")
            self.log_line(
                "✓ ACESSO AUTORIZADO" if autorizado else "✗ ACESSO NEGADO",
                "ok" if autorizado else "erro",
            )

        self._executar("Ciclo de acesso", corpo)

    def acao_cadastro_hw(self):
        """Enrolamento via hardware: exige a tecla A e o PIN mestre."""
        nome = self._perguntar("Cadastro", "Nome do novo usuário:")
        if not nome:
            return

        def corpo():
            ok = run_enrollment(self.conn, self.hal, self.cfg, nome)
            self.log_line(
                f"✓ Cadastro de '{nome}' concluído" if ok else f"✗ Cadastro de '{nome}' abortado",
                "ok" if ok else "erro",
            )

        self._executar(f"Cadastro por hardware de '{nome}'", corpo)

    def acao_cadastro_manual(self):
        """Cadastro só no banco (sem câmera), para preparar uma demonstração."""
        nome = self._perguntar("Cadastro manual", "Nome do usuário:")
        if not nome:
            return
        pin = self._perguntar("Cadastro manual", f"PIN de {nome}:") or ""
        cartao = self._perguntar("Cadastro manual", "UID do cartão (vazio = sem cartão):")

        def corpo():
            # Toda consulta ao banco fica na thread de trabalho, para o acesso
            # ao SQLite acontecer sempre a partir da mesma thread.
            if user_exists(self.conn, nome):
                self.log_line(f"✗ Usuário '{nome}' já existe", "erro")
                return
            create_user(self.conn, nome, pin, card_uid=cartao or None)
            self.log_line(f"✓ Usuário '{nome}' criado (sem amostras faciais)", "ok")

        self._executar(f"Cadastro manual de '{nome}'", corpo)

    def acao_simular(self):
        """Tentativa com os fatores digitados, sem tocar no hardware."""
        nome = self._perguntar("Simular", "Nome reconhecido (vazio = ninguém):")
        pin = self._perguntar("Simular", "PIN informado (vazio = nenhum):")
        cartao = self._perguntar("Simular", "UID do cartão (vazio = nenhum):")

        def corpo():
            bloqueado = bool(nome) and is_locked(self.conn, nome)
            autorizado, f1, f2 = run_access_attempt(
                self.conn, self.cfg, nome or None, pin or None, card_uid=cartao or None
            )
            self.log_line(f"  Fator 1 (facial): {'OK' if f1 else 'FALHOU'}")
            self.log_line(f"  Fator 2 (PIN/RFID): {'OK' if f2 else 'FALHOU'}")
            if bloqueado:
                self.log_line(
                    f"  BLOQUEADO ({self.cfg.lockout_seconds:.0f}s após falhas seguidas)",
                    "erro",
                )
            self.log_line(
                "✓ ACESSO AUTORIZADO" if autorizado else "✗ ACESSO NEGADO",
                "ok" if autorizado else "erro",
            )

        self._executar("Simulação de tentativa", corpo)

    def _perguntar(self, titulo, mensagem):
        """Caixa de texto modal; ``None`` se o usuário cancelar."""
        valor = simpledialog.askstring(titulo, mensagem, parent=self.root)
        return valor.strip() if valor else valor

    # ------------------------------------------------------------ ciclo de vida

    def fechar(self):
        try:
            self.conn.close()
        finally:
            self.root.destroy()

    def run(self):
        self.log_line(
            f"Sentinel iniciado · backend={self.cfg.backend} · atuador={self.cfg.lock_type}"
        )
        self.publish_status("Sentinel", "pronto")
        self.root.protocol("WM_DELETE_WINDOW", self.fechar)
        self.root.mainloop()


def current_panel():
    """Janela em execução, ou ``None`` (por exemplo, quando se usa a CLI).

    Delega ao :mod:`sentinel.app.panel`: guardar o registro aqui não funciona
    quando este arquivo é iniciado como script, porque ele passa a existir duas
    vezes (como ``__main__`` e como ``sentinel.app.gui``), cada um com sua
    própria variável.
    """
    return panel.current_panel()


def main():
    from sentinel.config import load_config

    cfg = load_config()
    app = SentinelApp(cfg)
    panel.set_panel(app)
    try:
        app.run()
    finally:
        panel.set_panel(None)


# ``SENTINEL_GUI_NO_LAUNCH`` deixa carregar este arquivo como script (para
# exercitar o cenário do módulo duplo — ver tests/test_gui.py) sem abrir a janela
# nem entrar no ``mainloop``, que bloquearia para sempre.
if __name__ == "__main__" and not os.environ.get("SENTINEL_GUI_NO_LAUNCH"):
    main()
