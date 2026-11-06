"""Actual mixed goal tabs share the ordinary Heist protocol and one broker."""
import unittest

import test_heist_protocol_app as heist_fixture
from engine_harness import lua_table


class BorrowedHeistGoalAppTests(unittest.TestCase):
    def setUp(self):
        self.seed = heist_fixture.HeistProtocolAppTests()
        self.seed.setUp()
        self.seed.app.Destroy(self.seed.app)
        self.h = self.seed.h
        self.base = self.seed.base.base
        self.base.storage.hash = self.h.lua.eval("function(text) return heistTestHash(text) end")
        self.base.storage.writes = self.h.lua.table()
        self.base.storage.Write = self.h.lua.eval("""function(s,key,value)
            s.writes[#s.writes+1]=key;s.data[key]=value;return true end""")
        self.port = self.seed.port
        self.scope = self.seed.protocol.lease.scope
        self.epoch = self.seed.protocol.lease.epoch
        self.raw = self.base.raw(active=[])
        self.raw.catalogKey = "a" * 64
        self.raw.contractConfig = self.raw.contractBonusConfig = self.raw.trophyCatalog = None
        self.raw.native.level = self.raw.native.maxLevel = 20
        self.raw.native.pools.energy = 20
        self.raw.native.serverNow = 2000000
        self.raw.native.derived.trophyReady = self.h.lua.table()
        self.raw.native.derived.contractDayReset = 2001000
        self.raw.native.derived.contractWeekReset = 2010000
        self.raw.native.contracts.daily[1] = lua_table(self.h.lua, {
            "id": "c_heist", "progress": 0, "goal": 1,
            "done": False, "claimed": False})
        for index in range(2, 6):
            self.raw.native.contracts.daily[index].claimed = True
        for row in self.raw.native.contracts.weekly.values():
            row.claimed = True
        self.raw.heistBoardProof = self.seed.raw.heistBoardProof
        self.start_app()

    def start_app(self):
        h = self.h
        lease = h.load("src/tabs/heists/NativeHeistLease.luau").new(
            self.port, h.clock, self.scope, self.epoch)[0]
        self.protocol = h.load("src/tabs/heists/HeistProtocol.luau").new(lua_table(h.lua, {
            "lease": lease, "clock": h.clock, "identity": h.session,
            "hash": h.lua.eval("function(text) return heistTestHash(text) end"),
            "config": {"xpForLevel": h.lua.eval("function() return 100 end")}}))
        deps = self.seed.base.heists.deps
        deps.heistProtocol = self.protocol
        self.heists = h.load("src/tabs/heists/Module.luau").new(deps)
        self.favors = h.load("src/tabs/favors/Module.luau").new(deps)
        contract_deps = {"config": {"CONTRACTS": {
            "DAILY_TIERS": [1, 1, 2, 2, 3], "WEEKLY_TIERS": [4] * 5,
            "TEMPLATES": [{"id": "c_heist", "key": "heiststarts"}],
            "BONUS": {"seals": 2, "energyRefill": True},
            "WEEKLY_BONUS": {"seals": 12, "crate": "crate_fixervault"}}},
            "fingerprint": "a" * 64, "release": "release-a"}
        trophy_deps = {"gameData": {"ITEMS": [
            {"id": key, "kind": "trophy"} for key in
            ("t_firstscore", "t_mastermind", "t_cleangetaway", "t_wrench",
             "t_accomplice", "t_streetname")], "TROPHY_TRADE_INS": {}},
            "fingerprint": "a" * 64, "release": "release-a"}
        for stem in ("ContractEntries", "ContractBonuses", "EarnedTrophies"):
            target = trophy_deps if stem == "EarnedTrophies" else contract_deps
            for suffix, folder in (("State", "game"), ("", "features"), ("Evidence", "features")):
                name = stem + suffix
                target[name] = h.load("src/" + folder + "/" + name + ".luau")
        for folder, names, target in (
            ("contracts", ("ContractGoalState", "ContractGoalBlocked", "ContractGoalRequests",
                           "ContractCashQuote", "NativeContractCatalog"), contract_deps),
            ("trophies", ("NativeTrophyCatalog", "TrophyFocusState", "TrophyFocusBlocked",
                          "TrophyGoalRequests"), trophy_deps)):
            for name in names:
                target[name] = h.load("src/tabs/" + folder + "/" + name + ".luau")
        self.contracts = h.load("src/tabs/contracts/Module.luau").new(lua_table(h.lua, contract_deps))
        self.trophies = h.load("src/tabs/trophies/Module.luau").new(lua_table(h.lua, trophy_deps))
        self.tabs = lua_table(h.lua, [self.heists, self.favors, self.contracts, self.trophies])
        composed, reason = h.load("src/tabs/TabComposition.luau").build(
            self.tabs, h.load("src/ui/Catalog.luau"), h.load("src/engine/FeatureRegistry.luau"),
            h.load("src/tabs/TabSnapshotAssembler.luau"))
        self.assertIsNone(reason)
        for feature in ("jobs", "operations", "collect"):
            composed.features[len(composed.features) + 1] = self.base.runtime.features[feature]
            composed.featurePages[feature] = feature
        self.executor = h.lua.execute("""return {calls={},queued={},reply={pending=true},
            Schedule=function(s,fn) s.queued[#s.queued+1]=fn;return true end,
            InvokeOwned=function(s,token,remote,method,...)
                s.calls[#s.calls+1]={remote=remote,args=table.pack(...),owned=true};return s.reply end,
            Invoke=function(s,remote,method,...)
                s.calls[#s.calls+1]={remote=remote,args=table.pack(...),owned=false};return s.ordinaryReply or {ok=true} end,
            Drain=function(s) local q=s.queued;s.queued={};for _,fn in ipairs(q) do fn() end end}""")
        self.lane = h.load("src/engine/RequestLane.luau").new(h.clock)
        self.adapter = h.load("src/transport/NativeDispatchAdapter.luau").new(
            h.load("src/transport/NativeCallPlan.luau"), self.executor, self.lane, h.clock, None, self.protocol)
        self.runtime = h.load("src/engine/AutomationRuntime.luau").new(lua_table(h.lua, {
            "clock": h.clock, "transport": self.adapter, "storage": self.base.storage,
            "identity": h.session, "modules": self.base.runtime.modules,
            "features": composed.features, "featurePages": composed.featurePages,
            "tabInstances": self.tabs, "snapshotAssembler": composed.snapshotAssembler}))
        self.app = h.load("src/App.luau").start(lua_table(h.lua, {
            "Ember": h.load("tests/ember_double.lua")(), "Catalog": h.load("src/ui/Catalog.luau"),
            "Settings": h.load("src/storage/Settings.luau"),
            "EmberAdapter": h.load("src/ui/EmberAdapter.luau"),
            "HeistsTab": h.load("src/tabs/heists/Module.luau"),
            "FavorsTab": h.load("src/tabs/favors/Module.luau"),
            "ContractsTab": h.load("src/tabs/contracts/Module.luau"),
            "TrophiesTab": h.load("src/tabs/trophies/Module.luau"),
            "automationRuntimeInstance": self.runtime}))

    def tearDown(self):
        self.app.Destroy(self.app)

    def select(self, trophy="t_firstscore", contract=True, starts=True, collect=True,
               trophy_borrow=True, contract_borrow=True):
        choices = {"trophyFocus.enabled": True, "trophyFocus.custom.goalId": trophy,
            "trophyFocus.custom.borrowHeists": trophy_borrow,
            "autoContracts.enabled": contract, "autoContracts.custom.borrowHeists": contract_borrow,
            "heists.enabled": starts, "heistCollect.enabled": collect}
        for key, value in choices.items():
            self.assertTrue(self.app.Set(self.app, key, value)[0], key)
        self.app.Resume(self.app)

    def later(self, t=1, run=True):
        # NativeSnapshotReader produces a fresh observation; never mutate a
        # retained pre-send snapshot while simulating the next Sync.
        self.raw = self.h.lua.eval("""function(raw)
            local function clone(value)
                if type(value)~='table' then return value end
                local result={};for k,v in pairs(value) do result[k]=clone(v) end;return result
            end
            return clone(raw) end""")(self.raw)
        self.h.at(t)
        self.raw.revision += 1
        self.raw.capturedAt = self.raw.heistBoardProof.capturedAt = t
        self.raw.native.serverNow = self.raw.heistBoardProof.board.serverNow = 2000000 + t
        if run:
            self.raw.heistBoardProof.board.mine = lua_table(self.h.lua, {
                "id": "run-a", "heistId": "h_b", "endsAt": 2001000})
            self.raw.heistBoardProof.board.startsLeft = 0

    def step(self):
        self.app.Step(self.app, self.raw)

    def drain(self):
        self.executor.Drain(self.executor)

    def records(self):
        return self.runtime.checkpoint.Records(self.runtime.checkpoint)

    def test_tab_composition_preserves_actual_goal_descriptors(self):
        self.assertIsNotNone(self.runtime.features.autoContracts.goals)
        self.assertIsNotNone(self.runtime.features.trophyFocus.goals)

    def test_contract_and_trophy_borrow_one_ordinary_owned_start(self):
        self.select()
        self.step()
        goals = self.runtime.Status(self.runtime).goals
        self.assertTrue(goals.autoContracts.routed)
        self.assertTrue(goals.trophyFocus.routed)
        self.assertEqual(self.runtime.session.broker.active.proposal.feature, "heists")
        self.drain()
        self.assertEqual(len(self.executor.calls), 1)
        self.assertTrue(self.executor.calls[1].owned)
        self.assertEqual(self.executor.calls[1].args[1], "start")
        self.assertEqual(self.executor.calls[1].args[3], 1)
        self.assertEqual(self.port.counter, 1)
        self.assertEqual(len(self.records()), 1)

    def test_sabotage_and_favor_trophies_do_not_borrow_personal_heists(self):
        for trophy in ("t_wrench", "t_accomplice"):
            self.select(trophy=trophy, contract=False)
            self.step()
            self.assertFalse(self.runtime.Status(self.runtime).goals.trophyFocus.routed, trophy)
            self.app.Set(self.app, "heists.enabled", False)
            self.drain()
            self.app.Set(self.app, "heists.enabled", True)

    def test_new_borrow_control_defaults_off_without_enabling_either_feature(self):
        for key in ("autoContracts.custom.borrowHeists", "autoContracts.enabled", "heists.enabled"):
            self.assertFalse(self.app.model["values"][key])
        self.assertEqual(self.app.ui.handles["autoContracts.custom.borrowHeists"].kind, "Toggle")

    def test_each_goal_requires_its_own_borrow_switch(self):
        self.select(trophy_borrow=False, contract_borrow=False)
        self.step()
        goals = self.runtime.Status(self.runtime).goals
        self.assertFalse(goals.autoContracts.routed)
        self.assertFalse(goals.trophyFocus.routed)
        self.drain()
        self.assertEqual(len(self.executor.calls), 1)  # The ordinary start remains explicitly enabled.

    def test_goals_cannot_enable_an_off_ordinary_heist(self):
        self.select(starts=False, collect=False)
        self.step()
        goals = self.runtime.Status(self.runtime).goals
        self.assertFalse(goals.autoContracts.routed)
        self.assertFalse(goals.trophyFocus.routed)
        self.assertIsNone(self.runtime.session.broker.active)
        self.assertEqual(len(self.executor.calls), 0)

    def test_trophy_requires_collection_while_start_contract_does_not_borrow_it(self):
        self.select(collect=False)
        self.step()
        goals = self.runtime.Status(self.runtime).goals
        self.assertTrue(goals.autoContracts.routed)
        self.assertFalse(goals.trophyFocus.routed)
        self.assertFalse(self.app.model["values"]["heistCollect.enabled"])

    def test_borrowing_preserves_selected_heist_and_ordinary_limits(self):
        self.select()
        for key, value in {"selection": "Only selected", "selectedIds": "h_a", "limitsEnabled": True,
                           "minLevel": 9.5, "maxLevel": 10, "maxHours": 1, "maxHelps": 3}.items():
            self.assertTrue(self.app.Set(self.app, "heists.custom." + key, value)[0])
        self.step()
        active = self.runtime.session.broker.active
        self.assertEqual(active.proposal.intent.heistId, "h_a")
        self.assertEqual(active.proposal.resources.cash, 100)
        self.assertEqual(active.proposal.resources.energy, 2)
        self.drain()
        self.assertEqual(self.executor.calls[1].args[2], "h_a")

    def test_limits_and_native_daily_allowance_remain_independent_goal_gates(self):
        self.select()
        self.app.Set(self.app, "heists.custom.limitsEnabled", True)
        self.app.Set(self.app, "heists.custom.maxEnergy", 0)
        self.step()
        self.assertIsNone(self.runtime.session.broker.active)
        self.assertFalse(self.runtime.Status(self.runtime).goals.autoContracts.routed)
        self.app.Set(self.app, "heists.custom.limitsEnabled", False)
        self.raw.heistBoardProof.board.startsLeft = 0
        self.later(1, False)
        self.step()
        self.assertIsNone(self.runtime.session.broker.active)
        self.assertEqual(self.raw.heistBoardProof.board.favorsLeft, 12)
        self.assertEqual(self.port.counter, 0)

    def test_start_success_requires_native_objective_progress_and_ready_not_owned(self):
        self.select()
        self.executor.reply = lua_table(self.h.lua, {"ok": True, "runId": "run-a"})
        self.step()
        self.drain()
        self.later()
        self.step()
        status = self.runtime.Status(self.runtime)
        self.assertEqual(status.outcomes.heists, "confirmed")
        self.assertEqual(status.goals.autoContracts.state, "waiting")
        self.assertEqual(status.goals.trophyFocus.state, "waiting")
        self.later(2)
        self.raw.native.contracts.daily[1].progress = 1
        self.raw.native.contracts.daily[1].done = True
        self.raw.native.derived.trophyReady = lua_table(self.h.lua, ["t_firstscore"])
        self.step()
        status = self.runtime.Status(self.runtime)
        self.assertEqual(status.goals.autoContracts.state, "complete")
        self.assertEqual(status.goals.trophyFocus.state, "ready")
        self.assertEqual(len(self.executor.calls), 1)
        self.assertEqual(len(self.records()), 0)
        self.assertEqual(self.raw.heistBoardProof.board.favorsLeft, 12)

    def test_collection_uses_owned_sequence_then_separate_native_ready_claim(self):
        heist_fixture.HeistProtocolAppTests.collect_result(self)
        self.select()
        self.step()
        self.assertTrue(self.runtime.Status(self.runtime).goals.trophyFocus.routed)
        self.assertFalse(self.runtime.Status(self.runtime).goals.autoContracts.routed)
        self.drain()
        self.assertEqual(self.executor.calls[1].args[1], "collect")
        self.assertIsNone(self.executor.calls[1].args[2])
        self.assertTrue(self.executor.calls[1].owned)
        heist_fixture.HeistProtocolAppTests.collected(self)
        self.raw.heistBoardProof.board.startsLeft = 0
        self.raw.native.derived.trophyReady = lua_table(self.h.lua, ["t_firstscore"])
        self.step()
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.heistCollect, "confirmed")
        self.assertEqual(self.runtime.Status(self.runtime).goals.trophyFocus.state, "ready")
        self.assertEqual(len(self.executor.calls), 1)
        self.app.Set(self.app, "trophies.enabled", True)
        self.step()
        self.drain()
        self.assertEqual(len(self.executor.calls), 2)
        self.assertEqual(self.executor.calls[2].remote, "ClaimTrophy")
        self.later(2, False)
        self.raw.native.inventoryBound.t_firstscore = 1
        self.raw.native.derived.trophyReady = self.h.lua.table()
        self.step()
        self.assertEqual(self.runtime.Status(self.runtime).goals.trophyFocus.state, "owned")
        self.assertEqual(self.port.counter, 1)

    def test_exact_rejection_does_not_mark_either_goal_complete(self):
        self.select()
        self.executor.reply = lua_table(self.h.lua, {"ok": False, "code": "insufficient_cash"})
        self.step()
        self.drain()
        self.later(1, False)
        self.step()
        status = self.runtime.Status(self.runtime)
        self.assertEqual(status.outcomes.heists, "rejected")
        self.assertEqual(status.goals.autoContracts.state, "waiting")
        self.assertEqual(status.goals.trophyFocus.state, "waiting")
        self.assertEqual(len(self.records()), 0)
        self.assertEqual(len(self.executor.calls), 1)
        self.assertEqual(self.port.counter, 1)

    def test_queued_ordinary_disable_cleans_native_owner_without_sending(self):
        self.select()
        self.step()
        self.app.Set(self.app, "heists.enabled", False)
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertIsNone(self.port.pending)
        self.assertEqual(len(self.records()), 0)

    def test_goal_disable_preserves_the_independently_enabled_ordinary_action(self):
        self.select()
        self.step()
        self.app.Set(self.app, "autoContracts.enabled", False)
        self.app.Set(self.app, "trophyFocus.enabled", False)
        self.drain()
        self.assertEqual(len(self.executor.calls), 1)
        self.assertTrue(self.executor.calls[1].owned)

    def test_newer_native_owner_is_not_overwritten_by_borrowed_dispatch(self):
        self.select()
        self.step()
        newer = self.h.lua.table()
        self.port.pending = newer
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertTrue(self.h.lua.eval("function(a,b) return a==b end")(self.port.pending, newer))

    def test_unload_fences_queued_goal_action_and_all_off_reload_recovers_unsent(self):
        self.select()
        self.step()
        old = self.executor
        self.app.Destroy(self.app)
        main_key = self.runtime.checkpoint.key
        writes_before = len(self.base.storage.writes)
        old.Drain(old)
        self.assertEqual(len(old.calls), 0)
        self.assertIsNone(self.port.pending)
        late_writes = [self.base.storage.writes[index]
                       for index in range(writes_before + 1, len(self.base.storage.writes) + 1)]
        self.assertNotIn(main_key, late_writes)
        self.assertEqual(len(late_writes), 1)
        self.assertIn("adapter-unsent", late_writes[0])
        self.start_app()
        self.later(1, False)
        self.step()
        self.assertEqual(len(self.records()), 0)
        self.assertEqual(len(self.executor.calls), 0)

    def test_unknown_45_second_outcome_holds_custody_and_never_replays(self):
        self.select()
        self.step()
        self.drain()
        self.later(45, False)
        self.step()
        status = self.runtime.Status(self.runtime)
        self.assertEqual(status.outcomes.heists, "skipped_unconfirmed")
        self.assertEqual(status.goals.autoContracts.state, "waiting")
        self.assertEqual(status.goals.trophyFocus.state, "waiting")
        self.assertEqual(len(self.records()), 1)
        self.assertIsNone(self.port.pending)
        self.app.Set(self.app, "jobs.enabled", True)
        self.later(46, False)
        self.step()
        self.drain()
        self.assertEqual([row.remote for row in self.executor.calls.values()], ["HeistAction", "DoJob"])
        self.assertEqual(self.port.counter, 1)
        self.assertEqual(len(self.records()), 2)

    def test_late_unsent_receipt_preserves_new_owners_job_checkpoint(self):
        self.select()
        self.step()
        old = self.executor
        self.app.Destroy(self.app)
        self.start_app()
        self.app.Set(self.app, "jobs.enabled", True)
        self.app.Resume(self.app)
        self.later(1, False)
        self.step()
        self.assertEqual(self.runtime.session.broker.active.proposal.feature, "jobs")
        self.assertEqual(len(self.records()), 2)
        self.drain()
        writes_before = len(self.base.storage.writes)
        old.Drain(old)
        late_writes = [self.base.storage.writes[index]
                       for index in range(writes_before + 1, len(self.base.storage.writes) + 1)]
        self.assertEqual(len(late_writes), 1)
        self.assertIn("adapter-unsent", late_writes[0])
        self.assertEqual(len(old.calls), 0)
        self.assertEqual(len(self.records()), 2)
        self.later(2, False)
        self.step()
        self.assertEqual(len(self.records()), 1)
        self.assertEqual(self.records()[1].feature, "jobs")
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.heists, "known_unsent")
        self.drain()
        self.assertEqual(len(self.executor.calls), 1)
        self.assertEqual(self.executor.calls[1].remote, "DoJob")

    def test_unload_during_native_invocation_never_mints_unsent_fact(self):
        self.executor.InvokeOwned = self.h.lua.eval("""function(s,token,remote,method,...)
            s.calls[#s.calls+1]={remote=remote,args=table.pack(...),owned=true}
            coroutine.yield('waiting');return {ok=true,runId='run-a'} end""")
        self.select()
        self.step()
        self.h.lua.globals().borrowedInvocation = self.executor.queued[1]
        self.h.lua.execute("borrowedThread=coroutine.create(borrowedInvocation);assert(coroutine.resume(borrowedThread))")
        self.assertEqual(len(self.executor.calls), 1)
        self.app.Destroy(self.app)
        writes_before = len(self.base.storage.writes)
        self.h.lua.execute("assert(coroutine.resume(borrowedThread))")
        self.assertEqual(len(self.base.storage.writes), writes_before)
        self.start_app()
        self.later(1, False)
        self.step()
        self.assertEqual(len(self.records()), 1)
        self.assertFalse(self.runtime.checkpoint.KnownUnsent(self.runtime.checkpoint, self.records()[1]))
        self.assertEqual(len(self.executor.calls), 0)

    def test_returned_pending_invocation_cannot_be_relabelled_unsent_after_unload(self):
        self.select()
        self.step()
        proposal = self.runtime.session.broker.active.proposal
        lifecycle = self.runtime.features.heists.lifecycle
        self.drain()
        self.app.Destroy(self.app)
        writes_before = len(self.base.storage.writes)
        self.assertFalse(lifecycle.abandonedUnsent(proposal))
        self.assertEqual(len(self.base.storage.writes), writes_before)
        self.start_app()
        self.later(1, False)
        self.step()
        self.assertEqual(len(self.records()), 1)
        self.assertEqual(len(self.executor.calls), 0)

    def test_same_native_owner_reload_can_reconcile_status_without_replay(self):
        self.select()
        self.step()
        self.drain()
        old = self.executor
        self.app.Destroy(self.app)
        self.start_app()
        self.later()
        self.step()
        self.assertEqual(len(self.records()), 1)
        call, reason = self.protocol.StatusCall(self.protocol)
        self.assertIsNone(reason)
        self.assertEqual(call.args[1], "status")
        self.protocol.AcceptStatus(self.protocol, call, lua_table(self.h.lua, {"ok": True, "runId": "run-a"}))
        self.later(2)
        self.step()
        self.assertEqual(len(self.records()), 0)
        self.assertEqual(len(old.calls), 1)
        self.assertEqual(len(self.executor.calls), 0)
        self.assertEqual(self.port.counter, 1)

    def test_saved_exact_rejection_recovers_all_off_without_new_start(self):
        self.select()
        self.executor.reply = lua_table(self.h.lua, {"ok": False, "code": "rejected"})
        self.step()
        self.drain()
        self.app.Destroy(self.app)
        self.start_app()
        self.later(1, False)
        self.step()
        self.assertEqual(len(self.records()), 0)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.heists, "rejected")
        self.assertEqual(len(self.executor.calls), 0)

    def test_selection_change_cancels_queued_start_without_spending(self):
        self.select()
        self.step()
        self.app.Set(self.app, "heists.custom.selection", "Only selected")
        self.app.Set(self.app, "heists.custom.selectedIds", "h_a")
        self.drain()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertIsNone(self.port.pending)
        self.assertEqual(len(self.records()), 0)

    def test_missing_current_native_owner_blocks_both_goal_routes(self):
        self.select()
        self.port.Current = self.h.lua.eval("function() return false end")
        self.step()
        goals = self.runtime.Status(self.runtime).goals
        self.assertFalse(goals.autoContracts.routed)
        self.assertFalse(goals.trophyFocus.routed)
        self.assertIsNone(self.runtime.session.broker.active)
        self.assertEqual(len(self.executor.calls), 0)

    def test_personal_mastermind_and_clean_getaway_share_same_bounded_completion_route(self):
        for trophy in ("t_mastermind", "t_cleangetaway"):
            self.select(trophy=trophy, contract=False)
            self.step()
            self.assertTrue(self.runtime.Status(self.runtime).goals.trophyFocus.routed)
            self.assertEqual(self.runtime.session.broker.active.proposal.feature, "heists")
            self.app.Set(self.app, "heists.enabled", False)
            self.drain()
            self.later(self.h.lua.globals().testNow + 1, False)
        self.assertEqual(len(self.executor.calls), 0)

    def test_changed_native_epoch_keeps_original_unknown_and_cannot_replay(self):
        self.select()
        self.step()
        self.drain()
        self.app.Destroy(self.app)
        self.epoch = lua_table(self.h.lua, {"id": "epoch-other", "counterSeen": 1})
        self.start_app()
        self.later()
        self.select()
        self.step()
        self.assertEqual(len(self.records()), 1)
        self.assertIsNone(self.protocol.StatusCall(self.protocol)[0])
        self.assertEqual(len(self.executor.calls), 0)
        self.assertEqual(self.port.counter, 1)

    def test_mixed_heist_contract_then_job_trophy_uses_one_broker_and_native_progress(self):
        self.select(trophy="t_streetname")
        self.app.Set(self.app, "trophyFocus.custom.borrowJobs", True)
        self.app.Set(self.app, "jobs.enabled", True)
        self.app.Set(self.app, "operations.enabled", True)
        self.app.Set(self.app, "operations.policy", "Highest tier")
        self.executor.reply = lua_table(self.h.lua, {"ok": True, "runId": "run-a"})
        self.step()
        self.drain()
        self.assertEqual(len(self.executor.calls), 1)
        self.assertEqual(self.executor.calls[1].remote, "HeistAction")
        self.later()
        self.raw.native.contracts.daily[1].progress = 1
        self.raw.native.contracts.daily[1].done = True
        self.step()
        self.assertEqual(self.runtime.session.broker.active.proposal.feature, "jobs")
        self.drain()
        self.assertEqual(len(self.executor.calls), 2)
        self.assertEqual(self.executor.calls[2].remote, "DoJob")
        self.later(2)
        self.raw.native.jobs.j_watch.completions = 1
        self.raw.native.derived.trophyReady = lua_table(self.h.lua, ["t_streetname"])
        self.step()
        status = self.runtime.Status(self.runtime)
        self.assertEqual(status.outcomes.jobs, "confirmed")
        self.assertEqual(status.goals.autoContracts.state, "complete")
        self.assertEqual(status.goals.trophyFocus.state, "ready")
        self.assertEqual(self.runtime.session.broker.active.proposal.feature, "operations")
        self.drain()
        self.assertEqual(len(self.executor.calls), 3)
        self.assertEqual(self.executor.calls[3].remote, "StartOperation")
        self.assertFalse(self.app.model["values"]["contracts.enabled"])
        self.assertFalse(self.app.model["values"]["trophies.enabled"])


if __name__ == "__main__":
    unittest.main()
