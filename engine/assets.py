"""Reuse published audio/art with local FFmpeg; never generate media or publish.

A render manifest may also name its canvas ('size', 720x1280 by default or a
1080x1920 master), the 'master_id' its channel cuts share, and a 'fontfile' and
'fontsdir' for FFmpeg builds with no default font, such as those on Windows (or
FULLTIME_FONT_FILE and FULLTIME_FONTS_DIR in the environment). With none of
these, a render is made exactly as before.

A manifest that also names 'layers' and 'instance' renders a take_clip in the
approved social kit (brand/social-kit/README.md): the kit's still layers, made by
brand/social-kit/take_clip.js, are composed over the published audio. Frame 0
holds for the first second, then one plate per caption segment, with the lime
progress fill drawn here, in the exact rectangle the layers record. Every check
above still applies, and the layers, the instance and the kit's lock are checked
too."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import textwrap
import urllib.parse
import urllib.request

from .records import atomic_json, fingerprint, now
from . import policy

STORAGE_HOST = 'hzadscrqmyilbisexvyz.supabase.co'
RENDERER_VERSION = 4
# Creative ID codes the renderer takes, and the platform each posts to. WEB is a private
# site preview: it has no brand identity, so it stays held for CHANNEL.
RENDER_PLATFORMS = {'TT': 'tiktok', 'YT': 'youtube', 'IG': 'instagram', 'TH': 'threads', 'FB': 'facebook',
                    'WC': 'whatsapp_channel', 'X': 'x', 'WEB': 'site'}
SIZES = {'720x1280': (720, 1280), '1080x1920': (1080, 1920)}
DEFAULT_SIZE = '720x1280'
MASTER_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9:._-]{0,79}$')   # the shape engine/pack.py accepts
REQUIRED_FIELDS = {'schema_version', 'creative_id', 'drop_id', 'segments', 'caption_alignment_verified'}
OPTIONAL_FIELDS = {'identity_ref', 'size', 'master_id', 'fontfile', 'fontsdir', 'layers', 'instance'}
FONT_ENV = {'fontfile': 'FULLTIME_FONT_FILE', 'fontsdir': 'FULLTIME_FONTS_DIR'}
# The approved social kit (The Switch). Its take_clip is a 1080x1920 master at 30 frames a second.
KIT_DIR = Path(__file__).resolve().parent.parent / 'brand' / 'social-kit'
KIT_SIZE = '1080x1920'
KIT_FPS = 30
FRAME0_SECONDS = 1.0
INSTANCE_FIELDS = {'schema_version', 'pundit', 'drop', 'home', 'away', 'score', 'date', 'shows', 'quote', 'captions', 'audio'}
LAYERS_FIELDS = {'schema_version', 'kit', 'revision', 'lock_sha256', 'instance', 'instance_sha256', 'size', 'width',
                 'height', 'time_label', 'frame0', 'plates', 'progress', 'rendered_at'}
LAYER_FILE = re.compile(r'^[a-z0-9][a-z0-9-]{0,40}\.png$')
HEX_COLOUR = re.compile(r'^#[0-9a-f]{6}$')
# The mid frame's ground plate (spec.md, "Mid frame"): the progress track sits inside it.
GROUND_PLATE = (64, 1068, 940, 1480)
KIT_LABELS = ('AI Pundit', 'Free pilot beta')
PLATE_LABEL = 'Made by AI from checked match facts'


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
    if ('layers' in manifest) != ('instance' in manifest):
        raise ValueError('a social kit render names both its layers folder and its instance')
    for key in ('layers', 'instance'):
        if key in manifest and (not isinstance(manifest[key], str) or not manifest[key].strip()):
            raise ValueError(f'{key} must be a path')
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
    if 'layers' in manifest:
        checked_kit(growth, manifest, verified, match, state)
    return verified, match, total


def lf_sha(path):
    """SHA-256 of a text file with CRLF read as LF, so a Windows checkout hashes the same."""
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def kit_lock(directory=None):
    """The approved social kit's LOCK.json with its own sha256. Refused if any locked file
    differs from the approved revision: a change needs a new revision Krish approves."""
    directory = Path(directory) if directory is not None else KIT_DIR
    lock = json.loads((directory / 'LOCK.json').read_text(encoding='utf-8'))
    changed = sorted(name for name, digest in lock['files'].items() if lf_sha(directory / name) != digest)
    if changed:
        raise ValueError('the social kit differs from its approved lock (' + ', '.join(changed) + '); '
                         'a change needs a new revision Krish approves')
    return {**lock, 'lock_sha256': lf_sha(directory / 'LOCK.json')}


def png_size(path):
    """(width, height) from a PNG header."""
    with open(path, 'rb') as handle:
        head = handle.read(24)
    if len(head) < 24 or head[:8] != b'\x89PNG\r\n\x1a\n' or head[12:16] != b'IHDR':
        raise ValueError('a layer is not a PNG')
    return struct.unpack('>II', head[16:24])


def kit_timeline(captions, duration, fps=KIT_FPS):
    """Frames for each layer: frame 0 for the first second, then one plate per caption from its
    start (the first from the end of frame 0) to the next caption's start, the last to the end."""
    marks = [0.0, FRAME0_SECONDS] + [c['start'] for c in captions[1:]] + [duration]
    frames = [int(round(mark * fps)) for mark in marks]
    counts = [b - a for a, b in zip(frames, frames[1:])]
    if any(count < 1 for count in counts):
        raise ValueError('each caption after the first must start after frame 0 and after the caption before it')
    return counts


def _copy_ok(growth, state, text):
    return not growth.problems({'platform': 'other', 'text': 'Caption: ' + text}, state)


def checked_kit(growth, manifest, verified, match, state):
    """The social kit's checks for a take_clip: the instance agrees with the published edition,
    its quote and captions are exact quotations, the layers are the ones take_clip.js recorded
    for this instance under the approved lock, and each carries its AI label. Returns the
    instance, the layers record, the layers folder, the lock and the frame counts."""
    if manifest.get('size') != KIT_SIZE:
        raise ValueError('a social kit take_clip is the 1080x1920 master: set size to 1080x1920')
    if len(verified) != 1:
        raise ValueError('a social kit take_clip is one published edition')
    segment, source = verified[0]
    local = Path(growth.LOCAL).resolve()
    instance_path = Path(manifest['instance']).resolve()
    folder = Path(manifest['layers']).resolve()
    if local not in instance_path.parents:
        raise ValueError('the instance must stay inside local/')
    if (local / 'brand-kit' / 'layers') not in folder.parents:
        raise ValueError('layers must stay inside local/brand-kit/layers/')
    instance = json.loads(instance_path.read_text(encoding='utf-8'))
    if not isinstance(instance, dict) or not INSTANCE_FIELDS <= set(instance) or set(instance) - INSTANCE_FIELDS - {'sample'}:
        raise ValueError('instance must have exactly the documented take_clip fields')
    if instance['schema_version'] != 1 or type(instance.get('sample', False)) is not bool:
        raise ValueError('instance must be schema_version 1, with sample true or false')
    if (instance['pundit'] != source['pundit'] or instance['drop'] != manifest['drop_id']
            or instance['home'] != match.get('home') or instance['away'] != match.get('away')
            or list(instance['score'] if isinstance(instance['score'], list) else []) != list(match.get('score') or [])
            or ('date' in match and instance['date'] != match['date'])):
        raise ValueError('instance does not name this published edition and its match')
    shows = instance['shows']
    if not isinstance(shows, list) or len(set(map(str, shows))) != len(shows) or set(shows) != set(match['pundits']):
        raise ValueError('instance shows must be exactly the AI Pundits published for this match')
    audio = instance['audio']
    if (not isinstance(audio, dict) or set(audio) != {'source_record', 'start_seconds', 'end_seconds'}
            or not isinstance(audio['source_record'], str)
            or Path(audio['source_record']).resolve() != Path(segment['source_record']).resolve()
            or audio['start_seconds'] != segment['start_seconds'] or audio['end_seconds'] != segment['end_seconds']):
        raise ValueError('instance audio must be the manifest segment of the published audio')
    transcript = normalise(source['transcript'])
    quote = instance['quote']
    if (not isinstance(quote, str) or not quote.strip() or len(quote.strip()) > 90 or '\n' in quote
            or normalise(quote) not in transcript or not _copy_ok(growth, state, quote)):
        raise ValueError('the frame 0 quote must be an exact transcript line of 90 characters or fewer that passes the copy checks')
    duration = segment['end_seconds'] - segment['start_seconds']
    captions, previous = instance['captions'], 0.0
    if not isinstance(captions, list) or not 1 <= len(captions) <= 60:
        raise ValueError('captions must be a list of one to sixty segments')
    for caption in captions:
        if not isinstance(caption, dict) or set(caption) != {'start', 'end', 'text'}:
            raise ValueError('each caption must be exactly {start, end, text}')
        start, end, text = caption['start'], caption['end'], caption['text']
        if type(start) not in (int, float) or type(end) not in (int, float) or not previous - 1e-9 <= start < end <= duration + 1e-6:
            raise ValueError('captions must run in order inside the clip')
        if (not isinstance(text, str) or not text.strip() or len(text) > 120 or any(ord(c) < 32 for c in text)
                or normalise(text) not in transcript or not _copy_ok(growth, state, text)):
            raise ValueError('each caption must be an exact transcript quotation that passes the copy checks')
        previous = end
    if normalise(' '.join(c['text'] for c in captions)) != normalise(segment['quote']):
        raise ValueError('the captions together must be exactly the segment quote')
    counts = kit_timeline(captions, duration)
    lock = kit_lock()
    record_path = folder / 'layers.json'
    if not record_path.is_file():
        raise ValueError('the layers folder has no layers.json: run brand/social-kit/take_clip.js for this instance')
    record = json.loads(record_path.read_text(encoding='utf-8'))
    if not isinstance(record, dict) or set(record) != LAYERS_FIELDS or record['schema_version'] != 1:
        raise ValueError('layers.json must have exactly the documented fields')
    if (record['revision'], record['lock_sha256']) != (lock['revision'], lock['lock_sha256']):
        raise ValueError('the layers were made under another social kit lock')
    if record['instance_sha256'] != sha(instance_path):
        raise ValueError('the layers were made for another instance')
    if (record['size'], record['width'], record['height']) != (KIT_SIZE, *SIZES[KIT_SIZE]):
        raise ValueError('the layers must be 1080x1920')
    plates = record['plates']
    if not isinstance(plates, list) or len(plates) != len(captions):
        raise ValueError('the layers need one plate per caption')
    names = set()
    for number, layer in enumerate([record['frame0']] + plates):
        if not isinstance(layer, dict) or not isinstance(layer.get('file'), str) or not LAYER_FILE.fullmatch(layer['file']):
            raise ValueError('each layer must be a PNG file in the layers folder')
        names.add(layer['file'])
        path = folder / layer['file']
        if not path.is_file() or sha(path) != layer.get('sha256') or path.stat().st_size != layer.get('bytes'):
            raise ValueError(f'layer {layer["file"]} is missing or changed since take_clip.js made it')
        if png_size(path) != SIZES[KIT_SIZE]:
            raise ValueError(f'layer {layer["file"]} is not 1080x1920')
        text = layer.get('text')
        if not isinstance(text, list) or not all(isinstance(x, str) for x in text):
            raise ValueError('each layer records the text it carries')
        joined = ' '.join(text)
        needed = KIT_LABELS + ((PLATE_LABEL,) if number else ()) + (('Sample line',) if instance.get('sample') else ())
        missing = [label for label in needed if label not in joined]
        if missing:
            raise ValueError(f'layer {layer["file"]} lacks ' + ', '.join(missing))
        if not _copy_ok(growth, state, joined):
            raise ValueError(f'layer {layer["file"]} does not pass the public-copy checks')
        if number and (layer.get('start'), layer.get('end'), layer.get('caption')) != (
                captions[number - 1]['start'], captions[number - 1]['end'], captions[number - 1]['text']):
            raise ValueError('each plate must carry its caption segment, in order')
    if len(names) != len(plates) + 1:
        raise ValueError('each layer must be its own file')
    progress = record['progress']
    if (not isinstance(progress, dict) or set(progress) != {'x', 'y', 'w', 'h', 'color'}
            or any(type(progress[k]) is not int for k in 'xywh') or not isinstance(progress['color'], str)
            or not HEX_COLOUR.fullmatch(progress['color'])):
        raise ValueError('the progress fill must be a whole-pixel rectangle and a #rrggbb colour')
    left, top, right, bottom = GROUND_PLATE
    if not (left <= progress['x'] and progress['x'] + progress['w'] <= right and top <= progress['y']
            and progress['y'] + progress['h'] <= bottom and progress['w'] >= 100 and progress['h'] >= 2):
        raise ValueError('the progress fill must sit inside the mid frame ground plate')
    return {'instance': instance, 'instance_path': instance_path, 'record': record, 'record_path': record_path,
            'folder': folder, 'lock': lock, 'counts': counts}


def kit_filters(counts, progress, duration):
    """Frame 0 and the plates in caption order, then the lime progress fill: a box in the exact
    track rectangle that grows with the audio, shown from the end of frame 0."""
    n = len(counts)
    x, y, w, h = progress['x'], progress['y'], progress['w'], progress['h']
    parts = [f'[{i}:v]format=rgb24,setsar=1,trim=end_frame={count},setpts=PTS-STARTPTS[l{i}]'
             for i, count in enumerate(counts)]
    parts.append(''.join(f'[l{i}]' for i in range(n)) + f'concat=n={n}:v=1:a=0[base]')
    parts.append('[base]split[b0][b1]')
    parts.append(f'[b1]crop={w}:{h}:{x}:{y}[track]')
    parts.append(f"[track][{n}:v]overlay=x='-w+floor(w*min(1,t/{duration}))':y=0:shortest=1[fill]")
    parts.append(f"[b0][fill]overlay=x={x}:y={y}:enable='gte(t,{FRAME0_SECONDS})',"
                 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p[v]')
    return ';'.join(parts)


def compose_kit(kit, segment, source, output, work):
    """The kit's take_clip, composed by FFmpeg from its layers over the published audio."""
    record, folder, counts = kit['record'], kit['folder'], kit['counts']
    duration = segment['end_seconds'] - segment['start_seconds']
    progress = record['progress']
    command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y']
    for layer in [record['frame0']] + record['plates']:
        command += ['-loop', '1', '-framerate', str(KIT_FPS), '-i', str(folder / layer['file'])]
    command += ['-f', 'lavfi', '-i', f'color=c=0x{progress["color"][1:]}:s={progress["w"]}x{progress["h"]}:r={KIT_FPS}:d={duration}',
                '-ss', str(segment['start_seconds']), '-t', str(duration), '-i', source['audio'],
                '-filter_complex', kit_filters(counts, progress, duration),
                '-map', '[v]', '-map', f'{len(counts) + 1}:a:0', '-t', str(duration), '-r', str(KIT_FPS),
                '-c:v', 'libx264', '-preset', 'veryfast', '-threads', '2', '-pix_fmt', 'yuv420p',
                '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709',
                '-c:a', 'aac', '-ar', '48000', '-ac', '2', '-movflags', '+faststart', str(Path(output).resolve())]
    result = subprocess.run(command, cwd=work, capture_output=True, timeout=300)
    if result.returncode:
        raise ValueError('social kit composition failed; check FFmpeg and the layers')
    captions = [f'{n}\n{timestamp(c["start"])} --> {timestamp(c["end"])}\n{textwrap.fill(c["text"], 36)}\n'
                for n, c in enumerate(kit['instance']['captions'], 1)]
    return captions


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
    kit = checked_kit(growth, manifest, segments, match, growth.load_state() or {}) if 'layers' in manifest else None
    key = {'renderer': RENDERER_VERSION, 'manifest': manifest}
    if font:
        key['fonts'] = font
    if kit:
        # The layer files and the instance can change under the same paths: the key names their contents.
        key['kit'] = {'lock': kit['lock']['lock_sha256'], 'layers': sha(kit['record_path']),
                      'instance': sha(kit['instance_path'])}
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
        if kit:
            captions = compose_kit(kit, segments[0][0], segments[0][1], output, work)
        for number, (segment, source) in enumerate([] if kit else segments, 1):
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
        if not kit:
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
    if kit and int(video.get('nb_frames') or 0) != sum(kit['counts']):
        raise ValueError('render failed the social kit timeline verification')
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
    if kit:
        record, lock = kit['record'], kit['lock']
        receipt['design'] = {'kit': lock['kit'], 'revision': lock['revision'], 'lock_sha256': lock['lock_sha256'],
                             'approval': lock['approval'], 'approved_on': lock['approved_on']}
        receipt['instance'] = str(kit['instance_path'])
        receipt['instance_sha256'] = sha(kit['instance_path'])
        receipt['layers'] = {'folder': str(kit['folder']), 'manifest_sha256': sha(kit['record_path']),
                             'frame0_sha256': record['frame0']['sha256'],
                             'plates_sha256': [plate['sha256'] for plate in record['plates']],
                             'progress': record['progress']}
        receipt['timeline'] = {'fps': KIT_FPS, 'frame0_seconds': FRAME0_SECONDS, 'frames': kit['counts']}
    atomic_json(receipt_path, receipt)
    return receipt


def render_checks(local, creative_id, media):
    """The pre-live checks a finished render proves for one pack item, read from its own
    receipt (local/renders/<creative_id>/*/render.json) when the item's video is that
    render, byte for byte: exact_quote and dimensions (the renderer refuses otherwise),
    media_hashes (the item names the render's SHA-256) and captions_aligned. Caption
    alignment comes from Krish's verdict, never self-declared (crew/motion_maker): he
    judges these exact bytes in G2, and only his no-edit "post it" counts toward
    readiness, so an edit or a reject (captions off included) never does. {} otherwise."""
    shas = {m.get('sha256') for m in media or () if isinstance(m, dict) and m.get('kind') == 'video'}
    folder = Path(local) / 'renders' / str(creative_id)
    for path in sorted(folder.glob('*/render.json')) if folder.is_dir() else ():
        try:
            receipt = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if receipt.get('creative_id') != creative_id or receipt.get('video_sha256') not in shas:
            continue
        return {'exact_quote': True, 'dimensions': True, 'media_hashes': True, 'captions_aligned': True}
    return {}
