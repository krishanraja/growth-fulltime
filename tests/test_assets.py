import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import types
import unittest

import growth
from engine.assets import checked_segments, download, probe, render, sha
from engine.records import atomic_json


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg and FFprobe required')
class AssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.state = {'sha':'a'*40,'rail':[{'drop':'drop1','pundits':['zen','gaffer'],'fill':2,
                                        'home':'Fixture Home','away':'Fixture Away','score':[1,0]}], 'rulings':{}}
        cls.api = types.SimpleNamespace(LOCAL=str(cls.root), SITE=growth.SITE, PUNDITS=growth.PUNDITS,
                                        RAIL_MIN=4, CREATIVE_ID=growth.CREATIVE_ID,
                                        tracked=growth.tracked, problems=growth.problems,
                                        load_state=lambda:copy.deepcopy(cls.state))
        cls.sources=[]
        for number,pundit in enumerate(('zen','gaffer')):
            folder=cls.root/'assets'/'drop1'/pundit;folder.mkdir(parents=True)
            audio,cover=folder/'audio.wav',folder/'cover.png'
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i',
                            f'sine=frequency={330+number*100}:duration=6','-c:a','pcm_s16le',str(audio)],check=True)
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i',
                            'color=c=0x122126:s=640x336','-frames:v','1','-threads','1',str(cover)],check=True)
            source={'schema_version':1,'drop_id':'drop1','pundit':pundit,
                    'source_url':f'{growth.SITE}/api/public/drops/drop1/variants/{pundit}',
                    'source_sha':'a'*40,'published_at':'fixture-only',
                    'audio':str(audio),'cover':str(cover),'audio_sha256':sha(audio),'cover_sha256':sha(cover),
                    'duration_seconds':6,'transcript':'QA fixture audio. This is a test clip.'}
            record=folder/'source.json';atomic_json(record,source);cls.sources.append(str(record))

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def manifest(self):
        return {'schema_version':1,'creative_id':'YT_CLASH_SHORT_C99_H01_V1_20261017',
                'drop_id':'drop1','caption_alignment_verified':False,
                'segments':[{'source_record':x,'start_seconds':0,'end_seconds':3,
                             'quote':'QA fixture audio.'} for x in self.sources]}

    def test_actual_two_pundit_render_and_reuse(self):
        path=self.root/'manifest.json';atomic_json(path,self.manifest())
        receipt=render(self.api,path)
        self.assertEqual(receipt['pundits'],['zen','gaffer'])
        self.assertEqual((receipt['width'],receipt['height']),(720,1280))
        self.assertIn('ASSETS',receipt['holds'])
        self.assertIn('RAIL',receipt['holds'])
        self.assertEqual(receipt['publication_status'],'private_preview')
        self.assertEqual(receipt['generated_media_calls'],0)
        self.assertTrue(Path(receipt['thumbnail']).exists())
        self.assertIn('00:00:03,000 --> 00:00:06,000',Path(receipt['captions']).read_text())
        self.assertTrue(render(self.api,path)['reused'])
        self.assertTrue(any(x['codec_type']=='audio' for x in probe(receipt['video'])['streams']))

    def test_cross_match_source_refused(self):
        manifest=self.manifest();manifest['drop_id']='another'
        with self.assertRaises(ValueError):checked_segments(self.api,manifest)

    def test_same_pundit_twice_is_not_a_comparison(self):
        manifest=self.manifest();manifest['segments'][1]=manifest['segments'][0]
        with self.assertRaises(ValueError):checked_segments(self.api,manifest)

    def test_invented_transcript_or_timestamp_refused(self):
        for changes in ({'quote':'This quotation was invented.'},{'end_seconds':100},{'start_seconds':-1}):
            manifest=self.manifest();manifest['segments'][0].update(changes)
            with self.assertRaises(ValueError):checked_segments(self.api,manifest)

    def test_tampered_asset_refused(self):
        source=Path(self.sources[0]);saved=source.read_bytes()
        data=json.loads(saved);data['audio_sha256']='0'*64;atomic_json(source,data)
        try:
            with self.assertRaises(ValueError):checked_segments(self.api,self.manifest())
        finally:source.write_bytes(saved)

    def test_source_outside_private_assets_refused(self):
        manifest=self.manifest();manifest['segments'][0]['source_record']='/etc/passwd'
        with self.assertRaises(ValueError):checked_segments(self.api,manifest)

    def test_download_only_public_unsigned_product_media(self):
        for url in ('http://example.test/a','https://example.test/a',
                    'https://hzadscrqmyilbisexvyz.supabase.co/private/a',
                    'https://hzadscrqmyilbisexvyz.supabase.co/storage/v1/object/public/a?token=private'):
            with self.subTest(url=url),self.assertRaises(ValueError):download(url,self.root/'bad',10)


if __name__=='__main__':unittest.main()
