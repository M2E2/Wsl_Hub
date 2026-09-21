#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
"""
WSL Hub: an always-on terminal, a file manager and an app launcher for WSL.
Runs inside WSL and is displayed on Windows through WSLg.

Dependencies (Ubuntu/Debian):
    sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-vte-2.91 adwaita-icon-theme

Configuration: ~/.config/wsl-hub/config.json (created on first launch).
Logs of launched apps: ~/.cache/wsl-hub/logs/

Shortcuts:
    Ctrl+Shift+T  new terminal tab             Ctrl+Shift+W  close tab
    Ctrl+Shift+C  copy from the terminal       Ctrl+Shift+V  paste into the terminal
    Ctrl+Shift+A  show/hide the app panel      Ctrl+Shift+F  search apps
"""

import copy
import json
import os
import re
import select
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Vte", "2.91")
from gi.repository import Gdk, Gio, GLib, Gtk, Pango, Vte  # noqa: E402

__version__ = "0.1.0"

APP_TITLE = "WSL Hub"
CONFIG_DIR = Path(GLib.get_user_config_dir()) / "wsl-hub"
CONFIG_FILE = CONFIG_DIR / "config.json"
CACHE_DIR = Path(GLib.get_user_cache_dir()) / "wsl-hub"
LOG_DIR = CACHE_DIR / "logs"
SOCKET_PATH = CACHE_DIR / "instance.sock"
DISTRO = os.environ.get("WSL_DISTRO_NAME", "Linux")
HOME = str(Path.home())
OWN_DESKTOP_ID = "wsl-hub.desktop"


# --------------------------------------------------------------------------- #
# Translations
# --------------------------------------------------------------------------- #
# The source language is English. To add a language, add its code to LANGUAGES
# and a dictionary to TRANSLATIONS that maps each English string to its
# translation. Missing strings fall back to English.
LANGUAGES = {"en": "English", "it": "Italiano"}
TRANSLATIONS = {
    "it": {
        "the file does not contain a JSON object": "il file non contiene un oggetto JSON",
        "config.json is not valid ({error}). A copy was saved to {backup}; using the default values.": "config.json non valido ({error}). Copia salvata in {backup}; uso i valori predefiniti.",
        "Wrong password.": "Password errata.",
        "You need the password of your Linux user, the one you use with sudo.": "Serve la password del tuo utente Linux, quella che usi con sudo.",
        "the process is not running as root": "il processo non è root",
        "Wrong password?": "Password errata?",
        "Could not get root permissions.": "Impossibile ottenere i permessi di root.",
        "no response from the root process": "nessuna risposta dal processo root",
        "the root process has exited": "il processo root si è chiuso",
        "root mode is not active": "modalità root non attiva",
        "root process not available ({error})": "processo root non disponibile ({error})",
        "unknown error": "errore sconosciuto",
        "Cancel": "Annulla",
        "Root permissions": "Permessi di root",
        "Confirm": "Conferma",
        "Password for {user} (sudo):": "Password di {user} per sudo:",
        "Close": "Chiudi",
        "Terminal": "Terminale",
        "Could not start the terminal: {error}": "Impossibile avviare il terminale: {error}",
        "Copy": "Copia",
        "Paste": "Incolla",
        "Show this folder in the file panel": "Mostra questa cartella nel pannello file",
        "New terminal (Ctrl+Shift+T)": "Nuovo terminale (Ctrl+Shift+T)",
        "Terminal with profile": "Terminale con profilo",
        "Open a shell with the variables of a profile": "Apri una shell con le variabili di un profilo",
        "Root terminal": "Terminale root",
        "Open a root shell in the current folder": "Apri una shell come root nella cartella corrente",
        "No profiles defined": "Nessun profilo definito",
        "Manage profiles…": "Gestisci profili…",
        "Close (Ctrl+Shift+W)": "Chiudi (Ctrl+Shift+W)",
        "Back": "Indietro",
        "Parent folder": "Cartella superiore",
        "Refresh": "Aggiorna",
        "Show hidden files": "Mostra i file nascosti",
        "follow": "segui",
        "Follow the active terminal's folder": "Segui la cartella del terminale attivo",
        "Root mode: view and edit files as administrator": "Modalità root: vedi e modifica i file come amministratore",
        "Bookmarks": "Segnalibri",
        "Name": "Nome",
        "Size": "Dimensione",
        "Modified": "Modificato",
        "Root mode on: file changes are made as root": "Modalità root attiva: le modifiche ai file vengono fatte come root",
        "Folder not found: {path}": "Cartella non trovata: {path}",
        "%Y-%m-%d %H:%M": "%d/%m/%Y %H:%M",
        "Permission denied for {path}: turn on “root” to see its contents": "Permesso negato per {path}: attiva «root» per vederne il contenuto",
        "Could not read {path}: {error}": "Impossibile leggere {path}: {error}",
        "Go to…": "Vai a…",
        "New bookmark": "Nuovo segnalibro",
        "Bookmark name:": "Nome del segnalibro:",
        "Opened “{file}” with {app}": "Aperto «{file}» con {app}",
        "{app} does not start ({error}); trying with Windows": "{app} non si avvia ({error}); provo con Windows",
        "Edit as root": "Modifica come root",
        "Open": "Apri",
        "Open with the Windows program": "Apri con il programma di Windows",
        "Root terminal here": "Terminale root qui",
        "Go here in the terminal (cd)": "Vai qui nel terminale (cd)",
        "New terminal here": "Nuovo terminale qui",
        "Show in Windows File Explorer": "Mostra in Esplora file di Windows",
        "Paste the path in the terminal": "Incolla il percorso nel terminale",
        "Copy path": "Copia percorso",
        "Copy Windows path": "Copia percorso Windows",
        "Add to bookmarks…": "Aggiungi ai segnalibri…",
        "Rename…": "Rinomina…",
        "Delete permanently (root)…": "Elimina definitivamente (root)…",
        "Move to trash": "Sposta nel cestino",
        "New folder…": "Nuova cartella…",
        "New empty file…": "Nuovo file vuoto…",
        "wslpath is not available": "wslpath non disponibile",
        "Rename": "Rinomina",
        "New name for “{name}”:": "Nuovo nome per «{name}»:",
        "The name cannot contain “/”.": "Il nome non può contenere «/».",
        "An item named “{name}” already exists.": "Esiste già un elemento chiamato «{name}».",
        "Could not rename “{name}”.": "Impossibile rinominare «{name}».",
        "Permanently delete “{name}” as root?": "Eliminare definitivamente «{name}» come root?",
        "{path}\n\nIn root mode the trash is not used and this cannot be undone.": "{path}\n\nIn modalità root il cestino non viene usato e l'operazione non si può annullare.",
        "Delete permanently": "Elimina definitivamente",
        "“{name}” deleted": "«{name}» eliminato",
        "Could not delete “{name}”.": "Impossibile eliminare «{name}».",
        "Move “{name}” to the trash?": "Spostare «{name}» nel cestino?",
        "The trash is in ~/.local/share/Trash.": "Il cestino si trova in ~/.local/share/Trash.",
        "“{name}” moved to the trash": "«{name}» spostato nel cestino",
        "The trash is not available for “{name}”.": "Il cestino non è disponibile per «{name}».",
        "{error}\n\nDelete it permanently? This cannot be undone.": "{error}\n\nEliminarlo definitivamente? L'operazione non si può annullare.",
        "Could not create “{name}”.": "Impossibile creare «{name}».",
        "Search apps": "Cerca un'app",
        "Add app…": "Aggiungi app…",
        "Show system apps": "Mostra le app di sistema",
        "Untitled": "Senza nome",
        "Profiles: ": "Profili: ",
        "Right-click for more options": "Tasto destro per altre opzioni",
        "Start {name} with:": "Avvia {name} con:",
        "Start without a profile": "Avvia senza profilo",
        "Start with profile": "Avvia con il profilo",
        "Edit…": "Modifica…",
        "Remove": "Rimuovi",
        "Create a custom copy (to attach profiles)…": "Crea una copia personalizzata (per associare profili)…",
        "Environment profiles": "Profili ambiente",
        "Save": "Salva",
        "New": "Nuovo",
        "Duplicate": "Duplica",
        "Delete": "Elimina",
        "Optional, e.g. /opt/sdk/environment-setup": "Opzionale, es. /opt/sdk/environment-setup",
        "Browse…": "Sfoglia…",
        "Description": "Descrizione",
        "Script loaded with “source” before launch, useful for SDKs that ship an environment-setup file.": "Script caricato con «source» prima dell'avvio, utile per gli SDK che forniscono un file environment-setup.",
        "Variable": "Variabile",
        "Value": "Valore",
        "Add variable": "Aggiungi variabile",
        "Remove variable": "Rimuovi variabile",
        "Check values": "Verifica valori",
        "<small>Double-click a cell to edit it. Use <tt>${NAME}</tt> to reuse an existing value, e.g. <tt>PATH = ${QTDIR}/bin:${PATH}</tt>. Variables are applied in the order they appear.</small>": "<small>Doppio clic su una cella per modificarla. Usa <tt>${NOME}</tt> per riutilizzare un valore esistente, es. <tt>PATH = ${QTDIR}/bin:${PATH}</tt>. Le variabili vengono applicate nell'ordine in cui compaiono.</small>",
        "(untitled)": "(senza nome)",
        "New profile": "Nuovo profilo",
        " (copy)": " (copia)",
        "Delete the profile “{name}”?": "Eliminare il profilo «{name}»?",
        "Apps that use it will no longer offer it.": "Le app che lo usano non lo proporranno più.",
        "Choose the environment script": "Scegli lo script d'ambiente",
        "Choose": "Scegli",
        "Script not found: {script}": "Script non trovato: {script}",
        "{key}: the path {path} does not exist": "{key}: il percorso {path} non esiste",
        "(no variables)": "(nessuna variabile)",
        "Warning:\n  ": "Attenzione:\n  ",
        "\n\n(Variables set by the script are not included in this preview.)": "\n\n(Le variabili impostate dallo script non sono incluse in questa anteprima.)",
        "Resulting values for “{name}”": "Valori risultanti per «{name}»",
        "Every profile needs a name.": "Ogni profilo deve avere un nome.",
        "Duplicate profile names: ": "Nomi di profilo duplicati: ",
        "Invalid variable names in profile “{name}”: ": "Nomi di variabile non validi nel profilo «{name}»: ",
        "Use only letters, digits and _, no spaces, and do not start with a digit (e.g. QT_DIR, MY_SDK_ROOT).": "Usa solo lettere, cifre e _, senza spazi, e non iniziare con una cifra (es. QT_DIR, MY_SDK_ROOT).",
        "Profile “{name}” still contains the placeholder NEW_VARIABLE.": "Il profilo «{name}» contiene ancora il segnaposto NEW_VARIABLE.",
        "Save anyway?": "Salvare comunque?",
        "Edit app": "Modifica app",
        "New app": "Nuova app",
        "e.g. qtcreator or /opt/app/bin/app --option": "es. qtcreator oppure /opt/app/bin/app --opzione",
        "Theme icon name or image path": "Nome di icona del tema o percorso di un'immagine",
        "Empty = home": "Vuoto = home",
        "Run in a terminal tab (for text-mode programs)": "Esegui in una scheda del terminale (per programmi testuali)",
        "Command": "Comando",
        "Icon": "Icona",
        "Working folder": "Cartella di lavoro",
        "Environment profiles to offer at launch": "Profili ambiente da proporre all'avvio",
        "No profiles: create one from “Environment profiles”.": "Nessun profilo: creane uno da «Profili ambiente».",
        "<small>With several profiles selected, you choose the environment when you click the icon. With just one, it is used directly.</small>": "<small>Con più profili selezionati, al clic sull'icona scegli l'ambiente. Con uno solo, viene usato direttamente.</small>",
        "Name and command are required.": "Nome e comando sono obbligatori.",
        "The command is not valid.": "Il comando non è valido.",
        "Edit config.json in the terminal": "Modifica config.json nel terminale",
        "Reload configuration": "Ricarica la configurazione",
        "Open the log folder": "Apri la cartella dei log",
        "Apps": "App",
        "Show or hide the app panel (Ctrl+Shift+A)": "Mostra o nascondi il pannello delle app (Ctrl+Shift+A)",
        "<small>Ctrl+Shift+T  new tab     Ctrl+Shift+F  search apps</small>": "<small>Ctrl+Shift+T  nuova scheda     Ctrl+Shift+F  cerca app</small>",
        "Ready. Configuration: {path}": "Pronto. Configurazione: {path}",
        "Copied: {text}": "Copiato: {text}",
        "Windows interoperability is not available in this distribution": "L'interoperabilità con Windows non è disponibile in questa distro",
        "The active terminal is running a program: opening a new tab": "Il terminale attivo sta eseguendo un programma: apro una nuova scheda",
        "The profile “{name}” no longer exists": "Il profilo «{name}» non esiste più",
        "Invalid command for {app}: {error}": "Comando non valido per {app}: {error}",
        "No command configured for {app}": "Nessun comando configurato per {app}",
        " with the PATH of profile “{name}”": " con il PATH del profilo «{name}»",
        "Command not found{where}: {command}": "Comando non trovato{where}: {command}",
        "Could not start {app}: {error}": "Impossibile avviare {app}: {error}",
        "Started {app}": "Avviato {app}",
        "{app} exited with code {code}": "{app} si è chiuso con codice {code}",
        "{app} exited right away (code {code})": "{app} si è chiuso subito (codice {code})",
        "Full log: {path}\n\n": "Log completo: {path}\n\n",
        "Remove “{name}” from the panel?": "Rimuovere «{name}» dal pannello?",
        "The program stays installed: only the icon is removed.": "Il programma resta installato: viene tolta solo l'icona.",
        "Profiles saved": "Profili salvati",
        "Configuration reloaded": "Configurazione ricaricata",
        "After saving, use “Reload configuration” from the menu": "Dopo aver salvato, usa «Ricarica la configurazione» dal menu",
        "New folder": "Nuova cartella",
        "New file": "Nuovo file",
        "Name of the new folder in {path}:": "Nome della nuova cartella in {path}:",
        "Name of the new file in {path}:": "Nome del nuovo file in {path}:",
        "{n} profile": "{n} profilo",
        "{n} profiles": "{n} profili",
        "Error:": "Errore:",
        "Settings": "Impostazioni",
        "Language": "Lingua",
        "Automatic (system language)": "Automatica (lingua del sistema)",
        "Terminal font": "Font del terminale",
        "Root access": "Accesso root",
        "Automatic: wsl.exe, no password": "Automatico: wsl.exe, senza password",
        "sudo: asks for your password": "sudo: chiede la tua password",
        "A language change takes effect after restarting WSL Hub.": "Il cambio di lingua ha effetto dopo il riavvio di WSL Hub.",
        "Restart WSL Hub now to apply the language?": "Riavviare ora WSL Hub per applicare la lingua?",
        "Open terminal tabs will be closed. Apps you started keep running.": "Le schede del terminale aperte verranno chiuse. Le app avviate restano in esecuzione.",
        "Restart now": "Riavvia ora",
        "The new language will be used the next time WSL Hub starts": "La nuova lingua sarà usata al prossimo avvio di WSL Hub",
        "Settings saved": "Impostazioni salvate",
        "Root /": "Radice /",
        "Example": "Esempio",
        "Demo profile: edit or delete it": "Profilo dimostrativo: modificalo o eliminalo",
    },
}
_current_language = "en"


def detect_language():
    """Language from the environment (LANGUAGE, LC_ALL, LC_MESSAGES, LANG); English if unsupported."""
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var, "")
        if value:
            code = re.split(r"[_.:@]", value, maxsplit=1)[0].lower()
            return code if code in LANGUAGES else "en"
    return "en"


def set_language(preference):
    """preference: a code from LANGUAGES, or "auto" to follow the system."""
    global _current_language
    _current_language = preference if preference in LANGUAGES else detect_language()


def current_language():
    return _current_language


def _(text):
    return TRANSLATIONS.get(_current_language, {}).get(text, text)


def ngettext(singular, plural, n):
    # English and Italian use the singular only for 1; languages with other
    # plural rules will need a dedicated function here.
    return _(singular if n == 1 else plural)

def default_config():
    """Default configuration, with names in the current language."""
    return {
        "language": "auto",  # "auto" follows the system; otherwise a code from LANGUAGES
        "dark_theme": True,
        "gtk_theme": "Adwaita",  # "" = use the system theme
        "terminal_font": "JetBrains Mono 11",  # if missing, Pango uses another monospace font
        "show_hidden": False,
        "show_system_apps": True,
        # How root permissions are obtained:
        #   "auto" = through wsl.exe -u root (no password, as from PowerShell), otherwise sudo
        #   "sudo" = always sudo (asks for your password)
        "root_method": "auto",
        "bookmarks": [
            {"name": _("Home"), "path": "~"},
            {"name": _("Root /"), "path": "/"},
            {"name": "Windows C:", "path": "/mnt/c"},
        ],
        # Environment profiles: variables applied before starting an app or a terminal.
        # ${VAR} refers to the existing value (including variables defined above).
        # "script" (optional) is loaded with `source` before launch.
        # More examples (several Qt versions, Yocto SDKs) in config.example.json.
        "profiles": {
            _("Example"): {
                "description": _("Demo profile: edit or delete it"),
                "script": "",
                "vars": {
                    "MY_TOOLS": "~/tools",
                    "PATH": "${MY_TOOLS}/bin:${PATH}",
                },
            },
        },
        # Custom apps shown in the panel (in addition to the system ones).
        "apps": [],
    }


TERM_FG = "#d7dae0"
TERM_BG = "#1f2329"
TERM_PALETTE = [
    "#282c34", "#e06c75", "#98c379", "#e5c07b", "#61afef", "#c678dd", "#56b6c2", "#abb2bf",
    "#5c6370", "#ef8189", "#a8d58a", "#f0d197", "#7cc0f5", "#d69ae8", "#6fcad6", "#ffffff",
]

# Palette dell'interfaccia (redesign: sfondi neutri freddi, un solo accento)
UI_BG = "#16181c"
UI_PANEL = "#181b20"
UI_HEADER = "#1b1e23"
UI_FIELD = "#12151a"
UI_TEXT = "#e7eaf0"
UI_DIM = "#8b929e"
UI_ACCENT = "#56c2cf"
UI_ROOT = "#e06c75"
UI_LINE = "rgba(255, 255, 255, 0.07)"

CSS = ("""
window, .hub-root { background-color: %(bg)s; }
window { font-family: "IBM Plex Sans", "Cantarell", sans-serif; font-size: 12px; }

headerbar {
    background-image: none;
    background-color: %(header)s;
    border-bottom: 1px solid %(line)s;
    box-shadow: none;
    min-height: 44px;
    padding: 0 8px;
}
headerbar .title { font-size: 13px; font-weight: 600; color: %(text)s; }
headerbar .subtitle { font-size: 10px; font-weight: 500; color: %(accent)s; }

button.flat-btn, button.icon-btn {
    background-image: none;
    background-color: rgba(255, 255, 255, 0.055);
    border: 1px solid %(line)s;
    border-radius: 6px;
    color: #c8cdd6;
    padding: 4px 10px;
    box-shadow: none;
    text-shadow: none;
}
button.flat-btn:hover, button.icon-btn:hover { background-color: rgba(255, 255, 255, 0.1); }
button.icon-btn { padding: 4px 6px; }

button.accent-btn {
    background-image: none;
    background-color: rgba(255, 255, 255, 0.055);
    border: 1px solid %(line)s;
    border-radius: 6px;
    color: #c8cdd6;
    padding: 4px 11px;
    box-shadow: none;
}
button.accent-btn:checked {
    background-color: %(accent)s;
    border-color: %(accent)s;
    color: #0f1114;
    font-weight: 600;
}

button.root-btn {
    background-image: none;
    background-color: rgba(224, 108, 117, 0.14);
    border: 1px solid rgba(224, 108, 117, 0.3);
    border-radius: 6px;
    color: %(root)s;
    font-weight: 600;
    box-shadow: none;
    text-shadow: none;
}

/* gli interruttori del pannello file formano un unico blocco segmentato */
.segmented { background-color: rgba(255, 255, 255, 0.05); border-radius: 7px; padding: 2px; }
.segmented button {
    background-image: none;
    background-color: transparent;
    border: none;
    border-radius: 5px;
    color: %(dim)s;
    font-size: 11px;
    padding: 3px 9px;
    box-shadow: none;
}
.segmented button:checked { background-color: rgba(255, 255, 255, 0.12); color: %(text)s; }
.segmented button.root-toggle:checked {
    background-color: rgba(224, 108, 117, 0.16);
    box-shadow: inset 0 0 0 1px rgba(224, 108, 117, 0.35);
    color: %(root)s;
    font-weight: 600;
}

entry {
    background-image: none;
    background-color: %(field)s;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 7px;
    color: #d7dae0;
    padding: 6px 9px;
}
entry:focus { border-color: %(accent)s; }
combobox button {
    background-image: none;
    background-color: %(field)s;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 7px;
    color: #d7dae0;
    box-shadow: none;
    text-shadow: none;
}
entry.path-entry { font-family: "JetBrains Mono", monospace; font-size: 12px; }
entry.root-mode { border-color: %(root)s; box-shadow: inset 0 0 0 1px rgba(224, 108, 117, 0.35); }

.file-panel { background-color: %(panel)s; }
treeview.view { background-color: transparent; color: #d7dae0; }
treeview.view:selected { background-color: rgba(255, 255, 255, 0.09); color: #ffffff; }
treeview header button {
    background-image: none;
    background-color: transparent;
    border: none;
    border-bottom: 1px solid %(line)s;
    color: %(dim)s;
    font-size: 10px;
    font-weight: 500;
    padding: 4px 6px;
}

.app-panel { background-color: %(bg)s; }
.app-tile {
    padding: 10px 6px;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 9px;
    background-image: none;
    background-color: rgba(255, 255, 255, 0.03);
    box-shadow: none;
}
.app-tile:hover { background-color: rgba(255, 255, 255, 0.08); }
.app-tile label { font-size: 11px; font-weight: 500; color: %(text)s; }
.tile-badge { color: #e0b483; font-family: "JetBrains Mono", monospace; }

notebook > header { background-color: %(header)s; border-bottom: 1px solid %(line)s; }
notebook > header > tabs > tab {
    background-image: none;
    background-color: transparent;
    border: none;
    border-top: 2px solid transparent;
    color: %(dim)s;
    font-size: 12px;
    padding: 7px 12px;
    box-shadow: none;
}
notebook > header > tabs > tab:checked {
    background-color: #1f2329;
    border-top: 2px solid %(accent)s;
    color: %(text)s;
    box-shadow: none;
}
.root-label { color: %(root)s; font-weight: bold; }

.status-bar {
    background-color: %(header)s;
    border-top: 1px solid %(line)s;
    padding: 5px 12px;
    font-size: 11px;
    color: %(dim)s;
}
.status-dot { color: %(accent)s; font-size: 9px; }
.status-dot.error { color: %(root)s; }
.status-hints { color: #6d747f; font-family: "JetBrains Mono", monospace; }

.panel-toolbar { padding: 6px; }
""" % {"bg": UI_BG, "panel": UI_PANEL, "header": UI_HEADER, "field": UI_FIELD,
       "text": UI_TEXT, "dim": UI_DIM, "accent": UI_ACCENT, "root": UI_ROOT,
       "line": UI_LINE}).encode()


# --------------------------------------------------------------------------- #
# Configurazione
# --------------------------------------------------------------------------- #
class Config:
    def __init__(self):
        self.error = None
        self.data = self._load()

    def _load(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        set_language("auto")
        if not CONFIG_FILE.exists():
            self._write(default_config())
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError(_('the file does not contain a JSON object'))
        except Exception as exc:  # noqa: BLE001
            backup = CONFIG_FILE.with_name("config.json.bad")
            shutil.copy(CONFIG_FILE, backup)
            self.error = (_('config.json is not valid ({error}). A copy was saved to {backup}; using the default values.').format(error=exc, backup=backup))
            data = default_config()
        set_language(data.get("language", "auto"))
        for key, value in default_config().items():
            data.setdefault(key, value)
        return data

    @staticmethod
    def _write(data):
        tmp = CONFIG_FILE.with_name("config.json.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, CONFIG_FILE)

    def save(self):
        self._write(self.data)

    def reload(self):
        self.error = None
        self.data = self._load()

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value


# --------------------------------------------------------------------------- #
# Ambiente e avvio processi
# --------------------------------------------------------------------------- #
_VAR_RE = re.compile(r"\$\{(\w+)\}|\$(\w+)")
_FIELD_CODE_RE = re.compile(r"%[fFuUdDnNickvm]")


def _is_path_list(name):
    return name.endswith("PATH") or name.endswith("_DIRS")


def build_env(profile=None, extra=None):
    """Ambiente corrente + variabili del profilo (con espansione di ${VAR})."""
    env = dict(os.environ)
    if profile:
        for key, raw in profile.get("vars", {}).items():
            key = key.strip()
            if not key:
                continue
            value = _VAR_RE.sub(lambda m: env.get(m.group(1) or m.group(2), ""), str(raw))
            if value.startswith("~"):
                value = os.path.expanduser(value)
            if _is_path_list(key):
                # evita "::" o ":" finali quando la variabile originale era vuota
                value = ":".join(part for part in value.split(":") if part)
            env[key] = value
    if extra:
        env.update(extra)
    return env


def wrap_with_script(argv, profile):
    """Se il profilo ha uno script, lo carica con `source` e poi esegue argv."""
    script = (profile or {}).get("script", "").strip()
    if not script:
        return list(argv)
    script = os.path.expanduser(script)
    return ["bash", "-c",
            'source "$0" || echo "WSL Hub: error loading $0" >&2; exec "$@"',
            script, *argv]


def desktop_argv(info):
    cmd = info.get_commandline() or info.get_executable() or ""
    cmd = _FIELD_CODE_RE.sub("", cmd).replace("%%", "%")
    try:
        return shlex.split(cmd)
    except ValueError:
        return cmd.split()


def to_windows_path(path):
    try:
        out = subprocess.run(["wslpath", "-w", path], capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def windows_explorer():
    exe = shutil.which("explorer.exe")
    if exe:
        return exe
    fallback = "/mnt/c/Windows/explorer.exe"
    return fallback if os.path.exists(fallback) else None


def windows_wsl_exe():
    exe = shutil.which("wsl.exe")
    if exe:
        return exe
    fallback = "/mnt/c/Windows/System32/wsl.exe"
    return fallback if os.path.exists(fallback) else None


# --------------------------------------------------------------------------- #
# Accesso root
# --------------------------------------------------------------------------- #
ROOT_HELPER_CODE = r'''
import json, os, shutil, sys
print(json.dumps({"ready": True, "uid": os.getuid()}), flush=True)
for line in sys.stdin:
    try:
        req = json.loads(line)
    except ValueError:
        continue
    if not isinstance(req, dict):
        continue
    rid, op = req.get("id"), req.get("op")
    try:
        if op == "list":
            out = []
            with os.scandir(req["path"]) as it:
                for e in it:
                    try:
                        st = e.stat()
                        out.append([e.name, e.is_dir(), st.st_size, st.st_mtime])
                    except OSError:
                        out.append([e.name, False, -1, 0])
            res = {"entries": out}
        elif op == "isdir":
            res = {"value": os.path.isdir(req["path"])}
        elif op == "exists":
            res = {"value": os.path.lexists(req["path"])}
        elif op == "rename":
            os.rename(req["src"], req["dst"]); res = {}
        elif op == "mkdir":
            os.mkdir(req["path"]); res = {}
        elif op == "touch":
            open(req["path"], "x").close(); res = {}
        elif op == "delete":
            p = req["path"]
            if os.path.isdir(p) and not os.path.islink(p):
                shutil.rmtree(p)
            else:
                os.remove(p)
            res = {}
        else:
            raise ValueError("unknown operation: %s" % op)
        res.update(id=rid, ok=True)
    except OSError as exc:
        res = {"id": rid, "ok": False, "error": exc.strerror or str(exc)}
    except Exception as exc:
        res = {"id": rid, "ok": False, "error": str(exc)}
    print(json.dumps(res), flush=True)
'''


class RootError(OSError):
    def __init__(self, msg):
        super().__init__(0, msg)


class RootHelper:
    """Processo che gira come root ed esegue solo operazioni sui file.
    L'interfaccia grafica resta con l'utente normale."""

    def __init__(self, hub):
        self.hub = hub
        self.proc = None
        self.method = None
        self._buf = b""
        self._next_id = 0

    # -- come si diventa root
    def _method(self):
        wanted = self.hub.config["root_method"]
        if wanted != "sudo" and os.environ.get("WSL_DISTRO_NAME") and windows_wsl_exe():
            return "wsl"
        return "sudo"

    def wrap(self, argv, cwd=None):
        """argv da eseguire come root (per terminali ed editor)."""
        if self._method() == "wsl":
            cmd = [windows_wsl_exe(), "-d", DISTRO, "-u", "root"]
            if cwd:
                cmd += ["--cd", cwd]
            return cmd + (["--exec", *argv] if argv else [])
        return ["sudo", *argv] if argv else ["sudo", "-s"]

    # -- ciclo di vita
    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def ensure(self):
        if self.alive():
            return True
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        helper = CACHE_DIR / "root_helper.py"
        helper.write_text(ROOT_HELPER_CODE, encoding="utf-8")
        method = self._method()
        password = None
        if method == "wsl":
            cmd = self.wrap(["/usr/bin/python3", "-u", str(helper)], cwd="/")
        elif subprocess.run(["sudo", "-n", "true"], stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            cmd = ["sudo", "-n", "/usr/bin/python3", "-u", str(helper)]
        else:
            password = ask_password(self.hub.window)
            if password is None:
                return False
            check = subprocess.run(["sudo", "-S", "-v", "-p", ""],
                                   input=(password + "\n").encode(),
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if check.returncode != 0:
                message(self.hub.window, _('Wrong password.'),
                        _('You need the password of your Linux user, the one you use with sudo.'))
                return False
            cmd = ["sudo", "-S", "-p", "", "/usr/bin/python3", "-u", str(helper)]
        err_path = CACHE_DIR / "root_helper.err"
        with open(err_path, "wb") as err:
            self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=err, cwd="/")
        self._buf = b""
        if password is not None:
            self.proc.stdin.write(password.encode() + b"\n")
            self.proc.stdin.flush()
        try:
            ready = json.loads(self._readline(25))
            if ready.get("uid") != 0:
                raise RootError(_('the process is not running as root'))
        except (OSError, EOFError, TimeoutError, ValueError) as exc:
            self.stop()
            detail = err_path.read_text(errors="replace").strip() if err_path.exists() else ""
            if password is not None and not detail:
                detail = _('Wrong password?')
            message(self.hub.window, _('Could not get root permissions.'),
                    detail or str(exc))
            return False
        self.method = method
        return True

    def stop(self):
        if self.proc is not None:
            try:
                self.proc.stdin.close()
            except OSError:
                pass
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None

    def _readline(self, timeout):
        fd = self.proc.stdout.fileno()
        deadline = time.monotonic() + timeout
        while b"\n" not in self._buf:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(_('no response from the root process'))
            ready, _unused, _unused2 = select.select([fd], [], [], remaining)
            if ready:
                chunk = os.read(fd, 65536)
                if not chunk:
                    raise EOFError(_('the root process has exited'))
                self._buf += chunk
        line, _sep, self._buf = self._buf.partition(b"\n")
        return line

    def call(self, op, **kwargs):
        if not self.alive():
            raise RootError(_('root mode is not active'))
        self._next_id += 1
        request = dict(kwargs, id=self._next_id, op=op)
        try:
            self.proc.stdin.write((json.dumps(request) + "\n").encode())
            self.proc.stdin.flush()
            while True:
                reply = json.loads(self._readline(30))
                if reply.get("id") == self._next_id:
                    break
        except (OSError, EOFError, TimeoutError, ValueError) as exc:
            self.stop()
            raise RootError(_('root process not available ({error})').format(error=exc)) from None
        if not reply.get("ok"):
            raise RootError(reply.get("error", _('unknown error')))
        return reply


# --------------------------------------------------------------------------- #
# Icone e piccoli helper GTK
# --------------------------------------------------------------------------- #
_ICON_CACHE = {}
FOLDER_ICON = Gio.ThemedIcon.new_from_names(["folder"])
FALLBACK_APP_ICON = "application-x-executable"


def icon_for_file(name):
    ctype, _uncertain = Gio.content_type_guess(name, None)
    icon = _ICON_CACHE.get(ctype)
    if icon is None:
        icon = Gio.content_type_get_icon(ctype)
        _ICON_CACHE[ctype] = icon
    return icon


def icon_from_spec(spec):
    spec = (spec or "").strip()
    if spec:
        path = os.path.expanduser(spec)
        if os.path.isabs(path) and os.path.exists(path):
            return Gio.FileIcon.new(Gio.File.new_for_path(path))
        return Gio.ThemedIcon.new_from_names([spec, FALLBACK_APP_ICON])
    return Gio.ThemedIcon.new_from_names([FALLBACK_APP_ICON])


def rgba(hex_color):
    color = Gdk.RGBA()
    color.parse(hex_color)
    return color


def add_menu_item(menu, label, callback=None, *args, sensitive=True):
    item = Gtk.MenuItem(label=label)
    item.set_sensitive(sensitive and callback is not None)
    if callback is not None:
        item.connect("activate", lambda _w: callback(*args))
    menu.append(item)
    return item


_open_menus = []  # evita che il garbage collector chiuda i menu popup


def show_menu(menu, widget, event=None):
    menu.show_all()
    menu.attach_to_widget(widget, None)
    _open_menus.append(menu)
    menu.connect("deactivate", lambda m: GLib.idle_add(_forget_menu, m))
    if event is not None:
        menu.popup_at_pointer(event)
    else:
        menu.popup_at_widget(widget, Gdk.Gravity.SOUTH_WEST, Gdk.Gravity.NORTH_WEST, None)


def _forget_menu(menu):
    if menu in _open_menus:
        _open_menus.remove(menu)
    return False


def message(parent, text, secondary=None, kind=Gtk.MessageType.ERROR):
    dlg = Gtk.MessageDialog(transient_for=parent, modal=True, message_type=kind,
                            buttons=Gtk.ButtonsType.OK, text=text)
    if secondary:
        dlg.format_secondary_text(secondary)
    dlg.run()
    dlg.destroy()


def confirm(parent, text, secondary=None, ok_label="OK"):
    dlg = Gtk.MessageDialog(transient_for=parent, modal=True,
                            message_type=Gtk.MessageType.QUESTION,
                            buttons=Gtk.ButtonsType.NONE, text=text)
    if secondary:
        dlg.format_secondary_text(secondary)
    dlg.add_buttons(_('Cancel'), Gtk.ResponseType.CANCEL, ok_label, Gtk.ResponseType.OK)
    dlg.set_default_response(Gtk.ResponseType.OK)
    ok = dlg.run() == Gtk.ResponseType.OK
    dlg.destroy()
    return ok


def ask_text(parent, title, label, initial=""):
    dlg = Gtk.Dialog(title=title, transient_for=parent, modal=True)
    dlg.add_buttons(_('Cancel'), Gtk.ResponseType.CANCEL, "OK", Gtk.ResponseType.OK)
    dlg.set_default_response(Gtk.ResponseType.OK)
    box = dlg.get_content_area()
    box.set_spacing(6)
    box.set_border_width(12)
    box.add(Gtk.Label(label=label, xalign=0))
    entry = Gtk.Entry(text=initial, activates_default=True, width_chars=40)
    box.add(entry)
    dlg.show_all()
    stem, dot, _ext = initial.rpartition(".")
    entry.select_region(0, len(stem) if dot and stem else -1)
    response = dlg.run()
    text = entry.get_text().strip()
    dlg.destroy()
    return text if response == Gtk.ResponseType.OK and text else None


def ask_password(parent):
    dlg = Gtk.Dialog(title=_('Root permissions'), transient_for=parent, modal=True)
    dlg.add_buttons(_('Cancel'), Gtk.ResponseType.CANCEL, _('Confirm'), Gtk.ResponseType.OK)
    dlg.set_default_response(Gtk.ResponseType.OK)
    box = dlg.get_content_area()
    box.set_spacing(6)
    box.set_border_width(12)
    box.add(Gtk.Label(label=_('Password for {user} (sudo):').format(user=os.environ.get('USER', '?')), xalign=0))
    entry = Gtk.Entry(visibility=False, activates_default=True, width_chars=30,
                      input_purpose=Gtk.InputPurpose.PASSWORD)
    box.add(entry)
    dlg.show_all()
    response = dlg.run()
    text = entry.get_text()
    dlg.destroy()
    return text if response == Gtk.ResponseType.OK else None


def show_text(parent, title, text):
    dlg = Gtk.Dialog(title=title, transient_for=parent, modal=True)
    dlg.add_buttons(_('Close'), Gtk.ResponseType.CLOSE)
    dlg.set_default_size(720, 380)
    view = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
    view.get_buffer().set_text(text)
    sw = Gtk.ScrolledWindow(vexpand=True)
    sw.add(view)
    area = dlg.get_content_area()
    area.set_border_width(8)
    area.pack_start(sw, True, True, 0)
    dlg.show_all()
    dlg.run()
    dlg.destroy()


def labeled(grid, row, text, widget, hint=None):
    lbl = Gtk.Label(label=text, xalign=1)
    grid.attach(lbl, 0, row, 1, 1)
    grid.attach(widget, 1, row, 1, 1)
    widget.set_hexpand(True)
    if hint:
        widget.set_tooltip_text(hint)


# --------------------------------------------------------------------------- #
# Terminale
# --------------------------------------------------------------------------- #
class TerminalTab(Gtk.ScrolledWindow):
    def __init__(self, hub, cwd=None, profile_name=None, argv=None, title=None, root=False):
        super().__init__()
        self.hub = hub
        self.pid = None
        self.root = root
        self.title = title or ("root" if root else profile_name or _('Terminal'))

        self.term = Vte.Terminal()
        self.term.set_scrollback_lines(10000)
        self.term.set_font(Pango.FontDescription.from_string(hub.config["terminal_font"]))
        self.term.set_mouse_autohide(True)
        # le schede root hanno uno sfondo rossastro per riconoscerle a colpo d'occhio
        bg = "#2b1d21" if root else TERM_BG
        self.term.set_colors(rgba(TERM_FG), rgba(bg), [rgba(c) for c in TERM_PALETTE])
        self.term.connect("key-press-event", self._on_key)
        self.term.connect("button-press-event", self._on_button)
        self.add(self.term)

        profile = hub.config["profiles"].get(profile_name) if profile_name else None
        extra = {"WSL_HUB": "1"}
        if profile_name:
            extra["WSL_HUB_PROFILE"] = profile_name
        env = build_env(profile, extra)
        if root:
            root_cwd = cwd or HOME
            argv = hub.root.wrap(argv or [], cwd=root_cwd)
            cwd = root_cwd if os.access(root_cwd, os.X_OK) else "/"
        else:
            if argv is None:
                argv = [env.get("SHELL") or "/bin/bash"]
            argv = wrap_with_script(argv, profile)
            cwd = cwd if cwd and os.path.isdir(cwd) else HOME
        envv = [f"{k}={v}" for k, v in env.items()]
        self.term.spawn_async(Vte.PtyFlags.DEFAULT, cwd, argv, envv,
                              GLib.SpawnFlags.SEARCH_PATH, None, None, -1, None,
                              self._on_spawned, None)

    def _on_spawned(self, _term, pid, error, *_args):
        if error is not None or pid is None or pid < 0:
            msg = getattr(error, "message", str(error))
            self.hub.status(_('Could not start the terminal: {error}').format(error=msg), error=True)
        else:
            self.pid = pid

    # -- stato della shell
    def cwd(self):
        if self.pid and not self.root:
            try:
                return os.readlink(f"/proc/{self.pid}/cwd")
            except OSError:
                pass
        return None

    def shell_is_idle(self):
        """True se in primo piano c'è la shell (nessun programma in esecuzione)."""
        pty = self.term.get_pty()
        if not pty or not self.pid:
            return False
        try:
            return os.tcgetpgrp(pty.get_fd()) == self.pid
        except OSError:
            return False

    def feed(self, text):
        data = text.encode()
        try:
            self.term.feed_child(data)
        except TypeError:  # versioni di VTE più vecchie
            self.term.feed_child(text, len(data))

    def send_cd(self, path):
        if self.root or not self.shell_is_idle():
            return False
        # Ctrl+U svuota la riga; lo spazio iniziale tiene il comando fuori dalla history
        self.feed("\x15 cd -- " + shlex.quote(path) + "\n")
        return True

    def copy(self):
        try:
            self.term.copy_clipboard_format(Vte.Format.TEXT)
        except AttributeError:
            self.term.copy_clipboard()

    def _on_key(self, _widget, event):
        mods = event.state & Gtk.accelerator_get_default_mod_mask()
        if mods == (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK):
            key = Gdk.keyval_to_lower(event.keyval)
            if key == Gdk.KEY_c:
                self.copy()
                return True
            if key == Gdk.KEY_v:
                self.term.paste_clipboard()
                return True
        return False

    def _on_button(self, widget, event):
        if event.type != Gdk.EventType.BUTTON_PRESS or event.button != 3:
            return False
        menu = Gtk.Menu()
        add_menu_item(menu, _('Copy'), self.copy, sensitive=self.term.get_has_selection())
        add_menu_item(menu, _('Paste'), self.term.paste_clipboard)
        menu.append(Gtk.SeparatorMenuItem())
        add_menu_item(menu, _('Show this folder in the file panel'),
                      lambda: self.hub.files.navigate(self.cwd()), sensitive=bool(self.cwd()))
        show_menu(menu, widget, event)
        return True


class TerminalPanel(Gtk.Box):
    def __init__(self, hub):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.hub = hub
        self.closing = False

        self.notebook = Gtk.Notebook(scrollable=True)
        self.notebook.set_show_border(False)

        actions = Gtk.Box(spacing=6)
        actions.set_margin_end(8)
        actions.set_margin_top(4)
        actions.set_margin_bottom(4)
        new_btn = Gtk.Button.new_from_icon_name("tab-new-symbolic", Gtk.IconSize.MENU)
        new_btn.set_relief(Gtk.ReliefStyle.NONE)
        new_btn.set_tooltip_text(_('New terminal (Ctrl+Shift+T)'))
        new_btn.connect("clicked", lambda _b: self.new_tab(cwd=self.current_cwd()))
        self.profile_btn = Gtk.MenuButton(label=_('Terminal with profile'))
        self.profile_btn.get_style_context().add_class("flat-btn")
        self.profile_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.profile_btn.set_tooltip_text(_('Open a shell with the variables of a profile'))
        root_btn = Gtk.Button(label=_('Root terminal'))
        root_btn.get_style_context().add_class("root-btn")
        root_btn.set_relief(Gtk.ReliefStyle.NONE)
        root_btn.set_tooltip_text(_('Open a root shell in the current folder'))
        root_btn.connect("clicked", lambda _b: self.new_tab(cwd=self.hub.files.path, root=True))
        actions.pack_start(new_btn, False, False, 0)
        actions.pack_start(self.profile_btn, False, False, 0)
        actions.pack_start(root_btn, False, False, 0)
        actions.show_all()
        self.notebook.set_action_widget(actions, Gtk.PackType.END)

        self.pack_start(self.notebook, True, True, 0)
        self.rebuild_profile_menu()

    def rebuild_profile_menu(self):
        menu = Gtk.Menu()
        profiles = self.hub.config["profiles"]
        if not profiles:
            add_menu_item(menu, _('No profiles defined'))
        for name in profiles:
            add_menu_item(menu, name, self.new_tab_with_profile, name)
        menu.append(Gtk.SeparatorMenuItem())
        add_menu_item(menu, _('Manage profiles…'), self.hub.open_profiles)
        menu.show_all()
        self.profile_btn.set_popup(menu)

    def new_tab_with_profile(self, name):
        self.new_tab(cwd=self.current_cwd(), profile_name=name)

    def new_tab(self, cwd=None, profile_name=None, argv=None, title=None, root=False):
        tab = TerminalTab(self.hub, cwd, profile_name, argv, title, root)
        header = Gtk.Box(spacing=4)
        tab_label = Gtk.Label(label=tab.title)
        if root:
            tab_label.get_style_context().add_class("root-label")
        header.pack_start(tab_label, False, False, 0)
        close = Gtk.Button.new_from_icon_name("window-close-symbolic", Gtk.IconSize.MENU)
        close.set_relief(Gtk.ReliefStyle.NONE)
        close.set_focus_on_click(False)
        close.set_tooltip_text(_('Close (Ctrl+Shift+W)'))
        close.connect("clicked", lambda _b: self.close_tab(tab))
        header.pack_start(close, False, False, 0)
        header.show_all()

        tab.term.connect("child-exited", lambda *_a: GLib.idle_add(self._on_exited, tab))
        tab.show_all()
        index = self.notebook.append_page(tab, header)
        self.notebook.set_tab_reorderable(tab, True)
        self.notebook.set_current_page(index)
        tab.term.grab_focus()
        return tab

    def close_tab(self, tab):
        # distruggendo il widget VTE manda SIGHUP alla shell
        index = self.notebook.page_num(tab)
        if index >= 0:
            self.notebook.remove_page(index)
        tab.destroy()
        if self.notebook.get_n_pages() == 0 and not self.closing:
            self.new_tab()  # il terminale deve esserci sempre

    def _on_exited(self, tab):
        if self.notebook.page_num(tab) >= 0:
            self.close_tab(tab)
        return False

    def current(self):
        index = self.notebook.get_current_page()
        return self.notebook.get_nth_page(index) if index >= 0 else None

    def current_cwd(self):
        tab = self.current()
        return tab.cwd() if tab else None


# --------------------------------------------------------------------------- #
# File manager
# --------------------------------------------------------------------------- #
class FilePanel(Gtk.Box):
    COL_ICON, COL_NAME, COL_SIZE, COL_MTIME, COL_PATH, COL_ISDIR = range(6)

    def __init__(self, hub):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.hub = hub
        self.path = HOME
        self.history = []
        self._follow_id = 0
        self._last_term_cwd = None
        self._updating_places = False
        self.root_mode = False

        self.get_style_context().add_class("file-panel")

        bar = Gtk.Box(spacing=4)
        bar.get_style_context().add_class("panel-toolbar")
        self.back_btn = self._tool("go-previous-symbolic", _('Back'), self.go_back)
        nav = Gtk.Box(spacing=3)
        for widget in (self.back_btn,
                       self._tool("go-up-symbolic", _('Parent folder'), self.go_up),
                       self._tool("go-home-symbolic", "Home", lambda: self.navigate(HOME)),
                       self._tool("view-refresh-symbolic", _('Refresh'), self.refresh)):
            nav.pack_start(widget, False, False, 0)
        bar.pack_start(nav, False, False, 0)

        # interruttori raccolti in un unico blocco segmentato
        self.hidden_btn = Gtk.ToggleButton(label=".*")
        self.hidden_btn.set_tooltip_text(_('Show hidden files'))
        self.hidden_btn.set_active(bool(hub.config["show_hidden"]))
        self.hidden_btn.connect("toggled", self._on_hidden)
        self.follow_btn = Gtk.ToggleButton(label=_('follow'))
        self.follow_btn.set_tooltip_text(_("Follow the active terminal's folder"))
        self.follow_btn.connect("toggled", self._on_follow)
        self.root_btn = Gtk.ToggleButton(label="root")
        self.root_btn.set_tooltip_text(_('Root mode: view and edit files as administrator'))
        self.root_btn.get_style_context().add_class("root-toggle")
        self.root_btn.connect("toggled", self._on_root_toggled)
        toggles = Gtk.Box(spacing=2)
        toggles.get_style_context().add_class("segmented")
        for widget in (self.hidden_btn, self.follow_btn, self.root_btn):
            widget.set_relief(Gtk.ReliefStyle.NONE)
            widget.set_focus_on_click(False)
            toggles.pack_start(widget, False, False, 0)
        bar.pack_end(toggles, False, False, 0)
        self.pack_start(bar, False, False, 0)

        # riga del percorso: campo monospaziato + segnalibri
        path_row = Gtk.Box(spacing=6)
        path_row.set_margin_start(6)
        path_row.set_margin_end(6)
        path_row.set_margin_bottom(6)
        self.entry = Gtk.Entry()
        self.entry.set_width_chars(8)
        self.entry.get_style_context().add_class("path-entry")
        self.entry.connect("activate", lambda e: self.navigate(e.get_text().strip()))
        path_row.pack_start(self.entry, True, True, 0)
        self.places = Gtk.ComboBoxText()
        self.places.set_size_request(96, -1)
        self.places.set_tooltip_text(_('Bookmarks'))
        self.places.connect("changed", self._on_place)
        path_row.pack_start(self.places, False, False, 0)
        self.pack_start(path_row, False, False, 0)

        self.store = Gtk.ListStore(Gio.Icon, str, str, str, str, bool)
        self.view = Gtk.TreeView(model=self.store)
        self.view.set_search_column(self.COL_NAME)
        name_col = Gtk.TreeViewColumn(_('Name'))
        name_col.set_expand(True)
        name_col.set_resizable(True)
        pix = Gtk.CellRendererPixbuf()
        name_col.pack_start(pix, False)
        name_col.add_attribute(pix, "gicon", self.COL_ICON)
        txt = Gtk.CellRendererText(ellipsize=Pango.EllipsizeMode.END)
        name_col.pack_start(txt, True)
        name_col.add_attribute(txt, "text", self.COL_NAME)
        self.view.append_column(name_col)
        for title, idx in ((_('Size'), self.COL_SIZE), (_('Modified'), self.COL_MTIME)):
            col = Gtk.TreeViewColumn(title, Gtk.CellRendererText(), text=idx)
            col.set_resizable(True)
            self.view.append_column(col)
        self.view.connect("row-activated", self._on_activated)
        self.view.connect("button-press-event", self._on_button)
        sw = Gtk.ScrolledWindow(vexpand=True)
        sw.add(self.view)
        self.pack_start(sw, True, True, 0)

        self.rebuild_places()
        self.navigate(HOME, record=False)

    # -- operazioni sui file: dirette o tramite il processo root
    def _isdir(self, path):
        if self.root_mode:
            try:
                return self.hub.root.call("isdir", path=path)["value"]
            except RootError:
                return False
        return os.path.isdir(path)

    def _exists(self, path):
        if self.root_mode:
            return self.hub.root.call("exists", path=path)["value"]
        return os.path.lexists(path)

    def _list(self, path):
        if self.root_mode:
            return [tuple(e) for e in self.hub.root.call("list", path=path)["entries"]]
        rows = []
        with os.scandir(path) as entries:
            for e in entries:
                try:
                    st = e.stat()
                    rows.append((e.name, e.is_dir(), st.st_size, st.st_mtime))
                except OSError:  # es. link simbolico rotto
                    rows.append((e.name, False, -1, 0))
        return rows

    def _fs(self, op, **kwargs):
        if self.root_mode:
            self.hub.root.call(op, **kwargs)
        elif op == "rename":
            os.rename(kwargs["src"], kwargs["dst"])
        elif op == "mkdir":
            os.mkdir(kwargs["path"])
        elif op == "touch":
            with open(kwargs["path"], "x", encoding="utf-8"):
                pass
        elif op == "delete":
            path = kwargs["path"]
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path)
            else:
                os.remove(path)

    def _on_root_toggled(self, btn):
        if btn.get_active():
            if not self.hub.root.ensure():
                btn.set_active(False)
                return
            self.root_mode = True
            self.entry.get_style_context().add_class("root-mode")
            self.hub.status(_('Root mode on: file changes are made as root'))
        else:
            self.root_mode = False
            self.entry.get_style_context().remove_class("root-mode")
            if not os.access(self.path, os.R_OK | os.X_OK):
                self.history.clear()
                self.path = HOME
        self.refresh()

    def _tool(self, icon, tip, callback):
        btn = Gtk.Button.new_from_icon_name(icon, Gtk.IconSize.BUTTON)
        btn.set_relief(Gtk.ReliefStyle.NONE)
        btn.set_focus_on_click(False)
        btn.get_style_context().add_class("icon-btn")
        btn.set_tooltip_text(tip)
        btn.connect("clicked", lambda _b: callback())
        return btn

    # -- navigazione
    def navigate(self, path, record=True):
        if not path:
            return
        path = os.path.abspath(os.path.expanduser(path))
        if not self._isdir(path):
            self.hub.status(_('Folder not found: {path}').format(path=path), error=True)
            self.entry.set_text(self.path)
            return
        if record and path != self.path:
            self.history.append(self.path)
            del self.history[:-100]
        self.path = path
        self.refresh()

    def go_back(self):
        if self.history:
            self.navigate(self.history.pop(), record=False)

    def go_up(self):
        parent = os.path.dirname(self.path)
        if parent != self.path:
            self.navigate(parent)

    def refresh(self):
        self.entry.set_text(self.path)
        self.back_btn.set_sensitive(bool(self.history))
        show_hidden = self.hidden_btn.get_active()
        rows = []
        try:
            for name, is_dir, size, mtime in self._list(self.path):
                if not show_hidden and name.startswith("."):
                    continue
                size_text = "" if is_dir or size < 0 else GLib.format_size(size)
                mtime_text = (time.strftime(_('%Y-%m-%d %H:%M'), time.localtime(mtime))
                              if mtime else "")
                icon = FOLDER_ICON if is_dir else icon_for_file(name)
                rows.append((icon, name, size_text, mtime_text,
                             os.path.join(self.path, name), is_dir))
        except PermissionError:
            self.hub.status(_('Permission denied for {path}: turn on “root” to see its contents').format(path=self.path), error=True)
        except OSError as exc:
            self.hub.status(_('Could not read {path}: {error}').format(path=self.path, error=exc.strerror), error=True)
        rows.sort(key=lambda r: (not r[5], r[1].casefold()))
        self.view.set_model(None)
        self.store.clear()
        for row in rows:
            self.store.append(row)
        self.view.set_model(self.store)

    def _on_hidden(self, btn):
        self.hub.config["show_hidden"] = btn.get_active()
        self.hub.config.save()
        self.refresh()

    def _on_follow(self, btn):
        if btn.get_active():
            self._last_term_cwd = None
            self._follow_tick()
            self._follow_id = GLib.timeout_add(700, self._follow_tick)
        elif self._follow_id:
            GLib.source_remove(self._follow_id)
            self._follow_id = 0

    def _follow_tick(self):
        cwd = self.hub.terminals.current_cwd()
        if cwd and cwd != self._last_term_cwd:
            self._last_term_cwd = cwd
            if cwd != self.path:
                self.navigate(cwd)
        return True

    # -- segnalibri
    def rebuild_places(self):
        self._updating_places = True
        self.places.remove_all()
        self.places.append_text(_('Go to…'))
        for bm in self.hub.config["bookmarks"]:
            self.places.append_text(bm.get("name") or bm.get("path", "?"))
        self.places.set_active(0)
        self._updating_places = False

    def _on_place(self, combo):
        index = combo.get_active()
        if self._updating_places or index <= 0:
            return
        bookmarks = self.hub.config["bookmarks"]
        if index - 1 < len(bookmarks):
            self.navigate(bookmarks[index - 1].get("path", "~"))
        GLib.idle_add(combo.set_active, 0)

    def _add_bookmark(self, path):
        name = ask_text(self.hub.window, _('New bookmark'), _('Bookmark name:'),
                        os.path.basename(path) or path)
        if name:
            self.hub.config["bookmarks"].append({"name": name, "path": path})
            self.hub.config.save()
            self.rebuild_places()

    # -- apertura file
    def _on_activated(self, _view, tree_path, _col):
        row = self.store[tree_path]
        self.open(row[self.COL_PATH], row[self.COL_ISDIR])

    def open(self, path, is_dir=None):
        if is_dir is None:
            is_dir = self._isdir(path)
        if is_dir:
            self.navigate(path)
            return
        if self.root_mode:
            self.hub.edit_as_root(path)
            return
        ctype, _uncertain = Gio.content_type_guess(path, None)
        app = Gio.AppInfo.get_default_for_type(ctype, False)
        if app is not None:
            if isinstance(app, Gio.DesktopAppInfo) and app.get_boolean("Terminal"):
                self.hub.terminals.new_tab(cwd=os.path.dirname(path),
                                           argv=desktop_argv(app) + [path],
                                           title=app.get_name())
                return
            try:
                app.launch([Gio.File.new_for_path(path)], None)
                self.hub.status(_('Opened “{file}” with {app}').format(file=os.path.basename(path), app=app.get_name()))
                return
            except GLib.Error as exc:
                self.hub.status(_('{app} does not start ({error}); trying with Windows').format(app=app.get_name(), error=exc.message), error=True)
        # nessuna app Linux associata: lo apre Windows con il suo programma predefinito
        self.hub.open_in_windows(path)

    # -- menu contestuale
    def _on_button(self, view, event):
        if event.type != Gdk.EventType.BUTTON_PRESS or event.button != 3:
            return False
        target, is_dir = None, True
        hit = view.get_path_at_pos(int(event.x), int(event.y))
        if hit:
            tree_path = hit[0]
            view.get_selection().select_path(tree_path)
            row = self.store[tree_path]
            target, is_dir = row[self.COL_PATH], row[self.COL_ISDIR]
        show_menu(self._build_menu(target, is_dir), view, event)
        return True

    def _build_menu(self, target, is_dir):
        hub = self.hub
        menu = Gtk.Menu()
        folder = self.path
        root = self.root_mode
        if target:
            add_menu_item(menu, _('Edit as root') if root and not is_dir else _('Open'),
                          self.open, target, is_dir)
            if not is_dir and not root:
                add_menu_item(menu, _('Open with the Windows program'), hub.open_in_windows, target)
                add_menu_item(menu, _('Edit as root'), hub.edit_as_root, target)
            menu.append(Gtk.SeparatorMenuItem())
            folder = target if is_dir else os.path.dirname(target)
        if root:
            add_menu_item(menu, _('Root terminal here'),
                          lambda: hub.terminals.new_tab(cwd=folder, root=True))
        else:
            add_menu_item(menu, _('Go here in the terminal (cd)'), hub.cd_in_terminal, folder)
            add_menu_item(menu, _('New terminal here'), lambda: hub.terminals.new_tab(cwd=folder))
            add_menu_item(menu, _('Root terminal here'),
                          lambda: hub.terminals.new_tab(cwd=folder, root=True))
            add_menu_item(menu, _('Show in Windows File Explorer'), hub.open_in_windows, folder)
        menu.append(Gtk.SeparatorMenuItem())
        if target:
            add_menu_item(menu, _('Paste the path in the terminal'), hub.paste_in_terminal, target)
            add_menu_item(menu, _('Copy path'), hub.copy_text, target)
            add_menu_item(menu, _('Copy Windows path'), self._copy_windows_path, target)
            if is_dir:
                add_menu_item(menu, _('Add to bookmarks…'), self._add_bookmark, target)
            menu.append(Gtk.SeparatorMenuItem())
            add_menu_item(menu, _('Rename…'), self._rename, target)
            add_menu_item(menu, _('Delete permanently (root)…') if root else _('Move to trash'),
                          self._trash, target)
            menu.append(Gtk.SeparatorMenuItem())
        add_menu_item(menu, _('New folder…'), self._new_item, True)
        add_menu_item(menu, _('New empty file…'), self._new_item, False)
        return menu

    def _copy_windows_path(self, path):
        win = to_windows_path(path)
        if win:
            self.hub.copy_text(win)
        else:
            self.hub.status(_('wslpath is not available'), error=True)

    def _rename(self, path):
        old = os.path.basename(path)
        name = ask_text(self.hub.window, _('Rename'), _('New name for “{name}”:').format(name=old), old)
        if not name or name == old:
            return
        if "/" in name:
            message(self.hub.window, _('The name cannot contain “/”.'))
            return
        dest = os.path.join(os.path.dirname(path), name)
        try:
            if self._exists(dest):
                message(self.hub.window, _('An item named “{name}” already exists.').format(name=name))
                return
            self._fs("rename", src=path, dst=dest)
        except OSError as exc:
            message(self.hub.window, _('Could not rename “{name}”.').format(name=old), exc.strerror)
        self.refresh()

    def _trash(self, path):
        name = os.path.basename(path)
        if self.root_mode:
            if confirm(self.hub.window, _('Permanently delete “{name}” as root?').format(name=name),
                       _('{path}\n\nIn root mode the trash is not used and this cannot be undone.').format(path=path), _('Delete permanently')):
                try:
                    self._fs("delete", path=path)
                    self.hub.status(_('“{name}” deleted').format(name=name))
                except OSError as exc:
                    message(self.hub.window, _('Could not delete “{name}”.').format(name=name), exc.strerror)
            self.refresh()
            return
        if not confirm(self.hub.window, _('Move “{name}” to the trash?').format(name=name),
                       _('The trash is in ~/.local/share/Trash.'), _('Move to trash')):
            return
        try:
            Gio.File.new_for_path(path).trash(None)
            self.hub.status(_('“{name}” moved to the trash').format(name=name))
        except GLib.Error as exc:
            if confirm(self.hub.window, _('The trash is not available for “{name}”.').format(name=name),
                       _('{error}\n\nDelete it permanently? This cannot be undone.').format(error=exc.message), _('Delete permanently')):
                try:
                    self._fs("delete", path=path)
                    self.hub.status(_('“{name}” deleted').format(name=name))
                except OSError as err:
                    message(self.hub.window, _('Could not delete “{name}”.').format(name=name), err.strerror)
        self.refresh()

    def _new_item(self, is_dir):
        name = ask_text(self.hub.window, _("New folder") if is_dir else _("New file"),
                        (_("Name of the new folder in {path}:") if is_dir else _("Name of the new file in {path}:")).format(path=self.path))
        if not name:
            return
        target = os.path.join(self.path, name)
        try:
            self._fs("mkdir" if is_dir else "touch", path=target)
        except OSError as exc:
            message(self.hub.window, _('Could not create “{name}”.').format(name=name), exc.strerror)
        self.refresh()


# --------------------------------------------------------------------------- #
# Launcher delle app
# --------------------------------------------------------------------------- #
class AppPanel(Gtk.Box):
    def __init__(self, hub):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.hub = hub
        self._items = []

        self.get_style_context().add_class("app-panel")
        bar = Gtk.Box(spacing=10)
        bar.get_style_context().add_class("panel-toolbar")
        self.search = Gtk.SearchEntry(placeholder_text=_('Search apps'))
        self.search.set_width_chars(24)
        self.search.connect("search-changed", lambda _e: self.flow.invalidate_filter())
        add_btn = Gtk.Button(label=_('Add app…'))
        add_btn.get_style_context().add_class("flat-btn")
        add_btn.connect("clicked", lambda _b: hub.edit_app())
        self.system_btn = Gtk.CheckButton(label=_('Show system apps'))
        self.system_btn.set_active(bool(hub.config["show_system_apps"]))
        self.system_btn.connect("toggled", self._on_system_toggled)
        bar.pack_start(self.search, False, False, 0)
        bar.pack_start(self.system_btn, False, False, 0)
        bar.pack_end(add_btn, False, False, 0)
        self.pack_start(bar, False, False, 0)

        self.flow = Gtk.FlowBox(valign=Gtk.Align.START, homogeneous=True,
                                selection_mode=Gtk.SelectionMode.NONE,
                                max_children_per_line=40, row_spacing=6, column_spacing=6,
                                margin=8)
        self.flow.set_filter_func(self._filter)
        sw = Gtk.ScrolledWindow(vexpand=True)
        sw.add(self.flow)
        self.pack_start(sw, True, True, 0)
        self.rebuild()

    def _on_system_toggled(self, btn):
        self.hub.config["show_system_apps"] = btn.get_active()
        self.hub.config.save()
        self.rebuild()

    def _collect(self):
        cfg = self.hub.config
        items = []
        for index, app in enumerate(cfg["apps"]):
            items.append({
                "name": app.get("name") or _('Untitled'),
                "icon": icon_from_spec(app.get("icon")),
                "command": app.get("command", ""),
                "cwd": app.get("cwd", ""),
                "terminal": bool(app.get("terminal")),
                "profiles": [p for p in app.get("profiles", []) if p in cfg["profiles"]],
                "custom_index": index,
                "desktop": None,
            })
        if cfg["show_system_apps"]:
            system = [info for info in Gio.AppInfo.get_all()
                      if info.should_show() and info.get_id() != OWN_DESKTOP_ID]
            system.sort(key=lambda info: info.get_name().casefold())
            for info in system:
                is_desktop = isinstance(info, Gio.DesktopAppInfo)
                items.append({
                    "name": info.get_name(),
                    "icon": info.get_icon() or icon_from_spec(None),
                    "command": info.get_commandline() or "",
                    "cwd": (info.get_string("Path") if is_desktop else None) or "",
                    "terminal": bool(is_desktop and info.get_boolean("Terminal")),
                    "profiles": [],
                    "custom_index": None,
                    "desktop": info,
                })
        return items

    def rebuild(self):
        for child in self.flow.get_children():
            self.flow.remove(child)
        self._items = self._collect()
        for item in self._items:
            self.flow.add(self._tile(item))
        self.flow.show_all()

    def _tile(self, item):
        btn = Gtk.Button(relief=Gtk.ReliefStyle.NONE)
        btn.get_style_context().add_class("app-tile")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        image = Gtk.Image.new_from_gicon(item["icon"], Gtk.IconSize.DIALOG)
        image.set_pixel_size(48)
        box.pack_start(image, False, False, 0)
        label = Gtk.Label(label=item["name"], ellipsize=Pango.EllipsizeMode.END,
                          max_width_chars=14, width_chars=12, justify=Gtk.Justification.CENTER)
        box.pack_start(label, False, False, 0)
        if item["profiles"]:
            n = len(item["profiles"])
            badge = Gtk.Label()
            badge.set_markup("<small>%s</small>" % ngettext("{n} profile", "{n} profiles", n).format(n=n))
            badge.get_style_context().add_class("tile-badge")
            box.pack_start(badge, False, False, 0)
        btn.add(box)
        tip = [item["name"], item["command"]]
        if item["profiles"]:
            tip.append(_('Profiles: ') + ", ".join(item["profiles"]))
        tip.append(_('Right-click for more options'))
        btn.set_tooltip_text("\n".join(t for t in tip if t))
        btn.connect("clicked", self._on_click, item)
        btn.connect("button-press-event", self._on_press, item)
        return btn

    def _filter(self, child):
        query = self.search.get_text().strip().casefold()
        if not query:
            return True
        index = child.get_index()
        item = self._items[index] if 0 <= index < len(self._items) else None
        return item is not None and query in item["name"].casefold()

    def _on_click(self, btn, item):
        profiles = item["profiles"]
        if len(profiles) == 1:
            self.hub.launch(item, profiles[0])
        elif len(profiles) > 1:
            menu = Gtk.Menu()
            add_menu_item(menu, _('Start {name} with:').format(name=item['name']))
            for name in profiles:
                add_menu_item(menu, "    " + name, self.hub.launch, item, name)
            show_menu(menu, btn)
        else:
            self.hub.launch(item, None)

    def _on_press(self, btn, event, item):
        if event.type != Gdk.EventType.BUTTON_PRESS or event.button != 3:
            return False
        hub = self.hub
        menu = Gtk.Menu()
        add_menu_item(menu, _('Start without a profile'), hub.launch, item, None)
        profiles = hub.config["profiles"]
        if profiles:
            sub = Gtk.Menu()
            for name in profiles:
                mark = "✓ " if name in item["profiles"] else "    "
                add_menu_item(sub, mark + name, hub.launch, item, name)
            parent = Gtk.MenuItem(label=_('Start with profile'))
            parent.set_submenu(sub)
            menu.append(parent)
        menu.append(Gtk.SeparatorMenuItem())
        if item["custom_index"] is not None:
            add_menu_item(menu, _('Edit…'), hub.edit_app, item["custom_index"])
            add_menu_item(menu, _('Remove'), hub.remove_app, item["custom_index"])
        else:
            add_menu_item(menu, _('Create a custom copy (to attach profiles)…'),
                          hub.customize_system_app, item)
        show_menu(menu, btn, event)
        return True


# --------------------------------------------------------------------------- #
# Dialoghi: profili e app
# --------------------------------------------------------------------------- #
class ProfilesDialog(Gtk.Dialog):
    def __init__(self, hub):
        super().__init__(title=_('Environment profiles'), transient_for=hub.window, modal=True)
        self.hub = hub
        self.set_default_size(900, 520)
        self.add_buttons(_('Cancel'), Gtk.ResponseType.CANCEL, _('Save'), Gtk.ResponseType.OK)
        self.items = [{"orig": name,
                       "name": name,
                       "description": p.get("description", ""),
                       "script": p.get("script", ""),
                       "vars": [[k, str(v)] for k, v in p.get("vars", {}).items()]}
                      for name, p in hub.config["profiles"].items()]
        self.current = None
        self._loading = False

        paned = Gtk.Paned()
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin=6)
        self.listbox = Gtk.ListBox()
        self.listbox.connect("row-selected", self._on_select)
        sw = Gtk.ScrolledWindow(vexpand=True)
        sw.set_size_request(230, -1)
        sw.add(self.listbox)
        left.pack_start(sw, True, True, 0)
        btns = Gtk.Box(spacing=4)
        for label, cb in ((_('New'), self._add), (_('Duplicate'), self._duplicate),
                          (_('Delete'), self._delete)):
            b = Gtk.Button(label=label)
            b.connect("clicked", lambda _b, f=cb: f())
            btns.pack_start(b, True, True, 0)
        left.pack_start(btns, False, False, 0)
        paned.pack1(left, False, False)

        grid = Gtk.Grid(row_spacing=6, column_spacing=8, margin=8)
        self.name_entry = Gtk.Entry()
        self.name_entry.connect("changed", self._on_name_changed)
        self.desc_entry = Gtk.Entry()
        self.script_entry = Gtk.Entry(placeholder_text=_('Optional, e.g. /opt/sdk/environment-setup'))
        script_box = Gtk.Box(spacing=4)
        script_box.pack_start(self.script_entry, True, True, 0)
        browse = Gtk.Button(label=_('Browse…'))
        browse.connect("clicked", self._browse_script)
        script_box.pack_start(browse, False, False, 0)
        labeled(grid, 0, _('Name'), self.name_entry)
        labeled(grid, 1, _('Description'), self.desc_entry)
        labeled(grid, 2, "Script (source)", script_box,
                _('Script loaded with “source” before launch, useful for SDKs that ship an environment-setup file.'))

        self.vars_store = Gtk.ListStore(str, str)
        self.vars_view = Gtk.TreeView(model=self.vars_store)
        for idx, title in ((0, _('Variable')), (1, _('Value'))):
            renderer = Gtk.CellRendererText(editable=True)
            renderer.connect("edited", self._on_cell_edited, idx)
            renderer.connect("editing-started", self._on_editing_started, idx)
            col = Gtk.TreeViewColumn(title, renderer, text=idx)
            col.set_resizable(True)
            col.set_expand(idx == 1)
            self.vars_view.append_column(col)
        vsw = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        vsw.add(self.vars_view)
        grid.attach(vsw, 0, 3, 2, 1)

        vbtns = Gtk.Box(spacing=4)
        for label, cb in ((_('Add variable'), self._add_var),
                          (_('Remove variable'), self._remove_var),
                          (_('Check values'), self._preview)):
            b = Gtk.Button(label=label)
            b.connect("clicked", lambda _b, f=cb: f())
            vbtns.pack_start(b, False, False, 0)
        grid.attach(vbtns, 0, 4, 2, 1)
        hint = Gtk.Label(xalign=0, wrap=True)
        hint.set_markup(_('<small>Double-click a cell to edit it. Use <tt>${NAME}</tt> to reuse an existing value, e.g. <tt>PATH = ${QTDIR}/bin:${PATH}</tt>. Variables are applied in the order they appear.</small>'))
        hint.get_style_context().add_class("dim-label")
        grid.attach(hint, 0, 5, 2, 1)
        self.editor = grid
        paned.pack2(grid, True, False)

        self.get_content_area().pack_start(paned, True, True, 0)
        self._fill_list()
        self.show_all()
        self._select(0)

    # -- lista profili
    def _fill_list(self):
        for row in self.listbox.get_children():
            self.listbox.remove(row)
        for item in self.items:
            self.listbox.add(Gtk.Label(label=item["name"], xalign=0, margin=6))
        self.listbox.show_all()
        if not self.items:
            self.editor.set_sensitive(False)

    def _select(self, index):
        row = self.listbox.get_row_at_index(index) if self.items else None
        if row is not None:
            self.listbox.select_row(row)
        else:
            self.editor.set_sensitive(False)

    def _on_select(self, _lb, row):
        self._commit()
        if row is None:
            self.current = None
            self.editor.set_sensitive(False)
            return
        self._load(row.get_index())

    def _load(self, index):
        self._loading = True
        self.current = index
        item = self.items[index]
        self.name_entry.set_text(item["name"])
        self.desc_entry.set_text(item["description"])
        self.script_entry.set_text(item["script"])
        self.vars_store.clear()
        for key, value in item["vars"]:
            self.vars_store.append([key, value])
        self.editor.set_sensitive(True)
        self._loading = False

    def _commit(self):
        if self.current is None or self.current >= len(self.items):
            return
        item = self.items[self.current]
        item["name"] = self.name_entry.get_text().strip()
        item["description"] = self.desc_entry.get_text().strip()
        item["script"] = self.script_entry.get_text().strip()
        item["vars"] = [[r[0].strip(), r[1]] for r in self.vars_store if r[0].strip()]

    def _on_name_changed(self, entry):
        if self._loading or self.current is None:
            return
        row = self.listbox.get_row_at_index(self.current)
        if row:
            row.get_child().set_text(entry.get_text().strip() or _('(untitled)'))

    def _unique(self, base):
        names = {it["name"] for it in self.items}
        name, n = base, 2
        while name in names:
            name, n = f"{base} {n}", n + 1
        return name

    def _add(self):
        self._commit()
        self.items.append({"orig": None, "name": self._unique(_('New profile')),
                           "description": "", "script": "", "vars": []})
        self.current = None
        self._fill_list()
        self._select(len(self.items) - 1)

    def _duplicate(self):
        if self.current is None:
            return
        self._commit()
        clone = copy.deepcopy(self.items[self.current])
        clone["orig"] = None
        clone["name"] = self._unique(clone["name"] + _(' (copy)'))
        self.items.append(clone)
        self.current = None
        self._fill_list()
        self._select(len(self.items) - 1)

    def _delete(self):
        if self.current is None:
            return
        name = self.items[self.current]["name"]
        if not confirm(self, _('Delete the profile “{name}”?').format(name=name),
                       _('Apps that use it will no longer offer it.'), _('Delete')):
            return
        index = self.current
        self.items.pop(index)
        self.current = None
        self._fill_list()
        self._select(min(index, len(self.items) - 1))

    # -- variabili
    def _on_cell_edited(self, _renderer, path, text, idx):
        self.vars_store[path][idx] = text.strip() if idx == 0 else text

    def _on_editing_started(self, _renderer, editable, path, idx):
        # In GTK3 cliccare fuori dalla cella annulla la modifica: copiamo il testo
        # nel modello a ogni tasto, così non si perde nulla.
        if isinstance(editable, Gtk.Entry):
            if idx == 0 and editable.get_text() == "NEW_VARIABLE":
                editable.select_region(0, -1)
            row_ref = Gtk.TreeRowReference.new(self.vars_store, Gtk.TreePath.new_from_string(path))

            def on_changed(entry):
                if row_ref.valid():
                    self.vars_store[row_ref.get_path()][idx] = entry.get_text()

            editable.connect("changed", on_changed)

    def _add_var(self):
        it = self.vars_store.append(["NEW_VARIABLE", ""])
        path = self.vars_store.get_path(it)
        self.vars_view.set_cursor(path, self.vars_view.get_column(0), True)

    def _remove_var(self):
        model, it = self.vars_view.get_selection().get_selected()
        if it is not None:
            model.remove(it)

    def _browse_script(self, _btn):
        dlg = Gtk.FileChooserDialog(title=_('Choose the environment script'), transient_for=self,
                                    action=Gtk.FileChooserAction.OPEN)
        dlg.add_buttons(_('Cancel'), Gtk.ResponseType.CANCEL, _('Choose'), Gtk.ResponseType.OK)
        if dlg.run() == Gtk.ResponseType.OK:
            self.script_entry.set_text(dlg.get_filename() or "")
        dlg.destroy()

    def _preview(self):
        self._commit()
        if self.current is None:
            return
        item = self.items[self.current]
        env = build_env({"vars": dict(item["vars"])})
        lines, warnings = [], []
        if item["script"] and not os.path.isfile(os.path.expanduser(item["script"])):
            warnings.append(_('Script not found: {script}').format(script=item['script']))
        for key, _raw in item["vars"]:
            value = env.get(key, "")
            lines.append(f"{key}={value}")
            for part in value.split(":"):
                if part.startswith("/") and not os.path.exists(part):
                    warnings.append(_('{key}: the path {path} does not exist').format(key=key, path=part))
        text = "\n".join(lines) or _('(no variables)')
        if warnings:
            text = _('Warning:\n  ') + "\n  ".join(dict.fromkeys(warnings)) + "\n\n" + text
        if item["script"]:
            text += _('\n\n(Variables set by the script are not included in this preview.)')
        show_text(self, _('Resulting values for “{name}”').format(name=item['name']), text)

    # -- salvataggio
    def apply(self):
        self._commit()
        names = [it["name"] for it in self.items]
        if any(not n for n in names):
            message(self, _('Every profile needs a name.'))
            return False
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            message(self, _('Duplicate profile names: ') + ", ".join(sorted(dupes)))
            return False
        for it in self.items:
            bad = [k for k, _v in it["vars"] if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k)]
            if bad:
                message(self, _('Invalid variable names in profile “{name}”: ').format(name=it['name'])
                              + ", ".join(bad),
                        _('Use only letters, digits and _, no spaces, and do not start with a digit (e.g. QT_DIR, MY_SDK_ROOT).'))
                return False
            if any(k == "NEW_VARIABLE" for k, _v in it["vars"]):
                if not confirm(self, _('Profile “{name}” still contains the placeholder NEW_VARIABLE.').format(name=it['name']), _('Save anyway?'), _('Save')):
                    return False
        renames, profiles = {}, {}
        for it in self.items:
            profiles[it["name"]] = {"description": it["description"], "script": it["script"],
                                    "vars": {k: v for k, v in it["vars"]}}
            if it["orig"]:
                renames[it["orig"]] = it["name"]
        cfg = self.hub.config
        for app in cfg["apps"]:
            app["profiles"] = [renames[p] for p in app.get("profiles", []) if p in renames]
        cfg["profiles"] = profiles
        cfg.save()
        return True


class AppDialog(Gtk.Dialog):
    def __init__(self, hub, app=None):
        editing = app is not None and app.get("_editing", False)
        super().__init__(title=_('Edit app') if editing else _('New app'),
                         transient_for=hub.window, modal=True)
        self.hub = hub
        app = app or {}
        self.set_default_size(560, -1)
        self.add_buttons(_('Cancel'), Gtk.ResponseType.CANCEL, _('Save'), Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)

        grid = Gtk.Grid(row_spacing=6, column_spacing=8, margin=12)
        self.name = Gtk.Entry(text=app.get("name", ""), activates_default=True)
        self.command = Gtk.Entry(text=app.get("command", ""), activates_default=True,
                                 placeholder_text=_('e.g. qtcreator or /opt/app/bin/app --option'))
        self.icon = Gtk.Entry(text=app.get("icon", ""),
                              placeholder_text=_('Theme icon name or image path'))
        self.cwd = Gtk.Entry(text=app.get("cwd", ""), placeholder_text=_('Empty = home'))
        self.terminal = Gtk.CheckButton(label=_('Run in a terminal tab (for text-mode programs)'))
        self.terminal.set_active(bool(app.get("terminal")))
        labeled(grid, 0, _('Name'), self.name)
        labeled(grid, 1, _('Command'), self.command)
        labeled(grid, 2, _('Icon'), self.icon)
        labeled(grid, 3, _('Working folder'), self.cwd)
        grid.attach(self.terminal, 1, 4, 1, 1)

        frame = Gtk.Frame(label=_('Environment profiles to offer at launch'))
        pbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin=8)
        self.checks = {}
        selected = set(app.get("profiles", []))
        for name, prof in hub.config["profiles"].items():
            check = Gtk.CheckButton(label=name)
            check.set_active(name in selected)
            if prof.get("description"):
                check.set_tooltip_text(prof["description"])
            self.checks[name] = check
            pbox.pack_start(check, False, False, 0)
        if not self.checks:
            pbox.pack_start(Gtk.Label(label=_('No profiles: create one from “Environment profiles”.'),
                                      xalign=0), False, False, 0)
        hint = Gtk.Label(xalign=0, wrap=True)
        hint.set_markup(_('<small>With several profiles selected, you choose the environment when you click the icon. With just one, it is used directly.</small>'))
        hint.get_style_context().add_class("dim-label")
        pbox.pack_start(hint, False, False, 4)
        frame.add(pbox)
        grid.attach(frame, 0, 5, 2, 1)

        self.get_content_area().pack_start(grid, True, True, 0)
        self.show_all()

    def get_data(self):
        name = self.name.get_text().strip()
        command = self.command.get_text().strip()
        if not name or not command:
            message(self, _('Name and command are required.'))
            return None
        try:
            shlex.split(command)
        except ValueError as exc:
            message(self, _('The command is not valid.'), str(exc))
            return None
        return {"name": name, "command": command,
                "icon": self.icon.get_text().strip(),
                "cwd": self.cwd.get_text().strip(),
                "terminal": self.terminal.get_active(),
                "profiles": [n for n, c in self.checks.items() if c.get_active()]}


class SettingsDialog(Gtk.Dialog):
    def __init__(self, hub):
        super().__init__(title=_("Settings"), transient_for=hub.window, modal=True)
        self.hub = hub
        cfg = hub.config
        self.set_default_size(520, -1)
        self.add_buttons(_("Cancel"), Gtk.ResponseType.CANCEL, _("Save"), Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        grid = Gtk.Grid(row_spacing=10, column_spacing=12, margin=16)

        self.language = Gtk.ComboBoxText()
        self.language.append("auto", _("Automatic (system language)"))
        for code, name in LANGUAGES.items():
            self.language.append(code, name)
        self.language.set_active_id(cfg["language"] if cfg["language"] in LANGUAGES else "auto")
        labeled(grid, 0, _("Language"), self.language)

        self.font = Gtk.FontButton()
        self.font.set_font(cfg["terminal_font"])
        self.font.set_filter_func(lambda family, _face, *_args: family.is_monospace())
        labeled(grid, 1, _("Terminal font"), self.font)

        self.root_method = Gtk.ComboBoxText()
        self.root_method.append("auto", _("Automatic: wsl.exe, no password"))
        self.root_method.append("sudo", _("sudo: asks for your password"))
        self.root_method.set_active_id("sudo" if cfg["root_method"] == "sudo" else "auto")
        labeled(grid, 2, _("Root access"), self.root_method)

        hint = Gtk.Label(xalign=0, wrap=True)
        hint.set_markup("<small>%s</small>" % GLib.markup_escape_text(
            _("A language change takes effect after restarting WSL Hub.")))
        hint.get_style_context().add_class("dim-label")
        grid.attach(hint, 0, 3, 2, 1)

        self.get_content_area().pack_start(grid, True, True, 0)
        self.show_all()

    def values(self):
        return {"language": self.language.get_active_id() or "auto",
                "terminal_font": self.font.get_font() or self.hub.config["terminal_font"],
                "root_method": self.root_method.get_active_id() or "auto"}


# --------------------------------------------------------------------------- #
# Finestra principale
# --------------------------------------------------------------------------- #
class Hub:
    def __init__(self):
        self.config = Config()
        self._status_id = 0
        self._procs = set()
        self.server = None  # socket for single-instance activation (set by main)

        settings = Gtk.Settings.get_default()
        if settings is not None:
            if self.config["gtk_theme"]:
                settings.set_property("gtk-theme-name", self.config["gtk_theme"])
            settings.set_property("gtk-application-prefer-dark-theme",
                                  bool(self.config["dark_theme"]))
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.window = Gtk.Window(title=f"{APP_TITLE} ({DISTRO})")
        self.window.set_default_size(1320, 820)
        self.window.set_icon_name("utilities-terminal")

        header = Gtk.HeaderBar(show_close_button=True, title=APP_TITLE, subtitle=DISTRO)
        profiles_btn = Gtk.Button(label=_('Environment profiles'))
        profiles_btn.get_style_context().add_class("flat-btn")
        profiles_btn.connect("clicked", lambda _b: self.open_profiles())
        header.pack_start(profiles_btn)
        menu_btn = Gtk.MenuButton()
        menu_btn.get_style_context().add_class("icon-btn")
        menu_btn.set_image(Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.BUTTON))
        menu = Gtk.Menu()
        add_menu_item(menu, _('Edit config.json in the terminal'), self.edit_config_file)
        add_menu_item(menu, _('Reload configuration'), self.reload_config)
        add_menu_item(menu, _('Open the log folder'), self.show_logs)
        menu.show_all()
        menu_btn.set_popup(menu)
        header.pack_end(menu_btn)
        settings_btn = Gtk.Button()
        settings_btn.get_style_context().add_class("icon-btn")
        theme = Gtk.IconTheme.get_default()
        gear = next((n for n in ("preferences-system-symbolic", "emblem-system-symbolic",
                                 "applications-system-symbolic") if theme.has_icon(n)), None)
        if gear:
            settings_btn.set_image(Gtk.Image.new_from_icon_name(gear, Gtk.IconSize.BUTTON))
        else:
            settings_btn.set_label("⚙")
        settings_btn.set_tooltip_text(_("Settings"))
        settings_btn.connect("clicked", lambda _b: self.open_settings())
        header.pack_end(settings_btn)
        self.apps_toggle = Gtk.ToggleButton(label=_('Apps'), active=True)
        self.apps_toggle.get_style_context().add_class("accent-btn")
        self.apps_toggle.set_tooltip_text(_('Show or hide the app panel (Ctrl+Shift+A)'))
        header.pack_end(self.apps_toggle)
        self.window.set_titlebar(header)

        self.status_dot = Gtk.Label(label="●")
        self.status_dot.get_style_context().add_class("status-dot")
        self.status_label = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
        self.status_hints = Gtk.Label(xalign=1)
        self.status_hints.set_markup(_('<small>Ctrl+Shift+T  new tab     Ctrl+Shift+F  search apps</small>'))
        self.status_hints.get_style_context().add_class("status-hints")
        self.status_bar = Gtk.Box(spacing=8)
        self.status_bar.get_style_context().add_class("status-bar")
        self.status_bar.pack_start(self.status_dot, False, False, 0)
        self.status_bar.pack_start(self.status_label, True, True, 0)
        self.status_bar.pack_end(self.status_hints, False, False, 0)

        self.root = RootHelper(self)
        self.terminals = TerminalPanel(self)
        self.files = FilePanel(self)
        self.apps = AppPanel(self)

        right = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        right.pack1(self.apps, False, True)
        right.pack2(self.terminals, True, False)
        right.set_position(282)
        main = Gtk.Paned()
        main.pack1(self.files, False, True)
        main.pack2(right, True, False)
        main.set_position(388)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.get_style_context().add_class("hub-root")
        root.pack_start(main, True, True, 0)
        root.pack_start(self.status_bar, False, False, 0)
        self.window.add(root)

        self.apps_toggle.connect("toggled", lambda b: self.apps.set_visible(b.get_active()))
        self.window.connect("key-press-event", self._on_key)
        self.window.connect("delete-event", self._on_delete)
        self.window.connect("destroy", lambda _w: Gtk.main_quit())
        self.window.show_all()
        self.terminals.new_tab()
        if self.config.error:
            self.status(self.config.error, error=True)
        else:
            self.status(_('Ready. Configuration: {path}').format(path=CONFIG_FILE))

    # -- utilità
    def status(self, text, error=False):
        prefix = "<span foreground='%s'><b>%s</b></span> " % (UI_ROOT, _("Error:")) if error else ""
        self.status_label.set_markup(prefix + GLib.markup_escape_text(text))
        dot = self.status_dot.get_style_context()
        if error:
            dot.add_class("error")
        else:
            dot.remove_class("error")
        if self._status_id:
            GLib.source_remove(self._status_id)
        self._status_id = GLib.timeout_add_seconds(12 if error else 6, self._clear_status)

    def _clear_status(self):
        self.status_label.set_text("")
        self.status_dot.get_style_context().remove_class("error")
        self._status_id = 0
        return False

    def copy_text(self, text):
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(text, -1)
        self.status(_('Copied: {text}').format(text=text))

    def open_in_windows(self, path):
        exe, win = windows_explorer(), to_windows_path(path)
        if not exe or not win:
            self.status(_('Windows interoperability is not available in this distribution'),
                        error=True)
            return
        subprocess.Popen([exe, win], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True,
                         cwd="/mnt/c" if os.path.isdir("/mnt/c") else None)

    def edit_as_root(self, path):
        editor = os.environ.get("EDITOR") or "nano"
        self.terminals.new_tab(cwd=os.path.dirname(path), argv=[editor, path],
                               title=f"root: {os.path.basename(path)}", root=True)

    def cd_in_terminal(self, folder):
        tab = self.terminals.current()
        if tab is not None and tab.send_cd(folder):
            tab.term.grab_focus()
        else:
            self.status(_('The active terminal is running a program: opening a new tab'))
            self.terminals.new_tab(cwd=folder)

    def paste_in_terminal(self, path):
        tab = self.terminals.current()
        if tab is not None:
            tab.feed(shlex.quote(path) + " ")
            tab.term.grab_focus()

    # -- avvio app
    def launch(self, item, profile_name=None):
        profile = None
        if profile_name:
            profile = self.config["profiles"].get(profile_name)
            if profile is None:
                self.status(_('The profile “{name}” no longer exists').format(name=profile_name), error=True)
                return
        if item.get("desktop") is not None:
            argv = desktop_argv(item["desktop"])
        else:
            try:
                argv = shlex.split(item.get("command", ""))
            except ValueError as exc:
                self.status(_('Invalid command for {app}: {error}').format(app=item['name'], error=exc), error=True)
                return
            if argv:
                argv[0] = os.path.expanduser(argv[0])
        if not argv:
            self.status(_('No command configured for {app}').format(app=item['name']), error=True)
            return

        cwd = os.path.expanduser(item.get("cwd") or "") or HOME
        if not os.path.isdir(cwd):
            cwd = HOME
        label = item["name"] + (f" [{profile_name}]" if profile_name else "")

        if item.get("terminal"):
            self.terminals.new_tab(cwd=cwd, profile_name=profile_name, argv=argv, title=label)
            return

        extra = {"WSL_HUB": "1"}
        if profile_name:
            extra["WSL_HUB_PROFILE"] = profile_name
        env = build_env(profile, extra)
        has_script = bool((profile or {}).get("script", "").strip())
        if not has_script and shutil.which(argv[0], path=env.get("PATH")) is None:
            where = _(' with the PATH of profile “{name}”').format(name=profile_name) if profile_name else ""
            self.status(_('Command not found{where}: {command}').format(where=where, command=argv[0]), error=True)
            return

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOG_DIR / (re.sub(r"[^\w.-]+", "_", label).strip("_") + ".log")
        with open(log_path, "ab") as log:
            log.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')}  "
                      f"{shlex.join(argv)}\n".encode())
            log.flush()
            try:
                proc = subprocess.Popen(wrap_with_script(argv, profile), cwd=cwd, env=env,
                                        stdin=subprocess.DEVNULL, stdout=log,
                                        stderr=subprocess.STDOUT, start_new_session=True)
            except OSError as exc:
                self.status(_('Could not start {app}: {error}').format(app=label, error=exc.strerror), error=True)
                return
        self.status(_('Started {app}').format(app=label))
        started = time.monotonic()
        # Il processo viene controllato ogni secondo (poll() lo raccoglie, niente zombie)
        # finché non termina; il riferimento resta in self._procs.
        self._procs.add(proc)
        GLib.timeout_add(1000, self._check_app, proc, label, log_path, started)

    def _check_app(self, proc, label, log_path, started):
        code = proc.poll()
        if code is None:
            return True
        self._procs.discard(proc)
        if code != 0 and time.monotonic() - started < 15:
            try:
                tail = log_path.read_text(errors="replace").splitlines()[-25:]
            except OSError:
                tail = []
            self.status(_('{app} exited with code {code}').format(app=label, code=code), error=True)
            show_text(self.window, _('{app} exited right away (code {code})').format(app=label, code=code),
                      _('Full log: {path}\n\n').format(path=log_path) + "\n".join(tail))
        return False

    # -- gestione app personalizzate
    def edit_app(self, index=None, template=None):
        apps = self.config["apps"]
        app = dict(apps[index], _editing=True) if index is not None else template
        dlg = AppDialog(self, app)
        while dlg.run() == Gtk.ResponseType.OK:
            data = dlg.get_data()
            if data is None:
                continue
            if index is None:
                apps.append(data)
            else:
                apps[index] = data
            self.config.save()
            self.apps.rebuild()
            break
        dlg.destroy()

    def customize_system_app(self, item):
        info = item["desktop"]
        icon = info.get_icon()
        template = {"name": item["name"],
                    "command": shlex.join(desktop_argv(info)),
                    "icon": icon.to_string() if icon else "",
                    "cwd": item.get("cwd", ""),
                    "terminal": item.get("terminal", False),
                    "profiles": []}
        self.edit_app(template=template)

    def remove_app(self, index):
        name = self.config["apps"][index].get("name", "")
        if confirm(self.window, _('Remove “{name}” from the panel?').format(name=name),
                   _('The program stays installed: only the icon is removed.'), _('Remove')):
            self.config["apps"].pop(index)
            self.config.save()
            self.apps.rebuild()

    # -- configurazione
    def open_settings(self):
        dlg = SettingsDialog(self)
        response = dlg.run()
        values = dlg.values()
        dlg.destroy()
        if response != Gtk.ResponseType.OK:
            return
        cfg = self.config
        old_language = current_language()
        cfg["language"] = values["language"]
        if values["terminal_font"] != cfg["terminal_font"]:
            cfg["terminal_font"] = values["terminal_font"]
            font = Pango.FontDescription.from_string(values["terminal_font"])
            for i in range(self.terminals.notebook.get_n_pages()):
                self.terminals.notebook.get_nth_page(i).term.set_font(font)
        if values["root_method"] != cfg["root_method"]:
            cfg["root_method"] = values["root_method"]
            self.files.root_btn.set_active(False)  # the next activation uses the new method
            self.root.stop()
        cfg.save()
        new_language = values["language"] if values["language"] in LANGUAGES else detect_language()
        if new_language == old_language:
            self.status(_("Settings saved"))
        elif confirm(self.window, _("Restart WSL Hub now to apply the language?"),
                     _("Open terminal tabs will be closed. Apps you started keep running."),
                     _("Restart now")):
            self.restart()
        else:
            self.status(_("The new language will be used the next time WSL Hub starts"))

    def restart(self):
        """Restart WSL Hub in the same process (used to apply a language change)."""
        self.terminals.closing = True
        for i in reversed(range(self.terminals.notebook.get_n_pages())):
            self.terminals.close_tab(self.terminals.notebook.get_nth_page(i))
        self.root.stop()
        if self.server is not None:
            self.server.close()
        try:
            SOCKET_PATH.unlink()
        except OSError:
            pass
        script = os.path.abspath(sys.argv[0])
        os.execv(sys.executable, [sys.executable, script, *sys.argv[1:]])

    def open_profiles(self):
        dlg = ProfilesDialog(self)
        saved = False
        while dlg.run() == Gtk.ResponseType.OK:
            if dlg.apply():
                saved = True
                break
        dlg.destroy()
        if saved:
            self.on_config_changed()
            self.status(_('Profiles saved'))

    def on_config_changed(self):
        self.apps.system_btn.set_active(bool(self.config["show_system_apps"]))
        self.apps.rebuild()
        self.terminals.rebuild_profile_menu()
        self.files.rebuild_places()

    def reload_config(self):
        self.config.reload()
        self.on_config_changed()
        if self.config.error:
            self.status(self.config.error, error=True)
        else:
            self.status(_('Configuration reloaded'))

    def edit_config_file(self):
        editor = os.environ.get("EDITOR") or "nano"
        self.terminals.new_tab(argv=[editor, str(CONFIG_FILE)], title="config.json")
        self.status(_('After saving, use “Reload configuration” from the menu'))

    def show_logs(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.files.navigate(str(LOG_DIR))

    # -- eventi finestra
    def _on_key(self, _w, event):
        mods = event.state & Gtk.accelerator_get_default_mod_mask()
        if mods != (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK):
            return False
        key = Gdk.keyval_to_lower(event.keyval)
        if key == Gdk.KEY_t:
            self.terminals.new_tab(cwd=self.terminals.current_cwd())
        elif key == Gdk.KEY_w:
            tab = self.terminals.current()
            if tab is not None:
                self.terminals.close_tab(tab)
        elif key == Gdk.KEY_a:
            self.apps_toggle.set_active(not self.apps_toggle.get_active())
        elif key == Gdk.KEY_f:
            self.apps_toggle.set_active(True)
            self.apps.search.grab_focus()
        else:
            return False
        return True

    def _on_delete(self, *_a):
        self.terminals.closing = True
        self.root.stop()
        return False


# --------------------------------------------------------------------------- #
# Istanza singola: un secondo avvio porta in primo piano la finestra esistente
# --------------------------------------------------------------------------- #
def activate_existing_instance():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(str(SOCKET_PATH))
        sock.sendall(b"show\n")
        return True
    except OSError:
        return False
    finally:
        sock.close()


def listen_for_activation(callback):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        SOCKET_PATH.unlink()
    except FileNotFoundError:
        pass
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(SOCKET_PATH))
    server.listen(4)
    server.setblocking(False)

    def on_ready(_fd, _cond):
        try:
            conn, _addr = server.accept()
            conn.close()
            callback()
        except OSError:
            pass
        return True

    GLib.io_add_watch(server.fileno(), GLib.PRIORITY_DEFAULT, GLib.IO_IN, on_ready)
    return server


def main():
    GLib.set_prgname("wsl-hub")
    GLib.set_application_name(APP_TITLE)
    if "--version" in sys.argv:
        print(f"{APP_TITLE} {__version__}")
        return 0
    if "--new-instance" not in sys.argv and activate_existing_instance():
        return 0
    hub = Hub()
    server = listen_for_activation(hub.window.present)
    hub.server = server
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, lambda: Gtk.main_quit() or False)
    try:
        Gtk.main()
    finally:
        server.close()
        try:
            SOCKET_PATH.unlink()
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
