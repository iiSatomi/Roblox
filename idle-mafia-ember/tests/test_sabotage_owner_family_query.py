"""Owned Heist owner metadata: exact Family correlation, bounded reads, no Scout."""
import unittest
from engine_harness import Harness, lua_table


class OwnerFamilyQueryTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.module = self.h.load("src/tabs/heists/OwnerFamilyQuery.luau")
        self.source = self.h.lua.execute("return {valid=true,Current=function(s,remote) return s.valid and (remote=='HeistAction' or remote=='PlayerProfile') end}")
        self.query = self.module.new(lua_table(self.h.lua, self.h.session), "a" * 64,
            self.source, self.h.load("src/tabs/combat/TargetSelection.luau"))
        self.settings = lua_table(self.h.lua, {"enabled": True, "relationAllies": "allied-family",
            "relationEnemies": "other-family", "enemyMode": "Enemies only"})
        self.raw = self.h.snapshot(native={"fullSync": True, "serverNow": 2000000,
            "family": {"id": "own-family"}}, heistBoardProof={"account": "user-a", "capturedAt": 0,
            "sourceKey": "a" * 64, "board": {"ok": True, "serverNow": 2000000, "rows": [
                {"id": "run-1", "ownerId": 42, "ownerName": "Owner", "ownerLevel": 20,
                 "famId": "other-family", "friend": False, "endsAt": 2000300}]}})
        self.raw.heistBoardProof.header = lua_table(self.h.lua, {key: self.raw[key] for key in
            ("session", "account", "place", "release", "revision", "capturedAt")})
        self.reply = lua_table(self.h.lua, {"ok": True, "profile": {"userId": 42,
            "name": "Owner", "level": 20, "familyId": "other-family"}})
        self.assertTrue(self.query.Configure(self.query, self.settings))
        self.assertTrue(self.query.ObserveBoard(self.query, self.raw))

    def admit(self):
        request, why = self.query.Prepare(self.query, self.raw)
        self.assertIsNotNone(request, why)
        staged, why = self.query.Accept(self.query, self.raw, request, self.reply)
        self.assertIsNotNone(staged, why)
        self.assertTrue(self.query.Commit(self.query, staged))
        return self.query.Read(self.query, self.raw)

    def test_minimal_family_metadata_is_sufficient_without_combat_stats_or_scout_quote(self):
        proof = self.admit()
        self.assertEqual(proof.rows[1].familyId, "other-family")
        self.assertEqual(proof.rows[1].userId, 42)
        self.assertFalse(self.query.NeedsRead(self.query, self.raw))
        self.assertIsNone(proof.rows[1].scoutCost)

    def test_hidden_combat_profile_still_only_supplies_explicit_family_metadata(self):
        self.reply.profile.statsHidden = True
        self.assertEqual(self.admit().rows[1].familyId, "other-family")

    def test_each_mismatched_owner_field_and_missing_family_is_refused(self):
        for field, value in (("userId", 43), ("name", "Other"), ("level", 21),
                             ("familyId", "changed-family"), ("familyId", None)):
            with self.subTest(field=field, value=value):
                old = self.reply.profile[field]
                self.reply.profile[field] = value
                request = self.query.Prepare(self.query, self.raw)[0]
                self.assertIsNone(self.query.Accept(self.query, self.raw, request, self.reply)[0])
                self.assertEqual(len(self.query.Read(self.query, self.raw).rows), 0)
                self.reply.profile[field] = old

    def test_unknown_or_own_family_and_unknown_friendship_do_not_request_profiles(self):
        for field, value in (("famId", None), ("famId", ""), ("famId", "0"),
                             ("famId", "own-family"), ("friend", None), ("friend", True)):
            with self.subTest(field=field, value=value):
                row = self.raw.heistBoardProof.board.rows[1]
                old = row[field]
                row[field] = value
                self.query.ObserveBoard(self.query, self.raw)
                self.assertFalse(self.query.NeedsRead(self.query, self.raw))
                row[field] = old
                self.query.ObserveBoard(self.query, self.raw)

    def test_policy_change_disable_close_and_source_replacement_revoke_proofs(self):
        for mode in ("policy", "disabled", "close", "source"):
            with self.subTest(mode=mode):
                self.setUp()
                self.admit()
                if mode == "policy":
                    self.settings.relationAllies = "other-family"
                    self.query.Configure(self.query, self.settings)
                elif mode == "disabled":
                    self.settings.enabled = False
                    self.query.Configure(self.query, self.settings)
                elif mode == "close": self.query.Close(self.query)
                else: self.source.Current = self.h.lua.eval("function() return true end")
                self.assertIsNone(self.query.Read(self.query, self.raw))

    def test_all_off_or_policy_off_never_prepares_profile(self):
        self.settings.enemyMode, self.settings.relationAllies = "Off", ""
        self.assertFalse(self.query.Configure(self.query, self.settings))
        self.assertFalse(self.query.NeedsRead(self.query, self.raw))
        self.assertIsNone(self.query.Prepare(self.query, self.raw)[0])

    def test_uncommitted_or_changed_board_and_header_cannot_mint_proof(self):
        self.admit()
        self.raw.heistBoardProof.board.rows[1].famId = "changed-family"
        self.assertIsNone(self.query.Read(self.query, self.raw))
        self.raw.heistBoardProof.board.rows[1].famId = "other-family"
        self.raw.revision = 2
        self.assertIsNone(self.query.Read(self.query, self.raw))

    def test_new_committed_header_reuses_only_same_owner_within_thirty_seconds(self):
        self.admit()
        for elapsed, expected in ((1, 1), (31, 0)):
            self.raw.revision += 1
            self.raw.capturedAt = elapsed
            self.raw.native.serverNow = 2000000 + elapsed
            proof = self.raw.heistBoardProof
            proof.capturedAt, proof.board.serverNow = elapsed, 2000000 + elapsed
            proof.header.revision, proof.header.capturedAt = self.raw.revision, elapsed
            self.assertTrue(self.query.ObserveBoard(self.query, self.raw))
            self.assertEqual(len(self.query.Read(self.query, self.raw).rows), expected)

    def test_changed_policy_starts_its_enemy_priority_without_old_read_cursor(self):
        self.admit()
        self.raw.heistBoardProof.board.rows[2] = lua_table(self.h.lua, {"id": "neutral", "ownerId": 43,
            "ownerName": "Neutral", "ownerLevel": 20, "famId": "neutral-family", "friend": False,
            "endsAt": 2000300})
        self.settings.enemyMode = "Prefer enemies"
        self.query.Configure(self.query, self.settings)
        self.query.ObserveBoard(self.query, self.raw)
        self.assertEqual(self.query.Prepare(self.query, self.raw)[0].args[1], 42)

    def test_replaced_request_changed_board_and_foreign_staged_commit_are_rejected(self):
        first = self.query.Prepare(self.query, self.raw)[0]
        second = self.query.Prepare(self.query, self.raw)[0]
        self.assertIsNone(self.query.Accept(self.query, self.raw, first, self.reply)[0])
        staged = self.query.Accept(self.query, self.raw, second, self.reply)[0]
        self.assertIsNotNone(staged)
        self.assertFalse(self.query.Commit(self.query, self.raw))
        self.assertEqual(len(self.query.Read(self.query, self.raw).rows), 0)


if __name__ == "__main__":
    unittest.main()
