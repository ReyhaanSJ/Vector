<div align="center">

<img src="docs/logo.png" alt="VECTOR" height="80">

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
- **Sees and controls your screen.** "What's on my screen?", "click the blue Submit button",
  "scroll down and read me the next email". It works from screenshots and uses the mouse and keyboard
  like you would. It asks once per request first, and Esc stops it.
- **Uses the internet.** It searches the web and reads pages itself (news, facts, prices, how-tos),
  and downloads files when you ask.
- **Safe by default.** Anything that changes your system (shell commands, deleting or moving files, typing keys, closing apps, power actions) **asks you first**.
- **Remembers you.** Tell it *"remember my project folder is ~/code/robot"* and it'll know next time.
- **Pick your brain.** Claude (best results) or a **free, private, offline** model through [Ollama](https://ollama.com).
- **Easy to extend.** A new skill is one Python function with a `@tool` decorator.

## Quick start

### Windows 10/11: two clicks, nothing to install first

1. Download **`VECTOR-Setup-<version>.zip`** from the [Releases page](https://github.com/ReyhaanSJ/Vector/releases),
   then right-click it → **Extract All**.
2. Double-click **`Install VECTOR.bat`**.

That's it. Setup gets its own copy of Python, installs VECTOR, sets up the **free** local AI
(or Claude if you have an API key), and adds Desktop and Start Menu shortcuts.
No Python, Git or API key needed beforehand.

Or paste one line into PowerShell:

```powershell
irm https://raw.githubusercontent.com/ReyhaanSJ/Vector/HEAD/install.ps1 | iex
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

### Option A: Claude (smartest, paid)

Get an API key at <https://console.anthropic.com>, then:

```bash
# macOS / Linux
export ANTHROPIC_API_KEY="sk-ant-..."
# Windows (PowerShell)
setx ANTHROPIC_API_KEY "sk-ant-..."
```

### Option B: free cloud AI with OpenRouter

Free models (like Google's Gemma 4 31B) run on OpenRouter's servers: much smarter than a small
local model, with no strong graphics card needed. Free models have daily limits, and your requests
are sent to OpenRouter and the model's provider.

```bash
# make a free key at https://openrouter.ai/keys, then:
export OPENROUTER_API_KEY="sk-or-..."      # Windows: setx OPENROUTER_API_KEY "sk-or-..."
vector --set provider=openrouter          # picks the best free model available
vector --models                           # see the free models; pick one with --set model=<id>
```

### Option C: free and local with Ollama (default when no API key is set)

Install [Ollama](https://ollama.com), then:

```bash
ollama pull llama3.2
vector                          # uses Ollama automatically when no Claude key is set
```

Small local models are less reliable at multi-step tasks than Claude, but nothing leaves your machine.

## Usage

### The VECTOR app (Windows)

After setup, VECTOR runs quietly in the background. Look for its icon by the clock.

- **Press `Ctrl+Shift+Space` anywhere** to pop up the summon bar and type a request.
- **Or just say "Vector, ..."**, no button needed. Example: *"Vector, open Spotify and set the volume to 30."*
  Listening for the wake word happens offline on your computer, and so does turning your
  speech into text.
- Risky actions show an **Allow / Deny** card, and you can also just say "yes" or "no".
- **Esc stops VECTOR**: it stops talking, cancels what it's doing and denies any pending
  action. While VECTOR is busy or talking, this works even when another app is in front.
  (In the terminal, Ctrl+C does the same.)
- Right-click the tray icon to turn listening off or quit. Change the shortcut with
  `vector --set hotkey=ctrl+alt+v`.

### Terminal

```bash
vector                          # chat by typing
vector --app                    # the background app (summon bar + voice)
vector --voice                  # hands-free in the terminal: "Vector, open Spotify"
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

### Voice notes

`pip install -e ".[voice]"` installs the offline wake-word spotter (Vosk), offline
speech-to-text (faster-whisper) and microphone access (sounddevice). The speech models
(~200 MB) download once; `vector --prepare-voice` fetches them ahead of time.
Pick a speech model with `vector --set whisper_model=small.en`. It's more accurate but slower.
`tiny.en` is the fastest.

## Updating

The VECTOR app checks for a new version once a day. When there is one, right-click the tray icon and choose
**Update to x.y.z**. It downloads, installs and restarts by itself, and keeps your settings and memory.

```bash
vector --versions          # every version, newest first
vector --update            # install the newest
vector --update 0.2.0      # install a specific version (also to go back)
```

Versions are published on the [Releases page](https://github.com/ReyhaanSJ/Vector/releases).
Maintainers: bump the version in `pyproject.toml` and `vector/__init__.py`, then on GitHub go to
**Actions → Release → Run workflow** (or push a tag like `v0.3.0`). The release builds itself.

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
- With Claude or OpenRouter, your requests and what the skills return (file names, file contents
  it reads, **screenshots of your screen**) are sent to that AI provider. Close private things
  before asking VECTOR to look at the screen, or use `vector --set screen_access=never`.
  With Ollama everything stays on your computer.
- Screen control asks once per request (`screen_access = "ask"`). Esc, or moving the mouse into a
  screen corner, stops it immediately.

## Roadmap

- [x] Offline wake word + Whisper speech recognition
- [x] Tray app with a summon bar
- [ ] Full desktop window with system HUD
- [ ] Calendar & email skills
- [ ] Screen understanding (screenshot -> "what's on my screen?")
- [ ] Scheduled routines ("every morning at 9, open my work apps")

Contributions are very welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE). Free to use, modify and share.
