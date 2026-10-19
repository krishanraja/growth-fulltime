"""Read-only check of the legacy packs read using the existing Actions secret; never log
credentials or packs. The growth engine protocol loop is growth.py cc (engine/control_center.py)."""

import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.control_center import opener  # the one Control Center transport: no redirects


def main():
    token = os.environ.get('GROWTH_ENGINE_TOKEN', '').strip()
    result = {'secret_configured': bool(token), 'authenticated_read': False}
    if not token:
        result['error'] = 'GROWTH_ENGINE_TOKEN is unavailable to this Actions run'
        print(json.dumps(result, sort_keys=True))
        return 2

    request = urllib.request.Request(
        'https://controlcenter.krishraja.com/api/growth/packs?days=1',
        headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'},
        method='GET',
    )
    try:
        with opener().open(request, timeout=25) as response:
            result['http_status'] = response.status
            payload = response.read(1_048_577)
        if len(payload) > 1_048_576:
            raise ValueError('response too large')
        data = json.loads(payload)
        result['authenticated_read'] = (
            isinstance(data, dict) and data.get('ok') is True
            and isinstance(data.get('packs'), list)
        )
        if result['authenticated_read']:
            result['fulltime_namespace_advertised'] = (
                isinstance(data.get('ventures'), list) and 'fulltime' in data['ventures']
            )
            result['write_readback'] = 'not_run'
        else:
            result['error'] = 'unexpected response shape'
    except urllib.error.HTTPError as error:
        result['http_status'] = error.code
        result['error'] = 'HTTP request refused; response body omitted'
    except (OSError, ValueError, urllib.error.URLError):
        result['error'] = 'request or JSON validation failed; details omitted'
    print(json.dumps(result, sort_keys=True))
    return 0 if result['authenticated_read'] else 1


if __name__ == '__main__':
    sys.exit(main())
