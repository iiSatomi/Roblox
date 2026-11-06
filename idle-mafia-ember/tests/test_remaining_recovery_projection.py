"""Territory, Recall and Market rental/payout capture contracts remain replay-free."""
import unittest

from engine_harness import Harness, lua_table
from recovery_projection_harness import assert_projection
import test_conditional_feature_contracts
import test_recall_runtime
import test_market_earnings


class RemainingRecoveryProjectionTests(unittest.TestCase):
    def test_station_and_recall_and_residency_keep_their_actual_proofs(self):
        helper = test_conditional_feature_contracts.ConditionalContracts(methodName="runTest")
        helper.setUp()
        station,_,before,proposal,_ = helper.station_attempt()
        with self.subTest(activity="station"):
            assert_projection(self,helper.h,station,proposal,before)
        residency,before,proposal,_,_ = helper.residency_attempt()
        with self.subTest(activity="residency"):
            assert_projection(self,helper.h,residency,proposal,before)
        recall = test_recall_runtime.RecallRuntimeTests(methodName="runTest")
        recall.setUp()
        proposal = recall.proposal()
        with self.subTest(activity="recall"):
            assert_projection(self,recall.h,recall.feature.evidence,proposal,recall.before)

    def test_station_catalog_recovery_keeps_only_exact_selected_district_terms(self):
        helper = test_conditional_feature_contracts.ConditionalContracts(methodName="runTest")
        helper.setUp()
        h = helper.h
        module = h.load("src/tabs/territory/Stationing.luau")
        districts = {f"unused_{i}":{"city":"city_"+"x"*100,"tier":1} for i in range(3000)}
        districts['d1'] = {"city":"city-a","tier":1}
        owner = module.new(lua_table(h.lua,{"TERRITORY":{"garrisonCap":200}}),
            lua_table(h.lua,{"DISTRICTS_BY_ID":districts}),test_conditional_feature_contracts.KEY,h.session['release'])
        before = helper.station_raw(owner)
        view,reason = module.read(before,before)
        self.assertIsNone(reason)
        proposal,reason = module.propose(view,lua_table(h.lua,{"enabled":True,
            "districtId":"d1","memberSlot":2,"minHome":1,"maxStationed":1,"maxAttempts":1}))
        self.assertIsNone(reason)
        decoded = assert_projection(self,h,module,proposal,before)
        self.assertEqual(list(decoded.before.stationCatalogProof.cities.keys()),['d1'])
        self.assertEqual(list(decoded.before.stationCatalogProof.caps.keys()),['d1'])
        self.assertEqual(decoded.before.stationCatalogProof.cities.d1,'city-a')
        self.assertEqual(decoded.before.stationCatalogProof.caps.d1,200)
        decoded.before.stationCatalogProof.cities.d1 = 'other-city'
        self.assertIsNone(module.capture(decoded.proposal,decoded.before)[0])

    def test_market_earnings_uses_full_native_receipt_baseline(self):
        helper = test_market_earnings.MarketEarningsTests(methodName="runTest")
        helper.setUp()
        before,proposal = helper.proposal()
        assert_projection(self,helper.h,helper.evidence,proposal,before)

    def test_market_rental_uses_bound_terms_and_checkpoint_allowance(self):
        h = Harness()
        feature = h.load("src/tabs/blackMarket/MarketRentRuntime.luau").new(lua_table(h.lua,{
            "MarketRentQuote":h.load("src/tabs/blackMarket/MarketRentQuote.luau"),
            "MarketRentEvidence":h.load("src/tabs/blackMarket/MarketRentEvidence.luau"),
            "MarketSettings":h.load("src/tabs/blackMarket/MarketSettings.luau")}))
        before = h.snapshot(native={"fullSync":True,"serverNow":100,"level":20,
            "market":{"shopUntil":0},"derived":{"marketShop":False},
            "inventory":{"gold_bar":10},"inventoryBound":{"gold_bar":0}})
        header = {k:before[k] for k in ('session','account','place','release','revision','capturedAt')}
        before.marketRentTermsProof = lua_table(h.lua,{**header,"terms":{"release":"release-a",
            "sourceKey":"a"*64,"minLevel":1,"rentPerPeriod":2,"rentPeriodHours":24,"rentMaxDays":30}})
        before.marketRentUsageProof = lua_table(h.lua,{**header,"attempted":0,"spent":0})
        view,reason = feature.read(before,before)
        self.assertIsNone(reason)
        proposal,reason = feature.propose(view,lua_table(h.lua,{"enabled":True,
            "goldReserve":0,"maxAttempts":1,"maxGoldSpend":2}))
        self.assertIsNone(reason)
        assert_projection(self,h,feature,proposal,before)


if __name__ == "__main__":
    unittest.main()
