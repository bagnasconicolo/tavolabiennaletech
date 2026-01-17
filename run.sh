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
echo "[1/11] Setting up environment..."
show_progress 1 11
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
  source venv/Scripts/activate
else
  source venv/bin/activate
fi
echo ""
echo "[2/11] Environment ready ✅"
show_progress 2 11
echo ""
echo "[3/11] Pulling latest changes..."
show_progress 3 11
git pull
echo "[4/11] Repository updated ✅"
show_progress 4 11
echo ""
echo "[5/11] Generating HTML report..."
show_progress 5 11
python v2.py \
  --api-url "https://script.google.com/macros/s/AKfycbwaaePQ5ou6wDggvkpsPvYhYHrZ7W9TpM7QZeVhFhgmjzDl6liP26R3rxaXHlKmJLQidg/exec" \
  --output ./html/index.html \
  --title "Tracker progressi - Piccolo Museo della Tavola Periodica @ Biennale Tech 2026 – campioni" 
echo ""
echo "[6/11] HTML generated successfully ✅"
show_progress 6 11
echo ""
echo "[7/11] Staging changes..."
show_progress 7 11
git add .
echo "[8/11] Files staged ✅"
show_progress 8 11
echo "[9/11] Committing changes..."
show_progress 9 11
git commit -m "Aggiornamento automatico dei dati"
echo "[10/11] Pushing to remote..."
show_progress 10 11
git push
echo "[11/11] Repository updated ✅"
show_progress 11 11
echo ""
echo "================================"
echo "🎉 All tasks completed!"
show_progress 11 11
echo "================================"
echo ""