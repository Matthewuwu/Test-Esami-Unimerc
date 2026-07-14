#!/usr/bin/env bash
# Prepara l'ambiente per lo scraper (una volta sola).
# Su Arch/Manjaro pip non può installare a livello di sistema: usiamo un venv.
set -e
cd "$(dirname "$0")"

echo "📦 Creo l'ambiente virtuale (.venv)..."
python -m venv .venv
source .venv/bin/activate

echo "⬆️  Aggiorno pip..."
pip install --upgrade pip >/dev/null

echo "📦 Installo Playwright..."
pip install playwright

echo "🌐 Scarico il browser Chromium (l'avviso 'not officially supported' è normale su Arch)..."
playwright install chromium

echo ""
echo "✅ Pronto! Ora lancia lo scraper con:"
echo "   ./avvia.sh \"https://www.unimercatorum.it/.../lezione\" --debug"
