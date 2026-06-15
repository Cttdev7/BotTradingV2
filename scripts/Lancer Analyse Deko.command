#!/bin/bash
cd "/Users/clementctt/Documents/Claude code/Bottrading V2"
echo "🔍 Démarrage Analyse Deko..."
echo "   Surveillance de sailor82 sur Polymarket"
echo "   Cycle : toutes les 15 min"
echo "   Pour arrêter : Ctrl+C"
echo ""
~/.pyenv/versions/3.11.9/bin/python3 bot/agent_deko.py
