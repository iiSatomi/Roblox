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
            on=False, slot=4):
        raw = self.h.snapshot(revision=revision,
            native={"fullSync": True, "level": 10, "cash": cash,
                "serverNow": slot * 300 + 20,
                "inventory": {"w_a": owned},
                "shopBought": {"w_a": bought},
                "shopRotation": {"slot": slot, "bought": {}},
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
        after = self.raw(revision=2, owned=1, bought=1)
        self.assertEqual(self.evidence.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "confirmed")

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


if __name__ == "__main__":
    unittest.main()
