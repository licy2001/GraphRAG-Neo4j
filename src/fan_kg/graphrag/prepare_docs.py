from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import Any

from fan_kg.utils import sanitize_filename, stable_id


TEXT_SUFFIXES = {".txt", ".md"}


def prepare_documents(source: str | Path, target: str | Path) -> dict[str, int]:
    source_path = Path(source)
    target_path = Path(target)
    target_path.mkdir(parents=True, exist_ok=True)

    counts = {"copied": 0, "converted": 0, "skipped": 0}
    if not source_path.exists():
        return counts

    for path in source_path.rglob("*"):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in TEXT_SUFFIXES:
            shutil.copy2(path, target_path / path.name)
            counts["copied"] += 1
        elif suffix == ".jsonl":
            counts["converted"] += _convert_jsonl(path, target_path)
        elif suffix == ".csv":
            counts["converted"] += _convert_csv(path, target_path)
        elif suffix == ".pdf":
            counts["converted"] += _convert_pdf(path, target_path)
        elif suffix == ".docx":
            counts["converted"] += _convert_docx(path, target_path)
        else:
            counts["skipped"] += 1
    return counts


def _format_document(row: dict[str, Any]) -> str:
    text = str(row.get("text") or row.get("content") or "").strip()
    meta = {
        "doc_id": row.get("doc_id") or row.get("id"),
        "title": row.get("title"),
        "source": row.get("source"),
        "publish_date": row.get("publish_date") or row.get("date"),
        "company": row.get("company"),
        "stock_code": row.get("stock_code"),
    }
    header = "\n".join(f"{k}: {v}" for k, v in meta.items() if v)
    return f"{header}\n\n{text}".strip()


def _doc_filename(row: dict[str, Any], fallback: str) -> str:
    doc_id = str(row.get("doc_id") or row.get("id") or fallback)
    title = str(row.get("title") or "")
    return sanitize_filename(f"{doc_id}_{title}".strip("_")) + ".txt"


def _convert_jsonl(path: Path, target: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            text = _format_document(row)
            if not text:
                continue
            out = target / _doc_filename(row, f"{path.stem}_{idx}")
            out.write_text(text, encoding="utf-8")
            count += 1
    return count


def _convert_csv(path: Path, target: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            text = _format_document(row)
            if not text:
                continue
            out = target / _doc_filename(row, f"{path.stem}_{idx}")
            out.write_text(text, encoding="utf-8")
            count += 1
    return count


def _convert_pdf(path: Path, target: Path) -> int:
    try:
        from pypdf import PdfReader
    except ImportError:
        return 0

    reader = PdfReader(str(path))
    text = "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if not text:
        return 0
    out = target / f"{sanitize_filename(path.stem)}_{stable_id(path.name)}.txt"
    out.write_text(text, encoding="utf-8")
    return 1


def _convert_docx(path: Path, target: Path) -> int:
    try:
        import docx
    except ImportError:
        return 0

    document = docx.Document(str(path))
    text = "\n".join(p.text for p in document.paragraphs if p.text).strip()
    if not text:
        return 0
    out = target / f"{sanitize_filename(path.stem)}_{stable_id(path.name)}.txt"
    out.write_text(text, encoding="utf-8")
    return 1
