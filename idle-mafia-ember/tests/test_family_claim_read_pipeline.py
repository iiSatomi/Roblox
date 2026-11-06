"""Real Family query -> App claim -> owned follow-up query -> newer exact proof."""
import unittest
import hashlib

import test_automation_runtime as runtime_fixture
import test_combat_tab_module as combat_fixture
from engine_harness import lua_table


class FamilyClaimReadPipelineTests(unittest.TestCase):
    family_id = 9
    def setUp(self):
        base = runtime_fixture.AutomationRuntimeTests()
        base.setUp()
        self.h, self.base = base.h, base
        self.h.lua.globals().familyHash=lambda value:hashlib.sha256(value.encode()).hexdigest()
        base.storage.hash=self.h.lua.eval('function(value) return familyHash(value) end')
        base.runtime.Close(base.runtime)
        self.start_current()

    def start_current(self):
        base = self.base
        self.lane = self.h.load("src/engine/RequestLane.luau").new(self.h.clock)
        self.reader = self.h.load("src/transport/NativeSnapshotReader.luau").new(
            lua_table(self.h.lua, self.h.session), self.h.clock, "a" * 64)
        deps = {"identity": self.h.session, "fingerprint": "a" * 64, "release": "release-a",
            "combatRules": {"hospitalHealth": 20, "staminaCost": 1, "dailyTargetCap": 5}}
        for name, path in (("HitListQuery", "tabs/combat/HitListQuery"),
                ("PlayerTargetState", "tabs/combat/PlayerTargetState"),
                ("BlockedFight", "tabs/combat/BlockedFight"), ("FamilyBossQuery", "tabs/combat/FamilyBossQuery"),
                ("FamilyTakedownState", "game/FamilyTakedownState")):
            deps[name] = self.h.load(f"src/{path}.luau")
        for _, reader, planner, evidence in combat_fixture.ROWS:
            deps[reader] = self.h.load(f"src/game/{reader}.luau")
            deps[planner] = self.h.load(f"src/features/{planner}.luau")
            deps[evidence] = self.h.load(f"src/features/{evidence}.luau")
        self.tab = self.h.load("src/tabs/combat/Module.luau").new(lua_table(self.h.lua, deps))
        self.spec = next(row for row in self.tab.Descriptors(self.tab).values() if row.id == "familyBossClaims")
        self.h.lua.globals().lane = self.lane
        self.h.lua.globals().familyState = lua_table(self.h.lua, {"ok": True, "serverNow": 1050,
            "week": 100, "famId": self.family_id, "inFamily": True, "stage": 2, "resetAt": 2000,
            "freeMax": 10, "freeUsed": 0, "freeRegen": 3600, "tickets": 0, "myDmg": 120,
            "claims": [{"week": 100, "stage": 1, "expiresAt": 2000, "cash": 10, "gold": 1, "crateId": "crate_loot", "crates": 1}], "claimedStages": []})
        self.executor = self.h.lua.execute("""return {queued={},calls={},
            Schedule=function(self,fn) self.queued[#self.queued+1]=fn; return true end,
            Invoke=function() error('Unowned call') end,
            InvokeOwned=function(self,token,remote,method,...)
                assert(lane:Owns(token))
                local args=table.pack(...)
                self.calls[#self.calls+1]={remote=remote,args=args}
                if args[1]=='state' then return familyState end
                assert(remote=='FamilyBossAction' and args[1]=='claim')
                local selected,remaining=nil,{}
                for _,row in ipairs(familyState.claims) do
                    if row.week==args[2] and row.stage==args[3] then selected=row
                    else remaining[#remaining+1]=row end
                end
                if not self.noRemoval then
                    familyState.claims=remaining
                    if args[2]==familyState.week then familyState.claimedStages={args[3]} end
                end
                if not self.noAward and selected then
                    familyNative.cash=familyNative.cash+(selected.cash or 0)
                    familyNative.inventoryBound.gold_bar=(familyNative.inventoryBound.gold_bar or 0)+(selected.gold or 0)
                    local function add(id,amount)
                        if id then familyNative.inventory[id]=(familyNative.inventory[id] or 0)+amount end
                    end
                    add(selected.crateId,selected.crates or 0)
                    add(selected.medal,1);add(selected.border,1)
                end
                return self.reply or {ok=true}
            end}""")
        call_plan = self.h.load("src/transport/NativeCallPlan.luau").withCombat(
            self.h.load("src/transport/NativeCallPlan.luau"),
            self.h.load("src/tabs/combat/CombatCallPlan.luau"))
        self.transport = self.h.load("src/transport/NativeDispatchAdapter.luau").new(
            call_plan, self.executor, self.lane, self.h.clock)
        self.h.lua.globals().nativeReader, self.h.lua.globals().nativeTransport = self.reader, self.transport
        sources = self.tab.ReadSources(self.tab, self.reader)
        budget = self.h.load("src/engine/ReadBudget.luau").new(self.h.clock,
            lua_table(self.h.lua, [{"id": "familyBoss", "interval": 3}]), 5, 60)
        reads = self.h.load("src/transport/ReadCoordinator.luau").new(lua_table(self.h.lua, {
            "clock": self.h.clock, "lane": self.lane, "budget": budget, "executor": self.executor,
            "sources": sources, "currentSnapshot": self.h.lua.eval("function() return nativeReader:Capture() end"),
            "borrowLease": self.h.lua.eval("function(feature) return nativeTransport:ReadLease(feature) end")}))
        self.runtime = self.h.load("src/engine/AutomationRuntime.luau").new(lua_table(self.h.lua, {
            "clock": self.h.clock, "transport": self.transport, "storage": base.storage,
            "identity": self.h.session, "modules": base.runtime.modules, "features": [self.spec],
            "tabInstances": [self.tab], "readCoordinator": reads, "readSources": sources,
            "featurePages": {"familyBossClaims":"combat"},
            "snapshotAssembler": self.h.load("src/tabs/TabSnapshotAssembler.luau").new(lua_table(self.h.lua,[self.tab]))}))
        self.app = self.h.load("src/App.luau").start(lua_table(self.h.lua, {
            "Ember": self.h.load("tests/ember_double.lua")(), "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"), "automationRuntimeInstance": self.runtime}))
        self.native = base.raw().native
        self.h.lua.globals().familyNative = self.native
        self.native.family, self.native.serverNow = lua_table(self.h.lua, {"id": self.family_id}), 1050
        self.reader.ObserveSync(self.reader, self.native)

    def step(self):
        return self.app.Step(self.app, self.reader.Capture(self.reader)[0])

    def test_one_claim_confirmed_by_followup_read_without_releasing_its_owner(self):
        self.assertTrue(self.app.Set(self.app, "familyBossClaims.enabled", True)[0])
        self.app.Resume(self.app)
        self.step()
        self.executor.queued[1]()
        self.h.at(0.25)
        self.step()
        self.assertEqual(len(self.executor.queued), 2)
        self.executor.queued[2]()
        self.assertEqual(self.lane.Status(self.lane).active.kind, "mutation")
        self.h.at(1)
        self.native.serverNow = self.h.lua.globals().familyState.serverNow = 1051
        self.reader.ObserveSync(self.reader, self.native)
        self.step()
        self.assertIsNone(self.runtime.Status(self.runtime).outcomes.familyBossClaims)
        self.h.at(3)
        self.native.serverNow = self.h.lua.globals().familyState.serverNow = 1053
        self.reader.ObserveSync(self.reader, self.native)
        self.step()
        self.executor.queued[3]()
        self.assertEqual(self.lane.Status(self.lane).active.kind, "mutation")
        self.h.at(3.25)
        self.step()
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.familyBossClaims, "confirmed")
        self.assertIsNone(self.lane.Status(self.lane).active)
        calls = self.executor.calls
        self.assertEqual([call.args[1] for call in calls.values()], ["state", "claim", "state"])
        self.assertEqual((calls[2].args.n, calls[2].args[2], calls[2].args[3]), (3, 100, 1))
        self.assertEqual(self.native.pools.stamina, self.base.raw().native.pools.stamina)

    def test_all_off_and_unload_make_no_game_calls_and_close_tab_reader(self):
        self.step()
        self.assertEqual(len(self.executor.queued), 0)
        self.app.Set(self.app, "familyBossClaims.enabled", True)
        self.app.Resume(self.app)
        self.step()
        self.app.Destroy(self.app)
        self.executor.queued[1]()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertIsNone(self.tab.PrepareFamilyBossRead(self.tab, self.reader.Capture(self.reader)[0])[0])

    def test_attachment_rejects_wrong_source_and_new_sync_drops_old_read(self):
        raw = self.reader.Capture(self.reader)[0]
        request, _ = self.tab.PrepareFamilyBossRead(self.tab, raw)
        staged, reason = self.tab.AcceptFamilyBossRead(self.tab, raw, request, self.h.lua.globals().familyState)
        self.assertIsNone(reason)
        staged.familyTakedownProof.sourceKey = "b" * 64
        self.assertFalse(self.reader.AttachFamilyBoss(self.reader, staged))
        staged.familyTakedownProof.sourceKey = "a" * 64
        self.assertTrue(self.reader.AttachFamilyBoss(self.reader, staged))
        self.reader.ObserveSync(self.reader, self.native)
        self.assertIsNone(self.reader.Capture(self.reader)[0].familyTakedownProof)
        self.assertFalse(self.reader.AttachFamilyBoss(self.reader, staged))

    def drain(self):
        queued,self.executor.queued=self.executor.queued,self.h.lua.table()
        for callback in queued.values(): callback()
    def begin_claim(self):
        self.app.Set(self.app,"familyBossClaims.enabled",True);self.app.Resume(self.app)
        self.step();self.drain();self.h.at(.25);self.step()
        self.assertEqual(len(self.executor.queued),1,str(dict(self.runtime.Status(self.runtime).reasons.items())))
    def followup(self):
        self.h.at(3);self.native.serverNow=self.h.lua.globals().familyState.serverNow=1053
        self.reader.ObserveSync(self.reader,self.native);self.step();self.drain();self.h.at(3.25);self.step()
    def restart(self):
        native,state=self.native,self.h.lua.globals().familyState
        self.app.Destroy(self.app);self.reader.Close(self.reader)
        self.h.session['session']='new-session';self.h.at(0);self.start_current()
        self.native=native;self.h.lua.globals().familyNative=native;self.h.lua.globals().familyState=state
        native.serverNow=state.serverNow=1051;self.reader.ObserveSync(self.reader,native)
    def attach_current_read(self):
        raw=self.reader.Capture(self.reader)[0]
        request=self.tab.PrepareFamilyBossRead(self.tab,raw)[0]
        staged,why=self.tab.AcceptFamilyBossRead(self.tab,raw,request,self.h.lua.globals().familyState)
        self.assertIsNotNone(staged,why);self.assertTrue(self.reader.AttachFamilyBoss(self.reader,staged))
    def test_claim_row_removal_without_awards_stays_pending(self):
        self.executor.noAward=True;self.begin_claim();self.drain();self.followup()
        self.assertIsNone(self.runtime.Status(self.runtime).outcomes.familyBossClaims)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
    def test_awards_without_claim_consumption_stay_pending(self):
        self.executor.noRemoval=True;self.begin_claim();self.drain();self.followup()
        self.assertIsNone(self.runtime.Status(self.runtime).outcomes.familyBossClaims)
    def test_pending_reply_cannot_confirm_even_with_full_awards(self):
        self.executor.reply=lua_table(self.h.lua,{'ok':True,'pending':True});self.begin_claim();self.drain();self.followup()
        self.assertIsNone(self.runtime.Status(self.runtime).outcomes.familyBossClaims)
    def test_busy_reply_cannot_confirm_full_awards_live_or_after_restart(self):
        self.executor.reply=lua_table(self.h.lua,{'ok':True,'code':'busy'})
        self.begin_claim();self.drain();self.followup()
        self.assertIsNone(self.runtime.Status(self.runtime).outcomes.familyBossClaims)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.restart();self.attach_current_read();self.step()
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.familyBossClaims)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        usage=self.runtime.checkpoint.FamilyClaimUsage(self.runtime.checkpoint,100,0)
        self.assertEqual(list(usage.stages.values()),[1])
        self.assertEqual(len(self.executor.calls),0)

    def test_partial_award_is_never_confirmed(self):
        self.begin_claim();self.drain();self.native.inventoryBound.gold_bar=0;self.followup()
        self.assertIsNone(self.runtime.Status(self.runtime).outcomes.familyBossClaims)
    def test_reward_origin_transfer_does_not_substitute_for_bound_gold(self):
        self.begin_claim();self.drain();self.native.inventoryBound.gold_bar=0;self.native.inventory.gold_bar=1;self.followup()
        self.assertIsNone(self.runtime.Status(self.runtime).outcomes.familyBossClaims)
    def test_saved_exact_award_recovers_paused_without_replaying(self):
        self.begin_claim();self.drain();self.restart();self.attach_current_read();self.step()
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.familyBossClaims,'confirmed')
        self.assertEqual(len(self.executor.calls),0)
    def test_saved_partial_award_stays_held(self):
        self.begin_claim();self.drain();self.native.inventoryBound.gold_bar=0
        self.restart();self.attach_current_read();self.step()
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.familyBossClaims)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
    def test_queued_disable_does_not_invoke_or_consume_stage_attempt(self):
        self.begin_claim();self.app.Set(self.app,'familyBossClaims.enabled',False);self.drain()
        self.assertEqual([row.args[1] for row in self.executor.calls.values()],['state'])
        self.assertEqual(len(self.runtime.checkpoint.FamilyClaimUsage(self.runtime.checkpoint,100,.25).stages),0)
    def test_native_quote_change_after_queue_fences_claim(self):
        self.begin_claim()
        raw=self.reader.Capture(self.reader)[0];raw.familyTakedownProof.state.claims[1].gold=2
        self.reader.familyTakedownProof=raw.familyTakedownProof
        self.step();self.drain()
        self.assertEqual([row.args[1] for row in self.executor.calls.values()],['state'])
    def test_quoted_historical_medal_and_border_require_actual_item_custody(self):
        state=self.h.lua.globals().familyState
        state.claims=lua_table(self.h.lua,[{'week':99,'stage':7,'expiresAt':2000,
            'medal':'m_weekly','border':'b_weekly','cash':0,'gold':0,'crates':0}])
        self.begin_claim();self.drain();self.followup()
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.familyBossClaims,'confirmed')
        self.assertEqual(self.native.inventory.m_weekly,1);self.assertEqual(self.native.inventory.b_weekly,1)
    def test_saved_historical_award_recovers_after_row_disappears(self):
        self.h.lua.globals().familyState.claims[1].week=99
        self.begin_claim();self.drain();self.restart();self.attach_current_read();self.step()
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.familyBossClaims,'confirmed')
    def test_unknown_award_row_is_not_sent(self):
        row=self.h.lua.globals().familyState.claims[1]
        row.cash=row.gold=row.crates=row.crateId=None
        self.app.Set(self.app,'familyBossClaims.enabled',True);self.app.Resume(self.app)
        self.step();self.drain();self.h.at(.25);self.step();self.drain()
        self.assertEqual([call.args[1] for call in self.executor.calls.values()],['state'])

    def tearDown(self):
        self.app.Destroy(self.app)
        self.reader.Close(self.reader)


class StringFamilyClaimReadPipelineTests(FamilyClaimReadPipelineTests):
    """Current native Family IDs retain exact string identity through the App."""
    family_id = "family-native-abc"


if __name__ == "__main__":
    unittest.main()
