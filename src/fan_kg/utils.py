from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

import yaml


def read_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f) or {}
    if not isinstance(loaded, dict):
        msg = f"YAML root must be a mapping: {path}"
        raise ValueError(msg)
    return loaded


def normalize_name(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", "", text)
    text = text.replace("股份有限公司", "")
    text = text.replace("有限公司", "")
    text = text.replace("集团股份", "集团")
    return text.lower()


def stable_id(*parts: Any, prefix: str | None = None) -> str:
    raw = "||".join("" if p is None else str(p) for p in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}" if prefix else digest


def is_null(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return str(value).strip().lower() in {"", "nan", "none", "null", "<na>", "nat"}


def parse_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return [v for v in value if not is_null(v)]
    if isinstance(value, tuple | set):
        return [v for v in value if not is_null(v)]
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text.replace("'", '"'))
            return parse_list(parsed)
        except json.JSONDecodeError:
            pass
    delimiter = ";" if ";" in text else ","
    return [item.strip() for item in text.split(delimiter) if item.strip()]


def safe_float(value: Any, default: float = 0.0) -> float:
    if is_null(value):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    if is_null(value):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def to_neo4j_value(value: Any) -> Any:
    if is_null(value):
        return None
    if hasattr(value, "tolist") and not isinstance(value, str | bytes):
        value = value.tolist()
    if hasattr(value, "item"):
        try:
            value = value.item()
        except ValueError:
            pass
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, list | tuple | set):
        out: list[Any] = []
        for item in value:
            converted = to_neo4j_value(item)
            if isinstance(converted, dict):
                converted = json.dumps(converted, ensure_ascii=False, sort_keys=True)
            if converted is not None:
                out.append(converted)
        return out
    return value


def clean_props(row: dict[str, Any], drop: set[str] | None = None) -> dict[str, Any]:
    drop = drop or set()
    props: dict[str, Any] = {}
    for key, value in row.items():
        if key in drop:
            continue
        converted = to_neo4j_value(value)
        if converted is not None:
            props[str(key)] = converted
    return props


def sanitize_filename(value: str) -> str:
    text = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", value.strip(), flags=re.UNICODE)
    return text[:120] or stable_id(value, prefix="doc")
