#!/bin/bash
cd "/Users/clementctt/Documents/Claude code/Bottrading V2"
echo "Dashboard lancé sur http://localhost:8080"
open http://localhost:8080
python3 -m http.server 8080
