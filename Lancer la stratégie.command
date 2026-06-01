#!/bin/bash
cd "/Users/clementctt/Documents/Claude code/Bottrading V2"
echo "🧠 Démarrage de la boucle de trading..."
echo "   Le bot va analyser les marchés et trader automatiquement."
echo "   Mode simulation (DRY_RUN=true) — aucun vrai ordre envoyé."
echo "   Pour passer en réel : mets DRY_RUN=false dans bot/.env"
echo "   Pour arrêter : Ctrl+C"
echo ""
python3 bot/loop.py
