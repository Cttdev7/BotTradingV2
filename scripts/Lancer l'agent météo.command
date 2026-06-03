#!/bin/bash
cd "$(dirname "$0")/.."
echo "🌦  Agent Météo Polymarket"
echo "   Analyse les marchés météo toutes les heures"
echo "   Tracking des paris à 85%+"
echo ""
python3 bot/agent_meteo.py
