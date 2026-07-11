# run-tests.ps1 — run the backend unit tests.
# Usage, from a terminal in the project root:  .\run-tests.ps1
#
# What it does:
#   1. Moves into the backend folder.
#   2. Runs pytest from the project's virtual environment.
#      "python -m pytest" (instead of plain "pytest") also puts the current
#      folder on Python's import path, which is how the tests can do
#      "import app.db".
#   -q = quiet: one line per test instead of a wall of text.
#
# pytest automatically discovers every tests/test_*.py file and runs every
# function inside named test_*.

Set-Location "$PSScriptRoot\backend"
& ".\.venv\Scripts\python.exe" -m pytest tests -q
