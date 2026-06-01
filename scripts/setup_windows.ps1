param(
  [string]$Python = "py -3.12"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
}

Invoke-Expression "$Python -m venv .venv"
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev,docs]"

Write-Host "Environment ready. Activate with: .\.venv\Scripts\Activate.ps1"
