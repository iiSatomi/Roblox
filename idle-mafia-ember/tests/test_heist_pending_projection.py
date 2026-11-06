"""Small exact Heist recovery snapshots preserve the original bounded serializer."""
import json
import unittest
from lupa import lua_type

import test_heist_start as start_fixture
import test_favor_help as favor_fixture
import test_sabotage as sabotage_fixture
import test_heist_collect as collect_fixture
from engine_harness import lua_table


class HeistPendingProjectionTests(unittest.TestCase):
    def plain(self, value):
        if lua_type(value) == "table":
            keys = list(value.keys())
            if keys and set(keys) == set(range(1, len(keys) + 1)):
                return [self.plain(value[index]) for index in range(1, len(keys) + 1)]
            return {key: self.plain(child) for key, child in value.items()}
        return value

    def proof(self, f, raw, counter, quote=False):
        value = {field: raw[field] for field in
            ("session", "account", "place", "release", "revision", "capturedAt")}
        value.update(controllerCounter=counter, nativeJob="job-a", nativeEpoch="epoch-a", nativeSourceKey="a" * 64)
        if quote:
            value["quote"] = {"sequence": counter + 1, "nativeJob": "job-a",
                "nativeEpoch": "epoch-a", "nativeSourceKey": "a" * 64}
        raw.heistProtocolProof = lua_table(f.h.lua, value)

    def case(self, kind, ok=True):
        if kind == "start":
            f = start_fixture.HeistStartTests()
            f.setUp()
            before = f.raw(revision=7)
            p = f.planner.propose(f.view(before)[0], f.settings(), f.reserves())[0]
            for name, value in {"sequence": 5, "nativeJob": "job-a", "nativeEpoch": "epoch-a", "nativeSourceKey": "a" * 64}.items():
                p.intent[name] = value
            self.proof(f, before, 4, quote=True)
            after = f.raw(revision=0, cash=600 if ok else 1000,
                energy=5 if ok else 10, starts=1 if ok else 2,
                mine={"id": "run-final", "heistId": "h_high", "endsAt": 2001000} if ok else None)
            after.session = "run-b"
            after.native.serverNow = after.heistBoardProof.board.serverNow = before.native.serverNow + 1
            self.proof(f, after, 5)
            reply = lua_table(f.h.lua, {"ok": ok})
        elif kind in ("favor", "sabotage"):
            f = favor_fixture.FavorHelpTests() if kind == "favor" else sabotage_fixture.SabotageTests()
            f.setUp()
            data, after = f.recovery_case(ok=ok, native=True)
            p, before, reply = data.proposal, data.before, data.reply
        else:
            f = collect_fixture.HeistCollectTests()
            f.setUp()
            before = f.before
            p = f.propose()[0]
            after = f.after(awarded=ok, removed=ok)
            after.session = after.heistProtocolProof.session = after.heistBoardProof.header.session = "run-b"
            reply = f.reply() if ok else lua_table(f.h.lua, {"ok": False, "collected": False})
        p.requestId = 11
        for raw in (before, after):
            proof = raw.heistBoardProof
            proof.sourceKey = "b" * 64
            proof.header = lua_table(f.h.lua, {field: raw[field] for field in
                ("session", "account", "place", "release", "revision", "capturedAt")})
            proof.provenance = lua_table(f.h.lua, {"seen": False, "source": "native-board"})
            proof.board.extra = lua_table(f.h.lua, {"nativeFlag": False, "sparse": {2: "two", "2": "string-two"}})
        baseline, why = f.evidence.capture(p, before)
        self.assertIsNotNone(baseline, why)
        return f, p, before, baseline, after, reply

    def inflate(self, f, before):
        # Every field is a valid primitive/table and each string is below 16 KiB.
        before.unrelatedCatalog = lua_table(f.h.lua, {"entry" + str(i): "c" * 4096 for i in range(64)})
        before.native.unrelatedHistory = lua_table(f.h.lua, {"entry" + str(i): "n" * 4096 for i in range(24)})
        before.unrelatedProof = lua_table(f.h.lua, {"source": "not-heist", "known": False})
        rows = before.heistBoardProof.board.rows
        for index in range(2, 18):
            rows[index] = lua_table(f.h.lua, {"id": "other-" + str(index), "heistId": "h_a",
                "ownerId": 800 + index, "endsAt": before.native.serverNow + 300,
                "nativePayload": "r" * 4096})
        if rows[1] is None:
            rows[1] = lua_table(f.h.lua, {"id": "other-1", "heistId": "h_a", "ownerId": 801,
                "endsAt": before.native.serverNow + 300, "nativePayload": "r" * 4096})

    def record(self, f, p):
        return lua_table(f.h.lua, {field: p[field] for field in
            ("requestId", "account", "place", "release", "feature", "actionKey", "resources")})

    def roundtrip(self, f, encoded):
        return lua_table(f.h.lua, json.loads(json.dumps(self.plain(encoded))))

    def test_sabotage_projection_retains_only_own_family_id_for_exact_recapture(self):
        f, p, before, baseline, after, reply = self.case("sabotage")
        before.native.family.unrelated = "private-family-detail" * 1000
        module = f.h.load("src/storage/PendingAction.luau")
        saved, why = module.Capture(p, before, baseline)
        self.assertIsNotNone(saved, why)
        record = self.record(f, p)
        saved = module.WithReply(saved, record, reply)[0]
        data = module.Decode(self.roundtrip(f, saved), record)
        self.assertIsNotNone(data.before.native.family)
        self.assertEqual(self.plain(data.before.native.family), {"id": "own-family"})
        self.assertEqual(data.proposal.intent.ownFamilyId, "own-family")
        self.assertEqual(data.proposal.intent.ownerFamilyId, "other-family")
        self.assertIsNotNone(f.evidence.capture(data.proposal, data.before)[0])
        self.assertEqual(f.evidence.recoverSaved(data, after), "confirmed")

    def profiled_sabotage(self):
        f, p, before, _, after, reply = self.case("sabotage")
        row = before.heistBoardProof.board.rows[1]
        row.ownerName, row.ownerLevel = "Owner", 20
        before.catalogKey = before.heistBoardProof.sourceKey
        policy = {"relationAllies": "allied-family", "relationEnemies": "other-family", "enemyMode": "Enemies only"}
        profile = {"rowId": row.id, "userId": row.ownerId, "name": row.ownerName, "level": row.ownerLevel,
            "familyId": row.famId, "observedAt": before.capturedAt, "observedServerNow": before.native.serverNow}
        before.sabotageOwnerProof = lua_table(f.h.lua, {"sourceKey": before.catalogKey,
            "header": {key: before[key] for key in ("session", "account", "place", "release", "revision", "capturedAt")},
            "ownFamilyId": before.native.family.id, "policy": policy, "rows": [profile]})
        for key, value in {"ownerProfileRequired": True, "ownerProfileName": row.ownerName, "ownerProfileLevel": row.ownerLevel,
            "ownerProfileAt": before.capturedAt, "ownerProfileServerNow": before.native.serverNow,
            "ownerPolicyAllies": policy["relationAllies"], "ownerPolicyEnemies": policy["relationEnemies"],
            "ownerPolicyMode": policy["enemyMode"], "ownerSourceKey": before.catalogKey}.items():
            p.intent[key] = value
        baseline, why = f.evidence.capture(p, before)
        self.assertIsNotNone(baseline, why)
        return f, p, before, baseline, after, reply

    def test_profiled_sabotage_keeps_only_selected_owner_proof_through_json_and_restart(self):
        f, p, before, baseline, after, reply = self.profiled_sabotage()
        before.sabotageOwnerProof.rows[2] = lua_table(f.h.lua, {"rowId": "another-row", "userId": 100,
            "unrelated": {str(i): "x" * 4096 for i in range(30)}})
        module = f.h.load("src/storage/PendingAction.luau")
        record = self.record(f, p)
        encoded, why = module.Capture(p, before, baseline)
        self.assertIsNotNone(encoded, why)
        encoded = module.WithReply(encoded, record, reply)[0]
        decoded = module.Decode(self.roundtrip(f, encoded), record)
        self.assertEqual(len(decoded.before.sabotageOwnerProof.rows), 1)
        self.assertEqual(decoded.before.sabotageOwnerProof.rows[1].userId, p.intent.ownerId)
        self.assertEqual(self.plain(f.evidence.capture(decoded.proposal, decoded.before)[0]), self.plain(baseline))
        self.assertEqual(f.evidence.recoverSaved(decoded, after), "confirmed")

    def test_saved_policy_without_exact_selected_owner_proof_remains_held(self):
        f, p, before, baseline, after, reply = self.profiled_sabotage()
        module = f.h.load("src/storage/PendingAction.luau")
        record = self.record(f, p)
        encoded = module.WithReply(module.Capture(p, before, baseline)[0], record, reply)[0]
        decoded = module.Decode(self.roundtrip(f, encoded), record)
        decoded.before.sabotageOwnerProof.rows[1].familyId = "changed-family"
        self.assertIsNone(f.evidence.capture(decoded.proposal, decoded.before)[0])
        self.assertIsNone(f.evidence.recoverSaved(decoded, after))
        before.sabotageOwnerProof = None
        self.assertIsNone(module.Capture(p, before, baseline)[0])

    def test_old_sabotage_unknown_family_records_remain_held(self):
        f, p, before, baseline, after, reply = self.case("sabotage")
        p.intent.ownFamilyId, p.intent.ownerFamilyId = None, None
        baseline.intent.ownFamilyId, baseline.intent.ownerFamilyId = None, None
        before.native.family = None
        before.heistBoardProof.board.rows[1].famId = None
        baseline.row.famId = None
        module = f.h.load("src/storage/PendingAction.luau")
        saved, why = module.Capture(p, before, baseline)
        self.assertIsNotNone(saved, why)
        record = self.record(f, p)
        saved = module.WithReply(saved, record, reply)[0]
        data = module.Decode(self.roundtrip(f, saved), record)
        self.assertIsNotNone(data)
        self.assertIsNone(f.evidence.recoverSaved(data, after))
        self.assertIsNotNone(module.Copy(saved, record)[0])

    def test_all_four_oversized_snapshots_capture_without_unrelated_data_or_mutation(self):
        for kind in ("start", "favor", "sabotage", "collect"):
            with self.subTest(kind=kind):
                f, p, before, baseline, _, _ = self.case(kind)
                self.inflate(f, before)
                original = self.plain(before)
                module = f.h.load("src/storage/PendingAction.luau")
                # This same full snapshot exceeds the unchanged generic limit.
                generic = f.h.proposal()
                generic.revision = before.revision
                self.assertIsNone(module.Capture(generic, before, baseline)[0])
                saved, why = module.Capture(p, before, baseline)
                self.assertIsNotNone(saved, why)
                data = module.Decode(saved)
                self.assertIsNone(data.before.unrelatedCatalog)
                self.assertIsNone(data.before.native.unrelatedHistory)
                self.assertIsNone(data.before.unrelatedProof)
                self.assertFalse(data.before.heistBoardProof.provenance.seen)
                self.assertEqual(data.before.heistBoardProof.board.extra.sparse[2], "two")
                self.assertEqual(data.before.heistBoardProof.board.extra.sparse["2"], "string-two")
                rows = data.before.heistBoardProof.board.rows
                self.assertEqual(len(rows), 1 if kind in ("favor", "sabotage") else 0)
                if kind in ("favor", "sabotage"):
                    self.assertEqual(rows[1].id, p.intent.rowId)
                self.assertEqual(self.plain(before), original)
                recaptured, why = f.evidence.capture(data.proposal, data.before)
                self.assertIsNotNone(recaptured, why)
                self.assertEqual(self.plain(recaptured), self.plain(baseline))

    def test_copy_withreply_and_json_keep_exact_recapture_and_saved_recovery_for_all_kinds(self):
        for kind in ("start", "favor", "sabotage", "collect"):
            for ok in (True, False):
                with self.subTest(kind=kind, ok=ok):
                    f, p, before, baseline, after, reply = self.case(kind, ok=ok)
                    self.inflate(f, before)
                    module = f.h.load("src/storage/PendingAction.luau")
                    saved, why = module.Capture(p, before, baseline)
                    self.assertIsNotNone(saved, why)
                    record = self.record(f, p)
                    copied = module.Copy(self.roundtrip(f, saved), record)[0]
                    self.assertIsNotNone(copied)
                    returned, why = module.WithReply(copied, record, reply)
                    self.assertIsNotNone(returned, why)
                    data = module.Decode(self.roundtrip(f, returned), record)
                    self.assertIsNotNone(data)
                    recaptured, why = f.evidence.capture(data.proposal, data.before)
                    self.assertIsNotNone(recaptured, why)
                    self.assertEqual(self.plain(recaptured), self.plain(baseline))
                    self.assertEqual(f.evidence.recoverSaved(data, after), "confirmed" if ok else "rejected")
                    self.assertIsNotNone(module.Copy(returned, record)[0])

    def test_exact_numeric_selected_row_does_not_capture_same_text_string_row(self):
        f = favor_fixture.FavorHelpTests()
        f.setUp()
        before = f.with_known_resources(f.raw())
        before.heistBoardProof.board.rows[1].id = 731
        p = f.planner.propose(f.view(before)[0], f.settings(), f.reserve())[0]
        baseline, why = f.evidence.capture(p, before)
        self.assertIsNotNone(baseline, why)
        before.heistBoardProof.board.rows[2] = lua_table(f.h.lua, {"id": "731", "ownerId": 43,
            "heistId": "h_a", "endsAt": 2000300, "friend": True, "helpsUsed": 0, "sabosUsed": 0})
        module = f.h.load("src/storage/PendingAction.luau")
        data = module.Decode(module.Capture(p, before, baseline)[0])
        self.assertEqual(len(data.before.heistBoardProof.board.rows), 1)
        self.assertEqual(data.before.heistBoardProof.board.rows[1].id, 731)
        self.assertNotIsInstance(data.before.heistBoardProof.board.rows[1].id, str)

    def test_missing_or_duplicate_exact_selected_row_cannot_be_fabricated(self):
        for mode in ("missing", "duplicate", "sparse"):
            f, p, before, baseline, _, _ = self.case("favor")
            rows = before.heistBoardProof.board.rows
            if mode == "missing": rows[1].id = "unselected"
            elif mode == "duplicate": rows[2] = rows[1]
            else: rows[3], rows[1] = rows[1], None
            module = f.h.load("src/storage/PendingAction.luau")
            self.assertIsNone(module.Capture(p, before, baseline)[0], mode)

    def test_required_heist_and_reward_payload_still_obeys_the_same_byte_limit(self):
        for field in ("heistCatalog", "heistProtocolProof"):
            f, p, before, baseline, _, _ = self.case("collect")
            before[field].requiredLarge = lua_table(f.h.lua, {str(i): "x" * 4096 for i in range(80)})
            module = f.h.load("src/storage/PendingAction.luau")
            self.assertIsNone(module.Capture(p, before, baseline)[0], field)
        f, p, before, baseline, _, _ = self.case("collect")
        before.heistBoardProof.board.result.nativeExtra.big = "x" * 16385
        self.assertIsNone(f.h.load("src/storage/PendingAction.luau").Capture(p, before, baseline)[0])

    def test_retained_custody_and_metatables_are_never_stripped_into_valid_data(self):
        for field in ("native", "heistBoardProof"):
            f, p, before, baseline, _, _ = self.case("favor")
            f.h.lua.eval("function(value) return setmetatable(value,{}) end")(before[field])
            self.assertIsNone(f.h.load("src/storage/PendingAction.luau").Capture(p, before, baseline)[0])
        f, p, before, baseline, _, _ = self.case("collect")
        before.native.inventory.corrupt = f.h.lua.eval("function() end")
        self.assertIsNone(f.h.load("src/storage/PendingAction.luau").Capture(p, before, baseline)[0])

    def test_original_unknown_reward_fields_remain_missing(self):
        f, p, before, baseline, _, _ = self.case("collect")
        before.heistBoardProof.board.result.gold = None
        encoded, why = f.h.load("src/storage/PendingAction.luau").Capture(p, before, baseline)
        self.assertIsNotNone(encoded, why)
        decoded = f.h.load("src/storage/PendingAction.luau").Decode(encoded)
        self.assertIsNone(decoded.before.heistBoardProof.board.result.gold)
        self.assertIsNone(f.evidence.capture(decoded.proposal, decoded.before)[0])

    def test_unrelated_features_keep_their_original_projection_behavior(self):
        f, _, before, baseline, _, _ = self.case("start")
        before.unrelatedKept = lua_table(f.h.lua, {"flag": False})
        p = f.h.proposal()
        p.revision = before.revision
        module = f.h.load("src/storage/PendingAction.luau")
        data = module.Decode(module.Capture(p, before, baseline)[0])
        self.assertFalse(data.before.unrelatedKept.flag)
        self.assertIsNotNone(data.before.heistCatalog)


if __name__ == "__main__":
    unittest.main()
