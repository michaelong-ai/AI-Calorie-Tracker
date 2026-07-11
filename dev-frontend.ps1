# dev-frontend.ps1 — start the React frontend for local development.
# Usage: from a terminal:  .\dev-frontend.ps1
#
# What it does, step by step:
#   1. Moves into the frontend folder.
#   2. Runs Vite's dev server via npm. Vite compiles the TypeScript/React
#      code on the fly and hot-reloads the browser when you save a file.
#
# The app is then available at:  http://localhost:5173
# (5173 is Vite's default port; the backend allows this origin in its CORS
# config — see backend/app/main.py.)

Set-Location "$PSScriptRoot\frontend"
npm run dev
