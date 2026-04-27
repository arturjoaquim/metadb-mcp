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
