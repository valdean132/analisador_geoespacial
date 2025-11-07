#!/usr/bin/env bash

# Define o título da janela (se o terminal suportar)
echo -n -e "\033]0;Servidor da API - Analisador Geoespacial\007"

# Navega para o diretório onde o script está localizado
# Isso garante que os caminhos relativos (como .venv) funcionem
cd "$(dirname "$0")"

echo "----------------------------------------------------"
echo "Ativando o ambiente virtual (.venv)..."
echo "----------------------------------------------------"

# Ativa o ambiente virtual (o caminho é diferente no Linux/macOS)
source .venv/bin/activate

# Verifica se o comando anterior falhou
if [ $? -ne 0 ]; then
    echo "ERRO: Nao foi possivel encontrar ou ativar o ambiente virtual."
    echo "Verifique se a pasta '.venv' existe e se 'source .venv/bin/activate' funciona."
    exit 1
fi

echo "Ambiente ativado com sucesso."
echo ""
echo "----------------------------------------------------"
echo "Iniciando o servidor da API (Uvicorn)..."
echo "----------------------------------------------------"
echo ""
echo "A API estara acessivel em:"
echo " - Localmente: http://127.0.0.1:8000"
echo " - Na rede:    http://<SEU_IP_DE_REDE>:8000 (ex: 172.16.207.86:8000)"
echo ""
echo "Pressione CTRL+C para parar o servidor."
echo ""

# Inicia o servidor Uvicorn escutando em todas as interfaces de rede
uvicorn api.main:app --host 0.0.0.0 --port 8000