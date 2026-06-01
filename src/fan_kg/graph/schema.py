from __future__ import annotations

from pathlib import Path

from fan_kg.graph.neo4j_client import Neo4jClient
from fan_kg.utils import read_yaml


CONSTRAINTS = [
    "CREATE CONSTRAINT company_id IF NOT EXISTS FOR (n:Company) REQUIRE n.company_id IS UNIQUE",
    "CREATE CONSTRAINT security_code IF NOT EXISTS FOR (n:Security) REQUIRE n.code IS UNIQUE",
    "CREATE CONSTRAINT product_category_id IF NOT EXISTS FOR (n:ProductCategory) REQUIRE n.product_id IS UNIQUE",
    "CREATE CONSTRAINT product_id IF NOT EXISTS FOR (n:Product) REQUIRE n.product_id IS UNIQUE",
    "CREATE CONSTRAINT sw_industry_code IF NOT EXISTS FOR (n:SWIndustry) REQUIRE n.sw_code IS UNIQUE",
    "CREATE CONSTRAINT brand_key IF NOT EXISTS FOR (n:Brand) REQUIRE n.brand_key IS UNIQUE",
    "CREATE CONSTRAINT channel_name IF NOT EXISTS FOR (n:Channel) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT region_name IF NOT EXISTS FOR (n:Region) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT material_id IF NOT EXISTS FOR (n:Material) REQUIRE n.material_id IS UNIQUE",
    "CREATE CONSTRAINT metric_id IF NOT EXISTS FOR (n:Metric) REQUIRE n.metric_id IS UNIQUE",
    "CREATE CONSTRAINT sales_id IF NOT EXISTS FOR (n:SalesMetric) REQUIRE n.sales_id IS UNIQUE",
    "CREATE CONSTRAINT weather_id IF NOT EXISTS FOR (n:WeatherEvent) REQUIRE n.weather_id IS UNIQUE",
    "CREATE CONSTRAINT commodity_price_id IF NOT EXISTS FOR (n:CommodityPrice) REQUIRE n.price_id IS UNIQUE",
    "CREATE CONSTRAINT market_feature_id IF NOT EXISTS FOR (n:MarketFeature) REQUIRE n.feature_id IS UNIQUE",
    "CREATE CONSTRAINT graph_entity_id IF NOT EXISTS FOR (n:GraphEntity) REQUIRE n.graphrag_id IS UNIQUE",
    "CREATE CONSTRAINT evidence_chunk_id IF NOT EXISTS FOR (n:EvidenceChunk) REQUIRE n.chunk_id IS UNIQUE",
    "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (n:Document) REQUIRE n.document_id IS UNIQUE",
    "CREATE CONSTRAINT graph_community_key IF NOT EXISTS FOR (n:GraphCommunity) REQUIRE n.community_key IS UNIQUE",
    "CREATE CONSTRAINT community_report_id IF NOT EXISTS FOR (n:CommunityReport) REQUIRE n.report_id IS UNIQUE",
    "CREATE CONSTRAINT quant_signal_id IF NOT EXISTS FOR (n:QuantSignal) REQUIRE n.signal_id IS UNIQUE",
]


def init_schema(client: Neo4jClient, ontology_path: str | Path) -> None:
    client.run_many(CONSTRAINTS)
    seed_ontology(client, ontology_path)


def seed_ontology(client: Neo4jClient, ontology_path: str | Path) -> None:
    ontology = read_yaml(ontology_path)
    root = ontology["root_product"]
    client.run(
        """
        MERGE (p:ProductCategory {product_id: $product_id})
        SET p.name = $name,
            p.normalized_name = $normalized_name,
            p.aliases = $aliases,
            p.updated_at = datetime()
        """,
        product_id=root["id"],
        name=root["name"],
        normalized_name=root.get("normalized_name", root["id"]),
        aliases=root.get("aliases", []),
    )

    for item in ontology.get("product_hierarchy", []):
        client.run(
            """
            MERGE (p:Product {product_id: $product_id})
            SET p.name = $name, p.updated_at = datetime()
            WITH p
            MATCH (root:ProductCategory {product_id: $parent_id})
            MERGE (root)-[:HAS_SUB_PRODUCT]->(p)
            """,
            product_id=item["id"],
            name=item["name"],
            parent_id=item.get("parent_id", root["id"]),
        )
