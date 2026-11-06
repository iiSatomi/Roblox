"""Independent review: an ordinary pending reply survives a real encoded restart."""
import json
import unittest

import test_automation_runtime as fixture
from engine_harness import lua_table


class RuntimePendingJsonRestartReviewTests(unittest.TestCase):
    def roundtrip(self, h, value):
        def wire(v):
            if not hasattr(v, "items"): return v
            entries = dict(v.items())
            if entries and set(entries) == set(range(1, len(entries) + 1)):
                return [wire(entries[i]) for i in range(1, len(entries) + 1)]
            return {k: wire(x) for k, x in entries.items()}
        return lua_table(h.lua, json.loads(json.dumps(wire(value), allow_nan=False)))

    def test_serialized_pending_callback_keeps_original_custody_in_new_session(self):
        for reply in ({"ok": True, "pending": True}, {"ok": False, "code": "pending"}):
            for attempted_verdict in ("confirmed", "rejected"):
                with self.subTest(reply=reply, attempted_verdict=attempted_verdict):
                    f = fixture.AutomationRuntimeTests(); f.setUp()
                    h = f.h
                    try:
                        spec = f.runtime.features.jobs
                        # The shared boundary must remain safe even if an
                        # ordinary feature's local callback adapter is faulty.
                        spec.evidence.evaluate = h.lua.eval("function() return '" + attempted_verdict + "' end")
                        spec.recoverSaved = h.lua.eval("function() return '" + attempted_verdict + "' end")
                        f.runtime.Resume(f.runtime)
                        f.step(settings=f.settings(True, False, False))
                        self.assertEqual(len(h.transport.sent), 1)
                        h.transport.callbacks[1](lua_table(h.lua, reply))
                        record = f.runtime.checkpoint.Records(f.runtime.checkpoint)[1]
                        action, request = record.actionKey, record.requestId
                        old = f.runtime.checkpoint.Recovery(f.runtime.checkpoint, action)[0]
                        self.assertEqual(old.reply.ok, reply["ok"])
                        h.at(46); f.step(f.raw(2), f.settings(False, False, False))
                        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 1)
                        modules = f.runtime.modules
                        f.runtime.Close(f.runtime)
                        for key, value in list(f.storage.data.items()):
                            f.storage.data[key] = self.roundtrip(h, value)
                        h.session["session"] = "independent-json-restart"
                        h.at(0)
                        h.clock = h.load("src/engine/Clock.luau").new(h.lua.eval("function() return testNow end"))
                        # Fresh constructor loads the persisted CP, not an
                        # injected recovery record or a retained old broker.
                        f.runtime = h.load("src/engine/AutomationRuntime.luau").new(lua_table(h.lua, {
                            "clock": h.clock, "transport": h.transport, "storage": f.storage,
                            "identity": h.session, "modules": modules, "features": [spec]}))
                        raw = f.raw(revision=0)
                        raw.native.serverNow = old.before.native.serverNow + 47
                        self.assertIsNotNone(f.runtime.session.broker.Fresh(f.runtime.session.broker, raw, h.clock.Now(h.clock))[0])
                        self.assertFalse(f.runtime.session.storageFault)
                        f.step(raw, f.settings(False, False, False))
                        recovered = f.runtime.checkpoint.Records(f.runtime.checkpoint)
                        self.assertEqual(len(recovered), 1)
                        self.assertEqual((recovered[1].actionKey, recovered[1].requestId), (action, request))
                        self.assertEqual(recovered[1].resources.energy, 1)
                        saved = f.runtime.checkpoint.Recovery(f.runtime.checkpoint, action)[0]
                        self.assertEqual(saved.proposal.session, old.proposal.session)
                        self.assertEqual(saved.reply.ok, reply["ok"])
                        self.assertIsNone(f.runtime.recoveries.jobs)
                        f.runtime.Resume(f.runtime)
                        f.step(raw, f.settings(True, False, False))
                        self.assertEqual(len(h.transport.sent), 1)
                    finally:
                        f.runtime.Close(f.runtime)
