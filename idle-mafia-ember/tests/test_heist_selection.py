"""Legacy Heist scoring and inclusive selection constraints, without a sender."""
import copy
import random
import unittest
from engine_harness import Harness,lua_table

POLICIES=('Best chest','Balanced','Highest tier','Lowest stake','XP / hour','Profit / hour')
def score(r,mode):
    expected=r['crateCount']*r['crateChance'];profit=(r['cash']-r['stake'])/r['duration'];xp=r['xp']/r['duration']
    if mode=='Best chest':return r['crateRarity']*1e9+expected*1e6+r['level']*1e3+profit
    if mode=='Balanced':return r['crateRarity']*1e9+expected*1e6+xp*1e3+profit
    if mode=='Highest tier':return (r['level'],r['crateRarity']*1e6+expected*1e3)
    if mode=='Lowest stake':return -r['stake']
    return xp if mode=='XP / hour' else profit

class HeistSelectionTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness();self.planner=self.h.load('src/features/HeistStart.luau')
        self.rows=[{'id':'rare','level':10,'stake':100,'energy':2,'crateCount':1,'crateChance':.25,'crateRarity':5,'duration':3600,'cash':500,'xp':100,'helpGoal':3},
                   {'id':'common','level':20,'stake':200,'energy':5,'crateCount':4,'crateChance':1,'crateRarity':2,'duration':1200,'cash':600,'xp':400,'helpGoal':6}]
    def view(self,rows=None):return lua_table(self.h.lua,{**self.h.session,'revision':1,'state':'idle','startsLeft':2,'bustWait':0,'serverDay':23,'serverNow':2000000,'level':100,'cash':100000,'energy':100,'catalogKey':'a'*64,'options':rows or self.rows})
    def propose(self,mode='Best chest',rows=None,**settings):return self.planner.propose(self.view(rows),lua_table(self.h.lua,{'enabled':True,'policy':mode,**settings}),lua_table(self.h.lua,{}))
    def test_best_chest_prioritizes_rarity_and_expected_drop_quotes_not_count_alone(self):
        p,why=self.propose();self.assertIsNone(why);self.assertEqual(p.intent.heistId,'rare')
    def test_all_six_modes_match_legacy_scoring_and_first_equal_quote_order(self):
        rng=random.Random(8675309)
        for _ in range(60):
            rows=[{'id':str(i),'level':rng.randrange(1,101),'stake':rng.randrange(0,1000),'energy':rng.randrange(0,100),'crateCount':rng.randrange(0,5),'crateChance':rng.choice([0,.1,.25,.5,1]),'crateRarity':rng.randrange(0,10),'duration':rng.choice([60,1200,3600]),'cash':rng.randrange(0,10000),'xp':rng.randrange(0,10000),'helpGoal':rng.randrange(0,10)} for i in range(7)]
            for mode in POLICIES:
                expected=max(rows,key=lambda r:score(r,mode))['id'];p,why=self.propose(mode,rows)
                self.assertIsNone(why,mode);self.assertEqual(p.intent.heistId,expected,mode)
        rows=[copy.deepcopy(self.rows[0]) for _ in range(2)];rows[0]['id']='z';rows[1]['id']='a'
        for mode in POLICIES:self.assertEqual(self.propose(mode,rows)[0].intent.heistId,'z',mode)
    def test_inclusive_fractional_bounds_and_explicit_selection(self):
        settings={'limitsEnabled':True,'minLevel':9.5,'maxLevel':10,'minEnergy':1.5,'maxEnergy':2,'minCrateRarity':4.5,'maxHours':1,'maxHelps':3,'selection':'Only selected','selectedIds':'rare'}
        self.assertEqual(self.propose(**settings)[0].intent.heistId,'rare')
        for field,value in [('minLevel',10.1),('maxLevel',9.9),('minEnergy',2.1),('maxEnergy',1.9),('minCrateRarity',5.1),('maxHours',.99),('maxHelps',2.9)]:
            with self.subTest(field=field):self.assertIsNone(self.propose(**{**settings,field:value})[0])
        for ids in ('','missing','rare,,common','rare,'):
            self.assertIsNone(self.propose(selection='Only selected',selectedIds=ids)[0])
        self.assertEqual(self.propose(selection='Only selected',selectedIds=' common , rare ')[0].intent.heistId,'rare')
    def test_missing_eligible_quote_refuses_instead_of_silently_ranking_partial_data(self):
        for field in ('duration','cash','xp','crateChance','crateRarity','helpGoal'):
            rows=copy.deepcopy(self.rows);rows[0].pop(field)
            self.assertIsNone(self.propose(rows=rows)[0],field)
            self.assertEqual(self.propose(rows=rows,selection='Only selected',selectedIds='common')[0].intent.heistId,'common')
    def test_core_reservations_and_fractional_shared_energy_floor_remain_effective(self):
        view=self.view();view.energy=2
        p,why=self.planner.propose(view,lua_table(self.h.lua,{'enabled':True,'policy':'Best chest','energyReserve':.5}),lua_table(self.h.lua,{}))
        self.assertIsNone(p);self.assertNotIn('Invalid shared',why)
        view=self.view();view.cash=200
        p,_=self.planner.propose(view,lua_table(self.h.lua,{'enabled':True,'policy':'Best chest'}),lua_table(self.h.lua,{'cash':75,'uncertainCash':30}))
        self.assertIsNone(p)
