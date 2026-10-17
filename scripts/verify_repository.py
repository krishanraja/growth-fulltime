"""Cheap repository contract, JSON and relative-document-link checks."""
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
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
if errors:
    print('\n'.join(errors));sys.exit(1)
print(f'Repository checks passed: {json_count} JSON files, {link_count} relative links, two consolidated jobs.')
