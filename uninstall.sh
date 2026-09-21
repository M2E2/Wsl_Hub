#!/usr/bin/env bash
# Rimuove WSL Hub.
#   ./uninstall.sh          rimuove programma, icona e avvio automatico
#   ./uninstall.sh --purge  rimuove anche configurazione e log
set -euo pipefail

if [ "$(id -u)" -eq 0 ]; then
    echo "Errore: esegui lo script come utente normale, senza sudo." >&2
    exit 1
fi

DEST="$HOME/.local/share/wsl-hub"
DESKTOP_FILE="/usr/share/applications/wsl-hub.desktop"
BASHRC="$HOME/.bashrc"
BEGIN="# >>> WSL Hub autostart >>>"
END="# <<< WSL Hub autostart <<<"

if grep -qF "$BEGIN" "$BASHRC" 2>/dev/null; then
    sed -i "/^$BEGIN\$/,/^$END\$/d" "$BASHRC"
    echo "Avvio automatico rimosso da ~/.bashrc"
fi

pkill -u "$(id -u)" -f "wsl-hub/wsl_hub.py" 2>/dev/null || true
rm -rf "$DEST"
if [ -f "$DESKTOP_FILE" ]; then
    sudo rm -f "$DESKTOP_FILE"
fi
echo "Programma e icona rimossi."

# Rimuovo le icone installate (se presenti)
sudo rm -f /usr/share/icons/hicolor/16x16/apps/wsl-hub.png || true
sudo rm -f /usr/share/icons/hicolor/24x24/apps/wsl-hub.png || true
sudo rm -f /usr/share/icons/hicolor/32x32/apps/wsl-hub.png || true
sudo rm -f /usr/share/icons/hicolor/48x48/apps/wsl-hub.png || true
sudo rm -f /usr/share/icons/hicolor/64x64/apps/wsl-hub.png || true
sudo rm -f /usr/share/icons/hicolor/128x128/apps/wsl-hub.png || true
sudo rm -f /usr/share/icons/hicolor/256x256/apps/wsl-hub.png || true
sudo rm -f /usr/share/icons/hicolor/scalable/apps/wsl-hub.svg || true

# Aggiorna la cache delle icone se possibile
sudo gtk-update-icon-cache -f /usr/share/icons/hicolor >/dev/null 2>&1 || true

# Rimuovo icona in /usr/share/pixmaps
sudo rm -f /usr/share/pixmaps/wsl-hub.png || true

if [ "${1:-}" = "--purge" ]; then
    rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/wsl-hub" "${XDG_CACHE_HOME:-$HOME/.cache}/wsl-hub"
    echo "Configurazione e log rimossi."
else
    echo "Configurazione conservata in ~/.config/wsl-hub (usa --purge per rimuoverla)."
fi
echo "L'icona sparirà dal menu Start di Windows dopo «wsl --shutdown» da PowerShell."
