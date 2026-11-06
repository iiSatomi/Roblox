"""Actual bounded one-period rental, independent from earned payout and trades."""
import unittest
import test_market_payout_runtime as payout_fixture
from engine_harness import lua_table


class MarketRentRuntimeTests(payout_fixture.MarketPayoutRuntimeFixture,unittest.TestCase):

    def setUp(self):
        self.feature_id = 'marketRent'
        super().setUp()

    def choose(self):
        for key,value in (('marketRent.enabled',True),('marketRent.custom.maxAttempts',1),
                ('marketRent.custom.maxGoldSpend',2),('marketRent.custom.goldReserve',5)):
            self.assertTrue(self.app.Set(self.app,key,value)[0])
        self.app.Resume(self.app)

    def step(self,revision=1,shop_until=900,loose=10,bound=3,now=1001,**ignored):
        raw = self.h.snapshot(revision=revision,captured_at=revision,native={
            'fullSync':True,'serverNow':now,'level':30,'market':{'shopUntil':shop_until,'earnings':0},
            'derived':{'marketShop':False},'inventory':{'gold_bar':loose},'inventoryBound':{'gold_bar':bound}})
        raw.marketRentUsageProof = lua_table(self.h.lua,{'spent':0,'attempted':0}) # Caller proof must be discarded.
        self.h.at(raw.capturedAt)
        self.assertTrue(self.app.Step(self.app,raw)[0])
        return raw

    def test_off_default_then_four_argument_rental_confirms_exact_expiry_and_gold(self):
        self.step()
        self.assertEqual(len(self.executor.queued),0)
        self.choose()
        self.step(revision=2)
        self.executor.Drain(self.executor)
        call = self.executor.calls[1]
        self.assertEqual(call.remote,'MarketAction')
        self.assertEqual([call.args[i] for i in range(1,5)],['rent',1,None,None])
        self.assertEqual(call.args.n,4)
        self.step(revision=3,shop_until=44201,loose=8,now=1002)
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.marketRent,'confirmed')
        self.assertEqual(self.runtime.checkpoint.Allowance(self.runtime.checkpoint,'marketRent')[0].spent,2)

    def test_all_off_restart_observes_exact_saved_rental_without_another_call(self):
        self.choose()
        self.step()
        self.executor.Drain(self.executor)
        self.restart()
        self.step(revision=0,shop_until=44201,loose=8,now=1002)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.marketRent,'confirmed')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(len(self.executor.calls),1)

    def test_actual_bound_funded_rent_recovers_exact_native_combined_debit_without_replay(self):
        self.choose()
        self.step(loose=0,bound=10)
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),1)
        self.assertEqual([self.executor.calls[1].args[i] for i in range(1,5)],['rent',1,None,None])
        saved=self.runtime.checkpoint.Records(self.runtime.checkpoint,True)[1]
        self.assertEqual(saved.recovery.version,2)
        self.restart()
        self.step(revision=0,shop_until=44201,loose=0,bound=8,now=1002)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.marketRent,'confirmed')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(self.runtime.checkpoint.Allowance(self.runtime.checkpoint,'marketRent')[0].spent,2)
        self.assertEqual(len(self.executor.calls),1)

    def test_pending_and_changed_gold_remain_held_after_restart(self):
        self.choose()
        self.executor.reply = lua_table(self.h.lua,{'ok':False,'pending':True})
        self.step()
        self.executor.Drain(self.executor)
        self.restart()
        self.step(revision=0,shop_until=44201,loose=8,now=1002)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertEqual(len(self.executor.calls),1)

    def test_disable_before_dispatch_refunds_only_definitely_unsent_rental(self):
        self.choose()
        self.step()
        self.app.Set(self.app,'marketRent.enabled',False)
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),0)
        self.assertEqual(self.runtime.checkpoint.Allowance(self.runtime.checkpoint,'marketRent')[0].spent,0)

    def test_unknown_reload_cannot_reuse_zero_caller_usage_proof(self):
        self.choose()
        self.step()
        self.executor.Drain(self.executor)
        self.restart()
        self.choose()
        self.step(revision=0,shop_until=900,loose=10,now=1002)
        self.assertEqual(len(self.executor.calls),1)
        self.assertEqual(len(self.executor.queued),0)
        self.assertEqual(self.runtime.checkpoint.Allowance(self.runtime.checkpoint,'marketRent')[0].attempted,1)


    def test_zero_limits_never_schedule_but_explicit_budget_can_use_native_total_gold(self):
        self.app.Set(self.app,'marketRent.enabled',True)
        self.app.Resume(self.app)
        self.step()
        self.assertEqual(len(self.executor.queued),0)
        self.choose()
        self.step(revision=2,loose=0,bound=100)
        self.assertEqual(len(self.executor.queued),1)

    def test_confirmed_exposure_survives_restart_and_only_explicit_paused_reset_reopens_it(self):
        self.choose()
        self.step()
        self.executor.Drain(self.executor)
        self.step(revision=2,shop_until=44201,loose=8,now=1002)
        self.restart()
        self.choose()
        self.step(revision=0,shop_until=44201,loose=8,now=50000)
        self.assertEqual(len(self.executor.queued),0)
        self.assertIsNone(self.app.PreviewAllowance(self.app,'marketRent')[0])
        self.app.Pause(self.app)
        preview,why = self.app.PreviewAllowance(self.app,'marketRent')
        self.assertIsNone(why)
        self.assertEqual((preview.attempted,preview.spent),(1,2))
        self.assertTrue(self.app.ConfirmAllowance(self.app,'marketRent')[0])
        self.assertFalse(self.runtime.requested)
        self.assertEqual(self.runtime.checkpoint.Allowance(self.runtime.checkpoint,'marketRent')[0].spent,0)
        self.assertEqual(len(self.executor.calls),1)

    def test_same_gold_debit_with_wrong_expiry_or_bound_change_keeps_pending(self):
        self.choose()
        self.step()
        self.executor.Drain(self.executor)
        self.step(revision=2,shop_until=44201,loose=8,bound=2,now=1002)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.step(revision=3,shop_until=50000,loose=8,bound=3,now=1003)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertEqual(len(self.executor.calls),1)


    def test_two_eligible_rentals_use_absolute_cap_and_third_is_blocked(self):
        self.choose()
        self.app.Set(self.app,'marketRent.custom.maxAttempts',2)
        self.app.Set(self.app,'marketRent.custom.maxGoldSpend',4)
        self.step()
        self.executor.Drain(self.executor)
        self.step(revision=2,shop_until=44201,loose=8,now=1002)
        self.step(revision=4,shop_until=44201,loose=8,now=50000)
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),2)
        self.step(revision=5,shop_until=93200,loose=6,now=50001)
        allowance = self.runtime.checkpoint.Allowance(self.runtime.checkpoint,'marketRent')[0]
        self.assertEqual((allowance.attempted,allowance.spent),(2,4))
        self.step(revision=6,shop_until=93200,loose=6,now=100000)
        self.assertEqual(len(self.executor.queued),0)
        self.assertEqual(len(self.executor.calls),2)


if __name__ == '__main__': unittest.main()
