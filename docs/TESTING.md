# Launch test checklist

Work through this on a real laptop before making the repo public.

## 1. Automatic checks

```powershell
vector --selftest
```

Everything should **PASS** except things you haven't installed. If something fails, copy the
"Details" section and report it.

## 2. Try it for real (`vector`)

Type each of these and tick it off when it works:

- [ ] `what's my battery and memory like?`
- [ ] `open spotify` (or any app you have), then `close spotify` (should ask permission first)
- [ ] `open notepad and calculator`
- [ ] `search youtube for lofi music`
- [ ] `open github.com`
- [ ] `what's in my downloads folder?`
- [ ] `find any pdf files on my desktop`
- [ ] `organize my downloads folder, but show me what you'd do first`
- [ ] `create a file on my desktop called test.txt that says hello` (asks first), then `open it`
- [ ] `set volume to 30`
- [ ] `set brightness to 60`
- [ ] `turn on dark mode`, then `switch back to light mode`
- [ ] `open bluetooth settings`
- [ ] `what wifi am I on?`
- [ ] `remind me to drink water in 1 minute` (a notification should pop up)
- [ ] `remember that my favourite editor is VS Code`, `/exit`, start `vector` again, `what's my favourite editor?`
- [ ] `take a screenshot`
- [ ] `copy "hello world" to my clipboard`, then paste somewhere
- [ ] `run a command to show my IP address` (asks first; answering `n` should cancel cleanly)

## 3. Voice (`vector --voice`)

- [ ] It says "Vector online"
- [ ] "Vector, what time is it?" gets a spoken answer
- [ ] Saying "Vector" alone, then a request after "Yes?", works
- [ ] A risky action asks for a spoken yes/no, and "no" cancels
- [ ] "Vector, goodbye" quits

## 4. Fresh install

- [ ] Clone into a new folder and run `scripts\install-windows.ps1` from a clean PowerShell window
- [ ] `vector --startup on`, sign out and in again: VECTOR opens. Then `vector --startup off`.

## Ready to launch when

- the self-test passes,
- sections 2 and 3 are all ticked (or the failures are written down as known issues),
- then merge the branch into `main` and make the repo public.
