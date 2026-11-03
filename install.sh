#!/bin/bash
# VECTOR installer for macOS (11 Big Sur or newer, Apple silicon or Intel).
#
# Easiest: open Terminal and paste
#     curl -fsSL https://raw.githubusercontent.com/ReyhaanSJ/Vector/HEAD/install.sh | bash
# Or double-click "Install VECTOR.command" in the downloaded VECTOR folder.
#
# It does everything: sets up VECTOR's own private copy of Python (yours is untouched),
# installs VECTOR, sets up the free local AI (Ollama) or Claude, and adds VECTOR to your
# Applications plus a `vector` command. Run it again any time to update.
#
# Unattended options (environment variables), mainly for testing:
#   VECTOR_INSTALL_YES=1            accept every default without asking
#   VECTOR_INSTALL_AI=ollama|openrouter|claude|none
#   VECTOR_INSTALL_SKIP_MODEL=1     don't download the Ollama model or voice models
#   VECTOR_INSTALL_VERSION=0.4.1    install that version (default: the newest release)
#   VECTOR_INSTALL_KEEP_SETTINGS=1  updating: keep the AI choice and login setting
#   VECTOR_INSTALL_LAUNCH=1         open VECTOR when done
#   VECTOR_INSTALL_NO_SHORTCUTS=1   don't add VECTOR to Applications
#
# Written for the bash that comes with macOS (3.2), so no newer bash features.

set -u

REPO="ReyhaanSJ/Vector"
APP_DIR="$HOME/Library/Application Support/VECTOR"
APP_SRC="$APP_DIR/src"
VENV="$APP_DIR/.venv"
PY="$VENV/bin/python"
BUNDLE="$HOME/Applications/VECTOR.app"
BIN_DIR="$HOME/.local/bin"
AUTO=0; [ "${VECTOR_INSTALL_YES:-}" = "1" ] && AUTO=1
AI_CHOICE=$(printf '%s' "${VECTOR_INSTALL_AI:-ask}" | tr '[:upper:]' '[:lower:]')
SKIP_MODEL=0; [ "${VECTOR_INSTALL_SKIP_MODEL:-}" = "1" ] && SKIP_MODEL=1

if [ -t 1 ]; then
    CYAN=$'\033[36m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; DIM=$'\033[2m'; OFF=$'\033[0m'
else
    CYAN=""; GREEN=""; YELLOW=""; RED=""; DIM=""; OFF=""
fi
say()  { printf '%s\n' "$*"; }
good() { printf '%s%s%s\n' "$GREEN" "$*" "$OFF"; }
warn() { printf '%s%s%s\n' "$YELLOW" "$*" "$OFF"; }
step() { printf '\n%s[%s/5] %s%s\n' "$CYAN" "$1" "$2" "$OFF"; }
fail() {
    printf '\n%sSetup stopped: %s%s\n' "$RED" "$*" "$OFF"
    printf '%sTake a screenshot of this window and open an issue on the VECTOR GitHub page.%s\n' "$RED" "$OFF"
    exit 1
}

# Questions are read from the keyboard even when this script itself arrives through a pipe
# (curl ... | bash), so they don't swallow the rest of the script.
TTY=""
if [ "$AUTO" = "0" ] && [ -r /dev/tty ] && { : < /dev/tty; } 2>/dev/null; then TTY=/dev/tty; fi
[ -z "$TTY" ] && AUTO=1
ask() {  # ask "Question" default(y/n) -> exit status 0 = yes
    local question="$1" default="$2" hint answer
    if [ "$AUTO" = "1" ]; then [ "$default" = "y" ]; return; fi
    if [ "$default" = "y" ]; then hint="[Enter = yes, n = no]"; else hint="[y = yes, Enter = no]"; fi
    printf '%s %s ' "$question" "$hint"
    IFS= read -r answer < "$TTY" || answer=""
    answer=$(printf '%s' "$answer" | tr '[:upper:]' '[:lower:]' | tr -d ' ')
    if [ -z "$answer" ]; then [ "$default" = "y" ]; return; fi
    [ "$answer" = "y" ] || [ "$answer" = "yes" ]
}
read_line() { local answer; IFS= read -r answer < "$TTY" || answer=""; printf '%s' "$answer"; }
read_secret() { local answer; IFS= read -rs answer < "$TTY" || answer=""; printf '\n' > "$TTY"; printf '%s' "$answer"; }

[ "$(uname -s)" = "Darwin" ] || fail "this installer is for macOS. On Windows, use 'Install VECTOR.bat'."

say ""
say "  ${CYAN}V E C T O R   setup${OFF}"
say "  ${DIM}your laptop, on command${OFF}"

# ---------------------------------------------------------------- 1. files
step 1 "Getting VECTOR"
SOURCE=""
HERE=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
    HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
fi
if [ -n "$HERE" ] && [ -f "$HERE/pyproject.toml" ]; then
    SOURCE="$HERE"
else
    if [ -n "${VECTOR_INSTALL_VERSION:-}" ]; then
        TAG="v${VECTOR_INSTALL_VERSION#[vV]}"
        URL="https://github.com/$REPO/archive/refs/tags/$TAG.tar.gz"
        say "Downloading VECTOR $TAG..."
    else
        URL="https://github.com/$REPO/archive/HEAD.tar.gz"
        TAG=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null \
              | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -n 1)
        if [ -n "$TAG" ]; then
            URL="https://github.com/$REPO/archive/refs/tags/$TAG.tar.gz"
            say "Downloading VECTOR $TAG..."
        else
            say "Downloading the latest version..."
        fi
    fi
    TMP=$(mktemp -d -t vector-setup)
    curl -fsSL "$URL" -o "$TMP/vector.tar.gz" || fail "couldn't download VECTOR. Check your internet connection."
    tar -xzf "$TMP/vector.tar.gz" -C "$TMP" || fail "the download looks damaged."
    FOUND=$(find "$TMP" -maxdepth 2 -name pyproject.toml | head -n 1)
    [ -n "$FOUND" ] || fail "the download didn't contain VECTOR."
    SOURCE=$(dirname "$FOUND")
fi
mkdir -p "$APP_DIR" || fail "couldn't create $APP_DIR."
# Updating? Close the running app first so its files can be replaced.
pkill -f "$VENV/bin/python -m vector.app" 2>/dev/null
pkill -f "$VENV/bin/vector-app" 2>/dev/null
if [ "$(cd "$SOURCE" && pwd -P)" != "$(mkdir -p "$APP_SRC" && cd "$APP_SRC" && pwd -P)" ]; then
    rsync -a --delete --exclude ".venv" --exclude ".git" --exclude "__pycache__" \
          --exclude ".pytest_cache" "$SOURCE/" "$APP_SRC/" || fail "couldn't copy VECTOR's files to $APP_SRC."
fi
say "Installing to $APP_DIR"

# ---------------------------------------------------------------- 2. python
step 2 "Setting up Python for VECTOR"
UV=$(command -v uv 2>/dev/null)
for candidate in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" /opt/homebrew/bin/uv /usr/local/bin/uv; do
    if [ -z "$UV" ] && [ -x "$candidate" ]; then UV="$candidate"; fi
done
if [ -n "$UV" ]; then
    say "Already installed: uv"
else
    say "Installing uv, the tool that manages VECTOR's Python..."
    curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 INSTALLER_NO_MODIFY_PATH=1 sh >/dev/null 2>&1
    for candidate in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv"; do
        if [ -z "$UV" ] && [ -x "$candidate" ]; then UV="$candidate"; fi
    done
fi
[ -n "$UV" ] || fail "couldn't install uv (https://docs.astral.sh/uv/)."
# VECTOR uses a Python that uv manages, because it always includes the window toolkit (Tk)
# VECTOR's summon bar needs. Python from Homebrew often doesn't. Your own Python is left alone.
PY_WANTED=">=3.11,<3.14"
EXISTING=$("$UV" python find --python-preference only-managed "$PY_WANTED" 2>/dev/null | head -n 1)
if [ -n "$EXISTING" ] && [ -x "$EXISTING" ]; then
    say "Already installed: $("$EXISTING" --version 2>&1) (reusing it)"
else
    say "Downloading Python 3.13 just for VECTOR (~20 MB, your own Python is left alone)..."
fi
if [ -x "$PY" ] && ! "$PY" -c "import tkinter" >/dev/null 2>&1; then
    rm -rf "$VENV"  # an older environment without Tk: start fresh
fi
"$UV" venv "$VENV" --python "$PY_WANTED" --python-preference only-managed --allow-existing --quiet \
    || fail "couldn't create VECTOR's Python environment."
[ -x "$PY" ] || fail "couldn't create VECTOR's Python environment."

# ---------------------------------------------------------------- 3. packages
step 3 "Installing VECTOR (parts already installed are skipped)"
( cd "$APP_SRC" && "$UV" pip install --python "$PY" ".[control,app]" --quiet ) \
    || fail "installing VECTOR's packages failed."
VOICE_OK=1
if ! ( cd "$APP_SRC" && "$UV" pip install --python "$PY" ".[voice]" --quiet ); then
    VOICE_OK=0
    warn "Voice support couldn't be installed. Typing and the summon bar work fine."
fi
if [ "$VOICE_OK" = "1" ] && [ "$SKIP_MODEL" = "0" ]; then
    "$PY" -m vector --prepare-voice || warn "Couldn't download them now; VECTOR will try again when you first use voice."
fi
"$PY" -m vector --setup >/dev/null 2>&1

# ---------------------------------------------------------------- 4. AI brain
step 4 "Choosing VECTOR's AI brain"
UPDATING=0
if [ "${VECTOR_INSTALL_KEEP_SETTINGS:-}" = "1" ] && [ -f "$HOME/.vector/config.toml" ]; then UPDATING=1; fi
keychain_has() { security find-generic-password -s VECTOR -a "$1" >/dev/null 2>&1; }
save_key() {
    if security add-generic-password -U -s VECTOR -a "$1" -l "VECTOR $1" -w "$2" >/dev/null 2>&1; then
        good "Key saved in your Mac's Keychain (only VECTOR uses it)."
    else
        warn "Couldn't save the key in the Keychain. Run this setup again to retry."
    fi
}
HAS_CLAUDE=0; { [ -n "${ANTHROPIC_API_KEY:-}" ] || keychain_has ANTHROPIC_API_KEY; } && HAS_CLAUDE=1
HAS_OPENROUTER=0; { [ -n "${OPENROUTER_API_KEY:-}" ] || keychain_has OPENROUTER_API_KEY; } && HAS_OPENROUTER=1

if [ "$UPDATING" = "1" ]; then
    say "Updating: keeping your AI settings."
    AI_CHOICE="keep"
elif [ "$AI_CHOICE" = "ask" ]; then
    DEFAULT=1; [ "$HAS_OPENROUTER" = "1" ] && DEFAULT=2; [ "$HAS_CLAUDE" = "1" ] && DEFAULT=3
    if [ "$AUTO" = "1" ]; then
        PICK=$DEFAULT
    else
        say "  1) Free AI on this Mac (Ollama). Private, works offline, no account."
        say "  2) Free cloud AI (OpenRouter: the best free model available). Smarter, needs internet"
        say "     and a free account. Free models have daily limits."
        say "  3) Claude. The smartest, needs an Anthropic API key (paid)."
        say "  4) Skip for now"
        printf 'Pick 1, 2, 3 or 4 [Enter = %s] ' "$DEFAULT"
        PICK=$(read_line | tr -d ' ')
        [ -z "$PICK" ] && PICK=$DEFAULT
    fi
    case "$PICK" in
        1) AI_CHOICE=ollama ;; 2) AI_CHOICE=openrouter ;; 3) AI_CHOICE=claude ;; *) AI_CHOICE=none ;;
    esac
fi

find_ollama() {
    command -v ollama 2>/dev/null && return
    for candidate in /Applications/Ollama.app/Contents/Resources/ollama \
                     "$HOME/Applications/Ollama.app/Contents/Resources/ollama" \
                     /opt/homebrew/bin/ollama /usr/local/bin/ollama; do
        if [ -x "$candidate" ]; then printf '%s\n' "$candidate"; return; fi
    done
}

case "$AI_CHOICE" in
ollama)
    OLLAMA=$(find_ollama)
    if [ -n "$OLLAMA" ]; then
        say "Already installed: Ollama"
    else
        say "Installing Ollama (the free AI engine)..."
        APPS=/Applications; [ -w /Applications ] || APPS="$HOME/Applications"
        mkdir -p "$APPS"
        OTMP=$(mktemp -d -t vector-ollama)
        if curl -fsSL "https://ollama.com/download/Ollama-darwin.zip" -o "$OTMP/Ollama.zip" \
           && ditto -x -k "$OTMP/Ollama.zip" "$APPS"; then
            OLLAMA=$(find_ollama)
        fi
        rm -rf "$OTMP"
    fi
    if [ -z "$OLLAMA" ]; then
        warn "Ollama isn't installed. Get it from https://ollama.com and run this setup again."
    else
        # Pick a model this Mac can run quickly: Apple silicon shares its memory with the GPU.
        MEM_GB=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1073741824 ))
        MODEL=llama3.2
        if [ "$(uname -m)" = "arm64" ] && [ "$MEM_GB" -ge 16 ]; then MODEL="qwen2.5:7b"; fi
        say "Using AI model $MODEL (${MEM_GB} GB memory, $(uname -m))."
        "$PY" -m vector --set provider=ollama --set "model=$MODEL" >/dev/null
        if [ "$SKIP_MODEL" = "0" ]; then
            if ! "$OLLAMA" list >/dev/null 2>&1; then
                case "$OLLAMA" in
                    *.app/*) open -g -a "${OLLAMA%%.app/*}.app" ;;
                    *) ( "$OLLAMA" serve >/dev/null 2>&1 & ) ;;
                esac
                for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
                    "$OLLAMA" list >/dev/null 2>&1 && break
                    sleep 2
                done
            fi
            if "$OLLAMA" list 2>/dev/null | grep -Eq "^${MODEL}(:latest)?[[:space:]]"; then
                say "Already downloaded: $MODEL"
            else
                say "Downloading the AI model $MODEL (a few GB, only needed once)..."
                "$OLLAMA" pull "$MODEL" || warn "Download failed. Later, run:  ollama pull $MODEL"
            fi
        fi
    fi
    ;;
openrouter)
    if [ "$HAS_OPENROUTER" = "0" ] && [ "$AUTO" = "0" ]; then
        say "1. Sign up free at https://openrouter.ai"
        say "2. Make a key at https://openrouter.ai/keys"
        printf '3. Paste the key here (it stays hidden): '
        KEY=$(read_secret)
        [ -n "$KEY" ] && save_key OPENROUTER_API_KEY "$KEY"
    fi
    "$PY" -m vector --set provider=openrouter --set "model=auto:free" >/dev/null
    ;;
claude)
    if [ "$HAS_CLAUDE" = "0" ] && [ "$AUTO" = "0" ]; then
        say "Get a key at https://console.anthropic.com (API keys page)."
        printf 'Paste your API key (it stays hidden): '
        KEY=$(read_secret)
        [ -n "$KEY" ] && save_key ANTHROPIC_API_KEY "$KEY"
    fi
    "$PY" -m vector --set provider=anthropic --set model= >/dev/null
    ;;
keep) ;;
*) say "Skipped. Set it up later by running this setup again." ;;
esac

# ---------------------------------------------------------------- 5. app + command
step 5 "Adding VECTOR to Applications and the vector command"
mkdir -p "$BIN_DIR"
# Small wrappers instead of links: they keep working even though the folder name has a space.
cat > "$BIN_DIR/vector" <<EOF
#!/bin/bash
# Added by VECTOR's installer. Removed by: vector --uninstall
exec "$PY" -m vector "\$@"
EOF
chmod +x "$BIN_DIR/vector"
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        PROFILE="$HOME/.zprofile"; [ "$(basename "${SHELL:-zsh}")" = "bash" ] && PROFILE="$HOME/.bash_profile"
        if ! grep -qs '.local/bin' "$PROFILE"; then
            printf '\n# Added by VECTOR setup\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$PROFILE"
        fi
        ;;
esac

VERSION=$("$PY" -m vector --version 2>/dev/null | sed 's/^VECTOR //')
[ -n "$VERSION" ] || fail "VECTOR was installed but doesn't start."
if [ "${VECTOR_INSTALL_NO_SHORTCUTS:-}" != "1" ]; then
    rm -rf "$BUNDLE"
    mkdir -p "$BUNDLE/Contents/MacOS" "$BUNDLE/Contents/Resources" || fail "couldn't create $BUNDLE."
    cp "$APP_SRC/vector/assets/icon.icns" "$BUNDLE/Contents/Resources/VECTOR.icns" 2>/dev/null
    cat > "$BUNDLE/Contents/MacOS/VECTOR" <<EOF
#!/bin/bash
# Opens VECTOR (made by VECTOR's installer).
exec "$PY" -m vector.app "\$@"
EOF
    chmod +x "$BUNDLE/Contents/MacOS/VECTOR"
    cat > "$BUNDLE/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>VECTOR</string>
  <key>CFBundleDisplayName</key><string>VECTOR</string>
  <key>CFBundleIdentifier</key><string>com.vector.assistant</string>
  <key>CFBundleExecutable</key><string>VECTOR</string>
  <key>CFBundleIconFile</key><string>VECTOR</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>LSApplicationCategoryType</key><string>public.app-category.productivity</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSMicrophoneUsageDescription</key><string>VECTOR listens for "Vector" and your requests when voice mode is on.</string>
  <key>NSAppleEventsUsageDescription</key><string>VECTOR controls other apps when you ask it to.</string>
</dict>
</plist>
EOF
    codesign --force --sign - "$BUNDLE" >/dev/null 2>&1   # a local signature keeps macOS' permission prompts tidy
    touch "$BUNDLE"
    LSREGISTER=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
    [ -x "$LSREGISTER" ] && "$LSREGISTER" -f "$BUNDLE" >/dev/null 2>&1
fi

LOGIN_AGENT="$HOME/Library/LaunchAgents/com.vector.assistant.plist"
if [ "$UPDATING" = "1" ]; then
    if [ -f "$LOGIN_AGENT" ]; then "$PY" -m vector --startup on >/dev/null; fi   # refresh it
elif ask "Start VECTOR quietly in the background when you log in? (recommended)" y; then
    "$PY" -m vector --startup on >/dev/null
fi

say ""
good "  All done!"
good "  VECTOR is in your Applications folder (open it with Spotlight: Cmd + Space, \"VECTOR\")."
good "    - press Ctrl + Shift + Space anywhere to type to it"
[ "$VOICE_OK" = "1" ] && good "    - or just say \"Vector, what time is it?\""
say "  ${DIM}The first time, macOS asks to allow the microphone, and for screen tasks Screen Recording${OFF}"
say "  ${DIM}and Accessibility (System Settings > Privacy & Security). VECTOR's guide shows how.${OFF}"
say "  ${DIM}Check everything works:  vector --selftest   (open a new Terminal window first)${OFF}"
say "  ${DIM}Remove it later: type /uninstall in the bar, or run: vector --uninstall${OFF}"
say ""
say "  ${DIM}Installed VECTOR $VERSION${OFF}"
if [ "${VECTOR_INSTALL_LAUNCH:-}" = "1" ]; then
    if [ -d "$BUNDLE" ]; then open "$BUNDLE"; else ( "$PY" -m vector.app >/dev/null 2>&1 & ); fi
elif [ "$AUTO" = "0" ] && ask "Open VECTOR now?" y; then
    if [ -d "$BUNDLE" ]; then open "$BUNDLE"; else ( "$PY" -m vector.app >/dev/null 2>&1 & ); fi
fi
exit 0
