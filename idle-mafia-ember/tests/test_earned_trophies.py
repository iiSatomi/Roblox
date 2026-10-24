"""Only proven non-consuming Gold-mastery trophies enter the claim planner."""
import unittest

from engine_harness import Harness, lua_table


CATALOG = [
    {"id": "t_eldersignet", "kind": "trophy"},
    {"id": "t_grudgeledger", "kind": "trophy"},
    {"id": "t_vesperacase", "kind": "trophy", "tradeIn": True},
]


class EarnedTrophyTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        self.reader = self.h.load("src/game/EarnedTrophiesState.luau")
        self.planner = self.h.load("src/features/EarnedTrophies.luau")
        self.evidence = self.h.load("src/features/EarnedTrophiesEvidence.luau")

    def raw(self, revision=1, ready=None, inventory=None, bound=None,
            catalog=None, **changes):
        data = {"native": {"fullSync": True,
                           "derived": {"trophyReady": ready if ready is not None
                                       else ["t_eldersignet", "t_grudgeledger"]},
                           "inventory": inventory if inventory is not None else {},
                           "inventoryBound": bound if bound is not None else {}},
                "catalogKey": "items-build-1",
                "trophyCatalog": catalog if catalog is not None else CATALOG}
        data.update(changes)
        return self.h.snapshot(revision=revision, **data)

    def view(self, raw):
        context, reason = self.context.Read(
            self.context, raw, lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        return self.reader.read(raw, context)

    def propose(self, raw=None, enabled=True):
        view, reason = self.view(raw or self.raw())
        self.assertIsNone(reason)
        return self.planner.propose(
            view, lua_table(self.h.lua, {"enabled": enabled}))

    def test_only_earned_allowlisted_trophy_proposed(self):
        proposal, reason = self.propose()
        self.assertIsNone(reason)
        self.assertEqual(proposal["feature"], "trophies")
        self.assertEqual(proposal["intent"]["targetId"], "t_eldersignet")
        self.assertEqual(proposal["intent"]["kind"], "earnedTrophyClaim")
        self.assertEqual(len(list(proposal["resources"].items())), 0)
        self.assertIsNone(self.propose(enabled=False)[0])

    def test_owned_or_consuming_routes_never_proposed(self):
        proposal, _ = self.propose(self.raw(inventory={"t_eldersignet": 1}))
        self.assertEqual(proposal["intent"]["targetId"], "t_grudgeledger")
        view, reason = self.view(self.raw(ready=["t_vesperacase"]))
        self.assertIsNone(reason)
        self.assertIsNone(self.planner.propose(
            view, lua_table(self.h.lua, {"enabled": True}))[0])
        view, reason = self.view(self.raw(ready=["t_grudgeledger"],
                                          bound={"t_grudgeledger": 1}))
        self.assertIsNone(reason)
        self.assertIsNone(self.planner.propose(
            view, lua_table(self.h.lua, {"enabled": True}))[0])

    def test_other_ready_non_consuming_trophy_and_cosmetic(self):
        catalog = CATALOG + [
            {"id": "t_streetname", "kind": "trophy"},
            {"id": "bg_reward", "kind": "background"}]
        for target in ("t_streetname", "bg_reward"):
            proposal, reason = self.propose(
                self.raw(ready=[target], catalog=catalog))
            self.assertIsNone(reason)
            self.assertEqual(proposal["intent"]["targetId"], target)

    def test_incomplete_and_malformed_state_blocks(self):
        self.assertIsNone(self.view(self.raw(native={"fullSync": False}))[0])
        self.assertIsNone(self.view(self.raw(catalog=[]))[0])
        self.assertIsNone(self.view(self.raw(ready=["t_eldersignet",
                                                  "t_eldersignet"]))[0])
        self.assertIsNone(self.view(self.raw(inventory={"t_grudgeledger": -1}))[0])
        self.assertIsNone(self.view(self.raw(catalog=[
            {"id": "t_eldersignet", "kind": "crate"},
            {"id": "t_grudgeledger", "kind": "trophy"}]))[0])

    def test_reply_plus_matching_ownership_and_marker_confirm(self):
        before = self.raw()
        proposal, _ = self.propose(before)
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        header, _ = self.h.contracts.validateSnapshot(
            before, lua_table(self.h.lua, self.h.session))
        ok = lua_table(self.h.lua, {"ok": True})
        self.assertEqual(self.evidence.evaluate(
            proposal, header, self.raw(2), ok, baseline), "pending")
        after = self.raw(2, ready=["t_grudgeledger"],
                         bound={"t_eldersignet": 1})
        self.assertEqual(self.evidence.evaluate(
            proposal, header, after, ok, baseline), "confirmed")
        still_ready = self.raw(2, bound={"t_eldersignet": 1})
        self.assertEqual(self.evidence.evaluate(
            proposal, header, still_ready, ok, baseline), "pending")
        other = self.raw(2, ready=["t_eldersignet"],
                         bound={"t_grudgeledger": 1})
        self.assertEqual(self.evidence.evaluate(
            proposal, header, other, ok, baseline), "pending")

    def test_rejection_and_cross_account_are_not_success(self):
        before = self.raw()
        proposal, _ = self.propose(before)
        baseline, _ = self.evidence.capture(proposal, before)
        header, _ = self.h.contracts.validateSnapshot(
            before, lua_table(self.h.lua, self.h.session))
        no = lua_table(self.h.lua, {"ok": False})
        self.assertEqual(self.evidence.evaluate(
            proposal, header, self.raw(2), no, baseline), "rejected")
        after = self.raw(2, ready=["t_grudgeledger"],
                         bound={"t_eldersignet": 1}, account="other")
        self.assertEqual(self.evidence.evaluate(
            proposal, header, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "pending")

    def test_optional_bound_inventory_absence_still_allows_loose_proof(self):
        before = self.raw()
        before["native"]["inventoryBound"] = None
        proposal, _ = self.propose(before)
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        header, _ = self.h.contracts.validateSnapshot(
            before, lua_table(self.h.lua, self.h.session))
        after = self.raw(2, ready=[], inventory={"t_eldersignet": 1})
        after["native"]["inventoryBound"] = None
        self.assertEqual(self.evidence.evaluate(
            proposal, header, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "confirmed")


if __name__ == "__main__":
    unittest.main()
