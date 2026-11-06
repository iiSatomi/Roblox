"""Actual Combat constructor/view/planner/policy/settings/adapter/receipts through the App."""
import unittest
import test_player_fight_app as app_fixture
import test_combat_tab_module as combat_fixture
from engine_harness import lua_table

class PlayerCombatPlannerAppTests(unittest.TestCase):
    def setUp(self):
        self.f=app_fixture.PlayerFightAppTests();self.f.setUp();self.h=self.f.h
        self.f.app.Destroy(self.f.app)
        self.f.tab_factory=self.tab_factory
        self.f.plan_factory=lambda f:self.h.load('src/tabs/combat/CombatCallPlan.luau')
        self.f.start();self.app=self.f.app
        # This fixture's generic fight harness replaces the constructor's
        # evidence. Restore the real owning Combat module's evidence here.
        self.f.e=self.f.production_player_evidence;self.f.tab.playerEvidence=self.f.e
        self.f.ledger.evidence=self.f.e
        self.seed(False)
        for k,v in {'minimumPayout':0,'minSamples':0,'maxAttackSpend':5,'maxScoutSpend':5,'maxStaminaCost':5}.items():
            self.assertTrue(self.app.Set(self.app,'combat.custom.'+k,v)[0])
    def tab_factory(self,f):
        h=self.h
        f.source.Friendship=h.lua.eval('function() return false end')
        f.source.CanScout=h.lua.eval('function() return true end')
        f.source.CombatFrame=h.lua.eval("""function(self,native,targets)
            self.lastFrameTargets=#targets
            if self.failFrame then error('native frame failed') end
            if self.yieldFrame then coroutine.yield('daily-native-frame') end
            local rows={};for _,r in ipairs(targets) do rows[tostring(r.userId)]={remainingDaily=self.dailyRemaining or 5,cooldownLeft=0,sameFamily=false,manualWarning=false} end
            return {ownUserId=1,ownFamilyId=native.family and native.family.id or 0,attack=200,health=native.pools.health,maxHealth=100,stamina=native.pools.stamina,
                hospitalHealth=20,staminaCost=1,scoutCost=1,maxStaminaCost=5,dailyTargetCap=5,targetCooldown=30,
                fightVariance=.2,fightVarianceCap=5000,busy=false,shielded=false,globalCooldown=0,targets=rows}
        end""")
        deps={'identity':h.session,'fingerprint':'a'*64,'release':'release-a','storage':f.f.base.storage,
            'nativeReadSource':f.source,'fightReceipts':f.owner,'combatRules':{'hospitalHealth':20,'staminaCost':1,'dailyTargetCap':5}}
        for name in ('HitListQuery','PlayerTargetState','BlockedFight','PlayerProfileQuery','FightReceipts','PlayerFightEvidence',
                'PlayerScoutEvidence','PlayerFightLedger','PlayerFightPlanner','TargetSelection'):
            deps[name]=h.load('src/tabs/combat/'+name+'.luau')
        for _,reader,planner,evidence in combat_fixture.ROWS:
            deps[reader]=h.load('src/game/'+reader+'.luau');deps[planner]=h.load('src/features/'+planner+'.luau')
            deps[evidence]=h.load('src/features/'+evidence+'.luau')
        tab=h.load('src/tabs/combat/Module.luau').new(lua_table(h.lua,deps))
        f.production_player_evidence=tab.playerEvidence
        return tab
    def seed(self,hidden,own_family=None,target_family=0,war=None,war_targets=None,extra=False,native_public=False):
        f,h=self.f,self.h;raw=f.result.before;raw.native.stats=lua_table(h.lua,{'maxHealth':100})
        if own_family is not None: raw.native.family=lua_table(h.lua,{'id':own_family})
        if war is not None: raw.native.derived=lua_table(h.lua,{'war':{'state':'active','enemyId':war}})
        q=f.tab.hitListQuery;request=q.Prepare(q,raw)[0]
        reply=lua_table(h.lua,{'ok':True,'list':[{'userId':42,'name':'Target B','level':128,'stamina':1,'familyId':target_family,'shielded':False}],
            'warStatus':{'day':f.result.day,'serverNow':raw.native.serverNow,'targets':[]}})
        if extra:reply.list[2]=lua_table(h.lua,{'userId':43,'name':'Other target','level':128,'stamina':1,'familyId':target_family,'shielded':False})
        if war is not None: reply.warStatus.summary=lua_table(h.lua,{'enemyId':war})
        if war_targets is not None: reply.warStatus.targets=lua_table(h.lua,war_targets)
        self.assertTrue(q.Commit(q,q.Accept(q,raw,request,reply)[0]))
        profiles=f.tab.playerProfiles
        for _ in range(2 if extra else 1):
            request=profiles.Prepare(profiles,raw)[0]
            if request is None:break
            target=request.args[1]
            response=lua_table(h.lua,{'ok':True,'profile':{'userId':target,'name':'Target B' if target==42 else 'Other target','level':128,'maxLevel':128,
                'familyId':target_family,'scoutCost':1,'statsHidden':hidden,'atk':100,'def':1,'crew':1}})
            if native_public:
                response.profile.statsHidden=None;response.profile.scoutCost=None
            self.assertTrue(profiles.Commit(profiles,profiles.Accept(profiles,raw,request,response)[0]))
    def test_first_attack_after_native_day_rollover_uses_real_evidence_and_keeps_raw_bucket(self):
        before=self.f.result.before;old_day=before.native.attackDaily.day-1
        before.native.attackDaily.day=old_day;before.native.attackDaily.counts['42']=5
        self.f.begin();self.f.send()
        records=self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)
        data=self.f.runtime.checkpoint.Recovery(self.f.runtime.checkpoint,records[1].actionKey)[0]
        self.assertEqual(data.baseline.dailyBefore,0)
        self.assertEqual(data.before.native.attackDaily.day,old_day)
        self.assertEqual(data.before.native.attackDaily.counts['42'],5)
        self.app.Set(self.app,'combat.enabled',False)
        self.f.result.after.native.stats=lua_table(self.h.lua,{'maxHealth':100});self.f.settle()
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.combat,'confirmed')
        self.assertEqual(self.f.ledger.Summary(self.f.ledger).fights,1)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
        self.assertEqual(self.f.executor.calls,1)

    def test_todays_native_repeat_winning_rollover_queue_race_is_known_unsent(self):
        raw=self.f.result.before;today=raw.native.attackDaily.day
        raw.native.attackDaily.day=today-1;raw.native.attackDaily.counts['42']=5
        self.f.begin();raw.native.attackDaily.day=today;raw.native.attackDaily.counts['42']=1
        self.f.source.dailyRemaining=4;self.f.executor.queued[1]()
        self.assertEqual(self.f.executor.calls,0)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'combat')[0].attackSpent,0)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)

    def test_native_day_rollover_does_not_reset_owned_spend_or_unknown_receipt(self):
        self.f.begin();self.f.send()
        raw=self.f.result.before;raw.native.serverNow+=86400;raw.capturedAt=86401;raw.revision+=1
        self.f.result.day=int(raw.native.serverNow//86400);self.h.at(86401);self.seed(False);self.f.step(raw)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.combat,'skipped_unconfirmed')
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'combat')[0].attackSpent,5)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),1)
        self.assertEqual(self.f.executor.calls,1);self.assertEqual(len(self.f.executor.queued),1)

    def test_daily_only_defaults_on_and_replicated_repeat_is_blocked_without_charge(self):
        self.assertTrue(self.app.model['values']['combat.custom.dailyOnly'])
        self.f.result.before.native.attackDaily.counts['42']=1
        self.app.Set(self.app,'combat.enabled',True);self.app.Resume(self.app);self.f.step()
        self.assertEqual(len(self.f.executor.queued),0);self.assertEqual(self.f.executor.calls,0)
    def test_daily_only_explicit_off_allows_repeat_within_other_caps(self):
        self.f.result.before.native.attackDaily.counts['42']=1;self.f.source.dailyRemaining=4
        self.assertTrue(self.app.Set(self.app,'combat.custom.dailyOnly',False)[0])
        self.f.begin();self.f.send();self.assertEqual(self.f.executor.calls,1)
    def test_native_repeat_after_queue_refuses_before_send_and_refunds_unsent_charge(self):
        self.f.begin();self.f.source.dailyRemaining=4
        self.f.executor.queued[1]();self.assertEqual(self.f.executor.calls,0)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'combat')[0].attackSpent,0)
    def test_enabling_daily_only_cancels_a_queued_repeat(self):
        self.f.result.before.native.attackDaily.counts['42']=1;self.f.source.dailyRemaining=4
        self.app.Set(self.app,'combat.custom.dailyOnly',False);self.f.begin()
        self.app.Set(self.app,'combat.custom.dailyOnly',True);self.f.step();self.f.executor.queued[1]()
        self.assertEqual(self.f.executor.calls,0)
    def test_saved_settled_history_blocks_repeat_after_reload_even_if_native_counts_omit_it(self):
        self.f.begin();self.f.send();self.f.result.after.native.stats=lua_table(self.h.lua,{'maxHealth':100});self.f.settle()
        self.app.Destroy(self.app);self.h.session['session']='daily-reload'
        raw=self.f.result.before;raw.session='daily-reload';raw.revision=1;raw.capturedAt=31
        raw.native.serverNow+=31;raw.native.attackDaily.counts=self.h.lua.table();self.h.at(31)
        self.f.start();self.app=self.f.app;self.seed(False)
        for key,value in [('minimumPayout',0),('minSamples',0),('maxAttackSpend',10),('maxStaminaCost',5)]:
            self.app.Set(self.app,'combat.custom.'+key,value)
        self.app.Set(self.app,'combat.enabled',True);self.app.Resume(self.app);self.f.step()
        self.assertEqual(self.f.ledger.Summary(self.f.ledger).fights,1)
        self.assertEqual(len(self.f.executor.queued),0);self.assertEqual(self.f.executor.calls,0)
        self.app.Set(self.app,'combat.custom.dailyOnly',False);self.f.step()
        self.assertEqual(len(self.f.executor.queued),1)
    def test_unknown_attack_stays_held_after_cooldown_even_with_daily_option_off(self):
        self.f.begin();self.f.send();self.h.at(45);raw=self.f.result.after
        raw.capturedAt=45;raw.native.stats=lua_table(self.h.lua,{'maxHealth':100});self.f.step(raw)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.combat,'skipped_unconfirmed')
        self.app.Set(self.app,'combat.custom.dailyOnly',False);self.app.Set(self.app,'combat.custom.maxAttackSpend',100)
        self.f.result.before=raw;raw.revision+=1;raw.capturedAt=91;raw.native.serverNow+=91;self.h.at(91);self.seed(False)
        self.f.step(raw);self.assertEqual(len(self.f.executor.queued),1);self.assertEqual(self.f.executor.calls,1)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),1)
    def test_missing_or_faulting_native_daily_preflight_refuses_without_rpc(self):
        for change in ('missing','raises'):
            self.tearDown();self.setUp();self.f.begin()
            if change=='missing':self.f.source.CombatFrame=None
            else:self.f.source.failFrame=True
            self.f.executor.queued[1]();self.assertEqual(self.f.executor.calls,0)
            self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'combat')[0].attackSpent,0)
    def test_yielded_native_daily_preflight_fences_unload_and_method_replacement(self):
        for change in ('unload','method'):
            self.tearDown();self.setUp();self.f.begin();self.f.source.yieldFrame=True
            self.h.lua.globals().dailyQueuedCallback=self.f.executor.queued[1]
            value=self.h.lua.execute('dailyQueueThread=coroutine.create(dailyQueuedCallback);local ok,value=coroutine.resume(dailyQueueThread);assert(ok);return value')
            self.assertEqual(value,'daily-native-frame')
            if change=='unload':self.app.Destroy(self.app)
            else:self.f.source.CombatFrame=None
            self.h.lua.execute('assert(coroutine.resume(dailyQueueThread))');self.assertEqual(self.f.executor.calls,0)
    def test_priority_change_cancels_queued_work_without_sending_or_charging(self):
        self.f.begin();self.assertTrue(self.app.Set(self.app,'combat.custom.targetPriority','Recent payout')[0])
        self.f.step();self.f.executor.queued[1]();self.assertEqual(self.f.executor.calls,0)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'combat')[0].attackSpent,0)
    def test_final_daily_preflight_reads_only_the_selected_target(self):
        self.seed(False,extra=True);self.f.begin();self.assertEqual(self.f.source.lastFrameTargets,2)
        self.f.send();self.assertEqual(self.f.source.lastFrameTargets,1)
    def test_minimum_native_quote_blocks_before_any_attack_or_scout_reservation(self):
        self.assertTrue(self.app.Set(self.app,'combat.custom.minStaminaCost',2)[0])
        self.app.Set(self.app,'combat.custom.allowScout',True);self.app.Set(self.app,'combat.enabled',True)
        self.app.Resume(self.app);self.f.step();self.assertEqual(len(self.f.executor.queued),0)
        self.assertEqual(self.f.executor.calls,0)
        self.app.Set(self.app,'combat.custom.minStaminaCost',1);self.f.step()
        self.assertEqual(len(self.f.executor.queued),1)
    def test_minimum_quote_change_cancels_queued_attack_without_attempt_charge(self):
        self.f.begin();self.app.Set(self.app,'combat.custom.minStaminaCost',2);self.f.step()
        self.f.executor.queued[1]();self.assertEqual(self.f.executor.calls,0)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'combat')[0].attackSpent,0)
    def test_actual_public_target_planner_dispatches_and_settles_with_maximum_allowance(self):
        self.f.begin();self.f.send();self.f.result.after.native.stats=lua_table(self.h.lua,{'maxHealth':100});self.f.settle()
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.combat,'confirmed')
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'combat')[0].attackSpent,5)
        self.assertEqual(self.f.ledger.Summary(self.f.ledger).fights,1)
    def test_native_public_profile_with_no_scout_quote_can_attack_through_actual_app(self):
        self.f.tab.playerProfiles.cache=self.h.lua.table()
        self.seed(False,native_public=True)
        self.assertIsNone(self.f.tab.playerProfiles.cache['42'].scoutCost)
        self.f.begin();self.f.send()
        self.f.result.after.native.stats=lua_table(self.h.lua,{'maxHealth':100});self.f.settle()
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.combat,'confirmed')
        self.assertEqual(self.f.ledger.Summary(self.f.ledger).fights,1)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'combat')[0].scoutSpent,0)
    def test_zero_cap_and_unknown_friendship_cannot_dispatch(self):
        self.app.Set(self.app,'combat.custom.maxAttackSpend',0);self.app.Set(self.app,'combat.enabled',True);self.app.Resume(self.app);self.f.step()
        self.assertEqual(len(self.f.executor.queued),0)
        self.app.Set(self.app,'combat.custom.maxAttackSpend',5)
        self.f.tab.playerProfiles.cache['42'].friend=None;self.f.tab.playerProfiles.cache['42'].friendshipStatus='unknown'
        self.f.step();self.assertEqual(len(self.f.executor.queued),0)
    def test_target_profile_change_after_queue_refuses_before_mutation(self):
        self.f.begin();self.f.tab.playerProfiles.cache['42'].friend=True;self.f.executor.queued[1]()
        self.assertEqual(self.f.executor.calls,0)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'combat')[0].attackSpent,0)
    def test_hidden_target_needs_separate_scout_consent_and_uses_scout_mapping(self):
        self.f.tab.playerProfiles.cache['42'].statsHidden=True;self.f.tab.playerProfiles.cache['42'].defense=None
        self.app.Set(self.app,'combat.enabled',True);self.app.Resume(self.app);self.f.step();self.assertEqual(len(self.f.executor.queued),0)
        self.app.Set(self.app,'combat.custom.allowScout',True);self.f.step()
        self.assertEqual(len(self.f.executor.queued),1,str(dict(self.f.runtime.Status(self.f.runtime).reasons.items())))
        self.f.executor.InvokeOwned=self.h.lua.eval("function(self,token,remote,method,target) assert(remote=='ScoutPlayer' and target==42);self.calls=self.calls+1;return {ok=true,atk=100,def=1,crew=1} end")
        self.f.send();raw=self.f.result.after;raw.native.stats=lua_table(self.h.lua,{'maxHealth':100});raw.native.attackDaily.counts['42']=None
        self.h.at(.25);raw.capturedAt=.25;self.f.step(raw)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.combat,'confirmed')
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'combat')[0].scoutSpent,5)
        self.assertEqual(self.f.tab.playerProfiles.Read(self.f.tab.playerProfiles,raw)['42'].scout.defense,1)
    def test_profile_shield_or_changed_followup_quote_cancels_queued_scout_as_unsent(self):
        for change in ('shield','quote'):
            with self.subTest(change=change):
                if change=='quote': self.tearDown();self.setUp()
                self.f.tab.playerProfiles.cache['42'].statsHidden=True;self.f.tab.playerProfiles.cache['42'].defense=None
                self.app.Set(self.app,'combat.custom.allowScout',True);self.f.begin()
                if change=='shield':
                    self.f.tab.playerProfiles.cache['42'].shieldUntil=self.f.result.now+20
                else: self.f.tab.hitListQuery.observed.rows[1].stamina=3
                self.f.executor.queued[1]()
                self.assertEqual(self.f.executor.calls,0)
                self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'combat')[0].scoutSpent,0)
    def test_scout_then_attack_uses_cached_stats_separate_caps_and_native_spacing(self):
        self.scout_then_attack()

    def test_scout_result_survives_quote_invalidated_list_until_fresh_read(self):
        self.scout_then_attack(refresh_list=True)

    def scout_then_attack(self,refresh_list=False):
        f,h=self.f,self.h
        if refresh_list:
            f.result.before.native.respect=0;self.seed(True)
        f.tab.playerProfiles.cache['42'].statsHidden=True;f.tab.playerProfiles.cache['42'].defense=None
        self.app.Set(self.app,'combat.custom.allowScout',True);f.begin()
        attackInvoke=f.executor.InvokeOwned
        f.executor.InvokeOwned=h.lua.eval("function(self,token,remote,method,target) assert(remote=='ScoutPlayer');self.calls=self.calls+1;return {ok=true,atk=100,def=1,crew=1} end")
        f.send();self.h.at(.25)
        scoutAfter=h.snapshot(revision=2,capturedAt=.25,native={'fullSync':True,'serverNow':f.result.now+1,
            'pools':{'stamina':19,'health':100},'stats':{'maxHealth':100},'attackDaily':{'day':f.result.day,'counts':{}}})
        if refresh_list:scoutAfter.native.respect=1
        f.step(scoutAfter);self.assertEqual(len(f.executor.queued),1)
        if refresh_list:
            self.assertIsNone(f.tab.hitListQuery.Read(f.tab.hitListQuery,scoutAfter))
            self.assertIsNotNone(f.tab.playerProfiles.scoutCache['42'],
                'A confirmed Scout result must survive temporary absence of a current list')
            self.assertEqual(f.tab.playerProfiles.scoutCache['42'].at,f.result.now)
            self.assertEqual(f.runtime.checkpoint.Allowance(f.runtime.checkpoint,'combat')[0].scoutSpent,5)
        h.at(1)
        nextRaw=h.snapshot(revision=3,capturedAt=1,native={'fullSync':True,'serverNow':f.result.now+2,
            'pools':{'stamina':19,'health':100},'stats':{'maxHealth':100},'attackDaily':{'day':f.result.day,'counts':{}}})
        if refresh_list:
            nextRaw.native.respect=1;f.result.before=nextRaw;self.seed(True)
        f.step(nextRaw);self.assertEqual(len(f.executor.queued),2,str(dict(f.runtime.Status(f.runtime).reasons.items())))
        self.assertEqual(f.runtime.session.broker.active.proposal.intent.kind,'playerAttack')
        f.executor.InvokeOwned=attackInvoke
        first=lua_table(h.lua,f.result.initial);first.targetDaily.serverNow=f.result.now+2
        h.lua.globals().fixtureFightReply=first;f.executor.queued[2]();self.assertEqual(f.executor.calls,2)
        f.source.callback('fightcash','',lua_table(h.lua,f.result.final))
        h.at(1.25)
        after=h.snapshot(revision=4,capturedAt=1.25,native={'fullSync':True,'serverNow':f.result.now+3,
            'pools':{'stamina':18,'health':100},'stats':{'maxHealth':100},'attackDaily':{'day':f.result.day,'counts':{'42':1}}})
        f.step(after)
        usage=f.runtime.checkpoint.Allowance(f.runtime.checkpoint,'combat')[0]
        self.assertEqual((usage.attackSpent,usage.scoutSpent),(5,5));self.assertEqual(f.ledger.Summary(f.ledger).fights,1)
        h.at(2);after.revision=5;after.capturedAt=2;after.native.serverNow+=1;f.step(after)
        self.assertEqual(len(f.executor.queued),2)
    def test_actual_planner_records_loss_as_execution_with_zero_win_history(self):
        first=lua_table(self.h.lua,self.f.result.initial);first.won=False
        final=lua_table(self.h.lua,self.f.result.final);final.won=False;final.cashConfirmed=0;final.stolen=0
        self.h.lua.globals().fixtureFightReply=first;self.f.begin();self.f.send()
        self.f.source.callback('fightcash','',final);self.h.at(.25)
        self.f.result.after.capturedAt=.25;self.f.result.after.native.stats=lua_table(self.h.lua,{'maxHealth':100});self.f.step(self.f.result.after)
        summary=self.f.ledger.Summary(self.f.ledger)
        self.assertEqual((summary.fights,summary.wins,summary.cash),(1,0,0))
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.combat,'confirmed')
    def test_canceled_native_fight_stays_unconfirmed_and_never_refunds_the_sent_allowance(self):
        self.f.begin();self.f.send();canceled=lua_table(self.h.lua,self.f.result.final);canceled.ok=False
        self.f.source.callback('fightcash','',canceled)
        self.h.at(45);raw=self.f.result.after;raw.capturedAt=45;raw.native.stats=lua_table(self.h.lua,{'maxHealth':100});raw.native.pools.stamina=20
        self.f.step(raw)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.combat,'skipped_unconfirmed')
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'combat')[0].attackSpent,5)
        self.assertEqual(self.f.ledger.Summary(self.f.ledger).fights,0)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),1)
    def test_active_enemy_is_excluded_but_unrelated_family_ordinary_target_can_dispatch(self):
        self.seed(False,'own-family','enemy-family','enemy-family')
        self.app.Set(self.app,'combat.enabled',True);self.app.Resume(self.app);self.f.step()
        self.assertEqual(len(self.f.executor.queued),0)
        self.seed(False,'own-family','other-family','enemy-family');self.f.step()
        self.assertEqual(len(self.f.executor.queued),1,str(dict(self.f.runtime.Status(self.f.runtime).reasons.items())))
        self.f.send();self.assertEqual(self.f.executor.calls,1)
    def test_queued_ordinary_attack_cancels_if_target_becomes_enemy_without_another_rpc(self):
        self.seed(False,'own-family','other-family','enemy-family');self.f.begin()
        raw=self.f.result.before;raw.revision+=1;raw.capturedAt=.25;raw.native.serverNow+=1
        raw.native.derived.war.enemyId='other-family';self.h.at(.25);self.f.step()
        self.f.executor.queued[1]();self.assertEqual(self.f.executor.calls,0)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'combat')[0].attackSpent,0)
    def test_enemy_roster_membership_overrules_conflicting_ordinary_family_metadata(self):
        self.seed(False,'own-family','other-family','enemy-family',[{'userId':42,'familyId':'enemy-family'}])
        self.app.Set(self.app,'combat.enabled',True);self.app.Resume(self.app);self.f.step()
        self.assertEqual(len(self.f.executor.queued),0)
        self.assertEqual(self.f.executor.calls,0)
    def commit_independent_enemy_roster(self,target=42):
        q=self.f.tab.warRosterQuery;raw=self.f.result.before;call=q.Prepare(q,raw)[0]
        reply=lua_table(self.h.lua,{'ok':True,'warStatus':{'day':self.f.result.day,'serverNow':raw.native.serverNow+.5,
            'summary':{'enemyId':'enemy-family'},'targets':[{'userId':target,'name':'Target B','level':128,'familyId':'enemy-family'}]}})
        self.assertTrue(q.Commit(q,q.Accept(q,raw,call,reply)[0]))
    def test_independent_enemy_roster_blocks_conflicting_ordinary_selection(self):
        self.seed(False,'own-family','other-family','enemy-family');self.commit_independent_enemy_roster()
        self.app.Set(self.app,'combat.enabled',True);self.app.Resume(self.app);self.f.step()
        self.assertEqual(len(self.f.executor.queued),0)
    def test_independent_enemy_roster_refuses_already_queued_ordinary_dispatch(self):
        self.seed(False,'own-family','other-family','enemy-family');self.f.begin();self.commit_independent_enemy_roster()
        self.f.executor.queued[1]();self.assertEqual(self.f.executor.calls,0)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'combat')[0].attackSpent,0)
    def test_independent_roster_preserves_unrelated_ordinary_target_permission(self):
        self.seed(False,'own-family','other-family','enemy-family');self.commit_independent_enemy_roster(43)
        self.f.begin();self.f.send();self.assertEqual(self.f.executor.calls,1)
    def test_actual_planner_terminal_receipt_recovers_hard_interruption_with_caps_intact(self):
        f,h=self.f,self.h
        f.begin();f.send()
        f.source.callback('fightcash','',lua_table(h.lua,f.result.final))
        self.assertEqual(f.ledger.Summary(f.ledger).fights,1)
        self.assertEqual(f.runtime.checkpoint.Allowance(f.runtime.checkpoint,'combat')[0].attackSpent,5)
        f.owner.Close(f.owner);f.ledger.Close(f.ledger);f.runtime.session.Close(f.runtime.session)
        h.session['session']='fresh-session';f.start();self.app=f.app
        raw=f.result.after;raw.session='fresh-session';raw.revision=3;raw.capturedAt=.25;h.at(.25)
        raw.native.stats=lua_table(h.lua,{'maxHealth':100});f.step(raw)
        self.assertEqual(f.runtime.Status(f.runtime).recoveries.combat,'confirmed')
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)),0)
        self.assertEqual(f.runtime.checkpoint.Allowance(f.runtime.checkpoint,'combat')[0].attackSpent,5)
        self.assertEqual(f.executor.calls,0)
        self.assertEqual(f.ledger.Summary(f.ledger).fights,1)

    def tearDown(self):self.f.tearDown()
