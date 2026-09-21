#!/usr/bin/env bash
# Attiva o disattiva l'avvio automatico di WSL Hub all'apertura di WSL.
#   ./autostart.sh             attiva (il terminale di WSL resta aperto)
#   ./autostart.sh --only-hub  attiva e chiude la console: resta solo l'hub
#   ./autostart.sh --remove    disattiva
set -euo pipefail

BASHRC="$HOME/.bashrc"
BEGIN="# >>> WSL Hub autostart >>>"
END="# <<< WSL Hub autostart <<<"
LAUNCHER="$HOME/.local/share/wsl-hub/wsl-hub"

if [ "$(id -u)" -eq 0 ]; then
    echo "Errore: esegui lo script come utente normale, senza sudo." >&2
    exit 1
fi

remove_block() {
    if grep -qF "$BEGIN" "$BASHRC" 2>/dev/null; then
        sed -i "/^$BEGIN\$/,/^$END\$/d" "$BASHRC"
    fi
}

case "${1:-}" in
    --remove)
        remove_block
        echo "Avvio automatico disattivato."
        exit 0 ;;
    --only-hub) CLOSE_CONSOLE=1 ;;
    "") CLOSE_CONSOLE=0 ;;
    *) echo "Uso: $0 [--only-hub | --remove]" >&2; exit 1 ;;
esac

if [ ! -x "$LAUNCHER" ]; then
    echo "Errore: $LAUNCHER non trovato. Esegui prima ./install.sh" >&2
    exit 1
fi

cp "$BASHRC" "$BASHRC.bak-wsl-hub"
remove_block
cat >> "$BASHRC" <<EOF
$BEGIN
# Avvia WSL Hub quando si apre WSL (non dentro l'hub stesso né in VS Code).
WSL_HUB_CLOSE_CONSOLE=$CLOSE_CONSOLE
if [[ \$- == *i* && -z "\$WSL_HUB" && -n "\$WSL_DISTRO_NAME" \\
      && "\$TERM_PROGRAM" != "vscode" && -z "\$VSCODE_IPC_HOOK_CLI" ]]; then
    if ! pgrep -u "\$(id -u)" -f "wsl-hub/wsl_hub.py" > /dev/null 2>&1; then
        _hub_wslg=""
        for _p in "/mnt/c/Program Files/WSL/wslg.exe" "/mnt/c/Windows/System32/wslg.exe"; do
            if [ -f "\$_p" ]; then _hub_wslg="\$_p"; break; fi
        done
        if [ -n "\$_hub_wslg" ]; then
            # Avviato tramite wslg.exe l'hub è una sessione WSL a sé:
            # continua a funzionare anche se chiudi questa console.
            ( cd /mnt/c && "\$_hub_wslg" -d "\$WSL_DISTRO_NAME" --cd "~" -- "$LAUNCHER" \\
                > /dev/null 2>&1 & )
        else
            setsid -f "$LAUNCHER" > /dev/null 2>&1
        fi
        unset _hub_wslg _p
        if [ "\$WSL_HUB_CLOSE_CONSOLE" = 1 ] && [ "\${SHLVL:-1}" -le 1 ]; then
            sleep 1
            exit 0
        fi
    fi
fi
$END
EOF

bash -n "$BASHRC" || { echo "Errore di sintassi: ripristino il backup" >&2; cp "$BASHRC.bak-wsl-hub" "$BASHRC"; exit 1; }

echo "Avvio automatico attivato (backup di .bashrc: $BASHRC.bak-wsl-hub)."
if [ "$CLOSE_CONSOLE" = 1 ]; then
    echo "All'apertura di WSL la console si chiuderà e resterà solo l'hub."
    echo "Se l'hub è già aperto, la console resta disponibile normalmente."
fi
echo "Per disattivarlo: ./autostart.sh --remove"
