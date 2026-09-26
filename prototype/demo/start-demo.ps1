param([int]$Port = 8013)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$python = Join-Path $taskRoot '.venv/Scripts/python.exe'
$model = Join-Path $taskRoot 'bert_intent_tagger/model/checkpoints/best'
if (-not (Test-Path -LiteralPath (Join-Path $model 'model.safetensors'))) {
    $model = Join-Path $taskRoot 'prototype/models/bert-boundary'
}
if (-not (Test-Path -LiteralPath $python)) { throw 'Create .venv and install prototype/requirements-bert.txt first.' }
if (-not (Test-Path -LiteralPath (Join-Path $model 'model.safetensors'))) { throw 'Local BERT checkpoint is missing.' }
$env:CITEFRONTIER_DEMO = '1'
$env:CITEFRONTIER_BACKEND = 'lightweight'
$env:CITEFRONTIER_PARSER = 'auto'
$env:CITEFRONTIER_BERT_MODEL = $model
$env:CITEFRONTIER_BERT_THRESHOLD = '0.90'
$env:CITEFRONTIER_BERT_DISAGREE_THRESHOLD = '0.97'
Push-Location $taskRoot
try {
    Write-Host "Starting guarded BERT demo at http://127.0.0.1:$Port"
    Write-Host 'BERT serves accepted boundaries; spaCy is the explicit fallback.'
    & $python -m uvicorn prototype.server:app --host 127.0.0.1 --port $Port
} finally {
    Pop-Location
}
