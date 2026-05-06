"""Gerenciador de conexão segura com SQLCipher (Singleton Thread-Safe).

Mantém uma única instância de conexão SQLCipher ativa após autenticação.
A conexão é compartilhada entre a thread do Dashboard (Uvicorn) e a
thread principal (MCP stdio) usando ``check_same_thread=False``.
"""

import logging
import threading
from pathlib import Path
from typing import Optional

import sqlcipher3  # type: ignore[import-untyped]
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

logger: logging.Logger = logging.getLogger(__name__)

# Caminho padrão do banco de dados criptografado
DB_FILE_PATH: Path = Path("mcp_cache.db")


class SecureConnectionError(Exception):
    """Exceção para falhas na conexão segura com o banco."""


class SecureConnectionManager:
    """Singleton thread-safe que gerencia o ciclo de vida da conexão SQLCipher.

    Responsabilidades:
        - Manter uma única instância de Engine/SessionLocal após desbloqueio.
        - Fornecer sessions para o Dashboard (thread web) e MCP (thread principal).
        - Expor estado (locked/unlocked) para consulta pelo frontend.
        - Garantir thread-safety via ``check_same_thread=False``.

    A chave derivada externamente (Argon2id) é passada como raw hex para
    o SQLCipher, bypassando o PBKDF2 interno e evitando dupla KDF.
    """

    _instance: Optional["SecureConnectionManager"] = None
    _init_lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "SecureConnectionManager":
        """Garante instância única (Singleton)."""
        with cls._init_lock:
            if cls._instance is None:
                instance: SecureConnectionManager = super().__new__(cls)
                instance._engine = None
                instance._session_factory = None
                instance._is_unlocked = False
                instance._conn_lock = threading.Lock()
                cls._instance = instance
            return cls._instance

    # ------------------------------------------------------------------ #
    # API Pública
    # ------------------------------------------------------------------ #

    def unlock(self, derived_key_hex: str) -> None:
        """Abre a conexão SQLCipher usando a chave derivada (hex).

        Fluxo:
            1. Cria Engine com dialeto ``sqlite+pysqlcipher`` e
               ``module=sqlcipher3``.
            2. Registra evento ``connect`` para enviar ``PRAGMA key``
               com chave raw ``x'...'`` a cada nova conexão raw.
            3. Valida a chave com ``SELECT count(*) FROM sqlite_master``.
            4. Cria SessionLocal e marca ``is_unlocked=True``.
            5. Cria tabelas ORM se necessário (``Base.metadata.create_all``).

        Args:
            derived_key_hex: Chave de 32 bytes em formato hexadecimal
                             (64 caracteres hex).

        Raises:
            SecureConnectionError: Se a chave for inválida ou o banco
                                   não puder ser aberto.
        """
        with self._conn_lock:
            if self._is_unlocked:
                logger.info("Banco já está desbloqueado.")
                return

            db_path: str = str(DB_FILE_PATH.resolve())
            raw_key_pragma: str = f"x'{derived_key_hex}'"

            engine: Engine = create_engine(
                f"sqlite+pysqlcipher://:{raw_key_pragma}@/{db_path}",
                module=sqlcipher3,
                connect_args={"check_same_thread": False},
                pool_pre_ping=True,
            )

            # Registrar PRAGMA key em cada conexão raw do pool
            @event.listens_for(engine, "connect")
            def _set_cipher_pragmas(
                dbapi_connection: sqlcipher3.Connection,
                connection_record: object,
            ) -> None:
                cursor: sqlcipher3.Cursor = dbapi_connection.cursor()
                cursor.execute(f"PRAGMA key = \"{raw_key_pragma}\"")
                cursor.execute("PRAGMA encoding = 'UTF-8'")
                cursor.close()

            # Validar a chave tentando acessar o banco
            try:
                with engine.connect() as conn:
                    result = conn.execute(
                        text("SELECT count(*) FROM sqlite_master")
                    )
                    count: int = result.scalar()  # type: ignore[assignment]
                    logger.info(
                        "Banco desbloqueado com sucesso. "
                        "Objetos encontrados: %d",
                        count,
                    )
            except Exception as exc:
                engine.dispose()
                raise SecureConnectionError(
                    "Falha ao desbloquear o banco. Chave inválida."
                ) from exc

            # Criar tabelas ORM se necessário
            Base.metadata.create_all(engine)

            self._engine = engine
            self._session_factory = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=engine,
            )
            self._is_unlocked = True
            logger.info("SecureConnectionManager: banco UNLOCKED.")

    def get_session(self) -> Session:
        """Retorna uma nova session SQLAlchemy.

        Returns:
            Uma sessão vinculada ao engine SQLCipher ativo.

        Raises:
            SecureConnectionError: Se o banco estiver travado (locked).
        """
        if not self._is_unlocked or self._session_factory is None:
            raise SecureConnectionError(
                "Banco está bloqueado. Faça login para desbloquear."
            )
        return self._session_factory()

    @property
    def is_unlocked(self) -> bool:
        """Indica se o banco está desbloqueado e pronto para uso."""
        return self._is_unlocked

    def lock(self) -> None:
        """Fecha a conexão e marca como locked.

        Descarta o engine e limpa o estado interno, forçando
        uma nova autenticação para reabrir o banco.
        """
        with self._conn_lock:
            if self._engine is not None:
                self._engine.dispose()
                self._engine = None
            self._session_factory = None
            self._is_unlocked = False
            logger.info("SecureConnectionManager: banco LOCKED.")
