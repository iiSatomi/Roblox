"""One durable own-deployment recall; recovered requests are status-only."""
import unittest

from engine_harness import Harness, ROOT, lua_table


class TerritoryRecallTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.h.session["account"] = "user-a"
        self.identitySource=self.h.lua.execute('local fence={owners={},writing={}};return {DurableFence=function()return fence end,Identity=function() return {account="user-a",userId=101,place="73897506680154",nativeJob="recall-job",nativeEpoch="recall-epoch",nativeSourceKey=string.rep("a",64)} end}')
        self.scope = lua_table(self.h.lua, {**self.h.session, "userId": 101})
        self.terms = lua_table(self.h.lua, {"release": "release-a",
            "recallCooldownSeconds": 600})
        path = ROOT / "src/tabs/territory/RecallTransactions.luau"
        self.assertTrue(path.is_file(), "Missing durable RecallTransactions")
        self.module = self.h.load(path.relative_to(ROOT).as_posix())
        self.storage = self.h.lua.execute("""return { strictRecovery=true,
            data={}, fail=false, writes=0,
            Read=function(self,key) return self.data[key] end,
            Write=function(self,key,value)
                if self.fail then return false end
                self.writes=self.writes+1; self.data[key]=value; return true
            end }""")
        self.tx = self.restart()

    def restart(self):
        tx, reason = self.module.new(self.storage, self.scope, self.terms, self.identitySource)
        self.assertIsNone(reason)
        return tx

    def test_territory_tab_factory_uses_reviewed_cooldown_and_own_scope(self):
        entry = self.h.load("src/tabs/territory/Module.luau")
        deps = {name: self.h.load(path) for name, path in {
            "TerritoryMapQuery": "src/tabs/territory/TerritoryMapQuery.luau",
            "ResidencyQuery": "src/tabs/territory/ResidencyQuery.luau",
            "TerritoryState": "src/tabs/territory/TerritoryState.luau",
            "ReadAttachment": "src/tabs/territory/ReadAttachment.luau",
            "TerritoryBlocked": "src/tabs/territory/TerritoryBlocked.luau"}.items()}
        deps.update({"RecallTransactions": self.module, "release": "release-a", "nativeRecallLease": self.identitySource,
                     "config": {"TERRITORY": {"recallCooldownSeconds": 600}}})
        tab = entry.new(lua_table(self.h.lua, deps))
        tx, reason = tab.NewRecallTransactions(tab, self.storage, self.scope)
        self.assertIsNone(reason)
        self.assertEqual(tx.LastRequestId(tx), 0)
        self.scope.userId = 102
        self.assertIsNone(tab.NewRecallTransactions(tab, self.storage, self.scope)[0])

    def raw(self, revision=4, server=1700000000, home=False, cooldown=True):
        member = {"name": "Guard", "rarity": 4, "train": 2, "healId": "guard",
                  "weapon": "w_baton", "injuredUntil": 0, "recalledUntil": 0}
        if not home:
            member.update(duty="d1", dutyToken="deployment-a", dutyAt=1699999000)
        elif cooldown:
            member.update(injuredUntil=1700000602, recalledUntil=1700000602)
        return self.h.snapshot(revision=revision, captured_at=10, native={
            "fullSync": True, "serverNow": server, "userId": 101, "family": {"id": "fam-a"},
            "crew": [{"name": "Player"}, member,
                     {"name": "Medic", "rarity": 3, "train": 1, "healId": "medic"}]})

    def proposal(self, request_id=1700000000000, fallback=False):
        intent = {"kind": "territoryRecall", "requestId": request_id,
            "districtId": "d1", "userId": 101, "memberIndex": 2,
            "deploymentId": "deployment-a", "at": 1699999000,
            "memberName": "Guard", "rarity": 4, "memberKey": "id:guard", "maxAttempts": 1000,
            "attemptedBefore": self.tx.Usage(self.tx).attempted if self.tx else 0,
            "nativeJob": "recall-job", "nativeEpoch": "recall-epoch", "nativeSourceKey": "a"*64, "nativeCounterBefore": 0}
        if fallback:
            del intent["deploymentId"]
        return lua_table(self.h.lua, {**self.h.session, "feature": "station",
            "revision": 4, "actionKey": "recall:" + str(request_id),
            "resources": {}, "intent": intent})

    def reply(self, fallback=False):
        target = {"districtId": "d1", "userId": 101, "memberIndex": 2,
            "deploymentId": "deployment-a", "at": 1699999000,
            "memberName": "Guard", "rarity": 4}
        if fallback:
            del target["deploymentId"]
        return lua_table(self.h.lua, {"ok": True, "settled": [target]})

    def prepare(self, fallback=False):
        raw, proposal = self.raw(), self.proposal(fallback=fallback)
        if fallback:
            raw.native.crew[2].dutyToken = None
        ok, reason = self.tx.Prepare(self.tx, proposal, raw, 11)
        self.assertTrue(ok, reason)
        return proposal, raw

    def send(self, fallback=False):
        proposal, raw = self.prepare(fallback)
        ok, reason = self.tx.MarkSending(self.tx, raw, 11)
        self.assertTrue(ok, reason)
        return proposal, raw

    def settle(self, fallback=False):
        self.send(fallback)
        ok, reason = self.tx.AcceptReply(self.tx, 1700000000000, self.reply(fallback))
        self.assertTrue(ok, reason)

    def test_write_ahead_single_submit_and_exact_saved_native_arguments(self):
        proposal, raw = self.prepare()
        self.assertIsNone(self.tx.SubmitCall(self.tx)[0])
        self.assertIsNone(self.tx.StatusCall(self.tx)[0])
        self.assertTrue(self.tx.MarkSending(self.tx, raw, 11)[0])
        call, reason = self.tx.SubmitCall(self.tx, raw, 11)
        self.assertIsNone(reason)
        self.assertEqual((call.remote, call.method, call.arity),
                         ("TerritoryAction", "InvokeServer", 3))
        self.assertEqual(call.args[1], "recallcrew")
        self.assertEqual(call.args[2], proposal.intent.requestId)
        self.assertEqual(len(call.args[3]), 1)
        target = call.args[3][1]
        self.assertEqual((target.userId, target.memberIndex, target.deploymentId,
                          target.at, target.memberName),
                         (101, 2, "deployment-a", 1699999000, "Guard"))
        self.assertIsNone(self.tx.SubmitCall(self.tx)[0])
        self.assertFalse(self.tx.MarkSending(self.tx, raw, 11)[0])
        self.assertEqual(len(self.h.transport.sent), 0)

    def test_restart_after_sent_gate_is_status_only_even_before_submit(self):
        self.send()
        self.tx = self.restart()
        self.assertIsNone(self.tx.SubmitCall(self.tx)[0])
        call, reason = self.tx.StatusCall(self.tx)
        self.assertIsNone(reason)
        self.assertEqual((call.remote, call.arity, call.args[1], call.args[2], call.args[3]),
                         ("TerritoryStatus", 3, "recallstatus", 1700000000000, None))
        self.assertFalse(self.tx.Prepare(self.tx, self.proposal(), self.raw(), 11)[0])

    def test_settled_reply_and_newer_same_member_home_cooldown_are_both_required(self):
        self.send()
        after = self.raw(5, 1700000005, home=True)
        self.assertNotEqual(self.tx.Reconcile(self.tx, after)[0], "observed")
        self.assertTrue(self.tx.AcceptReply(self.tx, 1700000000000, self.reply())[0])
        self.assertNotEqual(self.tx.Reconcile(self.tx, self.raw(5, 1700000005))[0], "observed")
        self.assertEqual(self.tx.Reconcile(self.tx, after)[0], "observed")
        self.assertTrue(self.tx.ClearObserved(self.tx)[0])
        restarted = self.restart()
        self.assertIsNone(restarted.Active(restarted))

    def test_restart_recovers_settled_proof_and_lower_local_revision_with_native_time(self):
        self.settle()
        self.tx = self.restart()
        after = self.raw(0, 1700000005, home=True)
        after.session = "restarted"
        self.assertEqual(self.tx.Reconcile(self.tx, after)[0], "observed")

    def test_same_or_regressed_native_time_after_restart_cannot_confirm(self):
        self.settle()
        after = self.raw(0, 1700000000, home=True)
        after.session = "restarted"
        for server in (1700000000, 1699999999, None, float("nan"), float("inf")):
            after.native.serverNow = server
            self.assertNotEqual(self.tx.Reconcile(self.tx, after)[0], "observed")
        after.session, after.revision, after.native.serverNow = "run-a", 4, 1700000005
        self.assertNotEqual(self.tx.Reconcile(self.tx, after)[0], "observed")

    def test_unknown_request_pending_rate_limited_missing_or_wrong_settlement_never_replays(self):
        self.send()
        self.tx.SubmitCall(self.tx, self.raw(), 11)
        for reply in (None, {"ok": False, "code": "unknown_request"},
                {"ok": True, "code": "unknown_request"},
                {"ok": True, "code": "rate_limited"},
                {"ok": True, "pending": True}, {"ok": True, "settled": []}):
            self.assertFalse(self.tx.AcceptReply(self.tx, 1700000000000,
                lua_table(self.h.lua, reply))[0])
            self.assertFalse(self.tx.ClearObserved(self.tx)[0])
            restarted = self.restart()
            self.assertIsNone(restarted.SubmitCall(restarted)[0])
        self.assertEqual(self.tx.Active(self.tx).stage, "sent")

    def test_reply_callback_id_and_exact_own_deployment_identity_are_mandatory(self):
        self.send()
        self.assertFalse(self.tx.AcceptReply(self.tx, 1700000000001, self.reply())[0])
        for field, value in (("userId", 202), ("memberIndex", 3), ("districtId", "d2"),
                             ("deploymentId", "deployment-b"), ("memberName", "Replacement")):
            reply = self.reply()
            reply.settled[1][field] = value
            self.assertFalse(self.tx.AcceptReply(self.tx, 1700000000000, reply)[0], field)
        reply = self.reply()
        reply.settled[2] = reply.settled[1]
        self.assertFalse(self.tx.AcceptReply(self.tx, 1700000000000, reply)[0])

    def test_at_fallback_requires_exact_timestamp_and_member_name(self):
        self.send(fallback=True)
        for field, value in (("at", 1699999001), ("memberName", "Other"),
                             ("deploymentId", "unexpected")):
            reply = self.reply(fallback=True)
            reply.settled[1][field] = value
            self.assertFalse(self.tx.AcceptReply(self.tx, 1700000000000, reply)[0])
        self.assertTrue(self.tx.AcceptReply(self.tx, 1700000000000, self.reply(True))[0])
        self.assertEqual(self.tx.Reconcile(self.tx, self.raw(5, 1700000005,
            home=True, cooldown=False))[0], "observed")

    def test_changed_family_account_member_roster_or_remaining_duty_cannot_confirm(self):
        self.settle()
        for change in ("account", "family", "replacement", "gear", "other-replacement",
                       "token", "training", "rolling", "incomplete", "size"):
            after = self.raw(5, 1700000005, home=True)
            if change == "account": after.account = "202"
            elif change == "family": after.native.family.id = "other"
            elif change == "replacement": after.native.crew[2].name = "Replacement"
            elif change == "gear": after.native.crew[2].weapon = "w_gavel"
            elif change == "other-replacement": after.native.crew[3].name = "Replacement"
            elif change == "token": after.native.crew[2].dutyToken = "deployment-b"
            elif change == "training": after.native.crew[2].training = self.h.lua.table()
            elif change == "rolling": after.native.crew[2].rolling = True
            elif change == "incomplete": after.native.fullSync = False
            else: after.native.crew[4] = lua_table(self.h.lua, {"name": "New", "rarity": 2})
            self.assertNotEqual(self.tx.Reconcile(self.tx, after)[0], "observed", change)

    def test_cooldown_exact_duration_bounds_and_unworn_no_cooldown(self):
        self.settle()
        for injured, recalled in ((1700000601, 1700000602), (1700000500, 1700000500),
                                  (1700000700, 1700000700), (0, 1700000602)):
            after = self.raw(5, 1700000005, home=True)
            after.native.crew[2].injuredUntil, after.native.crew[2].recalledUntil = injured, recalled
            self.assertNotEqual(self.tx.Reconcile(self.tx, after)[0], "observed")
        self.assertEqual(self.tx.Reconcile(self.tx, self.raw(5, 1700000005,
            home=True, cooldown=False))[0], "observed")

    def test_expired_return_cooldown_can_reconcile_after_late_restart(self):
        self.settle()
        after = self.raw(0, 1700000800, home=True)
        after.session = "late-restart"
        restarted = self.restart()
        self.assertEqual(restarted.Reconcile(restarted, after)[0], "observed")

    def test_prepare_rejects_other_player_stale_nonce_changed_target_and_bad_scope(self):
        for field, value in (("userId", 202), ("memberIndex", 1),
                ("deploymentId", "different"), ("at", 1), ("memberName", "Wrong"),
                ("requestId", 0), ("requestId", 1699999999999), ("requestId", 1.5)):
            proposal = self.proposal()
            proposal.intent[field] = value
            self.assertFalse(self.tx.Prepare(self.tx, proposal, self.raw(), 11)[0], field)
        self.assertFalse(self.tx.Prepare(self.tx, self.proposal(), self.raw(), 26)[0])
        scope = lua_table(self.h.lua, {**self.h.session, "userId": 202})
        self.assertIsNone(self.module.new(self.storage, scope, self.terms)[0])
        raw = self.raw()
        raw.native.crew[2].dutyToken, raw.native.crew[2].dutyAt = None, None
        self.assertFalse(self.tx.Prepare(self.tx, self.proposal(fallback=True), raw, 11)[0])

    def test_send_gate_rechecks_current_deployment_and_cannot_use_stale_capture(self):
        _, before = self.prepare()
        changed = self.raw()
        changed.native.crew[2].dutyToken = "replacement"
        self.assertFalse(self.tx.MarkSending(self.tx, changed, 11)[0])
        self.assertFalse(self.tx.MarkSending(self.tx, before, 26)[0])
        self.assertIsNone(self.tx.SubmitCall(self.tx)[0])

    def test_persistence_failure_at_every_transition_never_advances_or_arms_send(self):
        self.storage.fail = True
        self.assertFalse(self.tx.Prepare(self.tx, self.proposal(), self.raw(), 11)[0])
        self.assertIsNone(self.tx.Active(self.tx))
        self.storage.fail = False
        self.tx = self.restart()
        _, before = self.prepare()
        self.storage.fail = True
        self.assertFalse(self.tx.MarkSending(self.tx, before, 11)[0])
        self.assertIsNone(self.tx.SubmitCall(self.tx)[0])
        self.storage.fail = False
        self.tx = self.restart()
        self.tx.MarkSending(self.tx, before, 11)
        self.storage.fail = True
        self.assertFalse(self.tx.AcceptReply(self.tx, 1700000000000, self.reply())[0])
        self.assertEqual(self.tx.Active(self.tx).stage, "sent")
        self.storage.fail = False
        self.tx = self.restart()
        self.tx.AcceptReply(self.tx, 1700000000000, self.reply())
        self.storage.fail = True
        after = self.raw(5, 1700000005, home=True)
        self.assertNotEqual(self.tx.Reconcile(self.tx, after)[0], "observed")
        self.assertEqual(self.tx.Active(self.tx).stage, "settled")
        self.storage.fail = False
        self.tx = self.restart()
        self.tx.Reconcile(self.tx, after)
        self.storage.fail = True
        self.assertFalse(self.tx.ClearObserved(self.tx)[0])
        self.assertEqual(self.tx.Active(self.tx).stage, "observed")

    def test_saved_nested_copies_corruption_bounds_and_monotonic_highwater(self):
        self.settle()
        record = self.tx.Active(self.tx)
        record.target.deploymentId = "changed"
        self.assertEqual(self.tx.Active(self.tx).target.deploymentId, "deployment-a")
        saved = self.storage.data[self.tx.key]
        saved.transaction.baseline.members["2"].name = "Changed"
        self.assertEqual(self.tx.Active(self.tx).baseline.members["2"].name, "Guard")
        tx, reason = self.module.new(self.storage, self.scope, self.terms, self.identitySource)
        self.assertIsNone(tx)
        self.assertIn("Corrupt", reason)
        saved.transaction.baseline.members["2"].name = "Guard"
        self.tx.Reconcile(self.tx, self.raw(5, 1700000005, home=True))
        self.tx.ClearObserved(self.tx)
        self.tx = self.restart()
        self.assertFalse(self.tx.Prepare(self.tx, self.proposal(), self.raw(), 11)[0])
        proposal = self.proposal(1700000000001)
        self.assertTrue(self.tx.Prepare(self.tx, proposal, self.raw(), 11)[0])

    def test_idempotent_reply_reconcile_and_fake_executor_zero_automatic_retry(self):
        self.send()
        call = self.tx.SubmitCall(self.tx, self.raw(), 11)[0]
        executor = self.h.lua.execute("""return {calls={}, Invoke=function(self, remote, method, ...)
            self.calls[#self.calls+1]={remote=remote,method=method,args=table.pack(...)}
            return {ok=false,code='unknown_request'}
        end}""")
        reply = executor.Invoke(executor, call.remote, call.method,
            call.args[1], call.args[2], call.args[3])
        self.assertFalse(self.tx.AcceptReply(self.tx, call.args[2], reply)[0])
        self.assertEqual(len(executor.calls), 1)
        self.assertIsNone(self.tx.SubmitCall(self.tx)[0])
        self.tx.AcceptReply(self.tx, call.args[2], self.reply())
        writes = self.storage.writes
        self.assertTrue(self.tx.AcceptReply(self.tx, call.args[2], self.reply())[0])
        self.assertEqual(self.storage.writes, writes)
        after = self.raw(5, 1700000005, home=True)
        self.tx.Reconcile(self.tx, after)
        writes = self.storage.writes
        self.assertEqual(self.tx.Reconcile(self.tx, after)[0], "observed")
        self.assertEqual(self.storage.writes, writes)

    def test_malformed_source_numbers_roster_and_clocks_never_prepare(self):
        for field, value in (("train", False), ("injuredUntil", False),
                ("recalledUntil", False), ("dutyAt", float("nan")),
                ("dutyToken", {}), ("training", True), ("rolling", "false")):
            raw = self.raw()
            raw.native.crew[2][field] = lua_table(self.h.lua, value)
            self.assertFalse(self.tx.Prepare(self.tx, self.proposal(), raw, 11)[0], field)
        for now in (None, -1, float("nan"), float("inf")):
            self.assertFalse(self.tx.Prepare(self.tx, self.proposal(), self.raw(), now)[0])
        raw = self.raw()
        raw.capturedAt = 13
        self.assertFalse(self.tx.Prepare(self.tx, self.proposal(), raw, 11)[0])
        raw = self.raw()
        raw.native.crew[3].healId = raw.native.crew[2].healId
        self.assertFalse(self.tx.Prepare(self.tx, self.proposal(), raw, 11)[0])

    def test_corrupt_or_overlarge_recovery_data_is_held_without_rewrite(self):
        for problem in ("cycle", "depth", "rows", "scope", "highwater", "cooldown", "stage"):
            self.setUp()
            self.send()
            saved = self.storage.data[self.tx.key]
            record = saved.transaction
            if problem == "cycle": record.loop = record
            elif problem == "depth":
                record.extra = lua_table(self.h.lua, {"a": {"b": {"c": {"d": {"e": {"f": {"g": {}}}}}}}})
            elif problem == "rows":
                for index in range(3, 66):
                    record.baseline.members[str(index)] = record.baseline.members["2"]
            elif problem == "scope": record.account = "202"
            elif problem == "highwater": saved.lastRequestId -= 1
            elif problem == "cooldown": record.cooldownSeconds = 1
            else: record.stage = "cancelled"
            writes = self.storage.writes
            restarted, reason = self.module.new(self.storage, self.scope, self.terms, self.identitySource)
            self.assertIsNone(restarted, problem)
            self.assertIn("Corrupt", reason)
            self.assertEqual(self.storage.writes, writes)

    def test_call_targets_and_recovered_storage_are_detached_copies(self):
        self.send()
        call = self.tx.SubmitCall(self.tx, self.raw(), 11)[0]
        call.args[3][1].deploymentId = "changed"
        self.assertEqual(self.tx.Active(self.tx).target.deploymentId, "deployment-a")
        restarted = self.restart()
        self.storage.data[self.tx.key].transaction.baseline.members["2"].weapon = "changed"
        self.assertEqual(restarted.Active(restarted).baseline.members["2"].weapon, "w_baton")
        self.assertEqual(self.tx.Active(self.tx).baseline.members["2"].weapon, "w_baton")

    def test_failed_read_write_exception_and_unknown_intent_are_fail_closed(self):
        broken = self.h.lua.execute("""return {strictRecovery=true,
            Read=function() error('unreadable') end, Write=function() return true end}""")
        self.assertIsNone(self.module.new(broken, self.scope, self.terms)[0])
        proposal = self.proposal()
        proposal.intent.targets = self.h.lua.table()
        self.assertIsNone(self.module.describe(proposal)[0])
        self.assertFalse(self.tx.Prepare(self.tx, proposal, self.raw(), 11)[0])
        self.storage.Write = self.h.lua.eval("function() error('disk full') end")
        self.assertFalse(self.tx.Prepare(self.tx, self.proposal(), self.raw(), 11)[0])
        self.assertIsNone(self.tx.Active(self.tx))

    def test_prepared_restart_is_not_sent_or_cleared_and_highwater_is_visible(self):
        self.prepare()
        restarted = self.restart()
        self.assertTrue(callable(restarted.LastRequestId))
        self.assertEqual(restarted.LastRequestId(restarted), 1700000000000)
        self.assertIsNone(restarted.SubmitCall(restarted)[0])
        self.assertIsNone(restarted.StatusCall(restarted)[0])
        self.assertFalse(restarted.ClearObserved(restarted)[0])
        after = self.raw(0, 1700000005, home=True)
        after.session = "restart"
        self.assertEqual(restarted.Reconcile(restarted, after)[0], "prepared")

    def test_delayed_submit_and_matching_unknown_reply_consume_arm_without_replay(self):
        self.send()
        self.assertIsNone(self.tx.SubmitCall(self.tx, self.raw(), 26)[0])
        self.assertIsNone(self.tx.SubmitCall(self.tx, self.raw(), 11)[0])
        self.setUp()
        self.send()
        self.tx.AcceptReply(self.tx, 1700000000000,
            lua_table(self.h.lua, {"ok": False, "code": "unknown_request"}))
        self.assertIsNone(self.tx.SubmitCall(self.tx, self.raw(), 11)[0])

    def test_unrelated_crew_training_healing_and_gear_do_not_block_exact_recovery(self):
        self.send()
        self.tx.SubmitCall(self.tx, self.raw(), 11)
        self.tx.AcceptReply(self.tx, 1700000000000,
            lua_table(self.h.lua, {"ok": False, "code": "unknown_request"}))
        self.tx = self.restart()
        self.assertIsNone(self.tx.SubmitCall(self.tx, self.raw(), 11)[0])
        self.assertTrue(self.tx.AcceptReply(self.tx, 1700000000000, self.reply())[0])
        after = self.raw(0, 1700000100, home=True)
        after.session = "after-gate-release"
        other = after.native.crew[3]
        other.train = 3
        other.training = lua_table(self.h.lua, {"endsAt": 1700001000})
        other.weapon = "w_pipe"
        other.injuredUntil = 1700000500
        self.assertEqual(self.tx.Reconcile(self.tx, after)[0], "observed")
        self.assertIsNone(self.tx.SubmitCall(self.tx, after, 11)[0])
        self.assertEqual(len(self.h.transport.sent), 0)

    def test_discard_known_unsent_prepared_record_is_durable_and_preserves_highwater(self):
        self.assertTrue(callable(self.tx.DiscardPrepared))
        self.assertFalse(self.tx.DiscardPrepared(self.tx)[0])
        self.prepare()
        self.storage.fail = True
        self.assertFalse(self.tx.DiscardPrepared(self.tx)[0])
        self.assertEqual(self.tx.Active(self.tx).stage, "prepared")
        self.storage.fail = False
        self.tx = self.restart()
        self.assertTrue(self.tx.DiscardPrepared(self.tx)[0])
        self.assertIsNone(self.tx.Active(self.tx))
        self.tx = self.restart()
        self.assertIsNone(self.tx.Active(self.tx))
        self.assertEqual(self.tx.LastRequestId(self.tx), 1700000000000)
        self.assertFalse(self.tx.Prepare(self.tx, self.proposal(), self.raw(), 11)[0])
        self.assertTrue(self.tx.Prepare(self.tx, self.proposal(1700000000001), self.raw(), 11)[0])

    def test_discard_prepared_refuses_sent_uncertain_settled_and_observed_records(self):
        self.assertTrue(callable(self.tx.DiscardPrepared))
        self.send()
        self.assertFalse(self.tx.DiscardPrepared(self.tx)[0])
        self.tx.AcceptReply(self.tx, 1700000000000,
            lua_table(self.h.lua, {"ok": False, "code": "unknown_request"}))
        self.assertFalse(self.tx.DiscardPrepared(self.tx)[0])
        self.assertTrue(self.tx.AcceptReply(self.tx, 1700000000000, self.reply())[0])
        self.assertFalse(self.tx.DiscardPrepared(self.tx)[0])
        self.assertEqual(self.tx.Reconcile(self.tx,
            self.raw(5, 1700000005, home=True))[0], "observed")
        self.assertFalse(self.tx.DiscardPrepared(self.tx)[0])


if __name__ == "__main__":
    unittest.main()
