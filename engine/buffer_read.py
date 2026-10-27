"""Read-only Buffer receipts for Full Time's own channels.

Krish publishes by hand in Buffer (ruling 3, 27 October 2026). This module only
reads: query() names the parameters a Claude session passes to Buffer's
list_posts, limited to the allowlisted Full Time channels, and receipts() turns
the posts that come back into permalink receipts for History.mark. It builds no
request, holds no credential, makes no network call and has no write verb.

The allowlist lives in the ignored local/buffer-channels.json, shaped like
examples/buffer-channels.example.json:

    {"product": "fulltime", "organization_id": "<24 hex>",
     "channels": {"<ref>": {"buffer_channel_id": "<24 hex, or null when Buffer
                            does not carry the channel>",
                            "service": "tiktok", "channel": "tiktok",
                            "account_scope": "brand",
                            "identity_ref": "fulltime-tiktok"}}}

"organization_id" names the Buffer organisation: list_posts requires it, so
query() refuses an allowlist without it. An optional "_about" holds a note, and
an entry may carry an optional "buffer_name", the channel's name as Buffer's
list_channels shows it. Every entry is a Full Time brand channel: a personal or
other-product channel is refused, and a post on any channel outside the
allowlist is dropped before any other field of it is read.

The allowlist alone cannot prove who owns a Buffer channel ID: Krish types
every field. So the code checks what it can (each entry's service fits its
channel, and one ID is never filed under two services or two brand identities),
and query() and receipts() take Buffer's own channel records (from
list_channels or get_channel) when the session has them, refusing an ID that
Buffer does not list or lists with another service or name.
"""
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlsplit

from . import policy

FILE = 'buffer-channels.json'
TOP_FIELDS = {'product', 'channels'}
OPTIONAL_TOP = {'organization_id', '_about'}
ENTRY_FIELDS = {'buffer_channel_id', 'service', 'channel', 'account_scope', 'identity_ref'}
OPTIONAL_ENTRY = {'buffer_name'}
BUFFER_ID = re.compile(r'^[a-f0-9]{24}$')
REF = re.compile(r'^[a-z][a-z0-9_-]{1,63}$')
SERVICE = re.compile(r'^[a-z][a-z0-9_]{1,39}$')
# The Buffer service each channel posts through. This catches an entry whose
# service does not fit its channel; it cannot tell whose account an ID is, which
# only Buffer's own channel record shows (_verified).
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
        if not ENTRY_FIELDS <= set(entry) <= ENTRY_FIELDS | OPTIONAL_ENTRY:
            out.append(f'{where} must have exactly ' + ', '.join(sorted(ENTRY_FIELDS))
                       + ', and optionally buffer_name')
        name = entry.get('buffer_name', '')
        if 'buffer_name' in entry and (not isinstance(name, str) or not name.strip() or len(name) > 100
                                       or any(ord(c) < 32 for c in name)):
            out.append(f'{where} buffer_name must be the channel name Buffer shows, on one line')
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
        elif channel in SERVICES and service not in SERVICES[channel]:
            out.append(f'{where} posts through {service}, but {channel} posts through '
                       + ' or '.join(SERVICES[channel]))
        identifier = entry.get('buffer_channel_id')
        if identifier is not None and (not isinstance(identifier, str) or not BUFFER_ID.fullmatch(identifier)):
            out.append(f'{where} buffer_channel_id must be a Buffer ID (24 hex characters) or null')
    return out + _shared_id_errors(channels) + policy.sensitive_errors(data)


def _shared_id_errors(channels):
    """One Buffer channel is one account on one service, so refs sharing an ID must agree.
    Reels and feed legitimately share one Instagram channel; TikTok and Shorts never do."""
    by_id = {}
    for ref, entry in sorted(channels.items()):
        identifier = entry.get('buffer_channel_id') if isinstance(entry, dict) else None
        if isinstance(identifier, str) and BUFFER_ID.fullmatch(identifier):
            by_id.setdefault(identifier, []).append((ref, entry))
    out = []
    for shared in by_id.values():
        refs = ', '.join(f'"{ref}"' for ref, _ in shared)
        for key, what in (('service', 'services'), ('identity_ref', 'brand identities'),
                          ('buffer_name', 'Buffer names')):
            values = {str(entry.get(key)) for _, entry in shared if key in entry}
            if len(values) > 1:
                out.append(f'channel refs {refs} share one Buffer channel ID under different {what} '
                           f'({", ".join(sorted(values))}): one Buffer channel is one account on one service')
                break
    return out


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


def _records(buffer_channels):
    """Buffer's own channel records by ID: a list_channels list (bare or under "channels"),
    or one get_channel record (bare or under "channel")."""
    found = buffer_channels
    if isinstance(found, dict):
        found = found.get('channels', found.get('channel', found))
    if isinstance(found, dict):
        found = [found]
    if not isinstance(found, list) or not found:
        raise ValueError("Buffer's channel records must be what list_channels or get_channel returned")
    out = {}
    for number, record in enumerate(found, start=1):
        identifier = record.get('id') if isinstance(record, dict) else None
        if not isinstance(identifier, str) or not BUFFER_ID.fullmatch(identifier) \
                or not isinstance(record.get('service'), str):
            raise ValueError(f"Buffer's channel record {number} needs its id and service")
        if identifier in out and out[identifier]['service'] != record['service']:
            raise ValueError("Buffer's channel records list one channel ID with two services")
        out[identifier] = record
    return out


def _handle(name):
    return name.strip().lstrip('@').casefold() if isinstance(name, str) else None


def _verified(allowlist, buffer_channels):
    """The checked allowlist, and, when Buffer's own channel records are given, every
    allowlisted ID matched against them: Buffer must list it, with the entry's service,
    and with the entry's buffer_name when the entry has one."""
    _checked(allowlist)
    if buffer_channels is None:
        return allowlist
    records, out = _records(buffer_channels), []
    for ref, entry in sorted(allowlist['channels'].items()):
        if entry['buffer_channel_id'] is None:
            continue                     # a channel Buffer does not carry: Krish posts it by hand
        record = records.get(entry['buffer_channel_id'])
        where = f'channel ref "{ref}"'
        if record is None:
            out.append(f"{where} is not among Buffer's channel records, so Buffer cannot show whose it is")
        elif record['service'].casefold() != entry['service']:
            out.append(f'{where} is {entry["service"]} in the allowlist, but Buffer says {record["service"]}')
        elif 'buffer_name' in entry and _handle(entry['buffer_name']) != _handle(record.get('name')):
            out.append(f'{where} is "{entry["buffer_name"]}" in the allowlist, but Buffer names it '
                       f'"{record.get("name")}"')
    if out:
        raise ValueError("the Buffer allowlist does not match Buffer's own channel records: " + '; '.join(out))
    return allowlist


def channel_ids(allowlist, buffer_channels=None):
    """The Buffer channel IDs this engine may read, sorted. With Buffer's own channel
    records (list_channels or get_channel), each ID must match its record."""
    entries = _verified(allowlist, buffer_channels)['channels'].values()
    return sorted({e['buffer_channel_id'] for e in entries if e['buffer_channel_id'] is not None})


def query(allowlist, buffer_channels=None):
    """The list_posts parameters: sent posts on the allowlisted channels only, in the
    allowlist's organisation. An empty channel list would read the whole organisation,
    and list_posts requires an organisation, so both are refused."""
    ids = channel_ids(allowlist, buffer_channels)
    if not ids:
        raise ValueError('no allowlisted channel is in Buffer: refusing an organisation-wide listing')
    if 'organization_id' not in allowlist:
        raise ValueError('the Buffer allowlist needs organization_id: list_posts requires it, and the '
                         'session must never pick an organisation itself')
    return {'channelIds': ids, 'status': ['sent'], 'first': 100, 'organizationId': allowlist['organization_id']}


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


def _words(text):
    """Text with its whitespace collapsed (and Unicode in one form), so an approved caption
    still matches after Buffer or the platform reflows its lines."""
    return ' '.join(unicodedata.normalize('NFC', text).split()) if isinstance(text, str) else ''


def _says(words, item):
    """True when the post's words carry the item's approved caption, whole."""
    caption = _words(item.get('caption'))
    if not caption:
        return False
    head = r'(?<!\w)' if re.match(r'\w', caption) else ''
    tail = r'(?!\w)' if re.search(r'\w$', caption) else ''
    return re.search(head + re.escape(caption) + tail, words) is not None


def _mentions(text, item):
    link, creative_id = item.get('link'), item.get('creative_id')
    if isinstance(link, str) and link and link in text:
        return True
    return (isinstance(creative_id, str) and bool(creative_id)
            and re.search(r'(?<![A-Za-z0-9_])' + re.escape(creative_id) + r'(?![A-Za-z0-9_])', text) is not None)


def _owner(post, pairs):
    """The index in pairs of the one item this post is the receipt for, or None.

    The post must be sent, on the item's own Buffer channel and service, with an https
    permalink, and its text must carry the item's caption. The tracked link or creative
    ID is extra evidence, never enough alone: when the text names any item's link or ID,
    it must name exactly this one, and without them the caption must belong to only this
    item on the channel. So one post is the receipt for one item at most."""
    on = [i for i, (_, entry) in enumerate(pairs) if entry and entry['buffer_channel_id'] == post['channelId']]
    if not on or post.get('status') != 'sent' or not _https(_permalink(post)):
        return None
    service = post.get('channelService')
    if service is None and isinstance(post.get('channel'), dict):
        service = post['channel'].get('service')
    if service is not None and str(service).casefold() != pairs[on[0]][1]['service']:
        return None
    words = _words(post.get('text'))
    said = [i for i in on if _says(words, pairs[i][0])]
    named = [i for i, (item, _) in enumerate(pairs) if _mentions(words, item)]
    if named:
        return named[0] if len(named) == 1 and named[0] in said else None
    return said[0] if len(said) == 1 else None


def receipts(posts, pack, allowlist, buffer_channels=None):
    """Permalink receipts for the pack's items: [{creative_id, channel, permalink,
    published_at}]. A post counts only on its item's own allowlisted channel, with
    status sent and an https permalink, when its text carries the item's approved
    caption (whitespace aside); see _owner for how the tracked link or creative ID
    settles which item. One post is the receipt for one item at most, and an item
    takes its first matching post. With Buffer's own channel records, every
    allowlisted ID must match its record first."""
    channels = _verified(allowlist, buffer_channels)['channels']
    allowed = set(channel_ids(allowlist))
    # Drop every post outside the allowlist first: only channelId is read from it.
    kept = [p for p in posts or [] if isinstance(p, dict) and isinstance(p.get('channelId'), str)
            and p.get('channelId') in allowed]
    items = pack.get('items') if isinstance(pack, dict) else None
    pairs = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        ref = item.get('channel_ref')
        entry = channels.get(ref) if isinstance(ref, str) else None
        usable = (isinstance(entry, dict) and entry.get('buffer_channel_id') is not None
                  and entry.get('channel') == item.get('channel'))
        pairs.append((item, entry if usable else None))
    owners = [_owner(post, pairs) for post in kept]
    out = []
    for index, (item, entry) in enumerate(pairs):
        post = next((p for p, owner in zip(kept, owners) if owner == index), None) if entry else None
        if post is None:
            continue
        moment = post.get('sentAt') or post.get('dueAt')
        out.append({'creative_id': item.get('creative_id'), 'channel': item.get('channel'),
                    'permalink': _permalink(post), 'published_at': moment if isinstance(moment, str) else None})
    return out
