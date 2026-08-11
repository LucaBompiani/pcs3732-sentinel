"""Localizacao do XML da cascata de Haar entre instalacoes de OpenCV.

O wheel do PyPI expoe ``cv2.data.haarcascades``; o pacote python3-opencv do
Debian/Raspberry Pi OS NAO define ``cv2.data`` e instala os XML em /usr/share.
Assumir o primeiro caso quebra no dispositivo com AttributeError.
"""

import types

import pytest

from src.sentinel.services import face_detector as fd


class Cv2Wheel:
    """Imita o opencv-python do PyPI: tem cv2.data.haarcascades."""

    def __init__(self, diretorio):
        self.data = types.SimpleNamespace(haarcascades=str(diretorio) + "/")
        self.__file__ = str(diretorio) + "/cv2/__init__.py"


class Cv2Debian:
    """Imita o python3-opencv do Debian: SEM atributo ``data``."""

    def __init__(self, diretorio):
        self.__file__ = str(diretorio) + "/cv2/__init__.py"


def _cria_cascata(tmp_path, subdir):
    destino = tmp_path / subdir
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / fd.CASCADE_FILE
    arquivo.write_text("<opencv_storage/>")
    return arquivo


def test_encontra_pelo_cv2_data_do_wheel(tmp_path):
    arquivo = _cria_cascata(tmp_path, "haar")
    cv2 = Cv2Wheel(tmp_path / "haar")

    assert fd.find_cascade(cv2, dirs=()) == str(arquivo)


def test_encontra_em_usr_share_sem_cv2_data(tmp_path):
    # O caso que falha no Raspberry Pi: cv2 sem 'data'.
    arquivo = _cria_cascata(tmp_path, "usr/share/opencv4/haarcascades")
    cv2 = Cv2Debian(tmp_path)

    encontrado = fd.find_cascade(
        cv2, dirs=(str(tmp_path / "usr/share/opencv4/haarcascades") + "/",)
    )
    assert encontrado == str(arquivo)


def test_nao_estoura_attribute_error_quando_falta_cv2_data(tmp_path):
    # Regressao direta de "module cv2 has no attribute 'data'": a ausencia do
    # atributo deve virar RuntimeError explicativo, nunca AttributeError.
    cv2 = Cv2Debian(tmp_path)

    with pytest.raises(RuntimeError) as erro:
        fd.find_cascade(cv2, dirs=())

    assert "opencv-data" in str(erro.value)


def test_mensagem_de_erro_lista_onde_procurou(tmp_path):
    cv2 = Cv2Debian(tmp_path)

    with pytest.raises(RuntimeError) as erro:
        fd.find_cascade(cv2, dirs=("/caminho/inexistente/",))

    mensagem = str(erro.value)
    assert "Procurei em" in mensagem
    assert "/caminho/inexistente/" in mensagem


def test_diretorios_padrao_cobrem_debian_e_raspberry_pi_os():
    assert "/usr/share/opencv4/haarcascades/" in fd.CASCADE_DIRS
