"""Reuse published audio/art with local FFmpeg; never generate media or publish."""
import hashlib
import json
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
RENDERER_VERSION = 2


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def probe(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                             '-of', 'json', str(path)], capture_output=True, text=True, timeout=30)
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


def checked_segments(growth, manifest):
    allowed = {'schema_version', 'creative_id', 'drop_id', 'segments', 'caption_alignment_verified'}
    if not allowed <= set(manifest) or set(manifest) - allowed - {'identity_ref'} or manifest['schema_version'] != 1:
        raise ValueError('manifest must have exactly the documented render fields')
    if type(manifest['caption_alignment_verified']) is not bool:
        raise ValueError('caption alignment verification must be an explicit boolean')
    if not growth.CREATIVE_ID.fullmatch(manifest['creative_id']):
        raise ValueError('render requires a stable creative ID')
    if not manifest['creative_id'].startswith(('YT_', 'WEB_')):
        raise ValueError('the initial renderer supports Full Time YouTube and private site previews')
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
        source = json.loads(source_path.read_text())
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
    manifest = json.loads(Path(manifest_path).read_text())
    segments, match, total = checked_segments(growth, manifest)
    root = Path(growth.LOCAL) / 'renders' / manifest['creative_id'] / fingerprint({'renderer': RENDERER_VERSION, 'manifest': manifest})[:16]
    root.mkdir(parents=True, exist_ok=True)
    output, receipt_path = root / 'clip.mp4', root / 'render.json'
    if receipt_path.exists():
        cached = json.loads(receipt_path.read_text())
        if (output.exists() and sha(output) == cached['video_sha256']
                and all(Path(cached[k]).exists() and sha(cached[k]) == cached.get(k + '_sha256')
                        for k in ('captions', 'thumbnail'))):
            return {**cached, 'reused': True}
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
            filters = ('[0:v]drawbox=x=50:y=240:w=620:h=360:color=0x1b3037:t=fill,'
                       'drawbox=x=50:y=240:w=620:h=5:color=0x98e76a:t=fill,'
                       'drawtext=textfile=brand.txt:expansion=none:fontcolor=0x98e76a:fontsize=24:x=(w-tw)/2:y=70,'
                       'drawtext=textfile=heading.txt:expansion=none:fontcolor=white:fontsize=36:x=(w-tw)/2:y=150,'
                       'drawtext=textfile=match.txt:expansion=none:fontcolor=white:fontsize=34:x=(w-tw)/2:y=300:line_spacing=12,'
                       'drawtext=textfile=score.txt:expansion=none:fontcolor=white:fontsize=88:x=(w-tw)/2:y=450,'
                       'drawtext=textfile=label.txt:expansion=none:fontcolor=white:fontsize=22:x=(w-tw)/2:y=1070,'
                       'subtitles=caption.ass[v]')
            command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                       '-f', 'lavfi', '-i', 'color=c=0x122126:s=720x1280:r=24', '-ss', str(segment['start_seconds']),
                       '-i', source['audio'], '-filter_complex', filters, '-map', '[v]', '-map', '1:a:0',
                       '-t', str(duration), '-c:v', 'libx264', '-preset', 'veryfast', '-threads', '2',
                       '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '48000', '-ac', '2', '-movflags', '+faststart', str(part)]
            result = subprocess.run(command, cwd=work, capture_output=True, timeout=120)
            if result.returncode:
                raise ValueError('local render failed; check FFmpeg filters and source media')
            parts.append(part)
            captions.append(f'{number}\n{timestamp(offset)} --> {timestamp(offset + duration)}\n{textwrap.fill(segment["quote"],36)}\n')
            offset += duration
        (work / 'parts.txt').write_text('\n'.join(f"file '{p.name}'" for p in parts))
        result = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '1',
                                 '-i', 'parts.txt', '-c', 'copy', '-movflags', '+faststart', str(output.resolve())],
                                cwd=work, capture_output=True, timeout=60)
        if result.returncode:
            raise ValueError('render concatenation failed')
    metadata = probe(output)
    video = next((x for x in metadata['streams'] if x['codec_type'] == 'video'), {})
    audio = next((x for x in metadata['streams'] if x['codec_type'] == 'audio'), {})
    if (video.get('width'), video.get('height')) != (720, 1280) or not audio or abs(float(metadata['format']['duration']) - total) > 1:
        raise ValueError('render failed size, duration or audio verification')
    (root / 'captions.srt').write_text('\n'.join(captions), encoding='utf-8')
    thumb = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(output),
                            '-frames:v', '1', '-update', '1', str(root / 'thumbnail.jpg')], capture_output=True, timeout=30)
    if thumb.returncode:
        raise ValueError('thumbnail extraction failed')
    state = growth.load_state()
    landing = growth.tracked(f'https://fulltime.fm/?drop={manifest["drop_id"]}&pundit={segments[0][1]["pundit"]}', manifest['creative_id'])
    holds = ['APPROVAL']
    if not policy.release_open(state):
        holds.append('RELEASE')
    identity = (state.get('brand_identities') or {}).get(manifest.get('identity_ref'))
    if not policy.identity_verified(identity, 'youtube'):
        holds.append('CHANNEL')
    if not (state.get('rulings') or {}).get('D1', {}).get('in_force'):
        holds.append('D1')
    if not (state.get('rulings') or {}).get('D7', {}).get('in_force'):
        holds.append('CONSENT')
    if match['fill'] < growth.RAIL_MIN:
        holds.append('RAIL')
    if not manifest['caption_alignment_verified']:
        holds.append('ASSETS')
    receipt = {'renderer_version': RENDERER_VERSION, 'creative_id': manifest['creative_id'], 'video': str(output), 'video_sha256': sha(output),
               'captions': str(root / 'captions.srt'), 'thumbnail': str(root / 'thumbnail.jpg'),
               'captions_sha256': sha(root / 'captions.srt'), 'thumbnail_sha256': sha(root / 'thumbnail.jpg'),
               'duration_seconds': float(metadata['format']['duration']), 'width': 720, 'height': 1280,
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
