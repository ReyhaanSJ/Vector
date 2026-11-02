# Security Policy

> VECTOR is a **pre-release** and is still being tested. Thanks for helping keep it safe!

## Supported Versions

Only the newest version of VECTOR gets security fixes. To update, open the tray menu and click **Update**, or run `vector --update`.

| Version | Supported          |
| ------- | ------------------ |
| 0.4.x   | :white_check_mark: |
| < 0.4   | :x:                |

## Reporting a Vulnerability

**Please don't report security problems in a public issue.** Report them privately instead:

1. Go to the **Security** tab of this repository.
2. Click **Report a vulnerability**.
3. Describe the problem, how to reproduce it, and which VECTOR version you used.

**What to expect:**

- You'll get a reply within **7 days**.
- If the report is accepted, a fix is released as soon as possible and you'll be credited, unless you'd rather stay anonymous.
- If it's declined, you'll get an explanation of why.

## What counts as a security issue

VECTOR can control your computer, so these matter most:

- VECTOR runs a risky action (deleting files, running commands, shutting down) **without asking you first**
- VECTOR looks at your screen without your permission
- Your API keys or personal files get exposed or sent somewhere they shouldn't go
- A web page or file tricks VECTOR into doing something you didn't ask for (prompt injection)
- The installer or updater downloads or runs something it shouldn't

## Keeping yourself safe

- **Never share your API key** in issues, screenshots or chats.
- Keep **"ask before risky actions"** turned on (it's on by default).
- Only install VECTOR from this repository's **Releases** page.
