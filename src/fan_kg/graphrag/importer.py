from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fan_kg.graphrag.tables import locate_table, locate_tables
from fan_kg.graph.neo4j_client import Neo4jClient
from fan_kg.utils import clean_props, normalize_name, parse_list, stable_id, to_neo4j_value


def import_graphrag_output(client: Neo4jClient, output_dir: str | Path) -> dict[str, int]:
    tables = locate_tables(output_dir)
    counts: dict[str, int] = {}

    entities = _read_table(output_dir, "entities")
    entity_title_to_id = _entity_title_map(entities)

    counts["entities"] = _import_entities(client, entities)
    counts["relationships"] = _import_relationships(
        client, _read_table(output_dir, "relationships"), entity_title_to_id
    )
    counts["documents"] = _import_documents(client, _read_table(output_dir, "documents"))
    counts["text_units"] = _import_text_units(client, _read_table(output_dir, "text_units"))
    counts["communities"] = _import_communities(client, _read_table(output_dir, "communities"))
    counts["community_reports"] = _import_community_reports(
        client, _read_table(output_dir, "community_reports")
    )
    counts["covariates"] = _import_covariates(client, _read_table(output_dir, "covariates"))
    counts["domain_links"] = link_extracted_entities_to_domain(client)
    counts["located_tables"] = len(tables)
    return counts


def _read_table(output_dir: str | Path, table_name: str) -> list[dict[str, Any]]:
    import pandas as pd

    located = locate_table(output_dir, table_name)
    if located is None:
        return []
    if located.path.suffix.lower() == ".csv":
        df = pd.read_csv(located.path)
    else:
        df = pd.read_parquet(located.path)
    records = df.to_dict("records")
    return [_normalize_record(record) for record in records]


def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    return {str(k): to_neo4j_value(v) for k, v in record.items()}


def _entity_title_map(rows: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in rows:
        title = row.get("title")
        entity_id = row.get("id")
        if title and entity_id:
            result[normalize_name(title)] = str(entity_id)
    return result


def _import_entities(client: Neo4jClient, rows: list[dict[str, Any]]) -> int:
    payload = []
    for row in rows:
        entity_id = str(row.get("id") or stable_id(row.get("title"), row.get("type"), prefix="entity"))
        props = clean_props(row, drop={"id"})
        props["normalized_title"] = normalize_name(props.get("title", ""))
        payload.append({"id": entity_id, "props": props})
    if not payload:
        return 0
    query = """
    UNWIND $rows AS row
    MERGE (e:GraphEntity {graphrag_id: row.id})
    SET e += row.props,
        e.updated_at = datetime()
    """
    return client.write_batch(query, payload)


def _import_relationships(
    client: Neo4jClient, rows: list[dict[str, Any]], entity_title_to_id: dict[str, str]
) -> int:
    payload = []
    for row in rows:
        source_title = str(row.get("source") or "")
        target_title = str(row.get("target") or "")
        source_id = entity_title_to_id.get(normalize_name(source_title)) or stable_id(
            source_title, prefix="entity_fallback"
        )
        target_id = entity_title_to_id.get(normalize_name(target_title)) or stable_id(
            target_title, prefix="entity_fallback"
        )
        rel_id = str(row.get("id") or stable_id(source_id, target_id, row.get("description"), prefix="rel"))
        props = clean_props(row, drop={"id"})
        props["graphrag_relationship_id"] = rel_id
        payload.append(
            {
                "source_id": source_id,
                "source_title": source_title,
                "target_id": target_id,
                "target_title": target_title,
                "props": props,
            }
        )
    if not payload:
        return 0
    query = """
    UNWIND $rows AS row
    MERGE (s:GraphEntity {graphrag_id: row.source_id})
    ON CREATE SET s.title = row.source_title, s.normalized_title = toLower(row.source_title)
    MERGE (t:GraphEntity {graphrag_id: row.target_id})
    ON CREATE SET t.title = row.target_title, t.normalized_title = toLower(row.target_title)
    MERGE (s)-[r:GRAPHRAG_RELATED_TO {graphrag_relationship_id: row.props.graphrag_relationship_id}]->(t)
    SET r += row.props,
        r.updated_at = datetime()
    """
    return client.write_batch(query, payload)


def _import_documents(client: Neo4jClient, rows: list[dict[str, Any]]) -> int:
    payload = []
    for row in rows:
        doc_id = str(row.get("id") or row.get("document_id") or stable_id(row.get("title"), prefix="doc"))
        payload.append(
            {
                "id": doc_id,
                "props": clean_props(row, drop={"id", "text_unit_ids"}),
                "text_unit_ids": [str(v) for v in parse_list(row.get("text_unit_ids"))],
            }
        )
    if not payload:
        return 0
    create_docs = """
    UNWIND $rows AS row
    MERGE (d:Document {document_id: row.id})
    SET d += row.props,
        d.updated_at = datetime()
    """
    link_chunks = """
    UNWIND $rows AS row
    MATCH (d:Document {document_id: row.id})
    UNWIND row.text_unit_ids AS chunk_id
    MERGE (c:EvidenceChunk {chunk_id: chunk_id})
    MERGE (d)-[:HAS_CHUNK]->(c)
    """
    client.write_batch(create_docs, payload)
    client.write_batch(link_chunks, payload)
    return len(payload)


def _import_text_units(client: Neo4jClient, rows: list[dict[str, Any]]) -> int:
    payload = []
    for row in rows:
        chunk_id = str(row.get("id") or stable_id(row.get("text"), prefix="chunk"))
        payload.append(
            {
                "id": chunk_id,
                "props": clean_props(row, drop={"id", "entity_ids", "relationship_ids", "covariate_ids"}),
                "entity_ids": [str(v) for v in parse_list(row.get("entity_ids"))],
                "relationship_ids": [str(v) for v in parse_list(row.get("relationship_ids"))],
            }
        )
    if not payload:
        return 0
    create_chunks = """
    UNWIND $rows AS row
    MERGE (c:EvidenceChunk {chunk_id: row.id})
    SET c += row.props,
        c.updated_at = datetime()
    """
    link_entities = """
    UNWIND $rows AS row
    MATCH (c:EvidenceChunk {chunk_id: row.id})
    UNWIND row.entity_ids AS entity_id
    MATCH (e:GraphEntity {graphrag_id: entity_id})
    MERGE (e)-[:MENTIONED_IN]->(c)
    """
    client.write_batch(create_chunks, payload)
    client.write_batch(link_entities, payload)
    return len(payload)


def _import_communities(client: Neo4jClient, rows: list[dict[str, Any]]) -> int:
    payload = []
    for row in rows:
        community = str(row.get("community") or row.get("id") or "")
        level = str(row.get("level") or "")
        key = f"{community}:{level}"
        payload.append(
            {
                "key": key,
                "props": clean_props(row, drop={"entity_ids", "relationship_ids", "text_unit_ids"}),
                "entity_ids": [str(v) for v in parse_list(row.get("entity_ids"))],
            }
        )
    if not payload:
        return 0
    create_communities = """
    UNWIND $rows AS row
    MERGE (c:GraphCommunity {community_key: row.key})
    SET c += row.props,
        c.updated_at = datetime()
    """
    link_entities = """
    UNWIND $rows AS row
    MATCH (c:GraphCommunity {community_key: row.key})
    UNWIND row.entity_ids AS entity_id
    MATCH (e:GraphEntity {graphrag_id: entity_id})
    MERGE (c)-[:CONTAINS_ENTITY]->(e)
    """
    client.write_batch(create_communities, payload)
    client.write_batch(link_entities, payload)
    return len(payload)


def _import_community_reports(client: Neo4jClient, rows: list[dict[str, Any]]) -> int:
    payload = []
    for row in rows:
        community = str(row.get("community") or "")
        level = str(row.get("level") or "")
        key = f"{community}:{level}"
        report_id = str(row.get("id") or stable_id(key, row.get("title"), prefix="report"))
        props = clean_props(row, drop={"id", "full_content_json"})
        if row.get("full_content_json"):
            props["full_content_json"] = (
                row["full_content_json"]
                if isinstance(row["full_content_json"], str)
                else json.dumps(row["full_content_json"], ensure_ascii=False)
            )
        payload.append({"id": report_id, "community_key": key, "props": props})
    if not payload:
        return 0
    query = """
    UNWIND $rows AS row
    MERGE (c:GraphCommunity {community_key: row.community_key})
    MERGE (r:CommunityReport {report_id: row.id})
    SET r += row.props,
        r.updated_at = datetime()
    MERGE (c)-[:HAS_REPORT]->(r)
    """
    return client.write_batch(query, payload)


def _import_covariates(client: Neo4jClient, rows: list[dict[str, Any]]) -> int:
    payload = []
    for row in rows:
        claim_id = str(row.get("id") or stable_id(row.get("subject_id"), row.get("description"), prefix="claim"))
        payload.append({"id": claim_id, "subject_id": str(row.get("subject_id") or ""), "props": clean_props(row, drop={"id"})})
    if not payload:
        return 0
    query = """
    UNWIND $rows AS row
    MERGE (cl:Claim {claim_id: row.id})
    SET cl += row.props,
        cl.updated_at = datetime()
    FOREACH (_ IN CASE WHEN row.subject_id <> "" THEN [1] ELSE [] END |
      MERGE (e:GraphEntity {graphrag_id: row.subject_id})
      MERGE (e)-[:HAS_CLAIM]->(cl)
    )
    """
    return client.write_batch(query, payload)


def link_extracted_entities_to_domain(client: Neo4jClient) -> int:
    statements = [
        """
        MATCH (g:GraphEntity)
        WITH g, toLower(g.title) AS title
        MATCH (p:ProductCategory)
        WHERE title = toLower(p.name)
           OR any(alias IN coalesce(p.aliases, []) WHERE title = toLower(alias))
        MERGE (g)-[:SAME_AS]->(p)
        RETURN count(*) AS count
        """,
        """
        MATCH (g:GraphEntity)
        WITH g, toLower(g.title) AS title
        MATCH (c:Company)
        WHERE title = toLower(c.name)
           OR title = toLower(coalesce(c.stock_code, ""))
        MERGE (g)-[:SAME_AS]->(c)
        RETURN count(*) AS count
        """,
        """
        MATCH (g:GraphEntity)
        WITH g, toLower(g.title) AS title
        MATCH (b:Brand)
        WHERE title = toLower(b.name)
        MERGE (g)-[:SAME_AS]->(b)
        RETURN count(*) AS count
        """,
    ]
    total = 0
    for statement in statements:
        result = client.run(statement)
        total += int(result[0]["count"]) if result else 0
    return total
