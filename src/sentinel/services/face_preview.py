"""Exibição do rosto capturado, para conferir enquadramento e detecção.

Mostra o recorte JÁ NORMALIZADO (o mesmo que alimenta o reconhecimento), não o
quadro cru: é ele que decide se a pessoa é identificada, então é o que interessa
inspecionar. Se o recorte sai torto, escuro ou pegando o fundo, o problema está
na captura e não no limiar.

Nada é gravado em disco — a imagem é desenhada e descartada, preservando o
RNF04/LGPD, que veda persistir rostos.

Dois modos, por ``SENTINEL_FACE_PREVIEW``:

``ascii``
    Desenha no terminal com caracteres. Funciona por SSH, sem monitor nem
    servidor gráfico — é o padrão porque é o único que funciona em qualquer
    situação.
``window``
    Abre uma janela do OpenCV. Exige monitor no Pi (ou X11 encaminhado).
``off``
    Não exibe nada.
"""

# Do mais escuro ao mais claro. Espaço para preto e '@' para branco mantém o
# desenho legível em terminal de fundo escuro.
RAMPA = " .:-=+*#%@"

# Proporção do desenho em caracteres. A largura é o dobro da altura porque a
# célula do terminal é cerca de duas vezes mais alta que larga — sem isso o
# rosto sai achatado.
LARGURA = 32
ALTURA = 16


def render_ascii(gray, largura=LARGURA, altura=ALTURA, rampa=RAMPA):
    """Converte uma imagem em tons de cinza num desenho de caracteres.

    Reamostra por vizinho mais próximo (suficiente para conferência visual) e
    mapeia cada nível de cinza para um caractere da rampa.

    Args:
        gray: Sequência de linhas de inteiros 0..255.
        largura: Colunas do desenho.
        altura: Linhas do desenho.
        rampa: Caracteres do mais escuro para o mais claro.

    Returns:
        Lista de strings, uma por linha.
    """
    origem_altura = len(gray)
    origem_largura = len(gray[0]) if origem_altura else 0
    if not origem_altura or not origem_largura:
        return []

    ultimo = len(rampa) - 1
    linhas = []
    for r in range(altura):
        origem_r = min(r * origem_altura // altura, origem_altura - 1)
        linha_origem = gray[origem_r]
        linha = []
        for c in range(largura):
            origem_c = min(c * origem_largura // largura, origem_largura - 1)
            valor = linha_origem[origem_c]
            linha.append(rampa[valor * ultimo // 255])
        linhas.append("".join(linha))
    return linhas


def format_ascii(gray, titulo="", **kw):
    """Desenho em caracteres com moldura e título, pronto para imprimir."""
    linhas = render_ascii(gray, **kw)
    if not linhas:
        return ""
    largura = len(linhas[0])
    topo = f"┌─ {titulo} ".ljust(largura + 2, "─") + "┐" if titulo else "┌" + "─" * (largura + 2) + "┐"
    corpo = [f"│ {linha} │" for linha in linhas]
    base = "└" + "─" * (largura + 2) + "┘"
    return "\n".join([topo, *corpo, base])


def _show_window(gray, titulo):
    """Abre/atualiza uma janela do OpenCV com o recorte."""
    import cv2
    import numpy as np

    imagem = np.array(gray, dtype="uint8")
    # Ampliado 4x: 64x64 é pequeno demais para avaliar a olho.
    imagem = cv2.resize(imagem, (imagem.shape[1] * 4, imagem.shape[0] * 4),
                        interpolation=cv2.INTER_NEAREST)
    cv2.imshow(titulo or "Sentinel", imagem)
    cv2.waitKey(1)  # cede o controle ao loop de eventos sem bloquear o fluxo


def make(cfg, saida=print):
    """Devolve o callback de exibição do rosto, ou ``None`` se desligado.

    Args:
        cfg: Configuração (``cfg.face_preview``).
        saida: Função de escrita do modo ``ascii``; injetável para teste.

    Returns:
        ``callable(gray, rotulo)`` ou ``None``.
    """
    modo = getattr(cfg, "face_preview", "off")
    if modo == "off":
        return None

    def mostrar(gray, rotulo=""):
        if modo == "window":
            try:
                _show_window(gray, rotulo)
                return
            except Exception as erro:
                # Sem monitor/X11 o imshow falha. Cair para ASCII é melhor do
                # que derrubar uma autenticação por causa da pré-visualização.
                saida(f"[preview] janela indisponivel ({erro}); usando ascii")
        saida(format_ascii(gray, rotulo))

    return mostrar
