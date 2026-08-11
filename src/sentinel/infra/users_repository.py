"""Acesso à tabela de usuários (cadastro e verificação do Fator 2)."""

from sentinel.infra.security import gen_salt, hash_pin


def create_user(conn, username, pin, card_uid=None):
    """Cadastra um novo usuário com PIN e, opcionalmente, cartão RFID.

    Gera um salt aleatório por usuário (RNF04) e armazena apenas os hashes
    salgados do PIN e do UID do cartão — nunca os valores em texto plano.

    Args:
        conn: Conexão SQLite.
        username: Identificador único do usuário.
        pin: PIN do segundo fator, em texto plano.
        card_uid: UID do cartão RFID (texto plano) a associar, ou ``None``.

    Raises:
        sqlite3.IntegrityError: Se ``username`` já existir.
    """
    salt = gen_salt()
    card_hash = hash_pin(card_uid, salt) if card_uid is not None else None
    conn.execute(
        "INSERT INTO users (username, pin_hash, salt, card_uid_hash) "
        "VALUES (?, ?, ?, ?)",
        (username, hash_pin(pin, salt), salt, card_hash),
    )
    conn.commit()


def user_exists(conn, username):
    """Indica se há um usuário cadastrado com o nome informado."""
    row = conn.execute(
        "SELECT 1 FROM users WHERE username = ?", (username,)
    ).fetchone()
    return row is not None


def _get_salt(conn, username):
    """Retorna o salt do usuário, ou ``None`` se ele não existir."""
    row = conn.execute(
        "SELECT salt FROM users WHERE username = ?", (username,)
    ).fetchone()
    return row[0] if row is not None else None


def verify_pin(conn, username, pin):
    """Verifica o PIN de um usuário contra o hash salgado armazenado.

    Linhas legadas possuem ``salt = ''``, caso em que ``hash_pin(pin, "")``
    reproduz o hash original — mantendo a compatibilidade.
    """
    row = conn.execute(
        "SELECT pin_hash, salt FROM users WHERE username = ?", (username,)
    ).fetchone()
    if row is None:
        return False
    pin_hash, salt = row
    return pin_hash == hash_pin(pin, salt)


def verify_card(conn, username, card_uid):
    """Verifica o UID de cartão RFID vinculado a um usuário específico.

    A cláusula ``WHERE username = ?`` garante o RF05: o cartão só é aceito
    para o próprio usuário identificado no Fator 1, não para qualquer outro.

    Returns:
        ``True`` se o usuário tiver cartão associado e o UID corresponder.
    """
    row = conn.execute(
        "SELECT card_uid_hash, salt FROM users WHERE username = ?", (username,)
    ).fetchone()
    if row is None:
        return False
    card_hash, salt = row
    if card_hash is None:
        return False
    return card_hash == hash_pin(card_uid, salt)


def set_card_uid(conn, username, card_uid):
    """Associa (ou atualiza) o cartão RFID de um usuário já cadastrado.

    Returns:
        ``True`` se o usuário existir e o cartão for associado; ``False`` caso
        contrário.
    """
    salt = _get_salt(conn, username)
    if salt is None:
        return False
    conn.execute(
        "UPDATE users SET card_uid_hash = ? WHERE username = ?",
        (hash_pin(card_uid, salt), username),
    )
    conn.commit()
    return True


def add_face_embedding(conn, username, embedding):
    """Persiste um vetor de características facial (embedding) do usuário.

    Apenas o vetor é armazenado, nunca a imagem original (RNF04/LGPD).

    Args:
        conn: Conexão SQLite.
        username: Usuário dono da amostra.
        embedding: Vetor serializado em ``bytes``.
    """
    conn.execute(
        "INSERT INTO face_samples (username, embedding) VALUES (?, ?)",
        (username, embedding),
    )
    conn.commit()


def get_embeddings(conn):
    """Retorna todos os embeddings faciais cadastrados.

    Returns:
        Lista de tuplas ``(username, embedding_bytes)``.
    """
    return conn.execute(
        "SELECT username, embedding FROM face_samples"
    ).fetchall()
