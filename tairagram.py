#!/usr/bin/env python3
"""Tairagram: interactive Instagram reader/downloader (instagrapi).

Install with install.sh, then launch by typing `tairagram` anywhere.
Media and JSON output live beside this script, under tairagram_downloads/.
Instagram is an unofficial dependency: sessions and retrieval may fail.
"""

from __future__ import annotations

from datetime import datetime
from getpass import getpass
from html import unescape
import json
import os
from pathlib import Path
import re
import shutil
import sys
from urllib.request import Request, urlopen

APP_DIR = Path(__file__).resolve().parent
DOWNLOADS = APP_DIR / 'tairagram_downloads'
DATA_DIR = Path.home() / '.local' / 'share' / 'tairagram'
SESSION = DATA_DIR / 'session.json'
RECENTS = DATA_DIR / 'recent.json'
SECTIONS = ('profile', 'posts', 'reels', 'stories', 'highlights', 'followers', 'following')
LIMITED = {'posts', 'reels', 'stories', 'highlights', 'followers', 'following'}
BASENAME_PATTERN = re.compile(r'[a-zA-Z0-9_.]{1,30}\Z')

# Match the green brand accent across all questionary prompts.
GREEN = '#22C55E'


def menu_style():
    import questionary
    return questionary.Style([
        ('qmark', f'fg:{GREEN} bold'),
        ('question', 'bold'),
        ('answer', f'fg:{GREEN} bold'),
        ('pointer', f'fg:{GREEN} bold'),
        ('highlighted', f'fg:{GREEN} bold'),
        ('selected', f'fg:{GREEN}'),
        ('instruction', 'fg:#8B949E'),
        ('separator', 'fg:#6B7280'),
    ])


def green(text: str) -> str:
    if sys.stdout.isatty() and 'NO_COLOR' not in os.environ:
        return f'\033[92m{text}\033[0m'
    return text


def has_session() -> bool:
    # The existence of a session is not proof Instagram still accepts it.
    return SESSION.is_file()


def main_menu_options() -> list[tuple[str, str]]:
    if not has_session():
        return [('Add Instagram session', 'login')]
    return [
        ('Fetch from an Instagram account', 'fetch'),
        ('Manage session', 'manage'),
    ]


def ensure_private_dir(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)


def choice(title: str, options: list[tuple[str, str]]) -> str | None:
    """Choose with arrow keys+Enter, or keyboard shortcuts (1,2,...)."""
    import questionary
    return questionary.select(
        title,
        choices=[questionary.Choice(label, value=value) for label, value in options],
        use_arrow_keys=True, use_shortcuts=True, use_jk_keys=False,
        instruction='(arrows + Enter, or number keys; Ctrl+C to quit)',
        style=menu_style(),
    ).ask()


def ask_text(prompt: str, default: str = '') -> str | None:
    import questionary
    return questionary.text(prompt, default=default, style=menu_style()).ask()


def confirm(prompt: str, default: bool = False) -> bool:
    import questionary
    result = questionary.confirm(prompt, default=default, style=menu_style()).ask()
    return bool(result)


def normalize_username(value: str) -> str:
    value = value.strip().lstrip('@').strip().rstrip('/')
    if value.startswith(('https://www.instagram.com/', 'https://instagram.com/')):
        value = value.split('instagram.com/', 1)[-1].split('/', 1)[0]
    if not BASENAME_PATTERN.fullmatch(value):
        raise ValueError('Invalid username. Type @name, name, or an Instagram profile URL.')
    return value.lower()


def recent_usernames() -> list[str]:
    try:
        data = json.loads(RECENTS.read_text(encoding='utf-8'))
        if isinstance(data, list):
            return [x for x in data if isinstance(x, str) and BASENAME_PATTERN.fullmatch(x)][:10]
    except (OSError, ValueError, TypeError):
        pass
    return []


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    try:
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def remember_username(username: str) -> None:
    ensure_private_dir(DATA_DIR)
    saved = [username] + [u for u in recent_usernames() if u != username]
    write_json(RECENTS, saved[:10])
    RECENTS.chmod(0o600)


def choose_account() -> str | None:
    recent = recent_usernames()
    choices = [('Type a new username', 'new')] + [(f'@{u}', u) for u in recent[:8]] + [
        ('Open downloads folder', 'downloads'), ('Back', 'back'),
    ]
    answer = choice('Which Instagram account?', choices)
    if answer is None or answer == 'back':
        return None
    if answer == 'downloads':
        open_downloads_folder()
        return None
    if answer == 'new':
        typed = ask_text('Instagram username or profile URL:')
        if typed is None:
            return None
        answer = normalize_username(typed)
    return normalize_username(answer)


def choose_sections() -> tuple[str, ...] | None:
    entries = [
        ('Profile, bio, follower counts and profile picture', 'profile'),
        ('Posts (photos, videos, carousels)', 'posts'),
        ('Reels', 'reels'),
        ('Current Stories (usually last 24 hours)', 'stories'),
        ('Highlights', 'highlights'),
        ('Follower usernames', 'followers'),
        ('Following usernames', 'following'),
        ('Everything (all seven categories)', 'all'),
        ('Back', 'back'),
    ]
    answer = choice('What do you want to fetch?', entries)
    if not answer or answer == 'back':
        return None
    if answer == 'all':
        return SECTIONS
    return (answer,)


def choose_limit() -> int | None | str:
    answer = choice('How many items per category?', [
        ('Latest 5', '5'), ('Latest 10', '10'), ('Latest 20', '20'),
        ('Latest 50', '50'), ('Choose a number...', 'custom'),
        ('ALL available (can be slow / rate-limited)', 'all'), ('Back', 'back'),
    ])
    if answer is None or answer == 'back':
        return 'back'
    if answer == 'custom':
        raw = ask_text('How many items? (positive number)')
        if raw is None:
            return 'back'
        if not raw.isdecimal() or int(raw) < 1:
            raise ValueError('Enter a positive number.')
        return int(raw)
    if answer == 'all':
        if not confirm('Fetch ALL available items? This can take a long time and trigger rate limits.'):
            return 'back'
        return None
    return int(answer)


def create_client():
    try:
        from instagrapi import Client
    except ImportError as exc:
        raise RuntimeError('instagrapi not installed. Re-run install.sh.') from exc
    client = Client()
    client.request_timeout = 20
    return client


def save_session(client) -> None:
    ensure_private_dir(DATA_DIR)
    temporary = SESSION.with_name('session.tmp.json')
    try:
        old_umask = os.umask(0o077)
        try:
            client.dump_settings(str(temporary))
        finally:
            os.umask(old_umask)
        temporary.chmod(0o600)
        temporary.replace(SESSION)
    finally:
        temporary.unlink(missing_ok=True)


def login_sessionid() -> bool:
    print('\nPaste your OWN Instagram sessionid cookie (hidden input).')
    print('Keep it private; it can grant access to your account.')
    token = getpass('sessionid: ').strip()
    if not token or any(c.isspace() for c in token):
        print('Invalid/empty sessionid.')
        return False
    client = create_client()
    try:
        ok = client.login_by_sessionid(token)
    except Exception as exc:
        print(f'Instagram refused this login ({type(exc).__name__}).')
        return False
    if not ok:
        print('Instagram did not accept that sessionid.')
        return False
    save_session(client)
    print('Session saved privately. No password needed for the next run.')
    return True


def authenticated_client():
    if not SESSION.is_file():
        raise RuntimeError('No saved session. Select Add Instagram session.')
    client = create_client()
    client.load_settings(str(SESSION))
    return client


def serial(value):
    if value is None:
        return None
    return value.isoformat() if isinstance(value, datetime) else str(value)


def attr(obj, field: str, default=None):
    return getattr(obj, field, default)


def profile_record(user) -> dict:
    return {
        'username': attr(user, 'username'), 'name': attr(user, 'full_name'),
        'biography': attr(user, 'biography'),
        'followers_count': attr(user, 'follower_count'),
        'following_count': attr(user, 'following_count'),
        'posts_count': attr(user, 'media_count'),
        'is_private': attr(user, 'is_private'),
        'profile_picture_url': serial(attr(user, 'profile_pic_url_hd') or attr(user, 'profile_pic_url')),
        'website': serial(attr(user, 'external_url')),
    }


def media_record(media) -> dict:
    code = serial(attr(media, 'code'))
    return {
        'id': serial(attr(media, 'pk')),
        'date': serial(attr(media, 'taken_at')),
        'caption': attr(media, 'caption_text', '') or '',
        'media_type': attr(media, 'media_type'),
        'likes': attr(media, 'like_count'),
        'comments': attr(media, 'comment_count'),
        'url': f'https://www.instagram.com/{"reel" if attr(media, "product_type") == "clips" else "p"}/{code}/' if code else None,
        'thumbnail': serial(attr(media, 'thumbnail_url')),
    }


def story_record(story, username: str) -> dict:
    pk = serial(attr(story, 'pk'))
    return {
        'id': pk, 'date': serial(attr(story, 'taken_at')),
        'type': attr(story, 'media_type'),
        'url': f'https://www.instagram.com/stories/{username}/{pk}/' if pk else None,
        'thumbnail': serial(attr(story, 'thumbnail_url')),
        'video_url': serial(attr(story, 'video_url')),
    }


def highlight_record(h) -> dict:
    pk = serial(attr(h, 'pk'))
    return {
        'id': pk, 'title': attr(h, 'title'),
        'cover_url': serial(attr(h, 'cover_url')),
        'url': f'https://www.instagram.com/stories/highlights/{pk}/' if pk else None,
    }


def download_picture(url: str | None, folder: Path):
    if not url:
        return
    folder.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urlopen(req, timeout=20) as response:
        content = response.read(12 * 1024 * 1024 + 1)
        if len(content) > 12 * 1024 * 1024:
            raise ValueError('Profile picture exceeds 12 MB.')
        typ = response.headers.get('Content-Type', '')
    ext = '.png' if 'png' in typ else '.jpg'
    (folder / ('profile-picture' + ext)).write_bytes(content)


def save_media(client, obj, kind: str, folder: Path) -> None:
    pk = attr(obj, 'pk')
    folder.mkdir(parents=True, exist_ok=True)
    if kind == 'stories':
        client.story_download(pk, folder=folder)
    elif kind == 'reels':
        client.video_download(pk, folder=folder)
    elif attr(obj, 'media_type') == 8:
        client.album_download(pk, folder=folder)
    elif attr(obj, 'media_type') == 2:
        client.video_download(pk, folder=folder)
    else:
        client.photo_download(pk, folder=folder)


def safe_name(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_.-]', '_', name)[:45].strip('._') or 'unnamed'


def print_preview(name: str, items) -> None:
    print(f'  {len(items)} {name} retrieved.')
    for item in list(items)[:5]:
        title = item.get('username') or item.get('title') or item.get('date') or item.get('id')
        caption = re.sub(r'\s+', ' ', unescape(str(item.get('caption', '') or '')))
        print(f'   - {title}' + (f' — {caption[:100]}' if caption else ''))
    if len(items) > 5:
        print(f'   ... {len(items)-5} more saved to JSON')


def is_access_block(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    return any(s in name for s in (
        'loginrequired', 'challengerequired', 'feedbackrequired',
        'ratelimit', 'throttled', 'pleasewait', 'sentryblock',
    ))


def fetch_one_section(client, section: str, uid, user, username: str,
                      limit: int | None, save_downloads: bool, base: Path):
    folder = base / section
    folder.mkdir(parents=True, exist_ok=True)
    if section == 'profile':
        data = profile_record(user)
        write_json(folder / 'profile.json', data)
        print(f"  @{data['username']} — {data.get('followers_count')} followers; {data.get('following_count')} following")
        if save_downloads:
            try:
                download_picture(data['profile_picture_url'], folder)
            except Exception as exc:
                print(f'  Profile picture unavailable ({type(exc).__name__}).')
        return 1

    amount = 0 if limit is None else limit  # 0 is instagrapi's 'all' for list APIs
    if section == 'posts':
        objects = client.user_medias(uid, amount=amount)
        data = [media_record(o) for o in objects]
    elif section == 'reels':
        objects = client.user_clips(uid, amount=amount)
        data = [media_record(o) for o in objects]
    elif section == 'stories':
        objects = client.user_stories(uid, amount=limit)
        data = [story_record(o, username) for o in objects]
    elif section == 'highlights':
        objects = client.user_highlights(uid, amount=amount)
        data = [highlight_record(o) for o in objects]
    elif section in ('followers', 'following'):
        fn = client.user_followers if section == 'followers' else client.user_following
        persons = fn(uid, amount=amount)
        data = [
            {'username': attr(v, 'username'), 'name': attr(v, 'full_name')}
            for v in persons.values()
        ]
        objects = []
    else:
        raise ValueError('Unknown section: ' + section)

    write_json(folder / 'items.json', data)
    print_preview(section, data)

    if save_downloads and section in ('posts', 'reels', 'stories'):
        failures = 0
        for i, obj in enumerate(objects, 1):
            print(f'  Downloading {section} {i}/{len(objects)}...', end='\r', flush=True)
            try:
                save_media(client, obj, section, folder)
            except Exception as exc:
                failures += 1
                print(f'\n  Media {i} could not be downloaded ({type(exc).__name__}).')
                if is_access_block(exc):
                    raise
        print(f'  Media downloads finished: {len(objects)-failures}/{len(objects)} succeeded.    ')
    elif save_downloads and section == 'highlights':
        for i, h in enumerate(objects, 1):
            hpk = attr(h, 'pk')
            title = safe_name(str(attr(h, 'title', '') or 'highlight'))
            hfolder = folder / f'{hpk}_{title}'
            hfolder.mkdir(parents=True, exist_ok=True)
            print(f'  Highlight {i}/{len(objects)}: {title}')
            try:
                detail = client.highlight_info(hpk)
                stories = list(attr(detail, 'stories', []) or [])
                write_json(hfolder / 'stories.json', [story_record(s, username) for s in stories])
                for story in stories:
                    try:
                        save_media(client, story, 'stories', hfolder)
                    except Exception as exc:
                        print(f'   Highlight item skipped ({type(exc).__name__}).')
                        if is_access_block(exc):
                            raise
            except Exception as exc:
                print(f'   Highlight unavailable ({type(exc).__name__}).')
                if is_access_block(exc):
                    raise
    return len(data)


def fetch_account(client, username: str, sections: tuple[str, ...],
                  limit: int | None, download: bool) -> Path:
    now = datetime.now().astimezone()
    root = DOWNLOADS / username / now.strftime('%Y-%m-%d')
    root.mkdir(parents=True, exist_ok=True)
    print(f'\nFetching @{username} ...')
    print(f'Saving in: {root}')
    user = client.user_info_by_username(username)
    uid = str(user.pk)
    report = {
        'username': username, 'checked_at': now.isoformat(),
        'limit': 'all' if limit is None else limit,
        'download_media': download,
        'results': {}, 'errors': {},
    }
    for section in sections:
        print(f'\n[{section.upper()}]')
        try:
            count = fetch_one_section(client, section, uid, user, username, limit, download, root)
            report['results'][section] = count
        except KeyboardInterrupt:
            report['errors'][section] = 'Interrupted by user'
            break
        except Exception as exc:
            # Do not print exception details: some API errors can include sensitive URLs or cookies.
            reason = type(exc).__name__
            report['errors'][section] = reason
            print(f'  Failed: {reason} (Instagram may block this request).')
            if is_access_block(exc):
                print('  Stopping further requests to avoid repeated login/rate-limit errors.')
                break
        finally:
            write_json(root / 'report.json', report)
    remember_username(username)
    print(f'\nFinished. Files: {root}')
    if report['errors']:
        print('Some categories failed. Check report.json for a summary.')
    return root


def run_fetch_menu() -> None:
    username = choose_account()
    if not username:
        return
    sections = choose_sections()
    if not sections:
        return
    limit = 5
    if any(s in LIMITED for s in sections):
        limit = choose_limit()
        if limit == 'back':
            return
    need_media = any(s in sections for s in ('posts', 'reels', 'stories', 'highlights', 'profile'))
    download = confirm('Download photos/videos as well as metadata?', default=True) if need_media else False
    if len(sections) > 1 and not confirm(
        'Everything includes follower/following lists and may make many API requests. Continue?'
    ):
        return
    print(f'\n@{username} | {", ".join(sections)} | limit: {limit if limit is not None else "ALL"}')
    if not confirm('Start fetching now?', default=True):
        return
    try:
        client = authenticated_client()
        fetch_account(client, username, sections, limit, download)
    except Exception as exc:
        print(f'\nRequest could not complete: {type(exc).__name__}.')
        print('Check session validity, Instagram limits, and your internet connection.')


def open_downloads_folder() -> None:
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    print('Downloads:', DOWNLOADS)
    if shutil.which('xdg-open'):
        import subprocess
        subprocess.Popen(
            ['xdg-open', str(DOWNLOADS)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )


def manage_session() -> None:
    while has_session():
        answer = choice('Manage session', [
            ('Replace Instagram session', 'replace'),
            ('Show session status', 'status'),
            ('Remove saved session', 'remove'),
            ('Back', 'back'),
        ])
        if answer is None or answer == 'back':
            return
        if answer == 'replace':
            login_sessionid()  # A rejected token leaves the prior session intact.
        elif answer == 'status':
            print('A saved session is available (validity is checked when fetching).')
            print('Session file:', SESSION)
        elif answer == 'remove':
            if confirm('Remove the saved Instagram session?'):
                SESSION.unlink(missing_ok=True)
                print('Saved session removed.')
                return


def main() -> int:
    try:
        import questionary  # noqa: F401
    except ImportError:
        print('Missing menu dependency. Run install.sh to install requirements.')
        return 1
    print('\n' + green('━' * 46))
    print('  ' + green('TAIRAGRAM') + '  |  Instagram terminal reader')
    print('  Use arrow keys / numbers to navigate')
    print(green('━' * 46))
    while True:
        answer = choice('Main menu', main_menu_options())
        if answer is None:
            return 0
        if answer == 'fetch':
            try:
                run_fetch_menu()
            except (ValueError, RuntimeError) as exc:
                print(f'\n{exc}')
        elif answer == 'login':
            login_sessionid()
        elif answer == 'manage':
            manage_session()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print('\nCancelled.')
        raise SystemExit(130)
