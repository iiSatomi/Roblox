"""Actual App sabotage never treats unknown owner relations as safe."""
import unittest

import test_heist_protocol_app as fixture
from engine_harness import lua_table


class SabotageRelationsAppTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.HeistProtocolAppTests()
        self.f.setUp()
        self.h, self.app, self.raw = self.f.h, self.f.app, self.f.raw
        self.raw.native.family = lua_table(self.h.lua, {"id": "own-family"})
        self.raw.localUserIdProof = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 0, "userId": 7})
        self.row = self.raw.heistBoardProof.board.rows[1]
        self.row.ownerId, self.row.ownerName, self.row.ownerLevel = 42, "Owner", 20
        self.row.friend, self.row.famId, self.row.famRel = False, "other-family", None
        board = self.raw.heistBoardProof.board
        board.saboFavorCost, board.saboEnergyCost, board.saboMaxPerHeist = 2, 3, 5

    def tearDown(self):
        self.f.tearDown()

    def start(self):
        self.f.start("sabotage")

    def publish_changed_board(self):
        self.f.later(.25, False)
        self.raw.localUserIdProof.capturedAt = .25
        self.app.Step(self.app, self.raw)

    def assert_no_send(self):
        self.start()
        self.f.executor.Drain(self.f.executor)
        self.assertEqual(len(self.f.executor.calls), 0)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)), 0)
        self.assertIsNone(self.f.port.pending)

    def test_explicit_foreign_family_and_nonfriend_can_reach_owned_offline_transport(self):
        self.start()
        self.f.executor.Drain(self.f.executor)
        self.assertEqual(len(self.f.executor.calls), 1)
        self.assertEqual(self.f.executor.calls[1].args[1], "sabotage")

    def test_own_family_id_without_famrel_never_sends(self):
        self.row.famId = "own-family"
        self.assert_no_send()

    def test_missing_friendship_is_unknown_even_with_foreign_family_id(self):
        self.row.friend = None
        self.assert_no_send()

    def test_missing_owner_family_is_unknown_even_with_explicit_nonfriend(self):
        self.row.famId = None
        self.assert_no_send()

    def test_missing_own_family_is_not_inferred_as_familyless(self):
        self.raw.native.family = None
        self.assert_no_send()

    def test_owner_family_change_after_queue_refuses_before_emission(self):
        self.start()
        self.assertEqual(len(self.f.executor.queued), 1)
        self.row.famId = "own-family"
        self.publish_changed_board()
        self.f.executor.Drain(self.f.executor)
        self.assertEqual(len(self.f.executor.calls), 0)

    def test_unknown_friendship_after_queue_refuses_before_emission(self):
        self.start()
        self.assertEqual(len(self.f.executor.queued), 1)
        self.row.friend = None
        self.publish_changed_board()
        self.f.executor.Drain(self.f.executor)
        self.assertEqual(len(self.f.executor.calls), 0)


class SabotageOwnerPolicyAppTests(unittest.TestCase):
    def setUp(self):
        self.base = SabotageRelationsAppTests()
        self.base.setUp()
        self.f, self.h, self.app = self.base.f, self.base.h, self.base.app
        self.source = self.h.lua.execute("return {valid=true,Current=function(s) return s.valid end}")
        self.relations = self.h.load("src/tabs/combat/TargetSelection.luau")
        self.f.heists.deps.TargetSelection = self.relations
        self.f.heists.ownerFamilies = self.h.load("src/tabs/heists/OwnerFamilyQuery.luau").new(
            lua_table(self.h.lua, self.h.session), "a" * 64, self.source, self.relations)
        self.reader = self.h.load("src/transport/NativeSnapshotReader.luau").new(
            lua_table(self.h.lua, self.h.session), self.h.clock, "a" * 64)
        self.reader.ObserveSync(self.reader, self.base.raw.native)
        self.h.lua.globals().sabotageReader = self.reader
        self.proxy = self.h.lua.execute("""return {
            Capture=function() local raw=sabotageReader:Capture();raw.localUserIdProof={
                account=raw.account,capturedAt=raw.capturedAt,userId=7};return raw end,
            AttachHeistBoard=function(_,raw) return sabotageReader:AttachHeistBoard(raw) end}
        """)
        self.h.lua.globals().sabotageProxy = self.proxy
        self.h.lua.globals().sabotageBoard = self.base.raw.heistBoardProof.board
        self.profile = lua_table(self.h.lua, {"ok": True, "profile": {
            "userId": 42, "name": "Owner", "level": 20, "familyId": "other-family"}})
        self.h.lua.globals().sabotageProfile = self.profile
        self.f.executor.InvokeOwned = self.h.lua.eval("""function(s,token,remote,method,...)
            local args=table.pack(...);s.calls[#s.calls+1]={remote=remote,args=args}
            if remote=='HeistAction' and args[1]=='board' then return sabotageBoard end
            if remote=='PlayerProfile' then return sabotageProfile end
            return s.reply
        end""")
        self.install_reads()
        self.assertTrue(self.app.Set(self.app, "alliance.enemies", "other-family")[0])
        self.assertTrue(self.app.Set(self.app, "alliance.mode", "Enemies only")[0])

    def install_reads(self):
        sources = self.f.heists.ReadSources(self.f.heists, self.proxy)
        budget = self.h.load("src/engine/ReadBudget.luau").new(self.h.clock, lua_table(self.h.lua, [
            {"id": source.id, "interval": source.interval} for source in sources.values()]), 5, 60)
        self.f.runtime.readSources = sources
        self.f.runtime.readCoordinator = self.h.load("src/transport/ReadCoordinator.luau").new(lua_table(self.h.lua, {
            "clock": self.h.clock, "lane": self.f.lane, "budget": budget, "executor": self.f.executor,
            "sources": sources, "currentSnapshot": self.h.lua.eval("function() return sabotageProxy:Capture() end")}))
    def tearDown(self):
        self.base.tearDown()

    def step(self, at=0):
        self.h.at(at)
        return self.app.Step(self.app, self.proxy.Capture(self.proxy))

    def mutations(self):
        return [call for call in self.f.executor.calls.values()
                if call.remote == "HeistAction" and call.args[1] == "sabotage"]

    def profile_queue(self):
        self.assertTrue(self.app.Set(self.app, "sabotage.enabled", True)[0])
        self.app.Resume(self.app)
        self.step()
        self.f.executor.Drain(self.f.executor)
        self.step(.25)

    def ready_to_send(self):
        self.profile_queue()
        self.f.executor.Drain(self.f.executor)
        self.step(.5)

    def test_verified_selected_enemy_reaches_owned_app_transport_and_custody(self):
        self.ready_to_send()
        self.f.executor.Drain(self.f.executor)
        self.assertEqual([call.remote for call in self.f.executor.calls.values()],
            ["HeistAction", "PlayerProfile", "HeistAction"])
        self.assertEqual(len(self.mutations()), 1)
        self.assertEqual(self.mutations()[0].args[2], "run-1")
        records = self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)
        self.assertEqual(len(records), 1)
        saved = self.f.runtime.checkpoint.Recovery(self.f.runtime.checkpoint, records[1].actionKey)[0]
        self.assertEqual(saved.before.sabotageOwnerProof.rows[1].familyId, "other-family")
        self.assertIsNotNone(self.f.heists.deps.SabotageEvidence.capture(saved.proposal, saved.before)[0])

    def test_ally_beats_same_selected_enemy_and_never_uses_profile_or_mutation(self):
        self.app.Set(self.app, "alliance.allies", "other-family")
        self.ready_to_send()
        self.f.executor.Drain(self.f.executor)
        self.assertEqual(len(self.f.executor.calls), 1)
        self.assertEqual(self.mutations(), [])

    def test_changed_profile_family_holds_exact_owner(self):
        self.profile.profile.familyId = "changed-family"
        self.ready_to_send()
        self.f.executor.Drain(self.f.executor)
        self.assertEqual([call.remote for call in self.f.executor.calls.values()], ["HeistAction", "PlayerProfile"])
        self.assertEqual(self.mutations(), [])
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)), 0)

    def test_missing_profile_family_holds_exact_owner(self):
        self.profile.profile.familyId = None
        self.ready_to_send()
        self.f.executor.Drain(self.f.executor)
        self.assertEqual([call.remote for call in self.f.executor.calls.values()], ["HeistAction", "PlayerProfile"])
        self.assertEqual(self.mutations(), [])
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)), 0)

    def test_all_off_has_zero_remote_calls_even_with_saved_relation_preferences(self):
        self.step()
        self.f.executor.Drain(self.f.executor)
        self.assertEqual(len(self.f.executor.calls), 0)

    def test_disable_queued_profile_prevents_read_and_any_late_mutation(self):
        self.profile_queue()
        self.app.Set(self.app, "sabotage.enabled", False)
        self.step(.5)
        self.f.executor.Drain(self.f.executor)
        self.assertEqual(len(self.f.executor.calls), 1)
        self.assertEqual(self.mutations(), [])

    def test_unload_queued_profile_prevents_read_and_any_late_mutation(self):
        self.profile_queue()
        self.app.Destroy(self.app)
        self.f.executor.Drain(self.f.executor)
        self.assertEqual(len(self.f.executor.calls), 1)
        self.assertEqual(self.mutations(), [])

    def test_new_ally_setting_after_mutation_queue_refuses_before_emission(self):
        self.ready_to_send()
        self.app.Set(self.app, "alliance.allies", "other-family")
        self.f.executor.Drain(self.f.executor)
        self.assertEqual(self.mutations(), [])
        self.assertIsNone(self.f.port.pending)

    def test_profile_source_retirement_after_mutation_queue_refuses_before_emission(self):
        self.ready_to_send()
        self.source.valid = False
        self.f.executor.Drain(self.f.executor)
        self.assertEqual(self.mutations(), [])
        self.assertIsNone(self.f.port.pending)

    def test_prefer_enemies_uses_verified_enemy_before_earlier_neutral_run(self):
        self.app.Set(self.app, "alliance.mode", "Prefer enemies")
        board = self.h.lua.globals().sabotageBoard
        board.rows[2] = lua_table(self.h.lua, {"id": "run-0", "ownerId": 43, "ownerName": "Neutral",
            "ownerLevel": 20, "famId": "neutral-family", "friend": False, "heistId": "h_a",
            "endsAt": 2000100, "helpsUsed": 0, "sabosUsed": 0})
        self.ready_to_send()
        self.f.executor.Drain(self.f.executor)
        profile_calls = [c for c in self.f.executor.calls.values() if c.remote == "PlayerProfile"]
        self.assertEqual(profile_calls[0].args[1], 42)
        self.assertEqual(len(self.mutations()), 1)
        self.assertEqual(self.mutations()[0].args[2], "run-1")

    def test_allies_only_policy_accepts_verified_foreign_nonfriend(self):
        self.app.Set(self.app, "alliance.mode", "Off")
        self.app.Set(self.app, "alliance.allies", "allied-family")
        self.ready_to_send()
        self.f.executor.Drain(self.f.executor)
        self.assertEqual(len(self.mutations()), 1)

    def restart(self):
        self.app.Destroy(self.app)
        self.h.at(1)
        self.h.session["session"] = "run-b"
        deps = self.f.heists.deps
        deps.identity = lua_table(self.h.lua, self.h.session)
        deps.OwnerFamilyQuery = self.h.load("src/tabs/heists/OwnerFamilyQuery.luau")
        deps.nativeReadSource = self.source
        lease = self.h.load("src/tabs/heists/NativeHeistLease.luau").new(self.f.port, self.h.clock,
            lua_table(self.h.lua, {"account": "user-a", "place": self.h.session["place"], "jobId": "job-a", "sourceKey": "a" * 64}),
            lua_table(self.h.lua, {"id": "epoch-a", "counterSeen": self.f.port.counter}))[0]
        protocol = self.h.load("src/tabs/heists/HeistProtocol.luau").new(lua_table(self.h.lua, {
            "lease": lease, "clock": self.h.clock, "identity": self.h.session,
            "hash": self.h.lua.eval("function(text) return heistTestHash(text) end"),
            "config": {"xpForLevel": self.h.lua.eval("function() return 100 end")}}))
        deps.heistProtocol = protocol
        self.f.heists = self.h.load("src/tabs/heists/Module.luau").new(deps)
        self.f.favors = self.h.load("src/tabs/favors/Module.luau").new(deps)
        tabs = lua_table(self.h.lua, [self.f.heists, self.f.favors])
        composed, why = self.h.load("src/tabs/TabComposition.luau").build(tabs,
            self.h.load("src/ui/Catalog.luau"), self.h.load("src/engine/FeatureRegistry.luau"),
            self.h.load("src/tabs/TabSnapshotAssembler.luau"))
        self.assertIsNone(why)
        self.f.lane = self.h.load("src/engine/RequestLane.luau").new(self.h.clock)
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(
            self.h.load("src/transport/NativeCallPlan.luau"), self.f.executor, self.f.lane, self.h.clock, None, protocol)
        self.f.runtime = self.h.load("src/engine/AutomationRuntime.luau").new(lua_table(self.h.lua, {
            "clock": self.h.clock, "transport": adapter, "storage": self.f.base.base.storage,
            "identity": self.h.session, "modules": self.f.runtime.modules, "features": composed.features,
            "featurePages": composed.featurePages, "tabInstances": tabs, "snapshotAssembler": composed.snapshotAssembler}))
        self.app = self.h.load("src/App.luau").start(lua_table(self.h.lua, {
            "Ember": self.h.load("tests/ember_double.lua")(), "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"), "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "HeistsTab": self.h.load("src/tabs/heists/Module.luau"), "FavorsTab": self.h.load("src/tabs/favors/Module.luau"),
            "automationRuntimeInstance": self.f.runtime}))
        self.f.app = self.base.app = self.app
        self.reader = self.h.load("src/transport/NativeSnapshotReader.luau").new(
            lua_table(self.h.lua, self.h.session), self.h.clock, "a" * 64)
        self.base.raw.native.serverNow = 2000001
        self.h.lua.globals().sabotageBoard.serverNow = 2000001
        self.reader.ObserveSync(self.reader, self.base.raw.native)
        self.h.lua.globals().sabotageReader = self.reader
        self.install_reads()

    def test_new_app_session_retains_sent_policy_custody_without_replay(self):
        self.ready_to_send()
        self.f.executor.Drain(self.f.executor)
        records = self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)
        key = records[1].actionKey
        self.restart()
        self.assertFalse(self.app.model["values"]["sabotage.enabled"])
        records = self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[1].actionKey, key)
        saved = self.f.runtime.checkpoint.Recovery(self.f.runtime.checkpoint, key)[0]
        self.assertEqual(saved.before.session, "run-a")
        self.assertEqual(saved.before.sabotageOwnerProof.rows[1].familyId, "other-family")
        self.assertIsNotNone(self.f.heists.deps.SabotageEvidence.capture(saved.proposal, saved.before)[0])
        self.app.Set(self.app, "alliance.enemies", "other-family")
        self.app.Set(self.app, "alliance.mode", "Enemies only")
        self.app.Set(self.app, "sabotage.enabled", True)
        self.app.Resume(self.app)
        for at in (1, 1.25, 1.5):
            self.step(at)
            self.f.executor.Drain(self.f.executor)
        self.assertEqual(len(self.mutations()), 1)
        self.assertEqual(self.f.port.counter, 1)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)), 1)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).uncertainCount, 1)

    def test_untrusted_caller_owner_proof_is_stripped_before_policy_selection(self):
        self.app.Set(self.app, "sabotage.enabled", True)
        self.app.Resume(self.app)
        self.base.raw.sabotageOwnerProof = lua_table(self.h.lua, {"rows": [{"familyId": "other-family"}]})
        self.app.Step(self.app, self.base.raw)
        self.assertIsNone(self.f.runtime.latestOutcomeSnapshot.sabotageOwnerProof)
        self.assertEqual(self.mutations(), [])


if __name__ == "__main__":
    unittest.main()
