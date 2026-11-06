"""Shop purchase markers prove outcome despite later passive Cash, never its exact debit."""
import json
import unittest
from lupa import lua_type
import test_shop_cash as direct_fixture
import test_shop_cash_app as app_fixture
from engine_harness import lua_table


class ShopPassiveCashEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.f = direct_fixture.ShopCashTests()
        self.f.setUp()
        self.h, self.evidence = self.f.h, self.f.evidence

    def case(self, tracked=True, cash=1250.75):
        before = self.f.raw(cash=1000.25, tracked=tracked)
        for field in ('inventoryBound', 'collection', 'collectionBound'):
            before.native[field] = self.h.lua.table()
        view, reason = self.f.view(before)
        self.assertIsNone(reason)
        proposal, reason = self.f.planner.propose(view, self.f.settings(), self.h.lua.table())
        self.assertIsNone(reason)
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        after = self.f.raw(revision=2, owned=1, bought=1, cash=cash,
                           rotation_bought=True, tracked=tracked)
        after.native.serverNow = before.native.serverNow + 15.5
        for field in ('inventoryBound', 'collection', 'collectionBound'):
            after.native[field] = self.h.lua.table()
        return proposal, before, after, baseline

    def evaluate(self, case, reply=None):
        p, before, after, baseline = case
        return self.evidence.evaluate(p, before, after,
            lua_table(self.h.lua, {'ok': True} if reply is None else reply), baseline)

    def test_owned_purchase_marker_and_exact_grant_confirm_without_claiming_exact_cash_debit(self):
        for tracked in (True, False):
            for cash in (880.5, 1000.25, 1250.75, 1000000000.125):
                with self.subTest(tracked=tracked, cash=cash):
                    self.assertEqual(self.evaluate(self.case(tracked, cash)), 'confirmed')

    def test_passive_path_requires_later_valid_native_clock_and_noncontradictory_wallet(self):
        for field, value in (('serverNow', None), ('serverNow', 1220), ('serverNow', 1219),
                             ('serverNow', float('nan')), ('serverNow', float('inf')),
                             ('cash', 880), ('cash', -1), ('cash', float('nan')), ('cash', float('inf'))):
            with self.subTest(field=field, value=value):
                case = self.case()
                case[2].native[field] = value
                self.assertEqual(self.evaluate(case), 'pending')

    def test_passive_path_requires_every_item_origin_and_exact_purchase_identity(self):
        for change in ('noLooseGrant', 'extraLooseGrant', 'missingFlag', 'wrongSlot', 'missingLifetime',
                       'wrongLifetime', 'boundChanged', 'collectionChanged', 'collectionBoundChanged',
                       'missingBeforeBound', 'missingBeforeCollection', 'missingBeforeCollectionBound',
                       'partialSync', 'staleRevision'):
            with self.subTest(change=change):
                p, before, after, baseline = self.case()
                if change == 'noLooseGrant': after.native.inventory.w_a = 0
                elif change == 'extraLooseGrant': after.native.inventory.w_a = 2
                elif change == 'missingFlag': after.native.shopRotation.bought.w_a = None
                elif change == 'wrongSlot': after.native.shopRotation.slot = 3
                elif change == 'missingLifetime': after.native.shopBought = None
                elif change == 'wrongLifetime': after.native.shopBought.w_a = 2
                elif change == 'boundChanged': after.native.inventoryBound.w_a = 1
                elif change == 'collectionChanged': after.native.collection.w_a = 1
                elif change == 'collectionBoundChanged': after.native.collectionBound.w_a = 1
                elif change.startswith('missingBefore'):
                    field = {'missingBeforeBound': 'inventoryBound', 'missingBeforeCollection': 'collection',
                             'missingBeforeCollectionBound': 'collectionBound'}[change]
                    before.native[field] = None
                    baseline, reason = self.evidence.capture(p, before)
                    self.assertIsNone(reason)
                elif change == 'partialSync': after.native.fullSync = False
                elif change == 'staleRevision': after.revision = before.revision
                self.assertEqual(self.evaluate((p, before, after, baseline)), 'pending')

    def test_nonterminal_unknown_and_negative_replies_never_confirm_purchase_effects(self):
        for cash in (880.25, 1250.75):
            for reply in ({}, {'ok': False}, {'ok': True, 'pending': True},
                          {'ok': True, 'code': 'rate_limited'}, {'ok': True, 'code': 'presence'},
                          {'ok': True, 'code': 'busy'}):
                with self.subTest(cash=cash, reply=reply):
                    self.assertEqual(self.evaluate(self.case(cash=cash), reply), 'pending')

    def test_legacy_saved_baseline_uses_immutable_before_clock_without_retagging(self):
        p, before, after, baseline = self.case()
        baseline.serverNow = None
        data = lua_table(self.h.lua, {'proposal': p, 'before': before, 'baseline': baseline, 'reply': {'ok': True}})
        after.session = 'restarted'
        self.assertEqual(self.evidence.recoverSaved(data, after), 'confirmed')
        self.assertIsNone(data.baseline.serverNow)
        for invalid in (None, float('nan'), float('inf'), -1):
            with self.subTest(invalid=invalid):
                before.native.serverNow = invalid
                self.assertIsNone(self.evidence.recoverSaved(data, after))
        before.native.serverNow = 1220
        baseline.serverNow = 1219
        self.assertIsNone(self.evidence.recoverSaved(data, after))

    def test_existing_exact_cash_path_keeps_legacy_optional_origins_and_equal_clock(self):
        p, before, after, baseline = self.case(cash=880.25)
        before.native.inventoryBound = None
        baseline, reason = self.evidence.capture(p, before)
        self.assertIsNone(reason)
        after.native.serverNow = before.native.serverNow
        self.assertEqual(self.evaluate((p, before, after, baseline)), 'confirmed')


class ShopPassiveCashAppTests(unittest.TestCase):
    def setUp(self):
        self.f = app_fixture.ShopCashAppTests()
        self.f.setUp()
        self.f.set('shop.custom.limitTotal', True)
        self.f.set('shop.custom.maxSpend', 120)
        self.f.select('Single item')
        self.f.step()
        self.f.drain()
        self.assertEqual(len(self.f.executor.calls), 1)
        self.f.set('shop.enabled', False)

    def tearDown(self): self.f.tearDown()

    def assert_settled_without_replay(self, recovery=False):
        f = self.f
        status = f.runtime.Status(f.runtime)
        self.assertEqual((status.recoveries if recovery else status.outcomes).shop, 'confirmed')
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 0)
        self.assertEqual((f.allowance().attempted, f.allowance().spent), (1, 120))
        f.drain()
        self.assertEqual(len(f.executor.calls), 1)
        self.assertFalse(f.app.model['values']['shop.enabled'])

    def test_actual_app_settles_owned_positive_after_later_income_with_original_allowance(self):
        f = self.f
        f.h.at(15)
        f.step(f.raw(2, cash=1000000.25, bought=True))
        self.assert_settled_without_replay()

    def test_saved_positive_json_reload_recovers_same_original_evidence_and_quote(self):
        f = self.f
        key = f.runtime.checkpoint.ScopeKey(f.runtime.checkpoint)
        def plain(value):
            if lua_type(value) == 'table':
                keys = list(value.keys())
                if keys and set(keys) == set(range(1, len(keys) + 1)):
                    return [plain(value[index]) for index in range(1, len(keys) + 1)]
                return {key: plain(child) for key, child in value.items()}
            return value
        f.base.storage.data[key] = lua_table(f.h.lua, json.loads(json.dumps(plain(f.base.storage.data[key]))))
        f.restart()
        f.h.at(15)
        f.step(f.raw(0, cash=1000000.25, bought=True))
        # Restart creates a fresh offline executor; no recovery purchase is invoked.
        self.assertEqual(len(f.executor.calls), 0)
        status = f.runtime.Status(f.runtime)
        self.assertEqual(status.recoveries.shop, 'confirmed')
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 0)
        self.assertEqual((f.allowance().attempted, f.allowance().spent), (1, 120))
        self.assertFalse(f.app.model['values']['shop.enabled'])

    def test_saved_positive_contradictory_extra_loss_stays_held_without_new_send(self):
        f = self.f
        f.restart()
        f.h.at(15)
        f.step(f.raw(0, cash=879, bought=True))
        self.assertIsNone(f.runtime.Status(f.runtime).recoveries.shop)
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 1)
        self.assertEqual((f.allowance().attempted, f.allowance().spent), (1, 120))
        self.assertEqual(len(f.executor.calls), 0)
