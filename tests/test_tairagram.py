"""Offline smoke tests; no Instagram requests."""
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('tairagram', Path(__file__).resolve().parents[1] / 'tairagram.py')
ig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ig)


class FakeClient:
    def user_info_by_username(self, username):
        return NS(pk='1234', username=username, full_name='Campus', biography='events', follower_count=90,
                  following_count=11, media_count=4, is_private=False, profile_pic_url=None,
                  profile_pic_url_hd=None, external_url=None)

    def user_medias(self, uid, amount):
        return [NS(pk='100', code='abc', taken_at=None, caption_text='Campus event!', media_type=1,
                   like_count=5, comment_count=1, thumbnail_url=None)]

    def user_clips(self, uid, amount):
        return [NS(pk='101', code='def', taken_at=None, caption_text='Music Reel', media_type=2,
                   product_type='clips', like_count=9, comment_count=2, thumbnail_url=None)]

    def user_stories(self, uid, amount):
        return [NS(pk='102', taken_at=None, media_type=1, thumbnail_url=None, video_url=None)]

    def user_highlights(self, uid, amount):
        return [NS(pk='103', title='Events!', cover_url=None)]

    def user_followers(self, uid, amount):
        return {'10':NS(username='follower', full_name='Person')}

    def user_following(self, uid, amount):
        return {'11':NS(username='followed', full_name='Person2')}

    def highlight_info(self, pk):
        return NS(stories=[NS(pk='200', taken_at=None, media_type=1, thumbnail_url=None, video_url=None)])

    def photo_download(self, pk, folder):
        (folder / f'{pk}.jpg').write_bytes(b'fakeimage')

    def video_download(self, pk, folder):
        (folder / f'{pk}.mp4').write_bytes(b'fakevideo')

    def story_download(self, pk, folder):
        (folder / f'{pk}.jpg').write_bytes(b'fakeimage')


class MenuTests(unittest.TestCase):
    def test_only_add_session_without_saved_session(self):
        with TemporaryDirectory() as td:
            with patch.object(ig, 'SESSION', Path(td) / 'missing.json'):
                self.assertEqual(ig.main_menu_options(), [('Add Instagram session', 'login')])

    def test_exactly_two_main_items_with_saved_session(self):
        with TemporaryDirectory() as td:
            session = Path(td) / 'session.json'
            session.write_text('{}')
            with patch.object(ig, 'SESSION', session):
                self.assertEqual(ig.main_menu_options(), [
                    ('Fetch from an Instagram account', 'fetch'),
                    ('Manage session', 'manage'),
                ])

    def test_manage_session_remove_returns_to_add_session(self):
        with TemporaryDirectory() as td:
            session = Path(td) / 'session.json'
            session.write_text('{}')
            with patch.object(ig, 'SESSION', session), \
                 patch.object(ig, 'choice', return_value='remove'), \
                 patch.object(ig, 'confirm', return_value=True):
                ig.manage_session()
                self.assertEqual(ig.main_menu_options(), [('Add Instagram session', 'login')])

    def test_downloads_entry_is_not_on_main_menu(self):
        with TemporaryDirectory() as td:
            session = Path(td) / 'session.json'
            session.write_text('{}')
            with patch.object(ig, 'SESSION', session):
                self.assertFalse(any(value == 'downloads' for _, value in ig.main_menu_options()))


class TairagramTests(unittest.TestCase):
    def test_usernames(self):
        self.assertEqual(ig.normalize_username(' https://www.instagram.com/um6p_cultur.ed/ '), 'um6p_cultur.ed')
        self.assertEqual(ig.normalize_username('@LEET_MUSIC'), 'leet_music')
        for invalid in ['../other', 'name/subfolder', '', 'bad name', 'https://evil.com/username']:
            with self.assertRaises(ValueError, msg=invalid):
                ig.normalize_username(invalid)

    def test_all_sections_output(self):
        with TemporaryDirectory() as td:
            old_downloads, old_data, old_recents = ig.DOWNLOADS, ig.DATA_DIR, ig.RECENTS
            try:
                ig.DOWNLOADS = Path(td) / 'tairagram_downloads'
                ig.DATA_DIR = Path(td) / 'secure'
                ig.RECENTS = ig.DATA_DIR / 'recent.json'
                out = ig.fetch_account(FakeClient(), 'um6p_cultur.ed', ig.SECTIONS, 5, False)
                self.assertTrue((out/'profile'/'profile.json').exists())
                self.assertTrue((out/'posts'/'items.json').exists())
                self.assertTrue((out/'reels'/'items.json').exists())
                self.assertTrue((out/'stories'/'items.json').exists())
                self.assertTrue((out/'highlights'/'items.json').exists())
                self.assertTrue((out/'followers'/'items.json').exists())
                self.assertTrue((out/'following'/'items.json').exists())
                report = json.loads((out/'report.json').read_text())
                self.assertEqual(report['results']['posts'], 1)
                self.assertEqual(report['errors'], {})
                self.assertEqual(ig.recent_usernames(), ['um6p_cultur.ed'])
                self.assertEqual(out.relative_to(ig.DOWNLOADS).parts[0], 'um6p_cultur.ed')
            finally:
                ig.DOWNLOADS, ig.DATA_DIR, ig.RECENTS = old_downloads, old_data, old_recents

    def test_media_downloads_and_highlights(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            cli = FakeClient()
            user = cli.user_info_by_username('campus')
            for section in ('posts', 'reels', 'stories', 'highlights'):
                n = ig.fetch_one_section(cli, section, '1234', user, 'campus', 5, True, base)
                self.assertEqual(n, 1)
            self.assertTrue((base/'posts'/'100.jpg').exists())
            self.assertTrue((base/'reels'/'101.mp4').exists())
            self.assertTrue((base/'stories'/'102.jpg').exists())
            self.assertTrue((base/'highlights'/'103_Events'/'200.jpg').exists())


if __name__ == '__main__':
    unittest.main()
