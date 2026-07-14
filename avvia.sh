#!/usr/bin/env bash
# Avvia lo scraper dentro l'ambiente virtuale, passando tutti gli argomenti.
# Esempi:
#   ./avvia.sh "https://www.unimercatorum.it/.../lezione"
#   ./avvia.sh "URL" --debug
#   ./avvia.sh            (usa gli URL in dispense_urls.txt)
cd "$(dirname "$0")"
if [ ! -d ".venv" ]; then
  echo "⚠️  Ambiente non trovato. Esegui prima:  ./setup.sh"
  exit 1
fi
source .venv/bin/activate
python scarica_dispense.py "$@"
