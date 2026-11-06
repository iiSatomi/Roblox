"""Pending action data survives JSON key coercion without authorizing replay."""
import json
import unittest
from lupa import lua_type
from engine_harness import Harness, lua_table


class PendingActionRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.module = self.h.load("src/storage/PendingAction.luau")
        self.checkpoints = self.h.load("src/storage/Checkpoint.luau")
        self.storage = self.h.lua.execute("""return {strictRecovery=true,data={},
            Read=function(self,key) return self.data[key] end,
            Write=function(self,key,value) self.data[key]=value return true end}""")
        self.checkpoint = self.checkpoints.new(self.storage, None, None, self.module)
        self.checkpoint.Load(self.checkpoint, "user-a", self.h.session["place"], "release-a")

    def before(self):
        return self.h.snapshot(native={"fullSync": True, "serverNow": 1000, "jobs": {"j_a": {"completions": 8}}},
            catalog={2: {"cost": 100}, "2": {"cost": 999}})

    def baseline(self):
        return lua_table(self.h.lua, {"beforeCompletions": 8, "sparse": {2: False, 9: "nine"}, "empty": {}})

    def plain(self, value):
        if lua_type(value) == "table":
            keys = list(value.keys())
            if keys and set(keys) == set(range(1, len(keys) + 1)):
                return [self.plain(value[index]) for index in range(1, len(keys) + 1)]
            return {key: self.plain(child) for key, child in value.items()}
        return value

    def test_pending_intent_baseline_and_numeric_string_keys_survive_json_reload(self):
        proposal = self.h.proposal()
        ok, reason = self.checkpoint.Save(self.checkpoint, proposal, self.before(), self.baseline())
        self.assertTrue(ok, reason)
        # Real JSON round trip: sparse numeric keys must not become strings.
        key = self.checkpoint.ScopeKey(self.checkpoint)
        self.storage.data[key] = lua_table(self.h.lua, json.loads(json.dumps(self.plain(self.storage.data[key]))))
        restored = self.checkpoints.new(self.storage, None, None, self.module)
        self.assertIsNone(restored.Load(restored, "user-a", self.h.session["place"], "release-a")[1])
        recovered, reason = restored.Recovery(restored, proposal.actionKey)
        self.assertIsNone(reason)
        self.assertEqual(recovered.proposal.intent.targetId, proposal.intent.targetId)
        self.assertEqual(recovered.before.catalog[2].cost, 100)
        self.assertEqual(recovered.before.catalog["2"].cost, 999)
        self.assertFalse(recovered.baseline.sparse[2])
        self.assertEqual(recovered.baseline.sparse[9], "nine")
        self.assertIsNone(recovered.baseline.sparse[1])
        recovered.proposal.intent.targetId = "changed"
        self.assertNotEqual(restored.Recovery(restored, proposal.actionKey)[0].proposal.intent.targetId, "changed")

    def test_missing_baseline_or_unserializable_data_blocks_before_storage(self):
        for baseline in (None, self.h.lua.eval("{bad=function() end}")):
            self.assertFalse(self.checkpoint.Save(self.checkpoint, self.h.proposal(), self.before(), baseline)[0])
            self.assertEqual(len(self.checkpoint.Records(self.checkpoint)), 0)

    def test_forged_recovery_and_mismatched_scope_are_not_accepted(self):
        proposal = self.h.proposal()
        proposal.recovery = lua_table(self.h.lua, {"version": 99})
        self.assertTrue(self.checkpoint.Save(self.checkpoint, proposal, self.before(), self.baseline())[0])
        encoded = self.checkpoint.Records(self.checkpoint, True)[1].recovery
        record = self.checkpoint.Records(self.checkpoint)[1]
        record.account = "other"
        self.assertIsNone(self.module.Copy(encoded, record))
        downgraded = self.checkpoints.new(self.storage)
        self.assertIsNone(downgraded.Load(downgraded, "user-a", self.h.session["place"], "release-a")[0])

    def test_broker_timeout_and_restart_retain_original_request_without_replay(self):
        self.h.policy.captureBefore = self.h.lua.eval("function(p,raw) return {beforeCompletions=8} end")
        session = self.h.load("src/engine/Session.luau").new(self.h.broker, self.checkpoint,
            lua_table(self.h.lua, self.h.session))
        try:
            proposal, before = self.h.proposal(), self.before()
            self.assertEqual(session.Offer(session, proposal, before)[0], "admitted")
            self.assertEqual(session.Tick(session, before), "sent")
            self.h.at(45)
            self.assertEqual(session.Tick(session, self.before()), "skipped_unconfirmed")
            restored = self.checkpoints.new(self.storage, None, None, self.module)
            restored.Load(restored, "user-a", self.h.session["place"], "release-a")
            recovered, reason = restored.Recovery(restored, proposal.actionKey)
            self.assertIsNone(reason)
            self.assertEqual(recovered.baseline.beforeCompletions, 8)
            self.assertEqual(recovered.before.native.jobs.j_a.completions, 8)
            self.assertEqual(len(self.h.transport.sent), 1)
        finally:
            session.Close(session)

    def test_cyclic_oversized_or_unknown_schema_data_is_rejected(self):
        cyclic = self.h.lua.eval("function() local value={} value.self=value return value end")()
        self.assertIsNone(self.module.Capture(self.h.proposal(), self.before(), cyclic)[0])
        self.assertIsNone(self.module.Capture(self.h.proposal(), self.before(), lua_table(self.h.lua, {"large": "x" * 200000}))[0])
        self.assertIsNone(self.module.Copy(lua_table(self.h.lua, {"version": 999}), self.h.proposal()))

    def test_fast_metadata_reads_omit_payload_but_later_save_and_resolve_preserve_it(self):
        first, second = self.h.proposal(), self.h.proposal("operations", "operations:second")
        self.assertTrue(self.checkpoint.Save(self.checkpoint, first, self.before(), self.baseline())[0])
        self.assertIsNone(self.checkpoint.Records(self.checkpoint)[1].recovery)
        self.assertTrue(self.checkpoint.Save(self.checkpoint, second, self.before(), self.baseline())[0])
        self.assertTrue(self.checkpoint.Resolve(self.checkpoint, second.actionKey, "schedule_failed")[0])
        self.assertIsNotNone(self.checkpoint.Recovery(self.checkpoint, first.actionKey)[0])

    def test_native_result_is_persisted_but_never_counted_as_confirmation(self):
        self.h.policy.captureBefore = self.h.lua.eval("function() return {beforeCompletions=8} end")
        session = self.h.load("src/engine/Session.luau").new(self.h.broker, self.checkpoint,
            lua_table(self.h.lua, self.h.session))
        try:
            proposal, before = self.h.proposal(), self.before()
            session.Offer(session, proposal, before)
            session.Tick(session, before)
            self.h.transport.callbacks[1](lua_table(self.h.lua, {"ok": True, "job": "j_a"}))
            self.assertEqual(session.Status(session).active.phase, "returned")
            self.assertEqual(len(self.checkpoint.Records(self.checkpoint)), 1)
            restored = self.checkpoints.new(self.storage, None, None, self.module)
            restored.Load(restored, "user-a", self.h.session["place"], "release-a")
            self.assertTrue(restored.Recovery(restored, proposal.actionKey)[0].reply.ok)
            self.assertFalse(restored.RecordReply(restored, proposal.actionKey,
                lua_table(self.h.lua, {"ok": False}))[0])
            self.assertTrue(restored.Recovery(restored, proposal.actionKey)[0].reply.ok)
        finally:
            session.Close(session)

    def test_malformed_return_does_not_destroy_original_baseline(self):
        proposal = self.h.proposal()
        self.checkpoint.Save(self.checkpoint, proposal, self.before(), self.baseline())
        self.assertFalse(self.checkpoint.RecordReply(self.checkpoint, proposal.actionKey,
            self.h.lua.eval("{ok=true,callback=function() end}"))[0])
        recovered = self.checkpoint.Recovery(self.checkpoint, proposal.actionKey)[0]
        self.assertIsNone(recovered.reply)
        self.assertEqual(recovered.baseline.beforeCompletions, 8)

    def test_yielding_storage_commit_cannot_be_overwritten_by_another_pending_save(self):
        self.storage.Write = self.h.lua.eval("""function(self,key,value)
            coroutine.yield('write_wait') self.data[key]=value return true end""")
        self.h.lua.globals().recoveryCheckpoint = self.checkpoint
        self.h.lua.globals().recoveryProposal = self.h.proposal()
        self.h.lua.globals().recoveryBefore = self.before()
        self.h.lua.globals().recoveryBaseline = self.baseline()
        self.h.lua.execute("""pendingWriter=coroutine.create(function()
            return recoveryCheckpoint:Save(recoveryProposal,recoveryBefore,recoveryBaseline) end)
            assert(select(2,coroutine.resume(pendingWriter))=='write_wait')""")
        saved, reason = self.checkpoint.Save(self.checkpoint,
            self.h.proposal("operations", "other"), self.before(), self.baseline())
        self.assertFalse(saved)
        self.assertIn("in flight", reason)
        another = self.checkpoints.new(self.storage, None, None, self.module)
        self.assertIsNone(another.Load(another, "user-a", self.h.session["place"], "release-a")[0])
        self.assertIsNone(self.checkpoint.Load(self.checkpoint, "other", self.h.session["place"], "release-a")[0])
        self.h.lua.execute("assert(coroutine.resume(pendingWriter))")
        self.assertEqual(len(self.checkpoint.Records(self.checkpoint)), 1)

    def test_unload_fences_result_persistence_from_late_native_callback(self):
        self.h.policy.captureBefore = self.h.lua.eval("function() return {beforeCompletions=8} end")
        session = self.h.load("src/engine/Session.luau").new(self.h.broker, self.checkpoint,
            lua_table(self.h.lua, self.h.session))
        proposal = self.h.proposal()
        session.Offer(session, proposal, self.before())
        session.Tick(session, self.before())
        session.Close(session)
        self.h.transport.callbacks[1](lua_table(self.h.lua, {"ok": True}))
        self.assertIsNone(self.checkpoint.Recovery(self.checkpoint, proposal.actionKey)[0].reply)
