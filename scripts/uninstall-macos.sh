#!/bin/bash
# Removes VECTOR from this Mac.
# Started by /uninstall in the summon bar or `vector --uninstall`.
#
# Unattended options:
#   VECTOR_UNINSTALL_YES=1         don't ask anything
#   VECTOR_UNINSTALL_KEEP_DATA=1   keep settings, memory and saved keys (default when
#                                  unattended); 0 = delete them

AUTO=0; [ "${VECTOR_UNINSTALL_YES:-}" = "1" ] && AUTO=1
APP_DIR="$HOME/Library/Application Support/VECTOR"
DATA="$HOME/.vector"

echo ""
echo "  Uninstalling VECTOR"
echo ""

if [ "$AUTO" = "1" ]; then
    KEEP=1; [ "${VECTOR_UNINSTALL_KEEP_DATA:-}" = "0" ] && KEEP=0
elif [ -d "$DATA" ] && [ -r /dev/tty ]; then
    echo "Keep your settings and VECTOR's memory of you, so a reinstall remembers you?"
    printf '[Enter = keep, d = delete] '
    IFS= read -r ANSWER < /dev/tty
    ANSWER=$(printf '%s' "$ANSWER" | tr '[:upper:]' '[:lower:]')
    KEEP=1
    case "$ANSWER" in d|delete|n|no) KEEP=0 ;; esac
else
    KEEP=1
fi

# VECTOR may be running; stop it so its files can be deleted.
pkill -f "$APP_DIR/.venv/bin/python -m vector.app" 2>/dev/null
pkill -f "$APP_DIR/.venv/bin/vector-app" 2>/dev/null
sleep 0.5

AGENT="$HOME/Library/LaunchAgents/com.vector.assistant.plist"
for p in "$HOME/Applications/VECTOR.app" "$HOME/.local/bin/vector" "$AGENT" "$APP_DIR"; do
    if [ -e "$p" ]; then rm -rf "$p" && echo "Removed $p"; fi
done

if [ "$KEEP" = "1" ]; then
    [ -d "$DATA" ] && echo "Kept your data in $DATA and your saved keys (a reinstall will remember you)."
else
    if [ -d "$DATA" ]; then rm -rf "$DATA" && echo "Deleted your data ($DATA)"; fi
    for name in ANTHROPIC_API_KEY OPENROUTER_API_KEY; do
        security delete-generic-password -s VECTOR -a "$name" >/dev/null 2>&1 \
            && echo "Deleted your saved $name from the Keychain"
    done
fi

echo ""
echo "VECTOR is uninstalled."
echo "Ollama is a separate app: drag it from Applications to the Bin if you don't need it."
[ "$AUTO" = "1" ] || { printf 'Press Enter to close. '; read -r _ < /dev/tty; }
exit 0
