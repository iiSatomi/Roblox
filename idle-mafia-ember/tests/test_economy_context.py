"""Decree, Family exemption and quote arithmetic from saved client rules."""
import unittest

from engine_harness import Harness, lua_table


class EconomyContextTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        self.reader = self.h.load("src/game/EconomyContext.luau")

    def raw(self, family="other", ruler="ruling", shop=25,
            hire=10, market=15, discount=0.1, sale=0.2,
            revision=3):
        return self.h.snapshot(native={"fullSync": True, "serverNow": 2000000,
                                       "cityId": "city-a"},
            economyProof={"account": "user-a", "capturedAt": 0,
                "city": "city-a", "revision": revision,
                "familyId": family, "rulerId": ruler,
                "shopPct": shop, "hirePct": hire, "marketPct": market,
                "territoryShopDiscount": discount,
                "globalShopSale": sale})

    def view(self, raw):
        context, reason = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        return self.reader.read(raw, context)

    def test_normal_penalties_and_source_rounding(self):
        view, reason = self.view(self.raw())
        self.assertIsNone(reason)
        self.assertEqual(view["shopPct"], 25)
        self.assertEqual(self.reader.shopPrice(view, 1000), 900)
        self.assertEqual(self.reader.hireCost(view, 101), 111)
        self.assertEqual(self.reader.marketFee(view, 1000, False), 150)
        self.assertEqual(self.reader.marketFee(view, 1000, True), 105)
        self.assertEqual(self.reader.marketFee(view, 1, False), 1)

    def test_ruling_family_exempts_only_penalties(self):
        view, reason = self.view(self.raw(family="ruling", shop=25,
                                         hire=-20, market=15))
        self.assertIsNone(reason)
        self.assertEqual((view["shopPct"], view["hirePct"],
                          view["marketPct"]), (0, -20, 10))
        self.assertEqual(self.reader.shopPrice(view, 1000), 720)
        self.assertEqual(self.reader.hireCost(view, 100), 80)
        self.assertEqual(self.reader.marketFee(view, 1000, False), 100)

    def test_missing_stale_or_invalid_proof_fails_closed(self):
        bad = self.raw()
        bad["economyProof"]["familyId"] = None
        self.assertIsNone(self.view(bad)[0])
        bad = self.raw()
        bad["economyProof"]["capturedAt"] = 10
        self.assertIsNone(self.view(bad)[0])
        bad = self.raw(market=16)
        self.assertIsNone(self.view(bad)[0])
        bad = self.raw(discount=0.5)
        self.assertIsNone(self.view(bad)[0])
        bad = self.raw(sale=1.0)
        self.assertIsNone(self.view(bad)[0])

    def test_quote_key_changes_with_decree_or_family(self):
        first, _ = self.view(self.raw())
        changed, _ = self.view(self.raw(revision=4))
        family, _ = self.view(self.raw(family="ruling"))
        self.assertNotEqual(first["quoteKey"], changed["quoteKey"])
        self.assertNotEqual(first["quoteKey"], family["quoteKey"])

    def test_shared_context_marks_economy_known_or_unknown(self):
        context = self.h.load("src/game/Context.luau").new(
            self.h.contracts, self.reader)
        raw = self.raw()
        view, reason = context.Read(context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        self.assertEqual(view["economy"]["shopPct"], 25)
        bad = self.raw(market=16)
        view, reason = context.Read(context, bad,
            lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        self.assertEqual(view["economy"]["status"], "unknown")


if __name__ == "__main__":
    unittest.main()
