"""Offline creative standards, pinned composition and conservative review gates.

No model/provider calls, publishing, scoring heuristics or implicit approvals.
Private project data lives under ignored local/creative-system; tests use fixtures.
"""
import argparse
import copy
import datetime as dt
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parents[1]
SCHEMA = REPO / 'creative-system' / 'schema.json'
DEFAULT_ROOT = REPO / 'local' / 'creative-system'
SHA = re.compile(r'^[a-f0-9]{64}$')
VERSION = re.compile(r'^\d+\.\d+\.\d+$')


class Invalid(ValueError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),
                      parse_constant=lambda x: (_ for _ in ()).throw(Invalid('non-finite JSON')))


def write_new(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive create: immutable versions/events cannot be silently replaced.
    with path.open('x', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def safe(root, rel):
    if not isinstance(rel, str) or '\\' in rel or ':' in rel:
        raise Invalid('paths must be portable relative POSIX paths')
    part = PurePosixPath(rel)
    if not rel or part.is_absolute() or '..' in part.parts or '.' == rel:
        raise Invalid('unsafe relative path')
    resolved = (Path(root) / rel).resolve()
    try:
        resolved.relative_to(Path(root).resolve())
    except ValueError as exc:
        raise Invalid('path escapes project root') from exc
    return resolved


def private_output(path):
    path = Path(path).resolve()
    if path.is_relative_to(REPO) and not path.is_relative_to(REPO / 'local'):
        raise Invalid('private output cannot be written into the public repository outside local/')
    return path


def validate(data, definition, schema=None):
    """Validate the explicitly bounded JSON Schema vocabulary in schema.json.

    This is not a general JSON Schema implementation. Unsupported keywords fail.
    """
    schema = schema or read(SCHEMA)
    known = {'$ref', '$schema', '$id', '$defs', 'title', 'description', 'type',
             'properties', 'required', 'additionalProperties', 'items', 'enum',
             'const', 'minItems', 'maxItems', 'minLength', 'maxLength', 'pattern', 'minimum', 'uniqueItems'}

    def walk(value, rule, location):
        if set(rule) - known:
            raise Invalid('unsupported schema vocabulary: ' + ','.join(sorted(set(rule) - known)))
        if '$ref' in rule:
            ref = rule['$ref']
            if not ref.startswith('#/$defs/'):
                raise Invalid('only local schema definitions are supported')
            return walk(value, schema['$defs'][ref.split('/')[-1]], location)
        types = rule.get('type', [])
        types = [types] if isinstance(types, str) else types
        checks = {'object': lambda x: isinstance(x, dict), 'array': lambda x: isinstance(x, list),
                  'string': lambda x: isinstance(x, str), 'boolean': lambda x: isinstance(x, bool),
                  'integer': lambda x: isinstance(x, int) and not isinstance(x, bool),
                  'number': lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
                  'null': lambda x: x is None}
        if types and not any(checks[t](value) for t in types):
            raise Invalid(location + ': incorrect type')
        if 'const' in rule and (value != rule['const'] or isinstance(value, bool) != isinstance(rule['const'], bool)):
            raise Invalid(location + ': incorrect constant')
        if 'enum' in rule and value not in rule['enum']:
            raise Invalid(location + ': invalid choice')
        if isinstance(value, dict):
            props = rule.get('properties', {})
            missing = set(rule.get('required', [])) - set(value)
            if missing:
                raise Invalid(location + ': missing ' + ','.join(sorted(missing)))
            for key, child in value.items():
                if key in props:
                    walk(child, props[key], location + '.' + key)
                elif rule.get('additionalProperties') is False:
                    raise Invalid(location + ': unknown field ' + key)
                elif isinstance(rule.get('additionalProperties'), dict):
                    walk(child, rule['additionalProperties'], location + '.' + key)
        if isinstance(value, list):
            if len(value) < rule.get('minItems', 0):
                raise Invalid(location + ': too few items')
            if len(value) > rule.get('maxItems', sys.maxsize):
                raise Invalid(location + ': too many items')
            if rule.get('uniqueItems') and len({canonical(x) for x in value}) != len(value):
                raise Invalid(location + ': duplicate items')
            for i, child in enumerate(value):
                walk(child, rule.get('items', {}), location + '[' + str(i) + ']')
        if isinstance(value, str):
            if len(value) < rule.get('minLength', 0) or len(value) > rule.get('maxLength', sys.maxsize) or ('pattern' in rule and not re.search(rule['pattern'], value)):
                raise Invalid(location + ': invalid string')
        if isinstance(value, (int, float)) and not isinstance(value, bool) and 'minimum' in rule and value < rule['minimum']:
            raise Invalid(location + ': below minimum')
    walk(data, schema['$defs'][definition], definition)
    return data


class System:
    def __init__(self, root=DEFAULT_ROOT):
        self.root = Path(root).resolve()

    def load_release(self, relative=None):
        pointer = None
        if relative is None:
            if not (self.root / 'CURRENT.json').exists():
                raise Invalid('creative baseline missing; restore the private bundle, do not invent a replacement')
            pointer = validate(read(self.root / 'CURRENT.json'), 'pointer')
            relative = pointer['release']
        release = validate(read(safe(self.root, relative)), 'release')
        if pointer and digest(release) != pointer['sha256']:
            raise Invalid('CURRENT release digest mismatch')
        if file_hash(safe(self.root, release['archive']['path'])) != release['archive']['sha256']:
            raise Invalid('source archive manifest integrity failure')
        modules = {}
        for pin in release['modules']:
            path = safe(self.root, pin['path'])
            if file_hash(path) != pin['sha256']:
                raise Invalid('module integrity failure: ' + pin['id'])
            module = validate(read(path), 'module')
            if module['id'] in modules or module['id'] != pin['id'] or module['version'] != pin['version']:
                raise Invalid('duplicate or inconsistent module pin')
            expected = 'modules/' + module['id'] + '/' + module['version'] + '.json'
            if pin['path'] != expected:
                raise Invalid('module path does not match its immutable version')
            keys = set()
            for rule in module['rules']:
                if not rule['id'].startswith(module['id'] + '.') or rule['id'] in keys:
                    raise Invalid('cross-owner or duplicate rule: ' + rule['id'])
                keys.add(rule['id'])
            if module['kind'] == 'character' and not module['id'].startswith('character.'):
                raise Invalid('character ownership mismatch')
            if module['kind'] == 'shared' and not module['id'].startswith('style.'):
                raise Invalid('shared ownership mismatch')
            modules[module['id']] = module
        for module in modules.values():
            for dep in module['depends_on']:
                if dep not in modules:
                    raise Invalid('unresolved module dependency: ' + dep)
                if modules[dep]['kind'] != 'shared':
                    raise Invalid('a module cannot inherit a sibling character')
        def visit(key, trail):
            if key in trail:
                raise Invalid('dependency cycle')
            for dep in modules[key]['depends_on']:
                visit(dep, trail + [key])
        for key in modules:
            visit(key, [])
        for cid in release['characters']:
            if cid not in modules or modules[cid]['kind'] != 'character':
                raise Invalid('unresolved character')
        for sid in release['shared']:
            if sid not in modules or modules[sid]['kind'] != 'shared':
                raise Invalid('unresolved shared standard')
        if set(modules) != set(release['characters'] + release['shared']):
            raise Invalid('unclassified or duplicate release module')
        if len(set(release['characters'] + release['shared'])) != len(modules):
            raise Invalid('duplicate release composition')
        evidence = validate(read(safe(self.root, release['evidence']['path'])), 'evidence')
        if file_hash(safe(self.root, release['evidence']['path'])) != release['evidence']['sha256']:
            raise Invalid('evidence ledger integrity failure')
        ids = [x['id'] for x in evidence['items']]
        if len(ids) != len(set(ids)):
            raise Invalid('duplicate evidence ID')
        for module in modules.values():
            for rule in module['rules']:
                if not set(rule['evidence_ids']).issubset(ids):
                    raise Invalid('unknown rule provenance')
        for ref in release['locks']:
            if file_hash(safe(self.root, ref['path'])) != ref['sha256']:
                raise Invalid('locked artifact changed: ' + ref['id'])
        cases = validate(read(safe(self.root, release['cases']['path'])), 'cases')
        if file_hash(safe(self.root, release['cases']['path'])) != release['cases']['sha256']:
            raise Invalid('regression case integrity failure')
        case_ids = [x['id'] for x in cases['items']]
        if len(case_ids) != len(set(case_ids)):
            raise Invalid('duplicate case ID')
        all_rules = {r['id'] for m in modules.values() for r in m['rules']}
        for case in cases['items']:
            if not set(case['modules']).issubset(modules) or not set(case['criteria']).issubset(all_rules):
                raise Invalid('unknown regression case module or criterion')
        return release, modules, evidence, cases

    def feedback(self):
        rows = []
        for path in sorted((self.root / 'feedback').glob('*.json')):
            rows.append(validate(read(path), 'feedback'))
        ids = [r['id'] for r in rows]
        if len(ids) != len(set(ids)):
            raise Invalid('duplicate feedback event')
        return rows

    def record_feedback(self, event):
        validate(event, 'feedback')
        existing = self.root / 'feedback' / (event['id'] + '.json')
        if existing.exists():
            if read(existing) == event:
                return {'id': event['id'], 'duplicate': True}
            raise Invalid('feedback ID reuse with changed content')
        release, modules, _, _ = self.load_release()
        if not set(event['modules']).issubset(modules):
            raise Invalid('feedback references unknown owner')
        write_new(existing, event)
        return {'id': event['id'], 'duplicate': False, 'changes_active_standards': False}

    def compose(self, characters, release_path=None):
        release, modules, evidence, _ = self.load_release(release_path)
        if not characters or len(set(characters)) != len(characters) or not set(characters).issubset(release['characters']):
            raise Invalid('select distinct registered characters')
        selected = release['shared'] + characters
        # No field merging, precedence guessing or loading sibling personalities.
        packet = {'schema_version': 1, 'release': release['id'], 'release_sha256': digest(release),
                  'status': release['status'], 'purpose': release['purpose'],
                  'shared': [modules[k] for k in release['shared']],
                  'characters': [modules[k] for k in characters], 'locks': release['locks'],
                  'limitations': release['limitations'], 'evidence': [], 'pending_feedback': [],
                  'authority': 'Offline drafting only. No generation, spend or publication authority.'}
        needed = {i for k in selected for r in modules[k]['rules'] for i in r['evidence_ids']}
        packet['evidence'] = [e for e in evidence['items'] if e['id'] in needed]
        packet['pending_feedback'] = [e for e in self.feedback() if e['id'] not in release['addressed_feedback'] and set(e['modules']) & set(selected)]
        packet['packet_sha256'] = digest(packet)
        return packet

    def change_plan(self, candidate_path, declared):
        old, before, _, old_cases = self.load_release()
        new, after, _, new_cases = self.load_release(candidate_path)
        changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
        if set(changed) != set(declared):
            raise Invalid('declared owners differ from actual changed modules')
        for key in set(before) & set(after):
            if before[key] != after[key] and before[key]['version'] == after[key]['version']:
                raise Invalid('changed module needs a new immutable version')
            if before[key] != after[key] and tuple(map(int, after[key]['version'].split('.'))) <= tuple(map(int, before[key]['version'].split('.'))):
                raise Invalid('module version must increase')
        if old['locks'] != new['locks']:
            raise Invalid('standards change cannot replace approved artifact locks')
        # Existing canaries cannot vanish or be weakened while evaluating a change.
        old_map = {c['id']: c for c in old_cases['items']}
        new_map = {c['id']: c for c in new_cases['items']}
        if any(new_map.get(k) != c for k, c in old_map.items()):
            raise Invalid('existing regression cases cannot be removed or altered')
        affected = set(changed)
        progress = True
        while progress:
            previous = set(affected)
            for key, module in after.items():
                if set(module['depends_on']) & affected:
                    affected.add(key)
            progress = previous != affected
        # All identity canaries run even for a one-character edit. Shared edits
        # also exercise every dependent character and the ensemble.
        required = sorted(c['id'] for c in new_cases['items']
                          if c['always_run'] or set(c['modules']) & affected)
        untouched = sorted(k for k in before if k not in changed)
        return {'baseline_sha256': digest(old), 'candidate_sha256': digest(new),
                'changed': changed, 'affected': sorted(affected), 'untouched': untouched,
                'required_cases': required, 'status': 'awaiting_regression_reviews'}

    def change_gate(self, candidate_path, declared, reports):
        plan = self.change_plan(candidate_path, declared)
        _, _, _, cases = self.load_release(candidate_path)
        case_map = {c['id']: c for c in cases['items']}
        seen, holds, improvements = set(), [], []
        for report in reports:
            validate(report, 'regression_review')
            cid = report['case_id']
            if cid in seen or cid not in plan['required_cases']:
                raise Invalid('duplicate or out-of-plan regression review')
            seen.add(cid)
            if report['baseline_sha256'] != plan['baseline_sha256'] or report['candidate_sha256'] != plan['candidate_sha256']:
                raise Invalid('review belongs to another exact release')
            if report['case_sha256'] != digest(case_map[cid]):
                raise Invalid('review belongs to another case revision')
            if report['reviewer_kind'] != 'owner':
                holds.append(cid + ': owner judgment absent')
            if report['preference'] in ('baseline', 'not_judged'):
                holds.append(cid + ': comparison preference is ' + report['preference'])
            if report['reviewer_kind'] == 'owner' and report['preference'] == 'candidate' and set(case_map[cid]['modules']) & set(plan['affected']):
                improvements.append(cid)
            if not report['baseline_artifact_sha256'] or not report['candidate_artifact_sha256']:
                holds.append(cid + ': comparative artifacts absent')
            findings = report['findings']
            if len({f['criterion'] for f in findings}) != len(findings):
                raise Invalid('duplicate criterion finding')
            if {f['criterion'] for f in findings} != set(case_map[cid]['criteria']):
                raise Invalid('review does not cover exact case criteria')
            for finding in findings:
                if finding['candidate'] != 'holds':
                    holds.append(cid + ': ' + finding['criterion'] + ' is ' + finding['candidate'])
        holds += [c + ': review absent' for c in plan['required_cases'] if c not in seen]
        if not improvements:
            holds.append('no owner-observed improvement in an affected case')
        return {**plan, 'status': 'held' if holds else 'reviewed_for_owner_promotion',
                'holds': holds, 'improved_cases': improvements, 'publishing_authorized': False}

    def artifact_gate(self, production, reviews):
        validate(production, 'production')
        release, modules, _, _ = self.load_release(production['release_path'])
        if production['release_sha256'] != digest(release):
            raise Invalid('production references a different release')
        if digest(self.load_release()[0]) != digest(release):
            raise Invalid('production uses a superseded standards release')
        if not set(production['characters']).issubset(release['characters']):
            raise Invalid('unknown production character')
        for asset in production['assets']:
            if file_hash(safe(self.root, asset['path'])) != asset['sha256']:
                raise Invalid('production asset hash mismatch')
        selected = release['shared'] + production['characters']
        criteria = {r['id']: r for key in selected for r in modules[key]['rules']
                    if production['medium'] in r['media'] and r['state'] != 'awaiting_evidence'}
        holds, seen = [], set()
        for key in selected:
            for rule in modules[key]['rules']:
                if production['medium'] in rule['media'] and rule['state'] == 'awaiting_evidence':
                    holds.append(rule['id'] + ': requirement evidence not established')
        asset_digest = digest(production['assets'])
        for review in reviews:
            validate(review, 'artifact_review')
            if review['release_sha256'] != digest(release) or review['production_sha256'] != digest(production) or review['assets_sha256'] != asset_digest:
                raise Invalid('artifact review bound to wrong inputs')
            for finding in review['findings']:
                key = finding['criterion']
                if key not in criteria or key in seen:
                    raise Invalid('unknown or duplicate artifact criterion')
                seen.add(key)
                if review['reviewer_kind'] != 'owner' or finding['verdict'] != 'holds':
                    holds.append(key + ': ' + finding['verdict'] + ' (' + review['reviewer_kind'] + ')')
        holds += [k + ': not assessed' for k in sorted(set(criteria) - seen)]
        for key in selected:
            if modules[key]['status'] == 'awaiting_evidence':
                holds.append(key + ': character evidence not established for this surface')
        open_feedback = [f['id'] for f in self.feedback()
                         if f['id'] not in production['addressed_feedback'] and set(f['modules']) & set(selected)]
        holds += [f + ': unaddressed owner feedback' for f in open_feedback]
        if not production['technical_pass']:
            holds.append('technical checks not passed')
        holds += production['external_holds']
        return {'status': 'held' if holds else 'ready_for_owner_release_review',
                'holds': holds, 'creative_accepted': not holds,
                'publishing_authorized': False, 'generation_authorized': False,
                'required_criteria': sorted(criteria), 'reviewed_criteria': sorted(seen)}

    def promote(self, candidate_path, declared, reports, decision):
        # A crash leaves the lease for deliberate recovery, not a second writer.
        lease = self.root / '.promotion.lock'
        try:
            with lease.open('x', encoding='utf-8') as handle:
                handle.write('promotion in progress\n')
        except FileExistsError as exc:
            raise Invalid('another promotion or unfinished recovery owns the standards pointer') from exc
        try:
            return self._promote(candidate_path, declared, reports, decision)
        finally:
            lease.unlink()

    def _promote(self, candidate_path, declared, reports, decision):
        validate(decision, 'decision')
        event_path = self.root / 'promotions' / (decision['id'] + '.json')
        if event_path.exists():
            previous_event = read(event_path)
            if previous_event['decision'] != decision or decision['review_set_sha256'] != digest(reports) or previous_event['next']['release'] != candidate_path:
                raise Invalid('promotion event ID reuse with changed payload')
            current = read(self.root / 'CURRENT.json')
            if {k: current[k] for k in ('release', 'sha256')} == previous_event['next']:
                return {'status': 'promoted', 'duplicate': True, 'publication_authority': False}
            if current != previous_event['prior']:
                raise Invalid('cannot replay a promotion over a newer standards pointer')
        gate = self.change_gate(candidate_path, declared, reports)
        if gate['holds'] or decision['reviewer_kind'] != 'owner' or decision['decision'] != 'approve' or decision['candidate_sha256'] != gate['candidate_sha256'] or decision['review_set_sha256'] != digest(reports):
            raise Invalid('promotion requires passing reviews and exact owner decision')
        candidate, _, _, _ = self.load_release(candidate_path)
        current = read(self.root / 'CURRENT.json')
        event = {'prior': current, 'next': {'release': candidate_path, 'sha256': digest(candidate)},
                 'gate': gate, 'decision': decision}
        if not event_path.exists():
            write_new(event_path, event)
        target = self.root / 'CURRENT.json'
        temp = self.root / 'CURRENT.next.json'
        pointer = {'schema_version': 1, 'release': candidate_path, 'sha256': digest(candidate)}
        if temp.exists():
            if read(temp) != pointer:
                raise Invalid('unfinished pointer update needs explicit recovery')
        else:
            write_new(temp, pointer)
        temp.replace(target)
        return {'status': 'promoted', 'release': candidate['id'], 'publication_authority': False}

    def startup(self):
        release, modules, _, _ = self.load_release()
        archive = read(safe(self.root, release['archive']['path']))
        failed = []
        for entry in archive['files']:
            path = safe(self.root, entry['path'])
            if not path.exists() or file_hash(path) != entry['sha256']:
                failed.append(entry['path'])
        if failed:
            raise Invalid('source archive missing or changed: ' + ','.join(failed[:5]))
        return {'status': 'captured_baseline_loaded', 'release': release['id'],
                'release_sha256': digest(release), 'modules': len(modules),
                'archive_files_verified': len(archive['files']), 'limitations': release['limitations'],
                'pending_feedback': [f['id'] for f in self.feedback() if f['id'] not in release['addressed_feedback']],
                'next': release['next_action'], 'generation_authorized': False,
                'publication_authorized': False}


def export_bundle(root, output):
    root, output = Path(root).resolve(), private_output(output)
    System(root).startup()
    if output.exists() or output.is_relative_to(root):
        raise Invalid('bundle output must be new and outside the private root')
    files = sorted(p for p in root.rglob('*') if p.is_file())
    for path in files:
        safe(root, path.relative_to(root).as_posix())
    manifest = {'schema_version': 1, 'files': [{'path': p.relative_to(root).as_posix(),
                'sha256': file_hash(p), 'bytes': p.stat().st_size} for p in files]}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_STORED) as z:
        for path in files:
            z.write(path, path.relative_to(root).as_posix())
        z.writestr('BUNDLE-MANIFEST.json', canonical(manifest))
    write_new(str(output) + '.json', {'sha256': file_hash(output), 'files': len(files),
                                    'bytes': output.stat().st_size, 'private': True})
    return {'bundle': str(output), 'files': len(files), 'sha256': file_hash(output)}


def import_bundle(bundle, destination, expected_sha256):
    bundle, destination = Path(bundle), private_output(destination)
    if file_hash(bundle) != expected_sha256 or destination.exists():
        raise Invalid('bundle hash mismatch or restore destination already exists')
    with zipfile.ZipFile(bundle) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or sum(i.file_size for i in z.infolist()) > 2_000_000_000:
            raise Invalid('duplicate entries or oversized archive')
        manifest = json.loads(z.read('BUNDLE-MANIFEST.json'))
        entries = manifest['files']
        if len({e['path'] for e in entries}) != len(entries):
            raise Invalid('duplicate bundle manifest entry')
        if set(names) != {'BUNDLE-MANIFEST.json'} | {e['path'] for e in entries}:
            raise Invalid('bundle inventory mismatch')
        for entry in entries:
            safe(destination, entry['path'])
            info = z.getinfo(entry['path'])
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise Invalid('symlink entries refused')
            data = z.read(entry['path'])
            if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
                raise Invalid('bundle entry integrity failure')
        # Validate complete staged data before creating the requested destination.
        import tempfile
        with tempfile.TemporaryDirectory(prefix='creative-restore-', dir=destination.parent) as temporary:
            stage = Path(temporary) / 'root'
            stage.mkdir()
            for entry in entries:
                target = safe(stage, entry['path']); target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(entry['path']))
            System(stage).startup()
            stage.replace(destination)
    return {'status': 'restored', 'files': len(entries)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('startup')
    compose = sub.add_parser('compose'); compose.add_argument('--characters', nargs='+', required=True); compose.add_argument('--output', type=Path, required=True)
    plan = sub.add_parser('plan-change'); plan.add_argument('candidate'); plan.add_argument('--owners', nargs='+', required=True)
    check = sub.add_parser('change-gate'); check.add_argument('candidate'); check.add_argument('--owners', nargs='+', required=True); check.add_argument('--reviews', type=Path, required=True)
    artifact = sub.add_parser('artifact-gate'); artifact.add_argument('production', type=Path); artifact.add_argument('--reviews', type=Path, required=True)
    feedback = sub.add_parser('feedback'); feedback.add_argument('event', type=Path)
    promote = sub.add_parser('promote'); promote.add_argument('candidate'); promote.add_argument('--owners', nargs='+', required=True); promote.add_argument('--reviews', type=Path, required=True); promote.add_argument('--decision', type=Path, required=True)
    export = sub.add_parser('export'); export.add_argument('output', type=Path)
    restore = sub.add_parser('restore'); restore.add_argument('bundle', type=Path); restore.add_argument('destination', type=Path); restore.add_argument('--sha256', required=True)
    args = parser.parse_args(argv); system = System(args.root)
    try:
        if args.command == 'startup':
            result = system.startup()
        elif args.command == 'compose':
            result = system.compose(args.characters); write_new(private_output(args.output), result)
            result = {'packet': str(args.output), 'packet_sha256': result['packet_sha256'], 'characters': args.characters}
        elif args.command == 'plan-change':
            result = system.change_plan(args.candidate, args.owners)
        elif args.command == 'change-gate':
            result = system.change_gate(args.candidate, args.owners, read(args.reviews))
        elif args.command == 'artifact-gate':
            result = system.artifact_gate(read(args.production), read(args.reviews))
        elif args.command == 'feedback':
            result = system.record_feedback(read(args.event))
        elif args.command == 'promote':
            result = system.promote(args.candidate, args.owners, read(args.reviews), read(args.decision))
        elif args.command == 'export':
            result = export_bundle(args.root, args.output)
        else:
            result = import_bundle(args.bundle, args.destination, args.sha256)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get('status') == 'held' else 0
    except (Invalid, OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        print(json.dumps({'status': 'invalid', 'error': str(exc)})); return 1


if __name__ == '__main__':
    sys.exit(main())
