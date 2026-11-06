"""A Market rental quote is local and preserves Gold and attempt limits."""
import unittest

from engine_harness import Harness, lua_table


class MarketRentQuoteTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.quote = self.h.load(
            "src/tabs/blackMarket/MarketRentQuote.luau")
        self.header = {"session": "s", "account": "a", "place": "p",
                       "release": "r", "revision": 4, "capturedAt": 10}

    def inputs(self):
        raw = dict(self.header, native={"fullSync": True,
            "level": 50, "serverNow": 1000.5,
            "inventory": {"gold_bar": 8},
            "inventoryBound": {"gold_bar": 2},
            "derived": {"marketShop": False},
            "market": {"shopUntil": 900}})
        terms = {"release": "r", "minLevel": 20,
                 "rentPerPeriod": 1,
                 "rentPeriodHours": 12, "rentMaxDays": 7}
        settings = {"goldReserve": 5, "maxAttempts": 1,
                    "maxGoldSpend": 1}
        return [lua_table(self.h.lua, x) for x in
                (raw, self.header, terms, settings, 0)]

    def test_quotes_one_native_period_without_sending(self):
        proposal, reason = self.quote.assess(*self.inputs())
        self.assertIsNone(reason)
        self.assertEqual(proposal["feature"], "marketRent")
        self.assertEqual(proposal["intent"]["kind"], "marketRent")
        self.assertEqual(proposal["intent"]["periods"], 1)
        self.assertEqual(proposal["intent"]["cost"], 1)
        self.assertEqual(proposal["intent"]["durationSeconds"], 43200)
        self.assertEqual(proposal["revision"], 4)

    def test_open_or_permanent_shop_blocks_rent(self):
        values = self.inputs()
        values[0]["native"]["market"]["shopUntil"] = 1121
        self.assertIsNone(self.quote.assess(*values)[0])
        values = self.inputs()
        values[0]["native"]["derived"]["marketShop"] = True
        self.assertIsNone(self.quote.assess(*values)[0])

    def test_level_reserve_spend_and_attempt_caps(self):
        for target, field, value in (("native", "level", 19),
                                      ("settings", "goldReserve", 10),
                                      ("settings", "maxGoldSpend", 0),
                                      ("settings", "maxAttempts", 0)):
            values = self.inputs()
            row = values[0]["native"] if target == "native" else values[3]
            row[field] = value
            self.assertIsNone(self.quote.assess(*values)[0])
        values = self.inputs()
        values[4] = 1
        self.assertIsNone(self.quote.assess(*values)[0])

    def test_native_total_gold_can_fund_rent_without_assuming_payment_origin(self):
        values = self.inputs()
        values[0]["native"]["inventory"]["gold_bar"] = 0
        values[0]["native"]["inventoryBound"]["gold_bar"] = 10
        proposal,reason=self.quote.assess(*values)
        self.assertIsNone(reason)
        self.assertEqual(proposal.intent.cost, 1)
        self.assertEqual(proposal.intent.kind, "marketRent")

    def test_changed_header_or_incomplete_sync_blocks_quote(self):
        values = self.inputs()
        values[0]["native"]["fullSync"] = False
        self.assertIsNone(self.quote.assess(*values)[0])
        values = self.inputs()
        values[1]["revision"] = 5
        self.assertIsNone(self.quote.assess(*values)[0])
        values = self.inputs()
        values[0]["capturedAt"] = float("inf")
        values[1]["capturedAt"] = float("inf")
        self.assertIsNone(self.quote.assess(*values)[0])

    def test_invalid_or_overfilled_native_terms_block_quote(self):
        values = self.inputs()
        values[2]["rentPerPeriod"] = 0
        self.assertIsNone(self.quote.assess(*values)[0])
        values = self.inputs()
        values[0]["native"]["market"]["shopUntil"] = 1100
        values[2]["rentMaxDays"] = 0
        self.assertIsNone(self.quote.assess(*values)[0])
        values = self.inputs()
        values[2]["release"] = "old"
        self.assertIsNone(self.quote.assess(*values)[0])


if __name__ == "__main__":
    unittest.main()
