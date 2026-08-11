import os

from src.sentinel.config import load_config


def _with_env(env):
    """Context helper: aplica env, retorna Config e restaura o ambiente."""
    saved = {k: os.environ.get(k) for k in env}
    try:
        for k, v in env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return load_config()
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_defaults():
    cfg = _with_env(
        {
            "SENTINEL_BACKEND": None,
            "SENTINEL_LOCK_TYPE": None,
            "SENTINEL_DB_PATH": None,
            "SENTINEL_RELAY_SECONDS": None,
            "SENTINEL_FACTOR2_TIMEOUT": None,
            "SENTINEL_PRESENCE_TIMEOUT": None,
            "SENTINEL_TOTAL_TIMEOUT": None,
            "SENTINEL_FACE_SAMPLES": None,
            "SENTINEL_MASTER_PIN": None,
            "SENTINEL_MAX_FAILURES": None,
            "SENTINEL_LOCKOUT_SECONDS": None,
        }
    )
    assert cfg.backend == "mock"
    assert cfg.lock_type == "solenoid"
    assert cfg.db_path == "sentinel.db"
    assert cfg.relay_seconds == 5.0
    assert cfg.factor2_timeout == 15.0
    assert cfg.presence_timeout is None
    assert cfg.total_timeout == 8.0
    assert cfg.face_samples == 5
    assert cfg.master_pin == "0000"
    assert cfg.max_failures == 3
    assert cfg.lockout_seconds == 60.0


def test_backend_and_timeouts_parsed():
    cfg = _with_env(
        {
            "SENTINEL_BACKEND": "real",
            "SENTINEL_RELAY_SECONDS": "3.5",
            "SENTINEL_FACE_SAMPLES": "8",
        }
    )
    assert cfg.backend == "real"
    assert cfg.relay_seconds == 3.5
    assert cfg.face_samples == 8


def test_lockout_and_lock_type_parsed():
    cfg = _with_env(
        {
            "SENTINEL_LOCK_TYPE": "servo",
            "SENTINEL_MAX_FAILURES": "5",
            "SENTINEL_LOCKOUT_SECONDS": "120",
        }
    )
    assert cfg.lock_type == "servo"
    assert cfg.max_failures == 5
    assert cfg.lockout_seconds == 120.0


def test_presence_timeout_none_keyword():
    cfg = _with_env({"SENTINEL_PRESENCE_TIMEOUT": "none"})
    assert cfg.presence_timeout is None


def test_config_is_frozen():
    cfg = load_config()
    try:
        cfg.backend = "real"
        assert False, "Config deveria ser imutavel"
    except Exception:
        pass
