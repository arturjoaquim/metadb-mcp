@echo off
REM Script de inicialização plug and play para o MetaDB MCP em sistemas Windows

REM Navega para o diretório onde o script está localizado
set "DIR=%~dp0"
cd /d "%DIR%"

REM Verifica se o diretório do ambiente virtual (venv) existe
if not exist "venv\" (
    echo Ambiente virtual não encontrado. Criando um novo 'venv'... >&2
    
    python -m venv venv
    if errorlevel 1 (
        echo Erro: Falha ao criar o ambiente virtual. Verifique se o Python esta instalado e no PATH. >&2
        exit /b 1
    )
    
    echo Instalando dependências... >&2
    call venv\Scripts\python -m pip install --upgrade pip >&2
    call venv\Scripts\pip install -r requirements.txt >&2
    
    echo Dependências instaladas com sucesso! >&2
)

REM Executa o servidor usando o interpretador do ambiente virtual
venv\Scripts\python src/main.py %*
