from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import petctl
import publish

class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.base=Path(self.temporary.name)
        self.home=self.base/'codex home with spaces'
        self.ids=list(petctl.OUTFITS.values())
        self.pet=self.ids[0]
    def tearDown(self):self.temporary.cleanup()
    def install_one(self):return petctl.install(ROOT,self.home,[self.pet])
    def altered(self):
        self.install_one();path=self.home/'pets'/self.pet/'pet.json'
        value=json.loads(path.read_text());value['description']='old copy'
        path.write_text(json.dumps(value));return path.read_bytes()
    def test_all_source_packages_verify(self):
        for pet_id in self.ids:self.assertEqual(petctl.read_package(ROOT,pet_id)['id'],pet_id)
    def test_reject_unknown_and_traversal_ids(self):
        for value in ['../other','whale-knit/../other','other','', 'WHALE-KNIT']:
            with self.subTest(value=value),self.assertRaises(petctl.PetError):petctl.validate_id(value)
    def test_dry_run_does_not_create_home(self):
        plan=petctl.install(ROOT,self.home,self.ids,dry_run=True)
        self.assertEqual(len(plan),3);self.assertFalse(self.home.exists())
    def test_install_three_only_two_files_each(self):
        result=petctl.install(ROOT,self.home,self.ids)
        self.assertEqual(len(result),3)
        for pet_id in self.ids:
            self.assertEqual({p.name for p in (self.home/'pets'/pet_id).iterdir()},set(petctl.FILES))
    def test_idempotent_install(self):
        self.install_one();result=self.install_one()
        self.assertEqual(result[0]['action'],'unchanged');self.assertFalse((self.home/'pet-backups').exists())
    def test_no_touch_config_and_other_pet(self):
        self.home.mkdir();config=self.home/'config.toml';config.write_text('do not edit')
        other=self.home/'pets'/'another-pet';other.mkdir(parents=True);(other/'keep.txt').write_text('keep')
        self.install_one()
        self.assertEqual(config.read_text(),'do not edit');self.assertEqual((other/'keep.txt').read_text(),'keep')
    def test_existing_modified_requires_force(self):
        old=self.altered()
        with self.assertRaises(petctl.PetError):self.install_one()
        self.assertEqual((self.home/'pets'/self.pet/'pet.json').read_bytes(),old)
    def test_force_makes_complete_backup(self):
        old=self.altered();extra=self.home/'pets'/self.pet/'custom-note.txt';extra.write_text('keep this too')
        result=petctl.install(ROOT,self.home,[self.pet],force=True)
        backup=Path(result[0]['backup'])
        self.assertEqual((backup/'pet.json').read_bytes(),old)
        self.assertEqual((backup/'custom-note.txt').read_text(),'keep this too')
        self.assertFalse((self.home/'pets'/self.pet/'custom-note.txt').exists())
    def test_force_dry_run_preserves_existing(self):
        old=self.altered();petctl.install(ROOT,self.home,[self.pet],force=True,dry_run=True)
        self.assertEqual((self.home/'pets'/self.pet/'pet.json').read_bytes(),old)
        self.assertFalse((self.home/'pet-backups').exists())
    def test_wrong_identity_refused_even_force(self):
        dest=self.home/'pets'/self.pet;dest.mkdir(parents=True);(dest/'pet.json').write_text('{"id":"different"}')
        with self.assertRaises(petctl.PetError):petctl.install(ROOT,self.home,[self.pet],force=True)
        self.assertEqual((dest/'pet.json').read_text(),'{"id":"different"}')
    def test_foreign_empty_directory_refused(self):
        (self.home/'pets'/self.pet).mkdir(parents=True)
        with self.assertRaises(petctl.PetError):petctl.install(ROOT,self.home,[self.pet],force=True)
    def test_uninstall_moves_to_backup(self):
        self.install_one();result=petctl.uninstall(self.home,[self.pet])
        self.assertFalse((self.home/'pets'/self.pet).exists())
        self.assertTrue((Path(result[0]['backup'])/'spritesheet.webp').is_file())
    def test_uninstall_missing_is_noop(self):
        result=petctl.uninstall(self.home,self.ids)
        self.assertTrue(all(x['action']=='absent' for x in result));self.assertFalse(self.home.exists())
    def test_uninstall_dry_run_is_noop(self):
        self.install_one();petctl.uninstall(self.home,[self.pet],dry_run=True)
        self.assertTrue((self.home/'pets'/self.pet).exists());self.assertFalse((self.home/'pet-backups').exists())
    def test_existing_lock_blocks_write(self):
        self.home.mkdir();(self.home/'.whale-pet-install.lock').write_text('someone else')
        with self.assertRaises(petctl.PetError):self.install_one()
        self.assertFalse((self.home/'pets').exists())
    def test_destination_file_refused(self):
        self.home.write_text('not a directory')
        with self.assertRaises(petctl.PetError):self.install_one()
    @unittest.skipIf(os.name=='nt','Windows symlink permission varies')
    def test_symlink_pet_refused(self):
        outside=self.base/'outside';outside.mkdir();(self.home/'pets').mkdir(parents=True)
        (self.home/'pets'/self.pet).symlink_to(outside,target_is_directory=True)
        with self.assertRaises(petctl.PetError):self.install_one()
        self.assertEqual(list(outside.iterdir()),[])
    @unittest.skipIf(os.name=='nt','Windows symlink permission varies')
    def test_symlink_pets_root_refused(self):
        outside=self.base/'outside';outside.mkdir();self.home.mkdir();(self.home/'pets').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(petctl.PetError):self.install_one()
    def test_duplicate_selection_refused(self):
        with self.assertRaises(petctl.PetError):petctl.install(ROOT,self.home,[self.pet,self.pet])
    def test_checksum_tamper_detected_before_write(self):
        source=self.base/'source';shutil.copytree(ROOT/'pets'/self.pet,source/'pets'/self.pet)
        shutil.copy2(ROOT/'checksums.json',source/'checksums.json')
        with (source/'pets'/self.pet/'spritesheet.webp').open('ab') as stream:stream.write(b'corrupt')
        with self.assertRaises(petctl.PetError):petctl.install(source,self.home,[self.pet])
        self.assertFalse(self.home.exists())
    def test_staging_copy_failure_keeps_existing(self):
        old=self.altered()
        with patch.object(petctl.shutil,'copy2',side_effect=OSError('simulated disk failure')):
            with self.assertRaises(OSError):petctl.install(ROOT,self.home,[self.pet],force=True)
        self.assertEqual((self.home/'pets'/self.pet/'pet.json').read_bytes(),old)
        self.assertFalse((self.home/'.whale-pet-install.lock').exists())
    def test_swap_failure_rolls_back_backup(self):
        old=self.altered();original=petctl.os.replace
        def broken(src,dst):
            if '.whale-pet-stage-' in str(src):raise OSError('simulated swap failure')
            return original(src,dst)
        with patch.object(petctl.os,'replace',side_effect=broken):
            with self.assertRaises(OSError):petctl.install(ROOT,self.home,[self.pet],force=True)
        self.assertEqual((self.home/'pets'/self.pet/'pet.json').read_bytes(),old)
    def test_codex_home_env(self):
        with patch.dict(os.environ,{'CODEX_HOME':str(self.home)}):self.assertEqual(petctl.codex_home(),self.home)
    def test_explicit_home_wins(self):
        with patch.dict(os.environ,{'CODEX_HOME':'unused'}):self.assertEqual(petctl.codex_home(self.home),self.home)

class PublishTests(unittest.TestCase):
    def test_private_by_default(self):
        plan=publish.publication_plan('Vertein-hy','whale-codex-pets')
        self.assertEqual(plan['visibility'],'private');self.assertFalse(plan['performed'])
    def test_public_requires_explicit_option(self):
        self.assertEqual(publish.publication_plan('Vertein-hy','whale-codex-pets',True)['visibility'],'public')
    def test_invalid_repo_rejected(self):
        for value in ['../other','https://github.com/x/y','repo.git','', '--public']:
            with self.subTest(value=value),self.assertRaises(petctl.PetError):publish.publication_plan('Vertein-hy',value)
    def test_publish_dry_run_uses_no_network(self):
        with patch.object(publish,'run',side_effect=AssertionError('network must not be called')):
            plan=publish.publish('Vertein-hy','whale-codex-pets',dry_run=True)
        self.assertEqual(plan['operation'],'create-new-and-push')
    def test_publication_allowlist_excludes_secrets(self):
        self.assertNotIn('.git',publish.ALLOWLIST);self.assertNotIn('.env',publish.ALLOWLIST)
        self.assertNotIn('GITHUB_UPLOAD_RESULT.json',publish.ALLOWLIST)

if __name__=='__main__':unittest.main()
