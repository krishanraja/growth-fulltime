"""Preserved sources stay byte for byte, and the copy doctrine stays wired into drafting."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location('verify_repository', ROOT / 'scripts' / 'verify_repository.py')
verify = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verify)
SOURCES = json.loads((ROOT / 'knowledge' / 'sources.json').read_text())['sources']


class PreservedSources(unittest.TestCase):
    def test_every_preserved_source_matches_its_manifest(self):
        self.assertEqual(verify.source_errors(), [])

    def test_corpus_is_registered_with_its_received_hash(self):
        corpus = {s['path']: s for s in SOURCES}['knowledge/copywriting-offers-demand-corpus.md']
        self.assertEqual(corpus['original_filename'], 'copywriting-offer-corpus.md')
        self.assertEqual(corpus['bytes'], 68132)
        self.assertEqual(corpus['sha256'], '04fddb23da2cb210470f60b57a6d78b56d37c3f84316217e0e493caa6b9856d9')
        self.assertEqual(corpus['received'], '2026-10-19')

    def test_one_changed_byte_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'knowledge').mkdir()
            shutil.copy(ROOT / 'knowledge' / 'sources.json', root / 'knowledge' / 'sources.json')
            for source in SOURCES:
                shutil.copy(ROOT / source['path'], root / source['path'])
            self.assertEqual(verify.source_errors(root), [])
            target = root / SOURCES[0]['path']
            data = bytearray(target.read_bytes())
            data[100] ^= 1
            target.write_bytes(bytes(data))
            errors = verify.source_errors(root)
            self.assertTrue(any('SHA-256 differs' in e for e in errors), errors)
            target.write_bytes(target.read_bytes() + b'\n')
            self.assertTrue(any('bytes, the manifest says' in e for e in verify.source_errors(root)))
            target.unlink()
            self.assertTrue(any('missing' in e for e in verify.source_errors(root)))

    def test_missing_manifest_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(verify.source_errors(Path(tmp)))

    def test_git_never_converts_preserved_bytes(self):
        attributes = (ROOT / '.gitattributes').read_text().split('\n')
        for source in SOURCES:
            self.assertIn(f'{source["path"]} -text', attributes)


class CopyDoctrine(unittest.TestCase):
    def test_doctrine_is_plain_and_keeps_its_overrides(self):
        text = (ROOT / 'COPY.md').read_text()
        self.assertNotIn('\u2014', text)
        self.assertIn("## Where this engine's rules change the corpus", text)
        self.assertLess(len(text.splitlines()), 250)

    def test_drafting_surfaces_point_to_the_doctrine(self):
        for name in ('PLAYBOOK.md', 'jobs/morning.md', 'jobs/weekly.md', 'knowledge/README.md'):
            self.assertIn('COPY.md', (ROOT / name).read_text(), name)
        readme = (ROOT / 'knowledge' / 'README.md').read_text()
        for source in SOURCES:
            self.assertIn(Path(source['path']).name, readme)


if __name__ == '__main__':
    unittest.main()
