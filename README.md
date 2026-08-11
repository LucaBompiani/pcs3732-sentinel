# Sentinel

Sistema embarcado de controle de acesso físico com **autenticação multifator (MFA)** em Raspberry Pi 3 Model B+, combinando reconhecimento facial (Fator 1) com PIN ou cartão RFID (Fator 2) para autorizar a abertura de uma fechadura. Operação 100% local (edge computing).

Projeto da disciplina PCS3732 – Laboratório de Processadores (Poli-USP).

> **Status:** lógica de MFA e orquestração implementadas, com **Camada de Abstração de Hardware (HAL)** de dois backends: `mock` (roda em qualquer PC, usado nos testes) e `real` (drivers do Raspberry Pi). O segundo fator aceita **PIN ou cartão RFID**, com **bloqueio temporário após falhas seguidas**. O acesso pode ser atuado por fechadura solenoide (via relé) ou por servomotor (demonstração). Reconhecimento facial real (OpenCV LBPH) e drivers de GPIO/câmera/RFID rodam somente no Pi. Ver [docs/relatorio.md](docs/relatorio.md).

## Estrutura do repositório

```
docs/
  relatorio.md          # documentação do projeto (motivação, requisitos, arquitetura, testes)
  diagramas/            # fontes editáveis dos diagramas (D2)
  figuras/              # diagramas renderizados (SVG/PNG)
src/
  sentinel/
    config.py           # configuração via variáveis de ambiente (backend + tunables)
    app/                # máquina de estados / orquestração (state_machine, cli)
    services/           # reconhecimento facial, verificação do 2º fator, decisão MFA
    infra/              # persistência SQLite, segurança (hash+salt), repositórios
    hal/                # Camada de Abstração de Hardware
      interfaces.py     #   contratos dos dispositivos
      factory.py        #   monta o HAL conforme o backend e o atuador
      mock/             #   backend simulado (PC/testes)
      real/             #   drivers do Raspberry Pi (import tardio)
tests/                  # testes automatizados (75 casos)
```

## Como rodar

Requer [uv](https://docs.astral.sh/uv/). Na raiz do projeto:

```bash
make run     # CLI com backend mock (padrão) — roda em qualquer PC
make test    # executa a suíte de testes
```

Ou diretamente:

```bash
PYTHONPATH=src uv run python src/sentinel/app/cli.py
```

A CLI permite cadastrar usuários (PIN e/ou cartão RFID), simular tentativas de acesso e exercitar o ciclo completo dirigido pelo HAL.

### Execução no Raspberry Pi (backend real)

Todo o provisionamento está em `scripts/setup-pi.sh` — roda **uma vez por cartão SD** e é idempotente:

```bash
make setup-pi     # pacotes apt, SPI/I2C/câmera, grupos, venv, deps, diagnóstico
sudo reboot       # necessário na primeira vez (firmware + grupos)
cp .env.example .env && $EDITOR .env
make run-pi       # sobe a aplicação com backend real
```

O que o `setup-pi.sh` faz:

1. **apt** — `python3-picamera2`, `python3-opencv`, `python3-numpy`, `python3-lgpio`, `i2c-tools`, `libcap-dev`.
2. **Interfaces do firmware** — `dtparam=spi=on` (RC522), `dtparam=i2c_arm=on` (LCD1602) e `camera_auto_detect=1` em `config.txt`, via `raspi-config nonint`.
3. **Grupos** — adiciona o usuário a `gpio`, `spi`, `i2c`, `video`, `dialout`, para não precisar de `sudo`.
4. **Python** — instala o `uv` se faltar e cria a `.venv` a partir do **python3 do sistema** com `--system-site-packages`, depois `uv sync --extra pi --inexact`.
5. **Diagnóstico** — confere se a IMX219 (Camera v2) aparece, varre o barramento I2C atrás do `0x27` do LCD e valida `/dev/spidev0.0`.
6. **Pinagem** — imprime o mapa de pinos esperado para conferir a montagem.

Para só diagnosticar, sem alterar nada: `make check-pi` (`./scripts/setup-pi.sh --check`).

O `run-pi.sh` carrega o `.env` (sem sobrescrever variáveis já exportadas na shell), valida que SPI/I2C/venv estão prontos — falhando com mensagem clara em vez de um `ImportError` no meio da inicialização do HAL — e chama a CLI. Aceita `--mock` para depurar a lógica no próprio Pi sem tocar no hardware.

> **Por que `--system-site-packages`:** `picamera2`, `libcamera` e `cv2` dependem de bindings C++ compilados contra as bibliotecas do sistema e **não são instaláveis por pip** — vêm do apt. Uma venv isolada (ou um Python gerenciado pelo `uv`) não os enxerga. Por isso `requires-python` é `>=3.11`, o Python do Raspberry Pi OS Bookworm: o backend real precisa rodar no interpretador que tem esses módulos.

### Pinagem (Freenove Projects Board)

O hardware é a **Freenove Projects Board for Raspberry Pi**: os periféricos vêm soldados, então os GPIOs **não são ajustáveis** — são os do `Tutorial.pdf`. As constantes ficam no topo dos módulos em `src/sentinel/hal/real/` e estão travadas por `tests/test_hal_real_pins.py`.

| Periférico | GPIO (BCM) | Tutorial |
|---|---|---|
| Câmera v2 | conector CSI | — |
| RFID RC522 | SPI0 / CE0 | cap. 25 |
| LCD1602 | I2C `0x27` (SDA 2, SCL 3), 5V | cap. 19 |
| Teclado 4x4 — linhas | 16, 20, 21, 26 | cap. 21 |
| Teclado 4x4 — colunas | 19, 13, 6, 5 | cap. 21 |
| LED de status | 17 | cap. 1 |
| Buzzer ativo | 12 | cap. 6 |
| Servo (atuador) | 18 | cap. 13 |
| Sensor PIR | 24 (módulo externo) | cap. 22 |

Três restrições da placa (Tutorial, pág. 41) moldaram o projeto:

- **Relé e buzzer ativo dividem o GPIO 12.** Como a montagem não tem a solenoide de 12 V, o atuador é o servo (GPIO 18) e o buzzer fica com o 12. A fábrica **recusa** `SENTINEL_LOCK_TYPE=solenoid` no backend real, com mensagem explicando a troca necessária, em vez de estourar um `GPIOPinInUse` no meio da montagem do HAL.
- **O touch button (GPIO 26) é a linha 3 do teclado.** Não dá para usar os dois, então o cadastro (RF08) é disparado pela **tecla `A`** — o `EnrollButton` do HAL reaproveita a instância do teclado em vez de reivindicar um GPIO próprio.
- **A placa tem um único LED (GPIO 17)**, não um par verde/vermelho. O contrato do HAL foi mantido: `led_green` acende contínuo e `led_red` **pisca** o mesmo LED, distinguindo concedido de negado.

### Configuração (variáveis de ambiente)

| Variável | Padrão | Descrição |
|---|---|---|
| `SENTINEL_BACKEND` | `mock` | Backend de hardware: `mock` ou `real` |
| `SENTINEL_LOCK_TYPE` | `solenoid` | Atuador do acesso: `solenoid` ou `servo` |
| `SENTINEL_DB_PATH` | `sentinel.db` | Caminho do banco SQLite |
| `SENTINEL_RELAY_SECONDS` | `5.0` | Tempo de acionamento da fechadura (RF06) |
| `SENTINEL_FACTOR2_TIMEOUT` | `15.0` | Timeout de espera do 2º fator (RF04) |
| `SENTINEL_PRESENCE_TIMEOUT` | *(bloqueia)* | Timeout de espera por presença |
| `SENTINEL_TOTAL_TIMEOUT` | `8.0` | Orçamento total de autenticação (RNF05) |
| `SENTINEL_FACE_SAMPLES` | `5` | Amostras faciais coletadas no cadastro (RF08) |
| `SENTINEL_MASTER_PIN` | `0000` | PIN mestre do operador para enrolamento (RF08) |
| `SENTINEL_MAX_FAILURES` | `3` | Falhas seguidas do 2º fator até bloquear (RF10) |
| `SENTINEL_LOCKOUT_SECONDS` | `60.0` | Duração do bloqueio temporário (RF10) |

### Bloqueio por tentativas (RF10)

Após `SENTINEL_MAX_FAILURES` falhas **seguidas do segundo fator**, o usuário fica bloqueado por `SENTINEL_LOCKOUT_SECONDS` — durante o bloqueio, nem o PIN/cartão correto é aceito, e o segundo fator sequer é solicitado. O bloqueio é **por usuário** (os demais continuam acessando), expira sozinho e é persistido em relógio de parede, sobrevivendo a reinício (RNF03). Falhas do Fator 1 não contam: face não reconhecida pode ser iluminação ou ângulo, não credencial errada.

### Atuador: fechadura solenoide ou servomotor

`SENTINEL_LOCK_TYPE=servo` troca o relé + fechadura solenoide por um servo (GPIO 18, o pino de PWM por hardware) — útil para demonstrar o sistema sem a fechadura de 12 V e sua fonte independente, que são externas ao kit.

> ⚠️ O servo **não é fail-secure**: em queda de energia ele permanece no ângulo em que estava, enquanto o relé desacionado mantém a solenoide travada (RNF03). O servo é modo de demonstração; o atuador do requisito continua sendo a solenoide.

### Privacidade (LGPD, RNF04)

PIN e UID de cartão são armazenados apenas como **hash SHA-256 com salt por usuário** — nunca em texto plano. Dados faciais são guardados apenas como **vetores de características** (embeddings), nunca imagens. O enrolamento inclui etapa de consentimento. O sistema opera 100% offline.

## Diagramas

Para renderizar os diagramas de arquitetura (requer [D2](https://d2lang.com/tour/install)):

```bash
d2 docs/diagramas/arquitetura_fisica.d2 docs/figuras/arquitetura_fisica.svg
d2 docs/diagramas/arquitetura_software.d2 docs/figuras/arquitetura_software.svg
d2 docs/diagramas/fluxo_mfa.d2 docs/figuras/fluxo_mfa.svg
```

## Documentação

Ver [docs/relatorio.md](docs/relatorio.md).
