from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


@dataclass(frozen=True)
class Settings:
    root: Path
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str
    neo4j_database: str
    structured_dir: Path
    graphrag_root: Path

    @classmethod
    def from_env(cls, root: str | Path | None = None) -> "Settings":
        root_path = Path(root or os.getenv("FAN_KG_ROOT", ".")).resolve()
        env_path = root_path / ".env"
        if load_dotenv and env_path.exists():
            load_dotenv(env_path)

        structured = Path(os.getenv("FAN_KG_STRUCTURED_DIR", "data/raw/structured"))
        graphrag_root = Path(os.getenv("FAN_KG_GRAPHRAG_ROOT", "data/graphrag"))
        if not structured.is_absolute():
            structured = root_path / structured
        if not graphrag_root.is_absolute():
            graphrag_root = root_path / graphrag_root

        return cls(
            root=root_path,
            neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            neo4j_username=os.getenv("NEO4J_USERNAME", "neo4j"),
            neo4j_password=os.getenv("NEO4J_PASSWORD", "fan-kg-password"),
            neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
            structured_dir=structured,
            graphrag_root=graphrag_root,
        )
