import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build

class AssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=build.load(ROOT/'config.json')
        cls.report=build.validate()
    def test_all_native_packages_pass(self):self.assertEqual(self.report['status'],'PASS')
    def test_source_frames_648_verified(self):self.assertEqual(self.report['source_frames_verified'],648)
    def test_native_cell_count_and_padding(self):
        for pet in self.report['pets']:
            self.assertEqual(pet['visible_cells'],57);self.assertEqual(pet['transparent_padding_cells'],15)
    def test_state_order_is_fixed(self):
        self.assertEqual([r['state'] for r in self.config['rows']],['idle','running-right','running-left','waving','jumping','failed','waiting','running','review'])
    def test_counts_and_timing_match(self):
        self.assertEqual([len(r['frames']) for r in self.config['rows']],[6,8,8,4,5,8,6,6,6])
        for row in self.config['rows']:self.assertEqual(len(row['frames']),len(row['durations_ms']))
    def test_working_is_not_foot_running(self):
        row=next(r for r in self.config['rows'] if r['state']=='running')
        self.assertNotIn(row['source_action'],['02_walk','03_run'])
    def test_mirror_is_explicit(self):
        self.assertTrue(self.config['rows'][2]['mirror']);self.assertFalse(self.config['rows'][1]['mirror'])
    def test_desktop_runtime_not_falsely_claimed(self):self.assertFalse(self.report['codex_desktop_runtime_tested'])
    def test_selected_indices_in_source_range(self):
        for row in self.config['rows']:self.assertTrue(all(0<=i<24 for i in row['frames']))

if __name__=='__main__':unittest.main()
