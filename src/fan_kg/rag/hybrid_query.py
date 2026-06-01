from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from fan_kg.graph.neo4j_client import Neo4jClient


def fan_company_context(client: Neo4jClient, product_name: str = "风扇", limit: int = 20) -> list[dict[str, Any]]:
    return client.run(
        """
        MATCH (c:Company)-[ex:HAS_EXPOSURE_TO]->(p:ProductCategory)
        WHERE p.name CONTAINS $product_name
           OR any(alias IN coalesce(p.aliases, []) WHERE alias CONTAINS $product_name)
        OPTIONAL MATCH (c)-[:LISTED_AS]->(s:Security)
        OPTIONAL MATCH (c)-[:HAS_METRIC]->(m:Metric)
        WITH c, s, ex, collect(m)[0..5] AS metrics
        RETURN c.name AS company,
               c.company_id AS company_id,
               s.code AS stock_code,
               ex.weight AS exposure_weight,
               ex.source AS exposure_source,
               [m IN metrics | {name: m.name, period: m.period, value: m.value, unit: m.unit}] AS metrics
        ORDER BY exposure_weight DESC
        LIMIT $limit
        """,
        product_name=product_name,
        limit=limit,
    )


def run_graphrag_query(
    question: str,
    graphrag_root: str | Path,
    method: str = "local",
    timeout: int = 300,
) -> str:
    command = [
        "graphrag",
        "query",
        question,
        "--root",
        str(graphrag_root),
        "--method",
        method,
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        return completed.stderr.strip()
    return completed.stdout.strip()
