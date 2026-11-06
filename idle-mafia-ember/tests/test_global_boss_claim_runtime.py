"""Actual settled Global Boss claim and observed native award effects."""
import unittest
import test_global_boss_attack_runtime as fixture
from engine_harness import lua_table

class GlobalBossClaimRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.g=fixture.GlobalBossAttackRuntimeTests();self.g.setUp();self.f=self.g.f;self.h=self.g.h
        self.f.app.Destroy(self.f.app);self.f.feature_id='globalBossClaim'
        self.h.lua.globals().globalEvent.status='done';self.h.lua.globals().globalEvent.resultAt=2000050
        self.f.executor.reply=lua_table(self.h.lua,{'ok':True,'medals':2,'won':[{'i':'crate_loot','n':2}]})
        self.f.start_current()
    def tearDown(self):self.f.tearDown()
    def raw(self,revision=1,claimed=False,medals=1,crates=3,now=2000100,damage=50):
        raw=self.g.raw(revision,now=now,damage=damage);raw.native.gb.claimed=claimed
        if claimed:raw.native.gb.medals=2;raw.native.gb.won=lua_table(self.h.lua,[{'i':'crate_loot','n':2}])
        raw.native.inventory=lua_table(self.h.lua,{'crate_loot':crates})
        raw.native.inventoryBound=lua_table(self.h.lua,{'event_medal':medals})
        raw.native.paidMedals=0
        return raw
    def step(self,revision=1,**kw):
        raw=self.raw(revision,**kw);self.f.app.Step(self.f.app,raw);return raw
    def choose(self):self.f.app.Set(self.f.app,'globalBossClaim.enabled',True);self.f.app.Resume(self.f.app)
    def begin(self):
        self.choose();self.step();self.f.drain()
        self.assertEqual(len(self.f.executor.calls),1,str(dict(self.f.runtime.Status(self.f.runtime).reasons.items())))
    def test_exact_result_awards_and_native_one_argument_call(self):
        self.begin();call=self.f.executor.calls[1]
        self.assertEqual(call.remote,'GlobalBossAction');self.assertEqual(call.args.n,1);self.assertEqual(call.args[1],'claim')
        self.h.at(1);self.step(2,claimed=True,medals=3,crates=5,now=2000101)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.globalBossClaim,'confirmed')
    def test_fractional_participation_claims_once_and_recovers_the_same_exact_damage(self):
        self.choose(); self.step(damage=50.5); self.f.drain()
        self.assertEqual(len(self.f.executor.calls), 1,
                         str(dict(self.f.runtime.Status(self.f.runtime).reasons.items())))
        call = self.f.executor.calls[1]
        self.assertEqual((call.remote, call.args.n, call.args[1]), ('GlobalBossAction', 1, 'claim'))
        records = self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)
        data = self.f.runtime.checkpoint.Recovery(self.f.runtime.checkpoint, records[1].actionKey)[0]
        self.assertEqual(data.baseline.mineDamage, 50.5)
        self.assertEqual(self.f.runtime.checkpoint.globalClaimUsage.attempts, 1)
        import json
        from test_redundant_store import plain
        for key, saved in list(self.f.storage.data.items()):
            self.f.storage.data[key] = lua_table(self.h.lua, json.loads(json.dumps(plain(saved))))
        self.f.restart()
        self.step(0, claimed=True, medals=3, crates=5, damage=50.625, now=2000105)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)), 1)
        self.h.at(1)
        self.step(1, claimed=True, medals=3, crates=5, damage=50.5, now=2000106)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.globalBossClaim, 'confirmed')
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)), 0)
        self.assertEqual(len(self.f.executor.calls), 1)
        self.assertEqual(self.f.runtime.checkpoint.globalClaimUsage.attempts, 1)

    def test_claimed_marker_without_awards_is_not_success(self):
        self.begin();self.h.at(1);self.step(2,claimed=True,now=2000101)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.globalBossClaim)
    def test_missing_returned_award_list_is_uncertain(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':True});self.begin();self.h.at(1)
        self.step(2,claimed=True,medals=3,crates=5,now=2000101)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.globalBossClaim)
    def test_pending_reply_with_all_awards_does_not_confirm(self):
        self.f.executor.reply.pending=True;self.begin();self.h.at(1)
        self.step(2,claimed=True,medals=3,crates=5,now=2000101)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.globalBossClaim)
    def test_saved_claim_recovers_exact_awards_without_replaying(self):
        self.begin();self.f.restart();self.step(0,claimed=True,medals=3,crates=5,now=2000105)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.globalBossClaim,'confirmed')
        self.assertEqual(len(self.f.executor.calls),1)
    def test_run_or_private_access_change_after_queue_blocks_emit(self):
        self.choose();self.step();self.h.lua.globals().globalEvent.testUserId=99;self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
    def test_negative_with_medal_credit_stays_uncertain(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':False});self.begin();self.h.at(1)
        self.step(2,medals=3,now=2000101)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.globalBossClaim)
    def test_queued_disable_does_not_consume_run_attempt(self):
        self.choose();self.step();self.f.app.Set(self.f.app,'globalBossClaim.enabled',False);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
        self.assertEqual(self.f.runtime.checkpoint.globalClaimUsage.attempts,0)
    def test_native_won_list_must_match_returned_awards(self):
        self.begin();self.h.at(1);raw=self.raw(2,claimed=True,medals=3,crates=5,now=2000101)
        raw.native.gb.won=lua_table(self.h.lua,[{'i':'different_item','n':2}]);self.f.app.Step(self.f.app,raw)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.globalBossClaim)
    def test_paid_medal_change_cannot_prove_earned_award(self):
        self.begin();self.h.at(1);raw=self.raw(2,claimed=True,medals=3,crates=5,now=2000101)
        raw.native.paidMedals=2;self.f.app.Step(self.f.app,raw)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.globalBossClaim)

    def test_alternating_runs_cannot_reset_claim_attempt(self):
        self.begin();self.h.at(1);self.step(2,claimed=True,medals=3,crates=5,now=2000101)
        self.h.lua.globals().globalEvent.id='judge';self.h.at(2)
        raw=self.raw(3,medals=3,crates=5,now=2000102);raw.native.gb.run='judge_2000000'
        self.f.app.Step(self.f.app,raw);self.f.drain()
        self.h.at(3);raw=self.raw(4,claimed=True,medals=5,crates=7,now=2000103);raw.native.gb.run='judge_2000000'
        self.f.app.Step(self.f.app,raw)
        self.h.lua.globals().globalEvent.id='hellfire';self.h.at(4)
        self.step(5,medals=5,crates=7,now=2000104);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),2)
        self.f.restart()
        self.assertEqual(self.f.runtime.checkpoint.GlobalClaimUsage(self.f.runtime.checkpoint,'hellfire_2000000',0).attempts,1)

    def test_zero_random_drops_still_requires_exact_participation_medals(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':True,'medals':2,'won':[]});self.begin();self.h.at(1)
        raw=self.raw(2,claimed=True,medals=3,crates=3,now=2000101);raw.native.gb.won=self.h.lua.table()
        self.f.app.Step(self.f.app,raw)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.globalBossClaim,'confirmed')
    def test_exact_negative_keeps_run_attempt(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':False});self.begin();self.h.at(1);self.step(2,now=2000101)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.globalBossClaim,'rejected')
        self.assertEqual(self.f.runtime.checkpoint.globalClaimUsage.attempts,1)
    def test_saved_exact_negative_recovers_without_replay(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':False});self.begin();self.f.restart();self.step(0,now=2000105)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.globalBossClaim,'rejected')
        self.assertEqual(len(self.f.executor.calls),1)
    def test_unload_before_invoke_recovers_only_exact_unsent_attempt(self):
        self.choose();self.step();self.f.app.Destroy(self.f.app);self.f.drain();self.f.restart();self.step(0,now=2000105)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.globalBossClaim,'known_unsent')
        self.assertEqual(self.f.runtime.checkpoint.globalClaimUsage.attempts,0)
        self.assertEqual(len(self.f.executor.calls),0)
    def test_timeout_retains_award_custody_and_attempt(self):
        self.f.executor.reply.pending=True;self.begin();self.h.at(45);raw=self.step(2,now=2000145)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.globalBossClaim,'skipped_unconfirmed')
        self.assertTrue(self.f.runtime.reservationOwner.Held(self.f.runtime.reservationOwner,raw)[0].allItems)
        self.assertEqual(self.f.runtime.checkpoint.globalClaimUsage.attempts,1)
    def test_stale_negative_cannot_release_original_attempt(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':False});self.begin();self.step()
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.globalBossClaim)
    def test_extra_inventory_change_stays_uncertain(self):
        self.begin();self.h.at(1);raw=self.raw(2,claimed=True,medals=3,crates=5,now=2000101)
        raw.native.inventory.unrelated=1;self.f.app.Step(self.f.app,raw)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.globalBossClaim)
    def test_loose_participation_medals_do_not_prove_bound_award(self):
        self.begin();self.h.at(1);raw=self.raw(2,claimed=True,crates=5,now=2000101)
        raw.native.inventory.event_medal=2;self.f.app.Step(self.f.app,raw)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.globalBossClaim)
    def test_sparse_returned_winnings_cannot_confirm(self):
        self.f.executor.reply.won[3]=self.f.executor.reply.won[1];self.f.executor.reply.won[1]=None
        self.begin();self.h.at(1);self.step(2,claimed=True,medals=3,crates=5,now=2000101)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.globalBossClaim)
    def test_missing_attribute_decode_cannot_reuse_caller_proofs(self):
        self.choose();self.h.lua.globals().globalAttributes.GlobalBossState='invalid';self.step();self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
    def test_expired_claim_window_cannot_emit(self):
        self.choose();self.step(now=2604850);self.f.drain();self.assertEqual(len(self.f.executor.calls),0)
