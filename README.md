# Sentinel

Sistema embarcado de controle de acesso físico com **autenticação multifator (MFA)** em Raspberry Pi 3 Model B+, combinando reconhecimento facial (Fator 1) com PIN ou cartão RFID (Fator 2) para autorizar a abertura de uma fechadura. Operação 100% local (edge computing).

Projeto da disciplina PCS3732 – Laboratório de Processadores (Poli-USP).

> **Status:** Semana 1 do desenvolvimento incremental com estruturação do projeto. Requisitos, arquitetura e escolha do segundo fator (PIN vs. RFID) ainda em definição. Ver [docs/relatorio.md](docs/relatorio.md) para o documento completo.

## Estrutura do repositório

```
docs/
  relatorio.md        # documentação do projeto (motivação, requisitos, arquitetura, testes)
  diagramas/           # fontes editáveis dos diagramas (D2)
  figuras/              # diagramas renderizados (SVG/PNG)
src/
  sentinel/
    app/                # máquina de estados / orquestração
    services/           # reconhecimento facial, verificação do 2º fator, decisão MFA, log
    infra/               # captura de câmera, GPIO, persistência, LCD
tests/                  # testes automatizados
```

## Como rodar

Projeto ainda não possui implementação funcional. Instruções de instalação/execução serão adicionadas conforme o código for implementado nas próximas entregas.

Para renderizar os diagramas de arquitetura (requer [D2](https://d2lang.com/tour/install)):

```bash
d2 docs/diagramas/arquitetura_fisica.d2 docs/figuras/arquitetura_fisica.svg
d2 docs/diagramas/arquitetura_software.d2 docs/figuras/arquitetura_software.svg
d2 docs/diagramas/fluxo_mfa.d2 docs/figuras/fluxo_mfa.svg
```

## Documentação

Ver [docs/relatorio.md](docs/relatorio.md).
