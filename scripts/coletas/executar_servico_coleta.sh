#!/bin/bash
set -euo pipefail

SERVICO="${1:-}"

if [ -z "$SERVICO" ]; then
    echo "ERRO: informe o serviço. Exemplo: servico_01"
    exit 1
fi

cd /opt/inteligencia_mercado

echo "============================================================"
echo "Início da coleta do serviço: $SERVICO"
echo "Data/hora: $(date)"
echo "============================================================"

flock -n /tmp/inteligencia_mercado_coleta.lock \
xvfb-run -a /opt/inteligencia_mercado/.venv/bin/python manage.py executar_coletas \
    --servico "$SERVICO"

echo "============================================================"
echo "Fim da coleta do serviço: $SERVICO"
echo "Data/hora: $(date)"
echo "============================================================"
