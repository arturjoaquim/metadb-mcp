#!/bin/bash
# Script de inicialização plug and play para o MetaDB MCP em sistemas Unix (Linux/macOS)

# Navega para o diretório onde o script está localizado
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
cd "$DIR" || exit

# Verifica se o diretório do ambiente virtual (venv) existe
if [ ! -d "venv" ]; then
    echo "Ambiente virtual não encontrado. Criando um novo 'venv'..." >&2
    
    # Tenta usar python3, se não encontrar, tenta python
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        echo "Erro: Python não encontrado no sistema. Por favor, instale o Python 3.9+." >&2
        exit 1
    fi

    $PYTHON_CMD -m venv venv
    
    echo "Instalando dependências..." >&2
    ./venv/bin/pip install --upgrade pip >&2
    ./venv/bin/pip install -r requirements.txt >&2
    
    echo "Dependências instaladas com sucesso!" >&2
fi

# Executa o servidor usando o interpretador do ambiente virtual
# O uso do 'exec' substitui o processo atual pelo python, garantindo que os sinais (SIGINT, etc) sejam repassados corretamente
exec ./venv/bin/python src/main.py "$@"
