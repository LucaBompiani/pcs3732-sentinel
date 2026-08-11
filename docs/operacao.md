# Guia de operação — Sentinel no Raspberry Pi

Como usar o sistema no hardware: cadastrar pessoas, testar acessos e entender o
que cada mensagem do LCD quer dizer. Para instalar e configurar o Pi, ver o
[README](../README.md).

---

## 1. Antes de começar

```bash
make check-pi        # SPI, I2C, câmera, venv — sem alterar nada
make diag-camera     # se a câmera estiver em dúvida
make run-pi          # sobe a aplicação
```

O menu aparece **no terminal**; os avisos ao usuário aparecem **no LCD**. As duas
telas são usadas ao mesmo tempo: o operador digita no terminal (nome do usuário),
a pessoa sendo cadastrada interage com o teclado, a câmera e o leitor RFID.

```
1) Cadastrar usuario (Fator 1 + Fator 2)     <- só banco, sem hardware
2) Simular tentativa de acesso               <- só banco, sem hardware
3) Ciclo de acesso via hardware (HAL)        <- USA o hardware
4) Cadastro via hardware (HAL)               <- USA o hardware
5) Sair
```

As opções **3 e 4** são as que exercitam câmera, teclado, RFID, LCD e servo. As
opções 1 e 2 mexem apenas no banco e servem para conferir a lógica sem depender
da montagem.

### Teclado — teclas de controle

| Tecla | Função |
|---|---|
| `0`–`9` | dígitos do PIN |
| `#` | **confirma** o que foi digitado |
| `*` | apaga o último dígito |
| `A` | inicia o cadastro e confirma o consentimento |

Nada é enviado enquanto você não apertar `#`. Se errar, `*` apaga dígito a
dígito.

### Retorno visual do que você digita

A segunda linha do LCD mostra o progresso a cada tecla, para você saber que ela
foi registrada — a varredura do teclado ignora pressões muito curtas, e sem esse
retorno você digitaria às cegas:

```
Defina seu PIN          Defina seu PIN
termine com #     ->    ***
```

Por padrão os dígitos são **mascarados** (`SENTINEL_PIN_ECHO=mask`): aparece o
comprimento, não o segredo. Para conferir a montagem do teclado — por exemplo
suspeitando de tecla trocada — use `SENTINEL_PIN_ECHO=plain`, que mostra os
dígitos de verdade.

> Deixe `plain` apenas durante a depuração: qualquer pessoa que olhe a tela lê o
> PIN. `off` desliga o retorno por completo.

---

## 2. Caso de uso: cadastrar a primeira pessoa

**Objetivo:** registrar rosto + PIN da Ana.
**Quem participa:** o operador (sabe o PIN mestre) e a Ana.

| # | O que fazer | LCD mostra |
|---|---|---|
| 1 | No terminal, escolha `4` | — |
| 2 | Digite `ana` e Enter | `Novo cadastro` / `Tecle A p/ inic` |
| 3 | Ana aperta `A` no teclado | `PIN do operador` / `termine com #` |
| 4 | **Operador** digita o PIN mestre e `#` | `PIN do operador` / `***` → `Olhe p/ camera` |
| 5 | Ana olha para a câmera, parada | `Capturando 1/5` … `5/5` |
| 6 | — | `Defina seu PIN` / `termine com #` |
| 7 | Ana digita o PIN dela e `#` | `Defina seu PIN` / `****` → `Passe o cartao` |
| 8 | Ana encosta o cartão, **ou espera ~15 s** | `Aceita cadastro?` / `Tecle A p/ sim` |
| 9 | Ana aperta `A` | `Cadastro OK` |

O terminal confirma com `CADASTRO CONCLUIDO`.

**PIN mestre** é o do operador, não o da Ana — ele autoriza o cadastro (RF08).
Padrão `0000`; troque em `.env` (`SENTINEL_MASTER_PIN`) antes de usar pra valer.

**O passo 8 sempre espera o cartão**, mesmo se você só quer PIN. Isso é
esperado: basta aguardar o timeout. Um dos dois fatores basta — se nem PIN nem
cartão forem apresentados, o cadastro é recusado com `Sem PIN/cartao`.

### Se o rosto não for detectado

O LCD alterna para `Rosto nao visto` / `Olhe p/ camera` e continua tentando. O
sistema faz até 6 capturas por amostra desejada (30 no total, com o padrão de 5
amostras) antes de desistir com `Cadastro negado` / `Rosto nao visto`.

Para a detecção funcionar: rosto **frontal**, sem contraluz, a ~40–60 cm da
câmera, sem óculos escuros ou máscara. O detector Haar é frontal — rosto muito
inclinado não é encontrado.

---

## 3. Caso de uso: acesso autorizado

| # | O que fazer | LCD mostra |
|---|---|---|
| 1 | No terminal, escolha `3` | `Aproxime-se` |
| 2 | Ana se posiciona (o PIR detecta) | — |
| 3 | Ana olha para a câmera | `Fator 2` / `PIN ou cartao` |
| 4 | Ana digita o PIN e `#`, **ou** passa o cartão | `Fator 2` / `****` → `Bem-vindo` / `ana` |
| 5 | — | servo destrava por 5 s, LED aceso, 1 bipe |

Aqui, diferente do cadastro, **os dois fatores são lidos em paralelo**: o que
chegar primeiro (PIN ou cartão) é usado.

---

## 4. Caso de uso: acesso negado

### Rosto desconhecido (falha no Fator 1)

`Acesso negado` / `Face nao reconh.` — LED pisca, 3 bipes. O segundo fator nem
é pedido: sem identidade não há a quem comparar o PIN. Também é o que aparece
quando ninguém é detectado no quadro.

### PIN ou cartão errado (falha no Fator 2)

`Acesso negado` / `Fator 2 invalido`. O rosto foi reconhecido, mas o segundo
fator não confere. **Esta falha conta para o bloqueio.**

### Usuário bloqueado

`Bloqueado` / `ana`. Após 3 falhas **seguidas** do segundo fator, a pessoa fica
60 s bloqueada — nesse período nem o PIN correto é aceito, e o segundo fator
sequer é solicitado (RF10). O bloqueio é por usuário, expira sozinho e sobrevive
a reinício.

Falhas do Fator 1 **não** contam: rosto não reconhecido pode ser iluminação ou
ângulo, não credencial errada.

Ajuste com `SENTINEL_MAX_FAILURES` e `SENTINEL_LOCKOUT_SECONDS`.

---

## 5. Roteiro de demonstração (~5 min)

1. `make run-pi`
2. Opção `4` → cadastre a pessoa A com PIN `1234`
3. Opção `3` → pessoa A + PIN `1234` → **autorizado**, servo gira
4. Opção `3` → pessoa B (não cadastrada) → **negado no Fator 1**
5. Opção `3` → pessoa A + PIN `9999` → **negado no Fator 2**
6. Repita o passo 5 mais duas vezes → **bloqueado por 60 s**
7. Opção `3` → pessoa A + PIN `1234` → ainda **bloqueado** (mostra o RF10)

O passo 7 é o que diferencia bloqueio de simples negação: a credencial está
certa e mesmo assim é recusada.

---

## 6. Calibração do reconhecimento facial

O reconhecimento compara o rosto capturado com as amostras do cadastro por
distância qui-quadrado. `SENTINEL_FACE_THRESHOLD` (padrão `0.55`) é a distância
máxima aceita:

- **muito baixo** → não reconhece nem quem está cadastrado (falsos negativos)
- **muito alto** → aceita a pessoa errada (falsos positivos — falha de segurança)

Em faces sintéticas, a distância entre duas capturas da mesma pessoa fica em
~0.12 e entre pessoas diferentes em ~1.2–1.4, o que sustenta o padrão. **Com
rostos reais esses números mudam** e o valor precisa ser conferido na montagem.

Procedimento: cadastre duas pessoas, rode acessos repetidos e observe. Se a
pessoa certa é recusada com frequência, suba em passos de 0.05. Se alguém é
confundido com outro, desça — e prefira errar para o lado rigoroso, já que um
falso positivo abre a porta.

Qualidade da captura ajuda mais que o limiar: iluminação frontal constante,
mesma distância no cadastro e no acesso, e as 5 amostras com pequenas variações
de expressão e ângulo (não 5 fotos idênticas).

---

## 7. Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `Rosto nao visto` sempre | contraluz, rosto inclinado, longe demais | luz de frente, rosto frontal, ~50 cm |
| Reconhece a pessoa errada | limiar alto demais | reduzir `SENTINEL_FACE_THRESHOLD` |
| Nunca reconhece ninguém | limiar baixo demais, ou cadastro ruim | subir o limiar; recadastrar com boa luz |
| LCD apagado ou com blocos | contraste | ajustar o potenciômetro atrás do módulo |
| LCD não escreve | endereço I2C diferente de `0x27` | `i2cdetect -y 1` e ajustar `I2C_ADDR` em [display.py](../src/sentinel/hal/real/display.py) |
| Tecla errada aparece | linhas/colunas trocadas | `SENTINEL_PIN_ECHO=plain` para ver o que chega; conferir [keypad.py](../src/sentinel/hal/real/keypad.py) contra o Tutorial cap. 21 |
| Tecla não aparece no LCD | pressão curta demais, ou eco `off` | segurar ~0,3 s; conferir `SENTINEL_PIN_ECHO` |
| Cartão não é lido | SPI desabilitado, cartão incompatível | `make check-pi`; usar cartão Mifare 13,56 MHz |
| Servo não gira | alimentação insuficiente | servo em fonte externa, GND comum com o Pi |
| Câmera não detectada | pilha legada, cabo, sem reboot | `make diag-camera` |
| `Cascata de Haar não encontrada` | pacote `opencv-data` ausente | `sudo apt install -y opencv-data` |

---

## 8. Privacidade (LGPD, RNF04)

O que é guardado no banco:

- **PIN e UID do cartão:** apenas hash SHA-256 com salt por usuário
- **Rosto:** apenas o vetor de características LBPH — a imagem é descartada logo
  após a captura e nunca é gravada em disco
- **Eventos:** usuário, resultado e horário, para auditoria (RF09)

O passo de consentimento (`Aceita cadastro?`) é obrigatório e o sistema opera
100% offline.

Para apagar os dados de todos os usuários: `make clean` remove o `sentinel.db`.
