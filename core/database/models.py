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
    # SENHAS NÃO SÃO ARMAZENADAS A PEDIDO DO USUÁRIO
    created_at = Column(DateTime, default=datetime.utcnow)


class SyncTable(Base):
    __tablename__ = "sync_tables"
    id = Column(Integer, primary_key=True, autoincrement=True)
    connection_id = Column(Integer, ForeignKey("db_connections.id"))
    table_name = Column(String(255), nullable=False)
    schema_name = Column(String(255))
    comment = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class SyncColumn(Base):
    __tablename__ = "sync_columns"
    id = Column(Integer, primary_key=True, autoincrement=True)
    table_id = Column(Integer, ForeignKey("sync_tables.id"))
    column_name = Column(String(255), nullable=False)
    data_type = Column(String(255), nullable=False)
    is_nullable = Column(Integer)  # 0 = False, 1 = True
    default_value = Column(Text)
    comment = Column(Text)


class SyncConstraint(Base):
    __tablename__ = "sync_constraints"
    id = Column(Integer, primary_key=True, autoincrement=True)
    table_id = Column(Integer, ForeignKey("sync_tables.id"))
    constraint_name = Column(String(255))
    constraint_type = Column(String(100))  # PRIMARY KEY, FOREIGN KEY, UNIQUE
    columns = Column(Text)  # JSON list of column names
    ref_table = Column(String(255))  # Only for FKs
    ref_columns = Column(Text)  # Only for FKs


class SyncIndex(Base):
    __tablename__ = "sync_indexes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    table_id = Column(Integer, ForeignKey("sync_tables.id"))
    index_name = Column(String(255))
    columns = Column(Text)  # JSON list of column names
    is_unique = Column(Integer)


class SyncSample(Base):
    __tablename__ = "sync_samples"
    id = Column(Integer, primary_key=True, autoincrement=True)
    table_id = Column(Integer, ForeignKey("sync_tables.id"))
    row_data = Column(Text)  # JSON string of row
