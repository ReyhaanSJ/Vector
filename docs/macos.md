# VECTOR on a Mac

VECTOR runs on **macOS 11 Big Sur or newer**, on Apple silicon (M1 to M5) and Intel Macs.
It does everything the Windows version does: the summon bar, hands-free voice, read aloud,
seeing and clicking your screen, the internet, updates and `/uninstall`.

> **Pre-release:** the Mac version is new. It's tested automatically on real Macs, but not yet
> by many people. If something looks wrong, please
> [open an issue](https://github.com/ReyhaanSJ/Vector/issues) with a screenshot.

## Install

1. Open **Terminal** (press **Cmd + Space**, type `Terminal`, press Enter).
2. Paste this and press Enter:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/ReyhaanSJ/Vector/HEAD/install.sh | bash
   ```

3. Answer the questions. **Pressing Enter picks the suggested answer** every time.

Prefer downloading? Get **`VECTOR-Setup-<version>.zip`** from the
[Releases page](https://github.com/ReyhaanSJ/Vector/releases), open it, and double-click
**`Install VECTOR.command`**. If macOS says it *"cannot be opened because it is from an
unidentified developer"*, **right-click** the file → **Open** → **Open**.

**What setup does** (and skips if it's already there):

| Step | What happens |
|---|---|
| 1. Get VECTOR | Copies VECTOR to `~/Library/Application Support/VECTOR`. |
| 2. Python | Downloads a private Python 3.13 just for VECTOR (~20 MB). Your own Python and Homebrew are never touched. |
| 3. Packages | Installs VECTOR, voice support and the offline speech models (~200 MB). |
| 4. AI brain | Asks which AI to use. Keys are saved in your **Keychain**. For the free local AI it installs **Ollama** and picks a model for your Mac's memory. |
| 5. App | Adds **VECTOR** to your **Applications** folder (Spotlight and Launchpad find it), a `vector` command for Terminal, and (if you agree) starts VECTOR when you log in. |

## Using it

| | On a Mac |
|---|---|
| Open the bar | **Control + Shift + Space** from any app, or click VECTOR in the **Dock** |
| VECTOR's menu | When VECTOR is the active app, the **VECTOR** menu (top left of the screen): listen, check for updates, guide, quit |
| Quit | **Cmd + Q** while VECTOR is active, or the VECTOR menu → Quit |
| Stop anything | **Esc** |
| Change the shortcut | `vector --set hotkey=cmd+shift+v` (use `ctrl`, `shift`, `alt`/`option`, `cmd`) |

Everything else (voice, read aloud, bar commands like `/guide` and `/uninstall`) works exactly
as described in the [README](../README.md#6-using-vector).

## Permissions (macOS asks once)

macOS protects some things and asks you before VECTOR can use them. Click **Allow** or **OK**.

| Permission | When it's asked | What for |
|---|---|---|
| **Microphone** | The first time you turn voice on | Hearing "Vector, …" |
| **Screen Recording** | The first time VECTOR looks at your screen | Screenshots for "what's on my screen?" |
| **Accessibility** | The first time VECTOR clicks or types for you | Moving the mouse, clicking, typing, pressing keys |

If you clicked **Don't Allow** by mistake: open **System Settings → Privacy & Security →**
*Microphone* / *Screen & System Audio Recording* / *Accessibility*, switch **VECTOR** on, then
quit and reopen VECTOR. (If VECTOR isn't in the list, click **+** and pick it from your
Applications folder.)

The Control + Shift + Space shortcut needs **no** permission.

## Updating

Click VECTOR in the menu bar → **Check for updates** (VECTOR also checks by itself), or run
`vector --update`. Your settings, memory and AI choice are kept. Running the install command
again also updates.

## Uninstalling

Type **`/uninstall`** in the summon bar, or run `vector --uninstall` in Terminal. You choose
whether to keep your data (settings, memory, saved keys) for a later reinstall.

Dragging VECTOR from Applications to the Bin only removes the app icon; `/uninstall` also removes
its Python and login item. Ollama is a separate app: drag it to the Bin if you don't need it.

## Where things are

| What | Where |
|---|---|
| The app | `~/Applications/VECTOR.app` |
| VECTOR's files and Python | `~/Library/Application Support/VECTOR` |
| Your settings and memory | `~/.vector` |
| API keys | Your login Keychain (Keychain Access → search "VECTOR") |
| Start at login | `~/Library/LaunchAgents/com.vector.assistant.plist` |
| Log (for bug reports) | `~/.vector/app.log` |

## Troubleshooting

| Problem | Fix |
|---|---|
| `vector: command not found` | Open a **new** Terminal window (setup added `~/.local/bin` to your PATH). |
| The shortcut does nothing | Another app may use Control + Shift + Space. Pick another: `vector --set hotkey=ctrl+alt+v`, then quit and reopen VECTOR. |
| "What's on my screen?" only sees the wallpaper | Turn on **Screen & System Audio Recording** for VECTOR (see Permissions), then reopen VECTOR. |
| Clicks or typing do nothing | Turn on **Accessibility** for VECTOR, then reopen VECTOR. |
| Voice never hears "Vector" | Turn on **Microphone** for VECTOR; check the right mic is chosen in System Settings → Sound → Input. |
| Text looks too small or too big | Tell us in an issue with a screenshot (and your Mac model), so we can tune it. |
| "OpenRouter rejected the API key" (or Claude) | Run `vector --set-key openrouter` (or `vector --set-key claude`) in Terminal and paste the key again. It's checked before it's saved. Then quit and reopen VECTOR. |
| Anything else | Run `vector --selftest` in Terminal and paste the report in an issue. |
