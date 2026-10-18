#!/usr/bin/env python3
"""Deterministic adapter for existing 24-frame art. Never generates new poses."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import math
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))

def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def imaging():
    try:
        from PIL import Image, ImageOps
        return Image, ImageOps
    except ImportError as exc:
        raise RuntimeError('Build/visual validation requires Pillow. Run: python -m pip install Pillow') from exc

def normalized(im):
    """Preserve all visible pixels and alpha; zero hidden RGB in transparent pixels."""
    im = im.convert('RGBA')
    raw = bytearray(im.tobytes())
    for p in range(0, len(raw), 4):
        if raw[p + 3] == 0:
            raw[p:p + 3] = b'\0\0\0'
    return imaging()[0].frombytes('RGBA', im.size, bytes(raw))

def import_zip(archive: Path):
    Image, _ = imaging()
    with zipfile.ZipFile(archive) as z:
        candidates = [n for n in z.namelist() if n.endswith('/manifest.json')]
        if len(candidates) != 1:
            raise ValueError('Expected exactly one source manifest.json')
        source_manifest = json.loads(z.read(candidates[0]))
        prefix = candidates[0][:-len('manifest.json')]
        if source_manifest.get('frames_per_action') != 24:
            raise ValueError('Expected 24 frames per action')
        result = {'schema': 1, 'source_archive_sha256': sha(archive.read_bytes()),
                  'source_archive_name': archive.name, 'cell': [320, 320],
                  'grid': [6, 4], 'frames_per_action': 24, 'outfits': []}
        for outfit in source_manifest['outfits']:
            oid = outfit['id']
            if oid not in {'01_knit', '02_cape', '03_whale'}:
                raise ValueError(f'Unexpected outfit {oid!r}')
            output = {'id': oid, 'name': outfit['name'], 'actions': []}
            for action in outfit['actions']:
                aid = action['id']
                if not aid[:2].isdigit() or '/' in aid or '\\' in aid:
                    raise ValueError('Invalid source action name')
                if len(action['frames']) != 24:
                    raise ValueError('Source frame list must contain exactly 24 frames')
                sheet = Image.new('RGBA', (1920, 1280))
                hashes = []
                for i, name in enumerate(action['frames']):
                    with Image.open(io.BytesIO(z.read(prefix + name))) as image:
                        frame = normalized(image)
                    if frame.size != (320, 320) or not frame.getchannel('A').getbbox():
                        raise ValueError(f'Invalid frame: {name}')
                    hashes.append(sha(frame.tobytes()))
                    sheet.paste(frame, ((i % 6) * 320, (i // 6) * 320))
                relative = f'assets/source/{oid}/{aid}.webp'
                dest = ROOT / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                sheet.save(dest, format='WEBP', lossless=True, exact=True, method=4)
                # Verify that the compact source keeps every normalized source frame.
                reopened = Image.open(dest).convert('RGBA')
                for i, expected in enumerate(hashes):
                    x, y = (i % 6) * 320, (i // 6) * 320
                    if sha(reopened.crop((x, y, x+320, y+320)).tobytes()) != expected:
                        raise ValueError('Lossless source round-trip failed')
                output['actions'].append({'id': aid, 'name': action['name'], 'fps': action['fps'],
                    'loop': action['loop'], 'sheet': relative, 'frame_hashes': hashes,
                    'sheet_sha256': sha(dest.read_bytes())})
            result['outfits'].append(output)
        write_json(ROOT / 'assets/source/manifest.json', result)
    print('Imported 27 lossless source sheets; all 648 frame hashes verified.')

def source_frames(outfit):
    Image, _ = imaging()
    result = {}
    for action in outfit['actions']:
        sheet = Image.open(ROOT / action['sheet']).convert('RGBA')
        result[action['id']] = [sheet.crop(((i % 6)*320, (i//6)*320,
                                         (i%6+1)*320, (i//6+1)*320)) for i in range(24)]
    return result

def put_cell(frame, scale: float, mirror=False):
    Image, ImageOps = imaging()
    # Whole-canvas transformation with a fixed ground anchor preserves the jump arc.
    if mirror:
        frame = ImageOps.mirror(frame)
    side = round(320 * scale)
    resized = frame.resize((side, side), Image.Resampling.LANCZOS)
    x = round(96 - 160 * side / 320)
    y = round(194 - 292 * side / 320)
    cell = Image.new('RGBA', (192, 208))
    cell.paste(resized, (x, y))
    return normalized(cell)

def get_scale(frames):
    left, right, top, bottom = 160, 160, 292, 292
    for group in frames.values():
        for f in group:
            b = f.getchannel('A').getbbox()
            left, right = min(left, b[0]), max(right, b[2])
            top, bottom = min(top, b[1]), max(bottom, b[3])
    # 10+ pixels on each horizontal edge; 12 pixels above, 8 pixels below.
    return min(0.76, 84 / max(160-left, right-160), 180 / max(1, 292-top),
               6 / max(1, bottom-292))

def build():
    Image, _ = imaging()
    source = load(ROOT / 'assets/source/manifest.json')
    config = load(ROOT / 'config.json')
    source_by_id = {o['id']: o for o in source['outfits']}
    mappings = {'contract': config['contract'], 'pets': []}
    # Native packages intentionally keep the legacy four-field manifest.
    for pet in config['pets']:
        frames = source_frames(source_by_id[pet['source_outfit']])
        scale = get_scale(frames)
        atlas = Image.new('RGBA', (1536, 1872))
        records = []
        for row in config['rows']:
            selected = row['frames']
            action = row['source_action']
            cells = [put_cell(frames[action][i], scale, row.get('mirror', False)) for i in selected]
            for c, image in enumerate(cells):
                atlas.paste(image, (c*192, row['row']*208))
            records.append({**row, 'source_sheet': f"assets/source/{pet['source_outfit']}/{action}.webp"})
            # GIF previews have a deliberately opaque light background, never installed.
            previews = []
            for cell in cells:
                bg = Image.new('RGB', cell.size, (242, 244, 250))
                bg.paste(cell, mask=cell.getchannel('A'))
                previews.append(bg)
            gif = ROOT / 'assets/previews' / pet['id'] / f"{row['state']}.gif"
            gif.parent.mkdir(parents=True, exist_ok=True)
            previews[0].save(gif, save_all=True, append_images=previews[1:],
                             duration=row['durations_ms'], loop=0, disposal=2)
        dest = ROOT / 'pets' / pet['id']
        dest.mkdir(parents=True, exist_ok=True)
        atlas.save(dest/'spritesheet.webp', format='WEBP', lossless=True, exact=True, method=4)
        write_json(dest/'pet.json', {k: pet[k] for k in ['id', 'displayName', 'description']} |
                   {'spritesheetPath': 'spritesheet.webp'})
        mappings['pets'].append({'id': pet['id'], 'source_outfit': pet['source_outfit'],
                                'scale': scale, 'anchor': [96, 194], 'rows': records})
    write_json(ROOT / 'docs/animation-map.json', mappings)
    checksums = {p.relative_to(ROOT).as_posix(): sha(p.read_bytes())
                 for p in sorted((ROOT/'pets').rglob('*')) if p.is_file()}
    write_json(ROOT/'checksums.json', checksums)
    write_json(ROOT/'qa/asset-validation.json', validate())
    # Data script avoids file:// fetch restrictions and works completely offline.
    (ROOT/'preview-data.js').write_text('window.PET_DATA = ' + json.dumps(
        {'config': config, 'source': source}, ensure_ascii=False) + ';\n', encoding='utf-8')
    print('Built three native packages and 27 native-state GIF previews.')

def validate():
    Image, _ = imaging()
    config = load(ROOT/'config.json')
    report = {'schema': 1, 'native_atlas': [1536,1872], 'cell': [192,208],
              'target_contract': 'legacy-v1-8x9', 'codex_desktop_runtime_tested': False,
              'pets': [], 'errors': [], 'warnings': [
                'V1 compatibility atlas: no V2 16-direction look poses.',
                'Left movement is a mirrored right sequence; asymmetric accessories swap sides.',
                'Working/review reuse different portions of idle art; these are not newly drawn task actions.',
                'Native client state triggers and timing have not been tested on a real Codex Desktop instance.'
              ]}
    expected_sums = load(ROOT/'checksums.json')
    for pet in config['pets']:
        folder = ROOT/'pets'/pet['id']
        manifest = load(folder/'pet.json')
        if set(manifest) != {'id','displayName','description','spritesheetPath'}:
            report['errors'].append(f"{pet['id']}: non-contract manifest fields")
        if manifest.get('id') != pet['id'] or manifest.get('spritesheetPath') != 'spritesheet.webp':
            report['errors'].append(f"{pet['id']}: manifest identity/path mismatch")
        for filename in ['pet.json', 'spritesheet.webp']:
            p = folder/filename
            if sha(p.read_bytes()) != expected_sums.get(p.relative_to(ROOT).as_posix()):
                report['errors'].append(f'{pet["id"]}/{filename}: checksum mismatch')
        with Image.open(folder/'spritesheet.webp') as image:
            atlas = image.convert('RGBA')
        if atlas.size != (1536,1872):
            report['errors'].append(f"{pet['id']}: dimensions mismatch")
            continue
        record = {'id': pet['id'], 'file_bytes': (folder/'spritesheet.webp').stat().st_size,
                  'visible_cells': 0, 'transparent_padding_cells': 0, 'rows': []}
        for row in config['rows']:
            hashes = []
            bboxes = []
            for c in range(8):
                image = atlas.crop((c*192,row['row']*208,(c+1)*192,(row['row']+1)*208))
                alpha = image.getchannel('A')
                bbox = alpha.getbbox()
                if c < len(row['frames']):
                    record['visible_cells'] += 1
                    if not bbox:
                        report['errors'].append(f"{pet['id']}/{row['state']}/{c}: blank frame")
                    elif bbox[0] < 2 or bbox[1] < 2 or bbox[2] > 190 or bbox[3] > 206:
                        report['errors'].append(f"{pet['id']}/{row['state']}/{c}: edge clipping risk {bbox}")
                    hashes.append(sha(image.tobytes()))
                    bboxes.append(bbox)
                else:
                    record['transparent_padding_cells'] += 1
                    if bbox:
                        report['errors'].append(f"{pet['id']}/{row['state']}/{c}: padding not blank")
                if normalized(image).tobytes() != image.tobytes():
                    report['errors'].append(f"{pet['id']}/{row['state']}/{c}: hidden RGB residue")
            if len(set(hashes)) < 3:
                report['errors'].append(f"{pet['id']}/{row['state']}: too few unique visible frames")
            record['rows'].append({'state': row['state'], 'frames': len(hashes),
                                   'unique_frames': len(set(hashes)), 'alpha_bounds': bboxes})
        report['pets'].append(record)
    source = load(ROOT/'assets/source/manifest.json')
    source_count = 0
    for outfit in source['outfits']:
        for action in outfit['actions']:
            path = ROOT/action['sheet']
            if sha(path.read_bytes()) != action['sheet_sha256']:
                report['errors'].append(f'{path.name}: source checksum mismatch')
            sheet = Image.open(path).convert('RGBA')
            if sheet.size != (1920,1280):
                report['errors'].append(f'{path.name}: source dimensions mismatch')
            for i, expected in enumerate(action['frame_hashes']):
                x,y=(i%6)*320,(i//6)*320
                if sha(sheet.crop((x,y,x+320,y+320)).tobytes()) != expected:
                    report['errors'].append(f'{path.name}/{i}: source frame hash mismatch')
                source_count += 1
    report['source_frames_verified'] = source_count
    report['status'] = 'PASS' if not report['errors'] else 'FAIL'
    if report['errors']:
        write_json(ROOT/'qa/asset-validation.json', report)
        raise ValueError('\n'.join(report['errors']))
    return report

def export_frames(dest: Path):
    manifest = load(ROOT/'assets/source/manifest.json')
    if dest.exists() and any(dest.iterdir()):
        raise ValueError('Export destination must be empty; existing data will not be overwritten')
    dest.mkdir(parents=True, exist_ok=True)
    for outfit in manifest['outfits']:
        for aid, frames in source_frames(outfit).items():
            folder=dest/outfit['id']/aid
            folder.mkdir(parents=True, exist_ok=True)
            for i, frame in enumerate(frames):
                frame.save(folder/f'frame_{i:03}.png')
    print(f'Exported 648 transparent PNG frames to {dest}')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    imp=sub.add_parser('import-zip'); imp.add_argument('archive',type=Path)
    sub.add_parser('build'); sub.add_parser('validate')
    exp=sub.add_parser('export-frames'); exp.add_argument('destination',type=Path)
    args=parser.parse_args()
    try:
        if args.command=='import-zip': import_zip(args.archive)
        elif args.command=='build': build()
        elif args.command=='export-frames': export_frames(args.destination)
        else:
            report=validate(); write_json(ROOT/'qa/asset-validation.json',report)
            print(json.dumps({k: report[k] for k in ['status','source_frames_verified','errors','warnings']},ensure_ascii=False,indent=2))
    except (ValueError, OSError, RuntimeError, KeyError, zipfile.BadZipFile) as exc:
        parser.exit(1,f'Error: {exc}\n')
if __name__=='__main__': main()
