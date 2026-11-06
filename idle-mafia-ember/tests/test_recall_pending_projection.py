"""Recall keeps exact original custody without unrelated native/catalog bulk."""
import json
import unittest
from lupa import lua_type
from engine_harness import lua_table
import test_recall_runtime_app as fixture


class RecallPendingProjectionTests(unittest.TestCase):
    def setUp(self):
        self.p = fixture.RecallRuntimeAppTests()
        self.p.setUp()
        self.module = self.p.h.load("src/storage/PendingAction.luau")

    def tearDown(self):
        self.p.tearDown()

    def plain(self, value):
        if lua_type(value) == "table":
            keys = list(value.keys())
            if keys and set(keys) == set(range(1, len(keys) + 1)):
                return [self.plain(value[index]) for index in range(1, len(keys) + 1)]
            return {key: self.plain(child) for key, child in value.items()}
        return value

    def roundtrip(self, encoded):
        return lua_table(self.p.h.lua, json.loads(json.dumps(self.plain(encoded))))

    def inflate(self, raw):
        raw.unrelatedCatalog = lua_table(self.p.h.lua, {str(i): "c" * 4096 for i in range(64)})
        raw.native.heistLedger = lua_table(self.p.h.lua, {str(i): {"name": "Player" + str(i),
            "famId": "family" + str(i), "helped": i, "gotHelped": 0, "lastAt": 900,
            "unrelatedDisplay": "h" * 400} for i in range(200)})
        raw.native.family.unrelatedHistory = lua_table(self.p.h.lua, {str(i): "f" * 4096 for i in range(8)})
        for row in raw.native.crew.values():
            row.unrelatedCrewHistory = "r" * 4096

    def captured(self):
        p = self.p
        p.step()
        raw = p.runtime.latestOutcomeSnapshot
        view, why = p.recall.Read(p.recall, raw, raw)
        self.assertIsNotNone(view, why)
        proposal, why = p.recall.Propose(p.recall, view, lua_table(p.h.lua,
            {"enabled": True, "mode": "Recall", "districtId": "d1", "memberSlot": 2,
             "minGarrison": 1, "maxAttempts": 2}))
        self.assertIsNotNone(proposal, why)
        baseline, why = p.recall.Capture(p.recall, proposal, raw)
        self.assertIsNotNone(baseline, why)
        proposal.requestId = 11
        return proposal, raw, baseline

    def record(self, proposal):
        return lua_table(self.p.h.lua, {key: proposal[key] for key in
            ("requestId", "account", "place", "release", "feature", "actionKey", "resources")})

    def test_valid_oversized_recall_projects_exact_native_and_source_custody_without_original_edits(self):
        proposal, raw, baseline = self.captured()
        self.inflate(raw)
        original = self.plain(raw)
        generic = self.p.h.proposal()
        self.assertIsNone(self.module.Capture(generic, raw, baseline)[0])
        saved, why = self.module.Capture(proposal, raw, baseline)
        self.assertIsNotNone(saved, why)
        data = self.module.Decode(saved)
        self.assertIsNone(data.before.unrelatedCatalog)
        self.assertIsNone(data.before.native.heistLedger)
        self.assertIsNone(data.before.native.family.unrelatedHistory)
        self.assertIsNone(data.before.native.crew[2].unrelatedCrewHistory)
        self.assertEqual((data.before.native.userId, data.before.native.family.id,
            data.before.native.crew[2].healId, data.before.native.crew[2].dutyToken,
            data.before.native.crew[2].dutyAt), (42, "own-family", "guard", "deployment-a", 900))
        self.assertEqual(self.plain(data.before.territoryDistrict), self.plain(raw.territoryDistrict))
        self.assertEqual(self.plain(data.before.recallOwnerProof), self.plain(raw.recallOwnerProof))
        self.assertEqual(self.plain(data.before.stationReservationProof), self.plain(raw.stationReservationProof))
        recaptured, why = self.p.recall.Capture(self.p.recall, data.proposal, data.before)
        self.assertIsNotNone(recaptured, why)
        self.assertEqual(self.plain(recaptured), self.plain(baseline))
        self.assertEqual(self.plain(raw), original)

    def test_copy_withreply_json_recomputes_same_capture_and_exact_member_home_effect(self):
        proposal, raw, baseline = self.captured()
        self.inflate(raw)
        saved, why = self.module.Capture(proposal, raw, baseline)
        self.assertIsNotNone(saved, why)
        record = self.record(proposal)
        copied = self.module.Copy(self.roundtrip(saved), record)[0]
        self.assertIsNotNone(copied)
        returned, why = self.module.WithReply(copied, record, self.p.settled())
        self.assertIsNotNone(returned, why)
        data = self.module.Decode(self.roundtrip(returned), record)
        self.assertIsNotNone(data)
        recaptured, why = self.p.recall.Capture(self.p.recall, data.proposal, data.before)
        self.assertIsNotNone(recaptured, why)
        self.assertEqual(self.plain(recaptured), self.plain(baseline))
        after = self.p.raw(2, True, .25)
        self.assertEqual(self.p.recall.owner.Evaluate(self.p.recall.owner,
            data.proposal, data.before, after, data.reply, data.baseline), "confirmed")
        after.native.crew[2].healId = "replacement"
        self.assertEqual(self.p.recall.owner.Evaluate(self.p.recall.owner,
            data.proposal, data.before, after, data.reply, data.baseline), "pending")

    def test_changed_projected_member_deployment_user_or_district_fails_recapture(self):
        proposal, raw, baseline = self.captured()
        saved = self.module.Capture(proposal, raw, baseline)[0]
        for path, value in ((("native", "crew", 2, "healId"), "replacement"),
                (("native", "crew", 2, "dutyToken"), "other-deployment"),
                (("native", "crew", 2, "dutyAt"), 901),
                (("native", "userId"), 43),
                (("native", "family", "id"), "other-family"),
                (("territoryDistrict", "district", "holderId"), "other-family")):
            with self.subTest(path=path):
                data = self.module.Decode(saved)
                target = data.before
                for key in path[:-1]: target = target[key]
                target[path[-1]] = value
                self.assertIsNone(self.p.recall.Capture(self.p.recall, data.proposal, data.before)[0])

    def test_absent_original_member_fields_are_not_repaired_or_defaulted(self):
        proposal, raw, baseline = self.captured()
        raw.native.crew[2].healId = None
        encoded, why = self.module.Capture(proposal, raw, baseline)
        self.assertIsNotNone(encoded, why)
        data = self.module.Decode(encoded)
        self.assertIsNone(data.before.native.crew[2].healId)
        self.assertIsNone(data.before.native.crew[2].injuredUntil)
        self.assertIsNone(data.before.native.crew[2].recalledUntil)
        self.assertIsNone(self.p.recall.Capture(self.p.recall, data.proposal, data.before)[0])

    def test_retained_proofs_and_baseline_keep_existing_byte_and_shape_limits(self):
        for destination in ("territoryDistrict", "recallOwnerProof", "baseline"):
            proposal, raw, baseline = self.captured()
            target = baseline if destination == "baseline" else raw[destination]
            target.requiredLarge = lua_table(self.p.h.lua, {str(i): "x" * 4096 for i in range(80)})
            self.assertIsNone(self.module.Capture(proposal, raw, baseline)[0], destination)
        proposal, raw, baseline = self.captured()
        self.p.h.lua.eval("function(v) return setmetatable(v,{}) end")(raw.native.crew[2])
        self.assertIsNone(self.module.Capture(proposal, raw, baseline)[0])

    def test_actual_oversized_app_snapshot_sends_one_recall_and_confirms_only_exact_home(self):
        p = self.p
        self.inflate(p.before)
        p.executor.reply = p.settled()
        p.begin()
        p.send()
        self.assertEqual(len(p.executor.calls), 1)
        p.h.at(.25)
        p.step(p.raw(2, True, .25))
        self.assertEqual(p.runtime.Status(p.runtime).outcomes.station, "confirmed")
        self.assertEqual(len(p.runtime.checkpoint.Records(p.runtime.checkpoint)), 0)
        self.assertEqual(p.recall.owner.Usage(p.recall.owner).attempted, 1)

    def test_oversized_pending_snapshot_restart_remains_status_only_and_recovers_exact_effect(self):
        p = self.p
        self.inflate(p.before)
        p.begin()
        p.send()
        p.h.at(.25)
        p.restart()
        p.before = p.raw(2, False, .25)
        p.step()
        self.assertEqual(len(p.executor.queued), 2)
        p.executor.status = p.settled()
        p.executor.queued[2]()
        p.h.at(.5)
        p.step(p.raw(3, True, .5))
        self.assertEqual(p.runtime.Status(p.runtime).recoveries.station, "confirmed")
        self.assertEqual([call.command for call in p.executor.calls.values()], ["recallcrew", "recallstatus"])
        self.assertEqual(p.recall.owner.Usage(p.recall.owner).attempted, 1)

    def test_oversized_saved_terminal_reply_recovers_without_another_physical_request(self):
        p = self.p
        self.inflate(p.before)
        p.executor.reply = p.settled()
        p.begin()
        p.send()
        p.h.at(.25)
        p.restart()
        p.step(p.raw(2, True, .25))
        self.assertEqual(p.runtime.Status(p.runtime).recoveries.station, "confirmed")
        self.assertEqual(len(p.executor.calls), 1)
        self.assertEqual(len(p.runtime.checkpoint.Records(p.runtime.checkpoint)), 0)


if __name__ == "__main__":
    unittest.main()
