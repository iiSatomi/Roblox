"""Declared recovery projections retain full native state and exact action evidence."""
import json
from pathlib import Path
import unittest

from engine_harness import Harness, lua_table


class PendingActionSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.pending = self.h.load("src/storage/PendingAction.luau")
        self.evidence = self.h.load("src/features/JobsEvidence.luau")
        self.clone = self.h.lua.eval("""function(value)
            local function copy(v)
                if type(v) ~= 'table' then return v end
                local out={};for k,child in pairs(v) do out[k]=copy(child) end
                return out
            end
            return copy(value)
        end""")

    def action(self, inventory_size=1500):
        raw = self.h.snapshot(catalogKey="a"*64,
            native={"fullSync":True,"serverNow":100,"level":10,
                "pools":{"energy":5},"jobs":{"j_watch":{"completions":2}},
                "inventory":{f"owned_item_{i:04d}_"+"x"*24:i for i in range(inventory_size)}},
            jobCatalog=[{"id":"j_watch","level":1,"energy":1,"cash":10,"xp":2}],
            masteryRules=[{"completions":25,"energyDiscount":0}],
            stationCatalog=[{"id":f"district_{i}","tax":5,"holder":f"family_{i}","capacity":5}
                            for i in range(1500)],
            trophyCatalog=[{"id":f"trophy_{i}","kind":"trophy"} for i in range(100)])
        context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        view,reason = context.Read(context,raw,lua_table(self.h.lua,self.h.session),0,2)
        self.assertIsNone(reason)
        jobs,reason = self.h.load("src/game/JobsState.luau").read(raw,view)
        self.assertIsNone(reason)
        proposal,reason = self.h.load("src/features/Jobs.luau").propose(jobs,
            lua_table(self.h.lua,{"enabled":True,"policy":"Balanced"}),
            lua_table(self.h.lua,{"energy":0,"uncertainEnergy":0}))
        self.assertIsNone(reason)
        proposal.requestId = 7
        baseline,reason = self.evidence.capture(proposal,raw)
        self.assertIsNone(reason)
        return proposal,raw,baseline

    def assert_recaptures(self,proposal,before,baseline):
        encoded,reason = self.pending.Capture(proposal,before,baseline)
        self.assertIsNone(reason)
        decoded = self.pending.Decode(encoded)
        self.assertIsNotNone(decoded)
        self.assertIsNone(decoded.before.data)
        self.assertEqual(decoded.before.native.inventory["owned_item_0001_"+"x"*24],1)
        self.assertIsNone(decoded.before.stationCatalog)
        self.assertEqual(decoded.before.jobCatalog[1].id,"j_watch")
        self.assertEqual(decoded.before.masteryRules[1].completions,25)
        recaptured,reason = self.evidence.capture(decoded.proposal,decoded.before)
        self.assertIsNone(reason)
        self.assertEqual(dict(recaptured.items()),dict(decoded.baseline.items()))
        copied,reason = self.pending.Copy(encoded)
        self.assertIsNone(reason)
        self.assertTrue(self.pending.Same(encoded,copied))

    def test_large_all_tab_snapshot_with_native_alias_round_trips(self):
        proposal,before,baseline = self.action()
        before.data = before.native
        self.assert_recaptures(proposal,before,baseline)

    def test_separately_decoded_equivalent_native_duplicate_round_trips(self):
        proposal,before,baseline = self.action()
        before.data = self.clone(before.native)
        self.assert_recaptures(proposal,before,baseline)

    def test_conflicting_native_duplicate_is_rejected(self):
        proposal,before,baseline = self.action(inventory_size=1)
        before.data = self.clone(before.native)
        before.data.jobs.j_watch.completions = 3
        self.assertIsNone(self.pending.Capture(proposal,before,baseline)[0])

    def test_native_cycle_remains_rejected_even_when_data_is_an_alias(self):
        proposal,before,baseline = self.action(inventory_size=1)
        before.data = before.native
        before.native.cycle = before.native
        self.assertIsNone(self.pending.Capture(proposal,before,baseline)[0])

    def test_omitted_selection_catalogs_cannot_hide_cycles_or_malformed_values(self):
        for malformed in (self.h.lua.eval("function() return 1 end"), float('inf')):
            with self.subTest(malformed=type(malformed).__name__):
                proposal,before,baseline = self.action(inventory_size=1)
                before.stationCatalog[1].invalid = malformed
                self.assertIsNone(self.pending.Capture(proposal,before,baseline)[0])
        proposal,before,baseline = self.action(inventory_size=1)
        before.stationCatalog[1].cycle = before.stationCatalog
        self.assertIsNone(self.pending.Capture(proposal,before,baseline)[0])

    def test_required_native_data_still_obeys_original_storage_limit(self):
        proposal,before,baseline = self.action(inventory_size=7000)
        before.data = before.native
        self.assertIsNone(self.pending.Capture(proposal,before,baseline)[0])

    def operation_action(self, feature):
        _,raw,_ = self.action()
        raw.native.cash,raw.native.respect,raw.native.level = 10000,100,30
        raw.native.operations = lua_table(self.h.lua,{"active":[
            {"opId":"op_fence","remaining":0 if feature=="collect" else 10,"slot":1}]})
        raw.operationCatalog = lua_table(self.h.lua,[{"id":"op_fence","duration":600,
            "cost":200,"cash":1500,"xp":20}])
        context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        view,reason = context.Read(context,raw,lua_table(self.h.lua,self.h.session),0,2)
        self.assertIsNone(reason)
        view,reason = self.h.load("src/game/OperationsState.luau").read(raw,view)
        self.assertIsNone(reason)
        suffix = "Start" if feature=="operations" else "Collect"
        proposed = self.h.load(f"src/features/Operations{suffix}.luau").propose(view,
            lua_table(self.h.lua,{"enabled":True,"policy":"Shortest duration"}),
            lua_table(self.h.lua,{"cash":0,"uncertainCash":0}))
        proposal,reason = proposed
        self.assertIsNone(reason)
        evidence = self.h.load("src/features/OperationsEvidence.luau" if feature=="operations"
            else "src/features/OperationsCollectEvidence.luau")
        baseline,reason = evidence.capture(proposal,raw)
        self.assertIsNone(reason)
        return proposal,raw,baseline,evidence

    def test_large_all_tab_operation_start_and_collect_reproduce_exact_native_evidence(self):
        equal = self.h.lua.eval("function(a,b) local function eq(x,y) if type(x)~=type(y) then return false end if type(x)~='table' then return x==y end for k,v in pairs(x) do if not eq(v,y[k]) then return false end end for k in pairs(y) do if x[k]==nil then return false end end return true end return eq(a,b) end")
        for feature in ("operations","collect"):
            with self.subTest(feature=feature):
                proposal,raw,baseline,evidence = self.operation_action(feature)
                raw.data = raw.native
                encoded,reason = self.pending.Capture(proposal,raw,baseline)
                self.assertIsNone(reason)
                decoded = self.pending.Decode(encoded)
                recaptured,reason = evidence.capture(decoded.proposal,decoded.before)
                self.assertIsNone(reason)
                self.assertTrue(equal(recaptured,decoded.baseline))
                self.assertTrue(equal(raw.native,decoded.before.native))
                self.assertEqual(decoded.before.catalogKey,raw.catalogKey)
                self.assertEqual(decoded.before.operationCatalog[1].cost,200)
                self.assertIsNone(decoded.before.stationCatalog)
                self.assertIsNone(decoded.before.jobCatalog)
                after = self.clone(decoded.before)
                after.revision = 2
                if feature=="operations":
                    after.native.cash = 9800
                    after.native.operations.active[2] = lua_table(self.h.lua,
                        {"opId":"op_fence","remaining":600,"slot":2})
                else:
                    after.native.operations.active = self.h.lua.table()
                self.assertEqual(evidence.evaluate(decoded.proposal,decoded.before,after,
                    lua_table(self.h.lua,{"ok":True}),recaptured),"confirmed")

    def reward_action(self, feature):
        _,raw,_ = self.action()
        raw.native.level,raw.native.cash,raw.native.serverNow = 1,100,1000
        raw.native.inventoryBound = self.h.lua.table()
        raw.native.playtime = lua_table(self.h.lua,{"todaySeconds":301,"laddersClaimed":{}})
        raw.native.groupBonus = False
        catalog = self.h.load("src/tabs/rewards/NativeRewardsCatalog.luau").new(
            lua_table(self.h.lua,{"LADDER":[{"seconds":300*(i+1),"kind":"cash","flat":10} for i in range(7)],
                "LADDER_TIERS":[1,10,30,102],"GROUP":{"id":123,"incomeBonus":0.1},
                "MONTHLY_CALENDAR":{"enabled":True,"default":{"kind":"gold","amount":3}}}),
            "a"*64,"release-a")
        raw,reason = catalog.Enrich(catalog,raw)
        self.assertIsNone(reason)
        day = self.h.lua.eval("tonumber(os.date('!%Y%j',1000))")
        raw.weekendBuff = lua_table(self.h.lua,{"active":False,"day":day})
        raw.groupMembership = lua_table(self.h.lua,{**self.h.session,"groupId":123,"isMember":True,"checkedAt":0})
        proposal = self.h.proposal(feature,feature+":owned-claim")
        proposal.resources = self.h.lua.table()
        if feature=="groupBonus":
            proposal.intent = lua_table(self.h.lua,{"kind":"groupBonusClaim","groupId":123})
            evidence = self.h.load("src/features/GroupBonusEvidence.luau").new(catalog)
        else:
            marker = self.h.load("src/features/PlaytimeEvidence.luau" if feature=="playtime" else "src/features/MonthlyRewardsEvidence.luau")
            evidence = self.h.load("src/tabs/rewards/RewardEffects.luau").new(catalog,marker,feature)
            proposal.intent = lua_table(self.h.lua,{"kind":"playtimeClaim","index":1,"day":day,"catalogKey":"a"*64}
                if feature=="playtime" else {"kind":"monthlyClaim","nextDay":1,"today":day,"month":"1970-01"})
        baseline,reason = evidence.capture(proposal,raw)
        self.assertIsNone(reason)
        return proposal,raw,baseline,evidence,day

    def test_reward_recovery_retains_source_defined_effect_and_owned_claim_proofs(self):
        for feature in ("playtime","monthlyRewards","groupBonus"):
            with self.subTest(feature=feature):
                proposal,raw,baseline,evidence,day = self.reward_action(feature)
                raw.data = raw.native
                encoded,reason = self.pending.Capture(proposal,raw,baseline)
                self.assertIsNone(reason)
                decoded = self.pending.Decode(encoded)
                recaptured,reason = evidence.capture(decoded.proposal,decoded.before)
                self.assertIsNone(reason)
                equal = self.h.lua.eval("function(a,b) local function eq(x,y) if type(x)~=type(y) then return false end if type(x)~='table' then return x==y end for k,v in pairs(x) do if not eq(v,y[k]) then return false end end for k in pairs(y) do if x[k]==nil then return false end end return true end return eq(a,b) end")
                self.assertTrue(equal(recaptured,decoded.baseline))
                self.assertTrue(equal(raw.native,decoded.before.native))
                self.assertIsNone(decoded.before.stationCatalog)
                self.assertIsNone(decoded.before.operationCatalog)
                after = self.clone(decoded.before)
                after.revision,after.native.serverNow = 2,1001
                if feature=="playtime":
                    after.native.playtime.laddersClaimed['1'] = 1
                    after.native.cash = 110
                elif feature=="monthlyRewards":
                    after.native.monthly = lua_table(self.h.lua,{"month":"1970-01","claimed":1,"lastDay":day})
                    after.native.inventory.gold_bar = 3
                else:
                    after.native.groupBonus = True
                self.assertEqual(evidence.evaluate(decoded.proposal,decoded.before,after,
                    lua_table(self.h.lua,{"ok":True}),recaptured),"confirmed")

    def test_bank_recovery_preserves_quote_savings_and_exact_transfer_evidence(self):
        _,raw,_ = self.action()
        raw.native.cash,raw.native.banked = 50000,1000
        raw.native.derived = lua_table(self.h.lua,{"noBankFees":False})
        raw.bankConfig = lua_table(self.h.lua,{"depositFee":0.1})
        raw.purchaseSavings = lua_table(self.h.lua,{**self.h.session,"revision":1,"capturedAt":0,"amount":15000})
        context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        view,reason = context.Read(context,raw,lua_table(self.h.lua,self.h.session),0,2)
        self.assertIsNone(reason)
        view,reason = self.h.load("src/game/BankState.luau").read(raw,view)
        self.assertIsNone(reason)
        proposal,reason = self.h.load("src/features/BankDeposits.luau").propose(view,
            lua_table(self.h.lua,{"enabled":True,"depositThreshold":10000,"cashToKeep":0}),
            lua_table(self.h.lua,{"cash":0,"uncertainCash":0}))
        self.assertIsNone(reason)
        evidence = self.h.load("src/features/BankDepositsEvidence.luau")
        baseline,reason = evidence.capture(proposal,raw)
        self.assertIsNone(reason)
        raw.data = raw.native
        encoded,reason = self.pending.Capture(proposal,raw,baseline)
        self.assertIsNone(reason)
        decoded = self.pending.Decode(encoded)
        recaptured,reason = evidence.capture(decoded.proposal,decoded.before)
        self.assertIsNone(reason)
        self.assertEqual(dict(recaptured.items()),dict(decoded.baseline.items()))
        self.assertIsNone(decoded.before.stationCatalog)
        self.assertEqual(decoded.before.purchaseSavings.amount,15000)
        after = self.clone(decoded.before)
        after.revision,after.native.cash,after.native.banked = 2,15000,32500
        self.assertEqual(evidence.evaluate(decoded.proposal,decoded.before,after,
            lua_table(self.h.lua,{"ok":True,"fee":3500,"kept":31500}),recaptured),"confirmed")

    def test_each_action_catalog_switch_has_a_bounded_projection_and_unknowns_stay_closed(self):
        catalog = json.loads((Path(__file__).resolve().parents[1]/"preview/catalog.json").read_text(encoding="utf-8"))
        # These four descriptors derive goals or perform owned reads and never
        # submit an action to the checkpoint. All other advertised switches do.
        observers = {"autoContracts","trophyFocus","marketWatch","territoryWatch"}
        features = [row['id'] for row in catalog['features'] if row['id'] not in observers]
        self.assertEqual(len(features),51)
        for feature in features:
            with self.subTest(feature=feature):
                proposal,before,_ = self.action(inventory_size=1)
                proposal.feature = feature
                proposal.intent = lua_table(self.h.lua,{"kind":"encoding-schema-only"})
                before.unusedSelectionCatalog = lua_table(self.h.lua,[
                    {"id":f"unused_{i}","label":"x"*200} for i in range(1500)])
                encoded,reason = self.pending.Capture(proposal,before,self.h.lua.table())
                self.assertIsNone(reason)
                self.assertIsNone(self.pending.Decode(encoded).before.unusedSelectionCatalog)
        proposal.feature = "future-unmapped-feature"
        self.assertIsNone(self.pending.Capture(proposal,before,self.h.lua.table())[0])

    def test_optional_private_live_job_capture_preserves_real_evidence(self):
        path = Path(__file__).resolve().parents[1]/".private/native-654/failed-pending.json"
        if not path.is_file():
            self.skipTest("Private live diagnostic is deliberately not committed")
        raw = lua_table(self.h.lua,json.loads(path.read_text(encoding="utf-8-sig")))
        encoded,reason = self.pending.Capture(raw.proposal,raw.before,raw.baseline)
        self.assertIsNone(reason)
        decoded = self.pending.Decode(encoded)
        baseline,reason = self.evidence.capture(decoded.proposal,decoded.before)
        self.assertIsNone(reason)
        self.assertEqual(dict(baseline.items()),dict(decoded.baseline.items()))


if __name__ == "__main__":
    unittest.main()
