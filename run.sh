source venv/bin/activate
echo "👀 Generating ./html/index.html"
python v2.py \
  --api-url "https://script.google.com/macros/s/AKfycbwaaePQ5ou6wDggvkpsPvYhYHrZ7W9TpM7QZeVhFhgmjzDl6liP26R3rxaXHlKmJLQidg/exec" \
  --output ./html/index.html \
  --title "Tracker progressi - Piccolo Museo della Tavola Periodica @ Biennale Tech 2026 – campioni" 
echo "✅ Generated ./html/index.html"
echo "✅ Updating remote repository"
git add .
echo "✅ Committing and pushing changes to remote repository"
git commit -m "Aggiornamento automatico dei dati"
echo "✅ Pushing changes to remote repository"
git push
echo "✅ Aggiornato il repository remoto"
echo "🚀 Done!"
