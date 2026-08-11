"""Registro da janela em execução.

Módulo minúsculo e sem dependências, com um único propósito: ser o lugar
CANÔNICO onde a janela se anuncia e onde o reconhecedor a encontra.

Por que não guardar isso no próprio :mod:`sentinel.app.gui`: ao ser iniciado
como script (``python src/sentinel/app/gui.py``, que é o que os scripts de
execução fazem), o arquivo é carregado com o nome ``__main__``. Quando outro
módulo depois faz ``import sentinel.app.gui``, o Python carrega o MESMO arquivo
de novo, agora sob o nome real — dois objetos de módulo, com globais separadas.
A janela ficava registrada no ``__main__`` e o preview procurava no outro,
achava ``None`` e não exibia nada.

Este módulo nunca é o ponto de entrada, então só existe uma cópia dele.
"""

_painel = None


def set_panel(painel):
    """Registra a janela em execução (ou ``None`` ao encerrar)."""
    global _painel
    _painel = painel


def current_panel():
    """Janela em execução, ou ``None`` quando se usa a CLI."""
    return _painel
