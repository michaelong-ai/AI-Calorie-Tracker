# dev-bot.ps1 — start the Telegram meal-logging bot for local use (T6.2/T6.3).
# Usage from a terminal in the project root:  .\dev-bot.ps1
#
# What it does:
#   1. Moves into the backend folder (so .env and the DB resolve correctly).
#   2. Runs the long-polling bot FROM THE PROJECT'S OWN virtual environment,
#      so it uses the exact installed package versions.
#
# The bot needs TELEGRAM_BOT_TOKEN in backend/.env (from @BotFather). It runs
# INDEPENDENTLY of dev-backend.ps1 — it calls the estimation and save code
# directly, so the web server does NOT need to be running. Your PC does, though
# (long polling means this process is what talks to Telegram).
#
# Stop it with Ctrl+C.

Set-Location "$PSScriptRoot\backend"   # $PSScriptRoot = folder this script lives in

# "python -m" (not a .exe launcher) so a folder rename can't break it — same
# reason as dev-backend.ps1.
& ".\.venv\Scripts\python.exe" -m app.telegram_bot
