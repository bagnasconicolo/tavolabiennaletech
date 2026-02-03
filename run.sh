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
}

echo ""
echo "================================"
echo "🚀 Tracker Update Script"
echo "================================"
echo ""
TOTAL_STEPS=14
APPS_SCRIPT_DIR="apps-script"
APPS_SCRIPT_PROJECT_ID="1_Ph_bUS6lbFpWPIlhDZQUjIT7QZyGVZRG0todZ1o2GYhgj1Y0-OCDbJF"
APPS_SCRIPT_DEPLOYMENT_ID="AKfycbz2T-xieiHlll6pCUfHaoP9GQHACdcJhDD52Z5pCoSCj1S09vhzRZfL2kNJHJ-l8kL9cA"

echo "[1/${TOTAL_STEPS}] Setting up environment..."
show_progress 1 "$TOTAL_STEPS"
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
  source venv/Scripts/activate
else
  source venv/bin/activate
fi
echo ""
echo "[2/${TOTAL_STEPS}] Environment ready ✅"
show_progress 2 "$TOTAL_STEPS"
echo ""
echo "[3/${TOTAL_STEPS}] Pulling latest changes..."
show_progress 3 "$TOTAL_STEPS"
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Working tree dirty; skipping git pull to avoid stash conflicts."
else
  git pull
fi
echo "[4/${TOTAL_STEPS}] Repository updated ✅"
show_progress 4 "$TOTAL_STEPS"
echo ""
echo "[5/${TOTAL_STEPS}] Syncing Apps Script..."
show_progress 5 "$TOTAL_STEPS"
if command -v clasp >/dev/null 2>&1; then
  if [[ -f ".clasp.json" ]]; then
    clasp pull
    if git status --porcelain "$APPS_SCRIPT_DIR" | grep -q .; then
      echo "Apps Script changes detected; deploying..."
      clasp deploy -i "$APPS_SCRIPT_DEPLOYMENT_ID" -d "Auto deploy $(date +"%Y-%m-%d %H:%M:%S")"
    else
      echo "No Apps Script changes; skipping deploy."
    fi
  else
    echo "Missing .clasp.json in repo root."
    echo "Run: clasp clone \"$APPS_SCRIPT_PROJECT_ID\" --rootDir \"$APPS_SCRIPT_DIR\""
  fi
else
  echo "clasp not installed; skipping Apps Script sync."
fi
echo "[6/${TOTAL_STEPS}] Apps Script sync done ✅"
show_progress 6 "$TOTAL_STEPS"
echo ""
echo "[7/${TOTAL_STEPS}] Generating HTML report..."
show_progress 7 "$TOTAL_STEPS"
python v3.py \
  --api-url "https://script.google.com/macros/s/AKfycbz2T-xieiHlll6pCUfHaoP9GQHACdcJhDD52Z5pCoSCj1S09vhzRZfL2kNJHJ-l8kL9cA/exec" \
  --output ./html/index.html \
  --title "Tracker progressi - Piccolo Museo della Tavola Periodica @ Biennale Tech 2026 – campioni"
echo ""
echo "[8/${TOTAL_STEPS}] HTML generated successfully ✅"
show_progress 8 "$TOTAL_STEPS"
echo ""
echo "[9/${TOTAL_STEPS}] Generating PDF report..."
show_progress 9 "$TOTAL_STEPS"
python generate_pdf_report.py \
  --api-url "https://script.google.com/macros/s/AKfycbz2T-xieiHlll6pCUfHaoP9GQHACdcJhDD52Z5pCoSCj1S09vhzRZfL2kNJHJ-l8kL9cA/exec" \
  --output ./output/elementi_report.pdf \
  --title "Report campioni per elemento" \
  --subtitle "Piccolo Museo della Tavola Periodica @ Biennale Tech 2026"
echo ""
echo "[10/${TOTAL_STEPS}] PDF report generated ✅"
show_progress 10 "$TOTAL_STEPS"
echo ""
echo "[11/${TOTAL_STEPS}] Staging changes..."
show_progress 11 "$TOTAL_STEPS"
git add .
echo "[12/${TOTAL_STEPS}] Files staged ✅"
show_progress 12 "$TOTAL_STEPS"
echo "[13/${TOTAL_STEPS}] Committing changes..."
show_progress 13 "$TOTAL_STEPS"
git commit -m "Aggiornamento automatico dei dati"
echo "[14/${TOTAL_STEPS}] Pushing to remote..."
show_progress 14 "$TOTAL_STEPS"
git push
echo "[${TOTAL_STEPS}/${TOTAL_STEPS}] Repository updated ✅"
show_progress "$TOTAL_STEPS" "$TOTAL_STEPS"
echo ""
echo "================================"
echo "🎉 All tasks completed!"
show_progress "$TOTAL_STEPS" "$TOTAL_STEPS"
echo "================================"
echo ""
