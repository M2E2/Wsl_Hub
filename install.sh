#!/usr/bin/env bash
# Installa WSL Hub nella distro WSL corrente e lo aggiunge al menu Start di Windows (via WSLg).
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="$HOME/.local/share/wsl-hub"
LAUNCHER="$DEST/wsl-hub"
DESKTOP_FILE="/usr/share/applications/wsl-hub.desktop"
DISTRO="${WSL_DISTRO_NAME:-Ubuntu}"

if [ "$(id -u)" -eq 0 ]; then
    echo "Errore: non lanciare questo script con sudo o come root." >&2
    echo "Eseguilo come utente normale (./install.sh): la password verrà chiesta quando serve." >&2
    exit 1
fi

if [ ! -f "$SRC_DIR/wsl_hub.py" ]; then
    echo "Errore: wsl_hub.py non trovato in $SRC_DIR" >&2
    echo "Metti wsl_hub.py nella stessa cartella di install.sh (controlla che il nome non sia" >&2
    echo "cambiato durante il download, es. 'wsl_hub (1).py')." >&2
    exit 1
fi

echo "==> Installo le dipendenze (GTK3, VTE, icone)"
# un repository di terze parti rotto non deve bloccare l'installazione
if ! sudo apt-get update -q; then
    echo "Attenzione: apt-get update ha segnalato errori (vedi sopra), proseguo comunque." >&2
fi
sudo apt-get install -y -q python3-gi gir1.2-gtk-3.0 gir1.2-vte-2.91 \
    adwaita-icon-theme librsvg2-common fonts-dejavu-core shared-mime-info \
    fonts-ibm-plex fonts-jetbrains-mono

echo "==> Copio i file in $DEST"
mkdir -p "$DEST"
install -m 755 "$SRC_DIR/wsl_hub.py" "$DEST/wsl_hub.py"

# Il launcher usa una shell di login: così l'hub (e le app che avvia) ricevono
# il PATH e le variabili definite in ~/.profile, anche se aperto dal menu Start.
cat > "$LAUNCHER" <<EOF
#!/bin/bash -l
exec /usr/bin/python3 "$DEST/wsl_hub.py" "\$@"
EOF
chmod 755 "$LAUNCHER"

echo "==> Registro l'icona (comparirà nel menu Start di Windows)"
sudo tee "$DESKTOP_FILE" > /dev/null <<EOF
[Desktop Entry]
Type=Application
Name=WSL Hub
Comment=Terminale, file e app di WSL in un'unica finestra
Exec=$LAUNCHER
Icon=utilities-terminal
Terminal=false
Categories=System;Utility;
StartupWMClass=wsl-hub
EOF

cat <<EOF

Fatto.

1. Da PowerShell esegui:  wsl --shutdown
   poi riapri la distro una volta: WSLg aggiornerà il menu Start.
2. Cerca «WSL Hub ($DISTRO)» nel menu Start e fissalo sulla barra delle applicazioni.

Se l'icona non compare, crea a mano un collegamento sul desktop di Windows con destinazione:

  "C:\\Program Files\\WSL\\wslg.exe" -d $DISTRO --cd "~" -- $LAUNCHER

(Con WSL installato dal sistema operativo e non dallo Store, il percorso è
 C:\\Windows\\System32\\wslg.exe.) wslg.exe avvia l'app senza aprire una console.

Configurazione: ~/.config/wsl-hub/config.json (creata al primo avvio).
EOF
