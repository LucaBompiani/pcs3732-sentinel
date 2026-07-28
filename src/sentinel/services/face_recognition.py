from sentinel.infra.users_repository import user_exists


def recognize(conn, presented_name):
    # incompleto, no momento apenas bate no DB
    if presented_name and user_exists(conn, presented_name):
        return presented_name
    return None
