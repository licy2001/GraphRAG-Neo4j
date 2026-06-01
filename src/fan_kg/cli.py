from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from fan_kg.graphrag.importer import import_graphrag_output
from fan_kg.graphrag.prepare_docs import prepare_documents
from fan_kg.graph.neo4j_client import Neo4jClient
from fan_kg.graph.schema import init_schema as create_schema
from fan_kg.loaders.structured import load_all_structured, load_quant_signals
from fan_kg.rag.hybrid_query import fan_company_context, run_graphrag_query
from fan_kg.settings import Settings
from fan_kg.signals.build import build_fan_signals

app = typer.Typer(help="Fan industry GraphRAG + Neo4j toolkit.")
console = Console()


def _settings() -> Settings:
    return Settings.from_env(Path.cwd())


def _client() -> Neo4jClient:
    settings = _settings()
    return Neo4jClient(
        settings.neo4j_uri,
        settings.neo4j_username,
        settings.neo4j_password,
        settings.neo4j_database,
    )


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else Path.cwd() / path


def _find_command(command: str) -> str:
    found = shutil.which(command)
    if found:
        return found
    scripts_dir = Path(sys.executable).parent
    for suffix in (".exe", ".cmd", ".bat", ""):
        candidate = scripts_dir / f"{command}{suffix}"
        if candidate.exists():
            return str(candidate)
    return ""


@app.command("doctor")
def doctor() -> None:
    """Check local environment and project wiring."""
    settings = _settings()
    table = Table(title="Fan KG Doctor")
    table.add_column("Item")
    table.add_column("Status")
    table.add_column("Detail")

    py_ok = (3, 10) <= sys.version_info[:2] < (3, 13)
    table.add_row("Python", "OK" if py_ok else "WARN", sys.version.split()[0])
    graphrag_cli = _find_command("graphrag")
    table.add_row("graphrag CLI", "OK" if graphrag_cli else "MISS", graphrag_cli)
    table.add_row("Project root", "OK", str(settings.root))
    table.add_row("Structured dir", "OK" if settings.structured_dir.exists() else "MISS", str(settings.structured_dir))
    table.add_row("GraphRAG root", "OK" if settings.graphrag_root.exists() else "MISS", str(settings.graphrag_root))

    try:
        with _client() as client:
            client.verify()
        table.add_row("Neo4j", "OK", settings.neo4j_uri)
    except Exception as exc:  # noqa: BLE001
        table.add_row("Neo4j", "WARN", str(exc))

    console.print(table)


@app.command("init-schema")
def init_schema(
    ontology: Path = typer.Option(Path("config/ontology.yaml"), "--ontology", help="Ontology YAML."),
) -> None:
    """Create Neo4j constraints and seed the fan ontology."""
    ontology_path = _resolve(ontology)
    with _client() as client:
        create_schema(client, ontology_path)
    console.print(f"[green]Initialized schema and ontology from {ontology_path}[/green]")


@app.command("load-structured")
def load_structured(
    structured_dir: Path = typer.Option(
        Path("data/raw/structured"), "--structured-dir", help="CSV directory."
    ),
) -> None:
    """Load industry, company, sales, weather, commodity and market CSVs into Neo4j."""
    with _client() as client:
        counts = load_all_structured(client, _resolve(structured_dir))
    console.print_json(json.dumps(counts, ensure_ascii=False))


@app.command("prepare-docs")
def prepare_docs(
    source: Path = typer.Option(Path("data/raw/documents"), "--source", help="Raw document dir."),
    target: Path = typer.Option(Path("data/graphrag/input"), "--target", help="GraphRAG input dir."),
) -> None:
    """Convert raw documents into Microsoft GraphRAG input text files."""
    counts = prepare_documents(_resolve(source), _resolve(target))
    console.print_json(json.dumps(counts, ensure_ascii=False))


@app.command("import-graphrag")
def import_graphrag(
    output_dir: Path = typer.Option(
        Path("data/graphrag/output"), "--output-dir", help="Microsoft GraphRAG output dir."
    ),
) -> None:
    """Import Microsoft GraphRAG parquet outputs into Neo4j."""
    with _client() as client:
        counts = import_graphrag_output(client, _resolve(output_dir))
    console.print_json(json.dumps(counts, ensure_ascii=False))


@app.command("build-signals")
def build_signals(
    structured_dir: Path = typer.Option(
        Path("data/raw/structured"), "--structured-dir", help="CSV directory."
    ),
    out: Path = typer.Option(Path("data/processed/fan_signals.csv"), "--out", help="Output CSV."),
    write_neo4j: bool = typer.Option(True, "--write-neo4j/--no-write-neo4j"),
) -> None:
    """Build fan theme quant signals from structured data."""
    records = build_fan_signals(_resolve(structured_dir), _resolve(out))
    written = 0
    if write_neo4j and records:
        with _client() as client:
            written = load_quant_signals(client, records)
    console.print_json(
        json.dumps(
            {"signals": len(records), "neo4j_written": written, "output": str(_resolve(out))},
            ensure_ascii=False,
        )
    )


@app.command("graph-context")
def graph_context(
    product: str = typer.Option("风扇", "--product"),
    limit: int = typer.Option(20, "--limit"),
) -> None:
    """Show companies exposed to the fan product category from Neo4j."""
    with _client() as client:
        rows = fan_company_context(client, product, limit)
    console.print_json(json.dumps(rows, ensure_ascii=False))


@app.command("ask-graphrag")
def ask_graphrag(
    question: str = typer.Argument(...),
    root: Path = typer.Option(Path("data/graphrag"), "--root"),
    method: str = typer.Option("local", "--method"),
) -> None:
    """Proxy to Microsoft GraphRAG query."""
    answer = run_graphrag_query(question, _resolve(root), method=method)
    console.print(answer)


if __name__ == "__main__":
    app()
