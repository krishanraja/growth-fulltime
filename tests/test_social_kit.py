"""The approved social kit (The Switch, revision 1) and the take_clip it renders.

The lock: spec.md, templates.js and slots.json must match brand/social-kit/LOCK.json, so
any change to the kit fails here until Krish approves a new revision. The copy rules and
where lime may appear. Then the engine's take_clip path: synthetic PNG layers (made with
zlib and struct) and a synthetic FFmpeg tone, composed into a 1080x1920 clip whose first
second is frame 0 and whose progress fill grows. Nothing reaches the network."""
import copy
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import types
import unittest
import zlib

import growth
from engine import assets
from engine.assets import checked_segments, kit_lock, kit_timeline, lf_sha, probe, render, sha
from engine.records import atomic_json

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / 'brand' / 'social-kit'
EM_DASH = chr(0x2014)
BANNED = ('game-changing', 'next-generation', 'must-listen', 'unmissable', 'unbiased', 'seamless',
          'revolutionary', 'AI-powered')
JS_STRING = re.compile(r"'(?:[^'\\\n]|\\.)*'|\"(?:[^\"\\\n]|\\.)*\"|`(?:[^`\\]|\\.)*`", re.S)
MEDIA = bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))

FRAME0 = (63, 96, 124)      # the Reporter's paper
PLATE = (28, 22, 17)        # the ground plate
TRACK = (74, 68, 61)        # the empty progress track
LIME = '#7dfa46'
RECT = {'x': 152, 'y': 1277, 'w': 677, 'h': 10, 'color': LIME}


def text(name):
    return (KIT / name).read_text(encoding='utf-8')


def png(path, colour, box=None, box_colour=None, size=(1080, 1920)):
    """A solid RGB PNG, with an optional filled box, from the standard library alone."""
    w, h = size
    row = bytes(colour) * w
    boxed = row
    if box:
        x, y, bw, bh = box
        boxed = bytes(colour) * x + bytes(box_colour) * bw + bytes(colour) * (w - x - bw)
    raw = b''.join(b'\x00' + (boxed if box and box[1] <= r < box[1] + box[3] else row) for r in range(h))

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                           + chunk(b'IDAT', zlib.compress(raw, 1)) + chunk(b'IEND', b''))


class LockTests(unittest.TestCase):
    def test_the_lock_matches_the_approved_files(self):
        lock = json.loads(text('LOCK.json'))
        self.assertEqual((lock['kit'], lock['revision']), ('The Switch', 1))
        self.assertEqual((lock['approval'], lock['approved_on'], lock['approved_by']), ('I like it. Looks good.', '2026-10-27', 'Krish'))
        self.assertEqual(set(lock['files']), {'spec.md', 'templates.js', 'slots.json'})
        for name, digest in lock['files'].items():
            with self.subTest(name=name):
                self.assertEqual(lf_sha(KIT / name), digest,
                                 f'{name} differs from the approved revision: a change needs Krish to approve a new revision')
        self.assertEqual(kit_lock()['lock_sha256'], lf_sha(KIT / 'LOCK.json'))

    def test_any_change_to_a_locked_file_breaks_the_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ('LOCK.json', 'spec.md', 'templates.js', 'slots.json'):
                shutil.copy(KIT / name, Path(folder) / name)
            kit_lock(folder)
            crlf = Path(folder) / 'spec.md'
            crlf.write_bytes(crlf.read_bytes().replace(b'\n', b'\r\n'))   # a Windows checkout still matches
            kit_lock(folder)
            changed = Path(folder) / 'templates.js'
            changed.write_text(text('templates.js').replace('#3F607C', '#3F607D'), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'templates.js'):
                kit_lock(folder)

    def test_spec_is_at_most_4_kb(self):
        self.assertLessEqual(len((KIT / 'spec.md').read_bytes().replace(b'\r\n', b'\n')), 4 * 1024)

    def test_the_kit_holds_no_binaries_fonts_or_product_source(self):
        for path in KIT.rglob('*'):
            if path.is_file():
                with self.subTest(path=path.name):
                    self.assertIn(path.suffix, ('.md', '.js', '.mjs', '.json'))
        self.assertIn('/local/', (ROOT / '.gitignore').read_text(encoding='utf-8').split())


class CopyTests(unittest.TestCase):
    def strings(self):
        found = [m.group(0)[1:-1] for m in JS_STRING.finditer(text('templates.js'))]
        slots = json.loads(text('slots.json'))

        def walk(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, dict):
                for item in value.values():
                    yield from walk(item)
            elif isinstance(value, list):
                for item in value:
                    yield from walk(item)
        return found + list(walk(slots))

    def test_no_em_dash_or_banned_word_in_the_kit_copy(self):
        strings = self.strings()
        self.assertGreater(len(strings), 50)
        for name in ('templates.js', 'slots.json', 'spec.md', 'render.js', 'take_clip.js', 'board.js',
                     'prepare-assets.mjs', 'README.md'):
            self.assertNotIn(EM_DASH, text(name), name)
        for value in strings:
            for word in BANNED:
                self.assertNotIn(word.lower(), value.lower(), f'banned copy "{word}" in {value[:60]!r}')

    def test_the_offer_and_the_term_appear(self):
        slots = json.loads(text('slots.json'))
        self.assertEqual(slots['cta'], 'Pick your channel. Free pilot beta at fulltime.fm')
        self.assertIn('free pilot beta', ' '.join(self.strings()).lower())
        self.assertIn('AI Pundit', text('templates.js'))
        self.assertNotRegex(text('templates.js'), r'\b(AI pundit|Ai Pundit|ai pundit)')

    def test_the_four_published_matches(self):
        matches = json.loads(text('slots.json'))['matches']
        self.assertEqual(sorted(m['slug'] for m in matches.values()),
                         ['2026-09-19_tottenham-aston-villa', '2026-09-20_manchester-city-sunderland',
                          '2026-10-11_crystal-palace-nottingham-forest', '2026-10-19_tottenham-coventry'])

    def test_lime_only_where_the_spec_names_it(self):
        """Lime is for the mark, play/pause and the progress fill only (spec.md, "Mid frame")."""
        lines = text('templates.js').splitlines()
        start = next(i for i, line in enumerate(lines) if line.startswith('function takeMid('))
        end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith(('function ', '/* ')))
        uses = [(i, line) for i, line in enumerate(lines) if 'lime' in line.lower()]
        self.assertEqual(len(uses), 2)
        for i, line in uses:
            self.assertTrue(start < i < end, 'lime outside the mid frame: ' + line.strip()[:80])
            self.assertTrue('<svg' in line or 'd.progress' in line, 'lime outside the pause glyph and progress fill')
        render_lines = [line for line in text('render.js').splitlines() if 'lime' in line.lower()]
        self.assertEqual(len(render_lines), 1)
        self.assertIn('--lime:oklch(', render_lines[0])
        for line in text('take_clip.js').splitlines():
            if 'lime' in line.lower():
                self.assertIn('fill', line)
        spec = [line for line in text('spec.md').splitlines() if 'lime' in line.lower()]
        self.assertEqual(len(spec), 1)
        self.assertTrue(spec[0].startswith('**Mid frame.**') and 'lime pause + fill' in spec[0])
        for line in text('board.js').splitlines():
            if 'lime' in line.lower():
                self.assertTrue('pause' in line and 'progress' in line, line.strip()[:80])


class Base(unittest.TestCase):
    """A synthetic published edition, its instance and take_clip.js-shaped layers in a temporary local/."""
    CAPTIONS = [{'start': 0.0, 'end': 2.0, 'text': 'QA fixture audio.'},
                {'start': 2.0, 'end': 4.0, 'text': 'This is a test clip.'}]

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.state = {'sha': 'a' * 40, 'rail': [{'drop': 'drop1', 'pundits': ['zen'], 'fill': 1, 'date': '2026-10-19',
                                                'home': 'Fixture Home', 'away': 'Fixture Away', 'score': [3, 1]}],
                     'rulings': {}, 'synced_at': dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()}
        cls.api = types.SimpleNamespace(LOCAL=str(cls.root), SITE=growth.SITE, PUNDITS=growth.PUNDITS,
                                        RAIL_MIN=4, CREATIVE_ID=growth.CREATIVE_ID,
                                        tracked=growth.tracked, problems=growth.problems,
                                        load_state=lambda: copy.deepcopy(cls.state))
        folder = cls.root / 'assets' / 'drop1' / 'zen'
        folder.mkdir(parents=True)
        audio, cover = folder / 'audio.wav', folder / 'cover.png'
        if MEDIA:
            subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
                            'sine=frequency=440:duration=6', '-c:a', 'pcm_s16le', str(audio)], check=True)
        else:
            audio.write_bytes(b'synthetic')
        png(cover, PLATE, size=(64, 64))
        cls.source = folder / 'source.json'
        atomic_json(cls.source, {'schema_version': 1, 'drop_id': 'drop1', 'pundit': 'zen',
                                 'source_url': f'{growth.SITE}/api/public/drops/drop1/variants/zen',
                                 'source_sha': 'a' * 40, 'published_at': 'fixture-only',
                                 'audio': str(audio), 'cover': str(cover), 'audio_sha256': sha(audio),
                                 'cover_sha256': sha(cover), 'duration_seconds': 6,
                                 'transcript': 'QA fixture audio. This is a test clip.'})
        cls.layers = cls.root / 'brand-kit' / 'layers' / 'fixture'
        cls.layers.mkdir(parents=True)
        png(cls.layers / 'frame0.png', FRAME0)
        png(cls.layers / 'plate-001.png', PLATE, (RECT['x'], RECT['y'], RECT['w'], RECT['h']), TRACK)
        png(cls.layers / 'plate-002.png', PLATE, (RECT['x'], RECT['y'], RECT['w'], RECT['h']), TRACK)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.instance_path = self.root / 'fixture-instance.json'
        self.write_instance()
        self.write_layers()

    def write_instance(self, **change):
        instance = {'schema_version': 1, 'pundit': 'zen', 'drop': 'drop1', 'home': 'Fixture Home',
                    'away': 'Fixture Away', 'score': [3, 1], 'date': '2026-10-19', 'shows': ['zen'],
                    'quote': 'QA fixture audio.', 'sample': False, 'captions': copy.deepcopy(self.CAPTIONS),
                    'audio': {'source_record': str(self.source), 'start_seconds': 0, 'end_seconds': 4}}
        instance.update(change)
        self.instance_path.write_text(json.dumps(instance), encoding='utf-8')
        return instance

    def write_layers(self, **change):
        labels = ['CH 1 · AI Pundit', 'Pick your channel.', 'Free pilot beta at fulltime.fm']

        def layer(name, extra=()):
            path = self.layers / name
            return {'file': name, 'bytes': path.stat().st_size, 'sha256': sha(path), 'text': labels + list(extra)}
        instance = json.loads(self.instance_path.read_text(encoding='utf-8'))
        record = {'schema_version': 1, 'kit': 'The Switch', 'revision': 1, 'lock_sha256': kit_lock()['lock_sha256'],
                  'instance': str(self.instance_path), 'instance_sha256': sha(self.instance_path),
                  'size': '1080x1920', 'width': 1080, 'height': 1920, 'time_label': '0:04',
                  'frame0': layer('frame0.png', ['QA fixture audio.']),
                  'plates': [{**layer(f'plate-00{n}.png', [c['text'], 'Made by AI from checked match facts']),
                              'start': c['start'], 'end': c['end'], 'caption': c['text']}
                             for n, c in enumerate(instance['captions'], 1)],
                  'progress': dict(RECT), 'rendered_at': 'fixture'}
        record.update(change)
        atomic_json(self.layers / 'layers.json', record)
        return record

    def manifest(self, cid='TT_PROOF_CLIP_C90_H01_V1_20261027', **change):
        manifest = {'schema_version': 1, 'creative_id': cid, 'drop_id': 'drop1', 'caption_alignment_verified': False,
                    'size': '1080x1920', 'segments': [{'source_record': str(self.source), 'start_seconds': 0,
                                                       'end_seconds': 4, 'quote': 'QA fixture audio. This is a test clip.'}],
                    'layers': str(self.layers), 'instance': str(self.instance_path)}
        manifest.update(change)
        return manifest


class KitManifestTests(Base):
    def refused(self, words, manifest=None):
        with self.assertRaisesRegex(ValueError, words):
            checked_segments(self.api, manifest or self.manifest())

    def test_a_good_kit_manifest_passes_every_check(self):
        segments, match, total = checked_segments(self.api, self.manifest())
        self.assertEqual((len(segments), match['drop'], total), (1, 'drop1', 4))

    def test_the_timeline_holds_frame_0_for_one_second(self):
        self.assertEqual(kit_timeline(self.CAPTIONS, 4), [30, 30, 60])
        self.assertEqual(kit_timeline([{'start': 0, 'end': 4, 'text': 'x'}], 4), [30, 90])
        with self.assertRaisesRegex(ValueError, 'after frame 0'):
            kit_timeline([{'start': 0, 'end': 0.5, 'text': 'x'}, {'start': 0.5, 'end': 4, 'text': 'y'}], 4)

    def test_the_manifest_shape(self):
        self.refused('1080x1920', self.manifest(size='720x1280'))
        bare = self.manifest()
        del bare['size']
        self.refused('1080x1920', bare)
        alone = self.manifest()
        del alone['instance']
        self.refused('both its layers folder and its instance', alone)
        two = self.manifest()
        two['segments'] = two['segments'] * 2
        self.refused('two different AI Pundits', two)

    def test_paths_stay_inside_local(self):
        outside = Path(tempfile.mkdtemp())
        try:
            self.refused('inside local/brand-kit/layers', self.manifest(layers=str(outside)))
            self.refused('inside local/brand-kit/layers', self.manifest(layers=str(self.root / 'brand-kit')))
            shutil.copy(self.instance_path, outside / 'instance.json')
            self.refused('instance must stay inside local', self.manifest(instance=str(outside / 'instance.json')))
        finally:
            shutil.rmtree(outside)

    def test_the_instance_must_be_this_published_edition(self):
        for change, words in (({'pundit': 'gaffer'}, 'this published edition'), ({'score': [1, 3]}, 'this published edition'),
                              ({'home': 'Elsewhere'}, 'this published edition'), ({'date': '2026-10-20'}, 'this published edition'),
                              ({'shows': ['zen', 'gaffer']}, 'shows must be exactly'),
                              ({'audio': {'source_record': str(self.source), 'start_seconds': 1, 'end_seconds': 4}}, 'instance audio'),
                              ({'quote': 'A line nobody said.'}, 'frame 0 quote'),
                              ({'sample': 'yes'}, 'sample true or false'), ({'extra': 1}, 'documented take_clip fields')):
            with self.subTest(change=change):
                self.write_instance(**change)
                self.write_layers()
                self.refused(words)

    def test_captions_are_exact_quotations_of_the_segment(self):
        for captions, words in (([{'start': 0, 'end': 4, 'text': 'QA fixture audio.'}], 'exactly the segment quote'),
                                ([{'start': 0, 'end': 2, 'text': 'QA fixture audio.'}, {'start': 2, 'end': 4, 'text': 'Invented words.'}],
                                 'exact transcript quotation'),
                                ([{'start': 0, 'end': 2, 'text': 'QA fixture audio.'}, {'start': 1.5, 'end': 4, 'text': 'This is a test clip.'}],
                                 'in order'),
                                ([{'start': 0, 'end': 2, 'text': 'QA fixture audio.'}, {'start': 2, 'end': 9, 'text': 'This is a test clip.'}],
                                 'in order'),
                                ([{'start': 0, 'end': 2, 'text': 'QA fixture audio.', 'speaker': 'x'}], 'exactly {start, end, text}')):
            with self.subTest(captions=captions):
                self.write_instance(captions=captions)
                self.write_layers(plates=[])
                self.refused(words)

    def test_layers_must_be_the_ones_recorded_for_this_instance_under_the_lock(self):
        self.write_layers(lock_sha256='0' * 64)
        self.refused('another social kit lock')
        self.write_layers(instance_sha256='0' * 64)
        self.refused('another instance')
        record = self.write_layers()
        record['plates'][0]['sha256'] = '0' * 64
        atomic_json(self.layers / 'layers.json', record)
        self.refused('missing or changed')
        record = self.write_layers()
        record['plates'][1]['text'] = ['CH 1 · AI Pundit', 'Free pilot beta at fulltime.fm']
        atomic_json(self.layers / 'layers.json', record)
        self.refused('lacks Made by AI from checked match facts')
        self.write_layers(progress={**RECT, 'y': 1500})
        self.refused('inside the mid frame ground plate')
        self.write_layers(progress={**RECT, 'color': 'lime'})
        self.refused('#rrggbb')
        record = self.write_layers()
        record['plates'] = record['plates'][:1]
        atomic_json(self.layers / 'layers.json', record)
        self.refused('one plate per caption')
        os.remove(self.layers / 'layers.json')
        self.refused('no layers.json')

    def test_a_layer_that_is_not_1080x1920_is_refused(self):
        small = self.layers / 'plate-001.png'
        keep = small.read_bytes()
        try:
            png(small, PLATE, size=(720, 1280))
            self.write_layers()
            self.refused('not 1080x1920')
        finally:
            small.write_bytes(keep)

    def test_the_default_path_is_untouched(self):
        plain = {key: value for key, value in self.manifest().items() if key not in ('layers', 'instance', 'size')}
        checked_segments(self.api, plain)


@unittest.skipUnless(MEDIA, 'FFmpeg and FFprobe required')
class ComposeTests(Base):
    def frame(self, video, seconds):
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(seconds), '-i', str(video), '-frames:v', '1',
                              '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
        self.assertEqual(len(raw), 1080 * 1920 * 3)
        return raw

    @staticmethod
    def pixel(raw, x, y):
        at = (y * 1080 + x) * 3
        return tuple(raw[at:at + 3])

    def near(self, got, want, tolerance=12):
        self.assertTrue(all(abs(a - b) <= tolerance for a, b in zip(got, want)), f'{got} is not near {want}')

    def lime_run(self, raw):
        y = RECT['y'] + RECT['h'] // 2
        return sum(1 for x in range(RECT['x'], RECT['x'] + RECT['w'])
                   if self.pixel(raw, x, y)[1] > 200 and self.pixel(raw, x, y)[0] < 170)

    def test_a_synthetic_take_clip_is_composed_in_the_kit_design(self):
        path = self.root / 'kit-manifest.json'
        atomic_json(path, self.manifest())
        receipt = render(self.api, path)
        metadata = probe(receipt['video'])
        video = next(x for x in metadata['streams'] if x['codec_type'] == 'video')
        self.assertEqual((video['width'], video['height']), (1080, 1920))
        self.assertTrue(any(x['codec_type'] == 'audio' for x in metadata['streams']))
        self.assertAlmostEqual(float(metadata['format']['duration']), 4.0, delta=0.1)
        self.assertEqual(int(video['nb_frames']), 120)
        self.assertEqual(receipt['timeline'], {'fps': 30, 'frame0_seconds': 1.0, 'frames': [30, 30, 60]})
        # Frame 0 holds for the first second, with no progress fill on it.
        for seconds in (0.0, 0.5, 0.95):
            raw = self.frame(receipt['video'], seconds)
            self.near(self.pixel(raw, 540, 600), FRAME0)
            self.near(self.pixel(raw, RECT['x'] + 5, RECT['y'] + 5), FRAME0)
        # Then the plates, and a lime fill that grows in the exact track rectangle.
        early, late = self.frame(receipt['video'], 1.5), self.frame(receipt['video'], 3.5)
        self.near(self.pixel(early, 540, 600), PLATE)
        self.near(self.pixel(late, RECT['x'] + RECT['w'] - 3, RECT['y'] + 5), TRACK)
        self.near(self.pixel(early, RECT['x'] - 4, RECT['y'] + 5), PLATE)
        self.near(self.pixel(early, RECT['x'] + 5, RECT['y'] - 3), PLATE)
        grown = (self.lime_run(early), self.lime_run(late))
        self.assertGreater(grown[0], RECT['w'] * 0.3)
        self.assertGreater(grown[1], grown[0] + RECT['w'] * 0.4)
        self.assertLess(grown[1], RECT['w'])
        self.near(self.pixel(late, RECT['x'] + 5, RECT['y'] + 5), (0x7d, 0xfa, 0x46), tolerance=16)
        # The receipt carries the layers it was made from, the instance and the kit's lock.
        record = json.loads((self.layers / 'layers.json').read_text(encoding='utf-8'))
        self.assertEqual(receipt['layers']['frame0_sha256'], sha(self.layers / 'frame0.png'))
        self.assertEqual(receipt['layers']['plates_sha256'], [sha(self.layers / p['file']) for p in record['plates']])
        self.assertEqual(receipt['layers']['manifest_sha256'], sha(self.layers / 'layers.json'))
        self.assertEqual(receipt['layers']['progress'], RECT)
        self.assertEqual(receipt['instance_sha256'], sha(self.instance_path))
        self.assertEqual(receipt['design']['lock_sha256'], kit_lock()['lock_sha256'])
        self.assertEqual((receipt['design']['revision'], receipt['design']['approval']), (1, 'I like it. Looks good.'))
        self.assertEqual((receipt['renderer_version'], receipt['size'], receipt['publication_status']),
                         (assets.RENDERER_VERSION, '1080x1920', 'private_preview'))
        self.assertIn('ASSETS', receipt['holds'])
        captions = Path(receipt['captions']).read_text(encoding='utf-8')
        self.assertIn('00:00:02,000 --> 00:00:04,000\nThis is a test clip.', captions)
        self.assertTrue(Path(receipt['thumbnail']).exists())
        self.assertTrue(render(self.api, path)['reused'])
        # New layers under the same paths are a new render, never the cached one.
        changed = self.layers / 'plate-002.png'
        keep = changed.read_bytes()
        try:
            png(changed, (40, 30, 20), (RECT['x'], RECT['y'], RECT['w'], RECT['h']), TRACK)
            self.write_layers()
            again = render(self.api, path)
            self.assertFalse(again['reused'])
            self.assertNotEqual(again['video'], receipt['video'])
        finally:
            changed.write_bytes(keep)
            self.write_layers()


if __name__ == '__main__':
    unittest.main()
