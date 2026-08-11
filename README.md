# Sentinel

Sistema embarcado de controle de acesso físico com **autenticação multifator (MFA)** em Raspberry Pi 3 Model B+, combinando reconhecimento facial (Fator 1) com PIN ou cartão RFID (Fator 2) para autorizar a abertura de uma fechadura. Operação 100% local (edge computing).

Projeto da disciplina PCS3732 – Laboratório de Processadores (Poli-USP).

> **Status:** lógica de MFA e orquestração implementadas, com **Camada de Abstração de Hardware (HAL)** de dois backends: `mock` (roda em qualquer PC, usado nos testes) e `real` (drivers do Raspberry Pi). O segundo fator aceita **PIN ou cartão RFID**. Reconhecimento facial real (OpenCV LBPH) e drivers de GPIO/câmera/RFID rodam somente no Pi. Ver [docs/relatorio.md](docs/relatorio.md).

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
      factory.py        #   monta o HAL conforme o backend
      mock/             #   backend simulado (PC/testes)
      real/             #   drivers do Raspberry Pi (import tardio)
tests/                  # testes automatizados (60 casos)
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

No dispositivo, instale as dependências de hardware e selecione o backend real:

```bash
make install-pi          # uv sync --extra pi (gpiozero, picamera2, mfrc522, RPLCD, opencv...)
make run-real            # SENTINEL_BACKEND=real
```

Os pinos GPIO usados por cada driver estão definidos no topo dos módulos em `src/sentinel/hal/real/` e devem ser ajustados conforme a montagem física.

### Configuração (variáveis de ambiente)

| Variável | Padrão | Descrição |
|---|---|---|
| `SENTINEL_BACKEND` | `mock` | Backend de hardware: `mock` ou `real` |
| `SENTINEL_DB_PATH` | `sentinel.db` | Caminho do banco SQLite |
| `SENTINEL_RELAY_SECONDS` | `5.0` | Tempo de acionamento da fechadura (RF06) |
| `SENTINEL_FACTOR2_TIMEOUT` | `15.0` | Timeout de espera do 2º fator (RF04) |
| `SENTINEL_PRESENCE_TIMEOUT` | *(bloqueia)* | Timeout de espera por presença |
| `SENTINEL_TOTAL_TIMEOUT` | `8.0` | Orçamento total de autenticação (RNF05) |
| `SENTINEL_FACE_SAMPLES` | `5` | Amostras faciais coletadas no cadastro (RF08) |
| `SENTINEL_MASTER_PIN` | `0000` | PIN mestre do operador para enrolamento (RF08) |

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
