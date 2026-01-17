echo "1/10 - 🚀 Setting up the environment"
source venv/bin/activate
echo "2/10 - 🚀 Starting the update process"
echo "3/10 - 👀 Generating ./html/index.html"
python v2.py \
  --api-url "https://script.google.com/macros/s/AKfycbwaaePQ5ou6wDggvkpsPvYhYHrZ7W9TpM7QZeVhFhgmjzDl6liP26R3rxaXHlKmJLQidg/exec" \
  --output ./html/index.html \
  --title "Tracker progressi - Piccolo Museo della Tavola Periodica @ Biennale Tech 2026 – campioni" 
echo "4/10 - ✅ Generated ./html/index.html"
echo "5/10 - ✅ Updating remote repository"
git add .
echo "6/10 - ✅ Committing and pushing changes to remote repository"
git commit -m "Aggiornamento automatico dei dati"
echo "7/10 - ✅ Pushing changes to remote repository"
git push
echo "8/10 - ✅ Aggiornato il repository remoto"
echo "9/10 - 🚀 Done!"
echo "10/10 - 🎉 All tasks completed successfully!"