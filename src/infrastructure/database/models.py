from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class DBConnection(Base):
    __tablename__ = "db_connections"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    db_type = Column(String(50), nullable=False)  # 'postgresql' ou 'oracle'
    host = Column(String(255))
    port = Column(Integer)
    user = Column(String(255))
    dbname = Column(String(255))  # dbname or sid/service_name
    created_at = Column(DateTime, default=datetime.utcnow)


class MetadataTable(Base):
    __tablename__ = "metadata_tables"
    id = Column(Integer, primary_key=True, autoincrement=True)
    connection_id = Column(Integer, ForeignKey("db_connections.id"))
    table_name = Column(String(255), nullable=False)
    schema_name = Column(String(255))
    comment = Column(Text)
    is_sensitive = Column(Integer, default=0)  # 0 = False, 1 = True
    sample_size = Column(Integer, default=10)
    created_at = Column(DateTime, default=datetime.utcnow)


class MetadataColumn(Base):
    __tablename__ = "metadata_columns"
    id = Column(Integer, primary_key=True, autoincrement=True)
    table_id = Column(Integer, ForeignKey("metadata_tables.id"))
    column_name = Column(String(255), nullable=False)
    data_type = Column(String(255), nullable=False)
    is_nullable = Column(Integer)  # 0 = False, 1 = True
    default_value = Column(Text)
    comment = Column(Text)


class MetadataConstraint(Base):
    __tablename__ = "metadata_constraints"
    id = Column(Integer, primary_key=True, autoincrement=True)
    table_id = Column(Integer, ForeignKey("metadata_tables.id"))
    constraint_name = Column(String(255))
    constraint_type = Column(String(100))  # PRIMARY KEY, FOREIGN KEY, UNIQUE
    columns = Column(Text)  # JSON list of column names
    ref_table = Column(String(255))  # Only for FKs
    ref_columns = Column(Text)  # Only for FKs


class MetadataIndex(Base):
    __tablename__ = "metadata_indexes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    table_id = Column(Integer, ForeignKey("metadata_tables.id"))
    index_name = Column(String(255))
    columns = Column(Text)  # JSON list of column names
    is_unique = Column(Integer)


class MetadataSample(Base):
    __tablename__ = "metadata_samples"
    id = Column(Integer, primary_key=True, autoincrement=True)
    table_id = Column(Integer, ForeignKey("metadata_tables.id"))
    row_data = Column(Text)  # JSON string of row


class AppConfig(Base):
    """Configurações internas da aplicação armazenadas no banco criptografado."""

    __tablename__ = "app_config"
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(255), unique=True, nullable=False)
    value = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
