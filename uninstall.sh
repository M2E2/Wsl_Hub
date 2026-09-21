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

if [ "${1:-}" = "--purge" ]; then
    rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/wsl-hub" "${XDG_CACHE_HOME:-$HOME/.cache}/wsl-hub"
    echo "Configurazione e log rimossi."
else
    echo "Configurazione conservata in ~/.config/wsl-hub (usa --purge per rimuoverla)."
fi
echo "L'icona sparirà dal menu Start di Windows dopo «wsl --shutdown» da PowerShell."
