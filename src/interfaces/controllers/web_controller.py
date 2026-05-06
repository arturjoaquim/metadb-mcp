"""Controladores Web FastAPI."""

import pathlib
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, Depends, Response, Cookie
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from interfaces.dtos.requests import AuthRequest, ConnectionRequest, SyncRequest
from application.services.dashboard_service import DashboardService, DashboardServiceError
from infrastructure.security.auth_service import AuthenticationError

def init_web_controller(dashboard_service: DashboardService) -> APIRouter:
    web_router = APIRouter()

    TEMPLATE_DIR = pathlib.Path(__file__).parent.parent / "web" / "templates"
    templates = Jinja2Templates(directory=str(TEMPLATE_DIR.resolve()))


    async def require_auth(
        request: Request, auth_token: Optional[str] = Cookie(None)
    ) -> dict[str, Any]:
        """Dependência para validar o token JWT e o estado do banco."""
        if not auth_token:
            raise HTTPException(status_code=401, detail="Não autenticado.")
        
        payload = dashboard_service.verify_token(auth_token)
        if not payload:
            raise HTTPException(status_code=401, detail="Token inválido ou expirado.")
        
        if not dashboard_service.is_unlocked():
            raise HTTPException(status_code=423, detail="Banco de dados está bloqueado.")
            
        return payload


    @web_router.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        """Renderiza a página principal do dashboard."""
        return templates.TemplateResponse(
            request=request, name="index.html", context={"request": request}
        )


    @web_router.get("/api/auth/status")
    async def auth_status() -> Dict[str, Any]:
        """Retorna o estado atual da autenticação e do banco."""
        return {
            "db_exists": dashboard_service.database_exists(),
            "is_unlocked": dashboard_service.is_unlocked(),
        }


    @web_router.post("/api/auth/register")
    async def register(req: AuthRequest, response: Response) -> Dict[str, str]:
        """Cadastra um novo usuário e inicializa o banco criptografado."""
        try:
            token = dashboard_service.register(req.username, req.password)
            response.set_cookie(
                key="auth_token",
                value=token,
                httponly=True,
                samesite="lax",
                # A constante JWT_EXPIRATION_HOURS foi mantida dentro de auth_service, então usamos 8 fixo aqui ou expomos no orquestrador
                max_age=8 * 3600,
            )
            return {"status": "success", "message": "Banco criado com sucesso."}
        except AuthenticationError as e:
            raise HTTPException(status_code=400, detail=str(e))


    @web_router.post("/api/auth/login")
    async def login(req: AuthRequest, response: Response) -> Dict[str, str]:
        """Autentica o usuário e desbloqueia o banco."""
        try:
            token = dashboard_service.login(req.username, req.password)
            response.set_cookie(
                key="auth_token",
                value=token,
                httponly=True,
                samesite="lax",
                max_age=8 * 3600,
            )
            return {"status": "success", "message": "Login efetuado com sucesso."}
        except AuthenticationError as e:
            raise HTTPException(status_code=401, detail=str(e))


    @web_router.post("/api/auth/logout")
    async def logout(response: Response) -> Dict[str, str]:
        """Trava o banco e remove o cookie."""
        dashboard_service.logout()
        response.delete_cookie(key="auth_token")
        return {"status": "success", "message": "Logout efetuado."}


    @web_router.get("/api/auth/verify", dependencies=[Depends(require_auth)])
    async def verify_auth() -> Dict[str, str]:
        """Verifica se o usuário está autenticado (usado no carregamento da página)."""
        return {"status": "success", "message": "Autenticado."}


    @web_router.get("/api/connections", dependencies=[Depends(require_auth)])
    async def get_connections() -> Dict[str, List[Dict[str, Any]]]:
        """Retorna todas as conexões salvas no banco local."""
        try:
            conns = dashboard_service.get_connections()
            return {"connections": conns}
        except DashboardServiceError as e:
            raise HTTPException(status_code=500, detail=str(e))


    @web_router.post("/api/tables", dependencies=[Depends(require_auth)])
    async def get_tables(req: ConnectionRequest) -> Dict[str, Any]:
        """Lista tabelas do banco remoto e indica quais já estão sincronizadas."""
        try:
            return dashboard_service.get_tables(
                db_type=req.db_type,
                host=req.host,
                port=req.port,
                user=req.user,
                password=req.password,
                dbname=req.dbname,
                conn_name=req.conn_name,
            )
        except DashboardServiceError as e:
            raise HTTPException(status_code=400, detail=str(e))


    @web_router.post("/api/sync", dependencies=[Depends(require_auth)])
    async def sync_selected_tables(req: SyncRequest) -> Dict[str, str]:
        """Sincroniza as tabelas selecionadas para o cache local."""
        try:
            dashboard_service.sync_tables(
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
        except DashboardServiceError as e:
            raise HTTPException(status_code=500, detail=str(e))

    return web_router
