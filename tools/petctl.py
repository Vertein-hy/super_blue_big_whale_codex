#!/usr/bin/env python3
"""Install, verify or safely remove the three local Codex pets (standard library only)."""
from __future__ import annotations
import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
FILES = ('pet.json', 'spritesheet.webp')
OUTFITS = {'knit': 'whale-knit', 'cape': 'whale-cape', 'winter': 'whale-winter'}

class PetError(Exception):
    """An actionable validation/installation error; no unrelated files are touched."""

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise PetError(f'Cannot read JSON: {path}: {exc}') from exc

def validate_id(pet_id: str) -> str:
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', pet_id) or pet_id not in OUTFITS.values():
        raise PetError(f'Unknown/unsafe pet ID: {pet_id!r}')
    return pet_id

def read_package(root: Path, pet_id: str) -> dict:
    """Check manifest identity, confined paths, WebP container and SHA-256."""
    validate_id(pet_id)
    folder = root / 'pets' / pet_id
    if folder.is_symlink() or (root/'pets').is_symlink():
        raise PetError(f'Refusing symlinked source directory: {folder}')
    expected = read_json(root / 'checksums.json')
    for filename in FILES:
        path = folder / filename
        if path.is_symlink() or not path.is_file():
            raise PetError(f'Missing or symlinked package file: {path}')
        value = expected.get(f'pets/{pet_id}/{filename}')
        if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
            raise PetError(f'Missing checksum: {pet_id}/{filename}')
        if sha256(path) != value:
            raise PetError(f'Checksum mismatch: {pet_id}/{filename}; obtain a clean package')
    manifest = read_json(folder / 'pet.json')
    if not isinstance(manifest, dict) or set(manifest) != {'id','displayName','description','spritesheetPath'}:
        raise PetError(f'Manifest does not match the four-field V1 contract: {pet_id}')
    if manifest['id'] != pet_id or manifest['spritesheetPath'] != 'spritesheet.webp':
        raise PetError(f'Manifest identity or spritesheetPath mismatch: {pet_id}')
    if not all(isinstance(manifest[k], str) and manifest[k].strip() for k in manifest):
        raise PetError(f'Manifest contains an empty/non-string field: {pet_id}')
    data = (folder/'spritesheet.webp').read_bytes()
    if len(data) < 20 or data[:4] != b'RIFF' or data[8:12] != b'WEBP':
        raise PetError(f'Invalid WebP container: {pet_id}')
    if int.from_bytes(data[4:8], 'little') + 8 != len(data):
        raise PetError(f'Truncated WebP container: {pet_id}')
    return manifest

def codex_home(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit.expanduser().absolute()
    value = os.environ.get('CODEX_HOME', '').strip()
    return (Path(value).expanduser() if value else Path.home()/'.codex').absolute()

def validate_destination(home: Path):
    for path in [home, home/'pets', home/'pet-backups']:
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise PetError(f'Refusing symlink/non-directory destination: {path}')

def check_existing(target: Path, pet_id: str) -> bool:
    if target.is_symlink():
        raise PetError(f'Refusing symlinked pet directory: {target}')
    if not target.exists():
        return False
    if not target.is_dir():
        raise PetError(f'Not a pet directory: {target}')
    manifest = read_json(target/'pet.json')
    if not isinstance(manifest, dict) or manifest.get('id') != pet_id:
        raise PetError(f'Existing folder belongs to another package; left untouched: {target}')
    return True

@contextlib.contextmanager
def install_lock(home: Path):
    home.mkdir(parents=True, exist_ok=True)
    lock = home/'.whale-pet-install.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise PetError(f'Another installer may be active. Inspect the lock before retrying: {lock}') from exc
    try:
        os.write(fd, str(os.getpid()).encode('ascii'))
        os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)

def backup_folder(home: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    dest = home/'pet-backups'/f'{stamp}-{uuid.uuid4().hex[:8]}'
    dest.mkdir(parents=True, exist_ok=False)
    return dest

def install(root: Path, home: Path, ids: list[str], *, force=False, dry_run=False) -> list[dict]:
    validate_destination(home)
    if len(ids) != len(set(ids)):
        raise PetError('Duplicate pet selection')
    for pet_id in ids:
        read_package(root, pet_id)
    plan = []
    for pet_id in ids:
        source, target = root/'pets'/pet_id, home/'pets'/pet_id
        exists = check_existing(target, pet_id)
        same = exists and all((target/f).is_file() and not (target/f).is_symlink()
                              and sha256(source/f) == sha256(target/f) for f in FILES)
        if same:
            action = 'unchanged'
        elif exists and not force:
            raise PetError(f'Existing pet differs: {target}. Use --force to back it up before replacement.')
        else:
            action = 'replace-with-backup' if exists else 'install'
        plan.append({'id': pet_id, 'action': action, 'destination': str(target)})
    if dry_run or all(p['action'] == 'unchanged' for p in plan):
        return plan
    with install_lock(home):
        validate_destination(home)
        staging = Path(tempfile.mkdtemp(prefix='.whale-pet-stage-', dir=home))
        applied: list[tuple[Path, Path | None]] = []
        backups = None
        try:
            # Copy and verify everything before touching any existing pet.
            for p in plan:
                if p['action'] == 'unchanged':
                    continue
                stage = staging/p['id']; stage.mkdir()
                for filename in FILES:
                    shutil.copy2(root/'pets'/p['id']/filename, stage/filename)
                    if sha256(stage/filename) != sha256(root/'pets'/p['id']/filename):
                        raise PetError('Copy verification failed')
            (home/'pets').mkdir(parents=True, exist_ok=True)
            for p in plan:
                if p['action'] == 'unchanged':
                    continue
                target = home/'pets'/p['id']
                exists = check_existing(target, p['id'])
                if exists != (p['action'] == 'replace-with-backup'):
                    raise PetError(f'Destination changed during install: {target}')
                backup = None
                if exists:
                    if backups is None:
                        backups = backup_folder(home)
                    backup = backups/p['id']
                    os.replace(target, backup)
                    p['backup'] = str(backup)
                applied.append((target, backup))
                os.replace(staging/p['id'], target)
        except Exception:
            # Transaction rollback for only the known package directories in this run.
            for target, backup in reversed(applied):
                if target.exists():
                    shutil.rmtree(target)
                if backup is not None and backup.exists():
                    os.replace(backup, target)
            raise
        finally:
            shutil.rmtree(staging, ignore_errors=True)
    return plan

def uninstall(home: Path, ids: list[str], *, dry_run=False) -> list[dict]:
    """Removal is reversible: move complete package folders to pet-backups."""
    validate_destination(home)
    plan=[]
    for pet_id in ids:
        validate_id(pet_id)
        exists=check_existing(home/'pets'/pet_id, pet_id)
        plan.append({'id':pet_id,'action':'move-to-backup' if exists else 'absent',
                     'destination':str(home/'pets'/pet_id)})
    if dry_run or not any(p['action']=='move-to-backup' for p in plan):
        return plan
    with install_lock(home):
        backups=backup_folder(home)
        applied=[]
        try:
            for p in plan:
                if p['action']=='absent':
                    continue
                target=home/'pets'/p['id']
                check_existing(target,p['id'])
                backup=backups/p['id']
                os.replace(target,backup)
                applied.append((target,backup))
                p['backup']=str(backup)
        except Exception:
            for target,backup in reversed(applied):
                os.replace(backup,target)
            raise
    return plan

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['verify','install','uninstall'])
    parser.add_argument('--outfit', choices=['all', *OUTFITS], default='all')
    parser.add_argument('--home', type=Path, help='Override CODEX_HOME; default $CODEX_HOME or ~/.codex')
    parser.add_argument('--dry-run', action='store_true', help='Show operations without filesystem writes')
    parser.add_argument('--force', action='store_true', help='Back up and replace this package only')
    args=parser.parse_args()
    ids=list(OUTFITS.values()) if args.outfit=='all' else [OUTFITS[args.outfit]]
    try:
        if args.command=='verify':
            for pet_id in ids:
                read_package(ROOT,pet_id)
            result=[{'id':pet_id,'status':'PASS'} for pet_id in ids]
        elif args.command=='install':
            result=install(ROOT,codex_home(args.home),ids,force=args.force,dry_run=args.dry_run)
        else:
            result=uninstall(codex_home(args.home),ids,dry_run=args.dry_run)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        if args.command=='install' and not args.dry_run:
            print('Restart Codex, open Settings > Pets and select a pet. Use /pet to show it; menu location may vary by client version.')
    except (PetError,OSError) as exc:
        parser.exit(1,f'Error: {exc}\n')
if __name__=='__main__': main()
