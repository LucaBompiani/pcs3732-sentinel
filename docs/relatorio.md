# Sentinel: Controle de Acesso Físico com Autenticação Multifator (MFA) em Raspberry Pi 3

**Disciplina:** PCS3732 - Laboratório de Processadores
**Plataforma:** Raspberry Pi 3 Model B+

**Kit de referência:** Freenove (Projects Board / Ultimate Starter Kit for Raspberry Pi)

**Membros do grupo:** Bruno Nicola Viola Ladosky, Luca Bompiani e Paulo José Cardoso Racy Ferreira

> **Status do documento:** entrega final (Semana 4). O fluxo MFA está **implementado e funcional**, com Camada de Abstração de Hardware (HAL) de dois backends (`mock`, para PC/testes, e `real`, para o Raspberry Pi), Fator 1 por reconhecimento facial LBPH próprio, Fator 2 por PIN ou cartão RFID, bloqueio por tentativas (RF10) e aplicativo de janela. Os requisitos incorporam a avaliação por pares da Semana 2 (origem do RF10). A validação da solução é feita por uma suíte de **testes automatizados** (seção 7).

---

## 1. Motivação/Justificativa

Sistemas de controle de acesso baseados em um único fator (cartão, senha ou biometria isolada) têm vulnerabilidades conhecidas: cartões são clonáveis/perdíveis, senhas são compartilháveis, e biometria isolada (em particular reconhecimento facial) é suscetível a *spoofing* simples (foto impressa, vídeo em tela). A proposta deste projeto é um sistema de controle de acesso físico embarcado que exige **dois fatores independentes**, são eles reconhecimento facial (algo que o usuário *é*) combinado a um segundo fator possuído/conhecido (PIN ou cartão RFID), para autorizar a abertura de uma fechadura, operando de forma totalmente local (*edge computing*, sem dependência de nuvem).

Projetos similares consultados como referência de motivação:
- Sistemas comerciais de controle de acesso corporativo com biometria + cartão (ex.: catracas com leitor facial e RFID combinados).
- Trabalhos acadêmicos de reconhecimento facial em Raspberry Pi (com bibliotecas como `face_recognition`/dlib ou OpenCV; ver referências).
- Documentação do kit Freenove, usado como base de componentes de hardware do projeto.

A escolha por MFA é o refinamento central em relação à proposta anterior, pois um único fator biométrico, mesmo bem calibrado, não é suficiente como controle de acesso robusto, e a arquitetura precisa tratar a autenticação como a combinação obrigatória de dois mecanismos, não como fator único com um fallback opcional em caso de falha.

## 2. Objetivos

### 2.1 Objetivo geral

Projetar e implementar um sistema embarcado de controle de acesso físico com autenticação multifator (reconhecimento facial + PIN/cartão RFID) sobre Raspberry Pi 3 Model B+, operando de forma local e registrando eventos para auditoria.

### 2.2 Objetivos específicos

- Detectar presença de uma pessoa no ponto de acesso e capturar sua imagem.
- Reconhecer a face capturada contra uma base local de usuários cadastrados (Fator 1).
- Exigir um segundo fator independente (PIN via teclado matricial ou cartão RFID) para confirmar a identidade (Fator 2).
- Autorizar a abertura do acesso somente quando ambos os fatores forem validados.
- Sinalizar visual e sonoramente o resultado (autorizado/negado) em cada etapa.
- Permitir cadastro local de novos usuários com os dois fatores associados (enrolamento).
- Registrar eventos (tentativas, sucesso/falha por fator, cadastros) com data/hora para auditoria.
- Operar de forma 100% offline e tolerante a falhas de energia.

## 3. Requisitos

### 3.1 Requisitos funcionais

- **RF01:** Detectar a presença de uma pessoa no ponto de acesso. Critério de aceite: a detecção de presença dispara a captura em menos de 500 ms.
- **RF02:** Capturar imagem e detectar face no quadro (Fator 1, entrada). Critério de aceite: a face frontal deve ser detectada a 0,5–1,5 m da câmera.
- **RF03:** Reconhecer a face contra a base de cadastrados (Fator 1, verificação). Critério de aceite: a decisão de identificado/não identificado deve ocorrer em até 3 s após o enquadramento.
- **RF04:** Solicitar o segundo fator (PIN ou cartão RFID) somente após o Fator 1 identificar um candidato (Fator 2, entrada). Critério de aceite: o LCD deve solicitar o segundo fator e o tempo de espera deve ser limitado por um timeout configurável.
- **RF05:** Validar o segundo fator contra o cadastro do usuário identificado no Fator 1 (Fator 2, verificação). Critério de aceite: o PIN ou UID do cartão deve corresponder ao usuário do Fator 1, e não a qualquer outro usuário da base.
- **RF06:** Abrir o acesso somente quando os Fatores 1 e 2 forem válidos para o mesmo usuário. Critério de aceite: a fechadura deve ser acionada por 5 s, com feedback visual (LED) e sonoro.
- **RF07:** Negar e sinalizar caso qualquer um dos fatores falhe. Critério de aceite: deve ocorrer sinalização visual de negação (LED piscando), bipe distinto, acesso mantido travado e registro do motivo da falha (qual fator).
- **RF08:** Cadastrar usuários localmente com os dois fatores (enrolamento). Critério de aceite: o fluxo deve ocorrer por gatilho físico + PIN mestre de operador, com captura de N amostras faciais e associação do segundo fator (PIN definido ou cartão lido).
- **RF09:** Registrar eventos com data e hora (tentativa, resultado por fator, acesso concedido/negado e cadastro). Critério de aceite: o log deve ser persistente e consultável após reinício.
- **RF10:** Bloquear temporariamente o usuário após um número configurável de falhas seguidas do segundo fator, limitando ataques de força bruta. Critério de aceite: atingido o limite, novas tentativas daquele usuário devem ser negadas mesmo com o fator correto, sem que o segundo fator seja solicitado, e devem gerar registro com resultado `BLOQUEADO`; o bloqueio deve expirar sozinho após o prazo configurado, valer apenas para o usuário em questão e sobreviver a um reinício do sistema.

> **Origem do RF10:** sugestão da avaliação por pares da Semana 2 (*Peer Review* — Grupo J, issue #2 do repositório), de bloquear o usuário que erra a autenticação algumas vezes. Optou-se por bloquear o **usuário** e não a fechadura inteira, para que a penalidade não se transforme em negação de serviço contra os demais cadastrados, e por contar apenas falhas do **Fator 2**: uma falha do Fator 1 pode decorrer de iluminação ou ângulo, não de credencial incorreta.

### 3.2 Requisitos não funcionais

- **RNF01:** Minimizar a taxa de falsa aceitação (FAR) do sistema pela combinação dos fatores. Critério de aceite: a FAR composta deve ser estimada empiricamente e aproximar-se de FAR(Fator 1) × FAR(Fator 2).
- **RNF02:** Operar 100% offline. Critério de aceite: nenhuma função deve depender de Internet.
- **RNF03:** Ser tolerante a falhas de energia. Critério de aceite: o estado da base de usuários e dos logs deve ser persistido, e a fechadura deve operar em modo fail-secure.
- **RNF04:** Garantir privacidade conforme a LGPD. Critério de aceite: dados biométricos devem ser armazenados localmente apenas como vetores de características, o PIN e o UID do cartão devem ser armazenados com hash (SHA-256 com salt por usuário) e deve existir consentimento no cadastro.
- **RNF05:** Manter o tempo total de autenticação dos dois fatores dentro de um limite aceitável. Critério de aceite: o tempo total deve ser inferior ou igual a 8 s, do início da presença até a decisão final, a calibrar nos testes.

> **Definição do segundo fator (resolvida na Semana 2):** ambos os mecanismos foram implementados como **alternativos entre si** em cada tentativa — o usuário confirma com **PIN** (teclado matricial 4×4) **ou** com **cartão RFID** (leitor MFRC522). O primeiro fator apresentado que corresponder ao cadastro do usuário identificado no Fator 1 é aceito.

## 4. Diagramas da arquitetura

### 4.1 Arquitetura física

Blocos: sensor de presença (PIR), câmera CSI, teclado matricial 4×4 e leitor RFID (2º fator, alternativos), LCD1602, indicadores (LED e buzzer), atuador (relé + fechadura solenoide ou, em demonstração, servomotor), tudo conectado à Raspberry Pi 3. Fonte editável: [docs/diagramas/arquitetura_fisica.d2](diagramas/arquitetura_fisica.d2).

![Arquitetura física](figuras/arquitetura_fisica.svg)

> **Restrições da placa (Freenove Projects Board).** Na montagem real, os periféricos são soldados e três limitações da placa moldaram o projeto (Tutorial, pág. 41): (i) relé e buzzer ativo dividem o **GPIO 12**, então o atuador de demonstração é o servo (GPIO 18) e o buzzer fica com o 12; (ii) o *touch button* (GPIO 26) coincide com uma linha do teclado, então o cadastro (RF08) é disparado pela **tecla `A`**; (iii) a placa tem um **único LED** (GPIO 17), então `led_green` acende contínuo e `led_red` **pisca** o mesmo LED para distinguir concedido de negado. O contrato do HAL preserva a semântica de dois indicadores mesmo sobre esse hardware.

### 4.2 Arquitetura de software

Organização em camadas (Aplicação / Serviços / Infraestrutura / SO), com o serviço de decisão MFA isolado dos dois serviços de verificação de fator (facial e PIN/RFID). Fonte editável: [docs/diagramas/arquitetura_software.d2](diagramas/arquitetura_software.d2).

![Arquitetura de software](figuras/arquitetura_software.svg)

O código reflete essa divisão em `src/sentinel/`:

- **`app/`** — orquestração: máquina de estados (`VIGIA → FATOR1 → FATOR2 → ATUA`), CLI e aplicativo de janela (Tkinter).
- **`services/`** — lógica de domínio, independente de hardware: Fator 1 (`face_detector`, `face_encoding`, `face_recognition`, `face_preview`), Fator 2 (`second_factor`), bloqueio por tentativas (`lockout`) e a decisão MFA (`decision`).
- **`infra/`** — persistência SQLite (`db`, `users_repository`, `events_repository`) e segurança (`security`: hash SHA-256 com salt).
- **`hal/`** — **Camada de Abstração de Hardware**: `interfaces.py` define os contratos dos dispositivos e `factory.py` monta o *bundle* conforme o backend. Há dois backends que implementam os mesmos contratos: `mock/` (simulado, roda em qualquer PC e sustenta os testes) e `real/` (drivers do Raspberry Pi, com *import* tardio para não exigir bibliotecas de hardware no PC). Essa separação é o que permite exercitar toda a lógica de autenticação fora do dispositivo.

### 4.3 Fluxo de autenticação (máquina de estados)

Os dois fatores estão em **série obrigatória (E)**, de modo que a falha em qualquer um interrompe o fluxo, e não em esquema de fallback (OU). Fonte editável: [docs/diagramas/fluxo_mfa.d2](diagramas/fluxo_mfa.d2).

![Fluxo de autenticação MFA](figuras/fluxo_mfa.svg)

> A rastreabilidade entre requisitos e testes está consolidada na seção 7.1.

## 5. Ferramentas utilizadas

### 5.1 Linguagens
- Python 3 (aplicação principal, pipeline de visão, controle de GPIO). `requires-python >= 3.11`, alinhado ao Python do Raspberry Pi OS Bookworm, pré-requisito para enxergar os módulos de hardware do apt.

### 5.2 Bibliotecas/Frameworks

Reflete o que está efetivamente em uso no código (`pyproject.toml`):

- **OpenCV (`cv2`)** — usado **apenas para detecção de rosto** (classificador Haar) e recorte do quadro. Vem do apt (`python3-opencv`), pois depende de bindings C++ do sistema.
- **LBPH próprio** — a extração de características faciais (Local Binary Patterns Histograms) é **implementada no projeto** ([`face_encoding.py`](../src/sentinel/services/face_encoding.py)), em `stdlib` puro, e **não** usa `dlib`/`face_recognition` nem `cv2.face`. Motivos na seção 5.4.
- **`Picamera2`** — captura via câmera CSI no Pi (apt `python3-picamera2`).
- **`gpiozero` + `lgpio` / `RPi.GPIO`** — controle de GPIO (PIR, LED, buzzer, servo, teclado matricial).
- **`mfrc522` + `spidev`** — leitura do cartão RFID via SPI.
- **`RPLCD`** — controle do LCD1602 via I2C.
- **`sqlite3`** (padrão do Python) — persistência de usuários (embeddings + segundo fator com hash) e log de eventos.
- **`tkinter`** (padrão do Python; pacote `python3-tk`) — aplicativo de janela que substitui a CLI no Pi, exibindo a captura e espelhando o LCD sem servidor nem navegador.
- **`pytest`** — suíte de testes automatizados (ponto extra).

> `numpy`, `cv2`, `picamera2` e `libcamera` **não** são instalados por `pip`: vêm do apt e são vistos pela `.venv` graças a `--system-site-packages`. As dependências instaláveis por `pip` apenas no dispositivo ficam no *extra* `pi` do `pyproject.toml`.

### 5.3 Hardware
- Raspberry Pi 3 Model B+ (Freenove Projects Board / Ultimate Starter Kit).
- Sensor PIR HC-SR501.
- Câmera Raspberry Pi Camera Module v2 (CSI): item externo ao kit.
- Teclado matricial 4×4 e leitor RFID MFRC522 (segundo fator, alternativos entre si).
- LCD1602 I2C, LED de status único (GPIO 17), buzzer ativo (GPIO 12).
- Módulo relé + fechadura solenoide 12 V (fechadura e fonte externas ao kit): atuador de referência, *fail-secure*.
- Servomotor SG90 (GPIO 18, PWM por hardware): atuador **alternativo, apenas para demonstração**, quando não se dispõe da fechadura de 12 V e da sua fonte independente. Não substitui a solenoide no requisito, pois um servo não é *fail-secure*: em queda de energia ele permanece no ângulo em que estava, enquanto o relé desacionado mantém a solenoide travada (RNF03). A seleção do atuador é feita em tempo de inicialização, por variável de ambiente (`SENTINEL_LOCK_TYPE`).

### 5.4 Reconhecimento facial (Fator 1) — decisão de projeto

Pipeline: **detecção Haar** (OpenCV) recorta o rosto → normalização para 64×64 em tons de cinza com equalização de histograma → suavização 3×3 → **códigos LBP** de 8 vizinhos → **histograma espacial** numa grade 4×4 → vetor de 4096 dimensões. A identificação compara o vetor do quadro com as amostras do cadastro por **distância qui-quadrado** e aceita a mais próxima se ficar abaixo de `SENTINEL_FACE_THRESHOLD`. O LBPH foi implementado no projeto, em vez de `dlib`/`face_recognition` ou `cv2.face.LBPHFaceRecognizer`, por três razões:

- **LGPD (RNF04).** O recognizer do OpenCV treina a partir das *imagens*, o que obrigaria a persisti-las. Calculando o histograma diretamente, o banco guarda apenas o vetor de características — a imagem é descartada após a captura e nunca vai a disco.
- **Portabilidade.** `cv2.face` vive nos módulos *contrib*, que nem toda distribuição empacota; aqui o `cv2` é necessário apenas para detectar e recortar o rosto.
- **Testabilidade.** O algoritmo é `stdlib` puro, então roda e é verificado em qualquer PC, sem câmera nem OpenCV — os testes injetam um detector falso com faces sintéticas.

No acesso, a identificação usa uma **rajada** de quadros: o primeiro que reconhecer alguém encerra a busca, e só há negação quando todos falham. O critério de aceitação de cada quadro é o mesmo — a rajada apenas compensa falsos negativos banais do detector (piscada, micro-movimento, autofoco).

## 6. Metodologia de desenvolvimento

Desenvolvimento incremental, com entregas semanais versionadas no GitHub (uma Release por semana) e histórico de commits granular por funcionalidade/etapa, evitando *mega commits*. Uso de branches e Pull Requests durante o desenvolvimento, convergindo para uma única branch `main` na entrega final.

O código é organizado por camada (`app` / `services` / `infra` / `hal`), com documentação no padrão *docstring* do Google. A **Camada de Abstração de Hardware** (backends `mock` e `real` atrás de contratos comuns) é o pilar metodológico: permite desenvolver e testar toda a lógica de autenticação no PC, contra o backend `mock`, e trocar para o hardware real apenas por variável de ambiente. Isso viabilizou uma suíte de testes automatizados que roda em CI/PC sem depender do dispositivo. O provisionamento do Pi é script idempotente (`scripts/setup-pi.sh`), e a configuração é feita por variáveis de ambiente (`SENTINEL_*`), documentadas no README.

## 7. Testes / Resultados obtidos

A validação da solução é feita por uma suíte de **testes automatizados**, executáveis no PC contra o backend `mock` sem necessidade do hardware — possibilidade que decorre diretamente da separação `mock`/`real` do HAL. Essa estratégia cobre a lógica de todos os requisitos funcionais e dos requisitos não funcionais verificáveis por software.

### 7.1 Rastreabilidade requisito → teste (resultados obtidos)

A suíte `pytest` cobre os serviços de domínio, a infraestrutura e o HAL. Executada com `make test` (`PYTHONPATH=src uv run pytest`) no PC de desenvolvimento (backend `mock`), **170 casos passam e 20 são pulados** por exigirem display gráfico (testes da GUI) ou `cv2`/câmera (testes de captura real) — recursos ausentes no PC headless, presentes no Pi.

Cobertura por requisito:

| Requisito | Arquivo(s) de teste | O que valida |
|---|---|---|
| RF01 (presença) | `test_state_machine`, `test_hal_mock` | disparo da captura ao detectar presença |
| RF02 (detecção de face) | `test_face_detector_cascade` | recorte de rosto no quadro |
| RF03 (reconhecimento) | `test_face_encoding`, `test_face_recognition`, `test_face_recognition_real` | LBPH, distância qui-quadrado e limiar |
| RF04 (solicitar 2º fator / timeout) | `test_second_factor_timing`, `test_state_machine` | espera limitada e ordem dos fatores |
| RF05 (vínculo do 2º fator) | `test_second_factor`, `test_second_factor_rfid`, `test_users_repository`, `test_users_repository_card` | PIN/cartão só valem para o usuário do Fator 1 |
| RF06 (abrir acesso) | `test_decision`, `test_state_machine`, `test_hal_servo_lock` | acesso só com os dois fatores; acionamento do atuador |
| RF07 (negar e sinalizar) | `test_decision`, `test_indicators_beep`, `test_state_machine` | negação, bipe e sinalização |
| RF08 (cadastro) | `test_enrollment` | enrolamento dos dois fatores |
| RF09 (log de eventos) | `test_events_repository` | persistência com data/hora |
| RF10 (bloqueio por tentativas) | `test_lockout`, `test_second_factor_timing` | limite, expiração, por usuário, sobrevive a reinício |
| RNF04 (privacidade) | `test_security`, `test_face_encoding` | hash com salt; só vetores, nunca imagens |
| HAL / configuração / GUI | `test_hal_factory`, `test_hal_mock`, `test_hal_real_pins`, `test_config`, `test_pin_echo`, `test_face_burst_and_preview`, `test_gui`, `test_state_machine_hardware` | contratos dos dispositivos, pinagem travada, GUI |

## 8. Conclusões

Os objetivos centrais foram atingidos: o sistema executa o ciclo MFA completo (presença → Fator 1 facial → Fator 2 PIN/RFID → atuação), com cadastro local, log de auditoria e bloqueio por tentativas. Todos os requisitos funcionais (RF01–RF10) têm implementação e cobertura por testes automatizados. Entre os não funcionais, RNF02 (offline) e RNF04 (privacidade) são atendidos por construção; RNF03 (persistência) é exercitado pelos testes de bloqueio e de eventos, que sobrevivem a reinício do processo, e o comportamento *fail-secure* decorre da escolha do atuador (relé + solenoide); a lógica de tempo do RNF05 é verificada pelos testes de *timing* do segundo fator. A estimativa empírica da FAR composta (RNF01), que exige um conjunto de faces reais, fica como trabalho futuro.

Principais dificuldades e lições: as restrições físicas da Freenove Projects Board (GPIOs compartilhados, LED único, ausência da solenoide de 12 V) exigiram adaptar o HAL sem quebrar os contratos; a decisão de implementar o LBPH em vez de reutilizar bibliotecas prontas foi motivada por LGPD e testabilidade, e mostrou-se acertada por permitir validar o Fator 1 fora do Pi. A separação `mock`/`real` foi determinante para a produtividade e para viabilizar a suíte de testes automatizados.

Trabalhos futuros: medição empírica de FAR/FRR e latência com rostos reais no hardware, calibração do limiar facial (`SENTINEL_FACE_THRESHOLD`, hoje ajustado com faces sintéticas) e avaliação de robustez a *spoofing* (detecção de vivacidade).

## Referências (ABNT NBR 6023)

> AHONEN, T.; HADID, A.; PIETIKÄINEN, M. Face description with local binary patterns: application to face recognition. **IEEE Transactions on Pattern Analysis and Machine Intelligence**, v. 28, n. 12, p. 2037–2041, 2006.

> BRADSKI, G. The OpenCV Library. **Dr. Dobb's Journal of Software Tools**, 2000. Disponível em: https://opencv.org. Acesso em: 21 ago. 2026.

> BRASIL. **Lei nº 13.709, de 14 de agosto de 2018** (Lei Geral de Proteção de Dados Pessoais, LGPD). Diário Oficial da União: Brasília, DF, 15 ago. 2018.

> FREENOVE. **Freenove Ultimate Starter Kit for Raspberry Pi — Tutorial**. Shenzhen: Freenove Technology, 2023. Disponível em: https://github.com/Freenove/Freenove_Ultimate_Starter_Kit_for_Raspberry_Pi. Acesso em: 28 jul. 2026.

> GEITGEY, A. **face_recognition: the world's simplest facial recognition API for Python**. 2018. Disponível em: https://github.com/ageitgey/face_recognition. Acesso em: 28 jul. 2026.

> OJALA, T.; PIETIKÄINEN, M.; MÄENPÄÄ, T. Multiresolution gray-scale and rotation invariant texture classification with local binary patterns. **IEEE Transactions on Pattern Analysis and Machine Intelligence**, v. 24, n. 7, p. 971–987, 2002.

> RASPBERRY PI FOUNDATION. **Raspberry Pi Camera Module documentation**. 2024. Disponível em: https://www.raspberrypi.com/documentation/accessories/camera.html. Acesso em: 28 jul. 2026.
