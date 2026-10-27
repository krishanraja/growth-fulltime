"""Cheap repository contract, JSON, relative-document-link and preserved-source checks."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
SOURCES = 'knowledge/sources.json'


def source_errors(root=ROOT, manifest=SOURCES):
    """Every preserved source must match the size and SHA-256 recorded in its manifest."""
    errors = []
    try:
        listing = json.loads((Path(root) / manifest).read_text(encoding='utf-8'))
        entries = listing['sources']
    except (OSError, ValueError, KeyError, TypeError):
        return [manifest + ': missing or unreadable preserved-source manifest']
    if listing.get('schema_version') != 1 or not isinstance(entries, list) or not entries:
        return [manifest + ': must be schema_version 1 with a non-empty sources list']
    for entry in entries:
        try:
            name, size, digest = entry['path'], entry['bytes'], entry['sha256']
            entry['original_filename'], entry['received']
        except (KeyError, TypeError):
            errors.append(manifest + ': each source needs path, original_filename, received, bytes and sha256')
            continue
        try:
            data = (Path(root) / name).read_bytes()
        except OSError:
            errors.append(name + ': preserved source is missing')
            continue
        if len(data) != size:
            errors.append(f'{name}: preserved source is {len(data)} bytes, the manifest says {size}')
        if hashlib.sha256(data).hexdigest() != digest:
            errors.append(name + ': preserved source SHA-256 differs from the manifest; restore the original bytes')
    return errors


LIMITS = {'crew/*/card.md': 3 * 1024, 'crew/*/lens.md': 1024, 'tasks/*.json': 6 * 1024, 'docs/ENGINE.md': 6 * 1024}


def v2_errors(root=ROOT):
    """Engine v2 contracts that need no imports: size budgets, data-only folders, live pointers and CI hardening."""
    root = Path(root)
    errors = []
    for pattern, limit in LIMITS.items():
        for path in sorted(root.glob(pattern)):
            size = len(path.read_bytes())
            if size > limit:
                errors.append(f'{path.relative_to(root)}: {size} bytes, over the {limit}-byte budget')
    for folder in ('specs', 'formats'):
        for path in sorted((root / folder).rglob('*')):
            if path.is_file() and path.suffix not in ('.json', '.md'):
                errors.append(f'{path.relative_to(root)}: {folder}/ holds data only; per-run code is refused')
    front = re.match(r'---\n(.*?)\n---\n', (root / 'NOW.md').read_text(encoding='utf-8'), re.S)
    if not front:
        errors.append('NOW.md: missing front matter')
    else:
        for key in ('state_doc', 'history_log'):
            found = re.search(rf'^{key}: (\S+)$', front.group(1), re.M)
            if found and not (root / found.group(1)).exists():
                errors.append(f'NOW.md: {key} points to {found.group(1)}, which does not exist')
    handovers = sorted(p.name for p in root.glob('HANDOVER-*.md'))
    for job in json.loads((root / 'automations.json').read_text(encoding='utf-8'))['automations']:
        named = re.findall(r'HANDOVER-[0-9-]+[A-Z-]*\.md', job['prompt'])
        if named and handovers and named[-1] != handovers[-1]:
            errors.append(f'automations.json: "{job["name"]}" names {named[-1]}, not the newest handover')
    check = (root / '.github/workflows/check.yml').read_text(encoding='utf-8')
    for needle, reason in (('timeout-minutes:', 'CI jobs need a timeout (a hung apt step ran for over 20 minutes)'),
                           ('runs-on: ubuntu-24.04', 'the renderer check is pinned to Ubuntu 24.04'),
                           ('https://archive.ubuntu.com/ubuntu', 'renderer packages come from the HTTPS mirror')):
        if needle not in check:
            errors.append('.github/workflows/check.yml: ' + reason)
    return errors


def main():
    paths = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard'],
                                    cwd=ROOT, text=True).splitlines()
    errors, json_count, link_count = [], 0, 0
    for name in sorted(set(paths)):
        path = ROOT / name
        if not path.is_file():
            continue
        if path.suffix == '.json':
            try:
                json.loads(path.read_text(encoding='utf-8'), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
                json_count += 1
            except (ValueError, OSError):
                errors.append(name + ': invalid JSON')
        if path.suffix == '.md':
            for target in re.findall(r'\]\(([^\s)]+)\)', path.read_text(encoding='utf-8')):
                target = target.split('#', 1)[0]
                if not target or re.match(r'^[a-z]+://', target) or target.startswith('mailto:'):
                    continue
                target = unquote(target.strip('<>'))
                if not (path.parent / target).exists():
                    errors.append(name + ': missing relative link ' + target)
                link_count += 1
    manifest = json.loads((ROOT/'automations.json').read_text(encoding='utf-8'))
    if manifest.get('schema_version') != 2 or manifest.get('timezone') != 'Europe/London' or len(manifest['automations']) != 2:
        errors.append('the schedule must contain exactly the two current London jobs')
    if {x['job'] for x in manifest['automations']} != {'jobs/morning.md','jobs/weekly.md'}:
        errors.append('active job inventory differs from the schedule')
    preserved = source_errors()
    errors += preserved
    errors += v2_errors()
    if errors:
        print('\n'.join(errors));sys.exit(1)
    count = len(json.loads((ROOT / SOURCES).read_text(encoding='utf-8'))['sources'])
    print(f'Repository checks passed: {json_count} JSON files, {link_count} relative links, two consolidated jobs, '
          f'{count} preserved sources byte-identical.')


if __name__ == '__main__':
    main()
