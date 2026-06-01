param(
  [string]$StructuredDir = "data/sample",
  [string]$GraphRagRoot = "data/graphrag"
)

$ErrorActionPreference = "Stop"

fan-kg doctor
fan-kg init-schema
fan-kg load-structured --structured-dir $StructuredDir
fan-kg prepare-docs --source data/raw/documents --target "$GraphRagRoot/input"

Write-Host "MVP base graph is loaded."
Write-Host "Next run GraphRAG when $GraphRagRoot/.env has a valid GRAPHRAG_API_KEY:"
Write-Host "  graphrag index --root $GraphRagRoot"
Write-Host "  fan-kg import-graphrag --output-dir $GraphRagRoot/output"

fan-kg build-signals --structured-dir $StructuredDir --out data/processed/fan_signals.csv
