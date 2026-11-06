"""Ordinary Favor help under native board and durable-attempt proof."""
import unittest

from engine_harness import Harness, lua_table


class FavorHelpTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.board_reader = self.h.load("src/game/HeistBoardState.luau")
        self.context = self.h.load("src/game/Context.luau").new(
            self.h.contracts, None, None, self.board_reader)
        self.reader = self.h.load("src/game/FavorsState.luau")
        self.planner = self.h.load("src/features/FavorHelp.luau")
        self.evidence = self.h.load("src/features/FavorHelpEvidence.luau")

    def raw(self, revision=1, favors=12, helps=0, attempts=0,
            friend=True, relation=None, expires=2000300):
        board = {"ok": True, "serverNow": 2000000,
                 "rows": [{"id": "run-1", "ownerId": 42,
                           "heistId": "h_a", "endsAt": expires,
                           "friend": friend, "famRel": relation,
                           "helpsUsed": helps, "sabosUsed": 0}],
                 "startsLeft": 1, "bustWait": 0,
                 "favorsLeft": favors, "helpFavorCost": 1,
                 "helpEnergyCost": 2, "helpMaxPerHeist": 5,
                 "helpCashCap": 500}
        return self.h.snapshot(revision=revision,
            native={"fullSync": True, "serverNow": 2000000,
                    "level": 20, "pools": {"energy": 20}},
            heistCatalog=[{"id": "h_a", "level": 10,
                           "stake": 100, "energy": 2,
                           "helpCash": 1000, "helpXp": 50}],
            heistBoardProof={"account": "user-a", "capturedAt": 0,
                             "board": board},
            favorUsageProof={"account": "user-a", "day": 23,
                             "attempts": attempts, "capturedAt": 0})

    def view(self, raw):
        context = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        return self.reader.read(raw, context)

    def settings(self, policy="Best reward"):
        return lua_table(self.h.lua, {"enabled": True,
            "policy": policy, "maxDailyAttempts": 5,
            "minFavorReserve": 5, "minEnergyReserve": 10,
            "relations": "Friends or Family"})

    def reserve(self):
        return lua_table(self.h.lua, {"energy": 0,
            "uncertainEnergy": 0, "favors": 0,
            "uncertainFavors": 0})

    def test_selects_friend_and_caps_native_cash_reward(self):
        view, reason = self.view(self.raw())
        self.assertIsNone(reason)
        proposal, reason = self.planner.propose(view, self.settings(),
            self.reserve())
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["rowId"], "run-1")
        self.assertEqual(proposal["intent"]["rewardCash"], 500)
        self.assertEqual(proposal["resources"]["favors"], 1)

    def test_rejects_unconfigured_custom_policy(self):
        view, _ = self.view(self.raw())
        proposal, reason = self.planner.propose(view, self.settings("Custom"),
            self.reserve())
        self.assertIsNone(proposal)
        self.assertIn("policy", reason)

    def test_ordinary_policy_requires_explicit_limits(self):
        view, _ = self.view(self.raw())
        for field in ("maxDailyAttempts", "minFavorReserve",
                      "minEnergyReserve", "relations"):
            with self.subTest(field=field):
                settings = self.settings()
                settings[field] = None
                proposal, reason = self.planner.propose(
                    view, settings, self.reserve())
                self.assertIsNone(proposal)
                self.assertIn("limits", reason)

    def test_numeric_native_row_id_is_preserved_in_argument(self):
        raw = self.raw()
        raw["heistBoardProof"]["board"]["rows"][1]["id"] = 731
        view, reason = self.view(raw)
        self.assertIsNone(reason)
        proposal, reason = self.planner.propose(view, self.settings(),
            self.reserve())
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["rowId"], 731)
        self.assertIn("number:731", proposal["actionKey"])
        self.assertIsNotNone(self.evidence.capture(proposal, raw)[0])

    def test_relationship_daily_and_reserves_block(self):
        outsider, _ = self.view(self.raw(friend=False))
        self.assertIsNone(self.planner.propose(outsider,
            self.settings(), self.reserve())[0])
        family, _ = self.view(self.raw(friend=False, relation="family"))
        self.assertIsNotNone(self.planner.propose(family,
            self.settings(), self.reserve())[0])
        capped, _ = self.view(self.raw(attempts=5))
        self.assertIsNone(self.planner.propose(capped,
            self.settings(), self.reserve())[0])
        low, _ = self.view(self.raw(favors=5))
        self.assertIsNone(self.planner.propose(low,
            self.settings(), self.reserve())[0])

    def test_omitted_friend_flag_is_not_friend(self):
        raw = self.raw()
        raw["heistBoardProof"]["board"]["rows"][1]["friend"] = None
        view, reason = self.view(raw)
        self.assertIsNone(reason)
        self.assertIsNone(self.planner.propose(view,
            self.settings(), self.reserve())[0])

    def test_missing_or_wrong_day_usage_proof_blocks(self):
        raw = self.raw()
        raw["favorUsageProof"]["day"] = 22
        self.assertIsNone(self.view(raw)[0])
        raw = self.raw()
        raw["favorUsageProof"] = None
        self.assertIsNone(self.view(raw)[0])

    def test_exact_row_and_favor_change_confirm_help(self):
        before = self.raw()
        view, _ = self.view(before)
        proposal, _ = self.planner.propose(view, self.settings(),
            self.reserve())
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        after = self.raw(revision=2, favors=11, helps=1,
                         attempts=1)
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, lua_table(self.h.lua, {"ok": True}), baseline),
            "confirmed")
        after["heistBoardProof"]["board"]["rows"][1]["helpsUsed"] = 0
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, lua_table(self.h.lua, {"ok": True}), baseline),
            "pending")

    def test_saved_exact_help_recovers_across_session_without_replaying(self):
        before = self.raw()
        proposal = self.planner.propose(self.view(before)[0], self.settings(), self.reserve())[0]
        baseline = self.evidence.capture(proposal, before)[0]
        data = lua_table(self.h.lua, {"proposal": proposal, "before": before,
            "baseline": baseline, "reply": {"ok": True}})
        after = self.raw(revision=0, favors=11, helps=1, attempts=1)
        after.session = "run-b"
        self.assertEqual(self.evidence.evaluate(proposal, before, after, data.reply, baseline), "pending")
        self.assertEqual(self.evidence.recoverSaved(data, after), "confirmed")
        after.capturedAt = -1
        after.heistBoardProof.capturedAt = -1
        after.favorUsageProof.capturedAt = -1
        self.assertIsNone(self.evidence.recoverSaved(data, after))
        after.capturedAt = 0
        after.heistBoardProof.capturedAt = 0
        after.favorUsageProof.capturedAt = 0
        after.native.serverNow = 1999999
        self.assertIsNone(self.evidence.recoverSaved(data, after))

    def test_real_native_catalog_preserves_help_reward_planning_contract(self):
        raw = self.raw()
        source = self.h.lua.table(HEISTS=raw.heistCatalog)
        for row in source.HEISTS.values():
            row.stake, row.energy, row.crateCount = 10, 2, 1
        catalog = self.h.load("src/tabs/heists/NativeHeistCatalog.luau").new(
            source, "a" * 64, "release-a")
        enriched, reason = catalog.Enrich(catalog, raw)
        self.assertIsNone(reason)
        view, reason = self.view(enriched)
        self.assertIsNone(reason)
        proposal, reason = self.planner.propose(view, self.settings(), self.reserve())
        self.assertIsNone(reason)
        self.assertEqual(proposal.intent.rewardCash,
            min(raw.heistCatalog[1].helpCash, raw.heistBoardProof.board.helpCashCap))

    def test_preflight_rechecks_day_cap_and_reserves(self):
        before = self.raw()
        view, _ = self.view(before)
        proposal, _ = self.planner.propose(view, self.settings(),
            self.reserve())
        before["favorUsageProof"]["attempts"] = 5
        self.assertIsNone(self.evidence.capture(proposal, before)[0])
        before["favorUsageProof"]["attempts"] = 0
        before["native"]["pools"]["energy"] = 11
        self.assertIsNone(self.evidence.capture(proposal, before)[0])

    def test_changed_owner_does_not_confirm(self):
        before = self.raw()
        view, _ = self.view(before)
        proposal, _ = self.planner.propose(view, self.settings(),
            self.reserve())
        baseline, _ = self.evidence.capture(proposal, before)
        self.assertIsNotNone(baseline)
        after = self.raw(revision=2, favors=11, helps=1,
                         attempts=1)
        after["heistBoardProof"]["board"]["rows"][1]["ownerId"] = 99
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, lua_table(self.h.lua, {"ok": True}), baseline),
            "pending")


if __name__ == "__main__":
    unittest.main()
