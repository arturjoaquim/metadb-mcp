from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from infrastructure.database.models import DBConnection


class ConnectionDAO:
    """DAO para gerenciamento de conexões (DBConnection)."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, conn_id: int) -> Optional[DBConnection]:
        return self.session.query(DBConnection).filter(DBConnection.id == conn_id).first()

    def get_by_name(self, name: str) -> Optional[DBConnection]:
        return self.session.query(DBConnection).filter_by(name=name).first()

    def get_all(self) -> List[Dict[str, Any]]:
        """Retorna todas as conexões salvas com seus atributos."""
        conns = self.session.query(DBConnection).all()
        return [
            {
                "name": c.name,
                "db_type": c.db_type,
                "host": c.host,
                "port": c.port,
                "user": c.user,
                "dbname": c.dbname,
                "driver_path": c.driver_path,
            }
            for c in conns
        ]

    def save(
        self,
        name: str,
        db_type: str,
        host: str,
        port: int,
        user: str,
        dbname: str,
        driver_path: Optional[str] = None,
    ) -> int:
        """Persiste ou atualiza uma conexão pelo nome."""
        conn = self.get_by_name(name)
        if not conn:
            conn = DBConnection(
                name=name,
                db_type=db_type,
                host=host,
                port=port,
                user=user,
                dbname=dbname,
                driver_path=driver_path,
            )
            self.session.add(conn)
        else:
            conn.db_type = db_type
            conn.host = host
            conn.port = port
            conn.user = user
            conn.dbname = dbname
            conn.driver_path = driver_path
        self.session.commit()
        return int(conn.id)  # type: ignore
