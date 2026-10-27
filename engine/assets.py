"""Reuse published audio/art with local FFmpeg; never generate media or publish.

A render manifest may also name its canvas ('size', 720x1280 by default or a
1080x1920 master), the 'master_id' its channel cuts share, and a 'fontfile' and
'fontsdir' for FFmpeg builds with no default font, such as those on Windows (or
FULLTIME_FONT_FILE and FULLTIME_FONTS_DIR in the environment). With none of
these, a render is made exactly as before."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import textwrap
import urllib.parse
import urllib.request

from .records import atomic_json, fingerprint, now
from . import policy

STORAGE_HOST = 'hzadscrqmyilbisexvyz.supabase.co'
RENDERER_VERSION = 3
# Creative ID codes the renderer takes, and the platform each posts to. WEB is a private
# site preview: it has no brand identity, so it stays held for CHANNEL.
RENDER_PLATFORMS = {'TT': 'tiktok', 'YT': 'youtube', 'IG': 'instagram', 'TH': 'threads', 'FB': 'facebook',
                    'WC': 'whatsapp_channel', 'X': 'x', 'WEB': 'site'}
SIZES = {'720x1280': (720, 1280), '1080x1920': (1080, 1920)}
DEFAULT_SIZE = '720x1280'
MASTER_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9:._-]{0,79}$')   # the shape engine/pack.py accepts
REQUIRED_FIELDS = {'schema_version', 'creative_id', 'drop_id', 'segments', 'caption_alignment_verified'}
OPTIONAL_FIELDS = {'identity_ref', 'size', 'master_id', 'fontfile', 'fontsdir'}
FONT_ENV = {'fontfile': 'FULLTIME_FONT_FILE', 'fontsdir': 'FULLTIME_FONTS_DIR'}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def probe(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                             '-of', 'json', str(path)], capture_output=True, text=True, encoding='utf-8', timeout=30)
    if result.returncode:
        raise ValueError('FFprobe could not read the asset')
    return json.loads(result.stdout)


def download(url, path, limit):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname != STORAGE_HOST or parsed.username or parsed.password or parsed.query:
        raise ValueError('asset must be an unsigned public URL on the product storage host')
    if not parsed.path.startswith('/storage/v1/object/public/'):
        raise ValueError('asset is not public product media')
    with urllib.request.build_opener(NoRedirect).open(url, timeout=30) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('asset exceeds the download size limit')
    Path(path).write_bytes(data)


def fetch(growth, drop, pundit):
    state = growth.load_state() or {}
    match = next((m for m in state.get('rail') or [] if m['drop'] == drop), None)
    if not match or pundit not in match['pundits']:
        raise ValueError('only an edition published on the synced rail can be downloaded')
    url = f'{growth.SITE}/api/public/drops/{drop}/variants/{pundit}'
    data = growth.http(url)
    variant = data.get('variant') or {}
    if (data.get('state') != 'published' or variant.get('drop_id') != drop
            or variant.get('pundit_id') != pundit or not variant.get('published_at')):
        raise ValueError('public endpoint did not verify the exact published edition')
    root = Path(growth.LOCAL) / 'assets' / drop / pundit
    root.mkdir(parents=True, exist_ok=True)
    audio, cover = root / 'audio.mp3', root / 'cover.png'
    download(variant['audio_url'], audio, 32 * 1024 * 1024)
    download(variant['share_image_url'], cover, 8 * 1024 * 1024)
    duration = float(probe(audio)['format']['duration'])
    if not 1 <= duration <= 7200:
        raise ValueError('unexpected published audio duration')
    transcript = variant.get('transcript') or variant.get('display_script')
    if not isinstance(transcript, str) or not transcript:
        raise ValueError('published edition has no transcript')
    record = {'schema_version': 1, 'drop_id': drop, 'pundit': pundit,
              'source_url': url, 'source_sha': state['sha'], 'fetched_at': now(),
              'audio': str(audio.resolve()), 'audio_sha256': sha(audio),
              'cover': str(cover.resolve()), 'cover_sha256': sha(cover),
              'duration_seconds': duration, 'transcript': transcript,
              'published_at': variant['published_at']}
    atomic_json(root / 'source.json', record)
    return {'source_record': str(root / 'source.json'), 'duration_seconds': duration,
            'published': True, 'generated_media_calls': 0}


def normalise(value):
    return re.sub(r'\s+', ' ', value).strip().casefold()


def render_platform(growth, creative_id):
    """The platform a creative ID renders for, or a refusal naming the codes the renderer takes."""
    matched = growth.CREATIVE_ID.fullmatch(creative_id) if isinstance(creative_id, str) else None
    if not matched:
        raise ValueError('render requires a stable creative ID')
    if matched.group(1) not in RENDER_PLATFORMS:
        raise ValueError('the renderer supports Full Time brand channels (TT, YT, IG, TH, FB, WC, X) '
                         'and private site previews (WEB)')
    return RENDER_PLATFORMS[matched.group(1)]


def fonts(manifest):
    """The drawtext font file and the subtitles fonts folder, from the manifest or else the
    environment, as absolute paths with forward slashes. Empty when neither is set, so FFmpeg
    finds its own fonts as before."""
    out = {}
    for key, env in FONT_ENV.items():
        value = manifest.get(key) or os.environ.get(env, '').strip()
        if not value:
            continue
        path = Path(value).expanduser().resolve()
        if not (path.is_file() if key == 'fontfile' else path.is_dir()):
            raise ValueError(f'{key} must be an existing {"font file" if key == "fontfile" else "folder"} on this machine')
        text = path.as_posix()
        if any(c in text for c in "'\\") or any(ord(c) < 32 for c in text):
            raise ValueError(f'{key} must be a path without quotes, backslashes or control characters')
        out[key] = text
    return out


def filter_path(text):
    """A path as an FFmpeg filter option value: quoted, with each colon escaped (C\\:/Windows/Fonts)."""
    return "'" + text.replace(':', '\\:') + "'"


def video_filters(size, font):
    """The card, labels and captions, laid out for 720x1280 and scaled to the canvas."""
    k = SIZES[size][0] / 720

    def px(value):
        return int(round(value * k))
    face = f':fontfile={filter_path(font["fontfile"])}' if font.get('fontfile') else ''
    folder = f':fontsdir={filter_path(font["fontsdir"])}' if font.get('fontsdir') else ''
    return (f'[0:v]drawbox=x={px(50)}:y={px(240)}:w={px(620)}:h={px(360)}:color=0x1b3037:t=fill,'
            f'drawbox=x={px(50)}:y={px(240)}:w={px(620)}:h={px(5)}:color=0x98e76a:t=fill,'
            f'drawtext=textfile=brand.txt:expansion=none{face}:fontcolor=0x98e76a:fontsize={px(24)}:x=(w-tw)/2:y={px(70)},'
            f'drawtext=textfile=heading.txt:expansion=none{face}:fontcolor=white:fontsize={px(36)}:x=(w-tw)/2:y={px(150)},'
            f'drawtext=textfile=match.txt:expansion=none{face}:fontcolor=white:fontsize={px(34)}:x=(w-tw)/2:y={px(300)}'
            f':line_spacing={px(12)},'
            f'drawtext=textfile=score.txt:expansion=none{face}:fontcolor=white:fontsize={px(88)}:x=(w-tw)/2:y={px(450)},'
            f'drawtext=textfile=label.txt:expansion=none{face}:fontcolor=white:fontsize={px(22)}:x=(w-tw)/2:y={px(1070)},'
            f'subtitles=caption.ass{folder}[v]')


def render_holds(growth, state, manifest, match, pundits):
    """The gate codes a render carries. CHANNEL is checked for the creative's own platform.
    Under ORGANIC a render is a take: no RELEASE, and RAIL is the per-take gate."""
    state = state or {}
    platform = render_platform(growth, manifest['creative_id'])
    rulings = state.get('rulings') or {}
    holds = ['APPROVAL']
    if policy.release_needed(state):
        holds.append('RELEASE')
    identity = (state.get('brand_identities') or {}).get(manifest.get('identity_ref'))
    if not policy.identity_verified(identity, platform):
        holds.append('CHANNEL')
    if not rulings.get('D1', {}).get('in_force'):
        holds.append('D1')
    if not rulings.get('D7', {}).get('in_force'):
        holds.append('CONSENT')
    # A render clips one or two exact editions: a take, never a whole-match post.
    take = {'platform': platform, 'drop_id': manifest['drop_id'], 'pundits': list(pundits), 'whole_match': False}
    if (policy.take_gate(take, state) if policy.organic_in_force(state) else match['fill'] < growth.RAIL_MIN):
        holds.append('RAIL')
    if not manifest['caption_alignment_verified']:
        holds.append('ASSETS')
    return holds


def checked_segments(growth, manifest):
    if (not isinstance(manifest, dict) or not REQUIRED_FIELDS <= set(manifest)
            or set(manifest) - REQUIRED_FIELDS - OPTIONAL_FIELDS or manifest['schema_version'] != 1):
        raise ValueError('manifest must have exactly the documented render fields')
    if type(manifest['caption_alignment_verified']) is not bool:
        raise ValueError('caption alignment verification must be an explicit boolean')
    render_platform(growth, manifest['creative_id'])
    if manifest.get('size', DEFAULT_SIZE) not in SIZES:
        raise ValueError('size must be ' + ' or '.join(SIZES))
    if 'master_id' in manifest and (not isinstance(manifest['master_id'], str)
                                    or not MASTER_ID.fullmatch(manifest['master_id'])):
        raise ValueError('master_id must name the master this cut comes from')
    for key in FONT_ENV:
        if key in manifest and (not isinstance(manifest[key], str) or not manifest[key].strip()):
            raise ValueError(f'{key} must be a path')
    fonts(manifest)
    segments = manifest['segments']
    if not isinstance(segments, list) or not 1 <= len(segments) <= 2:
        raise ValueError('render one published edition or two distinct editions of the same match')
    state = growth.load_state() or {}
    match = next((x for x in state.get('rail') or [] if x['drop'] == manifest['drop_id']), None)
    if not match:
        raise ValueError('render match is not on the current rail')
    verified, pundits = [], set()
    asset_root = (Path(growth.LOCAL) / 'assets').resolve()
    total = 0
    for segment in segments:
        if set(segment) != {'source_record', 'start_seconds', 'end_seconds', 'quote'}:
            raise ValueError('segment must contain a source record, exact bounds and a transcript quote')
        source_path = Path(segment['source_record']).resolve()
        if asset_root not in source_path.parents:
            raise ValueError('source records must remain inside local/assets/')
        source = json.loads(source_path.read_text(encoding='utf-8'))
        pundit = source.get('pundit')
        expected_url = f'{growth.SITE}/api/public/drops/{manifest["drop_id"]}/variants/{pundit}'
        if (source.get('drop_id') != manifest['drop_id'] or pundit not in match['pundits']
                or source.get('source_url') != expected_url or not source.get('published_at')):
            raise ValueError('segment is not a published edition of the intended match')
        if pundit in pundits:
            raise ValueError('two-minds clips require two different AI Pundits')
        pundits.add(pundit)
        for kind in ('audio', 'cover'):
            path = Path(source[kind]).resolve()
            if asset_root not in path.parents or sha(path) != source[kind + '_sha256']:
                raise ValueError('source asset changed or is outside local/assets/')
        start, end = segment['start_seconds'], segment['end_seconds']
        if type(start) not in (int, float) or type(end) not in (int, float) or not 0 <= start < end <= source['duration_seconds']:
            raise ValueError('segment is outside the source audio')
        if not 3 <= end - start <= 20:
            raise ValueError('each excerpt must be between three and twenty seconds')
        quote = segment['quote']
        if not isinstance(quote, str) or not quote.strip() or normalise(quote) not in normalise(source['transcript']):
            raise ValueError('caption is not an exact quotation from the published transcript')
        if len(quote) > 400 or '-->' in quote or any(x in quote for x in ('\n', '{', '}', '\\')):
            raise ValueError('use a short single-line quotation without subtitle control syntax')
        if growth.problems({'platform': 'other', 'text': 'Caption: ' + quote}, state):
            raise ValueError('the transcript excerpt does not pass the public-copy checks')
        total += end - start
        verified.append((segment, source))
    if total > 30:
        raise ValueError('the combined clip must be thirty seconds or shorter')
    return verified, match, total


def timestamp(seconds):
    millis = round(seconds * 1000)
    return f'{millis//3600000:02}:{millis//60000%60:02}:{millis//1000%60:02},{millis%1000:03}'


def render(growth, manifest_path):
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        raise ValueError('local FFmpeg and FFprobe are required')
    manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    segments, match, total = checked_segments(growth, manifest)
    size = manifest.get('size', DEFAULT_SIZE)
    width, height = SIZES[size]
    font = fonts(manifest)
    key = {'renderer': RENDERER_VERSION, 'manifest': manifest}
    if font:
        key['fonts'] = font
    root = Path(growth.LOCAL) / 'renders' / manifest['creative_id'] / fingerprint(key)[:16]
    root.mkdir(parents=True, exist_ok=True)
    output, receipt_path = root / 'clip.mp4', root / 'render.json'
    if receipt_path.exists():
        cached = json.loads(receipt_path.read_text(encoding='utf-8'))
        if (output.exists() and sha(output) == cached['video_sha256']
                and all(Path(cached[k]).exists() and sha(cached[k]) == cached.get(k + '_sha256')
                        for k in ('captions', 'thumbnail'))):
            # The file is the same; the gates are today's, never the ones it was first made under.
            state = growth.load_state() or {}
            return {**cached, 'holds': render_holds(growth, state, manifest, match, [s['pundit'] for _, s in segments]),
                    'source_sha': state.get('sha'), 'reused': True}
    captions, offset = [], 0.0
    with tempfile.TemporaryDirectory(prefix='fulltime-render-') as temporary:
        work = Path(temporary)
        parts = []
        for number, (segment, source) in enumerate(segments, 1):
            duration = segment['end_seconds'] - segment['start_seconds']
            subtitle = f'1\n{timestamp(0)} --> {timestamp(duration)}\n' + textwrap.fill(segment['quote'], 36) + '\n'
            (work / 'caption.srt').write_text(subtitle, encoding='utf-8')
            ass = ('[Script Info]\nScriptType: v4.00+\nPlayResX: 720\nPlayResY: 1280\nWrapStyle: 2\n'
                   '[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n'
                   'Style: Default,DejaVu Sans,34,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,0,2,70,70,355,1\n'
                   '[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
                   'Dialogue: 0,0:00:00.00,' + f'0:00:{duration:05.2f}' + ',Default,,0,0,0,,'
                   + textwrap.fill(segment['quote'], 32).replace('\n', r'\N') + '\n')
            (work / 'caption.ass').write_text(ass, encoding='utf-8')
            (work / 'heading.txt').write_text(growth.PUNDITS[source['pundit']], encoding='utf-8')
            (work / 'label.txt').write_text('Full Time | AI-written, synthetic voices', encoding='utf-8')
            (work / 'brand.txt').write_text('FULL TIME', encoding='utf-8')
            (work / 'match.txt').write_text(textwrap.fill(match['home'] + ' v ' + match['away'], 28), encoding='utf-8')
            (work / 'score.txt').write_text(str(match['score'][0]) + '-' + str(match['score'][1]), encoding='utf-8')
            part = work / f'part{number}.mp4'
            filters = video_filters(size, font)
            command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                       '-f', 'lavfi', '-i', f'color=c=0x122126:s={size}:r=24', '-ss', str(segment['start_seconds']),
                       '-i', source['audio'], '-filter_complex', filters, '-map', '[v]', '-map', '1:a:0',
                       '-t', str(duration), '-c:v', 'libx264', '-preset', 'veryfast', '-threads', '2',
                       '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '48000', '-ac', '2', '-movflags', '+faststart', str(part)]
            result = subprocess.run(command, cwd=work, capture_output=True, timeout=120)
            if result.returncode:
                raise ValueError('local render failed; check FFmpeg filters and source media')
            parts.append(part)
            captions.append(f'{number}\n{timestamp(offset)} --> {timestamp(offset + duration)}\n{textwrap.fill(segment["quote"],36)}\n')
            offset += duration
        (work / 'parts.txt').write_text('\n'.join(f"file '{p.name}'" for p in parts), encoding='utf-8')
        result = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '1',
                                 '-i', 'parts.txt', '-c', 'copy', '-movflags', '+faststart', str(output.resolve())],
                                cwd=work, capture_output=True, timeout=60)
        if result.returncode:
            raise ValueError('render concatenation failed')
    metadata = probe(output)
    video = next((x for x in metadata['streams'] if x['codec_type'] == 'video'), {})
    audio = next((x for x in metadata['streams'] if x['codec_type'] == 'audio'), {})
    if (video.get('width'), video.get('height')) != (width, height) or not audio or abs(float(metadata['format']['duration']) - total) > 1:
        raise ValueError('render failed size, duration or audio verification')
    (root / 'captions.srt').write_text('\n'.join(captions), encoding='utf-8')
    thumb = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(output),
                            '-frames:v', '1', '-update', '1', str(root / 'thumbnail.jpg')], capture_output=True, timeout=30)
    if thumb.returncode:
        raise ValueError('thumbnail extraction failed')
    state = growth.load_state()
    landing = growth.tracked(f'https://fulltime.fm/?drop={manifest["drop_id"]}&pundit={segments[0][1]["pundit"]}', manifest['creative_id'])
    holds = render_holds(growth, state, manifest, match, [source['pundit'] for _, source in segments])
    receipt = {'renderer_version': RENDERER_VERSION, 'creative_id': manifest['creative_id'],
               'platform': render_platform(growth, manifest['creative_id']), 'master_id': manifest.get('master_id'),
               'video': str(output), 'video_sha256': sha(output),
               'captions': str(root / 'captions.srt'), 'thumbnail': str(root / 'thumbnail.jpg'),
               'captions_sha256': sha(root / 'captions.srt'), 'thumbnail_sha256': sha(root / 'thumbnail.jpg'),
               'duration_seconds': float(metadata['format']['duration']), 'size': size, 'width': width, 'height': height,
               'fonts': font or None,
               'source_sha': state['sha'], 'drop_id': manifest['drop_id'],
               'pundits': [x[1]['pundit'] for x in segments], 'landing_url': landing,
               'segments': [{'pundit': source['pundit'], 'start_seconds': segment['start_seconds'],
                             'end_seconds': segment['end_seconds'], 'quote': segment['quote'],
                             'source_url': source['source_url'], 'source_sha': source['source_sha'],
                             'published_at': source['published_at'], 'audio_sha256': source['audio_sha256']}
                            for segment, source in segments],
               'holds': holds, 'generated_media_calls': 0, 'marketing_cash_gbp': 0,
               'publication_status': 'private_preview', 'reused': False}
    atomic_json(receipt_path, receipt)
    return receipt
