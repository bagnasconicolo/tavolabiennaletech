#!/bin/bash

# Loading bar function
show_progress() {
  local current=$1
  local total=$2
  local percent=$((current * 100 / total))
  local filled=$((percent / 5))
  local empty=$((20 - filled))

  printf "\r["
  printf "%${filled}s" | tr ' ' '█'
  printf "%${empty}s" | tr ' ' '░'
  printf "] %3d%%" "$percent"
  printf "\n"
}

RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
CYAN="\033[0;36m"
NC="\033[0m"

timestamp() {
  date +"%H:%M:%S"
}

log_info() {
  echo -e "${CYAN}[$(timestamp)] INFO${NC} $1"
}

log_ok() {
  echo -e "${GREEN}[$(timestamp)] OK${NC} $1"
}

log_warn() {
  echo -e "${YELLOW}[$(timestamp)] WARN${NC} $1"
}

log_err() {
  echo -e "${RED}[$(timestamp)] ERROR${NC} $1"
}

SKIP_PDF=0
for arg in "$@"; do
  case "$arg" in
    --skip-pdf|--no-pdf)
      SKIP_PDF=1
      ;;
  esac
done

echo ""
echo "================================"
echo "🚀 Tracker Update Script"
echo "================================"
echo ""
log_info "Avvio con opzioni: $*"

TOTAL_STEPS=14
APPS_SCRIPT_DIR="apps-script"
APPS_SCRIPT_PROJECT_ID="1_Ph_bUS6lbFpWPIlhDZQUjIT7QZyGVZRG0todZ1o2GYhgj1Y0-OCDbJF"
APPS_SCRIPT_DEPLOYMENT_ID="AKfycbz2T-xieiHlll6pCUfHaoP9GQHACdcJhDD52Z5pCoSCj1S09vhzRZfL2kNJHJ-l8kL9cA"

log_info "[1/${TOTAL_STEPS}] Attivo ambiente virtuale"
show_progress 1 "$TOTAL_STEPS"
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
  source venv/Scripts/activate
else
  source venv/bin/activate
fi
echo ""
log_ok "[2/${TOTAL_STEPS}] Ambiente pronto"
show_progress 2 "$TOTAL_STEPS"
echo ""

log_info "[3/${TOTAL_STEPS}] Aggiornamento repository"
show_progress 3 "$TOTAL_STEPS"
if ! git diff --quiet || ! git diff --cached --quiet; then
  log_warn "Working tree dirty: salto git pull"
else
  git pull >/dev/null
fi
log_ok "[4/${TOTAL_STEPS}] Repository aggiornato"
show_progress 4 "$TOTAL_STEPS"
echo ""

log_info "[5/${TOTAL_STEPS}] Sync Apps Script"
show_progress 5 "$TOTAL_STEPS"
if command -v clasp >/dev/null 2>&1; then
  if [[ -f ".clasp.json" ]]; then
    clasp pull >/dev/null
    if git status --porcelain "$APPS_SCRIPT_DIR" | grep -q .; then
      log_info "Apps Script modificato: deploy in corso"
      clasp deploy -i "$APPS_SCRIPT_DEPLOYMENT_ID" -d "Auto deploy $(date +"%Y-%m-%d %H:%M:%S")" >/dev/null
    else
      log_info "Nessuna modifica Apps Script"
    fi
  else
    log_warn "Manca .clasp.json. Esegui: clasp clone \"$APPS_SCRIPT_PROJECT_ID\" --rootDir \"$APPS_SCRIPT_DIR\""
  fi
else
  log_warn "clasp non installato: salto sync Apps Script"
fi
log_ok "[6/${TOTAL_STEPS}] Apps Script sync completato"
show_progress 6 "$TOTAL_STEPS"
echo ""

log_info "[7/${TOTAL_STEPS}] Generazione HTML"
show_progress 7 "$TOTAL_STEPS"
python v3.py \
  --api-url "https://script.google.com/macros/s/AKfycbz2T-xieiHlll6pCUfHaoP9GQHACdcJhDD52Z5pCoSCj1S09vhzRZfL2kNJHJ-l8kL9cA/exec" \
  --output ./html/index.html \
  --title "Tracker progressi - Piccolo Museo della Tavola Periodica @ Biennale Tech 2026 – campioni"
echo ""
log_ok "[8/${TOTAL_STEPS}] HTML generato"
show_progress 8 "$TOTAL_STEPS"
echo ""

if [[ "$SKIP_PDF" -eq 1 ]]; then
  log_info "[9/${TOTAL_STEPS}] Salto PDF (flag attivo)"
  show_progress 9 "$TOTAL_STEPS"
  echo ""
  log_ok "[10/${TOTAL_STEPS}] PDF saltato"
  show_progress 10 "$TOTAL_STEPS"
else
  log_info "[9/${TOTAL_STEPS}] Generazione PDF"
  show_progress 9 "$TOTAL_STEPS"
  python generate_pdf_report.py \
    --api-url "https://script.google.com/macros/s/AKfycbz2T-xieiHlll6pCUfHaoP9GQHACdcJhDD52Z5pCoSCj1S09vhzRZfL2kNJHJ-l8kL9cA/exec" \
    --output ./output/elementi_report.pdf \
    --subtitle "Piccolo Museo della Tavola Periodica @ Biennale Tech 2026"
  echo ""
  log_ok "[10/${TOTAL_STEPS}] PDF generato"
  show_progress 10 "$TOTAL_STEPS"
fi
echo ""

log_info "[11/${TOTAL_STEPS}] Staging"
show_progress 11 "$TOTAL_STEPS"
git add .
log_ok "[12/${TOTAL_STEPS}] File in staging"
show_progress 12 "$TOTAL_STEPS"

log_info "[13/${TOTAL_STEPS}] Commit"
show_progress 13 "$TOTAL_STEPS"
if ! git commit -m "Aggiornamento automatico dei dati" >/dev/null; then
  log_warn "Nessuna modifica da committare"
fi

log_info "[14/${TOTAL_STEPS}] Push"
show_progress 14 "$TOTAL_STEPS"
git push >/dev/null
log_ok "[${TOTAL_STEPS}/${TOTAL_STEPS}] Repository aggiornato"
show_progress "$TOTAL_STEPS" "$TOTAL_STEPS"
echo ""
echo "================================"
log_ok "Tutte le operazioni completate"
show_progress "$TOTAL_STEPS" "$TOTAL_STEPS"
echo "================================"
echo ""
