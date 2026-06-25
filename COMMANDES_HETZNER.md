# Commandes Hetzner — ZeroToHeroBTC

## Se connecter au serveur
```bash
ssh -i ~/.ssh/id_hetzner root@178.105.136.96
```

## Lancer le bot (VPN requis !)
```bash
nordvpn connect Spain
/opt/zth_venv/bin/python3 /opt/bottrading/bot/zerotoherobtc.py
```

## Séquence complète après reboot serveur
```bash
nordvpn allowlist add port 22   # ← TOUJOURS faire ça en premier sinon SSH se bloque
nordvpn connect Spain
/opt/zth_venv/bin/python3 /opt/bottrading/bot/zerotoherobtc.py
```

## Connecter NordVPN (si déconnecté)
```bash
nordvpn allowlist add port 22
nordvpn connect Spain
```

## Login NordVPN (si token expiré)
```bash
nordvpn login --token TON_TOKEN_ICI
```
→ Token à générer sur my.nordaccount.com → Access tokens

## Mettre à jour le code (git pull)
```bash
cd /opt/bottrading && git pull
```

## Mettre à jour + relancer (tout en une fois)
```bash
cd /opt/bottrading && git pull && /opt/zth_venv/bin/python3 /opt/bottrading/bot/zerotoherobtc.py
```

## Voir les logs sauvegardés
```bash
cat /opt/zth.log
tail -50 /opt/zth.log
```

## Vérifier si le bot tourne
```bash
ps aux | grep zerotoherobtc
```

## Arrêter le bot (si lancé en arrière-plan)
```bash
pkill -f zerotoherobtc.py
```

## Installer / mettre à jour les packages Python
```bash
/opt/zth_venv/bin/pip install polymarket-client eth-account eth-utils eth-abi hexbytes pycryptodome
```

## Modifier le fichier .env
```bash
nano /opt/bottrading/bot/.env
```

## Voir le contenu du .env
```bash
cat /opt/bottrading/bot/.env
```
