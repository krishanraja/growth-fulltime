import datetime as dt
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from engine import control_center, ga4

TODAY = dt.date(2026, 10, 27)
CID = 'TT_CLASH_CLIP_C01_H01_V1_20261020'


def landing(content, new_users):
    return {'sessionSource': 'tiktok', 'sessionMedium': 'social', 'sessionCampaignName': 'matchday',
            'sessionManualAdContent': content, 'newUsers': str(new_users), 'sessions': str(new_users),
            'engagedSessions': '0'}


class MeasurementLines(unittest.TestCase):
    def setUp(self):
        self.local = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.local)

    def write_export(self, export):
        path = self.local / 'ga4' / 'landings-latest.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(export), encoding='utf-8')

    def test_north_star_is_missing_never_zero_and_ga4_says_not_read(self):
        lines = control_center.measurement_lines(self.local, TODAY)
        north = [line for line in lines if line.startswith('North Star reading, share_arrived_new_listeners')]
        self.assertEqual(len(north), 1)
        self.assertIn('missing', north[0])
        self.assertNotIn(' 0 people', ' '.join(lines))
        self.assertIn('Google Analytics: not read', lines[-1])

    def test_ga4_landings_are_named_by_creative_and_never_called_listeners(self):
        export = ga4.to_export([landing(CID, 5), landing('someone-elses-tag', 2)], '2026-10-20', '2026-10-26',
                               dt.datetime(2026, 10, 27, 6, tzinfo=dt.timezone.utc))
        self.write_export(export)
        line = control_center.measurement_lines(self.local, TODAY)[-1]
        self.assertIn('5 new web users from 1 tagged creatives and 2 from untagged links', line)
        self.assertIn(CID, line)
        self.assertIn('never listeners', line)

    def test_a_refused_export_is_reported_not_counted(self):
        self.write_export({'product': 'fulltime', 'source': 'ga4', 'rows': []})
        line = control_center.measurement_lines(self.local, TODAY)[-1]
        self.assertTrue(line.startswith('Google Analytics: the export was refused'), line)


if __name__ == '__main__':
    unittest.main()
