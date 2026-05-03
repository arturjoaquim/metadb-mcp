"""Ponto de entrada principal do MetaDB MCP.

Inicia dois componentes no mesmo processo Python:
- **Servidor Web (dashboard)**: Uvicorn/FastAPI numa thread daemon.
- **Servidor MCP (stdio)**: Comunicação JSON-RPC via stdin/stdout na thread principal.

A estratégia de isolamento redireciona ``sys.stdout`` e ``sys.stderr`` para um
arquivo de log, garantindo que apenas mensagens JSON-RPC do MCP trafeguem pelo
stdout original do processo.
"""

import argparse
import asyncio
import logging
import sys
import threading
from io import TextIOWrapper
from typing import Any, Dict, List, TextIO, Optional

import anyio
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Depends, Response, Cookie
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from core import database
from core.database import initialize_db_manager, secure_connection
from core.auth_service import auth_service, AuthenticationError
from core.mcp_server import mcp
from mcp.server.stdio import stdio_server

# ---------------------------------------------------------------------------
# Modelos de requisição
# ---------------------------------------------------------------------------


class AuthRequest(BaseModel):
    """Modelo para autenticação."""

    username: str
    password: str


class ConnectionRequest(BaseModel):
    """Modelo de dados para requisições de conexão ao banco."""

    conn_name: str
    db_type: str
    host: str
    port: int
    user: str
    password: str
    dbname: str


class SyncRequest(BaseModel):
    """Modelo de dados para requisições de sincronização de tabelas."""

    conn_name: str
    db_type: str
    host: str
    port: int
    user: str
    password: str
    dbname: str
    tables: List[str]


# ---------------------------------------------------------------------------
# Aplicação FastAPI (Dashboard Web)
# ---------------------------------------------------------------------------

app = FastAPI(title="Control Plane Metadados MCP")

app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Renderiza a página principal do dashboard."""
    return templates.TemplateResponse(
        request=request, name="index.html", context={"request": request}
    )


# ---------------------------------------------------------------------------
# Autenticação e Segurança
# ---------------------------------------------------------------------------

async def require_auth(
    request: Request, auth_token: Optional[str] = Cookie(None)
) -> dict[str, Any]:
    """Dependência para validar o token JWT e o estado do banco."""
    if not auth_token:
        raise HTTPException(status_code=401, detail="Não autenticado.")
    
    payload = auth_service.verify_token(auth_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado.")
    
    if not secure_connection.is_unlocked:
        raise HTTPException(status_code=423, detail="Banco de dados está bloqueado.")
        
    return payload


@app.get("/api/auth/status")
async def auth_status() -> Dict[str, Any]:
    """Retorna o estado atual da autenticação e do banco."""
    return {
        "db_exists": auth_service.database_exists(),
        "is_unlocked": secure_connection.is_unlocked,
    }


@app.post("/api/auth/register")
async def register(req: AuthRequest, response: Response) -> Dict[str, str]:
    """Cadastra um novo usuário e inicializa o banco criptografado."""
    try:
        token = auth_service.register(req.username, req.password)
        response.set_cookie(
            key="auth_token",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=auth_service.JWT_EXPIRATION_HOURS * 3600,
        )
        # Inicializa o db_manager agora que o banco está criado e desbloqueado
        initialize_db_manager()
        return {"status": "success", "message": "Banco criado com sucesso."}
    except AuthenticationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/auth/login")
async def login(req: AuthRequest, response: Response) -> Dict[str, str]:
    """Autentica o usuário e desbloqueia o banco."""
    try:
        token = auth_service.login(req.username, req.password)
        response.set_cookie(
            key="auth_token",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=auth_service.JWT_EXPIRATION_HOURS * 3600,
        )
        # Inicializa o db_manager agora que o banco foi desbloqueado
        initialize_db_manager()
        return {"status": "success", "message": "Login efetuado com sucesso."}
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))


@app.post("/api/auth/logout")
async def logout(response: Response) -> Dict[str, str]:
    """Trava o banco e remove o cookie."""
    secure_connection.lock()
    response.delete_cookie(key="auth_token")
    return {"status": "success", "message": "Logout efetuado."}


@app.get("/api/auth/verify", dependencies=[Depends(require_auth)])
async def verify_auth() -> Dict[str, str]:
    """Verifica se o usuário está autenticado (usado no carregamento da página)."""
    return {"status": "success", "message": "Autenticado."}


# ---------------------------------------------------------------------------
# API de Dados (Protegida)
# ---------------------------------------------------------------------------

@app.get("/api/connections", dependencies=[Depends(require_auth)])
async def get_connections() -> Dict[str, List[Dict[str, Any]]]:
    """Retorna todas as conexões salvas no banco local."""
    if not database.db_manager:
        raise HTTPException(status_code=500, detail="Database manager não inicializado.")
    conns: list[dict[str, Any]] = database.db_manager.get_connections()
    return {"connections": conns}


@app.post("/api/tables", dependencies=[Depends(require_auth)])
async def get_tables(req: ConnectionRequest) -> Dict[str, Any]:
    """Lista tabelas do banco remoto e indica quais já estão sincronizadas."""
    if not database.db_manager:
        raise HTTPException(status_code=500, detail="Database manager não inicializado.")

    if not database.db_manager.test_connection(
        req.db_type, req.host, req.port, req.user, req.password, req.dbname
    ):
        raise HTTPException(
            status_code=400,
            detail="Falha na conexão com o banco de dados. Verifique as credenciais.",
        )

    tables: list[str] = database.db_manager.get_all_tables(
        req.db_type, req.host, req.port, req.user, req.password, req.dbname
    )
    synced_tables: list[str] = database.db_manager.get_synced_tables_by_name(req.conn_name)
    return {"tables": tables, "synced_tables": synced_tables}


@app.post("/api/sync", dependencies=[Depends(require_auth)])
async def sync_selected_tables(req: SyncRequest) -> Dict[str, str]:
    """Sincroniza as tabelas selecionadas para o cache local."""
    try:
        if not database.db_manager:
            raise HTTPException(status_code=500, detail="Database manager não inicializado.")
        database.db_manager.sync_tables(
            conn_name=req.conn_name,
            tables_to_sync=req.tables,
            db_type=req.db_type,
            host=req.host,
            port=req.port,
            user=req.user,
            password=req.password,
            dbname=req.dbname,
        )
        return {
            "status": "success",
            "message": f"{len(req.tables)} tabelas sincronizadas com sucesso.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Funções de inicialização
# ---------------------------------------------------------------------------


def _run_web_server(host: str, port: int) -> None:
    """Inicia o Uvicorn numa thread separada com logs silenciados no stdout.

    O Uvicorn é configurado com ``log_config=None`` e ``access_log=False``
    para evitar que qualquer saída seja enviada ao stdout/stderr (que neste
    ponto já foram redirecionados para o arquivo de log).

    Args:
        host: Endereço de bind do servidor web.
        port: Porta de escuta do servidor web.
    """
    config: uvicorn.Config = uvicorn.Config(
        app="main:app",
        host=host,
        port=port,
        log_config=None,
        access_log=False,
        log_level="warning",
    )
    server: uvicorn.Server = uvicorn.Server(config)
    server.run()


async def _run_stdio_mcp(
    original_stdin: TextIO,
    original_stdout: TextIO,
) -> None:
    """Executa o servidor MCP via transporte stdio.

    Utiliza as referências **originais** de stdin/stdout (capturadas antes do
    redirecionamento) para garantir que a comunicação JSON-RPC não seja
    contaminada por logs de outras bibliotecas.

    Args:
        original_stdin: Referência ao ``sys.stdin`` original do processo.
        original_stdout: Referência ao ``sys.stdout`` original do processo.
    """
    stdin_async: anyio.AsyncFile[str] = anyio.wrap_file(
        TextIOWrapper(original_stdin.buffer, encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    )
    stdout_async: anyio.AsyncFile[str] = anyio.wrap_file(
        TextIOWrapper(original_stdout.buffer, encoding="utf-8")  # type: ignore[attr-defined]
    )

    async with stdio_server(stdin=stdin_async, stdout=stdout_async) as (
        read_stream,
        write_stream,
    ):
        await mcp._mcp_server.run(
            read_stream,
            write_stream,
            mcp._mcp_server.create_initialization_options(),
        )


def _parse_args() -> argparse.Namespace:
    """Parseia os argumentos de linha de comando.

    Returns:
        Namespace com os argumentos ``host``, ``port`` e ``log_file``.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="MetaDB MCP — Servidor MCP (stdio) + Dashboard Web",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Endereço de bind do servidor web (padrão: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Porta do servidor web (padrão: 8000)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default="metadb_mcp.log",
        help="Caminho do arquivo de log (padrão: metadb_mcp.log)",
    )
    return parser.parse_args()


def main() -> None:
    """Ponto de entrada principal.

    Fluxo:
        1. Parseia argumentos de linha de comando.
        2. Captura referências originais de ``stdin`` e ``stdout``.
        3. Redireciona ``sys.stdout`` e ``sys.stderr`` para arquivo de log.
        4. Inicia o servidor web (Uvicorn) numa thread daemon.
        5. Executa o servidor MCP (stdio) na thread principal (bloqueante).
    """
    args: argparse.Namespace = _parse_args()

    # 1. Capturar referências originais ANTES de qualquer redirecionamento
    original_stdin: TextIO = sys.stdin
    original_stdout: TextIO = sys.stdout

    # 2. Abrir arquivo de log e redirecionar stdout/stderr globais
    log_file: TextIO = open(args.log_file, "a", encoding="utf-8")  # noqa: SIM115
    sys.stdout = log_file
    sys.stderr = log_file

    # 3. Reconfigurar o logging raiz para usar o arquivo de log
    logging.basicConfig(
        stream=log_file,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        force=True,
    )

    # 4. Iniciar o servidor web numa thread daemon
    web_thread: threading.Thread = threading.Thread(
        target=_run_web_server,
        args=(args.host, args.port),
        daemon=True,
        name="uvicorn-web-server",
    )
    web_thread.start()

    # 5. Executar o servidor MCP stdio na thread principal (bloqueante)
    try:
        asyncio.run(_run_stdio_mcp(original_stdin, original_stdout))
    except KeyboardInterrupt:
        pass
    finally:
        log_file.close()


if __name__ == "__main__":
    main()
