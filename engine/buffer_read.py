"""Read-only Buffer receipts for Full Time's own channels.

Krish publishes by hand in Buffer (ruling 3, 27 October 2026). This module only
reads: query() names the parameters a Claude session passes to Buffer's
list_posts, limited to the allowlisted Full Time channels, and receipts() turns
the posts that come back into permalink receipts for History.mark. It builds no
request, holds no credential, makes no network call and has no write verb.

The allowlist lives in the ignored local/buffer-channels.json, shaped like
examples/buffer-channels.example.json:

    {"product": "fulltime",
     "channels": {"<ref>": {"buffer_channel_id": "<24 hex, or null when Buffer
                            does not carry the channel>",
                            "service": "tiktok", "channel": "tiktok",
                            "account_scope": "brand",
                            "identity_ref": "fulltime-tiktok"}}}

An optional "organization_id" names the Buffer organisation for list_posts,
and an optional "_about" holds a note. Every entry is a Full Time brand
channel: a personal or other-product channel is refused, and a post on any
channel outside the allowlist is dropped before any other field of it is read.
"""
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from . import policy

FILE = 'buffer-channels.json'
TOP_FIELDS = {'product', 'channels'}
OPTIONAL_TOP = {'organization_id', '_about'}
ENTRY_FIELDS = {'buffer_channel_id', 'service', 'channel', 'account_scope', 'identity_ref'}
BUFFER_ID = re.compile(r'^[a-f0-9]{24}$')
REF = re.compile(r'^[a-z][a-z0-9_-]{1,63}$')
SERVICE = re.compile(r'^[a-z][a-z0-9_]{1,39}$')
# The Buffer service each channel posts through, so a channel ID cannot be
# filed under the wrong channel by mistake.
SERVICES = {'tiktok': ('tiktok',), 'ig_reels': ('instagram',), 'ig_feed': ('instagram',),
            'yt_shorts': ('youtube',), 'threads': ('threads',), 'x': ('twitter', 'x'),
            'facebook': ('facebook',), 'whatsapp_channel': ('whatsapp',)}


def allowlist_errors(data):
    """Every reason this allowlist cannot be used, in plain words."""
    from .spec import CHANNELS
    if not isinstance(data, dict):
        return ['the Buffer allowlist must be a JSON object']
    out = []
    missing = TOP_FIELDS - set(data)
    if missing:
        out.append('the Buffer allowlist needs ' + ', '.join(sorted(missing)))
    unknown = set(data) - TOP_FIELDS - OPTIONAL_TOP
    if unknown:
        out.append('unsupported allowlist fields: ' + ', '.join(sorted(unknown)))
    if data.get('product') != 'fulltime':
        out.append('the Buffer allowlist must be scoped to product "fulltime"')
    if 'organization_id' in data and not BUFFER_ID.fullmatch(str(data['organization_id'])):
        out.append('organization_id must be a Buffer ID (24 hex characters)')
    if '_about' in data and not isinstance(data['_about'], str):
        out.append('_about must be text')
    channels = data.get('channels')
    if not isinstance(channels, dict) or not channels:
        return out + ['channels must name at least one Full Time brand channel']
    for ref, entry in channels.items():
        where = f'channel ref "{ref}"'
        if not REF.fullmatch(ref) or BUFFER_ID.fullmatch(ref) or ref.isdigit():
            out.append(f'{where} must be a short lowercase name, never a raw platform ID')
        if not isinstance(entry, dict):
            out.append(f'{where} must be an object')
            continue
        if set(entry) != ENTRY_FIELDS:
            out.append(f'{where} must have exactly ' + ', '.join(sorted(ENTRY_FIELDS)))
        if entry.get('account_scope') != 'brand':
            out.append(f'{where} is not a Full Time brand channel (personal and other channels are refused)')
        channel = entry.get('channel')
        if channel not in CHANNELS:
            out.append(f'{where} names channel "{channel}", which is not one of ' + ', '.join(CHANNELS))
        if not isinstance(entry.get('identity_ref'), str) or not REF.fullmatch(entry.get('identity_ref')):
            out.append(f'{where} needs an identity_ref naming its brand identity record')
        service = entry.get('service')
        if not isinstance(service, str) or not SERVICE.fullmatch(service):
            out.append(f'{where} needs a Buffer service name')
        identifier = entry.get('buffer_channel_id')
        if identifier is not None:
            if not isinstance(identifier, str) or not BUFFER_ID.fullmatch(identifier):
                out.append(f'{where} buffer_channel_id must be a Buffer ID (24 hex characters) or null')
            elif channel in SERVICES and service not in SERVICES[channel]:
                out.append(f'{where} posts through {service}, but {channel} posts through '
                           + ' or '.join(SERVICES[channel]))
    return out + policy.sensitive_errors(data)


def load_allowlist(local_dir):
    """The validated allowlist from local_dir/buffer-channels.json."""
    path = Path(local_dir) / FILE
    if not path.exists():
        raise ValueError(f'no Buffer allowlist at {path}: copy examples/buffer-channels.example.json '
                         'there and fill in the Full Time channel IDs')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except ValueError as error:
        raise ValueError(f'the Buffer allowlist at {path} is not valid JSON') from error
    errors = allowlist_errors(data)
    if errors:
        raise ValueError('the Buffer allowlist was refused: ' + '; '.join(errors))
    return data


def _checked(allowlist):
    errors = allowlist_errors(allowlist)
    if errors:
        raise ValueError('the Buffer allowlist was refused: ' + '; '.join(errors))
    return allowlist


def channel_ids(allowlist):
    """The Buffer channel IDs this engine may read, sorted."""
    entries = _checked(allowlist)['channels'].values()
    return sorted({e['buffer_channel_id'] for e in entries if e['buffer_channel_id'] is not None})


def query(allowlist):
    """The list_posts parameters: sent posts on the allowlisted channels only.
    An empty channel list would read the whole organisation, so it is refused."""
    ids = channel_ids(allowlist)
    if not ids:
        raise ValueError('no allowlisted channel is in Buffer: refusing an organisation-wide listing')
    params = {'channelIds': ids, 'status': ['sent'], 'first': 100}
    if 'organization_id' in allowlist:
        params['organizationId'] = allowlist['organization_id']
    return params


def _permalink(post):
    for key in ('permalink', 'externalLink'):
        value = post.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _https(url):
    if not isinstance(url, str) or re.search(r'\s', url):
        return False
    parts = urlsplit(url)
    return (parts.scheme == 'https' and bool(parts.hostname) and not parts.username
            and not parts.password and not policy.sensitive_errors(url))


def _mentions(text, item):
    link, creative_id = item.get('link'), item.get('creative_id')
    if isinstance(link, str) and link and link in text:
        return True
    return (isinstance(creative_id, str) and bool(creative_id)
            and re.search(r'(?<![A-Za-z0-9_])' + re.escape(creative_id) + r'(?![A-Za-z0-9_])', text) is not None)


def receipts(posts, pack, allowlist):
    """Permalink receipts for the pack's items: [{creative_id, channel, permalink,
    published_at}]. A post counts only on its item's own allowlisted channel, with
    status sent and an https permalink, when its text carries the item's tracked
    link or creative ID."""
    channels = _checked(allowlist)['channels']
    allowed = set(channel_ids(allowlist))
    # Drop every post outside the allowlist first: only channelId is read from it.
    kept = [p for p in posts or [] if isinstance(p, dict) and isinstance(p.get('channelId'), str)
            and p.get('channelId') in allowed]
    out = []
    items = pack.get('items') if isinstance(pack, dict) else None
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        ref = item.get('channel_ref')
        entry = channels.get(ref) if isinstance(ref, str) else None
        if (not isinstance(entry, dict) or entry.get('buffer_channel_id') is None
                or entry.get('channel') != item.get('channel')):
            continue
        for post in kept:
            if post['channelId'] != entry['buffer_channel_id'] or post.get('status') != 'sent':
                continue
            text = post.get('text') if isinstance(post.get('text'), str) else ''
            permalink = _permalink(post)
            if not _mentions(text, item) or not _https(permalink):
                continue
            moment = post.get('sentAt') or post.get('dueAt')
            out.append({'creative_id': item.get('creative_id'), 'channel': item.get('channel'),
                        'permalink': permalink, 'published_at': moment if isinstance(moment, str) else None})
            break
    return out
