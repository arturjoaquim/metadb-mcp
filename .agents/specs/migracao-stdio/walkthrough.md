# Walkthrough — Migração SSE → stdio (v2.0.0)

## Resumo

Migração completa do transporte MCP de **SSE (Server-Sent Events)** para **stdio nativo**, mantendo o dashboard web e o servidor MCP no mesmo processo Python com isolamento de stdout.

## Alterações Realizadas

### [main.py](file:///home/artur/ambiente-de-trabalho/workspace_python/mcp_metadb/main.py) — Reescrita completa

- **Removida** a montagem SSE (`app.mount("/mcp", mcp.sse_app())`)
- **Adicionado** argparse com `--host`, `--port` e `--log-file`
- **Implementado** isolamento de stdout:
  - `sys.stdin` e `sys.stdout` originais são capturados antes de qualquer operação
  - `sys.stdout` e `sys.stderr` globais são redirecionados para arquivo de log
  - O transporte stdio do MCP recebe as referências originais via `anyio.wrap_file()`
- **Servidor web** roda em thread daemon (`_run_web_server()`)
- **Servidor MCP** roda na thread principal (`_run_stdio_mcp()`)

```diff:main.py
from fastapi import FastAPI, Request, Form, Depends, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn

from core.database import db_manager
from core.mcp_server import mcp

app = FastAPI(title="Control Plane Metadados MCP")

app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")


class ConnectionRequest(BaseModel):
    conn_name: str
    db_type: str
    host: str
    port: int
    user: str
    password: str
    dbname: str


class SyncRequest(BaseModel):
    conn_name: str
    db_type: str
    host: str
    port: int
    user: str
    password: str
    dbname: str
    tables: List[str]


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request, name="index.html", context={"request": request}
    )


@app.get("/api/connections")
async def get_connections() -> Dict[str, List[Dict[str, Any]]]:
    conns = db_manager.get_connections()
    return {"connections": conns}


@app.post("/api/tables")
async def get_tables(req: ConnectionRequest) -> Dict[str, Any]:
    if not db_manager.test_connection(
        req.db_type, req.host, req.port, req.user, req.password, req.dbname
    ):
        raise HTTPException(
            status_code=400,
            detail="Falha na conexão com o banco de dados. Verifique as credenciais.",
        )

    tables = db_manager.get_all_tables(
        req.db_type, req.host, req.port, req.user, req.password, req.dbname
    )
    synced_tables = db_manager.get_synced_tables_by_name(req.conn_name)
    return {"tables": tables, "synced_tables": synced_tables}


@app.post("/api/sync")
async def sync_selected_tables(req: SyncRequest) -> Dict[str, str]:
    try:
        db_manager.sync_tables(
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


# --- MCP SSE Server Transport ---
# Montamos o app gerado pelo FastMCP
app.mount("/mcp", mcp.sse_app())

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
===
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
from typing import Any, Dict, List, TextIO

import anyio
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from core.database import db_manager
from core.mcp_server import mcp
from mcp.server.stdio import stdio_server

# ---------------------------------------------------------------------------
# Modelos de requisição
# ---------------------------------------------------------------------------


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


@app.get("/api/connections")
async def get_connections() -> Dict[str, List[Dict[str, Any]]]:
    """Retorna todas as conexões salvas no banco local."""
    conns: list[dict[str, Any]] = db_manager.get_connections()
    return {"connections": conns}


@app.post("/api/tables")
async def get_tables(req: ConnectionRequest) -> Dict[str, Any]:
    """Lista tabelas do banco remoto e indica quais já estão sincronizadas."""
    if not db_manager.test_connection(
        req.db_type, req.host, req.port, req.user, req.password, req.dbname
    ):
        raise HTTPException(
            status_code=400,
            detail="Falha na conexão com o banco de dados. Verifique as credenciais.",
        )

    tables: list[str] = db_manager.get_all_tables(
        req.db_type, req.host, req.port, req.user, req.password, req.dbname
    )
    synced_tables: list[str] = db_manager.get_synced_tables_by_name(req.conn_name)
    return {"tables": tables, "synced_tables": synced_tables}


@app.post("/api/sync")
async def sync_selected_tables(req: SyncRequest) -> Dict[str, str]:
    """Sincroniza as tabelas selecionadas para o cache local."""
    try:
        db_manager.sync_tables(
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
```

---

### [sse_proxy.py](file:///home/artur/ambiente-de-trabalho/workspace_python/mcp_metadb/utils-for-client/sse_proxy.py) — Removido

O proxy SSE→stdio se tornou obsoleto com a adoção de stdio nativo.

---

### [README.md](file:///home/artur/ambiente-de-trabalho/workspace_python/mcp_metadb/README.md) — Reescrito

- Toda documentação atualizada para refletir transporte stdio
- Instruções de configuração para Cursor, Kiro/Cline/Roo Code e Gemini CLI
- Nova seção sobre logs e argumentos de linha de comando
- Removidas referências ao SSE e ao proxy

---

### [CHANGELOG.md](file:///home/artur/ambiente-de-trabalho/workspace_python/mcp_metadb/CHANGELOG.md) — Nova versão 2.0.0

Breaking change documentado com categorias `Changed` e `Removed`.

---

### [.gitignore](file:///home/artur/ambiente-de-trabalho/workspace_python/mcp_metadb/.gitignore) — Atualizado

Adicionado `metadb_mcp.log`.

---

## Verificação

| Teste | Resultado |
|-------|-----------|
| Sintaxe do `main.py` (AST parse) | ✅ OK |
| Processo inicia sem saída no stdout | ✅ OK (exit code 124 = timeout esperado) |
| Dashboard web (`GET /`) | ✅ HTTP 200 |
| API (`GET /api/connections`) | ✅ JSON válido retornado |
| Isolamento de stdout (nenhum log vazou) | ✅ Verificado |
