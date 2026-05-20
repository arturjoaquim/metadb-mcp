"""Testes unitários para o OracleMetadataExtractor."""

from unittest.mock import MagicMock, patch
from infrastructure.database.adapters.oracle_metadata_extractor import (
    OracleMetadataExtractor,
)


class TestOracleMetadataExtractorInitializeDrivers:
    """Testes para o método initialize_drivers."""

    @patch("infrastructure.database.adapters.oracle_metadata_extractor.os.path.isdir")
    @patch("infrastructure.database.adapters.oracle_metadata_extractor.oracledb")
    def test_initialize_drivers_calls_init_with_lib_dir_when_path_provided(
        self, mock_oracledb: MagicMock, mock_isdir: MagicMock
    ) -> None:
        """Quando driver_path é fornecido, deve chamar init_oracle_client com lib_dir."""
        mock_isdir.return_value = True
        extractor = OracleMetadataExtractor(
            host="localhost",
            port=1521,
            user="user",
            password="pass",
            dbname="ORCL",
            driver_path="/opt/oracle/instantclient_21_14",
        )

        extractor.initialize_drivers()

        mock_oracledb.init_oracle_client.assert_called_once_with(
            lib_dir="/opt/oracle/instantclient_21_14"
        )

    @patch("infrastructure.database.adapters.oracle_metadata_extractor.oracledb")
    def test_initialize_drivers_does_nothing_when_no_path(
        self, mock_oracledb: MagicMock
    ) -> None:
        """Quando driver_path não é fornecido, não deve chamar init_oracle_client."""
        extractor = OracleMetadataExtractor(
            host="localhost",
            port=1521,
            user="user",
            password="pass",
            dbname="ORCL",
        )

        extractor.initialize_drivers()

        mock_oracledb.init_oracle_client.assert_not_called()

    @patch("infrastructure.database.adapters.oracle_metadata_extractor.oracledb")
    def test_initialize_drivers_does_nothing_when_path_is_none(
        self, mock_oracledb: MagicMock
    ) -> None:
        """Quando driver_path é explicitamente None, não deve chamar init_oracle_client."""
        extractor = OracleMetadataExtractor(
            host="localhost",
            port=1521,
            user="user",
            password="pass",
            dbname="ORCL",
            driver_path=None,
        )

        extractor.initialize_drivers()

        mock_oracledb.init_oracle_client.assert_not_called()


class TestOracleMetadataExtractorIsSystemSchema:
    """Testes para o método _is_system_schema."""

    def _create_extractor(self) -> OracleMetadataExtractor:
        return OracleMetadataExtractor(
            host="localhost",
            port=1521,
            user="user",
            password="pass",
            dbname="ORCL",
        )

    def test_sys_is_system_schema(self) -> None:
        extractor = self._create_extractor()
        assert extractor._is_system_schema("SYS") is True

    def test_system_is_system_schema(self) -> None:
        extractor = self._create_extractor()
        assert extractor._is_system_schema("SYSTEM") is True

    def test_xdb_is_system_schema(self) -> None:
        extractor = self._create_extractor()
        assert extractor._is_system_schema("XDB") is True

    def test_apex_prefix_is_system_schema(self) -> None:
        extractor = self._create_extractor()
        assert extractor._is_system_schema("APEX_040000") is True
        assert extractor._is_system_schema("APEX_050000") is True

    def test_flows_prefix_is_system_schema(self) -> None:
        extractor = self._create_extractor()
        assert extractor._is_system_schema("FLOWS_123") is True

    def test_ords_prefix_is_system_schema(self) -> None:
        extractor = self._create_extractor()
        assert extractor._is_system_schema("ORDS_SOMETHING") is True

    def test_user_schema_is_not_system(self) -> None:
        extractor = self._create_extractor()
        assert extractor._is_system_schema("HR") is False
        assert extractor._is_system_schema("ACADEMICO") is False
        assert extractor._is_system_schema("MY_APP") is False

    def test_case_insensitive_check(self) -> None:
        extractor = self._create_extractor()
        assert extractor._is_system_schema("sys") is True
        assert extractor._is_system_schema("System") is True


class TestOracleMetadataExtractorGetAllTables:
    """Testes para o método get_all_tables."""

    def _create_extractor(self) -> OracleMetadataExtractor:
        return OracleMetadataExtractor(
            host="localhost",
            port=1521,
            user="hr",
            password="pass",
            dbname="ORCL",
        )

    def _make_mock_row(self, owner: str, table_name: str) -> MagicMock:
        """Cria um mock de linha de resultado (acesso por índice)."""
        row = MagicMock()
        row.__getitem__ = MagicMock(
            side_effect=lambda i: owner if i == 0 else table_name
        )
        return row

    @patch.object(OracleMetadataExtractor, "get_engine")
    def test_get_all_tables_returns_user_tables(
        self, mock_get_engine: MagicMock
    ) -> None:
        """Deve retornar tabelas de schemas de usuário no formato OWNER.TABLE_NAME."""
        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        rows = [
            self._make_mock_row("HR", "EMPLOYEES"),
            self._make_mock_row("HR", "DEPARTMENTS"),
            self._make_mock_row("ACADEMICO", "ALUNOS"),
        ]

        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = iter(rows)

        extractor = self._create_extractor()
        tables = extractor.get_all_tables()

        assert "HR.EMPLOYEES" in tables
        assert "HR.DEPARTMENTS" in tables
        assert "ACADEMICO.ALUNOS" in tables
        assert len(tables) == 3

    @patch.object(OracleMetadataExtractor, "get_engine")
    def test_get_all_tables_excludes_system_schema_rows(
        self, mock_get_engine: MagicMock
    ) -> None:
        """Deve excluir linhas cujo OWNER seja um schema de sistema via _is_system_schema."""
        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        # Simula que ALL_TABLES retornou algum schema de sistema (não filtrado no SQL por prefixo)
        rows = [
            self._make_mock_row("APEX_040000", "SOME_TABLE"),
            self._make_mock_row("HR", "EMPLOYEES"),
        ]

        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = iter(rows)

        extractor = self._create_extractor()
        tables = extractor.get_all_tables()

        # APEX_040000 é filtrado pelo _is_system_schema em Python
        assert "HR.EMPLOYEES" in tables
        assert not any("APEX_040000" in t for t in tables)
        assert len(tables) == 1

    @patch.object(OracleMetadataExtractor, "get_engine")
    def test_get_all_tables_returns_empty_on_exception(
        self, mock_get_engine: MagicMock
    ) -> None:
        """Deve retornar lista vazia quando ocorre exceção na execução da query."""
        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine
        mock_engine.connect.side_effect = Exception("connection failed")

        extractor = self._create_extractor()
        tables = extractor.get_all_tables()

        assert tables == []

    @patch.object(OracleMetadataExtractor, "get_engine")
    def test_get_all_tables_uses_all_tables_view(
        self, mock_get_engine: MagicMock
    ) -> None:
        """A query enviada ao banco deve referenciar ALL_TABLES."""
        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = iter([])

        extractor = self._create_extractor()
        extractor.get_all_tables()

        # Verifica que execute foi chamado e o SQL contém ALL_TABLES
        assert mock_conn.execute.called
        sql_called: str = str(mock_conn.execute.call_args[0][0])
        assert "ALL_TABLES" in sql_called
