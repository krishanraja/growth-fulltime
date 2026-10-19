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
        listing = json.loads((Path(root) / manifest).read_text())
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
                json.loads(path.read_text(), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
                json_count += 1
            except (ValueError, OSError):
                errors.append(name + ': invalid JSON')
        if path.suffix == '.md':
            for target in re.findall(r'\]\(([^\s)]+)\)', path.read_text()):
                target = target.split('#', 1)[0]
                if not target or re.match(r'^[a-z]+://', target) or target.startswith('mailto:'):
                    continue
                target = unquote(target.strip('<>'))
                if not (path.parent / target).exists():
                    errors.append(name + ': missing relative link ' + target)
                link_count += 1
    manifest = json.loads((ROOT/'automations.json').read_text())
    if manifest.get('schema_version') != 2 or manifest.get('timezone') != 'Europe/London' or len(manifest['automations']) != 2:
        errors.append('the schedule must contain exactly the two current London jobs')
    if {x['job'] for x in manifest['automations']} != {'jobs/morning.md','jobs/weekly.md'}:
        errors.append('active job inventory differs from the schedule')
    preserved = source_errors()
    errors += preserved
    if errors:
        print('\n'.join(errors));sys.exit(1)
    count = len(json.loads((ROOT / SOURCES).read_text())['sources'])
    print(f'Repository checks passed: {json_count} JSON files, {link_count} relative links, two consolidated jobs, '
          f'{count} preserved sources byte-identical.')


if __name__ == '__main__':
    main()
