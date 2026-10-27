import datetime as dt
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from engine import control_center, formats, ga4, gates, pack, reporting
from tests.test_pack import allowlist, media, take

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
        self.assertIn('Control Center sent no landings', lines[-1])

    def test_ga4_landings_are_named_by_creative_and_never_called_listeners(self):
        export = ga4.to_export([landing(CID, 5), landing('someone-elses-tag', 2)], '2026-10-20', '2026-10-26',
                               dt.datetime(2026, 10, 27, 6, tzinfo=dt.timezone.utc))
        self.write_export(export)
        line = control_center.measurement_lines(self.local, TODAY)[-1]
        self.assertIn('5 new web users from 1 tagged creatives and 2 from untagged links', line)
        self.assertIn(CID, line)
        self.assertIn('never listeners', line)

    def test_control_center_landings_in_the_directive_come_first(self):
        mine = ga4.to_export([landing(CID, 1)], '2026-10-20', '2026-10-26',
                             dt.datetime(2026, 10, 27, 6, tzinfo=dt.timezone.utc))
        self.write_export(mine)
        theirs = ga4.to_export([landing(CID, 9)], '2026-10-20', '2026-10-26',
                               dt.datetime(2026, 10, 27, 6, tzinfo=dt.timezone.utc))
        line = control_center.measurement_lines(self.local, TODAY,
                                                directive={'directive': {'ga4_landings': theirs}})[-1]
        self.assertIn('(from Control Center)', line)
        self.assertIn('9 new web users', line)
        bad = control_center.measurement_lines(self.local, TODAY, directive={'directive': {'ga4_landings': {}}})[-1]
        self.assertIn('the export from Control Center was refused', bad)

    def test_a_refused_export_is_reported_not_counted(self):
        self.write_export({'product': 'fulltime', 'source': 'ga4', 'rows': []})
        line = control_center.measurement_lines(self.local, TODAY)[-1]
        self.assertTrue(line.startswith('Google Analytics: the export saved locally was refused'), line)


LOCK = 'a' * 64
EXPIRES = '2026-11-01T20:00:00+00:00'


def rail(*drops):
    return {'rail': [{'drop': d, 'date': '2026-10-31', 'home': 'Rovers', 'away': 'United', 'score': [2, 1],
                      'pundits': ['doomer'], 'fill': 1} for d in drops]}


def take_on(drop, n):
    cid = f'TT_CLASH_CLIP_C0{n}_H01_V1_20261101'
    return take(creative_id=cid, drop_id=drop, master_id=f'M_20261101_{drop.upper()}_{n}',
                media=[media(str(n) * 64, url=f'https://review.example.com/2026-11-01/take-0{n}')])


def queued_pack(local, day, *items, drops):
    built = pack.build(list(items), f'fulltime:{day}:g2', day, rail(*drops), allowlist(), False)
    proposal = pack.proposal(built, EXPIRES)
    context = {i['creative_id']: {'format_id': 'take_clip', 'lock_version': LOCK, 'fixture_ref': i['drop_id'],
                                  'unit_cost_recorded': True, 'unit_minutes_recorded': True} for i in built['items']}
    gates.prepare(local, 'g2', proposal, context)
    return built, proposal


def report_with_gates(local):
    return reporting.build('fulltime:2026-11-01:daily', 'live', '2026-11-01T06:00:00Z', rail('drop-a'), [],
                           {}, [], ['test'], gate_proposals=gates.pending(local))


def amended(proposal, payload):
    text = reporting.canonical(payload)
    decision = {'proposal_id': proposal['proposal_id'], 'decision': 'approved', 'amended': True,
                'payload_sha256': proposal['payload_sha256'], 'exact_payload': text}
    decision['amended_sha256'] = control_center.amended_digest(decision)
    return decision


class GateLoop(unittest.TestCase):
    def setUp(self):
        self.local = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.local)

    def test_a_queued_g2_rides_the_report_and_his_amendment_becomes_per_item_verdicts(self):
        built, proposal = queued_pack(self.local, '2026-11-01', take_on('drop-a', 1), take_on('drop-b', 2),
                                      take_on('drop-c', 3), drops=('drop-a', 'drop-b', 'drop-c'))
        report = report_with_gates(self.local)
        sent = next(p for p in report['proposals'] if p['proposal_id'] == proposal['proposal_id'])
        self.assertEqual(sent['wall'], 'post')
        mine = json.loads(sent['exact_payload'])
        mine['items'][1]['caption'] = 'His sharper line, still with the AI Pundit named.'
        del mine['items'][2]
        decided = control_center.classify([amended(sent, mine)], report['proposals'])
        rows = gates.settle(self.local, decided)
        self.assertEqual([r['verdict'] for r in rows], ['post_it', 'edit', 'reject'])
        self.assertEqual(gates.pending(self.local), [])
        self.assertEqual(gates.settle(self.local, decided), [])        # settled once only
        self.assertEqual(len(gates.verdicts(self.local)), 3)
        with self.assertRaises(ValueError):
            gates.prepare(self.local, 'g2', proposal, {i['creative_id']: {} for i in built['items']})

    def test_an_old_digest_or_unverified_amendment_settles_nothing(self):
        _, proposal = queued_pack(self.local, '2026-11-01', take_on('drop-a', 1), drops=('drop-a',))
        report = report_with_gates(self.local)
        stale = {'proposal_id': proposal['proposal_id'], 'decision': 'approved', 'payload_sha256': 'f' * 64}
        forged = {**amended(proposal, json.loads(proposal['exact_payload'])), 'amended_sha256': 'e' * 64}
        for decision in (stale, forged):
            decided = control_center.classify([decision], report['proposals'])
            self.assertEqual(gates.settle(self.local, decided), [])
        self.assertEqual(len(gates.pending(self.local)), 1)

    def test_three_clean_answers_on_three_matches_make_a_pinned_format_ready(self):
        for n, (day, drop) in enumerate((('2026-11-01', 'drop-a'), ('2026-11-02', 'drop-b'),
                                         ('2026-11-03', 'drop-c')), start=1):
            _, proposal = queued_pack(self.local, day, take_on(drop, n), drops=(drop,))
            report = report_with_gates(self.local)
            clear = {'proposal_id': proposal['proposal_id'], 'decision': 'approved',
                     'payload_sha256': proposal['payload_sha256']}
            gates.settle(self.local, control_center.classify([clear], report['proposals']))
        ledger = gates.verdicts(self.local)
        self.assertTrue(formats.readiness(ledger, 'take_clip', LOCK)['ready'])
        self.assertFalse(formats.readiness(ledger, 'take_clip', 'b' * 64)['ready'])   # a new lock starts again

    def test_a_signed_g1_is_kept_as_the_week_spec(self):
        from engine import spec
        example = spec.load(Path(__file__).resolve().parent.parent / 'specs' / 'examples' / 'synthetic-week.json')
        proposal = spec.proposal(example, EXPIRES)
        gates.prepare(self.local, 'g1', proposal)
        report = report_with_gates(self.local)
        sent = next(p for p in report['proposals'] if p['proposal_id'] == proposal['proposal_id'])
        clear = {'proposal_id': sent['proposal_id'], 'decision': 'approved', 'payload_sha256': sent['payload_sha256']}
        gates.settle(self.local, control_center.classify([clear], report['proposals']))
        signed = json.loads((self.local / 'specs' / '2026-W45.signed.json').read_text(encoding='utf-8'))
        self.assertEqual(spec.digest(signed['spec']), spec.digest(example))


class RulingOneInReports(unittest.TestCase):
    def rulings(self, organic='approved'):
        return {'D2': {'status': 'pending', 'unlocks': ['tiktok'], 'title': 'D2', 'recommendation': 'r'},
                'ORGANIC': {'status': organic, 'unlocks': [], 'requires': ['D1'], 'title': 'O', 'recommendation': 'r'},
                'RELEASE': {'status': 'pending', 'unlocks': [], 'title': 'Release', 'recommendation': 'r'},
                'D1': {'status': 'approved', 'unlocks': ['tiktok'], 'title': 'D1', 'recommendation': 'r'}}

    def report(self, state):
        return reporting.build('fulltime:2026-11-01:daily', 'synthetic', '2026-11-01T06:00:00Z', state, [],
                               self.rulings(), [], ['test'], identity_known=True)

    def test_release_is_never_asked_again_under_its_own_name(self):
        ids = [p['proposal_id'] for p in self.report({'push': {'open': False, 'why': 'thin'}})['proposals']]
        self.assertNotIn('fulltime:ruling:RELEASE', ids)
        self.assertNotIn('fulltime:ruling:release', ids)
        self.assertIn('fulltime:ruling:D2', ids)

    def test_organic_in_force_lifts_the_report_release_hold(self):
        held = {'push': {'open': False, 'why': 'thin'}, 'rulings': {'ORGANIC': {'in_force': False}}}
        reasons = [h['reason'] for h in self.report(held)['holds']]
        self.assertIn('RELEASE', reasons)
        live = {**held, 'rulings': {'ORGANIC': {'in_force': True}}}
        self.assertNotIn('RELEASE', [h['reason'] for h in self.report(live)['holds']])
        self.assertIn('RAIL', [h['reason'] for h in self.report(live)['holds']])   # whole-match still needs 4 of 6


class WeeklyLibrary(unittest.TestCase):
    def setUp(self):
        self.local = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.local)
        example = json.loads((Path(__file__).resolve().parent.parent / 'examples' / 'library-listing.example.json')
                             .read_text(encoding='utf-8'))
        from engine import library
        (self.local / 'library').mkdir()
        self.listing, self.rows = example['listing'], example['index']
        (self.local / 'library' / 'INDEX.csv').write_text(library.write_index(self.rows), encoding='utf-8')

    def write_listing(self, listing):
        (self.local / 'library' / 'listing.json').write_text(json.dumps({'listing': listing}), encoding='utf-8')

    def test_a_clean_library_holds_nothing_and_sprawl_leads_the_report(self):
        self.write_listing(self.listing)
        line, held = control_center.library_check(self.local)
        self.assertEqual(held, [])
        self.assertIn('reconciled clean', line)
        self.write_listing(self.listing + [{'path': 'Random stuff', 'bytes': None, 'is_folder': True},
                                           {'path': 'Random stuff/notes.txt', 'bytes': 10, 'is_folder': False}])
        line, held = control_center.library_check(self.local)
        self.assertEqual(held[0][0], 'LIBRARY')
        report = reporting.build('fulltime:2026-11-02:weekly', 'synthetic', '2026-11-02T08:00:00Z',
                                 {'push': {'open': False, 'why': 'thin'}}, [], {}, [], [line], extra_holds=held)
        self.assertEqual(report['holds'][0]['reason'], 'LIBRARY')

    def test_without_a_listing_it_says_so_and_holds_nothing(self):
        (self.local / 'library' / 'INDEX.csv').unlink()
        line, held = control_center.library_check(self.local)
        self.assertEqual(held, [])
        self.assertIn('not reconciled', line)


class Capabilities(unittest.TestCase):
    def setUp(self):
        from tests.test_control_center import StandIn, TOKEN, sample_report
        self.server = StandIn()
        self.addCleanup(self.server.close)
        self.client = control_center.Client(self.server.url, TOKEN, loopback_for_tests=True)
        self.report = sample_report()

    def run_once(self):
        return control_center.execute(self.client, 'morning', self.report['run_id'],
                                      lambda directive: (self.report, {}), None)

    def test_a_version_control_center_does_not_offer_is_never_sent(self):
        self.server.capabilities['schema_versions'] = ['1.0.0']
        summary = self.run_once()
        self.assertEqual((summary['status'], summary['error_code']), ('failed', 'version_not_offered'))
        self.assertEqual(self.server.reports, {})

    def test_the_mode_is_read_and_an_older_server_without_the_route_still_gets_its_report(self):
        summary = self.run_once()
        self.assertEqual((summary['status'], summary['autonomy']), ('succeeded', 'handcrafted'))
        self.server.capabilities = None
        self.report = {**self.report, 'run_id': 'fulltime:2026-10-20:daily'}
        self.report = reporting.seal({k: v for k, v in self.report.items() if k != 'payload_sha256'})
        summary = self.run_once()
        self.assertEqual(summary['status'], 'succeeded')
        self.assertNotIn('autonomy', summary)


if __name__ == '__main__':
    unittest.main()
