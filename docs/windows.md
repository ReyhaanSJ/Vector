# VECTOR on Windows 10/11

## Install (about 5 minutes, mostly downloading)

1. On the VECTOR GitHub page, open **Releases** and download the newest **`VECTOR-Setup-x.y.z.zip`**.
2. Open Downloads, right-click the ZIP → **Extract All** → **Extract**.
3. In the extracted folder, double-click **`Install VECTOR.bat`**.
   If Windows says "Windows protected your PC", click **More info → Run anyway**
   (it appears for any downloaded script).
4. Answer the questions. Pressing **Enter** picks the suggested answer every time.

Setup then:
- gets a private copy of Python 3.13 just for VECTOR (any Python you already have is left alone),
- installs VECTOR into `%LOCALAPPDATA%\Programs\VECTOR`, so you can delete the downloaded folder,
- sets up the AI: the **free** local AI (installs Ollama and picks a model your graphics card
  runs fast), or Claude if you paste an API key,
- adds a `vector` command and **VECTOR** shortcuts on the Desktop and in the Start Menu.

**Updates:** VECTOR checks daily. Right-click the tray icon → **Update to x.y.z**, or run
`vector --update`. `vector --versions` lists every version, and `vector --update 0.2.0` installs
an older one. Remove everything with
**Start Menu > VECTOR > Uninstall VECTOR**.

### Using VECTOR

VECTOR starts with Windows and waits in the background (icon by the clock).

- **`Ctrl+Shift+Space`** anywhere opens the summon bar. Type, then press Enter.
- **Esc** stops VECTOR: it stops talking, cancels the current request (no further steps run),
  denies a pending Allow, and closes the bar. It works from any app while VECTOR is busy or talking.
- **Say "Vector, ..."** to talk to it. No button needed. "Vector" alone works too: it answers
  "Yes?" and listens.
- When VECTOR asks permission, click **Allow** or **Deny**, press **Y** or **N**, or say yes or no.
- **Focus mode:** while the bar is open, the screen behind it dims and clicks outside the bar
  do nothing. Esc (or Ctrl+Shift+Space) closes it. It lifts while VECTOR uses the screen, and
  quiet pop-ups (notices, saying "Vector") don't dim. Off: `vector --set focus_mode=false`.
- **Read aloud** (small speaker button under the mic): VECTOR reads its replies out loud, even
  typed ones. Turning it on also reads the reply already on screen. VECTOR remembers the choice.
- Tray icon (right-click): turn listening on or off, open the bar, quit.

### Screen and internet

- **"What's on my screen?"**, **"Click Reply"**, **"Scroll down and summarise this page"**:
  VECTOR takes screenshots and uses the mouse and keyboard. The first time in each request it
  asks *"See and control your screen for this request?"* Esc stops it immediately.
- **"Search the web for…"**, **"What's the latest on…"**, **"Read this page: <link>"**: VECTOR
  searches and reads pages itself. Nothing opens unless you ask it to open something.
- Seeing the screen needs an AI that understands pictures: **Claude** does. The small local
  model doesn't (`ollama pull qwen2.5vl` gets a local one that does).
- Screenshots go to your AI provider. To never allow it: `vector --set screen_access=never`.
  To stop the question: `vector --set screen_access=always`.

### Changing settings later

```powershell
vector --set model=qwen2.5:14b      # a smarter free model (needs more memory)
vector --set provider=openrouter    # free cloud AI (needs OPENROUTER_API_KEY)
vector --models                     # list the AI models you can use
vector --set provider=anthropic     # switch to Claude (needs ANTHROPIC_API_KEY)
vector --set user_name=Ray          # what VECTOR calls you
vector --set hotkey=ctrl+alt+v      # a different summon shortcut
vector --set listen_on_start=false  # don't listen for "Vector" until you turn it on
vector --set whisper_model=small.en # more accurate speech recognition (slower)
```

| Graphics card memory | Suggested free model |
|---|---|
| none / under 6 GB | `llama3.2` (setup's pick) |
| 6-8 GB (e.g. RTX 4050/5050) | `qwen2.5:7b` (setup's pick) |
| 12 GB+, or 8 GB and patience | `qwen2.5:14b` |

Get a new model with `ollama pull <name>`, then `vector --set model=<name>`.

## Windows-only skills

| Say something like | Skill |
|---|---|
| "open Spotify" / "open Word" | finds **any** Start-menu app, including Microsoft Store apps |
| "turn on dark mode" | `set_dark_mode` |
| "brightness 40" | `set_brightness` (built-in laptop screen) |
| "open bluetooth settings" | `open_windows_settings` (wifi, display, sound, battery, updates ...) |
| "what wifi am I on?" | `wifi_status` |
| "show desktop" | `show_desktop` |
| "empty the recycle bin" | `empty_recycle_bin` (asks first) |
| "volume 30" | `set_volume` (exact, via Windows Core Audio) |

Shell commands VECTOR runs (`run_shell_command`) use **PowerShell**, and VECTOR always asks before running one.
Desktop, Documents, Downloads and Pictures are found even when OneDrive has moved them.

## Start with Windows

```powershell
vector --startup on     # opens VECTOR in voice mode at every login
vector --startup text   # same, but typing mode
vector --startup off    # stop
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `vector` is not recognized | Open a new terminal, or use the Desktop shortcut. |
| "Windows protected your PC" | Click **More info → Run anyway**. |
| "Can't reach the free local AI" | Start the **Ollama** app from the Start Menu, then try again. |
| "Free OpenRouter limit reached" | Free models have daily limits. Wait, or switch: `vector --set provider=ollama`. |
| "Couldn't find VECTOR's releases" | The GitHub repo is still private. Updates work once it's public. |
| "Ollama doesn't have 'model'" | Run `ollama pull <model>` with the name it shows. |
| Shortcut does nothing | Another app uses it. Pick another: `vector --set hotkey=ctrl+alt+v`, then restart VECTOR from the tray. |
| It reacts when nobody said "Vector" | Lower background noise, or turn listening off from the tray icon. |
| Something went wrong in the app | The log is at `C:\Users\<you>\.vector\app.log`. |
| VECTOR can't hear you | Settings > Privacy & security > Microphone: turn on **Let desktop apps access your microphone**. Check the right mic is the default under Settings > System > Sound. |
| It hears "Victor" | That's fine, "Victor" and "Vektor" also work as wake words. |
| No notifications | Settings > System > Notifications: make sure notifications (and Windows PowerShell) are on, and Do Not Disturb is off. |
| Brightness doesn't change | Only built-in laptop screens support this; external monitors don't. |
| Claude says the API key is missing | Open a new terminal after setting it, or set it: `[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY","sk-ant-...","User")` |
