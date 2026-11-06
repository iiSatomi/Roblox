"""Offline lifecycle and durable uncertainty with a fake atomic store."""
import unittest

from engine_harness import Harness, lua_table


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.store = self.h.lua.execute("""
            return { data = {}, failWrite = false, strictRecovery = true,
                Read = function(self, key) return self.data[key] end,
                Write = function(self, key, value)
                    if self.failWrite then error('disk unavailable') end
                    self.data[key] = value
                end,
            }
        """)
        self.checkpoint_module = self.h.load("src/storage/Checkpoint.luau")
        self.session_module = self.h.load("src/engine/Session.luau")
        self.checkpoint = self.checkpoint_module.new(self.store)
        self.session = self.session_module.new(
            self.h.broker, self.checkpoint, lua_table(self.h.lua, self.h.session)
        )

    def offer(self, feature="jobs", key="jobs:j_watch:1", resources=None):
        proposal = self.h.proposal(feature=feature, key=key)
        if resources is not None:
            proposal["resources"] = lua_table(self.h.lua, resources)
        return self.session.Offer(self.session, proposal, self.h.snapshot())

    def test_pause_blocks_send_and_resume_rechecks_preflight(self):
        self.assertEqual(self.offer()[0], "admitted")
        self.session.Pause(self.session)
        self.assertEqual(self.session.Tick(self.session, self.h.snapshot()), "paused")
        self.assertEqual(len(self.h.transport["sent"]), 0)
        self.assertEqual(self.offer(feature="operations", key="ops:1")[0], "blocked")
        self.session.Resume(self.session)
        self.h.at(3)
        self.assertEqual(self.session.Tick(self.session, self.h.snapshot(captured_at=0)), "stale_preflight")
        self.assertEqual(len(self.h.transport["sent"]), 0)

    def test_stop_before_send_and_close_are_terminal(self):
        self.assertEqual(self.offer()[0], "admitted")
        self.session.Stop(self.session)
        self.assertEqual(self.session.Tick(self.session, self.h.snapshot()), "stopped")
        self.assertEqual(self.offer()[0], "blocked")
        self.assertEqual(len(self.h.transport["sent"]), 0)

    def test_paused_sent_request_still_expires_at_original_deadline(self):
        self.offer()
        self.session.Tick(self.session, self.h.snapshot())
        self.session.Pause(self.session)
        self.h.at(45)
        self.assertEqual(self.session.Tick(self.session, self.h.snapshot()), "skipped_unconfirmed")
        self.assertEqual(self.session.Status(self.session)["uncertainCount"], 1)
        self.assertEqual(len(self.h.transport["sent"]), 1)
        self.session.Close(self.session)
        self.assertEqual(self.offer()[0], "blocked")

    def test_write_ahead_failure_prevents_transport_send(self):
        self.store["failWrite"] = True
        self.assertEqual(self.offer()[0], "admitted")
        self.assertEqual(self.session.Tick(self.session, self.h.snapshot()), "checkpoint_failed")
        self.assertEqual(len(self.h.transport["sent"]), 0)
        self.assertEqual(self.session.Status(self.session)["storageFault"], True)

    def test_adapter_false_write_also_prevents_send(self):
        self.store["Write"] = self.h.lua.eval("function() return false end")
        self.offer()
        self.assertEqual(self.session.Tick(self.session, self.h.snapshot()), "checkpoint_failed")
        self.assertEqual(len(self.h.transport["sent"]), 0)

    def test_read_exception_blocks_all_sends(self):
        self.session.Close(self.session)
        self.store["Read"] = self.h.lua.eval("function() error('disk unavailable') end")
        recovered = self.checkpoint_module.new(self.store)
        session = self.session_module.new(
            self.h.broker, recovered, lua_table(self.h.lua, self.h.session)
        )
        self.assertEqual(session.Status(session)["storageFault"], True)
        self.assertEqual(session.Offer(session, self.h.proposal(), self.h.snapshot())[0], "blocked")
        session.Close(session)

    def test_family_stage_claim_attempt_survives_restart(self):
        scope = self.h.session
        self.assertIsNone(self.checkpoint.Load(self.checkpoint,
            scope["account"], scope["place"], scope["release"])[1])
        first = self.h.proposal(feature="familyBossClaims",
            key="familyBossClaims:100:1")
        first["intent"] = lua_table(self.h.lua, {
            "kind": "familyBossClaim", "week": 100,
            "currentWeek": 100, "famId": 9,
            "stage": 1, "expiresAt": 1300, "attemptsBefore": 0})
        self.assertTrue(self.checkpoint.Save(self.checkpoint, first)[0])
        self.assertTrue(self.checkpoint.Resolve(
            self.checkpoint, first["actionKey"])[0])
        restarted = self.checkpoint_module.new(self.store)
        self.assertIsNone(restarted.Load(restarted,
            scope["account"], scope["place"], scope["release"])[1])
        usage = restarted.FamilyClaimUsage(restarted, 100, 0)
        self.assertEqual(usage["stages"][1], 1)
        self.assertFalse(restarted.Save(restarted, first)[0])
        self.assertEqual(len(restarted.FamilyClaimUsage(
            restarted, 101, 0)["stages"]), 0)
        historical = self.h.proposal(feature="familyBossClaims",
            key="familyBossClaims:99:7")
        historical["intent"] = lua_table(self.h.lua, {
            "kind": "familyBossClaim", "week": 99,
            "currentWeek": 100, "famId": 9,
            "stage": 7, "expiresAt": 1300, "attemptsBefore": 0})
        self.assertTrue(restarted.Save(restarted, historical)[0])
        self.assertTrue(restarted.Resolve(
            restarted, historical["actionKey"])[0])
        again = self.checkpoint_module.new(self.store)
        self.assertIsNone(again.Load(again,
            scope["account"], scope["place"], scope["release"])[1])
        self.assertEqual(again.FamilyClaimUsage(
            again, 99, 0)["stages"][1], 7)
        self.assertEqual(again.FamilyClaimUsage(
            again, 100, 0)["stages"][1], 1)

    def test_family_claim_checkpoint_migrates_legacy_single_week_shape(self):
        scope = self.h.session
        checkpoint = self.checkpoint_module.new(self.store)
        self.assertIsNone(checkpoint.Load(checkpoint,
            scope["account"], scope["place"], scope["release"])[1])
        key = checkpoint.ScopeKey(checkpoint)
        self.store["data"][key] = lua_table(self.h.lua, {
            "version": 1, "records": [],
            "familyClaimUsage": {"week": 99, "stages": [7]},
        })
        migrated = self.checkpoint_module.new(self.store)
        self.assertIsNone(migrated.Load(migrated,
            scope["account"], scope["place"], scope["release"])[1])
        self.assertEqual(migrated.FamilyClaimUsage(
            migrated, 99, 0)["stages"][1], 7)

    def test_family_free_attack_cap_and_spacing_survive_restart(self):
        scope = self.h.session
        self.assertIsNone(self.checkpoint.Load(self.checkpoint,
            scope["account"], scope["place"], scope["release"])[1])
        first = self.h.proposal(feature="familyBossAttacks",
            key="familyBossAttacks:100:9:0")
        first["intent"] = lua_table(self.h.lua, {
            "kind": "familyBossAttack", "week": 100,
            "famId": 9, "stage": 2, "serverNow": 1050,
            "hitsBefore": 0, "lastServerNowBefore": 0,
            "expectedStaminaCost": 1})
        self.assertTrue(self.checkpoint.Save(self.checkpoint, first)[0])
        self.assertTrue(self.checkpoint.Resolve(
            self.checkpoint, first["actionKey"])[0])
        restarted = self.checkpoint_module.new(self.store)
        self.assertIsNone(restarted.Load(restarted,
            scope["account"], scope["place"], scope["release"])[1])
        self.assertEqual(restarted.FamilyAttackUsage(
            restarted, 100, 9, 0)["hits"], 1)
        second = self.h.proposal(feature="familyBossAttacks",
            key="familyBossAttacks:100:9:1")
        second["intent"] = lua_table(self.h.lua, {
            "kind": "familyBossAttack", "week": 100,
            "famId": 9, "stage": 2, "serverNow": 1054,
            "hitsBefore": 1, "lastServerNowBefore": 1050,
            "expectedStaminaCost": 1})
        self.assertFalse(restarted.Save(restarted, second)[0])
        second["intent"]["serverNow"] = 1055
        self.assertTrue(restarted.Save(restarted, second)[0])
        self.assertEqual(restarted.FamilyAttackUsage(
            restarted, 101, 9, 0)["hits"], 0)

    def test_sent_action_survives_stop_and_rejoin_with_new_session_id(self):
        self.assertEqual(self.offer()[0], "admitted")
        self.assertEqual(self.session.Tick(self.session, self.h.snapshot()), "sent")
        self.session.Stop(self.session)
        recovered = self.checkpoint_module.new(self.store)
        other = dict(self.h.session, session="run-b")
        self.h.session = other
        self.h.policy["session"] = lua_table(self.h.lua, other)
        broker = self.h.load("src/engine/Broker.luau").new(
            self.h.clock, self.h.transport, self.h.journal, self.h.policy
        )
        session = self.session_module.new(
            broker, recovered, lua_table(self.h.lua, other)
        )
        self.assertEqual(session.Status(session)["uncertainCount"], 1)
        self.assertEqual(session.Offer(session, self.h.proposal(), self.h.snapshot())[0], "blocked")
        self.assertEqual(session.Offer(
            session, self.h.proposal(feature="operations", key="ops:1"), self.h.snapshot()
        )[0], "blocked")  # Both reserve energy.
        other_work = self.h.proposal(feature="operations", key="ops:cash")
        other_work["resources"] = lua_table(self.h.lua, {"cash": 1})
        self.assertEqual(session.Offer(session, other_work, self.h.snapshot())[0], "admitted")
        self.assertEqual(session.Tick(session, self.h.snapshot()), "sent")
        self.assertEqual(session.Status(session)["uncertainCount"], 2)
        session.Close(session)

    def test_skip_keeps_ledger_and_unrelated_work_continues(self):
        self.offer()
        self.session.Tick(self.session, self.h.snapshot())
        self.h.at(45)
        self.assertEqual(self.session.Tick(self.session, self.h.snapshot()), "skipped_unconfirmed")
        self.assertEqual(self.session.Status(self.session)["uncertainCount"], 1)
        other = self.h.proposal(feature="operations", key="ops:cash")
        other["resources"] = lua_table(self.h.lua, {"cash": 1})
        self.assertEqual(self.session.Offer(self.session, other, self.h.snapshot())[0], "admitted")

    def test_malformed_offer_with_unresolved_record_is_blocked_cleanly(self):
        self.offer()
        self.session.Tick(self.session, self.h.snapshot())
        self.h.at(45)
        self.session.Tick(self.session, self.h.snapshot())
        self.assertEqual(self.session.Offer(self.session, None, self.h.snapshot())[0], "blocked")

    def test_confirmation_clears_checkpoint_only_with_state_proof(self):
        self.offer()
        self.session.Tick(self.session, self.h.snapshot())
        self.assertEqual(self.session.Observe(self.session, self.h.snapshot()), "pending")
        self.assertEqual(self.session.Status(self.session)["uncertainCount"], 1)
        proof = self.h.snapshot(revision=2, proofKey="jobs:j_watch:1")
        self.assertEqual(self.session.Observe(self.session, proof), "confirmed")
        self.assertEqual(self.session.Status(self.session)["uncertainCount"], 0)

    def test_failed_clear_keeps_conservative_exposure(self):
        self.offer()
        self.session.Tick(self.session, self.h.snapshot())
        self.store["failWrite"] = True
        proof = self.h.snapshot(revision=2, proofKey="jobs:j_watch:1")
        self.assertEqual(self.session.Observe(self.session, proof), "confirmed")
        self.assertEqual(self.session.Status(self.session)["uncertainCount"], 1)
        self.assertEqual(self.offer(feature="operations", key="ops:1")[0], "blocked")

    def test_corrupt_record_and_failed_read_block_all_sends(self):
        self.session.Close(self.session)
        key = self.checkpoint.ScopeKey(self.checkpoint)
        self.store["data"][key] = lua_table(self.h.lua, {"version": 1, "records": [{"bad": True}]})
        recovered = self.checkpoint_module.new(self.store)
        session = self.session_module.new(
            self.h.broker, recovered, lua_table(self.h.lua, self.h.session)
        )
        self.assertEqual(session.Status(session)["storageFault"], True)
        self.assertEqual(session.Offer(session, self.h.proposal(), self.h.snapshot())[0], "blocked")
        session.Close(session)

    def test_account_place_release_scopes_do_not_cross(self):
        self.offer()
        self.session.Tick(self.session, self.h.snapshot())
        self.session.Close(self.session)
        for changed in ("account", "place", "release"):
            identity = dict(self.h.session, **{changed: "other"})
            checkpoint = self.checkpoint_module.new(self.store)
            records, reason = checkpoint.Load(
                checkpoint, identity["account"], identity["place"], identity["release"]
            )
            self.assertIsNone(reason)
            self.assertEqual(len(records), 0)

    def test_duplicate_initialization_rejected_until_stop(self):
        with self.assertRaises(Exception):
            self.session_module.new(
                self.h.broker, self.checkpoint_module.new(self.store),
                lua_table(self.h.lua, self.h.session)
            )
        self.session.Stop(self.session)
        replacement = self.session_module.new(
            self.h.broker, self.checkpoint_module.new(self.store),
            lua_table(self.h.lua, self.h.session)
        )
        replacement.Close(replacement)

    def test_favor_attempt_is_atomic_with_unresolved_action(self):
        proposal = self.h.proposal(feature="favors", key="favors:23:run-1:0")
        proposal["intent"] = lua_table(self.h.lua, {
            "kind": "favorHelp", "serverDay": 23,
            "usageAttemptsBefore": 0})
        self.assertEqual(self.checkpoint.FavorUsage(
            self.checkpoint, 23, 0)["attempts"], 0)
        self.assertEqual(self.session.Offer(self.session, proposal,
            self.h.snapshot())[0], "admitted")
        self.assertEqual(self.session.Tick(self.session,
            self.h.snapshot()), "sent")
        self.assertEqual(self.checkpoint.FavorUsage(
            self.checkpoint, 23, 0)["attempts"], 1)
        self.session.Close(self.session)
        recovered = self.checkpoint_module.new(self.store)
        records, reason = recovered.Load(recovered, "user-a",
            "73897506680154", "release-a")
        self.assertIsNone(reason)
        self.assertEqual(len(records), 1)
        self.assertEqual(recovered.FavorUsage(recovered, 23, 0)["attempts"], 1)
        self.assertEqual(recovered.FavorUsage(recovered, 24, 0)["attempts"], 0)
        self.assertIsNone(recovered.FavorUsage(recovered, 22, 0))

    def test_favor_cap_and_stale_attempt_cannot_write(self):
        for count in range(5):
            proposal = self.h.proposal(feature="favors",
                key=f"favors:23:run-{count}:0")
            proposal["intent"] = lua_table(self.h.lua, {
                "kind": "favorHelp", "serverDay": 23,
                "usageAttemptsBefore": count})
            self.assertEqual(self.checkpoint.Save(
                self.checkpoint, proposal)[0], True)
            self.assertEqual(self.checkpoint.Resolve(
                self.checkpoint, proposal["actionKey"])[0], True)
        self.assertEqual(self.checkpoint.FavorUsage(
            self.checkpoint, 23, 0)["attempts"], 5)
        capped = self.h.proposal(feature="favors", key="favors:23:run-5:0")
        capped["intent"] = lua_table(self.h.lua, {
            "kind": "favorHelp", "serverDay": 23,
            "usageAttemptsBefore": 5})
        self.assertEqual(self.checkpoint.Save(self.checkpoint, capped)[0], False)
        stale = self.h.proposal(feature="favors", key="favors:24:run-1:0")
        stale["intent"] = lua_table(self.h.lua, {
            "kind": "favorHelp", "serverDay": 24,
            "usageAttemptsBefore": 1})
        self.assertEqual(self.checkpoint.Save(self.checkpoint, stale)[0], False)
        self.assertEqual(self.checkpoint.FavorUsage(
            self.checkpoint, 24, 0)["attempts"], 0)

    def test_failed_favor_write_does_not_dispatch_or_count(self):
        proposal = self.h.proposal(feature="favors", key="favors:23:run-1:0")
        proposal["intent"] = lua_table(self.h.lua, {
            "kind": "favorHelp", "serverDay": 23,
            "usageAttemptsBefore": 0})
        self.store["failWrite"] = True
        self.assertEqual(self.session.Offer(self.session, proposal,
            self.h.snapshot())[0], "admitted")
        self.assertEqual(self.session.Tick(self.session,
            self.h.snapshot()), "checkpoint_failed")
        self.assertEqual(len(self.h.transport["sent"]), 0)

    def test_boss_attempt_count_and_spacing_survive_restart(self):
        first = self.h.proposal(feature="bosses", key="bosses:2026294:2:0")
        first["intent"] = lua_table(self.h.lua, {
            "kind": "bossStageAttack", "dayStamp": 2026294,
            "serverNow": 2000000, "expectedStaminaCost": 1,
            "hitsBefore": 0, "staminaBefore": 0,
            "lastServerNowBefore": 0})
        self.assertEqual(self.checkpoint.Save(self.checkpoint, first)[0], True)
        self.assertEqual(self.checkpoint.Resolve(
            self.checkpoint, first["actionKey"])[0], True)
        self.session.Close(self.session)
        recovered = self.checkpoint_module.new(self.store)
        self.assertIsNone(recovered.Load(recovered, "user-a",
            "73897506680154", "release-a")[1])
        proof = recovered.BossUsage(recovered, 2026294, 0)
        self.assertEqual((proof["hits"], proof["stamina"],
                          proof["lastServerNow"]), (1, 1, 2000000))
        second = self.h.proposal(feature="bosses", key="bosses:2026294:2:1")
        second["intent"] = lua_table(self.h.lua, {
            "kind": "bossStageAttack", "dayStamp": 2026294,
            "serverNow": 2000004, "expectedStaminaCost": 1,
            "hitsBefore": 1, "staminaBefore": 1,
            "lastServerNowBefore": 2000000})
        self.assertEqual(recovered.Save(recovered, second)[0], False)
        second["intent"]["serverNow"] = 2000005
        self.assertEqual(recovered.Save(recovered, second)[0], True)
        self.assertEqual(recovered.BossUsage(
            recovered, 2026294, 0)["hits"], 2)
        self.assertEqual(recovered.BossUsage(
            recovered, 2026295, 0)["hits"], 0)

    def test_boss_checkpoint_cap_is_independent_of_planner(self):
        key = self.checkpoint.ScopeKey(self.checkpoint)
        self.store["data"][key] = lua_table(self.h.lua, {
            "version": 1, "records": [],
            "bossUsage": {"day": 2026294, "hits": 100,
                          "stamina": 100,
                          "lastServerNow": 2000000}})
        self.session.Close(self.session)
        recovered = self.checkpoint_module.new(self.store)
        self.assertIsNone(recovered.Load(recovered, "user-a",
            "73897506680154", "release-a")[1])
        proposal = self.h.proposal(feature="bosses", key="bosses:cap")
        proposal["intent"] = lua_table(self.h.lua, {
            "kind": "bossStageAttack", "dayStamp": 2026294,
            "serverNow": 2000006, "expectedStaminaCost": 1,
            "hitsBefore": 100, "staminaBefore": 100,
            "lastServerNowBefore": 2000000})
        self.assertEqual(recovered.Save(recovered, proposal)[0], False)

    def test_sabotage_attempt_survives_restart_and_caps(self):
        proposal = self.h.proposal(feature="sabotage",
            key="sabotage:23:string:run-1:0")
        proposal["intent"] = lua_table(self.h.lua, {
            "kind": "heistSabotage", "serverDay": 23,
            "usageAttemptsBefore": 0})
        self.assertEqual(self.checkpoint.Save(
            self.checkpoint, proposal)[0], True)
        self.session.Close(self.session)
        recovered = self.checkpoint_module.new(self.store)
        self.assertIsNone(recovered.Load(recovered, "user-a",
            "73897506680154", "release-a")[1])
        self.assertEqual(recovered.SabotageUsage(
            recovered, 23, 0)["attempts"], 1)
        self.assertEqual(recovered.SabotageUsage(
            recovered, 24, 0)["attempts"], 0)
        self.assertIsNone(recovered.SabotageUsage(recovered, 22, 0))
        stale = self.h.proposal(feature="sabotage",
            key="sabotage:23:string:run-2:0")
        stale["intent"] = lua_table(self.h.lua, {
            "kind": "heistSabotage", "serverDay": 23,
            "usageAttemptsBefore": 0})
        self.assertEqual(recovered.Save(recovered, stale)[0], False)

    def test_global_claim_once_per_run_survives_restart(self):
        first = self.h.proposal(feature="globalBossClaim",
            key="globalBossClaim:hellfire_2000000")
        first["intent"] = lua_table(self.h.lua, {
            "kind": "globalBossClaim",
            "runKey": "hellfire_2000000",
            "attemptsBefore": 0})
        self.assertEqual(self.checkpoint.Save(
            self.checkpoint, first)[0], True)
        self.session.Close(self.session)
        recovered = self.checkpoint_module.new(self.store)
        self.assertIsNone(recovered.Load(recovered, "user-a",
            "73897506680154", "release-a")[1])
        self.assertEqual(recovered.GlobalClaimUsage(recovered,
            "hellfire_2000000", 0)["attempts"], 1)
        self.assertEqual(recovered.GlobalClaimUsage(recovered,
            "judge_3000000", 0)["attempts"], 0)
        second = self.h.proposal(feature="globalBossClaim",
            key="globalBossClaim:hellfire_2000000:retry")
        second["intent"] = lua_table(self.h.lua, {
            "kind": "globalBossClaim",
            "runKey": "hellfire_2000000",
            "attemptsBefore": 1})
        self.assertEqual(recovered.Save(recovered, second)[0], False)

    def test_global_attack_count_spacing_and_restart(self):
        first = self.h.proposal(feature="globalBossAttack",
            key="globalBossAttack:hellfire_2000000:0")
        first["intent"] = lua_table(self.h.lua, {
            "kind": "globalBossAttack",
            "runKey": "hellfire_2000000",
            "hitsBefore": 0, "lastServerNowBefore": 0,
            "serverNow": 2000100})
        self.assertEqual(self.checkpoint.Save(
            self.checkpoint, first)[0], True)
        self.session.Close(self.session)
        recovered = self.checkpoint_module.new(self.store)
        self.assertIsNone(recovered.Load(recovered, "user-a",
            "73897506680154", "release-a")[1])
        proof = recovered.GlobalAttackUsage(recovered,
            "hellfire_2000000", 0)
        self.assertEqual((proof["hits"], proof["lastServerNow"]),
                         (1, 2000100))
        self.assertEqual(recovered.GlobalAttackUsage(recovered,
            "judge_3000000", 0)["hits"], 0)
        second = self.h.proposal(feature="globalBossAttack",
            key="globalBossAttack:hellfire_2000000:1")
        second["intent"] = lua_table(self.h.lua, {
            "kind": "globalBossAttack",
            "runKey": "hellfire_2000000",
            "hitsBefore": 1, "lastServerNowBefore": 2000100,
            "serverNow": 2000104})
        self.assertEqual(recovered.Save(recovered, second)[0], False)
        second["intent"]["serverNow"] = 2000105
        self.assertEqual(recovered.Save(recovered, second)[0], True)

    def tearDown(self):
        self.session.Close(self.session)


if __name__ == "__main__":
    unittest.main()
