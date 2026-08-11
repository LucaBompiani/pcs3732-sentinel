"""Painel web do Sentinel: mostra a última captura e o estado do fluxo.

Existe porque o LCD tem 2x16 caracteres e o terminal não mostra imagem: durante
a montagem e a demonstração é preciso VER o que a câmera capturou, com o
retângulo do rosto detectado, e acompanhar as mensagens do fluxo.

A interface é escrita em Python com NiceGUI (que renderiza Vue/Quasar), servida
por FastAPI/uvicorn numa thread daemon — a autenticação nunca espera pelo
painel. O navegador acessa ``http://<ip-do-pi>:8080``.

As imagens ficam APENAS em memória, num buffer limitado — nada é gravado em
disco, preservando o RNF04/LGPD. Ao encerrar o processo, somem.
"""

import threading
import time

# Quantas capturas anteriores manter na faixa de histórico.
HISTORICO = 8

# Intervalo de atualização do painel, em segundos.
REFRESH = 0.4


class PainelState:
    """Estado compartilhado entre a autenticação e o painel.

    Guardado sob lock porque a máquina de estados escreve na thread principal e
    o servidor lê nas threads de requisição.
    """

    def __init__(self, historico=HISTORICO):
        self._lock = threading.Lock()
        self._imagens = {}  # versao -> jpeg
        self._ordem = []
        self._versao = -1
        self._rotulo = ""
        self._quando = ""
        self._linha1 = ""
        self._linha2 = ""
        self._historico = historico

    def publish_image(self, jpeg, rotulo=""):
        """Registra uma nova captura (bytes JPEG) e a torna a atual."""
        with self._lock:
            self._versao += 1
            self._imagens[self._versao] = jpeg
            self._ordem.append(self._versao)
            # Buffer limitado: um cadastro gera 5 capturas e um acesso até 10;
            # sem teto a memória cresceria sem parar num processo de longa vida.
            while len(self._ordem) > self._historico:
                self._imagens.pop(self._ordem.pop(0), None)
            self._rotulo = rotulo
            self._quando = time.strftime("%H:%M:%S")

    def publish_status(self, linha1, linha2=""):
        """Espelha no painel o que está escrito no LCD."""
        with self._lock:
            self._linha1 = linha1
            self._linha2 = linha2

    def status(self):
        """Instantâneo do estado, seguro para serializar."""
        with self._lock:
            return {
                "versao": self._versao,
                "rotulo": self._rotulo,
                "quando": self._quando,
                "linha1": self._linha1,
                "linha2": self._linha2,
                "historico": list(reversed(self._ordem[:-1])),
            }

    def image(self, versao=None):
        """JPEG de uma versão; ``None`` devolve a mais recente."""
        with self._lock:
            if versao is None:
                versao = self._versao
            return self._imagens.get(versao)


def _rotulo_amigavel(rotulo):
    """Traduz o rótulo interno para algo legível no painel."""
    if not rotulo:
        return "—"
    if rotulo == "verificacao":
        return "Verificação de acesso"
    return f"Cadastro: {rotulo}"


def build_app(state):
    """Monta a aplicação FastAPI com o painel NiceGUI e as rotas de imagem."""
    from fastapi import FastAPI
    from fastapi.responses import Response
    from nicegui import ui

    api = FastAPI()

    @api.get("/captura/{versao}.jpg")
    def captura(versao: int):
        jpeg = state.image(None if versao < 0 else versao)
        if jpeg is None:
            return Response(status_code=404)
        # sem cache: a versão muda a cada captura, mas o navegador reutilizaria
        # a resposta anterior se pudesse.
        return Response(jpeg, media_type="image/jpeg",
                        headers={"Cache-Control": "no-store"})

    @ui.page("/")
    def painel():
        ui.dark_mode().enable()
        ui.page_title("Sentinel")

        with ui.column().classes("w-full max-w-3xl mx-auto p-6 gap-4"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("shield_person", size="2rem").classes("text-primary")
                with ui.column().classes("gap-0"):
                    ui.label("Sentinel").classes("text-2xl font-bold leading-none")
                    ui.label("Controle de acesso multifator").classes(
                        "text-sm text-gray-400"
                    )

            with ui.card().classes("w-full p-4 gap-3"):
                foto = ui.image().classes(
                    "w-full rounded-lg bg-black min-h-[240px]"
                ).props("fit=contain")
                vazio = ui.label("Aguardando a primeira captura…").classes(
                    "text-gray-500 text-center py-16 w-full"
                )

                with ui.row().classes("items-center justify-between w-full"):
                    rotulo = ui.label("—").classes("font-semibold")
                    quando = ui.label("").classes("text-sm text-gray-400")

                # Espelho do LCD 2x16, com a cara do display verde.
                lcd = ui.label(" \n ").classes(
                    "font-mono text-lg whitespace-pre rounded-md px-4 py-2 w-full"
                ).style("background:#0b3d0b; color:#9cff9c; letter-spacing:1px")

                tira = ui.row().classes("gap-2 w-full overflow-x-auto")

            ui.label(
                "As imagens ficam apenas na memória do processo; nada é gravado em disco."
            ).classes("text-xs text-gray-500")

        # ``versao`` guarda o que já está na tela, para só trocar a imagem
        # quando houver captura nova (recarregar a cada ciclo piscaria).
        visto = {"versao": -1}

        def atualizar():
            s = state.status()
            lcd.set_text(f"{s['linha1'] or ' '}\n{s['linha2'] or ' '}")
            rotulo.set_text(_rotulo_amigavel(s["rotulo"]))
            quando.set_text(s["quando"])

            if s["versao"] == visto["versao"] or s["versao"] < 0:
                return
            visto["versao"] = s["versao"]

            vazio.set_visibility(False)
            foto.set_source(f"/captura/{s['versao']}.jpg")

            tira.clear()
            with tira:
                for v in s["historico"]:
                    ui.image(f"/captura/{v}.jpg").classes(
                        "h-16 rounded border border-gray-700 shrink-0"
                    )

        ui.timer(REFRESH, atualizar)

    ui.run_with(api, storage_secret="sentinel-painel")
    return api


class PreviewServer:
    """Sobe o painel numa thread daemon e recebe as publicações."""

    def __init__(self, port=8080, host="0.0.0.0"):
        self.port = port
        self.host = host
        self.state = PainelState()
        self._servidor = None
        self._thread = None

    # Delegações para o estado, para quem publica não precisar conhecê-lo.
    def publish_image(self, jpeg, rotulo=""):
        self.state.publish_image(jpeg, rotulo)

    def publish_status(self, linha1, linha2=""):
        self.state.publish_status(linha1, linha2)

    def status(self):
        return self.state.status()

    def image(self, versao=None):
        return self.state.image(versao)

    def start(self):
        """Sobe o servidor. Idempotente."""
        if self._servidor is not None:
            return self

        import uvicorn

        class ServidorEmThread(uvicorn.Server):
            def install_signal_handlers(self):
                """Não instala handlers: só a thread principal pode fazê-lo.

                Sem isto o uvicorn levanta ``ValueError`` ao subir fora da main
                thread, que é justamente o que queremos — o painel não pode
                bloquear a CLI.
                """

        config = uvicorn.Config(
            build_app(self.state), host=self.host, port=self.port, log_level="warning"
        )
        self._servidor = ServidorEmThread(config)
        self._thread = threading.Thread(target=self._servidor.run, daemon=True)
        self._thread.start()

        # Espera o socket abrir para poder informar a porta real (porta 0 nos
        # testes) e para o usuário não receber um link que ainda não responde.
        prazo = time.monotonic() + 10
        while time.monotonic() < prazo:
            if self._servidor.started and self._servidor.servers:
                self.port = self._servidor.servers[0].sockets[0].getsockname()[1]
                break
            time.sleep(0.05)
        return self

    def stop(self):
        if self._servidor is not None:
            self._servidor.should_exit = True
            if self._thread is not None:
                self._thread.join(timeout=5)
            self._servidor = None


# Instância única do processo: o reconhecedor publica de dentro do HAL, longe de
# onde o servidor é criado, e passar a referência por toda a cadeia só para isso
# poluiria as assinaturas.
_servidor = None


def ensure_server(cfg):
    """Devolve o servidor do processo, subindo-o na primeira chamada."""
    global _servidor
    if _servidor is None:
        _servidor = PreviewServer(port=getattr(cfg, "web_port", 8080)).start()
    return _servidor


def current_server():
    """Servidor já iniciado, ou ``None``."""
    return _servidor


def reset_for_tests():
    """Derruba a instância única (uso exclusivo dos testes)."""
    global _servidor
    if _servidor is not None:
        _servidor.stop()
        _servidor = None
