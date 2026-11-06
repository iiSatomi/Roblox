"""One durable Heist lifecycle owns start/help/sabotage/collection and status recovery."""
import hashlib
import unittest

from engine_harness import Harness, lua_table


class HeistRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.client = self.h.load("tests/fixtures/heist-client.lua")(
            self.h.load("tests/fixtures/prestige-client.lua"))
        self.client.data.serverNow = 1987300
        controller = self.h.load("src/tabs/heists/NativeHeistController.luau").bind(
            self.client.game, self.client.requireModule, self.client.readUpvalues)
        self.h.lua.globals().runtimeHash = lambda value: hashlib.sha256(value.encode()).hexdigest()
        self.deps = lua_table(self.h.lua, {"identity": self.h.session, "clock": self.h.clock,
            "nativeHeistController": controller, "fingerprint": "a" * 64, "release": "release-a",
            "sha256": self.h.lua.eval("function(v) return runtimeHash(v) end")})
        for name, path in {
            "HeistTransactions": "src/tabs/heists/HeistTransactions.luau",
            "HeistCallPlan": "src/tabs/heists/HeistCallPlan.luau",
            "HeistCollection": "src/tabs/heists/HeistCollection.luau",
            "SequenceRecovery": "src/tabs/heists/SequenceRecovery.luau",
            "PendingAction": "src/storage/PendingAction.luau",
            "HeistStartEvidence": "src/features/HeistStartEvidence.luau",
            "FavorHelpEvidence": "src/features/FavorHelpEvidence.luau",
            "SabotageEvidence": "src/features/SabotageEvidence.luau",
        }.items():
            self.deps[name] = self.h.load(path)
        self.deps.storage = self.h.lua.execute("""return {data={},strictRecovery=true,
            Read=function(self,k) return self.data[k] end,
            Write=function(self,k,v) self.data[k]=v; return true end} """)
        self.runtime, reason = self.h.load("src/tabs/heists/HeistRuntime.luau").new(self.deps)
        self.assertIsNone(reason)
        self.original = lua_table(self.h.lua, {"id": "heists",
            "reader": self.h.load("src/game/HeistBoardState.luau"),
            "planner": self.h.load("src/features/HeistStart.luau"),
            "evidence": self.deps.HeistStartEvidence})
        self.feature = self.runtime.Feature(self.runtime, self.original)

    def raw(self, revision=1, active=False):
        return self.h.snapshot(revision=revision, native={"fullSync": True, "serverNow": 1987300,
            "level": 20, "cash": 100, "pools": {"energy": 10}}, catalogKey="a" * 64,
            heistCatalog=[{"id": "h_a", "level": 10, "stake": 10, "energy": 2, "crateCount": 1}],
            heistBoardProof={"account": "user-a", "capturedAt": 0, "sourceKey": "a" * 64,
                "board": {"ok": True, "rows": [], "startsLeft": 1 if active else 2,
                    "bustWait": 0, "serverNow": 1987300,
                    "mine": {"id": "run-a", "heistId": "h_a", "endsAt": 1987400} if active else None}})

    def prepare(self):
        before = self.runtime.Enrich(self.runtime, self.raw())
        view = self.feature.reader.read(before, before)[0]
        proposal = self.feature.planner.propose(view,
            lua_table(self.h.lua, {"enabled": True, "policy": "Highest tier"}),
            lua_table(self.h.lua, {"cash": 0, "energy": 0, "uncertainCash": 0, "uncertainEnergy": 0}))[0]
        self.assertIsNotNone(proposal)
        baseline = self.feature.evidence.capture(proposal, before)[0]
        self.assertTrue(self.feature.lifecycle.prepare(proposal, before, baseline, 0)[0])
        return proposal, before, baseline

    def test_start_lifecycle_claims_before_native_call_then_settles_exact_board(self):
        proposal, before, _ = self.prepare()
        self.assertTrue(self.feature.canDispatch(proposal))
        call, why = self.feature.lifecycle.authorize(proposal, before, 0)
        self.assertIsNone(why)
        self.assertEqual(call.nativeSequence, 8)
        self.assertTrue(self.deps.nativeHeistController.Start(
            call.nativeSequence, call.args[1], call.args[2], call.recordHeistReturn))
        reply = lua_table(self.h.lua, {"ok": True, "runId": "run-a"})
        self.client.finishHeist(reply)
        self.assertTrue(self.feature.lifecycle.returned(proposal, reply)[0])
        after = self.runtime.Enrich(self.runtime, self.raw(revision=2, active=True))
        self.assertTrue(self.feature.lifecycle.resolve(proposal, "confirmed", after, 0)[0])
        self.assertIsNone(self.runtime.owner.Active(self.runtime.owner))
        self.assertTrue(self.deps.nativeHeistController.Read().controllersClear)

    def test_timeout_preserves_claim_and_stale_native_counter_blocks_dispatch(self):
        proposal, before, _ = self.prepare()
        self.feature.lifecycle.authorize(proposal, before, 0)
        self.assertTrue(self.feature.lifecycle.resolve(proposal, "skipped_unconfirmed", before, 46)[0])
        self.assertIsNotNone(self.runtime.owner.Active(self.runtime.owner))
        self.client.heistAct[2] = 8
        self.assertFalse(self.feature.canDispatch(proposal))

    def test_restart_settles_durable_late_reply_against_actual_new_session(self):
        proposal, before, baseline = self.prepare()
        call, _ = self.feature.lifecycle.authorize(proposal, before, 0)
        self.deps.nativeHeistController.Start(8, "start", "h_a", call.recordHeistReturn)
        self.client.finishHeist(lua_table(self.h.lua, {"ok": True, "runId": "run-a"}))
        self.runtime.Close(self.runtime)
        self.deps.identity = lua_table(self.h.lua, dict(self.h.session, session="run-b"))
        self.deps.nativeHeistController = self.h.load("src/tabs/heists/NativeHeistController.luau").bind(
            self.client.game, self.client.requireModule, self.client.readUpvalues)
        restored, reason = self.h.load("src/tabs/heists/HeistRuntime.luau").new(self.deps)
        self.assertIsNone(reason)
        feature = restored.Feature(restored, self.original)
        after = self.raw(revision=0, active=True)
        after.session = "run-b"
        after = restored.Enrich(restored, after)
        original_checkpoint = lua_table(self.h.lua, {"proposal": proposal, "before": before,
            "baseline": baseline})
        self.assertEqual(feature.recoverSaved(original_checkpoint, after), "confirmed")
        self.assertIsNone(restored.owner.Active(restored.owner))
        restored.Close(restored)
        reloaded, reason = self.h.load("src/tabs/heists/HeistRuntime.luau").new(self.deps)
        self.assertIsNone(reason)
        self.assertEqual(reloaded.owner.Receipt(reloaded.owner).outcome, "confirmed")

    def test_status_source_is_only_for_owned_sent_sequence_and_never_describes_start(self):
        proposal, before, _ = self.prepare()
        self.feature.lifecycle.authorize(proposal, before, 0)
        source = self.runtime.ReadSources(self.runtime)[1]
        self.assertTrue(source.enabled(self.h.lua.table()))
        call = source.prepare(before)[0]
        self.assertEqual((call.kind, call.arity), ("statusOnly", 3))
        self.assertEqual([call.args[i] for i in (1, 2, 3)], ["status", "h_a", 8])
        self.assertIsNone(source.accept(before, call,
            lua_table(self.h.lua, {"ok": False, "code": "no_pending"})))


if __name__ == "__main__":
    unittest.main()
