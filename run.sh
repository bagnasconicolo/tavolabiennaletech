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
echo "[1/10] Setting up environment..."
show_progress 1 10
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
  source venv/Scripts/activate
else
  source venv/bin/activate
fi
echo ""
echo "[2/10] Environment ready ✅"
show_progress 2 10
echo ""
echo "[3/10] Generating HTML report..."
show_progress 3 10
python v2.py \
  --api-url "https://script.google.com/macros/s/AKfycbwaaePQ5ou6wDggvkpsPvYhYHrZ7W9TpM7QZeVhFhgmjzDl6liP26R3rxaXHlKmJLQidg/exec" \
  --output ./html/index.html \
  --title "Tracker progressi - Piccolo Museo della Tavola Periodica @ Biennale Tech 2026 – campioni" 
echo ""
echo "[4/10] HTML generated successfully ✅"
show_progress 4 10
echo ""
echo "[5/10] Updating git repository..."
show_progress 5 10
git add .
echo "[6/10] Files staged ✅"
show_progress 6 10
echo "[7/10] Committing changes..."
show_progress 7 10
git commit -m "Aggiornamento automatico dei dati"
echo "[8/10] Pushing to remote..."
show_progress 8 10
git push
echo "[9/10] Repository updated ✅"
show_progress 9 10
echo ""
echo "================================"
echo "🎉 All tasks completed!"
show_progress 10 10
echo "================================"
echo ""