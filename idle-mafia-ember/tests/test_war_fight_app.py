"""Actual War tab/planner/App/checkpoint/adapter lifecycle with native boundaries doubled."""
import unittest
import test_player_fight_app as fixture
import test_combat_tab_module as combat_fixture
from engine_harness import lua_table

class WarFightAppTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.PlayerFightAppTests();self.f.tab_factory=self.tab_factory;self.f.include_war=True
        self.f.plan_factory=lambda f:f.h.load('src/transport/NativeCallPlan.luau').withCombat(
            f.h.load('src/transport/NativeCallPlan.luau'),f.h.load('src/tabs/combat/CombatCallPlan.luau'))
        self.f.setUp();self.h=self.f.h;self.app=self.f.app;self.seed()
        for key,value in {'minimumPayout':0,'minSamples':0,'maxAttackSpend':10,'maxScoutSpend':5,'maxStaminaCost':5}.items():
            self.assertTrue(self.app.Set(self.app,'warCombat.custom.'+key,value)[0])
    def tab_factory(self,f):
        h=f.h
        f.source.Friendship=h.lua.eval('function() return false end')
        f.source.CanScout=h.lua.eval('function() return true end')
        f.source.CombatFrame=h.lua.eval('''function(self,native,targets)
            self.lastFrameTargets=#targets
            if self.failFrame then error('frame unavailable') end
            if self.yieldFrame then coroutine.yield('war-frame') end
            local rows={}
            for _,r in ipairs(targets) do rows[tostring(r.userId)]={remainingDaily=self.dailyRemaining==nil and 5 or self.dailyRemaining,
                cooldownLeft=self.cooldown or 0,sameFamily=self.sameFamily==true,manualWarning=self.warning==true,
                staminaCost=self.missingQuote~=true and (self.quote or 1) or nil} end
            return {ownUserId=1,ownFamilyId=native.family and native.family.id or 0,attack=self.attack or 200,
                health=native.pools.health,maxHealth=100,stamina=native.pools.stamina,
                hospitalHealth=20,staminaCost=1,scoutCost=1,maxStaminaCost=5,dailyTargetCap=5,targetCooldown=30,
                fightVariance=.2,fightVarianceCap=5000,busy=false,shielded=false,globalCooldown=0,targets=rows}
        end''')
        deps={'identity':h.session,'fingerprint':'a'*64,'release':'release-a','storage':f.f.base.storage,
            'nativeReadSource':f.source,'fightReceipts':f.owner,'combatRules':{'hospitalHealth':20,'staminaCost':1,'dailyTargetCap':5}}
        for name in ('HitListQuery','PlayerTargetState','BlockedFight','PlayerProfileQuery','FightReceipts','PlayerFightEvidence',
                     'PlayerScoutEvidence','PlayerFightLedger','PlayerFightPlanner','WarFightPlanner','TargetSelection'):
            deps[name]=h.load('src/tabs/combat/'+name+'.luau')
        f.e=deps['PlayerFightEvidence'].new(deps['FightReceipts'],deps['PlayerTargetState'])
        f.ledger=deps['PlayerFightLedger'].new(f.f.base.storage,lua_table(h.lua,h.session),f.e)[0]
        for _,reader,planner,evidence in combat_fixture.ROWS:
            deps[reader]=h.load('src/game/'+reader+'.luau');deps[planner]=h.load('src/features/'+planner+'.luau')
            deps[evidence]=h.load('src/features/'+evidence+'.luau')
        return h.load('src/tabs/combat/Module.luau').new(lua_table(h.lua,deps))
    def seed(self,scouted=True):
        f,h=self.f,self.h;raw=f.result.before
        raw.native.family=lua_table(h.lua,{'id':'own-family'});raw.native.derived=lua_table(h.lua,{'war':{'state':'active','enemyId':'enemy-family'}})
        raw.native.level=128;raw.native.respect=1000;raw.native.userId=1;raw.native.stats=lua_table(h.lua,{'maxHealth':100})
        self.warReply=lua_table(h.lua,{'ok':True,'warStatus':{'day':f.result.day,'serverNow':raw.native.serverNow,
            'summary':{'enemyId':'enemy-family','canScore':True,'ownRemaining':8,'ownCap':20,'eligibleAt':0,'canFeed':False},
            'targets':[{'userId':42,'name':'Target B','level':128,'respect':500,'familyId':'enemy-family',
                'warStatus':{'day':f.result.day,'remaining':3,'cap':5,'attacksRemaining':2,'attacksCap':5,'pairRemaining':1,'canScore':True}}]}})
        q=f.tab.warRosterQuery;request=q.Prepare(q,raw)[0]
        staged,why=q.Accept(q,raw,request,self.warReply);self.assertIsNotNone(staged,why);self.assertTrue(q.Commit(q,staged))
        profiles=f.tab.warProfiles;request,why=profiles.Prepare(profiles,raw);self.assertIsNotNone(request,why)
        response=lua_table(h.lua,{'ok':True,'profile':{'userId':42,'name':'Target B','level':128,'maxLevel':128,
            'familyId':'enemy-family','scoutCost':1,'statsHidden':True,'shieldLeft':0}})
        staged,why=profiles.Accept(profiles,raw,request,response);self.assertIsNotNone(staged,why);self.assertTrue(profiles.Commit(profiles,staged))
        if scouted:profiles.scoutCache['42']=lua_table(h.lua,{'requestId':1,'target':42,'name':'Target B','level':128,
            'familyId':'enemy-family','sourceKey':'a'*64,'at':raw.native.serverNow-1,'cachedAt':raw.capturedAt,'defense':1,'kind':'scout'})
        after=f.result.after;after.native.family=raw.native.family;after.native.derived=raw.native.derived
        after.native.level=128;after.native.respect=1000;after.native.userId=1;after.native.stats=raw.native.stats
    def begin(self):
        self.assertTrue(self.app.Set(self.app,'warCombat.enabled',True)[0]);self.app.Resume(self.app);self.f.step()
        self.assertEqual(len(self.f.executor.queued),1,str(dict(self.f.runtime.Status(self.f.runtime).reasons.items())))
    def send(self):self.f.executor.queued[1]();self.assertEqual(self.f.executor.calls,1)
    def test_actual_war_attack_settles_native_receipt_into_separate_usage_and_exact_history(self):
        self.begin();self.send();self.f.settle()
        status=self.f.runtime.Status(self.f.runtime)
        self.assertEqual(status.outcomes.warCombat,'confirmed');self.assertEqual(self.f.ledger.Summary(self.f.ledger).fights,1)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'warCombat')[0].attackSpent,5)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'combat')[0].attackSpent,0)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
    def test_all_off_and_zero_war_cap_never_queue_or_borrow_ordinary_allowance(self):
        self.f.step();self.assertEqual(len(self.f.executor.queued),0)
        self.app.Set(self.app,'warCombat.custom.maxAttackSpend',0)
        self.app.Set(self.app,'combat.custom.maxAttackSpend',100);self.app.Set(self.app,'warCombat.enabled',True)
        self.app.Resume(self.app);self.f.step();self.assertEqual(len(self.f.executor.queued),0)
    def test_disable_queued_war_attack_prevents_send_and_refunds_definitely_unsent_charge(self):
        self.begin();self.app.Set(self.app,'warCombat.enabled',False);self.f.step();self.f.executor.queued[1]()
        self.assertEqual(self.f.executor.calls,0)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'warCombat')[0].attackSpent,0)
    def test_changed_native_warning_quote_daily_limit_or_power_cancels_queued_attempt(self):
        for key,value in (('warning',True),('quote',2),('dailyRemaining',0),('attack',100),('missingQuote',True)):
            if key!='warning':self.tearDown();self.setUp()
            self.begin();self.f.source[key]=value;self.f.executor.queued[1]();self.assertEqual(self.f.executor.calls,0,key)
            self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'warCombat')[0].attackSpent,0)
    def test_changed_current_enemy_or_profile_cancels_before_native_mutation(self):
        self.begin();self.f.result.before.native.derived.war.enemyId='new-enemy';self.f.executor.queued[1]()
        self.assertEqual(self.f.executor.calls,0)
        self.tearDown();self.setUp();self.begin();self.f.tab.warProfiles.cache['42'].friend=True;self.f.executor.queued[1]()
        self.assertEqual(self.f.executor.calls,0)
    def test_unconfirmed_war_attempt_skips_at_45s_keeps_custody_and_never_counts_success(self):
        self.begin();self.send();self.h.at(45);raw=self.f.result.after;raw.capturedAt=45;self.f.step(raw)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.warCombat,'skipped_unconfirmed')
        self.assertEqual(self.f.ledger.Summary(self.f.ledger).fights,0)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'warCombat')[0].attackSpent,5)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),1)
    def test_unload_during_yielding_final_frame_cannot_send_or_publish_after_resume(self):
        self.begin();self.f.source.yieldFrame=True;self.h.lua.globals().queuedWar=self.f.executor.queued[1]
        value=self.h.lua.execute('warThread=coroutine.create(queuedWar);local ok,v=coroutine.resume(warThread);assert(ok);return v')
        self.assertEqual(value,'war-frame');self.app.Destroy(self.app)
        self.h.lua.execute('assert(coroutine.resume(warThread))');self.assertEqual(self.f.executor.calls,0)
    def test_paid_scout_uses_separate_optin_then_owned_war_cache_for_followup_attack(self):
        self.f.tab.warProfiles.scoutCache=self.h.lua.table();self.app.Set(self.app,'warCombat.enabled',True)
        self.app.Resume(self.app);self.f.step();self.assertEqual(len(self.f.executor.queued),0)
        self.app.Set(self.app,'warCombat.custom.allowScout',True);self.f.step();self.assertEqual(len(self.f.executor.queued),1)
        self.f.executor.InvokeOwned=self.h.lua.eval('function(self,token,remote,method,target) assert(remote=="ScoutPlayer" and target==42);self.calls=self.calls+1;return {ok=true,atk=100,def=1,crew=1} end')
        self.send();raw=self.f.result.after;raw.native.attackDaily.counts['42']=None
        self.h.at(.25);raw.capturedAt=.25;self.f.step(raw)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.warCombat,'confirmed')
        self.assertEqual(self.f.tab.warProfiles.Read(self.f.tab.warProfiles,raw)['42'].scout.defense,1)
        ordinary=self.f.tab.playerProfiles.Read(self.f.tab.playerProfiles,raw)
        self.assertTrue(ordinary is None or ordinary['42'] is None)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'warCombat')[0].scoutSpent,5)
        self.h.at(1);raw.capturedAt=1;self.f.step(raw)
        self.assertEqual(len(self.f.executor.queued),2)
    def test_terminal_war_receipt_flushes_before_unload_and_recovers_all_off_without_replay(self):
        self.begin();self.send();self.f.source.callback('fightcash','',lua_table(self.h.lua,self.f.result.final));self.app.Destroy(self.app)
        self.assertEqual(self.f.ledger.Summary(self.f.ledger).fights,1)
        self.h.session['session']='fresh-war-session';self.f.start();self.app=self.f.app
        raw=self.f.result.after;raw.session='fresh-war-session';raw.revision=3;raw.capturedAt=.25;self.h.at(.25);self.f.step(raw)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.warCombat,'confirmed')
        self.assertEqual(self.f.executor.calls,0);self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
    def tearDown(self):self.f.tearDown()

    def test_explicit_native_roster_quote_supports_dispatch_without_a_formula_quote(self):
        self.warReply.warStatus.targets[1].stamina=1
        q=self.f.tab.warRosterQuery;raw=self.f.result.before;request=q.Prepare(q,raw)[0]
        self.assertTrue(q.Commit(q,q.Accept(q,raw,request,self.warReply)[0]))
        self.f.source.missingQuote=True;self.begin();self.send();self.f.settle()
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.warCombat,'confirmed')
    def test_missing_native_quote_never_spends_to_discover_a_war_cost(self):
        self.f.source.missingQuote=True;self.app.Set(self.app,'warCombat.enabled',True)
        self.app.Set(self.app,'warCombat.custom.allowScout',True);self.app.Resume(self.app);self.f.step()
        self.assertEqual(len(self.f.executor.queued),0)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'warCombat')[0].attempted,0)
    def test_changed_owned_scoring_cap_after_queue_never_sends(self):
        self.begin();self.f.tab.warRosterQuery.observed.rows[1].warStatus.pairRemaining=0
        self.f.executor.queued[1]();self.assertEqual(self.f.executor.calls,0)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'warCombat')[0].attackSpent,0)
