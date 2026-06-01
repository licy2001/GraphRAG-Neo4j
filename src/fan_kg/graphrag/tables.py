from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


TABLE_ALIASES = {
    "documents": ["documents", "create_final_documents"],
    "text_units": ["text_units", "create_final_text_units"],
    "entities": ["entities", "create_final_entities"],
    "relationships": ["relationships", "create_final_relationships"],
    "communities": ["communities", "create_final_communities"],
    "community_reports": ["community_reports", "create_final_community_reports"],
    "covariates": ["covariates", "create_final_covariates"],
}


@dataclass(frozen=True)
class LocatedTable:
    name: str
    path: Path


def locate_table(output_dir: str | Path, table_name: str) -> LocatedTable | None:
    root = Path(output_dir)
    aliases = TABLE_ALIASES.get(table_name, [table_name])
    candidates: list[Path] = []
    for alias in aliases:
        candidates.extend(root.rglob(f"{alias}.parquet"))
        candidates.extend(root.rglob(f"{alias}.csv"))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return LocatedTable(name=table_name, path=candidates[0])


def locate_tables(output_dir: str | Path) -> dict[str, LocatedTable]:
    return {
        table_name: located
        for table_name in TABLE_ALIASES
        if (located := locate_table(output_dir, table_name)) is not None
    }
