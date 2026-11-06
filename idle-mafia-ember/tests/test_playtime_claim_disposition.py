"""Variable awards certify the owned claim, never an invented payout formula."""
import json
import unittest
from contextlib import contextmanager

import test_group_income_effect as fixture
from engine_harness import lua_table


class PlaytimeDispositionTests(unittest.TestCase):
    @contextmanager
    def fixture(self, slot, reply=None):
        f = fixture.GroupIncomeEffectTests(); f.setUp()
        self.f, self.h, self.tab, self.slot = f, f.h, f.tab, slot
        self.spec = next(r for r in self.tab.Descriptors(self.tab).values() if r.id == "playtime")
        self.executor = self.h.lua.execute("""return {calls={},
            Schedule=function(self,fn)fn();return true end,
            Invoke=function(self,remote,method,...)self.calls[#self.calls+1]={remote=remote,args=table.pack(...)};return self.reply or {ok=true}end}""")
        self.executor.reply = lua_table(self.h.lua, reply) if reply else None
        self.start()
        try:
            yield
        finally:
            self.app.Destroy(self.app)

    def start(self):
        h = self.h
        adapter = h.load("src/transport/NativeDispatchAdapter.luau").new(h.load("src/transport/NativeCallPlan.luau"), self.executor)
        self.runtime = h.load("src/engine/AutomationRuntime.luau").new(lua_table(h.lua, {
            "clock": h.clock, "transport": adapter, "storage": self.f.base.storage,
            "identity": h.session, "modules": self.f.base.runtime.modules,
            "features": [self.spec]}))
        self.app = h.load("src/App.luau").start(lua_table(h.lua, {
            "Ember": h.load("tests/ember_double.lua")(), "Catalog": h.load("src/ui/Catalog.luau"),
            "Settings": h.load("src/storage/Settings.luau"), "EmberAdapter": h.load("src/ui/EmberAdapter.luau"),
            "automationRuntimeInstance": self.runtime}))

    def raw(self, revision=1, claimed=False, delta=0):
        raw = self.f.raw(revision)
        raw.native.serverNow += delta
        raw.native.level, raw.native.maxLevel, raw.native.cash = 30, 30, 1000.25
        raw.native.xpBoostEnd = self.f.raw().native.serverNow + 600
        raw.native.playtime.todaySeconds = 20000
        raw.native.playtime.laddersClaimed = lua_table(self.h.lua, {
            str(i): 3 for i in range(1, 8) if i != self.slot or claimed})
        return raw

    def begin(self):
        self.app.Set(self.app, "playtime.enabled", True); self.app.Resume(self.app)
        self.app.Step(self.app, self.raw())
        self.assertEqual(len(self.executor.calls), 1, self.runtime.Status(self.runtime).reasons.playtime)
        call = self.executor.calls[1]
        self.assertEqual((call.remote, call.args.n, call.args[1]), ("ClaimLadder", 1, self.slot))
        record = self.runtime.checkpoint.Records(self.runtime.checkpoint)[1]
        data = self.runtime.checkpoint.Recovery(self.runtime.checkpoint, record.actionKey)[0]
        self.assertEqual(dict(data.proposal.resources.items()), {})
        return data

    def observe(self, raw, at=1):
        self.h.at(at); self.app.Step(self.app, raw)

    def restart(self):
        self.app.Destroy(self.app)
        def wire(value):
            if not hasattr(value, "items"): return value
            entries = dict(value.items())
            if entries and set(entries) == set(range(1, len(entries) + 1)):
                return [wire(entries[i]) for i in range(1, len(entries) + 1)]
            return {k: wire(v) for k, v in entries.items()}
        for key, value in list(self.f.base.storage.data.items()):
            self.f.base.storage.data[key] = lua_table(self.h.lua, json.loads(json.dumps(wire(value))))
        self.h.session["session"] = "reloaded-disposition"; self.h.at(0); self.start()

    def test_owned_income_and_active_boost_claims_confirm_without_inventing_award(self):
        for slot in (1, 5):
            with self.subTest(slot=slot), self.fixture(slot):
                data = self.begin()
                self.assertEqual(data.baseline.disposition.verification, "claim_recorded_award_unverified")
                self.assertIsNone(data.baseline.spec.amount)
                after = self.raw(2, True, 2)
                # An arbitrary nondecreasing wallet / unchanged active end does
                # not establish Cash amount or the server's extension policy.
                if slot == 1: after.native.cash += 123.75
                self.app.Set(self.app, "playtime.enabled", False)
                self.observe(after)
                self.assertEqual(self.runtime.Status(self.runtime).outcomes.playtime, "confirmed")
                self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 0)
                self.assertEqual(len(self.executor.calls), 1)

    def test_normal_json_restart_recovers_original_disposition_without_replay(self):
        for slot in (1, 5):
            with self.subTest(slot=slot), self.fixture(slot):
                self.begin(); self.restart()
                self.observe(self.raw(0, True, 3))
                self.assertEqual(self.runtime.Status(self.runtime).recoveries.playtime, "confirmed")
                self.assertEqual(len(self.executor.calls), 1)
                self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 0)

    def test_marker_scope_source_clock_other_claims_and_wallet_contradictions_hold(self):
        for slot in (1, 5):
            with self.fixture(slot):
                data = self.begin()
                for case in ("missing", "tier", "day", "clock", "revision", "scope", "catalog", "weekend", "other", "cash" if slot == 1 else "xp"):
                    with self.subTest(slot=slot, case=case):
                        after = self.raw(2, True, 2)
                        if case == "missing": after.native.playtime.laddersClaimed[str(slot)] = None
                        elif case == "tier": after.native.playtime.laddersClaimed[str(slot)] = 2
                        elif case == "day": after.native.serverNow += 86400
                        elif case == "clock": after.native.serverNow = data.before.native.serverNow
                        elif case == "revision": after.revision = data.before.revision
                        elif case == "scope": after.account = "other"
                        elif case == "catalog": after.catalogKey = "b" * 64
                        elif case == "weekend":
                            original = self.f.base.rewards_source.IsWeekend
                            self.f.base.rewards_source.IsWeekend = self.h.lua.eval("function() return true end")
                        elif case == "other": after.native.playtime.laddersClaimed["7"] = None
                        elif case == "cash": after.native.cash -= 1
                        else: after.native.xpBoostEnd -= 1
                        self.assertIsNone(self.spec.recoverSaved(data, after))
                        if case == "weekend": self.f.base.rewards_source.IsWeekend = original

    def test_transient_and_contradictory_negative_keep_exact_action_through_timeout_reload(self):
        for slot in (1, 5):
            for code in ("pending", "busy", "rate_limited", "presence", "pending_flag", "negative"):
                reply = {"ok": code != "negative"}
                if code == "pending_flag": reply["pending"] = True
                elif code != "negative": reply["code"] = code
                with self.subTest(slot=slot, code=code), self.fixture(slot, reply):
                    data = self.begin()
                    self.observe(self.raw(2, True, 2))
                    self.observe(self.raw(3, True, 46), 46)
                    record = self.runtime.checkpoint.Records(self.runtime.checkpoint)[1]
                    self.assertEqual(record.actionKey, data.proposal.actionKey)
                    self.restart(); self.observe(self.raw(0, True, 47), 47)
                    self.app.Set(self.app, "playtime.enabled", True); self.app.Resume(self.app)
                    self.observe(self.raw(1, True, 48), 48)
                    self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 1)
                    self.assertEqual(len(self.executor.calls), 1)

    def test_terminal_negative_needs_strict_new_clock_and_unchanged_award_state(self):
        for slot in (1, 5):
            with self.subTest(slot=slot), self.fixture(slot, {"ok": False}):
                data = self.begin()
                changed = self.raw(2, False, 2)
                if slot == 1: changed.native.cash += 1
                else: changed.native.xpBoostEnd += 1
                self.assertIsNone(self.spec.recoverSaved(data, changed))
                self.restart()
                stale = self.raw(0)
                self.observe(stale)
                self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 1)
                self.observe(self.raw(1, False, 3), 2)
                self.assertEqual(self.runtime.Status(self.runtime).recoveries.playtime, "rejected")
                self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 0)
                self.assertEqual(len(self.executor.calls), 1)

    def test_new_path_requires_exact_zero_cost_action_and_immutable_original_proof(self):
        for slot in (1, 5):
            with self.subTest(slot=slot), self.fixture(slot):
                data = self.begin()
                data.proposal.resources.cash = 1
                self.assertIsNone(self.spec.evidence.capture(data.proposal, data.before)[0])
                data.proposal.resources.cash = None
                action = data.proposal.actionKey
                data.proposal.actionKey = "another-action"
                self.assertIsNone(self.spec.evidence.capture(data.proposal, data.before)[0])
                data.proposal.actionKey = action
                data.baseline.disposition.claimed["7"] = None
                self.assertIsNone(self.spec.recoverSaved(data, self.raw(2, True, 2)))

    def test_fixed_cash_and_expired_xp_saved_baseline_shape_stays_exact(self):
        for slot in (1, 5):
            with self.subTest(slot=slot), self.fixture(slot):
                before = self.raw()
                before.native.level, before.native.maxLevel = 1, 1
                before.native.xpBoostEnd = 0
                before.serverNow = before.native.serverNow
                view = self.spec.reader.read(before, before)[0]
                proposal = self.spec.planner.propose(view, lua_table(self.h.lua, {"enabled": True}))[0]
                baseline, why = self.spec.evidence.capture(proposal, before)
                self.assertIsNotNone(baseline, why)
                self.assertEqual(set(baseline.keys()), {"marker", "spec", "value"})
                after = self.raw(2, True, 2)
                after.native.level, after.native.maxLevel = 1, 1
                after.native.playtime.laddersClaimed[str(slot)] = 1
                if slot == 1: after.native.cash = before.native.cash + 10000
                else: after.native.xpBoostEnd = after.native.serverNow + 1800
                data = lua_table(self.h.lua, {"proposal": proposal, "before": before,
                    "baseline": baseline, "reply": {"ok": True}})
                self.assertEqual(self.spec.recoverSaved(data, after), "confirmed")
