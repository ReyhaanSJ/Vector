# VECTOR on Windows 10/11

## Install (about 5 minutes)

1. Install **Git** and **Python 3.13** if you don't have them. In PowerShell:
   ```powershell
   winget install -e --id Git.Git
   winget install -e --id Python.Python.3.13
   ```
   Then close PowerShell and open a new window.
2. Download VECTOR and run the installer:
   ```powershell
   git clone https://github.com/reyhaansj/vector.git
   cd vector
   powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1
   ```
   The installer sets up Python packages, adds a `vector` command, asks for your Claude API key
   (or sets up free local AI with Ollama), and can make VECTOR start when you log in.
3. Open a **new** terminal and run `vector` (typing) or `vector --voice` (talking).

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
| `vector` is not recognized | Open a new terminal. Or run `.venv\Scripts\vector.exe` from the VECTOR folder. |
| "running scripts is disabled" | Use the exact command above (`-ExecutionPolicy Bypass`). |
| Voice packages fail to install | Use Python 3.13 (`winget install Python.Python.3.13`), then re-run the installer. |
| VECTOR can't hear you | Settings > Privacy & security > Microphone: turn on **Let desktop apps access your microphone**. Check the right mic is the default under Settings > System > Sound. |
| It hears "Victor" | That's fine, "Victor" and "Vektor" also work as wake words. |
| No notifications | Settings > System > Notifications: make sure notifications (and Windows PowerShell) are on, and Do Not Disturb is off. |
| Brightness doesn't change | Only built-in laptop screens support this; external monitors don't. |
| Claude says the API key is missing | Open a new terminal after setting it, or set it: `[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY","sk-ant-...","User")` |
