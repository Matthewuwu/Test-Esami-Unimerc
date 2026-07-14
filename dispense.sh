#!/usr/bin/env bash
# ============================================================
#  UNICO COMANDO NECESSARIO.
#  Si aggiorna da GitHub, si prepara da solo e lancia lo scraper.
#
#  Esempi:
#    ./dispense.sh "https://lms.mercatorum.multiversity.click/videolezioni/XXX/52"
#    ./dispense.sh "URL" --debug          # mostra cosa trova senza scaricare
#    ./dispense.sh                        # usa gli URL in scraper/dispense_urls.txt
# ============================================================
set -e
cd "$(dirname "$0")"

# Python: su Arch "python" è già python3, altrove serve python3
PY=$(command -v python3 || command -v python)

# 1) AUTO-AGGIORNAMENTO — prende l'ultima versione dal repo.
#    (se sei offline o non è una cartella git, prosegue con quella che hai)
if git rev-parse --git-dir >/dev/null 2>&1; then
  echo "🔄 Controllo aggiornamenti..."
  git pull --ff-only 2>/dev/null && echo "   ok" || echo "   (offline o modifiche locali: uso la versione attuale)"
fi

# 2) AMBIENTE — creato e riempito solo la prima volta.
if [ ! -d .venv ]; then
  echo "📦 Prima esecuzione: preparo l'ambiente (serve solo questa volta)..."
  "$PY" -m venv .venv
fi
source .venv/bin/activate

python -c "import playwright" 2>/dev/null || {
  echo "📦 Installo Playwright..."
  pip install -q -r scraper/requirements.txt
}

if [ ! -f .venv/.chromium-ok ]; then
  echo "🌐 Scarico il browser (una volta sola; l'avviso 'not officially supported' su Arch è normale)..."
  playwright install chromium
  touch .venv/.chromium-ok
fi

# 3) VIA.
python scraper/scarica_dispense.py "$@"
