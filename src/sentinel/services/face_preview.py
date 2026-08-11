"""Exibição do rosto capturado, para conferir enquadramento e detecção.

Quatro modos, por ``SENTINEL_FACE_PREVIEW``:

``window``
    Abre uma janela do OpenCV com a **foto** da câmera e um retângulo sobre o
    rosto detectado. Exige monitor ligado ao Pi (ou X11 encaminhado por SSH).
``file``
    Grava a foto em JPEG e informa o caminho. É o modo para quem acessa o Pi
    por SSH — abrir o arquivo no VS Code Remote, por exemplo. **Grava rosto em
    disco**, ao contrário de todo o resto do sistema: ver o aviso abaixo.
``ascii``
    Desenha o recorte normalizado no terminal com caracteres. Não é a foto, mas
    é o único modo que funciona em qualquer terminal, sem monitor nem arquivos.
``off``
    Não exibe nada (padrão).

Aviso de privacidade (RNF04/LGPD): o sistema nunca persiste imagens de rosto —
o banco guarda apenas vetores de características. O modo ``file`` é a única
exceção e existe para depuração da montagem. Use-o temporariamente e apague o
diretório depois; deixá-lo ligado invalida a afirmação de privacidade do
projeto. Os modos ``window`` e ``ascii`` não gravam nada.
"""

import os

# Do mais escuro ao mais claro. Espaço para preto e '@' para branco mantém o
# desenho legível em terminal de fundo escuro.
RAMPA = " .:-=+*#%@"

# Proporção do desenho em caracteres. A largura é o dobro da altura porque a
# célula do terminal é cerca de duas vezes mais alta que larga — sem isso o
# rosto sai achatado.
LARGURA = 32
ALTURA = 16

# Onde o modo ``file`` grava as fotos.
PREVIEW_DIR = "/tmp/sentinel-preview"

# Cor e espessura do retângulo desenhado sobre o rosto (BGR, como o OpenCV usa).
COR_CAIXA = (0, 255, 0)
ESPESSURA_CAIXA = 2


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


def annotate(frame, caixa=None, rotulo=""):
    """Devolve a foto em BGR com o retângulo e o rótulo do rosto desenhados.

    Args:
        frame: Quadro cru da câmera (numpy, RGB/RGBA/cinza).
        caixa: ``(x, y, largura, altura)`` do rosto, ou ``None``.
        rotulo: Texto escrito acima do retângulo.

    Returns:
        Array numpy em BGR, pronto para ``imshow``/``imwrite``.
    """
    import cv2
    import numpy as np

    imagem = np.asarray(frame)
    canais = imagem.shape[2] if imagem.ndim == 3 else 1
    if canais == 1:
        imagem = cv2.cvtColor(imagem, cv2.COLOR_GRAY2BGR)
    elif canais == 4:
        imagem = cv2.cvtColor(imagem, cv2.COLOR_RGBA2BGR)
    else:
        # A picamera2 entrega RGB; o OpenCV desenha e grava em BGR.
        imagem = cv2.cvtColor(imagem, cv2.COLOR_RGB2BGR)

    imagem = imagem.copy()  # não rabiscar o quadro que segue para o reconhecedor
    if caixa is not None:
        x, y, w, h = caixa
        cv2.rectangle(imagem, (x, y), (x + w, y + h), COR_CAIXA, ESPESSURA_CAIXA)
        if rotulo:
            cv2.putText(
                imagem, rotulo, (x, max(y - 8, 12)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, COR_CAIXA, ESPESSURA_CAIXA,
            )
    return imagem


def has_display():
    """Há servidor gráfico para o ``imshow`` abrir janela?"""
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _mostrar_janela(frame, caixa, rotulo):
    import cv2

    cv2.imshow("Sentinel", annotate(frame, caixa, rotulo))
    cv2.waitKey(1)  # cede ao loop de eventos sem bloquear a autenticação


def _gravar_arquivo(frame, caixa, rotulo, diretorio, contador):
    import cv2

    os.makedirs(diretorio, exist_ok=True)
    nome = f"{contador:03d}-{rotulo or 'captura'}.jpg"
    caminho = os.path.join(diretorio, nome)
    cv2.imwrite(caminho, annotate(frame, caixa, rotulo))
    return caminho


def make(cfg, saida=print, diretorio=PREVIEW_DIR):
    """Devolve o callback de exibição da captura, ou ``None`` se desligado.

    Args:
        cfg: Configuração (``cfg.face_preview``).
        saida: Função de escrita das mensagens; injetável para teste.
        diretorio: Destino do modo ``file``.

    Returns:
        ``callable(frame, rosto, caixa, rotulo)`` ou ``None``.
    """
    modo = getattr(cfg, "face_preview", "off")
    if modo == "off":
        return None

    if modo == "window" and not has_display():
        saida(
            "[preview] SENTINEL_FACE_PREVIEW=window precisa de monitor no Pi "
            "(ou 'ssh -X'). Sem servidor gráfico; gravando em arquivo."
        )
        modo = "file"

    contador = [0]

    def mostrar(frame, rosto=None, caixa=None, rotulo=""):
        contador[0] += 1

        if modo == "ascii":
            if rosto is not None:
                saida(format_ascii(rosto, rotulo))
            return

        if frame is None:  # sem foto (backend simulado): só o recorte serve
            if rosto is not None:
                saida(format_ascii(rosto, rotulo))
            return

        try:
            if modo == "window":
                _mostrar_janela(frame, caixa, rotulo)
            else:
                caminho = _gravar_arquivo(frame, caixa, rotulo, diretorio, contador[0])
                saida(f"[preview] {caminho}")
        except Exception as erro:
            # Pré-visualização é diagnóstico: nunca deve derrubar um acesso.
            saida(f"[preview] falhou ({erro})")
            if rosto is not None:
                saida(format_ascii(rosto, rotulo))

    return mostrar
