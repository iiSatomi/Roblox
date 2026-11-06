"""Reviewed Heist/Favor preferences stage without activation or allowance adoption."""
import json
import unittest
import test_profile_management as fixture

class LegacyHeistFavorPreferencesTests(unittest.TestCase):
    def setUp(self):self.f=fixture.ProfileManagementTests();self.f.setUp();self.app=self.f.app
    def preview(self,**values):return self.app.PreviewImport(self.app,json.dumps({'version':17,**values}))
    def inert(self):
        self.assertTrue(self.app.model.paused)
        self.assertFalse(any(v for k,v in self.app.staged['values'].items() if k.endswith('.enabled')))
        self.assertEqual(len(self.f.base.storage.data),0)
    def test_all_reviewed_modes_import_including_explicit_legacy_defaults(self):
        for key,feature,modes in [('heistMode','heists',['Best chest','Balanced','Highest tier','Lowest stake','XP / hour','Profit / hour']),('favorMode','favors',['Balanced','Cash reward','XP reward','Ending soon','Highest tier'])]:
            for mode in modes:
                ok,why=self.preview(**{key:mode});self.assertTrue(ok,why)
                self.assertEqual(self.app.staged['values'][feature+'.policy'],mode);self.inert()
    def test_selected_heists_bounds_and_reward_thresholds_preserve_fractional_intent(self):
        ok,why=self.preview(heistSelection='Only selected',selectedHeists={'heist_truck':True,'heist_cornerstore':False},heistLimits=True,heistMinLevel=12.5,heistMaxLevel=40.5,heistMinEnergy=10.5,heistMaxEnergy=40.5,heistMinCrateRarity=4.5,heistMaxHours=1.5,heistMaxHelps=5.5,favorMinCash=100.5,favorMinXp=20.5)
        self.assertTrue(ok,why);v=self.app.staged['values']
        for k,x in {'selection':'Only selected','selectedIds':'heist_truck','limitsEnabled':True,'minLevel':12.5,'maxLevel':40.5,'minEnergy':10.5,'maxEnergy':40.5,'minCrateRarity':4.5,'maxHours':1.5,'maxHelps':5.5}.items():self.assertEqual(v['heists.custom.'+k],x)
        self.assertEqual(v['favors.custom.minRewardCash'],100.5);self.assertEqual(v['favors.custom.minRewardXp'],20.5);self.inert()
    def test_legacy_single_selected_mode_is_mapped_without_enabling_a_start(self):
        ok,why=self.preview(heistMode='Selected heist',heistId='heist_truck');self.assertTrue(ok,why)
        v=self.app.staged['values'];self.assertEqual(v['heists.policy'],'Best chest');self.assertEqual(v['heists.custom.selection'],'Only selected');self.assertEqual(v['heists.custom.selectedIds'],'heist_truck');self.inert()
    def test_single_selected_normalization_preserves_legacy_explicit_id_over_empty_old_map(self):
        for old in ({},{'heist_truck':False}):
            ok,why=self.preview(heistMode='Selected heist',heistId='heist_truck',heistSelection='Only selected',selectedHeists=old)
            self.assertTrue(ok,why);self.assertEqual(self.app.staged['values']['heists.custom.selectedIds'],'heist_truck');self.inert()
    def test_bad_modes_inverted_bounds_and_conflicting_selections_remain_reviewable(self):
        for values in [{'heistMode':'invented'},{'favorMode':'invented'},{'heistMode':'Custom'},{'favorMode':'Best reward'},{'heistLimits':True,'heistMinLevel':50,'heistMaxLevel':10},{'heistLimits':True,'heistMinEnergy':50,'heistMaxEnergy':10},{'heistMode':'Selected heist','heistId':''},{'heistMode':'Selected heist','heistId':'a','selectedHeists':{'b':True}},{'favorMinXp':1e12+1}]:
            ok,why=self.preview(**values);self.assertFalse(ok,values);self.assertIsNone(self.app.staged)
    def tearDown(self):self.f.tearDown()
