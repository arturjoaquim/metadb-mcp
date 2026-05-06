from dataclasses import dataclass
from typing import List, Optional, Dict, Any

@dataclass
class ExtractedColumn:
    name: str
    data_type: str
    is_nullable: bool
    default_value: Optional[str] = None
    comment: Optional[str] = None

@dataclass
class ExtractedIndex:
    name: str
    columns: List[str]
    is_unique: bool

@dataclass
class ExtractedConstraint:
    name: str
    constraint_type: str # PRIMARY KEY, FOREIGN KEY, UNIQUE
    columns: List[str]
    ref_table: Optional[str] = None
    ref_columns: Optional[str] = None

@dataclass
class ExtractedTableMetadata:
    table_name: str
    schema_name: Optional[str]
    comment: Optional[str]
    columns: List[ExtractedColumn]
    indexes: List[ExtractedIndex]
    constraints: List[ExtractedConstraint]
    samples: List[Dict[str, Any]]
