#!/usr/bin/env bash
#
# run-pi.sh — sobe o Sentinel no Raspberry Pi com o backend `real`.
#
# Carrega as variáveis de ambiente de `.env` (se existir), valida que as
# interfaces de hardware estão de fato disponíveis e chama a CLI. Sem esse
# wrapper seria preciso exportar SENTINEL_* na mão a cada boot.
#
# Uso:
#   ./scripts/run-pi.sh                    # backend real, atuador do .env
#   SENTINEL_LOCK_TYPE=servo ./scripts/run-pi.sh
#   ./scripts/run-pi.sh --mock             # força backend mock (debug no Pi)
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

c_reset=$'\033[0m'; c_warn=$'\033[33m'; c_err=$'\033[31m'

warn() { printf '%s[warn]%s %s\n' "$c_warn" "$c_reset" "$1" >&2; }
die()  { printf '%s[erro]%s %s\n' "$c_err" "$c_reset" "$1" >&2; exit 1; }

# ------------------------------------------------------------------ ambiente
# Precedência: variáveis já exportadas na shell > .env > padrões do config.py.
# Por isso o .env é carregado sem sobrescrever o que já existe.
if [[ -f .env ]]; then
    while IFS= read -r line; do
        [[ "$line" =~ ^[[:space:]]*(#|$) ]] && continue
        key="${line%%=*}"; key="${key//[[:space:]]/}"
        [[ -n "${!key:-}" ]] && continue
        export "${key}=${line#*=}"
    done < .env
fi

export SENTINEL_BACKEND="${SENTINEL_BACKEND:-real}"
export PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}"

if [[ "${1:-}" == "--mock" ]]; then
    export SENTINEL_BACKEND=mock
    shift
fi

# --------------------------------------------------------------- validações
# Falhar aqui com uma mensagem clara é melhor do que um ImportError ou um
# "Permission denied" no meio da inicialização do HAL.
if [[ "$SENTINEL_BACKEND" == "real" ]]; then
    [[ -e /dev/spidev0.0 ]] || die "SPI indisponível (RFID). Rode ./scripts/setup-pi.sh e reinicie."
    [[ -e /dev/i2c-1     ]] || die "I2C indisponível (LCD). Rode ./scripts/setup-pi.sh e reinicie."
    id -nG | grep -qw gpio || warn "usuário fora do grupo 'gpio' — faça logout/reboot após o setup"

    if [[ ! -f .venv/pyvenv.cfg ]]; then
        die ".venv ausente. Rode ./scripts/setup-pi.sh"
    fi
    grep -q 'include-system-site-packages = true' .venv/pyvenv.cfg \
        || warn ".venv sem system-site-packages: picamera2/cv2 não serão encontrados. Rode ./scripts/setup-pi.sh"
fi

printf 'Sentinel  backend=%s  lock=%s  db=%s\n' \
    "$SENTINEL_BACKEND" "${SENTINEL_LOCK_TYPE:-solenoid}" "${SENTINEL_DB_PATH:-sentinel.db}"

exec uv run --no-sync python src/sentinel/app/cli.py "$@"
