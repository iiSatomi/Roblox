"""Cash-only Shop quote, rotation, native owner and item custody."""
import unittest

from engine_harness import Harness, lua_table


class ShopCashTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.catalog = self.h.load("src/tabs/shop/NativeShopCatalog.luau").new(
            lua_table(self.h.lua, {"SHOP": [
                {"item": "w_a", "price": 100,
                 "priceMax": 150, "limit": 2},
                {"item": "w_gold", "goldPrice": 5}],
                "ITEMS_BY_ID": {"w_a": {"kind": "weapon", "rarity": 1},
                    "w_gold": {"kind": "weapon", "rarity": 2}}}),
            "a" * 64, "release-a")
        self.reader = self.h.load("src/game/ShopState.luau")
        self.planner = self.h.load("src/features/ShopBuy.luau")
        self.evidence = self.h.load("src/features/ShopBuyEvidence.luau")
        self.context = self.h.load("src/game/Context.luau").new(
            self.h.contracts)

    def raw(self, revision=1, owned=0, bought=0, cash=1000,
            on=False, slot=4, tracked=True, rotation_bought=False):
        raw = self.h.snapshot(revision=revision,
            native={"fullSync": True, "level": 10, "cash": cash,
                "serverNow": slot * 300 + 20,
                "inventory": {"w_a": owned},
                "shopBought": {"w_a": bought} if tracked else None,
                "shopRotation": {"slot": slot,
                    "bought": {"w_a": True} if rotation_bought else {}},
                "autoBuyRules": {"on": on}},
            shopQuoteProof={**self.h.session, "revision": revision,
                "capturedAt": 0, "catalogKey": "a" * 64,
                "slot": slot, "stock": {"w_a": True},
                "quotes": {"w_a": 120}})
        return self.catalog.Enrich(self.catalog, raw)[0]

    def view(self, raw):
        context = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        return self.reader.read(raw, context)

    def settings(self, reserve=100):
        return lua_table(self.h.lua, {"enabled": True, "itemId": "w_a",
            "cashReserve": reserve, "purchaseCap": 200})

    def test_selected_cash_offer_and_exact_grant(self):
        before = self.raw()
        view, reason = self.view(before)
        self.assertIsNone(reason)
        self.assertIsNone(view["offers"]["w_gold"])
        proposal, reason = self.planner.propose(view, self.settings(),
            lua_table(self.h.lua, {"cash": 0, "uncertainCash": 0}))
        self.assertIsNone(reason)
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        after = self.raw(revision=2, owned=1, bought=1, cash=880,
                         rotation_bought=True)
        self.assertEqual(self.evidence.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "confirmed")

    def test_current_sync_without_shop_bought_uses_rotation_and_grant(self):
        before = self.raw(tracked=False)
        view, reason = self.view(before)
        self.assertIsNone(reason)
        proposal, reason = self.planner.propose(view, self.settings(),
            lua_table(self.h.lua, {"cash": 0, "uncertainCash": 0}))
        self.assertIsNone(reason)
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        after = self.raw(revision=2, owned=1, tracked=False, cash=880,
                         rotation_bought=True)
        reply = lua_table(self.h.lua, {"ok": True})
        self.assertEqual(self.evidence.evaluate(proposal, before, after,
            reply, baseline), "confirmed")
        after["native"]["shopRotation"]["bought"]["w_a"] = None
        self.assertEqual(self.evidence.evaluate(proposal, before, after,
            reply, baseline), "pending")
        after["native"]["shopRotation"]["bought"]["w_a"] = True
        after["native"]["inventory"]["w_a"] = 0
        self.assertEqual(self.evidence.evaluate(proposal, before, after,
            reply, baseline), "pending")
        after["native"]["inventory"]["w_a"] = 1
        after["native"]["shopRotation"]["slot"] = 5
        self.assertEqual(self.evidence.evaluate(proposal, before, after,
            reply, baseline), "pending")
        after["native"]["shopRotation"]["slot"] = 4
        after["native"]["shopBought"] = 5
        self.assertEqual(self.evidence.evaluate(proposal, before, after,
            reply, baseline), "pending")

    def test_native_owner_rotation_and_missing_quote_block(self):
        view, _ = self.view(self.raw(on=True))
        self.assertIsNone(self.planner.propose(view, self.settings(),
            lua_table(self.h.lua, {}))[0])
        raw = self.raw()
        raw["shopQuoteProof"]["quotes"]["w_a"] = None
        self.assertIsNone(self.view(raw)[0])
        raw = self.raw()
        raw["native"]["serverNow"] = 1501
        self.assertIsNone(self.view(raw)[0])

    def test_fractional_native_cash_does_not_block_exact_cash_quote(self):
        before = self.raw(cash=1000.25, tracked=False)
        view, reason = self.view(before)
        self.assertIsNone(reason)
        proposal, reason = self.planner.propose(view, self.settings(),
            lua_table(self.h.lua, {"cash": 0, "uncertainCash": 0}))
        self.assertIsNone(reason)
        self.assertIsNotNone(self.evidence.capture(proposal, before)[0])

    def test_fractional_native_clock_keeps_quote_eligible(self):
        before = self.raw()
        before["native"]["serverNow"] += 0.25
        view, reason = self.view(before)
        self.assertIsNone(reason)
        proposal, reason = self.planner.propose(view, self.settings(),
            lua_table(self.h.lua, {}))
        self.assertIsNone(reason)
        self.assertIsNotNone(self.evidence.capture(proposal, before)[0])

    def test_grant_without_exact_cash_debit_does_not_confirm(self):
        before = self.raw()
        view, _ = self.view(before)
        proposal, _ = self.planner.propose(view, self.settings(),
            lua_table(self.h.lua, {}))
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        after = self.raw(revision=2, owned=1, bought=1,
                         rotation_bought=True)
        self.assertEqual(self.evidence.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "pending")

    def test_preflight_rechecks_quote_and_reserve(self):
        before = self.raw()
        view, _ = self.view(before)
        proposal, _ = self.planner.propose(view, self.settings(),
            lua_table(self.h.lua, {}))
        before["shopQuoteProof"]["quotes"]["w_a"] = 121
        self.assertIsNone(self.evidence.capture(proposal, before)[0])
        before["shopQuoteProof"]["quotes"]["w_a"] = 120
        before["native"]["cash"] = 200
        self.assertIsNone(self.evidence.capture(proposal, before)[0])
        before = self.raw()
        view, _ = self.view(before)
        proposal, _ = self.planner.propose(view, self.settings(),
            lua_table(self.h.lua, {}))
        before["shopCatalog"] = None
        self.assertIsNone(self.evidence.capture(proposal, before)[0])


if __name__ == "__main__":
    unittest.main()
