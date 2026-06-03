#!/bin/bash
launchctl unload ~/Library/LaunchAgents/com.tradingbot.agent_meteo.plist 2>/dev/null
pkill -f "agent_meteo.py" 2>/dev/null
echo "✅ Agent météo arrêté"
