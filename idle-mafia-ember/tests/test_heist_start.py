"""Offline personal Heist selection and conservative run evidence."""
import unittest

from engine_harness import Harness, lua_table


class HeistStartTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        self.reader = self.h.load("src/game/HeistBoardState.luau")
        self.planner = self.h.load("src/features/HeistStart.luau")
        self.evidence = self.h.load("src/features/HeistStartEvidence.luau")

    def raw(self, revision=1, mine=None, cash=1000, energy=10,
            starts=2, bust=0, day=23):
        now = day * 86400 + 100
        return self.h.snapshot(revision=revision,
            native={"fullSync": True, "serverNow": now,
                "level": 20, "cash": cash,
                "pools": {"energy": energy}},
            catalogKey="heists-build-1",
            heistCatalog=[
                {"id": "h_low", "level": 10, "stake": 100,
                 "energy": 2, "crateCount": 1, "crateChance": 1, "crateRarity": 2, "duration": 600, "cash": 200, "xp": 10, "helpGoal": 3},
                {"id": "h_high", "level": 20, "stake": 400,
                 "energy": 5, "crateCount": 2, "crateChance": 1, "crateRarity": 3, "duration": 1200, "cash": 600, "xp": 20, "helpGoal": 5}],
            heistBoardProof={"account": "user-a", "capturedAt": 0,
                "query": None, "board": {"ok": True,
                    "serverNow": now, "mine": mine,
                    "rows": [], "startsLeft": starts,
                    "bustWait": bust}})

    def view(self, raw):
        context = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        return self.reader.read(raw, context)

    def settings(self, policy="Best chest"):
        return lua_table(self.h.lua, {"enabled": True,
            "policy": policy})

    def reserves(self, cash=0, energy=0):
        return lua_table(self.h.lua, {"cash": cash,
            "energy": energy, "uncertainCash": 0,
            "uncertainEnergy": 0})

    def test_selects_highest_affordable_chest_and_tier(self):
        view, reason = self.view(self.raw())
        self.assertIsNone(reason)
        proposal, reason = self.planner.propose(view, self.settings(),
            self.reserves())
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["heistId"], "h_high")
        self.assertEqual(proposal["resources"]["cash"], 400)
        self.assertTrue(proposal["intent"]["needsSequence"])
        self.assertEqual(self.planner.propose(view,
            self.settings("Highest tier"), self.reserves())[0]
            ["intent"]["heistId"], "h_high")

    def test_reservations_cap_and_busy_board_block(self):
        view, _ = self.view(self.raw())
        proposal, _ = self.planner.propose(view, self.settings(),
            self.reserves(cash=700, energy=6))
        self.assertEqual(proposal["intent"]["heistId"], "h_low")
        self.assertIsNone(self.planner.propose(view, self.settings(),
            self.reserves(cash=950))[0])
        full, _ = self.view(self.raw(starts=0))
        self.assertIsNone(self.planner.propose(full, self.settings(),
            self.reserves())[0])
        active, _ = self.view(self.raw(mine={"id": "run-1",
            "heistId": "h_low", "endsAt": 2000000}))
        self.assertIsNone(self.planner.propose(active, self.settings(),
            self.reserves())[0])

    def test_confirmation_requires_reply_run_id_and_new_board(self):
        before = self.raw()
        view, _ = self.view(before)
        proposal, _ = self.planner.propose(view, self.settings(),
            self.reserves())
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        after = self.raw(revision=2, starts=1,
            mine={"id": "run-2", "heistId": "h_high",
                  "endsAt": 2000000})
        self.assertEqual(self.evidence.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "pending")
        self.assertEqual(self.evidence.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": True, "runId": "other"}),
            baseline), "pending")
        self.assertEqual(self.evidence.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": True, "runId": "run-2"}),
            baseline), "confirmed")

    def native_start(self):
        before=self.raw();view,_=self.view(before);p,_=self.planner.propose(view,self.settings(),self.reserves())
        values={'sequence':1,'nativeJob':'job-a','nativeEpoch':'epoch-a','nativeSourceKey':'a'*64}
        for k,v in values.items():p.intent[k]=v
        proof={k:before[k] for k in ('session','account','place','release','revision','capturedAt')}
        proof.update({k:v for k,v in values.items() if k!='sequence'});proof.update({'controllerCounter':0,'quote':values})
        before.heistProtocolProof=lua_table(self.h.lua,proof)
        baseline,why=self.evidence.capture(p,before);self.assertIsNotNone(baseline,why)
        return p,before,baseline
    def native_after(self):
        after=self.raw(revision=2,starts=1,cash=600,energy=5,mine={'id':'native-run','heistId':'h_high','endsAt':2000000})
        proof={k:after[k] for k in ('session','account','place','release','revision','capturedAt')}
        proof.update({'nativeJob':'job-a','nativeEpoch':'epoch-a','nativeSourceKey':'a'*64,'controllerCounter':1})
        after.heistProtocolProof=lua_table(self.h.lua,proof);return after
    def test_owned_native_start_does_not_invent_missing_server_run_id(self):
        p,before,baseline=self.native_start();after=self.native_after()
        self.assertEqual(self.evidence.evaluate(p,before,after,lua_table(self.h.lua,{'ok':True}),baseline),'confirmed')
        for k,v in [('controllerCounter',2),('nativeEpoch','other')]:
            old=after.heistProtocolProof[k];after.heistProtocolProof[k]=v
            self.assertEqual(self.evidence.evaluate(p,before,after,lua_table(self.h.lua,{'ok':True}),baseline),'pending');after.heistProtocolProof[k]=old
        self.assertEqual(self.evidence.evaluate(p,before,after,lua_table(self.h.lua,{'ok':True,'runId':'other'}),baseline),'pending')
    def test_owned_native_start_confirms_board_transition_during_passive_cash_and_energy_regeneration(self):
        p,before,baseline=self.native_start();after=self.native_after()
        after.native.cash=before.native.cash+10000.5;after.native.pools.energy=before.native.pools.energy
        self.assertEqual(self.evidence.evaluate(p,before,after,lua_table(self.h.lua,{'ok':True,'msg':'started'}),baseline),'confirmed')
        after.heistProtocolProof.controllerCounter=2
        self.assertEqual(self.evidence.evaluate(p,before,after,lua_table(self.h.lua,{'ok':True,'msg':'started'}),baseline),'pending')

    def test_owned_native_start_recovers_across_local_revision_reset_only_in_original_controller(self):
        p,before,baseline=self.native_start();after=self.native_after();after.session='run-b';after.revision=1
        after.native.serverNow=after.native.serverNow+1;after.heistBoardProof.board.serverNow=after.native.serverNow
        after.heistProtocolProof.session='run-b';after.heistProtocolProof.revision=1
        data=lua_table(self.h.lua,{'proposal':p,'before':before,'baseline':baseline,'reply':{'ok':True}})
        self.assertEqual(self.evidence.recoverSaved(data,after),'confirmed')
        after.heistProtocolProof.nativeEpoch='other';self.assertIsNone(self.evidence.recoverSaved(data,after))

    def start_baseline(self):
        before = self.raw()
        view, _ = self.view(before)
        proposal, _ = self.planner.propose(view, self.settings(),
            self.reserves())
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        return proposal, before, baseline

    def test_rejection_requires_newer_unchanged_personal_board(self):
        proposal, before, baseline = self.start_baseline()
        reply = lua_table(self.h.lua, {"ok": False, "code": "requirements"})
        self.assertEqual(self.evidence.evaluate(proposal, before,
            self.raw(revision=2), reply, baseline), "rejected")
        for revision in (0, 1, 1.5, float("inf")):
            with self.subTest(revision=revision):
                self.assertEqual(self.evidence.evaluate(proposal, before,
                    self.raw(revision=revision), reply, baseline), "pending")

    def test_partial_or_different_run_never_proves_rejection(self):
        proposal, before, baseline = self.start_baseline()
        for changes in ({"starts": 1}, {"bust": 10},
                        {"mine": {"id": "run-2", "heistId": "h_high"}},
                        {"mine": {"id": "other", "heistId": "h_low"}},
                        {"mine": {}, "starts": 1},
                        {"cash": 600}, {"energy": 5},
                        {"cash": 1000.25}, {"energy": 11}, {"day": 24}):
            with self.subTest(changes=changes):
                self.assertEqual(self.evidence.evaluate(proposal, before,
                    self.raw(revision=2, **changes),
                    lua_table(self.h.lua, {"ok": False}), baseline), "pending")
        after = self.raw(revision=2)
        after["heistBoardProof"]["board"]["result"] = lua_table(
            self.h.lua, {"heistId": "h_high", "ok": True})
        self.assertEqual(self.evidence.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": False}), baseline), "pending")

    def test_uncertain_replies_remain_pending_even_with_exact_run(self):
        proposal, before, baseline = self.start_baseline()
        for signal in ({"pending": True}, {"code": "pending"},
                       {"code": "no_pending"}, {"code": "rate_limited"},
                       {"code": "presence"}):
            for ok in (False, True):
                for after in (self.raw(revision=2), self.raw(revision=2,
                        starts=1, mine={"id": "run-2", "heistId": "h_high"})):
                    with self.subTest(signal=signal, ok=ok):
                        self.assertEqual(self.evidence.evaluate(proposal, before,
                            after, lua_table(self.h.lua,
                                {"ok": ok, "runId": "run-2", **signal}),
                            baseline), "pending")

    def test_rejection_requires_current_scope_and_complete_resources(self):
        proposal, before, baseline = self.start_baseline()
        changes = [((), "account", "other"), ((), "session", "other"),
                   ((), "place", "other"), ((), "release", "other"),
                   ((), "catalogKey", "other"), ((), "capturedAt", -1),
                   (("native",), "cash", None),
                   (("native",), "level", 21),
                   (("native",), "pools", None),
                   (("native",), "serverNow", 0),
                   (("heistBoardProof",), "account", "other"),
                   (("heistBoardProof",), "query", "other"),
                   (("heistBoardProof", "board"), "serverNow", 23 * 86400),
                   (("heistBoardProof", "board"), "serverNow", None)]
        for path, field, value in changes:
            after = self.raw(revision=2)
            target = after
            for part in path:
                target = target[part]
            target[field] = value
            with self.subTest(path=path, field=field, value=value):
                self.assertEqual(self.evidence.evaluate(proposal, before, after,
                    lua_table(self.h.lua, {"ok": False}), baseline), "pending")

    def test_preflight_rejects_changed_board_or_price(self):
        before = self.raw()
        view, _ = self.view(before)
        proposal, _ = self.planner.propose(view, self.settings(),
            self.reserves())
        before["heistBoardProof"]["board"]["startsLeft"] = 1
        self.assertIsNone(self.evidence.capture(proposal, before)[0])
        before["heistBoardProof"]["board"]["startsLeft"] = 2
        before["heistCatalog"][2]["stake"] = 401
        self.assertIsNone(self.evidence.capture(proposal, before)[0])

    def test_fractional_cash_preserves_integer_stake_and_preflight(self):
        before = self.raw(cash=1000.25)
        view, reason = self.view(before)
        self.assertIsNone(reason)
        proposal, reason = self.planner.propose(view, self.settings(),
            self.reserves())
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["expectedStake"], 400)
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        self.assertEqual(baseline["heistId"], "h_high")

    def test_fractional_board_clock_preserves_start_preflight(self):
        before = self.raw()
        before["native"]["serverNow"] += 0.25
        before["heistBoardProof"]["board"]["serverNow"] += 0.5
        view, reason = self.view(before)
        self.assertIsNone(reason)
        proposal, reason = self.planner.propose(view, self.settings(),
            self.reserves())
        self.assertIsNone(reason)
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        self.assertEqual(baseline["serverDay"], 23)


if __name__ == "__main__":
    unittest.main()
