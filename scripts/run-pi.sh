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
#   ./scripts/run-pi.sh --cli              # terminal em vez da janela
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

c_reset=$'\033[0m'; c_warn=$'\033[33m'; c_err=$'\033[31m'

warn() { printf '%s[warn]%s %s\n' "$c_warn" "$c_reset" "$1" >&2; }
die()  { printf '%s[erro]%s %s\n' "$c_err" "$c_reset" "$1" >&2; exit 1; }

# ------------------------------------------------------------------------ uv
# O instalador do uv coloca o binário em ~/.local/bin e ajusta os perfis da
# shell — o que só vale em uma sessão NOVA. Numa shell já aberta (ou sob make)
# o `uv` continua fora do PATH, então procuramos nos destinos conhecidos em vez
# de exigir logout.
ensure_uv() {
    command -v uv >/dev/null 2>&1 && return 0
    local d
    for d in "$HOME/.local/bin" "$HOME/.cargo/bin" /usr/local/bin; do
        if [[ -x "$d/uv" ]]; then
            export PATH="$d:$PATH"
            return 0
        fi
    done
    die "uv não encontrado. Rode ./scripts/setup-pi.sh (ou abra uma shell nova, se acabou de instalar)."
}
ensure_uv

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
# A montagem física usa o servo (GPIO 18): não há solenoide de 12 V ligada, e o
# relé da placa dividiria o GPIO 12 com o buzzer. O padrão do config.py continua
# sendo 'solenoid' (o atuador do requisito), então o wrapper ajusta aqui.
export SENTINEL_LOCK_TYPE="${SENTINEL_LOCK_TYPE:-servo}"
export PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}"

if [[ "${1:-}" == "--mock" ]]; then
    export SENTINEL_BACKEND=mock
    shift
fi

# Interface: janela (padrão, exige monitor no Pi) ou CLI no terminal.
MODULO="sentinel/app/gui.py"
if [[ "${1:-}" == "--cli" ]]; then
    MODULO="sentinel/app/cli.py"
    shift
elif [[ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    warn "sem servidor gráfico (sessão SSH?); abrindo a CLI. Use --cli para não ver este aviso."
    MODULO="sentinel/app/cli.py"
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

exec uv run --no-sync python "src/$MODULO" "$@"
