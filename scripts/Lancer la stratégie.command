#!/bin/bash
cd "/Users/clementctt/Documents/Claude code/Bottrading V2"
echo "🧠 Démarrage de la boucle de trading..."
echo "   Mode simulation (DRY_RUN=true)"
echo "   Pour arrêter : Ctrl+C"
echo ""
~/.pyenv/versions/3.11.9/bin/python3 bot/loop.py
