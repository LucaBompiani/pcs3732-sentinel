from src.sentinel.services.decision import authorize


def test_autoriza_com_dois_fatores_ok():
    assert authorize("joao", True) is True


def test_nega_sem_fator1():
    assert authorize(None, True) is False


def test_nega_sem_fator2():
    assert authorize("joao", False) is False


def test_nega_sem_nenhum_fator():
    assert authorize(None, False) is False
