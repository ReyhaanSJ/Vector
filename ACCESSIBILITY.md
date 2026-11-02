# Accessibility

> VECTOR is a **pre-release** and is still being tested. Accessibility is important to us, and we're still improving it.

VECTOR aims to be usable by as many people as possible, whether you prefer typing, talking or listening.

## Ways to use VECTOR

- **Keyboard only:** press `Ctrl + Shift + Space` to open the summon bar, type your request and press `Enter`. Press `Esc` to stop VECTOR or close the bar. You never need the mouse.
- **Voice only:** turn on voice mode and say *"Vector, …"*. You don't need to press any button.
- **Listening:** turn on **Read aloud** (the small speaker button under the mic) and VECTOR speaks every reply.
- **Change the hotkey:** if `Ctrl + Shift + Space` is hard to press, pick another one with `vector --set hotkey=...`.
- **Focus mode:** the screen dims and only the summon bar stays active, which cuts down distractions. You can turn it off with `vector --set focus_mode=false`.

## Reporting an accessibility problem

If something in VECTOR is hard or impossible for you to use:

1. Open a new **Issue** in this repository.
2. Start the title with **[Accessibility]**.
3. Tell us what you were trying to do, what got in the way, and what tools you use (for example a screen reader, magnifier or voice control).

### How we respond

- You'll get a reply within **7 days**.
- We'll let you know whether we can fix it and roughly when.
- If there's a workaround, we'll share it while the fix is being made.
- When a fix is released, we'll ask you to try it and confirm it works for you.

## Ownership and maintenance

VECTOR is maintained by [@ReyhaanSJ](https://github.com/ReyhaanSJ), who reviews accessibility issues and checks this page with every major release.

## Supported environments

- **Windows 10 and Windows 11**
- **English only** (voice and text) for now
- Voice mode needs a working **microphone**. Read aloud uses the speech voices built into Windows.

## Known limitations

- **Screen readers** (like NVDA, JAWS or Narrator) **haven't been tested yet** and may not read the summon bar or the guide window correctly. Voice mode and Read aloud can be used instead.
- **High contrast mode** and custom Windows text sizes haven't been tested. Some text may look small on high-resolution screens.
- Voice recognition works best with a clear voice and a quiet room. Strong accents or background noise may cause mistakes. You can always type instead.
- VECTOR only understands **English** at the moment.

## Feedback and improvements

Ideas for making VECTOR easier to use are always welcome. Open an **Issue** starting with **[Accessibility]**, or suggest changes to this page in a pull request. If something is blocking you right now, please use the reporting steps above.
