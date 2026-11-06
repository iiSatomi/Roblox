"""Real conditional action captures preserve their source and durable allowance proofs."""
import unittest

from engine_harness import Harness, lua_table
from recovery_projection_harness import assert_projection


def proof(h, raw, **fields):
    return lua_table(h.lua,{**{key:raw[key] for key in (
        "session","account","place","release","revision","capturedAt")},**fields})


class ConditionalRecoveryProjectionTests(unittest.TestCase):
    def test_family_cash_stamina_and_gold_use_actual_personal_contribution_contracts(self):
        for lane in ("cash","stamina","gold"):
            with self.subTest(lane=lane):
                h = Harness()
                h.session['account'] = '42'
                module = h.load("src/tabs/family/FamilyContributionState.luau")
                state = module.new(lua_table(h.lua,{"FAMILY":{"donateMin":100,"contributeMax":5,
                    "baseCap":30,"capPerLevel":5,"maxCap":50,"capSlotMax":10,
                    "staminaPerkCosts":[10,20],"perkTracks":{"boost":{"kind":"stamina"}}}}),
                    'a'*64,'release-a',h.lua.execute("return {Current=function() return true end,Read=function(_,native) if native.userId==42 then return {userId=42,name='42'} end end}"))
                raw = h.snapshot(native={"fullSync":True,"serverNow":100,"userId":42,"family":{"id":"fam"},
                    "cash":1000,"pools":{"stamina":10},"inventory":{"gold_bar":10},"inventoryBound":{}})
                raw,reason = state.Enrich(state,raw)
                self.assertIsNone(reason)
                raw,reason = state.Stage(state,raw,lua_table(h.lua,{"ok":True,"family":{
                    "id":"fam","level":1,"capSlots":0,"memberCap":30,
                    "members":[{"userId":42}],"perks":{"boost":0},"perkProgress":{"boost":0}}}))
                self.assertIsNone(reason)
                raw.familyUsageProof = proof(h,raw,usage={feature:{"attempted":0,"spent":0}
                    for feature in ('familyCash','familyStamina','familyGold')})
                view,reason = module.read(raw,raw)
                self.assertIsNone(reason)
                planner = h.load("src/tabs/family/FamilyContributions.luau")[lane]
                proposal,reason = planner.propose(view,lua_table(h.lua,{"enabled":True,
                    "amount":100 if lane=='cash' else 1,"reserve":0,"runBudget":1000,
                    "maxAttempts":2,"selectedPerk":"boost"}),h.lua.table())
                self.assertIsNone(reason)
                evidence = h.load("src/tabs/family/FamilyContributionEvidence.luau").new(module)
                decoded = assert_projection(self,h,evidence,proposal,raw)
                self.assertEqual(decoded.before.familyContributionCatalog.key,'a'*64)
                self.assertEqual(decoded.before.familyContributionProof.family.actorId,42)

    def test_current_native_event_shop_source_and_usage_survive_projection(self):
        h = Harness()
        definition = lua_table(h.lua,{"MEDAL":"event_medal","MAX_ITEM_COUNT":99,
            "CURRENCIES":{"medal":{"item":"event_medal","paidField":"paidMedals"}},
            "ROWS":[{"key":"loot","item":"crate_loot","kind":"crate","price":2,"count":1}]})
        source,reason = h.load("src/tabs/events/NativeEventShopSource.luau").new(definition,
            h.lua.eval("function() return {GlobalEventShop=true,GlobalEventShopEnd=1000,MWPaidRandomRestricted=false,serverNow=100} end"),
            'a'*64,'release-a')
        self.assertIsNone(reason)
        raw = h.snapshot(native={"fullSync":True,"serverNow":100,"inventory":{},
            "inventoryBound":{"event_medal":10},"paidMedals":0})
        raw,reason = source.Enrich(source,raw)
        self.assertIsNone(reason)
        raw.eventShopUsageProof = proof(h,raw,attempted=0,spent=0)
        feature = h.load("src/tabs/events/EventShopBuyer.luau").new(source)
        view,reason = feature.read(raw,raw)
        self.assertIsNone(reason)
        proposal,reason = feature.propose(view,lua_table(h.lua,{"enabled":True,
            "offerKey":"loot","medalReserve":0,"maxSpend":10,"maxAttempts":2}))
        self.assertIsNone(reason)
        decoded = assert_projection(self,h,feature,proposal,raw)
        self.assertEqual(decoded.before.eventShopProof.sourceKey,'a'*64)
        self.assertEqual(decoded.before.eventShopUsageProof.attempted,0)

    def test_both_funded_crew_replacement_stages_reproduce_capture(self):
        h = Harness()
        odds = [0,100,0,0,0,0,0,0]
        feature,reason = h.load("src/tabs/crew/CrewReplacement.luau").new(
            lua_table(h.lua,{"CREW":{"hireTiers":[{"id":"street","cost":100,"odds":odds,"oddsLucky":odds}]}}),
            'a'*64,'release-a')
        self.assertIsNone(reason)
        def raw(revision=1,empty=False):
            value = h.snapshot(revision=revision,native={"fullSync":True,"serverNow":99+revision,
                "cash":1000,"cityId":"ny","derived":{"luckyHire":False},"crew":[{},
                    {} if empty else {"name":"Weak","rarity":1,"atk":1,"def":1,"healId":"a"},
                    {"name":"Keep","rarity":3,"atk":3,"def":3,"healId":"b"}]},
                economyProof={"account":"user-a","capturedAt":0,"city":"ny","revision":1,
                    "familyId":"","rulerId":"","hirePct":0})
            value.crewReplacementUsageProof = proof(h,value,attempted=1 if empty else 0,spent=0,controllersClear=True)
            value.crewReplacementOwnerProof = proof(h,value,ownerId="owner",slot=2)
            return feature.Enrich(feature,value)[0]
        before = raw()
        view,reason = feature.read(before,before)
        self.assertIsNone(reason)
        proposal,reason = feature.propose(view,lua_table(h.lua,{"enabled":True,"allowDismiss":True,
            "slot":2,"tier":"street","targetRarity":2,"maxDismissRarity":1,"cashReserve":100,
            "minHome":1,"maxCost":100,"maxSpend":200,"maxAttempts":2}))
        self.assertIsNone(reason)
        assert_projection(self,h,feature,proposal,before)
        after = raw(2,True)
        hire,reason = feature.FundedHire(after,proposal.intent)
        self.assertIsNone(reason)
        self.assertEqual(hire.intent.kind,"crewReplacementHire")
        assert_projection(self,h,feature,hire,after)


if __name__ == "__main__":
    unittest.main()
