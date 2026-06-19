#!/bin/zsh

cd /Users/thiagoresende/Documents/inteligencia_mercado

echo "Iniciando ambiente virtual..."
source .venv/bin/activate

echo "Verificando projeto Django..."
python manage.py check

echo ""
echo "Servidor iniciado."
echo "Acesse no seu Mac:"
echo "http://127.0.0.1:8000/"
echo ""
echo "Para acessar de outra máquina da rede, use:"
echo "http://IP-DO-SEU-MAC:8000/"
echo ""
echo "Para parar o servidor, pressione CTRL + C."
echo ""

python manage.py runserver 0.0.0.0:8000
