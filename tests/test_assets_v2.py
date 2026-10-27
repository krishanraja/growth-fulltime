"""The renderer widened for every brand channel and for Windows FFmpeg builds:
creative ID codes, the CHANNEL hold for the creative's own platform, the
1080x1920 master, master_id, and explicit font files. Synthetic media only,
made with local FFmpeg in a temporary folder; nothing reaches the network."""
import copy
import datetime as dt
import glob
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

import growth
from engine import assets
from engine.assets import checked_segments, fonts, probe, render, render_holds, render_platform, sha, video_filters
from engine.records import atomic_json

CODES = {'TT': 'tiktok', 'YT': 'youtube', 'IG': 'instagram', 'TH': 'threads', 'FB': 'facebook',
         'WC': 'whatsapp_channel', 'X': 'x', 'WEB': 'site'}
# The filter graph the renderer used before this change, kept here to prove the default is unchanged.
OLD_FILTERS = ('[0:v]drawbox=x=50:y=240:w=620:h=360:color=0x1b3037:t=fill,'
               'drawbox=x=50:y=240:w=620:h=5:color=0x98e76a:t=fill,'
               'drawtext=textfile=brand.txt:expansion=none:fontcolor=0x98e76a:fontsize=24:x=(w-tw)/2:y=70,'
               'drawtext=textfile=heading.txt:expansion=none:fontcolor=white:fontsize=36:x=(w-tw)/2:y=150,'
               'drawtext=textfile=match.txt:expansion=none:fontcolor=white:fontsize=34:x=(w-tw)/2:y=300:line_spacing=12,'
               'drawtext=textfile=score.txt:expansion=none:fontcolor=white:fontsize=88:x=(w-tw)/2:y=450,'
               'drawtext=textfile=label.txt:expansion=none:fontcolor=white:fontsize=22:x=(w-tw)/2:y=1070,'
               'subtitles=caption.ass[v]')
NO_FONT_ENV = {k: v for k, v in os.environ.items() if k not in ('FULLTIME_FONT_FILE', 'FULLTIME_FONTS_DIR')}


def system_font():
    """A real TrueType font on this machine, for the render that names one."""
    for pattern in ('/usr/share/fonts/**/DejaVuSans.ttf', '/usr/share/fonts/**/*.ttf', '/Library/Fonts/*.ttf',
                    'C:/Windows/Fonts/arial.ttf'):
        found = sorted(glob.glob(pattern, recursive=True))
        if found:
            return found[0]
    return None


def identity(platform, host):
    return {'verified': True, 'platform': platform, 'account_scope': 'brand',
            'source_url': f'https://{host}/example-fixture', 'verified_at': dt.datetime.now(dt.timezone.utc).isoformat()}


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.state = {'sha': 'a' * 40, 'rail': [{'drop': 'drop1', 'pundits': ['zen', 'gaffer'], 'fill': 2,
                                                'home': 'Fixture Home', 'away': 'Fixture Away', 'score': [1, 0]}],
                     'rulings': {}, 'synced_at': dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()}
        cls.api = types.SimpleNamespace(LOCAL=str(cls.root), SITE=growth.SITE, PUNDITS=growth.PUNDITS,
                                        RAIL_MIN=4, CREATIVE_ID=growth.CREATIVE_ID,
                                        tracked=growth.tracked, problems=growth.problems,
                                        load_state=lambda: copy.deepcopy(cls.state))
        cls.sources = []
        cls.media = bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))
        for number, pundit in enumerate(('zen', 'gaffer')):
            folder = cls.root / 'assets' / 'drop1' / pundit
            folder.mkdir(parents=True)
            audio, cover = folder / 'audio.wav', folder / 'cover.png'
            if cls.media:
                subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
                                f'sine=frequency={330 + number * 100}:duration=6', '-c:a', 'pcm_s16le', str(audio)], check=True)
                subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
                                'color=c=0x122126:s=640x336', '-frames:v', '1', '-threads', '1', str(cover)], check=True)
            else:
                audio.write_bytes(b'synthetic'); cover.write_bytes(b'synthetic')
            source = {'schema_version': 1, 'drop_id': 'drop1', 'pundit': pundit,
                      'source_url': f'{growth.SITE}/api/public/drops/drop1/variants/{pundit}',
                      'source_sha': 'a' * 40, 'published_at': 'fixture-only',
                      'audio': str(audio), 'cover': str(cover), 'audio_sha256': sha(audio), 'cover_sha256': sha(cover),
                      'duration_seconds': 6, 'transcript': 'QA fixture audio. This is a test clip.'}
            record = folder / 'source.json'
            atomic_json(record, source)
            cls.sources.append(str(record))

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def manifest(self, cid='TT_CLASH_CLIP_C98_H01_V1_20261027', pundits=1, **extra):
        return {'schema_version': 1, 'creative_id': cid, 'drop_id': 'drop1', 'caption_alignment_verified': False,
                'segments': [{'source_record': x, 'start_seconds': 0, 'end_seconds': 3, 'quote': 'QA fixture audio.'}
                             for x in self.sources[:pundits]], **extra}


class ManifestTests(Base):
    def test_every_brand_channel_code_and_web_render(self):
        for code, platform in CODES.items():
            with self.subTest(code=code):
                cid = f'{code}_CLASH_CLIP_C98_H01_V1_20261027'
                self.assertEqual(render_platform(self.api, cid), platform)
                checked_segments(self.api, self.manifest(cid))

    def test_other_codes_are_refused(self):
        for code in ('INV', 'WA', 'EM', 'RD', 'LI', 'HN', 'PH', 'PR', 'CR', 'AD', 'FPL'):
            with self.subTest(code=code), self.assertRaisesRegex(ValueError, 'brand channels'):
                checked_segments(self.api, self.manifest(f'{code}_CLASH_CLIP_C98_H01_V1_20261027'))
        with self.assertRaisesRegex(ValueError, 'stable creative ID'):
            checked_segments(self.api, self.manifest('clip-1'))

    def test_size_master_id_and_fields(self):
        checked_segments(self.api, self.manifest(size='720x1280'))
        checked_segments(self.api, self.manifest(size='1080x1920', master_id='M_20261027_FIXTURE_ZEN'))
        for extra, words in (({'size': '1920x1080'}, 'size must be'), ({'size': 1080}, 'size must be'),
                             ({'master_id': ''}, 'master_id'), ({'master_id': 'has space'}, 'master_id'),
                             ({'master_id': 7}, 'master_id'), ({'channel': 'tiktok'}, 'documented render fields'),
                             ({'fontfile': ''}, 'fontfile must be a path'),
                             ({'fontsdir': str(self.root / 'missing')}, 'existing folder'),
                             ({'fontfile': str(self.root / 'missing.ttf')}, 'existing font file')):
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, words):
                checked_segments(self.api, self.manifest(**extra))

    def test_a_font_path_with_a_quote_is_refused(self):
        folder = self.root / "quote's"
        folder.mkdir(exist_ok=True)
        with self.assertRaisesRegex(ValueError, 'without quotes'):
            fonts({'fontsdir': str(folder)})


class FilterAndFontTests(Base):
    def test_default_filters_are_unchanged(self):
        self.assertEqual(video_filters('720x1280', {}), OLD_FILTERS)

    def test_master_canvas_scales_the_layout(self):
        filters = video_filters('1080x1920', {})
        for part in ('drawbox=x=75:y=360:w=930:h=540', 'fontsize=132', 'y=1605', 'line_spacing=18'):
            self.assertIn(part, filters)

    def test_fonts_reach_drawtext_and_subtitles_with_colons_escaped(self):
        font = {'fontfile': 'C:/Windows/Fonts/fixture.ttf', 'fontsdir': 'C:/Windows/Fonts'}
        filters = video_filters('720x1280', font)
        self.assertEqual(filters.count(r":fontfile='C\:/Windows/Fonts/fixture.ttf'"), 5)
        self.assertTrue(filters.endswith(r"subtitles=caption.ass:fontsdir='C\:/Windows/Fonts'[v]"))

    def test_fonts_come_from_the_manifest_or_else_the_environment(self):
        folder = self.root / 'env fonts'
        folder.mkdir(exist_ok=True)
        face = folder / 'face.ttf'
        face.write_bytes(b'synthetic')
        other = self.root / 'manifest.ttf'
        other.write_bytes(b'synthetic')
        with patch.dict(os.environ, NO_FONT_ENV, clear=True):
            self.assertEqual(fonts({}), {})
        with patch.dict(os.environ, {**NO_FONT_ENV, 'FULLTIME_FONT_FILE': str(face), 'FULLTIME_FONTS_DIR': str(folder)},
                        clear=True):
            self.assertEqual(fonts({}), {'fontfile': face.resolve().as_posix(), 'fontsdir': folder.resolve().as_posix()})
            self.assertEqual(fonts({'fontfile': str(other)})['fontfile'], other.resolve().as_posix())
        with patch.dict(os.environ, {**NO_FONT_ENV, 'FULLTIME_FONT_FILE': str(self.root / 'gone.ttf')}, clear=True):
            with self.assertRaisesRegex(ValueError, 'existing font file'):
                fonts({})


class HoldTests(Base):
    def holds(self, cid, state, pundits=('zen',), verified=False):
        manifest = {**self.manifest(cid), 'caption_alignment_verified': verified}
        return render_holds(self.api, state, manifest, state['rail'][0], list(pundits))

    def test_channel_is_checked_for_the_creative_platform(self):
        state = {**copy.deepcopy(self.state), 'brand_identities': {'fixture-tiktok': identity('tiktok', 'tiktok.com')}}
        tiktok = {**self.manifest(), 'identity_ref': 'fixture-tiktok'}
        self.assertNotIn('CHANNEL', render_holds(self.api, state, tiktok, state['rail'][0], ['zen']))
        youtube = {**self.manifest('YT_CLASH_SHORT_C98_H01_V1_20261027'), 'identity_ref': 'fixture-tiktok'}
        self.assertIn('CHANNEL', render_holds(self.api, state, youtube, state['rail'][0], ['zen']))
        state['brand_identities']['fixture-threads'] = identity('threads', 'www.threads.net')
        threads = {**self.manifest('TH_CLASH_CLIP_C98_H01_V1_20261027'), 'identity_ref': 'fixture-threads'}
        self.assertNotIn('CHANNEL', render_holds(self.api, state, threads, state['rail'][0], ['zen']))
        web = {**self.manifest('WEB_CLASH_CLIP_C98_H01_V1_20261027'), 'identity_ref': 'fixture-tiktok'}
        self.assertIn('CHANNEL', render_holds(self.api, state, web, state['rail'][0], ['zen']))

    def test_without_organic_the_holds_are_as_before(self):
        self.assertEqual(self.holds('TT_CLASH_CLIP_C98_H01_V1_20261027', self.state),
                         ['APPROVAL', 'RELEASE', 'CHANNEL', 'D1', 'CONSENT', 'RAIL', 'ASSETS'])

    def test_under_organic_a_render_is_a_take(self):
        state = {**copy.deepcopy(self.state), 'rulings': {'ORGANIC': {'in_force': True}, 'D1': {'in_force': True},
                                                          'D7': {'in_force': True}}}
        self.assertEqual(self.holds('TT_CLASH_CLIP_C98_H01_V1_20261027', state, verified=True), ['APPROVAL', 'CHANNEL'])
        self.assertIn('RAIL', self.holds('TT_CLASH_CLIP_C98_H01_V1_20261027', state, pundits=('doomer',)))
        no_consent = {**state, 'rulings': {**state['rulings'], 'D7': {'in_force': False}}}
        self.assertIn('CONSENT', self.holds('TT_CLASH_CLIP_C98_H01_V1_20261027', no_consent))

    def test_under_organic_a_render_from_an_old_sync_is_held_for_rail(self):
        state = {**copy.deepcopy(self.state), 'rulings': {'ORGANIC': {'in_force': True}, 'D1': {'in_force': True},
                                                          'D7': {'in_force': True}}}
        old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=27)).isoformat()
        for synced in (old, None, 'yesterday'):
            with self.subTest(synced=synced):
                self.assertEqual(self.holds('TT_CLASH_CLIP_C98_H01_V1_20261027', {**state, 'synced_at': synced}, verified=True),
                                 ['APPROVAL', 'CHANNEL', 'RAIL'])


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg and FFprobe required')
class RenderTests(Base):
    def run_capturing(self, manifest, env):
        path = self.root / (manifest['creative_id'] + '.json')
        atomic_json(path, manifest)
        calls, real = [], subprocess.run

        def spy(command, *args, **kwargs):
            calls.append(command)
            return real(command, *args, **kwargs)
        with patch.dict(os.environ, env, clear=True), patch.object(assets.subprocess, 'run', spy):
            receipt = render(self.api, path)
        return receipt, [' '.join(map(str, c)) for c in calls if c and c[0] == 'ffmpeg']

    def test_actual_1080x1920_master_with_fonts_and_master_id(self):
        face = system_font()
        if not face:
            self.skipTest('no TrueType font on this machine')
        folder = self.root / 'fonts: windows style, a;b'
        folder.mkdir(exist_ok=True)
        shutil.copy(face, folder / 'Face.ttf')
        manifest = self.manifest(pundits=2, size='1080x1920', master_id='M_20261027_FIXTURE_TWO_MINDS',
                                 fontfile=str(folder / 'Face.ttf'), fontsdir=str(folder))
        receipt, commands = self.run_capturing(manifest, NO_FONT_ENV)
        streams = probe(receipt['video'])['streams']
        video = next(x for x in streams if x['codec_type'] == 'video')
        self.assertEqual((video['width'], video['height']), (1080, 1920))
        self.assertTrue(any(x['codec_type'] == 'audio' for x in streams))
        self.assertEqual((receipt['size'], receipt['width'], receipt['height']), ('1080x1920', 1080, 1920))
        self.assertEqual((receipt['platform'], receipt['master_id']), ('tiktok', 'M_20261027_FIXTURE_TWO_MINDS'))
        self.assertEqual(receipt['fonts'], {'fontfile': (folder / 'Face.ttf').resolve().as_posix(),
                                            'fontsdir': folder.resolve().as_posix()})
        self.assertEqual(receipt['pundits'], ['zen', 'gaffer'])
        self.assertIn('CHANNEL', receipt['holds'])
        self.assertEqual((receipt['publication_status'], receipt['generated_media_calls']), ('private_preview', 0))
        escaped = folder.resolve().as_posix().replace(':', '\\:')
        renders = [c for c in commands if 'drawtext' in c]
        self.assertEqual(len(renders), 2)
        for command in renders:
            self.assertIn('color=c=0x122126:s=1080x1920:r=24', command)
            self.assertIn(f":fontfile='{escaped}/Face.ttf'", command)
            self.assertIn(f"subtitles=caption.ass:fontsdir='{escaped}'", command)
        self.assertTrue(Path(receipt['thumbnail']).exists())
        saved = json.loads(Path(receipt['video']).with_name('render.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['master_id'], 'M_20261027_FIXTURE_TWO_MINDS')
        with patch.dict(os.environ, NO_FONT_ENV, clear=True):
            self.assertTrue(render(self.api, self.root / (manifest['creative_id'] + '.json'))['reused'])

    def test_a_cached_render_carries_todays_holds(self):
        cid = 'TT_CLASH_CLIP_C96_H01_V1_20261027'
        open_state = {**copy.deepcopy(self.state), 'sha': 'b' * 40,
                      'rulings': {'ORGANIC': {'in_force': True}, 'D1': {'in_force': True}, 'D7': {'in_force': True}},
                      'brand_identities': {'fixture-tiktok': identity('tiktok', 'tiktok.com')}}
        manifest = {**self.manifest(cid), 'identity_ref': 'fixture-tiktok', 'caption_alignment_verified': True}
        with patch.object(self.api, 'load_state', lambda: copy.deepcopy(open_state)):
            first, _ = self.run_capturing(manifest, NO_FONT_ENV)
        self.assertEqual((first['holds'], first['source_sha'], first['reused']), (['APPROVAL'], 'b' * 40, False))
        closed = {**copy.deepcopy(self.state), 'sha': 'c' * 40, 'rulings': {'ORGANIC': {'in_force': True},
                                                                         'D1': {'in_force': True}}}
        with patch.object(self.api, 'load_state', lambda: copy.deepcopy(closed)):
            again, commands = self.run_capturing(manifest, NO_FONT_ENV)
        self.assertEqual(commands, [])
        self.assertEqual((again['reused'], again['video_sha256'], again['source_sha']), (True, first['video_sha256'], 'c' * 40))
        self.assertEqual(again['holds'], ['APPROVAL', 'CHANNEL', 'CONSENT'])

    def test_default_render_on_a_new_channel_keeps_720x1280_and_no_font(self):
        manifest = self.manifest('WC_CLASH_CLIP_C97_H01_V1_20261027')
        receipt, commands = self.run_capturing(manifest, NO_FONT_ENV)
        self.assertEqual((receipt['width'], receipt['height'], receipt['size']), (720, 1280, '720x1280'))
        self.assertEqual((receipt['platform'], receipt['master_id'], receipt['fonts']), ('whatsapp_channel', None, None))
        self.assertTrue(all('fontfile' not in c and 'fontsdir' not in c for c in commands))
        self.assertIn(OLD_FILTERS, next(c for c in commands if 'drawtext' in c))
        self.assertIn('utm_source=whatsapp_channel', receipt['landing_url'])


if __name__ == '__main__':
    unittest.main()
