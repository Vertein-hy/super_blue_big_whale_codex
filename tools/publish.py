#!/usr/bin/env python3
"""Create one NEW GitHub repository and push a clean copy via a locally logged-in gh CLI."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from petctl import PetError, read_package, OUTFITS

ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST = ['README.md','QUICKSTART.md','LICENSE','ASSET-NOTICE.md','.gitignore','.gitattributes',
             'config.json','checksums.json','install.sh','install.command','install.ps1',
             'publish.command','preview.html','preview.js','preview-data.js',
             'pets','assets','docs','tools','tests','qa']

def run(command: list[str], *, cwd: Path | None = None, check=True):
    result = subprocess.run(command,cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=300)
    if check and result.returncode:
        raise PetError(f'{command[0]} {command[1]} failed: {result.stderr.strip() or result.stdout.strip()}')
    return result

def publication_plan(owner: str, name: str, public: bool=False) -> dict:
    if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})', owner):
        raise PetError('Invalid GitHub owner')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}',name) or name.endswith('.git'):
        raise PetError('Invalid repository name; do not include a URL or .git suffix')
    return {'repository': f'{owner}/{name}', 'visibility':'public' if public else 'private',
            'branch':'main','operation':'create-new-and-push','touch_existing_repositories':False,
            'paths':ALLOWLIST,'performed':False}

def publish(owner: str, name: str, *, public=False, dry_run=False):
    plan=publication_plan(owner,name,public)
    if dry_run:
        return plan
    for pet_id in OUTFITS.values():
        read_package(ROOT,pet_id)
    if not (ROOT/'assets/source/manifest.json').is_file():
        raise PetError('Publishing requires the full source project ZIP, not the lightweight install ZIP')
    for executable in ['git','gh']:
        if shutil.which(executable) is None:
            raise PetError(f'{executable} is not installed. Install Git and GitHub CLI; then run gh auth login on your computer. Never paste a token in chat.')
    run(['gh','auth','status','--hostname','github.com'])
    profile=json.loads(run(['gh','api','user']).stdout)
    if profile.get('login','').lower()!=owner.lower():
        raise PetError(f'Logged in as {profile.get("login")}, but selected owner is {owner}. Switch gh accounts or explicitly set --owner.')
    probe=run(['gh','api',f'repos/{plan["repository"]}'],check=False)
    if probe.returncode==0:
        raise PetError('Repository already exists. This script never overwrites or appends to existing repositories; choose another new name.')
    if 'HTTP 404' not in probe.stderr:
        raise PetError('Could not verify that the new repository is absent: '+probe.stderr.strip())
    with tempfile.TemporaryDirectory(prefix='whale-publish-') as temporary:
        stage=Path(temporary)/name;stage.mkdir()
        for item in ALLOWLIST:
            src,dst=ROOT/item,stage/item
            if not src.exists():
                continue
            if src.is_symlink():
                raise PetError(f'Refusing symlinked publication input: {item}')
            if src.is_dir():
                for path in src.rglob('*'):
                    if path.is_symlink():
                        raise PetError(f'Refusing symlinked publication input: {path.relative_to(ROOT)}')
                shutil.copytree(src,dst,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.DS_Store','.git','.env','.env.*','*.pem','*.key','.git-credentials'))
            else:
                shutil.copy2(src,dst)
        run(['git','init','--initial-branch=main'],cwd=stage)
        run(['git','config','user.name',profile['login']],cwd=stage)
        run(['git','config','user.email',f'{profile["id"]}+{profile["login"]}@users.noreply.github.com'],cwd=stage)
        # Disable inherited signing for this disposable repo only; no global config is edited.
        run(['git','config','commit.gpgsign','false'],cwd=stage)
        run(['git','add','--all'],cwd=stage)
        run(['git','commit','-m','feat: add three whale Codex pets and lossless animation sources'],cwd=stage)
        command=['gh','repo','create',plan['repository'],'--public' if public else '--private',
                 '--description','Three cute whale-girl outfits for Codex, with 24-frame source art and safe installers.',
                 '--source',str(stage),'--remote','origin','--push']
        try:
            run(command,cwd=stage)
        except PetError as exc:
            raise PetError(str(exc)+'\nA repository may have been created before a push failure. Inspect GitHub before retrying; no remote repository was deleted.') from exc
        local=run(['git','rev-parse','HEAD'],cwd=stage).stdout.strip()
        remote=json.loads(run(['gh','api',f'repos/{plan["repository"]}/git/ref/heads/main']).stdout)['object']['sha']
        if remote!=local:
            raise PetError('Remote main does not match the prepared commit; upload is not verified')
        result={**plan,'performed':True,'verified':True,'commit':remote,
                'url':f'https://github.com/{plan["repository"]}'}
        (ROOT/'GITHUB_UPLOAD_RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner',default='Vertein-hy')
    parser.add_argument('--name',default='whale-codex-pets')
    parser.add_argument('--public',action='store_true',help='Explicitly publish art publicly; default is PRIVATE')
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    try:
        print(json.dumps(publish(args.owner,args.name,public=args.public,dry_run=args.dry_run),ensure_ascii=False,indent=2))
    except (PetError,OSError,ValueError,subprocess.TimeoutExpired) as exc:
        parser.exit(1,f'Error: {exc}\n')
if __name__=='__main__':main()
