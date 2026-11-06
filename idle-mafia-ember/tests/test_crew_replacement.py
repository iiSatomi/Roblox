"""One funded ordinary dismissal/hire; no native autoroll or uncertain replay."""
import unittest
from engine_harness import Harness, lua_table


class CrewReplacementTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.load_components()

    def load_components(self):
        self.module = self.h.load("src/tabs/crew/CrewReplacement.luau")
        self.config = lua_table(self.h.lua, {"CREW": {"hireTiers": [
            {"id": "street", "cost": 10000, "odds": [50, 30, 20, 0, 0, 0, 0, 0],
             "oddsLucky": [40, 30, 30, 0, 0, 0, 0, 0]}]}})
        self.source, reason = self.module.new(self.config, "a" * 64, "release-a")
        self.assertIsNone(reason)
        self.tx_module = self.h.load("src/tabs/crew/CrewReplacementTransactions.luau")
        self.storage = self.h.lua.execute("""return {data={},fail=false,
            Read=function(self,key) return self.data[key] end,
            Write=function(self,key,value) if self.fail then return false end; self.data[key]=value; return true end}""")
        self.scope = lua_table(self.h.lua, {**self.h.session, "ownerId": "replacement-a"})
        self.tx = self.restart()

    def restart(self):
        tx, reason = self.tx_module.new(self.storage, self.scope, self.source)
        self.assertIsNone(reason)
        return tx

    def raw(self, revision=1, stage="member", cash=50000, attempted=0, spent=0, session=None):
        target = {"name": "Recruit", "rarity": 1, "atk": 2, "def": 3, "train": 0}
        if stage == "empty": target = {}
        if stage == "hired": target = {"name": "New", "rarity": 2, "atk": 5, "def": 6, "train": 0}
        raw = self.h.snapshot(revision=revision, captured_at=revision, native={"fullSync": True,
            "serverNow": 1000 + revision, "cash": cash, "cityId": "city-a", "autoRolls": {},
            "derived": {"luckyHire": False}, "crew": [{"name": "Player"}, target,
                {"name": "Guard", "rarity": 4, "atk": 10, "def": 10}]})
        if session: raw.session = session
        header = {key: raw[key] for key in ("session", "account", "place", "release", "revision", "capturedAt")}
        raw.crewReplacementUsageProof = lua_table(self.h.lua, {**header, "attempted": attempted,
            "spent": spent, "controllersClear": True})
        raw.crewReplacementOwnerProof = lua_table(self.h.lua, {**header, "ownerId": "replacement-a", "slot": 2})
        raw.economyProof = lua_table(self.h.lua, {"account": raw.account, "capturedAt": raw.capturedAt,
            "revision": 7, "city": "city-a", "familyId": "", "rulerId": "", "hirePct": 0})
        return self.source.Enrich(self.source, raw)[0]

    def settings(self, **changes):
        values = dict(enabled=True, allowDismiss=True, slot=2, tier="street", targetRarity=3,
            maxDismissRarity=2, cashReserve=1000, minHome=1, maxCost=10000, maxSpend=10000, maxAttempts=1)
        values.update(changes)
        return lua_table(self.h.lua, values)

    def proposal(self, raw=None, **changes):
        raw = raw if raw is not None else self.raw()
        view, reason = self.source.read(raw, raw)
        self.assertIsNone(reason)
        proposal, reason = self.source.propose(view, self.settings(**changes))
        self.assertIsNone(reason)
        return proposal

    def prepare(self):
        before = self.raw()
        proposal = self.proposal(before)
        ok, reason = self.tx.PrepareDismiss(self.tx, proposal, before, 1)
        self.assertTrue(ok, reason)
        return proposal, before

    def dismissed(self):
        proposal, before = self.prepare()
        self.assertTrue(self.tx.MarkSending(self.tx, before, 1)[0])
        self.assertIsNotNone(self.tx.SubmitCall(self.tx, before, 1)[0])
        self.assertTrue(self.tx.AcceptReply(self.tx, proposal.actionKey, lua_table(self.h.lua, {"ok": True}))[0])
        after = self.raw(revision=2, stage="empty", attempted=1)
        self.assertTrue(self.tx.Reconcile(self.tx, after, 2)[0])
        return after

    def test_durable_cycle_usage_is_atomic_independent_and_cannot_be_forged_on_reload(self):
        self.assertEqual(dict(self.tx.Usage(self.tx).items()), {'attempted': 0, 'spent': 0})
        proposal, before = self.prepare()
        self.assertEqual(self.tx.Usage(self.tx).attempted, 1)
        recovered = self.restart()
        self.assertEqual((recovered.Usage(recovered).attempted, recovered.Usage(recovered).spent), (1, 0))
        self.assertTrue(self.tx.DiscardPrepared(self.tx)[0])
        self.assertEqual(self.tx.Usage(self.tx).attempted, 0)
        # An invented prior allowance cannot fund a new cycle.
        forged = self.raw(attempted=0, spent=1)
        self.assertFalse(self.tx.PrepareDismiss(self.tx, self.proposal(forged, maxSpend=20000), forged, 1)[0])

    def test_yielding_write_blocks_load_and_stale_owner_cannot_overwrite(self):
        self.h.lua.globals().crewYieldTx = self.tx
        self.h.lua.globals().crewYieldBefore = self.raw()
        self.h.lua.globals().crewYieldProposal = self.proposal()
        self.storage.Write = self.h.lua.eval("""function(self,key,value)
            coroutine.yield('saving'); self.data[key]=value; return true end """)
        self.h.lua.execute("crewWriter=coroutine.create(function() return crewYieldTx:PrepareDismiss(crewYieldProposal,crewYieldBefore,1) end)")
        self.assertTrue(self.h.lua.eval('coroutine.resume(crewWriter)')[0])
        owner, reason = self.tx_module.new(self.storage,self.scope,self.source)
        self.assertIsNone(owner)
        self.assertIn('in flight',reason)
        self.assertTrue(self.h.lua.eval('coroutine.resume(crewWriter)')[0])
        self.storage.Write = self.h.lua.eval('function(self,key,value) self.data[key]=value return true end')
        recovered = self.restart()
        self.assertTrue(self.tx.DiscardPrepared(self.tx)[0])
        self.assertFalse(recovered.DiscardPrepared(recovered)[0])
        self.assertEqual(self.restart().Usage(self.restart()).attempted,0)

    def test_closed_unsent_evidence_cannot_overwrite_or_authorize_a_newer_generation(self):
        proposal, before = self.prepare()
        self.assertTrue(self.tx.MarkSending(self.tx,before,1)[0])
        self.tx.Close(self.tx)
        newer = self.restart()
        self.assertTrue(newer.save(newer,newer.Active(newer))[0])
        generation = newer.generation
        main = self.source.Copy(self.storage.data[newer.key])
        self.assertTrue(self.tx.RecordAbandonedUnsent(self.tx,proposal.actionKey))
        self.assertTrue(self.source.Same(self.storage.data[newer.key],main))
        self.assertEqual(newer.generation,generation)
        self.assertFalse(newer.KnownUnsent(newer))
        self.assertFalse(newer.RecoverKnownUnsent(newer)[0])

    def test_unsent_evidence_is_exact_detached_and_cannot_cover_a_returned_call(self):
        proposal, before = self.prepare()
        self.assertTrue(self.tx.MarkSending(self.tx,before,1)[0])
        self.tx.Close(self.tx)
        self.assertTrue(self.tx.RecordAbandonedUnsent(self.tx,proposal.actionKey))
        recovered = self.restart()
        self.assertTrue(recovered.KnownUnsent(recovered))
        side_key = next(key for key in self.storage.data.keys() if ':adapter-unsent:' in key)
        original = self.source.Copy(self.storage.data[side_key])
        self.storage.data[side_key].baseline.before.native.cash = 1
        self.assertFalse(recovered.KnownUnsent(recovered))
        self.storage.data[side_key] = original
        self.assertTrue(recovered.KnownUnsent(recovered))
        self.assertTrue(recovered.AcceptReply(recovered,proposal.actionKey,lua_table(self.h.lua,{'ok':True}))[0])
        self.assertFalse(recovered.KnownUnsent(recovered))
        self.assertFalse(recovered.RecordAbandonedUnsent(recovered,proposal.actionKey))

    def test_funded_flat_dismiss_and_ordinary_exact_signature(self):
        before = self.raw()
        proposal = self.proposal(before)
        self.assertEqual(proposal.feature, "crewRoll")
        self.assertEqual(proposal.intent.kind, "crewReplacementDismiss")
        self.assertEqual(dict(proposal.resources.items()), {})
        call, reason = self.module.describe(proposal)
        self.assertIsNone(reason)
        self.assertEqual((call.remote, call.arity, call.args[1], call.args[2]), ("CrewAction", 4, "dismiss", 2))
        self.assertIsNotNone(self.source.capture(proposal, before)[0])

    def test_defaults_funding_protections_and_missing_proofs_block(self):
        for change in (dict(allowDismiss=False), dict(maxCost=0), dict(maxSpend=0), dict(maxAttempts=0),
                       dict(targetRarity=8), dict(minHome=2), dict(cashReserve=45000)):
            raw = self.raw()
            self.assertIsNone(self.source.propose(self.source.read(raw, raw)[0], self.settings(**change))[0])
        for field, value in (("weapon", "w_baton"), ("train", 1), ("duty", "district-a"),
                             ("injuredUntil", 2000), ("rolling", True), ("training", {})):
            raw = self.raw(); raw.native.crew[2][field] = lua_table(self.h.lua, value)
            view = self.source.read(raw, raw)[0]
            self.assertTrue(view is None or self.source.propose(view, self.settings())[0] is None, field)
        for field in ("crewReplacementUsageProof", "crewReplacementOwnerProof"):
            raw = self.raw(); raw[field] = None
            self.assertIsNone(self.source.propose(self.source.read(raw, raw)[0], self.settings())[0])
        raw = self.raw(); raw.native.crew[3] = self.h.lua.table()
        self.assertIsNone(self.source.propose(self.source.read(raw, raw)[0], self.settings())[0])

    def test_persist_before_send_single_emission_restart_no_submit_and_stale_preflight(self):
        proposal, before = self.prepare()
        self.assertIsNone(self.tx.SubmitCall(self.tx, before, 1)[0])
        self.assertTrue(self.tx.MarkSending(self.tx, before, 1)[0])
        recovered = self.restart()
        self.assertIsNone(recovered.SubmitCall(recovered, before, 1)[0])
        call = self.tx.SubmitCall(self.tx, before, 1)[0]
        self.assertEqual(call.args[1], "dismiss")
        self.assertIsNone(self.tx.SubmitCall(self.tx, before, 1)[0])
        self.assertFalse(self.tx.AcceptReply(self.tx, "wrong", lua_table(self.h.lua, {"ok": True}))[0])
        self.tx.Close(self.tx)
        self.assertFalse(self.tx.AcceptReply(self.tx, proposal.actionKey, lua_table(self.h.lua, {"ok": True}))[0])

    def test_full_durable_cycle_exact_cash_reply_member_and_retained_empty(self):
        empty = self.dismissed()
        self.assertFalse(self.tx.ClearObserved(self.tx)[0])
        self.tx = self.restart()
        proposal, reason = self.tx.PrepareHire(self.tx, empty, 2)
        self.assertIsNone(reason)
        self.assertEqual(proposal.intent.kind, "crewReplacementHire")
        self.assertTrue(self.tx.MarkSending(self.tx, empty, 2)[0])
        call = self.tx.SubmitCall(self.tx, empty, 2)[0]
        self.assertEqual((call.args[1], call.args[2], call.args[3], call.arity), ("hire", "street", 10000, 4))
        reply = lua_table(self.h.lua, {"ok": True, "member": {"name": "New", "rarity": 2, "atk": 5, "def": 6}})
        self.assertTrue(self.tx.AcceptReply(self.tx, proposal.actionKey, reply)[0])
        after = self.raw(revision=3, stage="hired", cash=40000, attempted=1, spent=10000)
        self.assertTrue(self.tx.Reconcile(self.tx, after, 3)[0])
        recovered = self.restart()
        self.assertEqual(recovered.Active(recovered).stage, "observedMember")
        self.assertTrue(self.tx.ClearObserved(self.tx)[0])
        self.assertEqual((self.tx.Usage(self.tx).attempted, self.tx.Usage(self.tx).spent), (1, 10000))
        self.assertEqual(self.restart().Usage(self.restart()).spent, 10000)

    def test_failed_persistence_preserves_prepared_and_sent_custody(self):
        before = self.raw(); proposal = self.proposal(before)
        self.storage.fail = True
        self.assertFalse(self.tx.PrepareDismiss(self.tx, proposal, before, 1)[0])
        self.assertIsNone(self.tx.Active(self.tx))
        self.storage.fail = False; self.prepare()
        self.storage.fail = True
        self.assertFalse(self.tx.MarkSending(self.tx, before, 1)[0])
        self.assertEqual(self.tx.Active(self.tx).stage, "preparedDismiss")
        self.assertIsNone(self.tx.SubmitCall(self.tx, before, 1)[0])
        self.assertFalse(self.tx.DiscardPrepared(self.tx)[0])
        self.storage.fail = False
        self.assertTrue(self.tx.DiscardPrepared(self.tx)[0])
        recovered = self.restart()
        self.assertIsNone(recovered.Active(recovered))

    def test_large_unrelated_inventory_absent_native_controller_and_detached_records(self):
        raw = self.raw()
        raw.native.inventory = lua_table(self.h.lua, {f"item_{i}": 1 for i in range(1000)})
        raw.native.autoRolls = None
        enriched, reason = self.source.Enrich(self.source, raw)
        self.assertIsNone(reason)
        self.assertEqual(len(list(enriched.native.inventory.items())), 1000)
        proposal = self.proposal(enriched)
        self.assertTrue(self.tx.PrepareDismiss(self.tx, proposal, enriched, 1)[0])
        self.assertIsNone(self.tx.Active(self.tx).baseline.before.native.inventory)
        active = self.tx.Active(self.tx)
        active.baseline.before.native.crew[2].name = "Edited"
        proposal.intent.cost = 1
        enriched.native.crew[2].atk = 99
        recovered = self.restart()
        self.assertEqual(recovered.Active(recovered).baseline.before.native.crew[2].name, "Recruit")
        self.assertEqual(recovered.Active(recovered).proposal.intent.cost, 10000)
        self.assertFalse(recovered.MarkSending(recovered, self.raw(), 1)[0])
        for malformed in (False, "none", {"2": {"rolls": 0}}):
            current = self.raw(); current.native.autoRolls = lua_table(self.h.lua, malformed)
            self.assertIsNone(self.source.read(current, current)[0])

    def test_source_and_usage_owner_corruption_or_malformed_records_fail_closed(self):
        for field, key, value in (("crewReplacementUsageProof", "revision", 9),
                ("crewReplacementUsageProof", "attempted", "0"),
                ("crewReplacementUsageProof", "controllersClear", False),
                ("crewReplacementOwnerProof", "slot", 3),
                ("crewReplacementOwnerProof", "session", "old")):
            raw = self.raw(); raw[field][key] = value
            self.assertIsNone(self.source.propose(self.source.read(raw, raw)[0], self.settings())[0])
        self.prepare()
        key = next(iter(self.storage.data.keys()))
        for mutation in ("stage", "intent", "cycle", "oversized"):
            original = self.source.Copy(self.storage.data[key])
            active = self.storage.data[key].active
            if mutation == "stage": active.stage = "unknown"
            elif mutation == "intent": active.proposal.intent.cost = 1
            elif mutation == "cycle": active.baseline.before.loop = active.baseline.before
            else: active.baseline.before.native.crew[2].name = "x" * 33000
            recovered, reason = self.tx_module.new(self.storage, self.scope, self.source)
            self.assertIsNone(recovered, mutation)
            self.assertIsNotNone(reason)
            self.storage.data[key] = original

    def test_failed_submit_consumes_arm_but_stale_callback_cannot_disarm_new_stage(self):
        proposal, before = self.prepare()
        self.assertTrue(self.tx.MarkSending(self.tx, before, 1)[0])
        changed = self.raw(); changed.native.crew[2].name = "Other"
        self.assertIsNone(self.tx.SubmitCall(self.tx, changed, 1)[0])
        self.assertIsNone(self.tx.SubmitCall(self.tx, before, 1)[0])
        self.assertTrue(self.tx.AcceptReply(self.tx, proposal.actionKey, lua_table(self.h.lua, {"ok": True}))[0])
        empty = self.raw(revision=2, stage="empty", attempted=1)
        self.assertTrue(self.tx.Reconcile(self.tx, empty, 2)[0])
        hire = self.tx.PrepareHire(self.tx, empty, 2)[0]
        self.assertTrue(self.tx.MarkSending(self.tx, empty, 2)[0])
        self.assertFalse(self.tx.AcceptReply(self.tx, proposal.actionKey, lua_table(self.h.lua, {"ok": True}))[0])
        call = self.tx.SubmitCall(self.tx, empty, 2)[0]
        self.assertIsNotNone(call)
        self.assertEqual(call.args[1], "hire")
        self.assertEqual(self.tx.Active(self.tx).proposal.actionKey, hire.actionKey)

    def test_intermediate_recovery_preserves_original_proof_and_holds_manual_changes(self):
        empty = self.dismissed()
        for drift in ("target", "other", "quote", "usage", "owner", "stale"):
            current = self.raw(revision=3, stage="empty", attempted=1)
            if drift == "target": current.native.crew[2].name = "Manual"
            elif drift == "other": current.native.crew[3].atk = 11
            elif drift == "quote": current.economyProof.hirePct = 1
            elif drift == "usage": current.crewReplacementUsageProof.spent = 1
            elif drift == "owner": current.crewReplacementOwnerProof.ownerId = "other"
            self.assertIsNone(self.tx.PrepareHire(self.tx, current, 20 if drift == "stale" else 3)[0], drift)
        proposal = self.tx.PrepareHire(self.tx, empty, 2)[0]
        recovered = self.restart()
        self.assertEqual(recovered.Active(recovered).dismissal.baseline.before.native.crew[2].name, "Recruit")
        self.assertFalse(recovered.MarkSending(recovered, empty, 2)[0])
        self.assertFalse(recovered.DiscardPrepared(recovered)[0])
        self.assertFalse(recovered.ClearObserved(recovered)[0])
        self.assertEqual(recovered.Active(recovered).proposal.actionKey, proposal.actionKey)

    def test_optional_real_heal_id_fences_same_name_stat_replacement_and_policy(self):
        raw = self.raw(); raw.native.crew[2].healId = "member-a"
        proposal = self.proposal(raw)
        raw.native.crew[2].healId = "member-b"
        self.assertIsNone(self.source.capture(proposal, raw)[0])
        current = self.raw()
        self.assertIsNone(self.source.propose(self.source.read(current, current)[0],
            self.settings(policy="Native autoroll"))[0])
        self.assertIsNotNone(self.source.propose(self.source.read(current, current)[0],
            self.settings(policy="Bounded replacement"))[0])

    def test_failed_reply_or_observation_writes_and_close_preserve_sent_record(self):
        proposal, before = self.prepare()
        self.tx.MarkSending(self.tx, before, 1)
        self.tx.SubmitCall(self.tx, before, 1)
        self.storage.fail = True
        self.assertFalse(self.tx.AcceptReply(self.tx, proposal.actionKey, lua_table(self.h.lua, {"ok": True}))[0])
        self.assertIsNone(self.tx.Active(self.tx).reply)
        self.storage.fail = False
        self.tx.AcceptReply(self.tx, proposal.actionKey, lua_table(self.h.lua, {"ok": True}))
        self.storage.fail = True
        self.assertFalse(self.tx.Reconcile(self.tx, self.raw(revision=2, stage="empty", attempted=1), 2)[0])
        self.assertEqual(self.tx.Active(self.tx).stage, "sentDismiss")
        self.storage.fail = False
        self.tx.Close(self.tx)
        self.assertFalse(self.tx.Reconcile(self.tx, self.raw(revision=2, stage="empty", attempted=1), 2)[0])
        self.assertFalse(self.tx.DiscardPrepared(self.tx)[0])

    def test_unknown_restart_cannot_replay_or_infer_success_from_empty(self):
        proposal, before = self.prepare()
        self.tx.MarkSending(self.tx, before, 1)
        self.tx = self.restart()
        empty = self.raw(revision=2, stage="empty", attempted=1, session="restart")
        self.assertFalse(self.tx.Reconcile(self.tx, empty, 2)[0])
        self.assertFalse(self.tx.DiscardPrepared(self.tx)[0])
        self.assertIsNone(self.tx.SubmitCall(self.tx, empty, 2)[0])
        self.assertTrue(self.tx.AcceptReply(self.tx, proposal.actionKey, lua_table(self.h.lua, {"ok": True}))[0])
        self.assertTrue(self.tx.Reconcile(self.tx, empty, 2)[0])

    def test_duplicate_fallback_target_manual_change_and_old_capture_rejected(self):
        raw = self.raw(); raw.native.crew[3] = lua_table(self.h.lua, dict(raw.native.crew[2].items()))
        self.assertIsNone(self.source.propose(self.source.read(raw, raw)[0], self.settings())[0])
        proposal, before = self.prepare()
        before.native.crew[2].atk = 3
        self.assertFalse(self.tx.MarkSending(self.tx, before, 1)[0])
        self.assertFalse(self.tx.MarkSending(self.tx, self.raw(), 20)[0])
        self.assertTrue(self.tx.DiscardPrepared(self.tx)[0])

    def test_hire_cannot_confirm_wrong_cash_reply_index_or_missing_member(self):
        empty = self.dismissed()
        proposal = self.tx.PrepareHire(self.tx, empty, 2)[0]
        baseline = self.source.capture(proposal, empty)[0]
        for reply in ({"ok": True}, {"ok": True, "index": 3, "member": {"name": "New", "rarity": 2, "atk": 5, "def": 6}},
                      {"ok": True, "pending": True, "member": {"name": "New", "rarity": 2, "atk": 5, "def": 6}}):
            after = self.raw(revision=3, stage="hired", cash=40000, attempted=1)
            self.assertEqual(self.source.evaluate(proposal, empty, after, lua_table(self.h.lua, reply), baseline), "pending")
        after = self.raw(revision=3, stage="hired", cash=50000, attempted=1)
        self.assertEqual(self.source.evaluate(proposal, empty, after,
            lua_table(self.h.lua, {"ok": True, "member": {"name": "New", "rarity": 2, "atk": 5, "def": 6}}), baseline), "pending")


if __name__ == "__main__": unittest.main()
