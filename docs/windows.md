# VECTOR on Windows 10/11

## Install (about 5 minutes, mostly downloading)

1. On the VECTOR GitHub page: green **Code** button → **Download ZIP**.
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

Run `Install VECTOR.bat` again any time to update. Remove everything with
**Start Menu > VECTOR > Uninstall VECTOR**.

### Changing settings later

```powershell
vector --set model=qwen2.5:14b      # a smarter free model (needs more memory)
vector --set provider=anthropic     # switch to Claude (needs ANTHROPIC_API_KEY)
vector --set user_name=Ray          # what VECTOR calls you
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
| "Ollama doesn't have 'model'" | Run `ollama pull <model>` with the name it shows. |
| VECTOR can't hear you | Settings > Privacy & security > Microphone: turn on **Let desktop apps access your microphone**. Check the right mic is the default under Settings > System > Sound. |
| It hears "Victor" | That's fine, "Victor" and "Vektor" also work as wake words. |
| No notifications | Settings > System > Notifications: make sure notifications (and Windows PowerShell) are on, and Do Not Disturb is off. |
| Brightness doesn't change | Only built-in laptop screens support this; external monitors don't. |
| Claude says the API key is missing | Open a new terminal after setting it, or set it: `[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY","sk-ant-...","User")` |
