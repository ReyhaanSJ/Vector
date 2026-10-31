<div align="center">

# VECTOR

**An open-source, JARVIS-style AI assistant that runs your laptop.**

Talk or type: *"Vector, open VS Code and my project folder"*, *"tidy up my Downloads"*,
*"how's my battery?"*, *"remind me to stretch in 20 minutes"*. VECTOR works out the steps and does them.

Windows · macOS · Linux · Claude or fully local (Ollama) · MIT licensed

</div>

> **Pre-release:** VECTOR is still being tested and isn't ready for general use yet.

---

## Features

- **Natural language control.** Ask in plain English. The AI picks and chains the right skills.
- **Voice mode.** Hands-free with a wake word (*"Vector, ..."*) and spoken replies.
- **31 built-in skills, plus 6 more on Windows** (dark mode, brightness, Settings pages, Wi-Fi, show desktop, Recycle Bin):
  | Area | Skills |
  |---|---|
  | Apps & web | open/close apps (on Windows, any Start-menu or Store app), open websites, search Google/YouTube/GitHub/Maps, list running apps |
  | Files | list, find, open, read, write, create folders, move/rename, delete, **auto-organize a folder** |
  | System | battery/CPU/RAM/disk status, volume, lock screen, screenshots, shutdown/restart/sleep, run shell commands |
  | Productivity | reminders, desktop notifications, clipboard read/write, long-term memory (remember/recall/forget) |
  | Control | type text, keyboard shortcuts, media play/pause/next |
- **Start with your PC.** `vector --startup on` (Windows) launches it in voice mode at login.
- **Safe by default.** Anything that changes your system (shell commands, deleting or moving files, typing keys, closing apps, power actions) **asks you first**.
- **Remembers you.** Tell it *"remember my project folder is ~/code/robot"* and it'll know next time.
- **Pick your brain.** Claude (best results) or a **free, private, offline** model through [Ollama](https://ollama.com).
- **Easy to extend.** A new skill is one Python function with a `@tool` decorator.

## Quick start

### Windows 10/11 (one command)

```powershell
git clone https://github.com/reyhaansj/vector.git
cd vector
powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1
```

The full Windows guide, Windows-only skills and troubleshooting are in **[docs/windows.md](docs/windows.md)**.

### macOS / Linux / manual install

Requires **Python 3.11+**.

```bash
git clone https://github.com/reyhaansj/vector.git
cd vector
pip install -e ".[all]"      # or just `pip install -e .` for text-only mode
vector --setup               # creates ~/.vector/config.toml (optional)
```

### Option A: Claude (recommended)

Get an API key at <https://console.anthropic.com>, then:

```bash
# macOS / Linux
export ANTHROPIC_API_KEY="sk-ant-..."
# Windows (PowerShell)
setx ANTHROPIC_API_KEY "sk-ant-..."
```

### Option B: free and local with Ollama

Install [Ollama](https://ollama.com), then:

```bash
ollama pull llama3.1
vector --provider ollama        # or set provider = "ollama" in the config
```

Small local models are less reliable at multi-step tasks than Claude, but nothing leaves your machine.

## Usage

```bash
vector                          # chat by typing
vector --voice                  # hands-free: "Vector, open Spotify"
vector open my downloads folder # one-shot command
vector --list-skills            # see everything it can do
vector --selftest               # check everything works on your computer
```

In chat: `/help`, `/skills`, `/reset` (start a fresh conversation), `/exit`.

Example session:

```
you > what's taking up memory, and close spotify
  -> list_running_apps(limit=15)
  -> close_app(name='spotify')
  ! VECTOR wants to run close_app(name='spotify')
    Allow? [y/N] y
VECTOR > Chrome is the biggest at 1.8 GB. Spotify is closed.
```

### Voice mode setup notes

`pip install -e ".[voice]"` installs SpeechRecognition, pyttsx3 and PyAudio.

- **Linux:** `sudo apt install portaudio19-dev espeak-ng` before installing.
- **macOS:** `brew install portaudio` before installing.
- Speech-to-text uses Google's free recognizer (needs internet). See `vector/voice.py` to swap in Whisper for offline use.

## Configuration

`~/.vector/config.toml` (create it with `vector --setup`):

```toml
user_name = "Boss"
provider = "anthropic"        # or "ollama"
model = ""                    # blank = default (claude-opus-5-5 / llama3.1)
effort = "low"                # Claude thinking effort: low | medium | high | xhigh | max
confirm_dangerous = true      # ask before risky actions; keep this on
wake_word = "vector"
speak_replies = true
skill_dirs = []               # extra folders with your own skills
```

Any setting can also be set with an environment variable: `VECTOR_PROVIDER=ollama`, `VECTOR_USER_NAME=Ray`, and so on.

## Add your own skill

Drop a `.py` file in `~/.vector/skills/`:

```python
from vector import tool

@tool
def open_my_project() -> str:
    """Open my main coding project in VS Code."""
    import subprocess
    subprocess.Popen(["code", "~/code/robot"])
    return "Project opened."
```

Restart VECTOR and say *"open my project"*. The docstring tells the AI what the skill does, and type hints define the inputs.
Use `@tool(dangerous=True)` for anything that changes or deletes things. More in [docs/skills.md](docs/skills.md) and [examples/skills](examples/skills).

## How it works

```
 you (voice/text) -> VECTOR agent -> brain (Claude / Ollama)
                         ^              | picks skills to call
                         |              v
                     results  <-  skill registry -> your laptop
                                  (asks before risky actions)
```

| File | Purpose |
|---|---|
| `vector/cli.py` | terminal + voice interface |
| `vector/agent.py` | system prompt, safety checks, tool execution |
| `vector/brain/` | AI providers (`claude.py`, `ollama.py`) |
| `vector/registry.py` | `@tool` decorator, schema generation, plugin loading |
| `vector/skills/` | built-in skills |

## Safety

VECTOR can control your computer, so:
- Keep `confirm_dangerous = true`. `--yes` turns confirmations off; only use it if you trust what you're asking.
- Read through any third-party skill before putting it in your skills folder. It runs with your user's permissions.
- With Claude, your requests and the results of the skills it runs (file names, file contents it reads) are sent to Anthropic's API. Use Ollama if you want everything local.

## Roadmap

- [ ] Offline wake word + Whisper speech recognition
- [ ] System-tray / desktop GUI with a HUD
- [ ] Calendar & email skills
- [ ] Screen understanding (screenshot -> "what's on my screen?")
- [ ] Scheduled routines ("every morning at 9, open my work apps")

Contributions are very welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE). Free to use, modify and share.
