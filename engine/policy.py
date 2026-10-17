"""The owner's channel limits apply to held drafts as well as ready work."""
import re
import datetime as dt
import json
from pathlib import Path
from urllib.parse import urlsplit

VERSION = 'fulltime-brand-zero-cash-v1'
EXCLUDED = {'invite', 'linkedin', 'hn', 'producthunt', 'press', 'creator', 'ads', 'fpl'}
BRAND_CHANNELS = {'youtube', 'tiktok', 'instagram', 'x', 'reddit'}
INTERNAL = {'site', 'other'}
HOLDS = {'RAIL', 'RELEASE', 'CHANNEL', 'CONSENT', 'DATA', 'ASSETS', 'APPROVAL',
         'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7'}
PACK_FIELDS = {'schema_version', 'policy_version', 'pack_date', 'kind', 'venture',
               'fulltime_sha', 'headline', 'items', 'numbers', 'metrics', 'source',
               'link', 'observed_at', 'run_id', 'usage', 'report_id'}
ITEM_FIELDS = {'item_id', 'platform', 'creative_id', 'experiment_id', 'target_url',
               'target_name', 'why', 'text', 'needs', 'holds', 'account_scope',
               'identity_ref', 'contact_basis', 'consent_ref', 'sender',
               'distribution', 'drop_id', 'pundits', 'assets', 'estimated_minutes'}
USAGE_FIELDS = {'marketing_cash_gbp', 'model_calls', 'audio_generation_calls', 'model_spend_usd',
                'agent_spend_usd', 'hosting_spend_usd', 'elapsed_seconds', 'founder_minutes'}


def sensitive_errors(value):
    """Reject obvious credentials and private contact data in every nested field."""
    out = []
    if isinstance(value, dict):
        for nested in value.values():
            out.extend(sensitive_errors(nested))
    elif isinstance(value, list):
        for nested in value:
            out.extend(sensitive_errors(nested))
    elif isinstance(value, str):
        if any(x.lower() != 'krish@fulltime.fm' for x in re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', value)):
            out.append('private contact details are not accepted in growth records')
        if re.search(r'\bgh[pousr]_[A-Za-z0-9]{20,}|\bsk-[A-Za-z0-9_-]{20,}|\bBearer [A-Za-z0-9._-]{16,}|\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}', value):
            out.append('credential-like content is not accepted in growth records')
        if re.search(r'https?://[^\s]+[?&](?:token|api_key|apikey|authorization|email|recipient|jwt)=', value, re.I):
            out.append('credential or private-contact URL parameters are not accepted')
    return list(dict.fromkeys(out))


def holds(item):
    value = item.get('holds', [])
    out = list(value) if isinstance(value, list) else []
    if item.get('needs') and item['needs'] not in out:
        out.append(item['needs'])
    return out


def release_open(state):
    """A separate source-backed product decision is required; D1 is insufficient."""
    evidence = (state or {}).get('marketing_release') or {}
    return (evidence.get('verified') is True
            and evidence.get('fulltime_sha') == (state or {}).get('sha')
            and evidence.get('decision_heading') in (state or {}).get('decisions', [])
            and evidence.get('source_path') == 'docs/12-roadmap.md')


def identity_verified(identity, platform):
    if not isinstance(identity, dict):
        return False
    try:
        checked = dt.datetime.fromisoformat(identity.get('verified_at', '').replace('Z', '+00:00'))
        age = dt.datetime.now(dt.timezone.utc) - checked
        host = urlsplit(identity.get('source_url', '')).hostname or ''
        expected = {'youtube': ('youtube.com', 'youtu.be'), 'tiktok': ('tiktok.com',),
                    'instagram': ('instagram.com',), 'x': ('x.com', 'twitter.com'), 'reddit': ('reddit.com',)}[platform]
        source_ok = (identity['source_url'].startswith('https://')
                     and any(host == domain or host.endswith('.' + domain) for domain in expected))
        return (identity.get('verified') is True and identity.get('platform') == platform
                and identity.get('account_scope') == 'brand' and source_ok
                and dt.timedelta(minutes=-5) <= age <= dt.timedelta(days=30))
    except (ValueError, TypeError, KeyError):
        return False


def load_identities(local):
    path = Path(local) / 'brand-identities.json'
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if set(data) != {'product', 'identities'} or data['product'] != 'fulltime' or not isinstance(data['identities'], dict):
        raise ValueError('invalid product-scoped brand identity registry')
    return data['identities']


def errors(item, state=None):
    state = state or {}
    out = []
    platform = str(item.get('platform', '')).lower()
    unknown = set(item) - ITEM_FIELDS
    if unknown:
        out.append('unsupported item fields: ' + ', '.join(sorted(unknown)))
    if platform in EXCLUDED:
        out.append(f'{platform} is excluded by the current owner policy, including held drafts')
    if item.get('account_scope') == 'personal':
        out.append('personal social accounts and personal-network acquisition are excluded')
    if not isinstance(item.get('holds', []), list) or any(
            not isinstance(x, str) or x not in HOLDS for x in item.get('holds', [])):
        out.append('holds must be a list of documented gate codes')
    pending = holds(item)
    if platform in BRAND_CHANNELS:
        if item.get('account_scope') != 'brand':
            out.append('social work requires account_scope brand')
        identity = (state.get('brand_identities') or {}).get(item.get('identity_ref')) or {}
        verified = identity_verified(identity, platform)
        if not verified and 'CHANNEL' not in pending:
            out.append('unverified brand identity must be held for CHANNEL')
        if not release_open(state) and 'RELEASE' not in pending:
            out.append('public acquisition must be held for RELEASE until separately verified')
        if not any(m.get('fill', 0) >= 4 for m in state.get('rail') or []) and 'RAIL' not in pending:
            out.append('public work must be held for RAIL while no eligible match exists')
        if not (state.get('rulings') or {}).get('D7', {}).get('in_force') and 'CONSENT' not in pending:
            out.append('public acquisition must be held for CONSENT until its product review is closed')
    if platform == 'whatsapp':
        if item.get('distribution') != 'listener_initiated':
            out.append('WhatsApp is voluntary listener sharing only; no owner account or groups')
    if platform == 'email':
        if item.get('contact_basis') not in ('explicit_opt_in', 'inbound') or not item.get('consent_ref'):
            out.append('email needs an inbound or explicit opt-in basis and a non-identifying consent reference')
        if item.get('sender') != 'krish@fulltime.fm':
            out.append('email must use the product inbox sender')
        if item.get('target_name') or re.search(r'@|mailto:', item.get('target_url', ''), re.I):
            out.append('private recipient details must stay outside packs')
    if platform not in INTERNAL and item.get('target_name'):
        out.append('recipient names and handles are not needed in the active growth plan')
    if item.get('estimated_minutes') is not None and (
            type(item['estimated_minutes']) not in (int, float) or item['estimated_minutes'] < 0):
        out.append('estimated_minutes must be a non-negative number')
    return out


def pack_errors(pack):
    unknown = set(pack) - PACK_FIELDS
    out = ['unsupported pack fields: ' + ', '.join(sorted(unknown))] if unknown else []
    if pack.get('policy_version', VERSION) != VERSION:
        out.append('pack policy_version is not the current owner policy')
    usage = pack.get('usage') or {}
    if not isinstance(usage, dict):
        return out + ['usage must be a typed object']
    if set(usage) - USAGE_FIELDS:
        out.append('usage has unsupported fields')
    if usage.get('marketing_cash_gbp', 0) != 0:
        out.append('incremental marketing cash must be zero')
    import math
    if any(v is not None and (type(v) not in (int, float) or not math.isfinite(v) or v < 0) for v in usage.values()):
        out.append('usage values must be non-negative finite numbers or null')
    if pack.get('kind') in ('partners', 'launch'):
        out.append('partner and founder-launch jobs are inactive in this execution cycle')
    return out + sensitive_errors(pack)
