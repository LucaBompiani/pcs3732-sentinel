#!/usr/bin/env bash
#
# setup-pi.sh — provisiona um Raspberry Pi 3 Model B+ para rodar o Sentinel
# com o backend `real` (câmera CSI v2, RFID-RC522, teclado matricial 4x4,
# LCD1602 I2C, LEDs/buzzer, relé ou servo).
#
# Executa uma vez por cartão SD. É idempotente: rodar de novo não quebra nada.
# Passos que exigem reinício (interfaces do firmware, grupos do usuário) são
# detectados e avisados no fim.
#
# Uso:
#   ./scripts/setup-pi.sh              # instalação completa
#   ./scripts/setup-pi.sh --check      # apenas diagnostica, não altera nada
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECK_ONLY=0
[[ "${1:-}" == "--check" ]] && CHECK_ONLY=1

NEEDS_REBOOT=0
FAILURES=0
UV_NOT_ON_LOGIN_PATH=0

# ---------------------------------------------------------------- utilidades

c_reset=$'\033[0m'; c_ok=$'\033[32m'; c_warn=$'\033[33m'; c_err=$'\033[31m'; c_hdr=$'\033[1;36m'

step() { printf '\n%s==> %s%s\n' "$c_hdr" "$1" "$c_reset"; }
ok()   { printf '  %s[ ok ]%s %s\n' "$c_ok" "$c_reset" "$1"; }
warn() { printf '  %s[warn]%s %s\n' "$c_warn" "$c_reset" "$1"; }
fail() { printf '  %s[FAIL]%s %s\n' "$c_err" "$c_reset" "$1"; FAILURES=$((FAILURES + 1)); }
run()  { if (( CHECK_ONLY )); then printf '  (check) pularia: %s\n' "$*"; else "$@"; fi; }

require_pi() {
    if ! grep -qi raspberry /proc/device-tree/model 2>/dev/null; then
        fail "Este script é para o Raspberry Pi. Em PC use 'make run' (backend mock)."
        exit 1
    fi
    ok "Modelo: $(tr -d '\0' < /proc/device-tree/model)"
}

# Arquivo de configuração do firmware: Bookworm+ usa /boot/firmware/config.txt.
boot_config() {
    if [[ -f /boot/firmware/config.txt ]]; then echo /boot/firmware/config.txt
    else echo /boot/config.txt; fi
}

# Garante uma linha `chave=valor` em config.txt, comentando conflitos anteriores.
ensure_boot_param() {
    local key="$1" value="$2" cfg
    cfg="$(boot_config)"
    if grep -qE "^[[:space:]]*${key}=${value}[[:space:]]*$" "$cfg"; then
        ok "$key=$value já em $cfg"
        return
    fi
    if (( CHECK_ONLY )); then
        warn "faltando '$key=$value' em $cfg"
        return
    fi
    sudo sed -i -E "s|^[[:space:]]*(${key}=.*)$|# (sentinel) \1|" "$cfg"
    printf '%s=%s\n' "$key" "$value" | sudo tee -a "$cfg" >/dev/null
    ok "adicionado $key=$value em $cfg"
    NEEDS_REBOOT=1
}

# ------------------------------------------------------- 1. pacotes do sistema
#
# picamera2 e libcamera NÃO são instaláveis por pip: dependem de bindings C++
# compilados contra o libcamera do sistema. Vêm do apt e são usados pela venv
# via --system-site-packages (ver passo 4).
#
APT_PACKAGES=(
    python3-picamera2      # câmera CSI (traz libcamera + python3-kms++)
    python3-libcamera
    python3-opencv         # deteccao de rosto (services/face_detector)
    opencv-data            # cascatas de Haar; NAO e dependencia do python3-opencv
    python3-numpy
    python3-tk             # interface grafica do aplicativo (sentinel.app.gui)
    python3-venv
    python3-dev
    python3-lgpio          # backend de GPIO do gpiozero no Pi
    i2c-tools              # i2cdetect, para achar o endereço do LCD1602
    libcap-dev             # dependência de build do python-prctl (picamera2)
    git
)

# Instalados individualmente, ignorando falha: o nome muda entre versões do
# Raspberry Pi OS (rpicam-apps no Bookworm, libcamera-apps no Bullseye) e a
# ausência de um não deve abortar o setup inteiro.
OPTIONAL_PACKAGES=(rpicam-apps libcamera-apps)

install_packages() {
    step "1/6 Pacotes do sistema (apt)"
    local missing=()
    for pkg in "${APT_PACKAGES[@]}"; do
        dpkg -s "$pkg" >/dev/null 2>&1 || missing+=("$pkg")
    done
    if (( ${#missing[@]} == 0 )); then
        ok "todos os ${#APT_PACKAGES[@]} pacotes já instalados"
        return
    fi
    warn "faltando: ${missing[*]}"
    run sudo apt-get update
    run sudo apt-get install -y "${missing[@]}"
    (( CHECK_ONLY )) || ok "pacotes instalados"

    # Ferramentas de linha de comando da câmera (rpicam-hello), usadas no
    # diagnóstico. Nome varia por versão, então tenta cada um sem abortar.
    local opt
    for opt in "${OPTIONAL_PACKAGES[@]}"; do
        dpkg -s "$opt" >/dev/null 2>&1 && { ok "$opt já instalado"; continue; }
        if (( CHECK_ONLY )); then
            printf '  (check) tentaria instalar: %s\n' "$opt"
        elif sudo apt-get install -y "$opt" >/dev/null 2>&1; then
            ok "$opt instalado"
        fi
    done
}

# --------------------------------------- 2. interfaces do firmware (SPI/I2C/cam)
#
# SPI  -> leitor RFID-RC522 (hal/real/rfid.py, via mfrc522/spidev)
# I2C  -> display LCD1602 PCF8574 (hal/real/display.py)
# cam  -> câmera CSI v2 (hal/real/camera.py, via picamera2)
#
enable_interfaces() {
    step "2/6 Interfaces do firmware (SPI, I2C, câmera)"

    if command -v raspi-config >/dev/null 2>&1 && (( ! CHECK_ONLY )); then
        # nonint: 0 = habilitar. Idempotente.
        sudo raspi-config nonint do_spi 0
        sudo raspi-config nonint do_i2c 0
        ok "SPI e I2C habilitados via raspi-config"
    fi

    ensure_boot_param dtparam=spi on
    ensure_boot_param dtparam=i2c_arm on
    # camera_auto_detect substitui o antigo start_x=1 / gpu_mem=128.
    ensure_boot_param camera_auto_detect 1

    # A pilha legada de câmera (start_x=1) e o libcamera são mutuamente
    # exclusivos: com start_x=1 o firmware reserva a câmera e picamera2 não a
    # encontra — sintoma idêntico ao de cabo solto, e muito mais comum.
    local cfg; cfg="$(boot_config)"
    if grep -qE '^[[:space:]]*start_x=1' "$cfg" 2>/dev/null; then
        if (( CHECK_ONLY )); then
            warn "start_x=1 presente (pilha legada) — impede o libcamera"
        else
            sudo sed -i -E 's|^[[:space:]]*(start_x=1.*)$|# (sentinel) \1|' "$cfg"
            ok "start_x=1 comentado (pilha legada desativada)"
            NEEDS_REBOOT=1
        fi
    else
        ok "pilha legada de câmera não está ativa"
    fi

    # Verificação: os device nodes só existem depois do reboot.
    [[ -e /dev/spidev0.0 ]] && ok "/dev/spidev0.0 presente" || warn "/dev/spidev0.0 ausente (precisa reiniciar)"
    [[ -e /dev/i2c-1    ]] && ok "/dev/i2c-1 presente"    || warn "/dev/i2c-1 ausente (precisa reiniciar)"
}

# ------------------------------------------------------- 3. grupos do usuário
#
# Sem isso, gpiozero/spidev/i2c só funcionam com sudo — e rodar o app como root
# é desnecessário e ruim.
#
setup_groups() {
    step "3/6 Grupos do usuário ($USER)"
    for grp in gpio spi i2c video dialout; do
        getent group "$grp" >/dev/null || { warn "grupo '$grp' não existe neste sistema, pulando"; continue; }
        if id -nG "$USER" | tr ' ' '\n' | grep -qx "$grp"; then
            ok "já em '$grp'"
        else
            run sudo usermod -aG "$grp" "$USER"
            (( CHECK_ONLY )) || { ok "adicionado a '$grp'"; NEEDS_REBOOT=1; }
        fi
    done
}

# --------------------------------------------------------------- 4. ambiente Python
#
# A venv é criada a partir do python3 DO SISTEMA e com --system-site-packages,
# para enxergar picamera2/libcamera/cv2 do apt. Um Python gerenciado pelo uv
# (ou uma venv isolada) NÃO enxerga esses módulos.
#
setup_python() {
    step "4/6 Ambiente Python"

    # Se o uv já foi instalado antes mas a shell atual é anterior à instalação,
    # o binário existe e só falta no PATH. Procurar evita reinstalar à toa.
    if ! command -v uv >/dev/null 2>&1; then
        local d
        for d in "$HOME/.local/bin" "$HOME/.cargo/bin" /usr/local/bin; do
            [[ -x "$d/uv" ]] && { export PATH="$d:$PATH"; break; }
        done
    fi

    # Instalador oficial da Astral (docs.astral.sh/uv). O Raspberry Pi OS não
    # empacota o uv no apt, então esta é a via suportada em arm64/armhf.
    # O instalador acrescenta ~/.local/bin ao PATH nos perfis da shell; o export
    # abaixo cobre a sessão atual, que já foi iniciada sem ele.
    if ! command -v uv >/dev/null 2>&1; then
        warn "uv não encontrado — instalando de https://astral.sh/uv/install.sh"
        if (( CHECK_ONLY )); then
            printf '  (check) pularia: instalação do uv\n'
        else
            # mktemp evita o /tmp com nome previsível. A limpeza é explícita em
            # cada saída: um `trap ... RETURN` não é escopado à função e
            # dispararia de novo nas funções seguintes, com a variável já fora
            # de escopo — o que sob `set -u` aborta o script.
            local installer rc=0
            installer="$(mktemp)" || { fail "mktemp falhou — /tmp cheio ou somente-leitura?"; return 1; }
            curl -LsSf https://astral.sh/uv/install.sh -o "$installer" && sh "$installer" || rc=$?
            rm -f "$installer"
            if (( rc )); then
                fail "instalação do uv falhou (rc=$rc) — sem rede? tente: curl -LsSf https://astral.sh/uv/install.sh | sh"
                return 1
            fi
            export PATH="$HOME/.local/bin:$PATH"
        fi
    fi

    if command -v uv >/dev/null 2>&1; then
        ok "uv $(uv --version 2>/dev/null | awk '{print $2}') ($(command -v uv))"
        # Confere se uma shell de login NOVA também acharia o uv. Se não, os
        # scripts continuam funcionando (eles procuram o binário), mas chamar
        # `uv` na mão falharia — então avisamos como corrigir.
        if ! bash -lc 'command -v uv' >/dev/null 2>&1; then
            UV_NOT_ON_LOGIN_PATH=1
        fi
    elif (( ! CHECK_ONLY )); then
        fail "uv indisponível após a instalação — abra uma shell nova e rode de novo"
        return 1
    fi

    local sys_python; sys_python="$(command -v python3)"
    ok "python do sistema: $sys_python ($("$sys_python" -V 2>&1 | awk '{print $2}'))"

    local venv="$REPO_DIR/.venv"
    if [[ -f "$venv/pyvenv.cfg" ]] && grep -q 'include-system-site-packages = true' "$venv/pyvenv.cfg"; then
        ok ".venv já criada com system-site-packages"
    else
        [[ -d "$venv" ]] && warn ".venv existente sem system-site-packages — será recriada"
        run rm -rf "$venv"
        run uv venv --python "$sys_python" --system-site-packages "$venv"
        (( CHECK_ONLY )) || ok ".venv criada"
    fi

    # Base (nicegui/fastapi/uvicorn, do painel web) + --extra pi (gpiozero,
    # mfrc522, spidev, RPLCD, RPi.GPIO).
    # --inexact: preserva os pacotes do sistema visíveis na venv.
    run uv sync --project "$REPO_DIR" --extra pi --inexact
    (( CHECK_ONLY )) || ok "dependências Python instaladas"
}

# ----------------------------------------------------------- 5. sanidade do HW
detect_hardware() {
    step "5/6 Detecção de hardware"

    # ATENÇÃO ao 2>&1: rpicam-hello escreve a lista de câmeras no STDERR.
    # Descartar stderr faz a câmera parecer ausente mesmo funcionando.
    local cam_cmd=""
    local c
    for c in rpicam-hello libcamera-hello; do
        command -v "$c" >/dev/null 2>&1 && { cam_cmd="$c"; break; }
    done
    if [[ -z "$cam_cmd" ]]; then
        warn "rpicam-hello/libcamera-hello ausentes — instale rpicam-apps"
    elif "$cam_cmd" --list-cameras 2>&1 | grep -qi imx219; then
        ok "câmera IMX219 (Camera v2) detectada via $cam_cmd"
    else
        warn "câmera não detectada — rode ./scripts/diag-camera.sh"
    fi

    if [[ -e /dev/i2c-1 ]] && command -v i2cdetect >/dev/null 2>&1; then
        local addrs; addrs="$(i2cdetect -y 1 2>/dev/null | tail -n +2 | grep -oE '\b[0-9a-f]{2}\b' | tr '\n' ' ')"
        if [[ -n "${addrs// /}" ]]; then
            ok "dispositivos I2C: $addrs"
            grep -q '27' <<<"$addrs" || warn "0x27 não encontrado — ajuste I2C_ADDR em src/sentinel/hal/real/display.py"
        else
            warn "nenhum dispositivo I2C — cheque a alimentação e os fios SDA/SCL do LCD"
        fi
    fi

    [[ -e /dev/spidev0.0 ]] && ok "SPI pronto para o RC522" || warn "SPI indisponível — o RFID não vai funcionar"
}

# ------------------------------------------------------- 6. resumo dos pinos
print_pinout() {
    step "6/6 Pinagem esperada (BCM) — confira a montagem"
    cat <<'PINOUT'
  Placa: Freenove Projects Board for Raspberry Pi — os periféricos são soldados,
  os GPIOs abaixo NÃO são ajustáveis (referências ao Tutorial.pdf).

  Câmera v2      conector CSI (cabo flat)
  RFID RC522     SPI0 / CE0, na própria placa            (cap. 25)
  LCD1602 I2C    SDA=GPIO2  SCL=GPIO3  addr 0x27  5V     (cap. 19)
  Teclado 4x4    linhas  = GPIO 16, 20, 21, 26           (cap. 21)
                 colunas = GPIO 19, 13, 6, 5
  LED de status  GPIO 17  (único LED da placa)           (cap. 1)
  Buzzer ativo   GPIO 12                                 (cap. 6)
  Servo (atuador) GPIO 18 — PWM por hardware             (cap. 13)
  Sensor PIR     GPIO 24 — módulo externo, External Port (cap. 22)
  Cadastro       tecla "A" do teclado (a placa não tem botão livre)

  Restrições da placa (pág. 41) que este projeto respeita:
    - relé (GPIO 12) e buzzer ativo dividem o pino: usamos o servo como atuador
    - touch button (GPIO 26) é linha do teclado: o cadastro virou uma tecla
    - servo (GPIO 18) e WS2812: não usamos WS2812
PINOUT
}

# -------------------------------------------------------------------- main
main() {



    
    printf '%sSentinel — setup do Raspberry Pi%s  (repo: %s)\n' "$c_hdr" "$c_reset" "$REPO_DIR"
    (( CHECK_ONLY )) && printf '%smodo --check: nada será alterado%s\n' "$c_warn" "$c_reset"

    require_pi
    install_packages
    enable_interfaces
    setup_groups
    setup_python
    detect_hardware
    print_pinout

    step "Resumo"
    if (( FAILURES )); then
        fail "$FAILURES etapa(s) falharam — veja acima"
        exit 1
    fi
    if (( CHECK_ONLY )); then
        ok "diagnóstico concluído"
        exit 0
    fi
    ok "setup concluído"
    if (( UV_NOT_ON_LOGIN_PATH )); then
        printf '\n  %suv fora do PATH desta shell.%s  make run-pi funciona mesmo assim\n' "$c_warn" "$c_reset"
        printf '  (os scripts localizam o binário), mas para chamar "uv" na mão:\n'
        printf '      source ~/.profile     # ou abra uma shell nova / faça login de novo\n'
    fi
    if (( NEEDS_REBOOT )); then
        printf '\n  %sREINICIE antes de rodar:%s  sudo reboot\n' "$c_warn" "$c_reset"
        printf '  (interfaces do firmware e grupos do usuário só valem após o boot)\n'
    fi
    printf '\n  Depois:  ./scripts/run-pi.sh        # ou: make run-pi\n'
    printf '           ./scripts/setup-pi.sh --check\n\n'
}

main "$@"
