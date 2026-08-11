#!/usr/bin/env bash
#
# diag-camera.sh — diagnostica a câmera CSI (Camera v2 / IMX219) no Raspberry Pi.
#
# Não altera nada. Roda os testes na ordem em que a câmera pode falhar: firmware
# -> device tree -> kernel -> libcamera -> picamera2. O primeiro passo que falhar
# é a causa; os seguintes tendem a falhar em cascata.
#
# Uso: ./scripts/diag-camera.sh
#
set -uo pipefail   # sem -e: queremos rodar TODOS os testes, mesmo com falhas

c_reset=$'\033[0m'; c_ok=$'\033[32m'; c_warn=$'\033[33m'; c_err=$'\033[31m'; c_hdr=$'\033[1;36m'
step() { printf '\n%s==> %s%s\n' "$c_hdr" "$1" "$c_reset"; }
ok()   { printf '  %s[ ok ]%s %s\n' "$c_ok" "$c_reset" "$1"; }
warn() { printf '  %s[warn]%s %s\n' "$c_warn" "$c_reset" "$1"; }
bad()  { printf '  %s[FALHA]%s %s\n' "$c_err" "$c_reset" "$1"; }

cfg=/boot/firmware/config.txt
[[ -f "$cfg" ]] || cfg=/boot/config.txt

step "0. Sistema"
printf '  modelo : %s\n' "$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo '?')"
printf '  SO     : %s\n' "$(. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME")"
printf '  kernel : %s\n' "$(uname -r)"
printf '  config : %s\n' "$cfg"
printf '  uptime : %s\n' "$(uptime -p 2>/dev/null)"

step "1. config.txt — o que está declarado"
grep -nE '^[[:space:]]*(camera_auto_detect|start_x|gpu_mem|dtoverlay|display_auto_detect)' "$cfg" 2>/dev/null \
    | sed 's/^/  /' || warn "nada encontrado"

# A pilha legada (start_x=1) e a moderna (libcamera) são mutuamente exclusivas:
# com start_x=1 o firmware toma a câmera para si e o libcamera não a enxerga.
if grep -qE '^[[:space:]]*start_x=1' "$cfg" 2>/dev/null; then
    bad "start_x=1 presente: pilha LEGADA ativa, libcamera/picamera2 não verão a câmera"
    printf '      corrija: sudo sed -i "s/^start_x=1/# start_x=1/" %s && sudo reboot\n' "$cfg"
else
    ok "sem start_x=1 (pilha legada desativada)"
fi

if grep -qE '^[[:space:]]*camera_auto_detect=1' "$cfg" 2>/dev/null; then
    ok "camera_auto_detect=1 declarado"
else
    bad "camera_auto_detect=1 AUSENTE — rode ./scripts/setup-pi.sh"
fi

if grep -qE '^[[:space:]]*gpu_mem=' "$cfg" 2>/dev/null; then
    warn "gpu_mem definido: desnecessário no stack KMS e pode atrapalhar"
fi

step "2. Device tree — o firmware carregou o sensor?"
if [[ -d /proc/device-tree/soc ]]; then
    found="$(find /proc/device-tree -maxdepth 4 -iname '*imx219*' 2>/dev/null | head -3)"
    if [[ -n "$found" ]]; then
        ok "nó imx219 presente no device tree"
        printf '%s\n' "$found" | sed 's/^/      /'
    else
        bad "nenhum nó imx219 — firmware não detectou o sensor (cabo? reboot?)"
    fi
fi

step "3. Kernel — o driver ligou?"
if dmesg 2>/dev/null | grep -iE 'imx219|unicam|csi' | tail -12 | grep -q .; then
    dmesg 2>/dev/null | grep -iE 'imx219|unicam|csi' | tail -12 | sed 's/^/  /'
else
    warn "nada sobre imx219/unicam no dmesg (tente: sudo dmesg | grep -i imx219)"
fi
[[ -e /dev/video0 ]] && ok "/dev/video0 existe" || warn "/dev/video0 ausente"

step "4. I2C do sensor — a câmera responde no barramento?"
# A Camera v2 fica em um barramento I2C dedicado (i2c-0 ou i2c-10), NÃO no
# i2c-1 do LCD. Endereço 0x10 = IMX219.
for bus in 0 10 11; do
    [[ -e /dev/i2c-$bus ]] || continue
    if command -v i2cdetect >/dev/null 2>&1; then
        if sudo i2cdetect -y "$bus" 2>/dev/null | grep -qE '\b10\b'; then
            ok "sensor respondendo em i2c-$bus, endereço 0x10"
        fi
    fi
done

step "5. libcamera"
cam_cmd=""
for c in rpicam-hello libcamera-hello; do
    command -v "$c" >/dev/null 2>&1 && { cam_cmd="$c"; break; }
done
if [[ -z "$cam_cmd" ]]; then
    bad "nem rpicam-hello nem libcamera-hello instalados"
    printf '      corrija: sudo apt install -y rpicam-apps  (ou libcamera-apps)\n'
else
    ok "usando $cam_cmd"
    printf '  --- saída de "%s --list-cameras" ---\n' "$cam_cmd"
    "$cam_cmd" --list-cameras 2>&1 | sed 's/^/  /'
fi

step "6. picamera2 (o que o Sentinel usa)"
if python3 -c 'import picamera2' 2>/dev/null; then
    ok "picamera2 importável no python3 do sistema"
    python3 - <<'PY' 2>&1 | sed 's/^/  /'
from picamera2 import Picamera2
info = Picamera2.global_camera_info()
print(f"cameras vistas pelo picamera2: {len(info)}")
for c in info:
    print("  ", c)
PY
else
    bad "picamera2 NÃO importável — sudo apt install -y python3-picamera2"
fi

step "Resumo"
cat <<'FIM'
  Ordem de causas mais comuns:
    1. Não reiniciou depois do setup-pi.sh          -> sudo reboot
    2. start_x=1 no config.txt (pilha legada)       -> comente e reinicie
    3. Cabo flat: solto, invertido, ou no conector
       errado. No Pi 3B+ o conector da câmera fica
       entre o HDMI e o conector de áudio (o outro,
       perto do Ethernet, é DISPLAY/DSI).
       Contatos metálicos voltados para o HDMI.     -> reassente com o Pi desligado
    4. Cabo solto no lado da PLACA DA CÂMERA        -> confira as duas pontas
FIM
