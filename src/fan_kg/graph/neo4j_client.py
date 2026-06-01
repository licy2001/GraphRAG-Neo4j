from __future__ import annotations

from collections.abc import Iterable
from typing import Any


class Neo4jClient:
    def __init__(self, uri: str, username: str, password: str, database: str = "neo4j") -> None:
        try:
            from neo4j import GraphDatabase
        except ImportError as exc:  # pragma: no cover
            msg = "Please install dependencies first: python -m pip install -e ."
            raise RuntimeError(msg) from exc

        self.database = database
        self.driver = GraphDatabase.driver(uri, auth=(username, password))

    def close(self) -> None:
        self.driver.close()

    def verify(self) -> None:
        self.driver.verify_connectivity()

    def run(self, query: str, **params: Any) -> list[dict[str, Any]]:
        with self.driver.session(database=self.database) as session:
            return session.run(query, params).data()

    def run_many(self, statements: Iterable[str]) -> None:
        with self.driver.session(database=self.database) as session:
            for statement in statements:
                session.run(statement).consume()

    def write_batch(self, query: str, rows: list[dict[str, Any]], batch_size: int = 1000) -> int:
        total = 0
        with self.driver.session(database=self.database) as session:
            for start in range(0, len(rows), batch_size):
                batch = rows[start : start + batch_size]
                session.run(query, rows=batch).consume()
                total += len(batch)
        return total

    def __enter__(self) -> "Neo4jClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
