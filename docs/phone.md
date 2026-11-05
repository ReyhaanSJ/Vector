# VECTOR Remote: use VECTOR from your phone

See your computer's screen live on your iPhone (or Android phone), tap to click, type, and ask
VECTOR to do things, from the sofa or another room.

> **Pre-release:** VECTOR Remote is new. Please [open an issue](https://github.com/ReyhaanSJ/Vector/issues)
> if something doesn't work, and say which phone you used.

It isn't an App Store app: VECTOR serves it to your phone itself, and you keep it on your Home
Screen like any other app. That means it's free, needs no Apple account, and works on iPhone and
Android.

## Set it up (one minute)

1. On your computer, press **Ctrl+Shift+Space** and type **`/phone`** (or right-click the VECTOR
   tray icon → **Use from your phone...**; on a Mac, the VECTOR menu).
2. A QR code appears. On your phone, open the **Camera**, point it at the code and tap the link.
   Your phone must be on the **same Wi-Fi** as the computer.
   - Windows may ask about the **firewall**: click **Allow**.
   - macOS may ask to **accept incoming connections**: click **Allow**.
3. Keep it:
   - **iPhone:** tap **Share** (the square with an arrow) → **Add to Home Screen** → **Add**.
   - **Android:** tap the **⋮** menu → **Add to Home screen**.

Now **VECTOR** is on your Home Screen. Open it any time VECTOR is running on your computer.

## Using it

| | |
|---|---|
| **See the screen** | The top of the app shows your computer's screen, live. The blue ring is the mouse. |
| **Click** | Tap anywhere on the picture. Tap twice quickly to double-click. |
| **Right-click** | Hold your finger down for half a second. |
| **Scroll** | Drag up or down on the picture. |
| **Look without clicking** | Tap **👁 View**, so taps don't click anything. |
| **Type on the computer** | Tap **⌨ Type**, write your text, then **Type** (or **Type + Enter**). |
| **Keys** | **Esc**, **Enter**, **⌫**, **Tab**, arrows, play/pause and volume, in the row under the picture (swipe it sideways for more). |
| **Bigger picture** | Turn your phone sideways, or tap **⤢ Big**. |
| **Ask VECTOR** | Type in **Ask VECTOR to do something...** at the bottom and tap the arrow. To talk instead, tap the **🎤** on your phone's keyboard. |
| **Allow / Deny** | Risky actions ask on the phone, just like the bar does on the computer. |
| **Stop** | The red **Stop** button stops whatever VECTOR is doing, straight away. |
| **Hear replies** | Tap the speaker next to the text box and your phone reads VECTOR's answers out loud. |

Requests you send from the phone are answered on the phone; your computer's screen isn't covered
by the summon bar. Requests typed on the computer show up on the phone too.

## Turning it off, and safety

- **Off:** type **`/phone off`** in the bar, or click **Turn phone remote off** in the QR window.
  It stays on (even after a restart) until you turn it off.
- **Unpair every phone:** type **`/phone reset`**. A new QR code is made and old links stop
  working.
- **Who can connect:** only a phone with the link from *your* QR code. The link carries a long
  secret key that's checked on every request. Someone guessing keys is locked out after 20 tries.
- **Only your network:** VECTOR refuses anything coming from the internet; only devices on your
  home network (or your own [Tailscale](https://tailscale.com) network) get an answer.
- **Not encrypted:** the connection is plain http on your Wi-Fi, so anyone *on the same Wi-Fi*
  could in principle watch the traffic. Use it on your own home network, not on café or school Wi-Fi.
- **Anyone holding your phone** can use your computer through it, the same as sitting at it. Lock
  your phone, and use `/phone reset` if you lose it.

## Using it away from home

The phone and computer must be on the same network. To use VECTOR Remote from anywhere, install
the free [Tailscale](https://tailscale.com) app on both and sign in with the same account. Then
type `/phone` again: the QR window shows a second link, **"Away from home, with Tailscale on
both"**. Open that link on your phone (Tailscale on) and add it to your Home Screen too. VECTOR
treats Tailscale addresses as your own network; nothing is opened to the internet.

## Troubleshooting

| Problem | Fix |
|---|---|
| "Can't reach your computer" | Is VECTOR running on the computer? Is the phone on the same Wi-Fi (not mobile data)? On Windows, make sure your Wi-Fi is set to a **Private** network (Settings → Network → Wi-Fi → your network). |
| It worked yesterday, not today | The computer's address on your Wi-Fi may have changed. Type `/phone` again, scan the new code and add it to your Home Screen again (delete the old icon). |
| "This link isn't paired" | Someone used `/phone reset`. Scan the new QR code. |
| The screen is black or only shows the wallpaper (Mac) | Allow **Screen & System Audio Recording** for VECTOR in System Settings → Privacy & Security, then reopen VECTOR. |
| Taps don't click (Mac) | Allow **Accessibility** for VECTOR in System Settings → Privacy & Security, then reopen VECTOR. |
| The picture is slow | Move closer to the Wi-Fi router. The picture updates up to about 7 times a second. |
| Port already in use | Another copy of VECTOR is running. Quit it (tray icon → Quit), then type `/phone`. |
