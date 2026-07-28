from sentinel.infra.users_repository import verify_pin


def verify(conn, username, pin):
    return verify_pin(conn, username, pin)
