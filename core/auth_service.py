"""Serviço de autenticação com Argon2id, Keyring e JWT.

Gerencia o fluxo completo de cadastro e login, derivação de chave
criptográfica e emissão de tokens JWT. A senha do usuário NUNCA é
armazenada — o banco SQLCipher criptografado é o mecanismo de
verificação de identidade.
"""

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
import keyring
from argon2.low_level import Type, hash_secret_raw

from .database import secure_connection
from .database.models import AppConfig
from .database.secure_connection import DB_FILE_PATH, SecureConnectionError

logger: logging.Logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Exceção para falhas de autenticação."""


class AuthService:
    """Gerencia cadastro, login, derivação de chave e tokens JWT.

    Fluxo de Cadastro:
        1. Gera salt aleatório (32 bytes) → armazena no keyring do SO
           usando o username fornecido.
        2. Deriva chave com ``Argon2id(password, salt)`` → 32 bytes hex.
        3. Desbloqueia ``SecureConnectionManager`` com a chave derivada
           (cria o banco criptografado).
        4. Cria tabelas ORM + armazena ``jwt_secret`` na tabela
           ``app_config`` (dentro do banco criptografado).
        5. Gera JWT e retorna o token.

    Fluxo de Login:
        1. Recupera salt do keyring usando o username fornecido.
        2. Deriva chave com ``Argon2id(password, salt)``.
        3. Tenta desbloquear ``SecureConnectionManager``.
        4. Se ``PRAGMA key`` falhar → credenciais inválidas.
        5. Se sucesso → gera JWT e retorna o token.

    ⚠️ NENHUM hash de senha é armazenado em lugar algum.
    O banco SQLCipher criptografado É o mecanismo de verificação.
    """

    KEYRING_SERVICE: str = "metadb-mcp"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 8

    # Parâmetros Argon2id (256 MB de memória)
    ARGON2_TIME_COST: int = 3
    ARGON2_MEMORY_COST: int = 262144  # 256 MB
    ARGON2_PARALLELISM: int = 4
    ARGON2_HASH_LEN: int = 32  # 256 bits

    def register(self, username: str, password: str) -> str:
        """Cadastro inicial — cria banco criptografado e retorna JWT.

        Args:
            username: Nome de usuário para associação no keyring.
            password: Senha que será usada para derivar a chave de
                      criptografia.

        Returns:
            Token JWT assinado.

        Raises:
            AuthenticationError: Se o banco já existir (cadastro duplicado)
                                 ou se houver falha na criação.
        """
        if self.database_exists():
            raise AuthenticationError(
                "Banco de dados já existe. Use login ao invés de cadastro."
            )

        # 1. Gerar salt aleatório e armazenar no keyring
        salt: bytes = os.urandom(32)
        salt_hex: str = salt.hex()
        keyring.set_password(self.KEYRING_SERVICE, username, salt_hex)
        logger.info(
            "Salt gerado e armazenado no keyring para o usuário '%s'.",
            username,
        )

        # 2. Derivar chave com Argon2id
        derived_key_hex: str = self.derive_key(password, salt)

        # 3. Desbloquear (cria o banco criptografado)
        try:
            secure_connection.unlock(derived_key_hex)
        except SecureConnectionError:
            # Limpar salt do keyring em caso de falha
            keyring.delete_password(self.KEYRING_SERVICE, username)
            raise AuthenticationError(
                "Falha ao criar o banco de dados criptografado."
            )

        # 4. Armazenar JWT secret dentro do banco criptografado
        jwt_secret: str = secrets.token_hex(32)
        session = secure_connection.get_session()
        try:
            config_entry: AppConfig = AppConfig(
                key="jwt_secret_key",
                value=jwt_secret,
            )
            session.add(config_entry)

            # Armazenar username para referência
            username_entry: AppConfig = AppConfig(
                key="auth_username",
                value=username,
            )
            session.add(username_entry)
            session.commit()
        except Exception as exc:
            session.rollback()
            raise AuthenticationError(
                "Falha ao configurar o banco de dados."
            ) from exc
        finally:
            session.close()

        # 5. Gerar e retornar JWT
        token: str = self._generate_jwt(username, jwt_secret)
        logger.info("Cadastro concluído com sucesso para '%s'.", username)
        return token

    def login(self, username: str, password: str) -> str:
        """Login — recupera salt do keyring, deriva chave e desbloqueia.

        O banco SQLCipher é o mecanismo de verificação: se a chave
        derivada for incorreta, o ``PRAGMA key`` falhará e a
        autenticação será recusada.

        Args:
            username: Nome de usuário registrado no keyring.
            password: Senha para derivação da chave.

        Returns:
            Token JWT assinado.

        Raises:
            AuthenticationError: Se o banco não existir, o username não
                                 for encontrado no keyring, ou a senha
                                 estiver incorreta.
        """
        if not self.database_exists():
            raise AuthenticationError(
                "Banco de dados não encontrado. Realize o cadastro inicial."
            )

        # 1. Recuperar salt do keyring
        salt_hex: Optional[str] = keyring.get_password(
            self.KEYRING_SERVICE, username
        )
        if salt_hex is None:
            raise AuthenticationError(
                "Credenciais inválidas. Usuário não encontrado."
            )

        salt: bytes = bytes.fromhex(salt_hex)

        # 2. Derivar chave com Argon2id
        derived_key_hex: str = self.derive_key(password, salt)

        # 3. Tentar desbloquear — o banco É o verificador
        try:
            secure_connection.unlock(derived_key_hex)
        except SecureConnectionError as exc:
            raise AuthenticationError(
                "Credenciais inválidas. Senha incorreta."
            ) from exc

        # 4. Recuperar JWT secret do banco
        jwt_secret: str = self._get_jwt_secret()

        # 5. Gerar e retornar JWT
        token: str = self._generate_jwt(username, jwt_secret)
        logger.info("Login bem-sucedido para '%s'.", username)
        return token

    def derive_key(self, password: str, salt: bytes) -> str:
        """Deriva chave de 32 bytes via Argon2id (256 MB de memória).

        Args:
            password: Senha do usuário em texto plano.
            salt: Salt aleatório de 32 bytes.

        Returns:
            Chave derivada como string hexadecimal (64 caracteres).
        """
        derived: bytes = hash_secret_raw(
            secret=password.encode("utf-8"),
            salt=salt,
            time_cost=self.ARGON2_TIME_COST,
            memory_cost=self.ARGON2_MEMORY_COST,
            parallelism=self.ARGON2_PARALLELISM,
            hash_len=self.ARGON2_HASH_LEN,
            type=Type.ID,
        )
        return derived.hex()

    def verify_token(self, token: str) -> Optional[dict[str, Any]]:
        """Valida um token JWT.

        Args:
            token: Token JWT a ser validado.

        Returns:
            Payload decodificado se válido, ``None`` caso contrário.
        """
        if not secure_connection.is_unlocked:
            return None

        try:
            jwt_secret: str = self._get_jwt_secret()
            payload: dict[str, Any] = jwt.decode(
                token,
                jwt_secret,
                algorithms=[self.JWT_ALGORITHM],
            )
            return payload
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None

    def database_exists(self) -> bool:
        """Verifica se o arquivo do banco de dados já existe no disco.

        Returns:
            ``True`` se o arquivo ``.db`` existir, ``False`` caso contrário.
        """
        return DB_FILE_PATH.exists() and DB_FILE_PATH.stat().st_size > 0

    # ------------------------------------------------------------------ #
    # Métodos Privados
    # ------------------------------------------------------------------ #

    def _generate_jwt(self, username: str, jwt_secret: str) -> str:
        """Gera um token JWT com expiração configurada.

        Args:
            username: Nome de usuário a ser incluído no payload.
            jwt_secret: Chave secreta para assinatura do token.

        Returns:
            Token JWT assinado como string.
        """
        now: datetime = datetime.now(tz=timezone.utc)
        payload: dict[str, Any] = {
            "sub": username,
            "iat": now,
            "exp": now + timedelta(hours=self.JWT_EXPIRATION_HOURS),
        }
        return jwt.encode(payload, jwt_secret, algorithm=self.JWT_ALGORITHM)

    def _get_jwt_secret(self) -> str:
        """Recupera o JWT secret armazenado dentro do banco criptografado.

        Returns:
            Chave secreta JWT como string.

        Raises:
            AuthenticationError: Se o secret não for encontrado no banco.
        """
        session = secure_connection.get_session()
        try:
            config: Optional[AppConfig] = (
                session.query(AppConfig)
                .filter_by(key="jwt_secret_key")
                .first()
            )
            if config is None:
                raise AuthenticationError(
                    "Configuração JWT não encontrada no banco."
                )
            return str(config.value)
        finally:
            session.close()


# Instância global do serviço de autenticação
auth_service: AuthService = AuthService()
