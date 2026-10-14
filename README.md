# Tairagram

A small, interactive Instagram terminal reader/downloader for Linux. No command flags needed: choose with arrow keys, **Enter**, or number shortcuts.

**Unofficial project.** Tairagram uses `instagrapi`, which is not affiliated with Instagram. Private APIs and session-cookie logins can fail, require verification, or be rate-limited. Use your own account and respect account access permissions.

## Requirements

- Ubuntu or another Linux desktop, Python **3.10+**, internet access
- A valid Instagram `sessionid` cookie owned by you and accepted by Instagram
- Python `venv` (`sudo apt install python3-venv` on Ubuntu when missing)

## Install

Keep the source in a permanent directory (example: `~/tairagram`) and run:

```bash
cd ~/tairagram
bash install.sh
```

The installer creates a local virtual environment and a launcher in `~/.local/bin/tairagram`. Ensure `~/.local/bin` is in your `$PATH` (log out/in if necessary, or run `export PATH="$HOME/.local/bin:$PATH"`).

Run from **any directory**:

```bash
tairagram
```

After pulling future updates, run `bash install.sh` again to refresh dependencies and the launcher.

## Menu flow

**No session saved:**

```text
TAIRAGRAM
Main menu
  1. Add Instagram session
```

**A session is saved:**

```text
TAIRAGRAM
Main menu
  1. Fetch from an Instagram account
  2. Manage session
```

**Manage session** contains **Replace Instagram session**, **Show session status**, **Remove saved session**, and **Back**. A saved session means one exists on disk, not that Instagram still accepts it.

**Fetch from an Instagram account** asks for a username (or recent username). Its menu also has **Open downloads folder** and **Back**. Then choose profile, posts, Reels, Stories, highlights, followers, following, or everything; select the last 5, 10, 20, 50, a custom number, or all available items. You can choose to download media or only save JSON metadata.

Press **Ctrl+C** to quit (or cancel a terminal prompt).

## File output

Each fetch saves files beside the Tairagram source code, organized by username, local date of download, and category:

```text
tairagram/
├── tairagram.py
├── install.sh
└── tairagram_downloads/
    └── um6p_cultur.ed/
        └── 2026-10-14/
            ├── profile/
            │   ├── profile.json
            │   └── profile-picture.jpg
            ├── posts/
            │   ├── items.json
            │   └── ...jpg / ...mp4
            ├── stories/
            │   ├── items.json
            │   └── ...jpg / ...mp4
            ├── reels/
            ├── highlights/
            ├── followers/
            ├── following/
            └── report.json
```

Fetching the same category twice on the same day may overwrite files with the same filenames.

## Authentication and safety

1. Sign in to Instagram using a browser you trust.
2. In browser developer tools, find the `sessionid` cookie for **your account**.
3. Select **Add Instagram session**. Paste it at the hidden prompt. It is not shown on screen or passed as a command-line argument.
4. On success, the `instagrapi` session is stored under `~/.local/share/tairagram/session.json`, using permissions `0600` in a private directory.

Do not publish cookies, session files, logins, or screenshots showing their values. The saved session is highly sensitive. Never commit downloads if they contain content you don't want to publish.

Access to Stories may register a view; access to private profiles requires authorization from Instagram. Downloads and follower lists may fail due to upstream restrictions. Avoid repeatedly retrying after rate limits.

## Run tests (offline; no Instagram access)

```bash
python3 -m unittest discover -s tests -v
```

## License

MIT; see `LICENSE`.
