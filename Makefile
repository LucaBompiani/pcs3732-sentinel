.DEFAULT_GOAL := help
.PHONY: help run run-pi setup-pi check-pi diag-camera diag-hw install-pi test clean

## Lista os alvos disponíveis
help:
	@echo 'Sentinel — alvos disponíveis:'
	@echo
	@grep -E '^## |^[a-zA-Z_-]+:' $(MAKEFILE_LIST) \
	  | sed -E 'N; s/^## (.*)\n([a-zA-Z_-]+):.*/\2|\1/; t; D' \
	  | awk -F'|' '{ printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2 }'
	@echo
	@echo 'No PC use "run" (backend mock). No Raspberry Pi: setup-pi -> reboot -> run-pi.'

## Roda a CLI com backend mock (qualquer PC)
run:
	PYTHONPATH=src uv run --frozen python src/sentinel/app/cli.py

## Provisiona o Raspberry Pi (apt, SPI/I2C/camera, grupos, venv) — uma vez
setup-pi:
	./scripts/setup-pi.sh

## Diagnostica o Raspberry Pi sem alterar nada
check-pi:
	./scripts/setup-pi.sh --check

## Diagnostica a camera CSI passo a passo (firmware -> libcamera -> picamera2)
diag-camera:
	./scripts/diag-camera.sh

## Testa cada periferico isoladamente (buzzer, led, display, servo, teclado...)
diag-hw:
	./scripts/diag-hardware.py $(DEV)

## Sobe o Sentinel no Raspberry Pi (carrega .env e valida o hardware)
run-pi:
	./scripts/run-pi.sh

## Instala apenas as dependencias Python de hardware
install-pi:
	uv sync --extra pi --inexact

## Executa a suite de testes
test:
	uv run --frozen pytest tests/ -v

## Remove __pycache__ e o banco SQLite local
clean:
	find . -name __pycache__ -exec rm -rf {} +
	rm -f sentinel.db
