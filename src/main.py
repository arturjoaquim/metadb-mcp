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
import os
import pathlib
import sys
import threading
from io import TextIOWrapper
from typing import TextIO

import anyio
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from shared.utils import network
from interfaces.controllers.web_controller import web_router
from interfaces.controllers.mcp_controller import mcp
from mcp.server.stdio import stdio_server

# ---------------------------------------------------------------------------
# Aplicação FastAPI (Dashboard Web)
# ---------------------------------------------------------------------------

app = FastAPI(title="Control Plane Metadados MCP")

BASE_DIR = pathlib.Path(__file__).parent.resolve()
STATIC_DIR = BASE_DIR / "interfaces" / "web" / "static"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(web_router)


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

    # Encontrar uma porta livre dinamicamente para permitir múltiplas instâncias
    args.port = network.find_free_port(args.host, args.port)
    web_url: str = f"http://{args.host}:{args.port}"
    os.environ["METADB_WEB_URL"] = web_url

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
    logging.info("Servidor MCP iniciado. Dashboard web rodando em: %s", web_url)

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
