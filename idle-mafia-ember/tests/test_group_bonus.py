"""Group reward requires separate existing-membership evidence."""
import unittest

from engine_harness import Harness, lua_table


class GroupBonusTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        self.reader = self.h.load("src/game/GroupBonusState.luau")
        self.planner = self.h.load("src/features/GroupBonus.luau")
        self.evidence = self.h.load("src/features/GroupBonusEvidence.luau")

    def raw(self, revision=1, claimed=False, member=True, checked_at=0, **extra):
        data = {
            "native": {"fullSync": True, "groupBonus": claimed},
            "groupConfig": {"id": 674050067},
            "groupMembership": {**self.h.session,
                                "groupId": 674050067,
                                "isMember": member,
                                "checkedAt": checked_at},
        }
        data.update(extra)
        return self.h.snapshot(revision=revision, **data)

    def view(self, raw):
        context, reason = self.context.Read(
            self.context, raw, lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        return self.reader.read(raw, context)

    def test_existing_member_gets_no_argument_claim(self):
        view, reason = self.view(self.raw())
        self.assertIsNone(reason)
        proposal, reason = self.planner.propose(
            view, lua_table(self.h.lua, {"enabled": True}))
        self.assertIsNone(reason)
        self.assertEqual(proposal["feature"], "groupBonus")
        self.assertEqual(proposal["intent"]["kind"], "groupBonusClaim")
        self.assertEqual(proposal["intent"]["groupId"], 674050067)
        self.assertEqual(len(list(proposal["resources"].items())), 0)

    def test_missing_membership_and_claimed_block(self):
        self.assertIsNone(self.view(self.raw(member=False))[0])
        self.assertIsNone(self.view(self.raw(claimed=True))[0])
        self.assertIsNone(self.view(self.raw(checked_at=-31))[0])
        self.assertIsNone(self.view(self.raw(groupMembership=None))[0])
        self.assertIsNone(self.view(self.raw(groupConfig={"id": 2}))[0])
        self.assertIsNone(self.view(self.raw(native={"fullSync": False}))[0])
        view, _ = self.view(self.raw())
        self.assertIsNone(self.planner.propose(
            view, lua_table(self.h.lua, {"enabled": False}))[0])

    def test_exact_replicated_claim_confirms(self):
        before = self.raw()
        view, _ = self.view(before)
        proposal, _ = self.planner.propose(
            view, lua_table(self.h.lua, {"enabled": True}))
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        header, _ = self.h.contracts.validateSnapshot(
            before, lua_table(self.h.lua, self.h.session))
        ok = lua_table(self.h.lua, {"ok": True})
        self.assertEqual(self.evidence.evaluate(
            proposal, header, self.raw(2), ok, baseline), "pending")
        self.assertEqual(self.evidence.evaluate(
            proposal, header, self.raw(2, claimed=True), ok, baseline),
            "confirmed")
        self.assertEqual(self.evidence.evaluate(
            proposal, header, self.raw(1, claimed=True), ok, baseline),
            "pending")

    def test_rejection_and_mismatch(self):
        before = self.raw()
        view, _ = self.view(before)
        proposal, _ = self.planner.propose(
            view, lua_table(self.h.lua, {"enabled": True}))
        baseline, _ = self.evidence.capture(proposal, before)
        header, _ = self.h.contracts.validateSnapshot(
            before, lua_table(self.h.lua, self.h.session))
        no = lua_table(self.h.lua, {"ok": False})
        self.assertEqual(self.evidence.evaluate(
            proposal, header, self.raw(2), no, baseline), "rejected")
        self.assertEqual(self.evidence.evaluate(
            proposal, header, self.raw(2, claimed=True, account="other"),
            no, baseline), "pending")


if __name__ == "__main__":
    unittest.main()
