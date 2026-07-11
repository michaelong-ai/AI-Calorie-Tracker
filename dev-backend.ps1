# dev-backend.ps1 — start the FastAPI backend for local development.
# Usage: right-click > Run with PowerShell, or from a terminal:  .\dev-backend.ps1
#
# What it does, step by step:
#   1. Moves into the backend folder (so relative paths resolve correctly).
#   2. Runs uvicorn (the web server) FROM THE PROJECT'S OWN virtual
#      environment (.venv) — this guarantees we use the exact package
#      versions installed for this project, not whatever is global.
#   3. --reload watches the source files and restarts the server on save.
#
# The API is then available at:  http://localhost:8000
# Interactive API docs at:       http://localhost:8000/docs

Set-Location "$PSScriptRoot\backend"   # $PSScriptRoot = folder this script lives in

# "python -m uvicorn" (instead of calling uvicorn.exe directly) matters on
# Windows: pip bakes the venv's ABSOLUTE path into every .exe launcher it
# creates, so renaming/moving the project folder breaks those launchers
# ("Fatal error in launcher"). python.exe itself locates the venv relatively
# and keeps working — this line survives a folder rename.
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --port 8000
