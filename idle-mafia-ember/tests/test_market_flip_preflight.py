"""A hypothetical flip purchase must pass current Gold and shop guards."""
import unittest

from engine_harness import Harness, lua_table


class MarketFlipPreflightTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.preflight = self.h.load(
            "src/tabs/blackMarket/MarketFlipPreflight.luau")

    def inputs(self):
        quote = {"hypothetical": True, "listingId": "L1",
            "itemId": "w_baton", "kind": "weapon",
            "rarity": 5, "buy": 8, "ask": 13,
            "margin": 3, "capturedAt": 10}
        header = {"session": "s", "account": "a", "place": "p",
                  "release": "r", "revision": 4, "capturedAt": 10}
        raw = dict(header, native={"fullSync": True,
            "level": 50, "serverNow": 1000.5,
            "derived": {"marketShop": False},
            "inventory": {"gold_bar": 20},
            "inventoryBound": {"gold_bar": 2},
            "market": {"shopUntil": 2000, "listings": {}}})
        terms = {"release": "r", "minLevel": 20,
                 "maxSlots": 5}
        budget = {"maxBuy": 10, "sessionBudget": 20,
            "goldReserve": 5, "maxAttempts": 2,
            "transactionOpen": False,
            "blockedItems": {}, "blockedKinds": {},
            "blockedRarities": {}}
        return [lua_table(self.h.lua, x) for x in
                (quote, raw, header, terms, budget, 0, 0, 11)]

    def test_valid_quote_yields_unsent_single_buy_intent(self):
        proposal, reason = self.preflight.assess(*self.inputs())
        self.assertIsNone(reason)
        self.assertTrue(proposal["preflightOnly"])
        self.assertEqual(proposal["feature"], "marketFlip")
        self.assertEqual(proposal["intent"]["kind"], "marketBuy")
        self.assertEqual(proposal["intent"]["quantity"], 1)
        self.assertEqual(proposal["intent"]["quotedPrice"], 8)
        self.assertIsNone(proposal["remote"])

    def test_stale_quote_or_changed_header_is_rejected(self):
        values = self.inputs()
        values[0]["capturedAt"] = -20
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[2]["account"] = "other"
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[1]["native"]["fullSync"] = False
        self.assertIsNone(self.preflight.assess(*values)[0])

    def test_expired_shop_full_slots_or_locked_level_block(self):
        values = self.inputs()
        values[1]["native"]["market"]["shopUntil"] = 1050
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[3]["maxSlots"] = 1
        values[1]["native"]["market"]["listings"]["ours"] = {}
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[1]["native"]["level"] = 19
        self.assertIsNone(self.preflight.assess(*values)[0])

    def test_gold_reserve_session_budget_and_attempt_cap_block(self):
        values = self.inputs()
        values[4]["goldReserve"] = 13
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[5] = 13
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[6] = 2
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[4]["transactionOpen"] = True
        self.assertIsNone(self.preflight.assess(*values)[0])

    def test_item_kind_and_rarity_exclusions_block(self):
        for field, value in (("blockedItems", "w_baton"),
                             ("blockedKinds", "weapon"),
                             ("blockedRarities", 5)):
            values = self.inputs()
            values[4][field][value] = True
            self.assertIsNone(self.preflight.assess(*values)[0])

    def test_wrong_source_terms_or_missing_gold_block(self):
        values = self.inputs()
        values[3]["release"] = "old"
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[1]["native"]["inventory"]["gold_bar"] = 0
        values[1]["native"]["inventoryBound"]["gold_bar"] = 20
        self.assertIsNone(self.preflight.assess(*values)[0])


if __name__ == "__main__":
    unittest.main()
