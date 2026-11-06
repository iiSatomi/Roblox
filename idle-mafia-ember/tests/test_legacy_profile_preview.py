"""Legacy schema-17 choices require an inert, loss-visible import preview."""
import json,unittest
from pathlib import Path
from test_redundant_store import plain
import test_profile_management as fixture
from engine_harness import lua_table

class LegacyProfilePreviewTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.ProfileManagementTests();self.f.setUp();self.app=self.f.app;self.h=self.f.h
    def tearDown(self):self.f.tearDown()
    def preview(self,settings,**extra):
        return self.app.PreviewImport(self.app,json.dumps(dict(settings,**extra)))
    def test_explicit_review_stages_current_defaults_and_retains_original_choices(self):
        raw = {"version":17,"skipConfirmation":True,"favorUsageCount":30,"bankCashToKeep":700}
        original = dict(raw)
        choices = self.h.lua.table_from({"skipConfirmation":"useCurrentDefault","favorUsageCount":"useCurrentDefault"})
        accepted, reason = self.app.PreviewImport(self.app,json.dumps(raw),choices)
        self.assertTrue(accepted,reason)
        self.assertEqual(raw,original)
        self.assertEqual(self.app.importReview.original.favorUsageCount,30)
        self.assertEqual(self.app.importReview.reviewedExclusions.favorUsageCount,"useCurrentDefault")
        self.assertEqual(self.app.staged["values"]["bank.custom.cashToKeep"],700)
        self.assertFalse(any(v for k,v in self.app.staged["values"].items() if k.endswith(".enabled")))

    def test_partial_or_unknown_review_cannot_stage_an_import(self):
        text=json.dumps({"version":17,"skipConfirmation":True,"favorUsageCount":30})
        choices=self.h.lua.table_from({"skipConfirmation":"useCurrentDefault"})
        self.assertFalse(self.app.PreviewImport(self.app,text,choices)[0])
        self.assertIsNone(self.app.staged)
        text=json.dumps({"version":17,"unknownPreference":12})
        choices=self.h.lua.table_from({"unknownPreference":"useCurrentDefault"})
        self.assertFalse(self.app.PreviewImport(self.app,text,choices)[0])
        self.assertIsNone(self.app.staged)

    def test_reviewed_nondefault_bank_choices_stage_without_activation_or_storage(self):
        accepted,reason=self.preview({"version":17,"depositThreshold":25000,"bankCashToKeep":700})
        self.assertTrue(accepted,reason)
        self.assertEqual(self.app.staged["values"]["bank.custom.depositThreshold"],25000)
        self.assertEqual(self.app.staged["values"]["bank.custom.cashToKeep"],700)
        self.assertEqual(self.app.model["values"]["bank.custom.cashToKeep"],0)
        self.assertEqual(len(self.f.base.storage.data),0)
        self.assertFalse(self.app.staged["values"]["bank.enabled"])
        self.assertTrue(self.app.ApplyProfile(self.app,self.app.staged)[0]);self.assertTrue(self.app.model.paused)
    def test_nondefault_unmapped_constraint_is_named_and_preserved_without_staging(self):
        self.assertTrue(self.app.PreviewImport(self.app,'{"schema":1,"values":{"jobs.enabled":true}}')[0])
        accepted,reason=self.preview({"version":17,"skipConfirmation":True,"bankCashToKeep":700})
        self.assertFalse(accepted);self.assertIn("skipConfirmation",reason)
        self.assertIsNone(self.app.staged)
        self.assertEqual(self.app.importReview.original.skipConfirmation,True)
        self.assertEqual(self.app.importReview.mapped["bank.custom.cashToKeep"],700)
    def test_unknown_legacy_keys_and_runtime_usage_are_never_silently_discarded(self):
        for key,value in (("typoReserve",12),("favorUsageCount",3),("skipConfirmation",True),("marketAutoCheck",False)):
            accepted,reason=self.preview({"version":17,key:value})
            self.assertFalse(accepted);self.assertIn(key,reason)
    def test_profile_record_never_imports_enabled_senders_or_combat_permission(self):
        text=json.dumps({"settings":{"version":17,"bankCashToKeep":700},"enabled":{"bank":True},"combatPermission":True})
        accepted,reason=self.app.PreviewImport(self.app,text)
        self.assertFalse(accepted);self.assertIn("enabled.bank",reason);self.assertIn("combatPermission",reason)
        self.assertFalse(self.app.model["values"]["bank.enabled"])
    def test_invalid_typed_or_out_of_range_values_do_not_coerce(self):
        for value in (True,"700",-1,10**16):
            accepted,reason=self.preview({"version":17,"bankCashToKeep":value})
            self.assertFalse(accepted);self.assertIn("bankCashToKeep",reason)
    def test_modern_profile_still_uses_strict_schema_and_clears_old_legacy_review(self):
        self.preview({"version":17,"typoReserve":12})
        self.assertTrue(self.app.PreviewImport(self.app,'{"schema":1,"values":{"jobs.enabled":true}}')[0])
        self.assertIsNone(self.app.importReview)
    def test_entire_recorded_baseline_is_recognized_and_defaults_are_visible(self):
        module=self.h.load("src/storage/LegacySettings.luau");defaults=plain(module.defaults())
        inventory=json.loads((Path(__file__).parents[1]/"docs/legacy-settings-inventory.json").read_text(encoding="utf-8"))
        expected={row["legacy_key"]:plain(self.h.lua.execute("return "+row["legacy_default_literal"])) for row in inventory["settings"]}
        self.assertEqual(defaults,expected);self.assertEqual(len(defaults),231)
        accepted,reason=self.preview(defaults);self.assertTrue(accepted,reason)
        self.assertEqual(len(self.app.importReview.currentDefaults),209)
        for key in ("shopKind", "shopRule", "shopCashMax", "shopOwnedCap", "shopMinRarity",
                    "shopCosmetics", "shopCrates", "shopRarityOverride", "shopOverrideRarities", "shopUseBank"):
            self.assertNotIn(key, plain(self.app.importReview.currentDefaults))
        self.assertEqual(self.app.importReview.mapped["shop.custom.selection"],"Category rules")
        self.assertFalse(self.app.importReview.mapped["withdraw.custom.allowShop"])
        self.assertEqual(self.app.importReview.mapped["favors.policy"],"Balanced")
        self.assertEqual(self.app.importReview.mapped["bosses.custom.selection"],"Smart")
        self.assertEqual(self.app.staged["values"]["familyStamina.custom.selectedPerk"],"runners")
        for pool in ("health", "energy", "stamina"):
            self.assertEqual(self.app.importReview.mapped[f"restoratives.custom.{pool}Below"],25)
            self.assertEqual(self.app.staged["values"][f"restoratives.custom.{pool}Below"],25)
        self.assertEqual(self.app.staged["values"]["combat.custom.targetSource"],"Saved only")
        self.assertFalse(any(v for k,v in self.app.staged["values"].items() if k.endswith(".enabled")))
    def test_each_nondefault_key_is_either_mapped_or_explicitly_unresolved(self):
        defaults=plain(self.h.load("src/storage/LegacySettings.luau").defaults())
        for key,value in defaults.items():
            if key=="version":continue
            changed=not value if isinstance(value,bool) else value+1 if isinstance(value,(int,float)) else value+"_" if isinstance(value,str) else {"unmapped_choice":True}
            accepted,reason=self.preview({"version":17,key:changed})
            with self.subTest(key=key):
                if accepted:self.assertGreater(sum(1 for _ in self.app.importReview.mapped.items()),0)
                else:self.assertIn(key,reason)
    def test_unsupported_schema_unknown_false_switch_and_conflicting_perk_precedence_refuse(self):
        for record,key in (({"version":18},"version"),
            ({"settings":{"version":17},"enabled":{"unknown":False}},"enabled.unknown"),
            ({"version":17,"familyPerk":"enforcers","familyPerks":{"runners":True}},"familyPerk")):
            accepted,reason=self.preview(record);self.assertFalse(accepted);self.assertIn(key,reason)
    def test_pure_preview_does_not_alias_source_and_rejects_cycles(self):
        module=self.h.load("src/storage/LegacySettings.luau")
        raw=lua_table(self.h.lua,{"version":17,"skipConfirmation":True})
        profile,review,reason=module.preview(raw,self.app.model)
        self.assertIsNone(profile);review.original.skipConfirmation=False;self.assertTrue(raw.skipConfirmation)
        raw.loop=raw;self.assertIsNone(module.preview(raw,self.app.model)[0])
    def test_ui_review_contains_original_mapping_default_changes_and_inactive_result(self):
        raw={"version":17,"bankCashToKeep":700,"marketSellFromCollection":True}
        self.assertTrue(self.preview(raw)[0])
        report=json.loads(self.app.ui.profiles.importReviewText.value)
        self.assertEqual(report["original"],raw)
        self.assertEqual(report["mapped"]["bank.custom.cashToKeep"],700)
        self.assertIn("marketSellFromCollection",report["currentDefaults"])
        self.assertFalse(report["stagedPreview"]["values"]["marketSell.custom.fromCollection"])
        self.assertFalse(any(value for key,value in report["stagedPreview"]["values"].items() if key.endswith(".enabled")))
    def test_unresolved_review_is_copyable_without_staging_or_losing_original_intent(self):
        self.assertFalse(self.preview({"version":17,"favorUsageCount":3,"skipConfirmation":True})[0])
        report=json.loads(self.app.ui.profiles.importReviewText.value)
        self.assertEqual(set(report["unresolved"]),{"favorUsageCount","skipConfirmation"})
        self.assertEqual(report["original"]["favorUsageCount"],3);self.assertIsNone(self.app.staged)
    def test_editing_review_output_cannot_change_staged_choices(self):
        self.assertTrue(self.preview({"version":17,"bankCashToKeep":700})[0])
        self.app.ui.profiles.importReviewText.Set(self.app.ui.profiles.importReviewText,'{"schema":1,"values":{"jobs.enabled":true}}',True)
        self.assertTrue(self.app.ApplyProfile(self.app,self.app.staged)[0])
        self.assertFalse(self.app.model["values"]["jobs.enabled"])
    def test_failed_modern_import_preserves_matching_legacy_review_and_preview(self):
        self.assertTrue(self.preview({"version":17,"bankCashToKeep":700})[0])
        before=self.app.ui.profiles.importReviewText.value
        self.assertFalse(self.app.PreviewImport(self.app,'{"schema":1,"values":{"unknown":true}}')[0])
        self.assertEqual(self.app.ui.profiles.importReviewText.value,before)
        self.assertEqual(self.app.staged["values"]["bank.custom.cashToKeep"],700)
    def test_failed_review_output_does_not_stage_a_legacy_profile(self):
        self.h.lua.globals().json_encode=self.h.lua.eval("function() error('encode unavailable') end")
        accepted,reason=self.preview({"version":17,"bankCashToKeep":700})
        self.assertFalse(accepted);self.assertIn("review",reason.lower());self.assertIsNone(self.app.staged)
        self.assertEqual(self.app.importReview.original.bankCashToKeep,700)
    def test_reviewed_job_cash_policy_and_cached_id_preserve_separate_intent(self):
        self.assertTrue(self.preview({"version":17,"jobMode":"Cash / energy","jobId":"j_tag"})[0])
        self.assertEqual(self.app.staged["values"]["jobs.policy"],"Cash")
        self.assertEqual(self.app.staged["values"]["jobs.custom.selectedJobId"],"j_tag")
        self.assertFalse(self.app.staged["values"]["jobs.enabled"])
    def test_selected_job_import_never_falls_back_to_current_default_job(self):
        for source in ({"version":17,"jobMode":"Selected job"},{"version":17,"jobMode":"Selected job","jobId":"removed_job"}):
            accepted,reason=self.preview(source);self.assertFalse(accepted);self.assertIn("jobId",reason)
        self.assertTrue(self.preview({"version":17,"jobMode":"Selected job","jobId":"j_tag"})[0])
        self.assertEqual(self.app.staged["values"]["jobs.policy"],"Selected job")
    def test_reviewed_income_operation_rarity_and_relation_labels_translate_explicitly(self):
        source={"version":17,"propertyMode":"Income","operationMode":"Highest tier","crewTrainMinRarity":"Secret","favorRelationship":"Family only"}
        self.assertTrue(self.preview(source)[0]);values=self.app.staged["values"]
        self.assertEqual(values["properties.policy"],"Most income");self.assertEqual(values["operations.policy"],"Highest tier")
        self.assertEqual(values["crewTrain.custom.minRarity"],7);self.assertEqual(values["favors.custom.relations"],"Family only")
    def test_non_equivalent_legacy_policies_remain_named_instead_of_approximated(self):
        for key,value in (("jobMode","Balanced"),("propertyMode","Future policy"),("operationMode","Future policy"),("favorRelationship","Anyone")):
            accepted,reason=self.preview({"version":17,key:value});self.assertFalse(accepted);self.assertIn(key,reason)
    def test_crew_roll_reserve_and_tier_never_import_dismissal_or_spending_permission(self):
        self.assertTrue(self.preview({"version":17,"crewRollCashReserve":2000000,"crewRollTier":"Professional"})[0])
        values=self.app.staged["values"]
        self.assertEqual(values["crewRoll.custom.cashReserve"],2000000);self.assertEqual(values["crewRoll.custom.tier"],"professional")
        self.assertFalse(values["crewRoll.custom.allowDismiss"]);self.assertEqual(values["crewRoll.custom.maxAttempts"],0)
    def test_review_explains_runtime_usage_and_confirmation_bypass_separately(self):
        self.preview({"version":17,"favorUsageCount":3,"skipConfirmation":True})
        report=json.loads(self.app.ui.profiles.importReviewText.value)
        self.assertIn("ledger",report["unresolvedReasons"]["favorUsageCount"].lower())
        self.assertIn("confirmation",report["unresolvedReasons"]["skipConfirmation"].lower())
    def test_legacy_job_bounds_keep_explicit_enable_and_cached_values(self):
        source={"version":17,"jobLimits":True,"jobMinLevel":2,"jobMaxLevel":10,"jobMinEnergy":2,"jobMaxEnergy":25}
        self.assertTrue(self.preview(source)[0]);values=self.app.staged["values"]
        self.assertTrue(values["jobs.custom.limitsEnabled"]);self.assertEqual(values["jobs.custom.minLevel"],2)
        self.assertEqual(values["jobs.custom.maxLevel"],10);self.assertEqual(values["jobs.custom.minCost"],2);self.assertEqual(values["jobs.custom.maxCost"],25)
        self.assertFalse(values["jobs.enabled"])
        source["jobLimits"]=False;self.assertTrue(self.preview(source)[0])
        self.assertFalse(self.app.staged["values"]["jobs.custom.limitsEnabled"])
        self.assertEqual(self.app.staged["values"]["jobs.custom.maxCost"],25)
    def test_inverted_enabled_legacy_job_bounds_are_named_and_not_staged(self):
        for source in ({"version":17,"jobLimits":True,"jobMinLevel":10,"jobMaxLevel":2},
            {"version":17,"jobLimits":True,"jobMinEnergy":25,"jobMaxEnergy":2}):
            accepted,reason=self.preview(source);self.assertFalse(accepted);self.assertIn("jobMax",reason)
            self.assertIsNone(self.app.staged)
    def test_legacy_city_id_is_staged_without_substituting_an_unknown_city(self):
        self.assertTrue(self.preview({"version":17,"jobCity":"city_ashport"})[0])
        self.assertEqual(self.app.staged["values"]["jobs.custom.city"],"city_ashport")
        self.assertFalse(self.app.staged["values"]["jobs.enabled"])
        accepted,reason=self.preview({"version":17,"jobCity":"city_missing"})
        self.assertFalse(accepted);self.assertIn("jobCity",reason);self.assertIsNone(self.app.staged)
    def test_legacy_native_job_policies_and_named_mastery_target_translate_without_enabling(self):
        for goal in ("Job count","Highest tier","Mastery"):
            self.assertTrue(self.preview({"version":17,"jobMode":goal,"masteryTarget":"Silver"})[0])
            self.assertEqual(self.app.staged["values"]["jobs.policy"],goal)
            self.assertEqual(self.app.staged["values"]["jobs.custom.masteryTarget"],"Silver")
            self.assertFalse(self.app.staged["values"]["jobs.enabled"])
    def test_legacy_energy_reserve_maps_once_to_shared_preference_and_stays_inactive(self):
        self.assertTrue(self.preview({"version":17,"energyReserve":25})[0])
        self.assertEqual(self.app.staged["values"]["shared.energyReserve"],25)
        self.assertFalse(self.app.staged["values"]["jobs.enabled"])
        self.assertFalse(self.app.staged["values"]["heists.enabled"])
    def test_operation_bounds_and_selected_id_map_stage_without_enabling(self):
        source={'version':17,'operationLimits':True,'operationMinLevel':3,'operationMaxLevel':8,
            'minOperationHours':.5,'maxOperationHours':1,'operationMinCrateRarity':4,
            'operationSelection':'Only selected','selectedOperations':{'op_truck':True,'op_fence':True,'op_ignored':False}}
        accepted,reason=self.preview(source);self.assertTrue(accepted,reason);values=self.app.staged['values']
        for key,want in [('limitsEnabled',True),('minLevel',3),('maxLevel',8),('minHours',.5),('maxHours',1),('minCrateRarity',4),('selection','Only selected'),('selectedIds','op_fence,op_truck')]:
            self.assertEqual(values['operations.custom.'+key],want)
        self.assertFalse(values['operations.enabled']);self.assertTrue(self.app.model.paused)
        self.assertEqual(len(self.f.base.storage.data),0)
    def test_operation_rate_labels_translate_and_inverted_ranges_block(self):
        for mode in ('XP / hour','Shortest duration','Balanced'):
            accepted,reason=self.preview({'version':17,'operationMode':mode});self.assertTrue(accepted,reason)
            self.assertEqual(self.app.staged['values']['operations.policy'],mode)
        for source in ({'version':17,'operationLimits':True,'operationMinLevel':10,'operationMaxLevel':2},
            {'version':17,'operationLimits':True,'minOperationHours':5,'maxOperationHours':2}):
            self.assertFalse(self.preview(source)[0]);self.assertIsNone(self.app.staged)
    def test_invalid_selected_map_and_oversized_operation_lists_remain_reviewable(self):
        for selected in ({'op_a':'true'},[True],{'bad,id':True},{'op_'+str(i):True for i in range(65)}):
            accepted,reason=self.preview({'version':17,'selectedOperations':selected})
            self.assertFalse(accepted);self.assertIn('selectedOperations',reason);self.assertIsNone(self.app.staged)
            self.assertIsNotNone(self.app.importReview.original.selectedOperations)
    def test_property_selection_bounds_and_highest_goal_import_inactive(self):
        source={'version':17,'propertyMode':'Highest tier','propertyLimits':True,'propertyMinLevel':3,'propertyMaxLevel':8,
            'propertySelection':'Only selected','selectedProperties':{'p_city':True,'p_other':True,'p_ignored':False}}
        accepted,reason=self.preview(source);self.assertTrue(accepted,reason);values=self.app.staged['values']
        for key,want in [('limitsEnabled',True),('minLevel',3),('maxLevel',8),('selection','Only selected'),('selectedIds','p_city,p_other')]:
            self.assertEqual(values['properties.custom.'+key],want)
        self.assertEqual(values['properties.policy'],'Highest tier');self.assertFalse(values['properties.enabled'])
        self.assertTrue(self.app.model.paused);self.assertEqual(len(self.f.base.storage.data),0)
    def test_inverted_property_bounds_and_malformed_selection_hold_import(self):
        for source in ({'version':17,'propertyLimits':True,'propertyMinLevel':10,'propertyMaxLevel':2},
            {'version':17,'selectedProperties':{'p_city':'true'}}):
            accepted,reason=self.preview(source);self.assertFalse(accepted);self.assertIsNone(self.app.staged)
            self.assertIn('property' if 'propertyLimits' in source else 'selectedProperties',reason)
    def test_supported_safehouse_and_skill_caps_import_without_enabling(self):
        accepted,reason=self.preview({'version':17,'safehouseCap':12,'skillCap':30})
        self.assertTrue(accepted,reason)
        self.assertEqual(self.app.staged['values']['safehouse.custom.maxTier'],12)
        self.assertEqual(self.app.staged['values']['skills.custom.maxAllocations'],30)
        self.assertFalse(self.app.staged['values']['safehouse.enabled']);self.assertFalse(self.app.staged['values']['skills.enabled'])
    def test_unsupported_safehouse_and_zero_skill_caps_are_retained_for_review(self):
        for key,value in [('safehouseCap',19),('skillCap',0)]:
            accepted,reason=self.preview({'version':17,key:value});self.assertFalse(accepted);self.assertIn(key,reason)
            self.assertEqual(self.app.importReview.original[key],value);self.assertIsNone(self.app.staged)
    def test_legacy_sale_exclusions_map_without_losing_false_entries_or_enabling(self):
        source={'version':17,'marketSellFromCollection':False,'marketSellBlockedItems':{'w_baton':True,'v_car':False},
            'marketSellBlockedKinds':{'weapon':True,'armor':True},
            'marketSellBlockedRarities':{'Legendary':True,'Contraband':True,'Common':False}}
        accepted,reason=self.preview(source);self.assertTrue(accepted,reason)
        values=self.app.staged['values']
        self.assertEqual(values['marketSell.custom.excludedItems'],'w_baton')
        self.assertEqual(values['marketSell.custom.excludedKinds'],'armor,weapon')
        self.assertEqual(values['marketSell.custom.excludedRarities'],'5,9')
        self.assertFalse(values['marketSell.enabled']);self.assertFalse(values['marketSell.custom.fromCollection'])
        self.assertEqual(values['marketSell.custom.maxListAttempts'],0)
        self.assertFalse(self.app.importReview.original.marketSellBlockedItems.v_car)
        self.assertEqual(len(self.f.base.storage.data),0)
    def test_sale_exclusion_unknown_names_bad_types_and_oversized_lists_hold_review(self):
        for key,value in [('marketSellBlockedKinds',{'unknown_kind':True}),('marketSellBlockedRarities',{'Unknown':True}),
            ('marketSellBlockedRarities',{'5':True}),('marketSellBlockedItems',{'w_baton':'true'}),
            ('marketSellBlockedItems',{'bad,id':True}),('marketSellBlockedItems',{'w_'+str(i):True for i in range(65)})]:
            accepted,reason=self.preview({'version':17,key:value});self.assertFalse(accepted);self.assertIn(key,reason)
            self.assertIsNone(self.app.staged);self.assertIsNotNone(self.app.importReview.original[key])
    def test_imported_sale_exclusions_reach_actual_app_planner_before_dispatch(self):
        from test_market_sell_runtime import MarketSellRuntimeTests
        for legacy,value,current in [('marketSellBlockedItems','w_baton','excludedItems'),
            ('marketSellBlockedKinds','weapon','excludedKinds'),('marketSellBlockedRarities','Legendary','excludedRarities')]:
            with self.subTest(legacy=legacy):
                accepted,reason=self.preview({'version':17,legacy:{value:True}});self.assertTrue(accepted,reason)
                f=MarketSellRuntimeTests();f.setUp()
                try:
                    f.choose();raw=f.raw();f.warm(raw)
                    profile=lua_table(f.h.lua,plain(self.app.staged));self.assertTrue(f.app.ApplyProfile(f.app,profile)[0])
                    self.assertTrue(f.app.model.paused);f.choose();f.app.Step(f.app,raw);f.executor.Drain(f.executor)
                    self.assertEqual(len(f.executor.calls),0)
                    self.assertEqual(f.tab.transactions.ListingAttempts(f.tab.transactions)[0],0)
                    f.app.Set(f.app,'marketSell.custom.'+current,'');f.app.Step(f.app,raw);f.executor.Drain(f.executor)
                    self.assertEqual(len(f.executor.calls),1)
                finally:f.tearDown()
    def test_all_nine_legacy_rarity_names_map_to_current_numeric_exclusions(self):
        names=['Common','Uncommon','Rare','Epic','Legendary','Mythic','Secret','Forbidden','Contraband']
        accepted,reason=self.preview({'version':17,'marketSellBlockedRarities':{name:True for name in names}})
        self.assertTrue(accepted,reason);self.assertEqual(self.app.staged['values']['marketSell.custom.excludedRarities'],'1,2,3,4,5,6,7,8,9')
    def test_imported_rarity_exclusion_blocks_collection_withdrawal_and_attempt_charge(self):
        from test_market_sell_runtime import MarketSellRuntimeTests
        accepted,reason=self.preview({'version':17,'marketSellBlockedRarities':{'Legendary':True}});self.assertTrue(accepted,reason)
        f=MarketSellRuntimeTests();f.setUp()
        try:
            f.choose()
            for key,value in [('fromCollection',True),('maxWithdraw',1),('maxWithdrawAttempts',1)]:f.app.Set(f.app,'marketSell.custom.'+key,value)
            raw=f.raw(loose=1,collected=2);f.warm(raw)
            self.assertTrue(f.app.ApplyProfile(f.app,lua_table(f.h.lua,plain(self.app.staged)))[0]);f.choose()
            for key,value in [('fromCollection',True),('maxWithdraw',1),('maxWithdrawAttempts',1)]:f.app.Set(f.app,'marketSell.custom.'+key,value)
            f.app.Step(f.app,raw);f.executor.Drain(f.executor)
            self.assertEqual(len(f.executor.calls),0);self.assertIsNone(f.tab.transactions.Active(f.tab.transactions))
            self.assertEqual(f.tab.transactions.WithdrawAttempts(f.tab.transactions)[0],0)
            f.app.Set(f.app,'marketSell.custom.excludedRarities','');f.app.Step(f.app,raw);f.executor.Drain(f.executor)
            self.assertEqual(len(f.executor.calls),1);self.assertEqual(f.executor.calls[1].remote,'CollectionAction')
        finally:f.tearDown()
    def test_ordinary_combat_payout_and_win_thresholds_stage_without_permission_or_allowance(self):
        source={'version':17,'combatMinimum':250000000,'combatMinWinRate':95,'combatMinWinChance':97}
        accepted,reason=self.preview(source);self.assertTrue(accepted,reason);values=self.app.staged['values']
        for key,want in [('minimumPayout',250000000),('minWinRate',95),('minWinChance',97)]:
            self.assertEqual(values['combat.custom.'+key],want)
        self.assertFalse(values['combat.enabled']);self.assertFalse(values['warCombat.enabled'])
        self.assertFalse(values['combat.custom.allowScout']);self.assertEqual(values['combat.custom.maxAttackSpend'],0)
        self.assertEqual(values['combat.custom.maxScoutSpend'],0);self.assertTrue(self.app.model.paused)
        self.assertEqual(len(self.f.base.storage.data),0)
    def test_invalid_combat_thresholds_preserve_original_intent_for_review(self):
        for key,value in [('combatMinimum',-1),('combatMinimum',1.5),('combatMinWinRate',101),
                ('combatMinWinChance',-1),('combatMinWinChance','95'),('combatMinWinRate',True)]:
            accepted,reason=self.preview({'version':17,key:value});self.assertFalse(accepted);self.assertIn(key,reason)
            self.assertIsNone(self.app.staged);self.assertEqual(self.app.importReview.original[key],value)
    def test_unsupported_combat_limits_and_scout_permission_are_not_imported_by_threshold_aliases(self):
        for key,value in [('combatScout',True),('combatMinSamples',5)]:
            accepted,reason=self.preview({'version':17,'combatMinimum':200000000,key:value})
            self.assertFalse(accepted);self.assertIn(key,reason);self.assertIsNone(self.app.staged)
            self.assertEqual(self.app.importReview.mapped['combat.custom.minimumPayout'],200000000)
    def test_imported_minimum_payout_reaches_actual_combat_planner_before_dispatch(self):
        from test_player_combat_planner_app import PlayerCombatPlannerAppTests
        accepted,reason=self.preview({'version':17,'combatMinimum':200000000});self.assertTrue(accepted,reason)
        f=PlayerCombatPlannerAppTests();f.setUp()
        try:
            self.assertTrue(f.app.ApplyProfile(f.app,lua_table(f.h.lua,plain(self.app.staged)))[0])
            self.assertTrue(f.app.model.paused);self.assertEqual(len(f.f.executor.queued),0)
            for key,value in [('minSamples',0),('maxAttackSpend',5),('maxScoutSpend',5),('maxStaminaCost',5)]:
                self.assertTrue(f.app.Set(f.app,'combat.custom.'+key,value)[0])
            f.app.Set(f.app,'combat.enabled',True);f.app.Resume(f.app);f.f.step()
            self.assertEqual(len(f.f.executor.queued),0);self.assertEqual(f.f.executor.calls,0)
            f.app.Set(f.app,'combat.custom.minimumPayout',0);f.f.step()
            self.assertEqual(len(f.f.executor.queued),1);f.f.send();self.assertEqual(f.f.executor.calls,1)
        finally:f.tearDown()
    def test_enabled_legacy_combat_ranges_preserve_defaults_and_separate_feature_caps(self):
        source={'version':17,'combatLimits':True,'combatMinTargetLevel':20,'combatMaxTargetLevel':200,
            'combatMinStaminaCost':2,'combatMaxStaminaCost':4,'combatMinSamples':5}
        accepted,reason=self.preview(source);self.assertTrue(accepted,reason);values=self.app.staged['values']
        for feature in ('combat','warCombat'):
            for key,want in [('minTargetLevel',20),('maxTargetLevel',200),('minStaminaCost',2),('maxStaminaCost',4)]:
                self.assertEqual(values[feature+'.custom.'+key],want)
            self.assertFalse(values[feature+'.enabled']);self.assertFalse(values[feature+'.custom.allowScout'])
            self.assertEqual(values[feature+'.custom.maxAttackSpend'],0);self.assertEqual(values[feature+'.custom.maxScoutSpend'],0)
        self.assertEqual(values['combat.custom.minSamples'],5)
        self.assertTrue(self.preview({'version':17,'combatLimits':True})[0]);values=self.app.staged['values']
        self.assertEqual(values['combat.custom.maxTargetLevel'],10000);self.assertEqual(values['combat.custom.minSamples'],1)
        self.assertEqual(values['combat.custom.maxStaminaCost'],5)
    def test_inactive_cached_combat_ranges_remain_unresolved_instead_of_becoming_active(self):
        for switch in (None,False):
            source={'version':17,'combatMinStaminaCost':2,'combatMaxTargetLevel':200}
            if switch is not None:source['combatLimits']=switch
            accepted,reason=self.preview(source);self.assertFalse(accepted);self.assertIn('combatMinStaminaCost',reason)
            self.assertIsNone(self.app.staged);self.assertEqual(self.app.importReview.original.combatMinStaminaCost,2)
    def test_invalid_enabled_combat_ranges_are_named_and_never_staged(self):
        for changes in ({'combatMinTargetLevel':200,'combatMaxTargetLevel':20},
                {'combatMinStaminaCost':4,'combatMaxStaminaCost':2},{'combatMinSamples':33},
                {'combatMinSamples':0},{'combatMinStaminaCost':1.5},{'combatMinStaminaCost':6}):
            accepted,reason=self.preview({'version':17,'combatLimits':True,**changes})
            self.assertFalse(accepted);self.assertIsNone(self.app.staged);self.assertIn('combat',reason)
    def test_imported_enabled_cost_range_reaches_actual_combat_planner(self):
        from test_player_combat_planner_app import PlayerCombatPlannerAppTests
        accepted,reason=self.preview({'version':17,'combatLimits':True,'combatMinStaminaCost':2})
        self.assertTrue(accepted,reason);f=PlayerCombatPlannerAppTests();f.setUp()
        try:
            self.assertTrue(f.app.ApplyProfile(f.app,lua_table(f.h.lua,plain(self.app.staged)))[0])
            for key,value in [('minimumPayout',0),('minSamples',0),('maxAttackSpend',5)]:
                f.app.Set(f.app,'combat.custom.'+key,value)
            f.app.Set(f.app,'combat.enabled',True);f.app.Resume(f.app);f.f.step()
            self.assertEqual(len(f.f.executor.queued),0);self.assertEqual(f.f.executor.calls,0)
            f.app.Set(f.app,'combat.custom.minStaminaCost',1);f.f.step()
            self.assertEqual(len(f.f.executor.queued),1)
        finally:f.tearDown()
    def test_daily_repeat_option_imports_explicit_false_without_enabling_fights(self):
        accepted,reason=self.preview({'version':17,'combatDailyOnly':False});self.assertTrue(accepted,reason)
        values=self.app.staged['values'];self.assertIs(values['combat.custom.dailyOnly'],False)
        self.assertFalse(values['combat.enabled']);self.assertFalse(values['combat.custom.allowScout'])
        self.assertEqual(values['combat.custom.maxAttackSpend'],0)
        self.assertTrue(self.preview({'version':17,'combatDailyOnly':True})[0])
        self.assertTrue(self.app.staged['values']['combat.custom.dailyOnly'])
    def test_reviewed_source_phases_preserve_even_explicit_legacy_default_without_scout_permission(self):
        for old,new in [('Saved history','Saved only'),('History then discover','Saved and new')]:
            accepted,reason=self.preview({'version':17,'combatSource':old});self.assertTrue(accepted,reason)
            values=self.app.staged['values'];self.assertEqual(values['combat.custom.targetSource'],new)
            self.assertFalse(values['combat.enabled']);self.assertFalse(values['combat.custom.allowScout'])
            self.assertEqual(values['combat.custom.maxScoutSpend'],0)
        accepted,reason=self.preview({'version':17,'combatSource':'Scout new hit-list targets'})
        self.assertFalse(accepted);self.assertIn('combatSource',reason);self.assertIsNone(self.app.staged)
        self.assertIn('Scout',self.app.importReview.unresolvedReasons.combatSource)
    def test_daily_option_and_source_phase_invalid_types_stay_reviewable(self):
        for key,value in [('combatDailyOnly','false'),('combatDailyOnly',0),('combatSource',False),('combatSource','Unknown phase')]:
            accepted,reason=self.preview({'version':17,key:value});self.assertFalse(accepted);self.assertIn(key,reason)
            self.assertEqual(self.app.importReview.original[key],value);self.assertIsNone(self.app.staged)
    def test_imported_saved_only_phase_reaches_actual_planner_without_paying_for_scout(self):
        from test_player_combat_planner_app import PlayerCombatPlannerAppTests
        accepted,reason=self.preview({'version':17,'combatSource':'Saved history'});self.assertTrue(accepted,reason)
        f=PlayerCombatPlannerAppTests();f.setUp()
        try:
            self.assertTrue(f.app.ApplyProfile(f.app,lua_table(f.h.lua,plain(self.app.staged)))[0])
            for key,value in [('minimumPayout',0),('minSamples',0),('maxAttackSpend',5)]:f.app.Set(f.app,'combat.custom.'+key,value)
            f.app.Set(f.app,'combat.enabled',True);f.app.Resume(f.app);f.f.step()
            self.assertEqual(len(f.f.executor.queued),0);self.assertEqual(f.f.executor.calls,0)
            f.app.Set(f.app,'combat.custom.targetSource','Saved and new');f.f.step()
            self.assertEqual(len(f.f.executor.queued),1);f.f.send();self.assertEqual(f.f.executor.calls,1)
        finally:f.tearDown()
    def test_reviewed_legacy_target_priority_maps_both_modes_inertly(self):
        for priority in ('Risk-adjusted value','Value / stamina','Recent payout','Safest history','Highest eligible level'):
            accepted,reason=self.preview({'version':17,'combatPriority':priority});self.assertTrue(accepted,reason)
            values=self.app.staged['values']
            for feature in ('combat','warCombat'):
                self.assertEqual(values[feature+'.custom.targetPriority'],priority)
                self.assertFalse(values[feature+'.enabled']);self.assertFalse(values[feature+'.custom.allowScout'])
                self.assertEqual(values[feature+'.custom.maxAttackSpend'],0)
        accepted,reason=self.preview({'version':17,'combatPriority':'Unknown priority'})
        self.assertFalse(accepted);self.assertIn('combatPriority',reason);self.assertIsNone(self.app.staged)
    def test_old_stationed_crew_cap_stages_without_allowance_or_activation(self):
        accepted,reason=self.preview({'version':17,'stationMaxStationed':4});self.assertTrue(accepted,reason)
        self.assertEqual(self.app.staged['values']['station.custom.maxStationed'],4)
        self.assertEqual(self.app.staged['values']['station.custom.maxAttempts'],0)
        self.assertFalse(self.app.staged['values']['station.enabled'])
        self.assertFalse(self.preview({'version':17,'stationMaxStationed':46})[0])
if __name__=="__main__":unittest.main()
