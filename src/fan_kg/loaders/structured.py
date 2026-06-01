from __future__ import annotations

from pathlib import Path
from typing import Any

from fan_kg.graph.neo4j_client import Neo4jClient
from fan_kg.utils import clean_props, is_null, normalize_name, safe_float, stable_id


def _read_csv(path: Path) -> list[dict[str, Any]]:
    import pandas as pd

    if not path.exists():
        return []
    df = pd.read_csv(path, dtype=str).fillna("")
    return df.to_dict("records")


def _value(row: dict[str, Any], key: str, default: str = "") -> str:
    value = row.get(key, default)
    return default if is_null(value) else str(value).strip()


def _company_id(row: dict[str, Any]) -> str:
    return _value(row, "company_id") or _value(row, "stock_code") or stable_id(
        _value(row, "company_name"), prefix="company"
    )


def _product_id(row: dict[str, Any]) -> str:
    return _value(row, "product_id") or stable_id(_value(row, "product_name"), prefix="product")


def load_all_structured(client: Neo4jClient, structured_dir: str | Path) -> dict[str, int]:
    directory = Path(structured_dir)
    counts = {
        "sw_industry": load_sw_industry(client, directory / "sw_industry.csv"),
        "company_product_channel": load_company_product_channel(
            client, directory / "company_product_channel.csv"
        ),
        "financial_metrics": load_financial_metrics(client, directory / "financial_metrics.csv"),
        "sales_metrics": load_sales_metrics(client, directory / "sales_metrics.csv"),
        "weather_metrics": load_weather_metrics(client, directory / "weather_metrics.csv"),
        "commodity_prices": load_commodity_prices(client, directory / "commodity_prices.csv"),
        "material_exposure": load_material_exposure(client, directory / "material_exposure.csv"),
        "market_features": load_market_features(client, directory / "market_features.csv"),
    }
    return counts


def load_sw_industry(client: Neo4jClient, path: Path) -> int:
    rows = []
    for row in _read_csv(path):
        sw_code = _value(row, "sw_code") or stable_id(
            _value(row, "source", "申万"), _value(row, "sw_level"), _value(row, "sw_name"), prefix="sw"
        )
        rows.append(
            {
                "product_id": _product_id(row),
                "product_name": _value(row, "product_name", "风扇"),
                "sw_code": sw_code,
                "sw_name": _value(row, "sw_name"),
                "sw_level": _value(row, "sw_level"),
                "source": _value(row, "source", "申万"),
                "confidence": safe_float(row.get("confidence"), 1.0),
            }
        )
    if not rows:
        return 0
    query = """
    UNWIND $rows AS row
    MERGE (p:ProductCategory {product_id: row.product_id})
    SET p.name = row.product_name, p.updated_at = datetime()
    MERGE (i:SWIndustry {sw_code: row.sw_code})
    SET i.name = row.sw_name,
        i.level = row.sw_level,
        i.source = row.source,
        i.updated_at = datetime()
    MERGE (p)-[r:BELONGS_TO_INDUSTRY]->(i)
    SET r.source = row.source,
        r.confidence = row.confidence,
        r.updated_at = datetime()
    """
    return client.write_batch(query, rows)


def load_company_product_channel(client: Neo4jClient, path: Path) -> int:
    rows = []
    for row in _read_csv(path):
        company_id = _company_id(row)
        product_id = _product_id(row)
        stock_code = _value(row, "stock_code")
        brand_name = _value(row, "brand_name")
        channel = _value(row, "channel")
        rows.append(
            {
                "company_id": company_id,
                "company_name": _value(row, "company_name"),
                "stock_code": stock_code,
                "product_id": product_id,
                "product_name": _value(row, "product_name", "风扇"),
                "brand_name": brand_name,
                "brand_key": stable_id(company_id, brand_name, prefix="brand") if brand_name else "",
                "channel": channel,
                "exposure_type": _value(row, "exposure_type", "product_revenue"),
                "exposure_weight": safe_float(row.get("exposure_weight"), 0.0),
                "source": _value(row, "source"),
                "evidence": _value(row, "evidence"),
                "confidence": safe_float(row.get("confidence"), 1.0),
            }
        )
    if not rows:
        return 0
    query = """
    UNWIND $rows AS row
    MERGE (c:Company {company_id: row.company_id})
    SET c.name = row.company_name,
        c.stock_code = row.stock_code,
        c.normalized_name = toLower(row.company_name),
        c.updated_at = datetime()
    MERGE (p:ProductCategory {product_id: row.product_id})
    SET p.name = row.product_name, p.updated_at = datetime()
    MERGE (c)-[ex:HAS_EXPOSURE_TO]->(p)
    SET ex.exposure_type = row.exposure_type,
        ex.weight = row.exposure_weight,
        ex.source = row.source,
        ex.evidence = row.evidence,
        ex.confidence = row.confidence,
        ex.updated_at = datetime()
    MERGE (c)-[prod:PRODUCES]->(p)
    SET prod.confidence = row.confidence,
        prod.source = row.source,
        prod.updated_at = datetime()
    FOREACH (_ IN CASE WHEN row.stock_code <> "" THEN [1] ELSE [] END |
      MERGE (s:Security {code: row.stock_code})
      SET s.company_id = row.company_id, s.name = row.company_name, s.updated_at = datetime()
      MERGE (c)-[:LISTED_AS]->(s)
    )
    FOREACH (_ IN CASE WHEN row.brand_name <> "" THEN [1] ELSE [] END |
      MERGE (b:Brand {brand_key: row.brand_key})
      SET b.name = row.brand_name, b.company_id = row.company_id, b.updated_at = datetime()
      MERGE (c)-[:OWNS_BRAND]->(b)
      MERGE (b)-[:BRAND_OF]->(p)
    )
    FOREACH (_ IN CASE WHEN row.channel <> "" THEN [1] ELSE [] END |
      MERGE (ch:Channel {name: row.channel})
      MERGE (c)-[sell:SELLS_ON]->(ch)
      SET sell.product_id = row.product_id, sell.updated_at = datetime()
    )
    """
    return client.write_batch(query, rows)


def load_financial_metrics(client: Neo4jClient, path: Path) -> int:
    rows = []
    for row in _read_csv(path):
        company_id = _company_id(row)
        metric_name = _value(row, "metric_name")
        period = _value(row, "period")
        rows.append(
            {
                "company_id": company_id,
                "company_name": _value(row, "company_name"),
                "stock_code": _value(row, "stock_code"),
                "metric_id": stable_id(company_id, period, metric_name, prefix="metric"),
                "metric_name": metric_name,
                "period": period,
                "value": safe_float(row.get("value")),
                "unit": _value(row, "unit"),
                "source": _value(row, "source"),
            }
        )
    if not rows:
        return 0
    query = """
    UNWIND $rows AS row
    MERGE (c:Company {company_id: row.company_id})
    SET c.name = row.company_name,
        c.stock_code = row.stock_code,
        c.updated_at = datetime()
    MERGE (m:Metric {metric_id: row.metric_id})
    SET m.name = row.metric_name,
        m.period = row.period,
        m.value = row.value,
        m.unit = row.unit,
        m.source = row.source,
        m.updated_at = datetime()
    MERGE (c)-[r:HAS_METRIC]->(m)
    SET r.period = row.period,
        r.name = row.metric_name,
        r.updated_at = datetime()
    """
    return client.write_batch(query, rows)


def load_sales_metrics(client: Neo4jClient, path: Path) -> int:
    rows = []
    for row in _read_csv(path):
        product_id = _product_id(row)
        brand_name = _value(row, "brand_name")
        rows.append(
            {
                "sales_id": stable_id(
                    product_id,
                    brand_name,
                    _value(row, "channel"),
                    _value(row, "region"),
                    _value(row, "date"),
                    prefix="sales",
                ),
                "product_id": product_id,
                "product_name": _value(row, "product_name", "风扇"),
                "brand_name": brand_name,
                "channel": _value(row, "channel"),
                "region": _value(row, "region"),
                "date": _value(row, "date"),
                "sales_volume": safe_float(row.get("sales_volume")),
                "sales_amount": safe_float(row.get("sales_amount")),
                "asp": safe_float(row.get("asp")),
                "yoy_volume": safe_float(row.get("yoy_volume")),
                "yoy_amount": safe_float(row.get("yoy_amount")),
                "source": _value(row, "source"),
            }
        )
    if not rows:
        return 0
    query = """
    UNWIND $rows AS row
    MERGE (p:ProductCategory {product_id: row.product_id})
    SET p.name = row.product_name, p.updated_at = datetime()
    MERGE (sm:SalesMetric {sales_id: row.sales_id})
    SET sm += {
      brand_name: row.brand_name,
      channel: row.channel,
      region: row.region,
      date: row.date,
      sales_volume: row.sales_volume,
      sales_amount: row.sales_amount,
      asp: row.asp,
      yoy_volume: row.yoy_volume,
      yoy_amount: row.yoy_amount,
      source: row.source
    },
    sm.updated_at = datetime()
    MERGE (p)-[:HAS_SALES_METRIC]->(sm)
    FOREACH (_ IN CASE WHEN row.channel <> "" THEN [1] ELSE [] END |
      MERGE (ch:Channel {name: row.channel})
      MERGE (sm)-[:SOLD_ON]->(ch)
    )
    FOREACH (_ IN CASE WHEN row.region <> "" THEN [1] ELSE [] END |
      MERGE (r:Region {name: row.region})
      MERGE (sm)-[:SOLD_IN]->(r)
    )
    """
    return client.write_batch(query, rows)


def load_weather_metrics(client: Neo4jClient, path: Path) -> int:
    rows = []
    for row in _read_csv(path):
        region = _value(row, "region")
        date = _value(row, "date")
        rows.append(
            {
                "weather_id": stable_id(region, date, prefix="weather"),
                "region": region,
                "date": date,
                "max_temp": safe_float(row.get("max_temp")),
                "avg_temp": safe_float(row.get("avg_temp")),
                "high_temp_days": safe_float(row.get("high_temp_days")),
                "population_weight": safe_float(row.get("population_weight"), 1.0),
                "demand_weight": safe_float(row.get("demand_weight"), 1.0),
                "source": _value(row, "source"),
            }
        )
    if not rows:
        return 0
    query = """
    UNWIND $rows AS row
    MERGE (r:Region {name: row.region})
    MERGE (w:WeatherEvent {weather_id: row.weather_id})
    SET w += {
      date: row.date,
      max_temp: row.max_temp,
      avg_temp: row.avg_temp,
      high_temp_days: row.high_temp_days,
      population_weight: row.population_weight,
      demand_weight: row.demand_weight,
      source: row.source
    },
    w.updated_at = datetime()
    MERGE (r)-[:HAS_WEATHER]->(w)
    WITH w
    MATCH (p:ProductCategory {product_id: "fan"})
    MERGE (w)-[d:DRIVES_DEMAND_OF]->(p)
    SET d.driver = "temperature", d.updated_at = datetime()
    """
    return client.write_batch(query, rows)


def load_commodity_prices(client: Neo4jClient, path: Path) -> int:
    rows = []
    for row in _read_csv(path):
        material_id = _value(row, "material_id") or stable_id(_value(row, "material_name"), prefix="mat")
        date = _value(row, "date")
        rows.append(
            {
                "material_id": material_id,
                "material_name": _value(row, "material_name"),
                "price_id": stable_id(material_id, date, prefix="price"),
                "date": date,
                "price": safe_float(row.get("price")),
                "change_pct": safe_float(row.get("change_pct")),
                "unit": _value(row, "unit"),
                "source": _value(row, "source"),
            }
        )
    if not rows:
        return 0
    query = """
    UNWIND $rows AS row
    MERGE (m:Material {material_id: row.material_id})
    SET m.name = row.material_name, m.updated_at = datetime()
    MERGE (p:CommodityPrice {price_id: row.price_id})
    SET p += {
      date: row.date,
      price: row.price,
      change_pct: row.change_pct,
      unit: row.unit,
      source: row.source
    },
    p.updated_at = datetime()
    MERGE (m)-[:HAS_PRICE]->(p)
    """
    return client.write_batch(query, rows)


def load_material_exposure(client: Neo4jClient, path: Path) -> int:
    rows = []
    for row in _read_csv(path):
        material_id = _value(row, "material_id") or stable_id(_value(row, "material_name"), prefix="mat")
        rows.append(
            {
                "product_id": _product_id(row),
                "product_name": _value(row, "product_name", "风扇"),
                "material_id": material_id,
                "material_name": _value(row, "material_name"),
                "cost_weight": safe_float(row.get("cost_weight")),
            }
        )
    if not rows:
        return 0
    query = """
    UNWIND $rows AS row
    MERGE (p:ProductCategory {product_id: row.product_id})
    SET p.name = row.product_name, p.updated_at = datetime()
    MERGE (m:Material {material_id: row.material_id})
    SET m.name = row.material_name, m.updated_at = datetime()
    MERGE (p)-[r:USES_MATERIAL]->(m)
    SET r.cost_weight = row.cost_weight, r.updated_at = datetime()
    """
    return client.write_batch(query, rows)


def load_market_features(client: Neo4jClient, path: Path) -> int:
    rows = []
    for row in _read_csv(path):
        stock_code = _value(row, "stock_code")
        date = _value(row, "date")
        rows.append(
            {
                "feature_id": stable_id(stock_code, date, prefix="market"),
                "stock_code": stock_code,
                "company_id": _company_id(row),
                "date": date,
                "return_5d": safe_float(row.get("return_5d")),
                "turnover_zscore": safe_float(row.get("turnover_zscore")),
                "main_net_inflow": safe_float(row.get("main_net_inflow")),
                "order_imbalance": safe_float(row.get("order_imbalance")),
                "source": _value(row, "source"),
            }
        )
    if not rows:
        return 0
    query = """
    UNWIND $rows AS row
    MERGE (s:Security {code: row.stock_code})
    SET s.company_id = row.company_id, s.updated_at = datetime()
    MERGE (mf:MarketFeature {feature_id: row.feature_id})
    SET mf += {
      date: row.date,
      return_5d: row.return_5d,
      turnover_zscore: row.turnover_zscore,
      main_net_inflow: row.main_net_inflow,
      order_imbalance: row.order_imbalance,
      source: row.source
    },
    mf.updated_at = datetime()
    MERGE (s)-[:HAS_MARKET_FEATURE]->(mf)
    """
    return client.write_batch(query, rows)


def load_quant_signals(client: Neo4jClient, rows: list[dict[str, Any]]) -> int:
    payload = []
    for row in rows:
        company_id = _value(row, "company_id")
        date = _value(row, "date")
        payload.append(
            {
                "company_id": company_id,
                "company_name": _value(row, "company_name"),
                "stock_code": _value(row, "stock_code"),
                "signal_id": stable_id(company_id, date, "fan_theme", prefix="signal"),
                "date": date,
                "signal_name": "fan_theme",
                "weather_signal": safe_float(row.get("weather_signal")),
                "sales_signal": safe_float(row.get("sales_signal")),
                "cost_pressure_signal": safe_float(row.get("cost_pressure_signal")),
                "market_confirmation_signal": safe_float(row.get("market_confirmation_signal")),
                "combined_signal": safe_float(row.get("combined_signal")),
            }
        )
    if not payload:
        return 0
    query = """
    UNWIND $rows AS row
    MERGE (c:Company {company_id: row.company_id})
    SET c.name = row.company_name,
        c.stock_code = row.stock_code,
        c.updated_at = datetime()
    MERGE (q:QuantSignal {signal_id: row.signal_id})
    SET q += {
      date: row.date,
      name: row.signal_name,
      weather_signal: row.weather_signal,
      sales_signal: row.sales_signal,
      cost_pressure_signal: row.cost_pressure_signal,
      market_confirmation_signal: row.market_confirmation_signal,
      combined_signal: row.combined_signal
    },
    q.updated_at = datetime()
    MERGE (c)-[:GENERATES_SIGNAL]->(q)
    """
    return client.write_batch(query, payload)
