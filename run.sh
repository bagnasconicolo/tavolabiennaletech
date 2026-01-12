echo "Generating ./html/index.html"
python v2.py \
  --api-url "https://script.google.com/macros/s/AKfycbwaaePQ5ou6wDggvkpsPvYhYHrZ7W9TpM7QZeVhFhgmjzDl6liP26R3rxaXHlKmJLQidg/exec" \
  --output ./html/index.html \
  --title "Tracker progressi - Piccolo Museo della Tavola Periodica @ Biennale Tech 2026 – campioni" 
echo "Generated ./html/index.html"

git add .
git commit -m "Aggiornamento automatico dei dati"
git push
