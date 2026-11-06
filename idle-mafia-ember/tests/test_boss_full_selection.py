"""Reviewed build-653 whole Boss selection; exhaustive offline oracle."""
import unittest
import random
from engine_harness import Harness,lua_table
import test_bosses as unit
import test_bosses_runtime as runtime

MODES=('Smart','First undefeated','Highest level','Best chest','Cash reward','XP reward')

def source(h):
    return h.lua.execute("""
local data={BOSSES={},ITEMS_BY_ID={crate_boss={rarity=7},common={rarity=1},rare={rarity=5}}}
for i=1,32 do data.BOSSES[i]={level=(i*7)%23+1,hp=i*100,def=i*2,hitBackMax=i%9+1,
    cash=i*17,xp=i%8*100,crate=i%3==0 and 'rare' or 'common',firstKillCrate=i%8==0 and 'crate_boss' or nil} end
local s={MAX_STAGE=100000,CITY_STAGES=32,CITY_XP_MULT=1,MW_TIER_XP_STEP=.07,
 MOST_WANTED={DON_CRATE='crate_boss',DON_HP_MULT=12,HP_MULT=8,DEF_GROWTH=1.04,LINEAR_GROWTH=.02},
 MW_BASE={hitBackMin=32,hitBackMax=47,xp=66177.8125},calls=0,
 SHOP={gear={{item='g',price=1}},crates={{item='common',price=1}}},crateUnlocked=function() return true end}
function s.get(stage)
 s.calls=s.calls+1
 local base=data.BOSSES[stage<=32 and stage or (stage-33)%32+1]
 if stage<=32 then return {stage=stage,level=base.level,hp=base.hp,hitBackMax=base.hitBackMax,cash=base.cash,xp=math.floor(base.xp+.5),crate=base.crate,firstClearCrate=base.firstKillCrate,mostWanted=false} end
 local n=stage-32;local last=data.BOSSES[32]
 return {stage=stage,level=last.level,hp=math.floor(last.def*1.04^n+.5)*(base.firstKillCrate and 12 or 8),
 hitBackMax=math.floor(47*(1+.02*n)+.5),cash=math.floor(last.cash*1.04^n+.5),
 xp=math.floor(66177.8125*(1+.07*(1+(n-1)/32))+.5),firstClearCrate=base.firstKillCrate and 'crate_boss' or nil,mostWanted=true}
end
return s,data,{PlaceId=73897506680154,PlaceVersion=653}
""")

class BossFullSelectionTests(unittest.TestCase):
    def setUp(self):
        self.f=unit.BossesTests();self.f.setUp();self.h=self.f.h
        self.stages,self.data,self.game=source(self.h)
        self.catalog=self.h.load('src/tabs/combat/NativeBossCatalog.luau').new(self.stages,
            lua_table(self.h.lua,{'BOSS':{'staminaCost':1}}),'a'*64,'release-a',self.data,self.game)
    def raw(self,best=80,done=None,health=150,max_health=200):
        raw=self.f.raw(best=best,done=done,health=health)
        raw.native.level=100;raw.native.stats.maxHealth=max_health
        return raw
    def choose(self,raw,mode='Smart',**kw):
        settings=lua_table(self.h.lua,dict(enabled=True,selection=mode,**kw))
        enriched,why=self.catalog.Enrich(self.catalog,raw,settings)
        if enriched is None:return None,why
        view,why=self.f.view(enriched)
        if view is None:return None,why
        return self.f.planner.propose(view,settings,self.h.lua.table())
    def test_full_selection_beats_old_truncated_window(self):
        raw=self.raw(best=200,health=100,max_health=100)
        self.assertEqual(self.choose(raw,'Smart')[0].intent.stage,1)
        self.assertLessEqual(self.stages.calls,36)
    def test_irrelevant_overflow_frontier_does_not_block_safe_city_winner(self):
        raw=self.raw(best=1000,health=100,max_health=100)
        for mode in MODES+('Current progression',):
            expected=self.oracle(raw,mode,{})
            self.assertEqual(self.choose(raw,mode)[0].intent.stage,expected,mode)
    def test_invalid_city_preferences_or_health_do_not_suppress_shop(self):
        for missing in (False,True):
            raw=self.raw()
            if missing:raw.native.pools.health=None
            settings=lua_table(self.h.lua,{'limitsEnabled':True,'minLevel':11,'maxLevel':5}) if not missing else None
            enriched,reason=self.catalog.Enrich(self.catalog,raw,settings)
            self.assertIsNotNone(enriched,reason);self.assertIsNotNone(enriched.bossShopProof)
            self.assertIsNone(enriched.bossStageProof)
            self.assertIsNotNone(raw.bossStageProof)
    def test_player_level_above_boss_quote_domain_remains_eligible(self):
        for level in (1000001,9007199254740991):
            raw=self.raw(best=1);raw.native.level=level
            self.assertEqual(self.choose(raw,'Smart')[0].intent.stage,2)
    def test_unknown_build_refuses_explicit_ranking(self):
        self.game.PlaceVersion=654
        self.assertIsNone(self.choose(self.raw(),'XP reward')[0])

    def oracle(self,raw,mode,settings):
        native=raw.native;best=native.bossStage.best;top=min(best+1,100000)
        chosen=None
        def rarity(row):
            repeat=self.data.ITEMS_BY_ID[row.crate].rarity if row.crate else 0
            first=self.data.ITEMS_BY_ID[row.firstClearCrate].rarity if row.stage>best and row.firstClearCrate else 0
            return max(repeat,first)
        def score(row):
            if mode=='Highest level':return (row.level,row.stage)
            if mode=='Best chest':return rarity(row)
            if mode=='Cash reward':return row.cash if row.stage>best else 0
            if mode=='XP reward':return row.xp
            return 0
        for stage in [top]+list(range(1,best+1)):
            row=self.stages.get(stage)
            if row.level>native.level:continue
            if settings.get('limitsEnabled',False) and not settings.get('minLevel',1)<=row.level<=settings.get('maxLevel',10000):continue
            if native.pools.health<row.hitBackMax+native.stats.maxHealth*settings.get('healthFloor',50)/100:continue
            if native.bossStage.day==self.f.day and native.bossStage.done[str(stage)] is True:continue
            if chosen is None:chosen=row
            elif score(row)>score(chosen):chosen=row
            if mode in ('Smart','First undefeated','Current progression') and chosen is not None:break
        return chosen.stage if chosen is not None else None
    def test_all_modes_match_exhaustive_source_oracle(self):
        rng=random.Random(653)
        for best in (0,1,17,31,32,33,45,80,160,300):
            for sample in range(6):
                done={str(i):True for i in range(1,best+1) if rng.random()<.55}
                raw=self.raw(best,done,health=rng.randint(30,250),max_health=300)
                settings={'healthFloor':rng.choice((1,20.25,50,75)), 'limitsEnabled':sample%2==0,'minLevel':rng.choice((1,5,15)),'maxLevel':rng.choice((16,23,10000))}
                for mode in MODES+('Current progression',):
                    expected=self.oracle(raw,mode,settings);self.stages.calls=0
                    proposal,reason=self.choose(raw,mode,**settings)
                    self.assertEqual(proposal.intent.stage if proposal is not None else None,expected,(best,sample,mode,reason))
                    self.assertLessEqual(self.stages.calls,36)
    def test_city_rounded_ties_and_next_first_tie_order(self):
        # City XP is floor(base+.5); equal XP and crate rarity retain top-first,
        # then the earliest repeat, while Highest level breaks ties upward.
        for row in self.data.BOSSES.values():row.xp=123;row.level=5;row.crate='common';row.firstKillCrate=None
        self.catalog=self.h.load('src/tabs/combat/NativeBossCatalog.luau').new(self.stages,
            lua_table(self.h.lua,{'BOSS':{'staminaCost':1}}),'a'*64,'release-a',self.data,self.game)
        for mode in ('XP reward','Best chest','Cash reward','Highest level'):
            self.assertEqual(self.choose(self.raw(best=20),mode)[0].intent.stage,21)
        raw=self.raw(best=20,done={'21':True})
        self.assertEqual(self.choose(raw,'XP reward')[0].intent.stage,1)
        self.assertEqual(self.choose(raw,'Best chest')[0].intent.stage,1)
        self.assertEqual(self.choose(raw,'Highest level')[0].intent.stage,20)
    def test_complete_source_revokes_on_mutation_even_if_restored(self):
        for change in ('build','constants','constant_table','get','city','rarity','data_table','city_ref','item_ref'):
            self.setUp();original=None
            if change=='build':self.game.PlaceVersion=654
            elif change=='constants':self.stages.MW_TIER_XP_STEP=.08
            elif change=='constant_table':self.stages.MW_BASE=lua_table(self.h.lua,{'hitBackMin':32,'hitBackMax':47,'xp':66177.8125})
            elif change=='get':self.stages.get=self.h.lua.eval('function(stage) return nil end')
            elif change=='city':self.data.BOSSES[1].xp=999
            elif change=='rarity':self.data.ITEMS_BY_ID.common.rarity=4
            elif change=='city_ref':self.data.BOSSES[1]=self.h.lua.eval('function(row) local copy={} for k,v in pairs(row) do copy[k]=v end return copy end')(self.data.BOSSES[1])
            elif change=='item_ref':self.data.ITEMS_BY_ID.common=lua_table(self.h.lua,{'rarity':1})
            elif change=='data_table':self.data.BOSSES=self.h.lua.eval('function(rows) local copy={} for i,v in ipairs(rows) do copy[i]=v end return copy end')(self.data.BOSSES)
            self.assertIsNone(self.choose(self.raw(),'Smart')[0],change)
            self.assertTrue(self.catalog.retired,change)
            self.game.PlaceVersion=653
            self.assertIsNone(self.choose(self.raw(),'Smart')[0],change)
    def test_selected_quote_mismatch_revokes_even_with_matching_constants(self):
        original=self.stages.get;self.h.lua.globals().originalBossQuote=original
        self.stages.get=self.h.lua.eval('function(stage) local row=originalBossQuote(stage) row.xp=row.xp+1 return row end')
        self.catalog=self.h.load('src/tabs/combat/NativeBossCatalog.luau').new(self.stages,
            lua_table(self.h.lua,{'BOSS':{'staminaCost':1}}),'a'*64,'release-a',self.data,self.game)
        self.assertIsNone(self.choose(self.raw(),'Smart')[0]);self.assertTrue(self.catalog.retired)
    def test_mutation_inside_native_quote_cannot_produce_full_proof(self):
        self.h.lua.globals().bossSource=self.stages;self.h.lua.globals().originalBossQuote=self.stages.get
        self.stages.get=self.h.lua.eval('function(stage) local row=originalBossQuote(stage) if stage==1 then bossSource.MW_BASE.xp=1 end return row end')
        self.catalog=self.h.load('src/tabs/combat/NativeBossCatalog.luau').new(self.stages,
            lua_table(self.h.lua,{'BOSS':{'staminaCost':1}}),'a'*64,'release-a',self.data,self.game)
        self.assertIsNone(self.choose(self.raw(),'Smart')[0])
    def test_sparse_done_holes_near_maximum_remain_bounded_and_fail_numeric_domain(self):
        raw=self.raw(best=99999,done={str(i):True for i in range(33,99999) if i not in (99997,)},health=1000000,max_health=1000000)
        self.assertIsNotNone(self.choose(raw,'Highest level',healthFloor=1)[0])
        proposal,reason=self.choose(raw,'XP reward',healthFloor=1)
        self.assertIsNone(proposal)
        enriched,reason=self.catalog.Enrich(self.catalog,raw,lua_table(self.h.lua,{'selection':'XP reward','healthFloor':1}))
        self.assertIsNotNone(enriched,reason);self.assertIsNone(enriched.bossStageProof)
        self.assertIsNotNone(enriched.bossShopProof)
        self.assertLessEqual(self.stages.calls,36)
    def test_current_progression_fallback_and_explicit_rankings_on_unreviewed_initial_build(self):
        self.game.PlaceVersion=654
        self.catalog=self.h.load('src/tabs/combat/NativeBossCatalog.luau').new(self.stages,
            lua_table(self.h.lua,{'BOSS':{'staminaCost':1}}),'a'*64,'release-a',self.data,self.game)
        self.assertIsNotNone(self.choose(self.raw(best=1),'Current progression')[0])
        for mode in MODES:self.assertIsNone(self.choose(self.raw(best=1),mode)[0])

class BossFullSelectionAppTests(unittest.TestCase):
    def fixture(self):
        f=runtime.BossesRuntimeTests();f.setUp();f.app.Destroy(f.app)
        f.source,f.boss_game_data,f.boss_client_game=source(f.h);f.start_current()
        self.addCleanup(f.tearDown)
        original=f.raw
        def raw(*args,**kwargs):
            result=original(*args,**kwargs);result.native.bossStage.best=getattr(f,'observed_best',200)
            result.native.stats.maxHealth=200;result.native.level=100
            result.native.pools.health=kwargs.get('health',150)
            if getattr(f,'observed_hp',None) is not None:result.native.bossStage.hp['35']=f.observed_hp
            return result
        f.raw=raw
        return f
    def test_actual_app_modes_are_independent_visible_and_default_off(self):
        for mode in MODES:
            f=self.fixture();self.assertFalse(f.app.model['values']['bosses.enabled'])
            self.assertTrue(f.app.ui.features.bosses.custom.visible)
            self.assertTrue(f.app.Set(f.app,'bosses.custom.selection',mode)[0])
            f.begin();self.assertEqual(len(f.executor.calls),1)
    def test_queued_goal_quote_disable_unload_and_build_changes_fence(self):
        for change in ('selection','quote','disable','unload','build'):
            f=self.fixture();f.app.Set(f.app,'bosses.custom.selection','XP reward');f.choose();f.step()
            self.assertEqual(len(f.executor.queued),1)
            if change=='selection':f.app.Set(f.app,'bosses.custom.selection','Smart')
            elif change=='quote':f.boss_game_data.BOSSES[1].cash=1
            elif change=='disable':f.app.Set(f.app,'bosses.enabled',False)
            elif change=='unload':f.app.Destroy(f.app)
            else:f.boss_client_game.PlaceVersion=654
            f.drain();self.assertEqual(len(f.executor.calls),0)
    def test_exact_sent_and_saved_stage_recovers_when_new_candidate_window_excludes_it(self):
        for restart in (False,True):
            f=self.fixture();f.app.Set(f.app,'bosses.custom.selection','XP reward');f.begin()
            self.assertEqual(f.executor.calls[1].args[2],35)
            if restart:f.restart()
            f.app.Set(f.app,'bosses.custom.selection','Smart')
            f.observed_hp=400;f.observed_best=1000;f.step(0 if restart else 2,health=100,stamina=11,server_now=2000005)
            status=f.runtime.Status(f.runtime)
            self.assertEqual((status.recoveries if restart else status.outcomes).bosses,'confirmed')
            self.assertEqual(len(f.executor.calls),1)
    def test_saved_reward_quote_change_stays_pending_without_replay(self):
        f=self.fixture();f.app.Set(f.app,'bosses.custom.selection','XP reward');f.begin();f.restart()
        f.boss_game_data.ITEMS_BY_ID.common.rarity=6
        f.observed_hp=400;f.step(0,stamina=11,server_now=2000005)
        self.assertIsNone(f.runtime.Status(f.runtime).recoveries.bosses)
        self.assertEqual(len(f.executor.calls),1)
    def test_legacy_modes_import_inertly_and_caps_stay_distinct(self):
        import test_legacy_remaining_preferences as legacy
        f=legacy.LegacyRemainingPreferencesTests();f.setUp();self.addCleanup(f.tearDown)
        for mode in MODES:
            accepted,reason=f.preview(bossMode=mode);self.assertTrue(accepted,reason);f.assert_inert()
            self.assertEqual(f.app.staged['values']['bosses.custom.selection'],mode)
        for key in ('bossMaxHits','bossMaxStamina','bossHitDelay'):
            accepted,reason=f.preview(**{key:12});self.assertTrue(accepted,reason);f.assert_inert()

if __name__=='__main__':unittest.main()
