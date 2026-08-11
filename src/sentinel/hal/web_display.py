"""Display que espelha no painel web o que vai para o LCD.

Decorador sobre o display real ou simulado: repassa a mensagem ao dispositivo e
publica a mesma coisa no painel. Assim o navegador mostra o estado do fluxo
("Fator 2", "Bem-vindo joao") junto da foto, sem que a máquina de estados
precise conhecer o painel.
"""


class WebDisplay:
    """Encaminha para o display real e para o painel web."""

    def __init__(self, display, servidor):
        self._display = display
        self._servidor = servidor

    def show(self, line1, line2=""):
        self._display.show(line1, line2)
        self._servidor.publish_status(line1, line2)

    def clear(self):
        self._display.clear()
        self._servidor.publish_status("", "")

    def __getattr__(self, nome):
        # Repassa o que for específico do display embrulhado (ex.: ``buffer``
        # do mock, usado em testes).
        return getattr(self._display, nome)
