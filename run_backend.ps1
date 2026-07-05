param(
    [int]$Port = 8000
)

Write-Host "Starting FastAPI on http://127.0.0.1:$Port"
& .\venv\Scripts\uvicorn.exe src.main:app --reload --reload-dir src --reload-dir ui --reload-exclude logs --reload-exclude data --port $Port
