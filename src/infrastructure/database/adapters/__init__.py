"""Adaptadores de banco de dados para inspeção e teste de conexão."""

from .base_metadata_extractor import BaseMetadataExtractor
from .postgres_metadata_extractor import PostgresMetadataExtractor
from .oracle_metadata_extractor import OracleMetadataExtractor

__all__ = ["BaseMetadataExtractor", "PostgresMetadataExtractor", "OracleMetadataExtractor"]
