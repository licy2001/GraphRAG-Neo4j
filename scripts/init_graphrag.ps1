param(
  [string]$Root = "data/graphrag",
  [string]$Model = $env:GRAPHRAG_MODEL,
  [string]$EmbeddingModel = $env:GRAPHRAG_EMBEDDING_MODEL
)

$ErrorActionPreference = "Stop"

if (-not $Model) { $Model = "gpt-4.1-mini" }
if (-not $EmbeddingModel) { $EmbeddingModel = "text-embedding-3-small" }

graphrag init --root $Root --force --model $Model --embedding-model $EmbeddingModel

Write-Host "GraphRAG initialized at $Root"
Write-Host "Put API key in $Root/.env as GRAPHRAG_API_KEY=..."
Write-Host "Put text files in $Root/input or run: fan-kg prepare-docs"
