"""Testes do LBPH (extracao do vetor facial).

Usam imagens sinteticas: o algoritmo e puro, entao nao precisa de camera nem de
OpenCV, e o comportamento pode ser verificado exatamente.
"""

import pytest

from src.sentinel.services import face_encoding as fe


def _imagem(largura, altura, func):
    return [[func(r, c) for c in range(largura)] for r in range(altura)]


def _uniforme(valor=128, lado=fe.FACE_SIZE):
    return _imagem(lado, lado, lambda r, c: valor)


def _gradiente(lado=fe.FACE_SIZE):
    return _imagem(lado, lado, lambda r, c: (r * 4 + c * 2) % 256)


def _xadrez(lado=fe.FACE_SIZE, bloco=4):
    return _imagem(lado, lado, lambda r, c: 255 if (r // bloco + c // bloco) % 2 else 0)


def test_lbp_reduz_a_borda():
    codes = fe.lbp_image(_uniforme(lado=10))
    assert len(codes) == 8  # 10 - 2
    assert len(codes[0]) == 8


def test_lbp_em_area_uniforme_e_tudo_um():
    # Todo vizinho e >= ao centro, logo os 8 bits ligam: 0b11111111 = 255.
    codes = fe.lbp_image(_uniforme(lado=6))
    assert all(v == 255 for linha in codes for v in linha)


def test_lbp_e_invariante_a_iluminacao_uniforme():
    # A propriedade central do LBP: so importam as comparacoes entre vizinhos,
    # nao os valores absolutos. Clarear a imagem inteira nao muda o codigo.
    escura = _imagem(8, 8, lambda r, c: 40 + r * 3 + c * 2)
    clara = _imagem(8, 8, lambda r, c: 90 + r * 3 + c * 2)
    assert fe.lbp_image(escura) == fe.lbp_image(clara)


def test_lbp_rejeita_imagem_pequena():
    with pytest.raises(ValueError):
        fe.lbp_image([[1, 2], [3, 4]])


def test_histograma_tem_dimensao_esperada_e_soma_um():
    vetor = fe.spatial_histogram(fe.lbp_image(_gradiente()))
    assert len(vetor) == fe.DIM
    assert sum(vetor) == pytest.approx(1.0)


def test_encode_decode_ida_e_volta():
    blob = fe.encode(_gradiente())
    assert isinstance(blob, bytes)
    assert len(blob) == fe.DIM * 4  # float de precisao simples

    vetor = fe.decode(blob)
    assert len(vetor) == fe.DIM
    assert sum(vetor) == pytest.approx(1.0, abs=1e-4)


def test_decode_rejeita_dados_que_nao_sao_vetor():
    # Bases anteriores a esta implementacao guardavam o nome do usuario.
    assert fe.decode(b"joao") is None
    assert fe.decode(b"") is None
    assert fe.decode(None) is None
    assert fe.decode("joao") is None


def test_distancia_de_um_vetor_para_ele_mesmo_e_zero():
    v = fe.decode(fe.encode(_gradiente()))
    assert fe.chi_square(v, v) == pytest.approx(0.0)


def test_imagens_diferentes_ficam_mais_distantes_que_iguais():
    grad = fe.decode(fe.encode(_gradiente()))
    grad2 = fe.decode(fe.encode(_gradiente()))
    xadrez = fe.decode(fe.encode(_xadrez()))

    assert fe.chi_square(grad, grad2) == pytest.approx(0.0)
    assert fe.chi_square(grad, xadrez) > fe.chi_square(grad, grad2)


def test_chi_square_de_vetores_disjuntos_e_dois():
    # Limite superior da metrica para histogramas normalizados sem sobreposicao.
    a = [1.0] + [0.0] * 9
    b = [0.0] * 9 + [1.0]
    assert fe.chi_square(a, b) == pytest.approx(2.0)


def test_chi_square_exige_mesma_dimensao():
    with pytest.raises(ValueError):
        fe.chi_square([0.5, 0.5], [1.0])


def test_ruido_leve_afasta_menos_que_imagem_diferente():
    # Sanidade do limiar: a mesma face com pequena perturbacao deve ficar
    # muito mais perto do que uma imagem estruturalmente distinta.
    base = _gradiente()
    ruidosa = [[(v + (2 if (r + c) % 7 == 0 else 0)) % 256 for c, v in enumerate(linha)]
               for r, linha in enumerate(base)]

    vb = fe.decode(fe.encode(base))
    vr = fe.decode(fe.encode(ruidosa))
    vx = fe.decode(fe.encode(_xadrez()))

    assert fe.chi_square(vb, vr) < fe.chi_square(vb, vx)
