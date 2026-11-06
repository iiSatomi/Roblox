"""Real tab-owned durable custody flows; no native transport is invoked."""
import unittest

from engine_harness import Harness, ROOT, lua_table


class MarketTransactionFlowTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        deps = {p.stem: self.h.load(p.relative_to(ROOT).as_posix())
                for p in (ROOT / "src/tabs/blackMarket").glob("*.luau")
                if p.name != "Module.luau"}
        for name, folder in (("MarketEarningsState", "game"),
                ("MarketEarnings", "features"),
                ("MarketEarningsEvidence", "features"),
                ("MarketBrowse", "features"), ("MarketPrices", "features"),
                ("MarketRap", "features"), ("MarketReadRuntime", "features")):
            deps[name] = self.h.load(f"src/{folder}/{name}.luau")
        self.module = deps["MarketTransactions"]
        self.tab = self.h.load("src/tabs/blackMarket/Module.luau").new(
            lua_table(self.h.lua, deps))
        self.scope = lua_table(self.h.lua, self.h.session)
        self.storage = self.h.lua.execute("""return {
            strictRecovery = true, data = {}, fail = false, writes = 0,
            Read = function(self, key) return self.data[key] end,
            Write = function(self, key, value)
                if self.fail then return false end
                self.writes = self.writes + 1
                self.data[key] = value; return true
            end }""")
        self.tx = self.restart()

    def restart(self):
        tx, reason = self.tab.NewTransactions(self.tab, self.storage, self.scope)
        self.assertIsNone(reason)
        return tx

    def raw(self, kind, phase="before", revision=4, server=1000,
            session=None, captured=10):
        loose = 1 if phase == "before" else (3 if kind == "withdraw" else 2)
        if phase == "listed":
            loose -= 3 if kind == "withdraw" else 1
        raw = self.h.snapshot(revision=revision, captured_at=captured, native={
            "fullSync": True, "serverNow": server, "level": 50,
            "inventory": {"w_baton": loose,
                          "gold_bar": 12 if kind == "buy" and phase != "before" else 20},
            "inventoryBound": {"w_baton": 0, "gold_bar": 2},
            "collection": {"w_baton": 12 if phase == "before" else 10,
                           "w_baton@2": 1},
            "collectionBound": {}, "derived": {"marketShop": False},
            "market": {"shopUntil": 9000, "listings": {}}})
        if session is not None:
            raw.session = session
        if phase == "listed":
            qty = 3 if kind == "withdraw" else 1
            raw.native.market.listings.L2 = lua_table(self.h.lua, {
                "state": "live", "item": "w_baton", "price": 13,
                "indexed": 1, "qty": qty, "left": qty, "createdAt": 1003,
                "itemOrigin": {"total": qty, "free": 0}})
        return raw

    def views(self, raw, kind, first=False):
        header = {field: raw[field] for field in
                  ("session", "account", "place", "release", "revision", "capturedAt")}
        qty = 3 if kind == "withdraw" else 1
        custody = dict(header, itemId="w_baton", loose=raw.native.inventory.w_baton,
            bound=0, collected=raw.native.collection.w_baton,
            collectedBound=0, collectedTotal=raw.native.collection.w_baton + 1,
            checkpointFloor=10, collectionSurplus=3, reservedLoose=1,
            quantity=qty, withdraw=2 if first else 0)
        quote = dict(header, itemId="w_baton", quantity=qty,
            withdraw=2 if first else 0, ask=13, fee=1, net=12)
        listings, reason = self.tab.ReadListings(self.tab, raw,
            lua_table(self.h.lua, header))
        self.assertIsNone(reason)
        terms = {"release": raw.release, "minPrice": 2, "maxPrice": 9999999,
                 "maxSlots": 5, "rentAllowance": 0, "permanent": False}
        settings = {"minNet": 5, "minMargin": 2, "maxListAttempts": 1,
                    "maxWithdraw": 5, "maxAttempts": 1}
        return [lua_table(self.h.lua, x) for x in
                (custody, quote, listings, terms, settings)]

    def first_proposal(self, kind, before):
        if kind == "withdraw":
            proposal, reason = self.tab.AssessCollectionWithdraw(self.tab,
                *self.views(before, kind, first=True), 0, before.capturedAt + 1)
        else:
            quote = lua_table(self.h.lua, {"hypothetical": True,
                "listingId": "L1", "itemId": "w_baton", "kind": "weapon",
                "rarity": 5, "buy": 8, "ask": 13, "margin": 4,
                "capturedAt": before.capturedAt})
            context = lua_table(self.h.lua, {field: before[field] for field in
                ("session", "account", "place", "release", "revision", "capturedAt")})
            proposal, reason = self.h.load(
                "src/tabs/blackMarket/MarketFlipPreflight.luau").assess(
                quote, before, context, lua_table(self.h.lua, {
                    "release": before.release, "minLevel": 20, "maxSlots": 5}),
                lua_table(self.h.lua, {"maxBuy": 10, "sessionBudget": 20,
                    "goldReserve": 5, "maxAttempts": 1, "transactionOpen": False,
                    "blockedItems": {}, "blockedKinds": {}, "blockedRarities": {}}),
                0, 0, before.capturedAt + 1)
        self.assertIsNone(reason)
        return proposal

    def runtime_buy(self):
        before=self.raw('buy');p=self.first_proposal('buy',before)
        p.preflightOnly=None;p.actionKey='market-buy:a:1:L1'
        p.resources=lua_table(self.h.lua,{'gold_bar':8})
        p.intent.sourceKey='a'*64;p.intent.ownerGeneration=self.tx.generation+1
        p.intent.attemptedBefore=0;p.intent.spentBefore=0
        p.intent.maxAttempts=1;p.intent.sessionBudget=8
        return p,before

    def test_runtime_buy_persists_independent_usage_and_refuses_second_authorization(self):
        p,before=self.runtime_buy()
        self.assertTrue(self.tx.PrepareRuntimeBuy(self.tx,p,before)[0])
        self.assertEqual(self.tx.BuyUsage(self.tx).attempted,0)
        self.assertTrue(self.tx.AuthorizeRuntimeBuy(self.tx,p)[0])
        self.tx=self.restart()
        self.assertEqual(self.tx.BuyUsage(self.tx).attempted,1)
        self.assertEqual(self.tx.BuyUsage(self.tx).spent,8)
        self.assertFalse(self.tx.AuthorizeRuntimeBuy(self.tx,p)[0])
        self.assertEqual(self.tx.BuyUsage(self.tx).spent,8)

    def test_runtime_buy_failed_authorization_write_does_not_charge(self):
        p,before=self.runtime_buy();self.assertTrue(self.tx.PrepareRuntimeBuy(self.tx,p,before)[0])
        self.storage.fail=True
        self.assertFalse(self.tx.AuthorizeRuntimeBuy(self.tx,p)[0])
        self.assertEqual(self.tx.BuyUsage(self.tx).spent,0)
        self.assertEqual(self.tx.Active(self.tx).stage,'prepared')

    def test_runtime_buy_rejects_mismatched_gold_resources_and_stale_totals(self):
        p,before=self.runtime_buy();p.resources.gold_bar=7
        self.assertFalse(self.tx.PrepareRuntimeBuy(self.tx,p,before)[0])
        p.resources.gold_bar=8;p.intent.spentBefore=1
        self.assertFalse(self.tx.PrepareRuntimeBuy(self.tx,p,before)[0])
        self.assertIsNone(self.tx.Active(self.tx))

    def test_runtime_buy_corrupt_charged_usage_blocks_restart(self):
        p,before=self.runtime_buy();self.tx.PrepareRuntimeBuy(self.tx,p,before);self.tx.AuthorizeRuntimeBuy(self.tx,p)
        self.storage.data[self.tx.key].buySpent=0
        tx,reason=self.tab.NewTransactions(self.tab,self.storage,self.scope)
        self.assertIsNone(tx)
        self.assertIn('Corrupt',reason)

    def test_runtime_buy_definitely_unsent_refunds_exact_own_exposure_once(self):
        p,before=self.runtime_buy();self.tx.PrepareRuntimeBuy(self.tx,p,before);self.tx.AuthorizeRuntimeBuy(self.tx,p)
        self.assertTrue(self.tx.RecordRuntimeUnsent(self.tx,p.actionKey,p.intent.ownerGeneration)[0])
        review=self.tx.RuntimeUnsentReview(self.tx)[0]
        self.assertTrue(self.tx.ReleaseRuntimeUnsent(self.tx,review)[0])
        self.assertEqual(self.tx.BuyUsage(self.tx).attempted,0)
        self.assertEqual(self.tx.BuyUsage(self.tx).spent,0)
        self.assertFalse(self.tx.ReleaseRuntimeUnsent(self.tx,review)[0])
        self.assertIsNotNone(self.tx.RuntimeUnsentReceipt(self.tx,p.actionKey,p.intent.ownerGeneration))

    def test_runtime_buy_return_and_exact_effect_retain_charged_item_owner(self):
        p,before=self.runtime_buy();self.tx.PrepareRuntimeBuy(self.tx,p,before);self.tx.AuthorizeRuntimeBuy(self.tx,p)
        self.assertTrue(self.tx.RecordRuntimeReturn(self.tx,p.actionKey,p.intent.ownerGeneration,lua_table(self.h.lua,{'ok':True}))[0])
        self.assertFalse(self.tx.RecordRuntimeUnsent(self.tx,p.actionKey,p.intent.ownerGeneration)[0])
        after=self.raw('buy','observed',revision=5,server=1002)
        self.assertEqual(self.tx.Reconcile(self.tx,after)[0],'observed')
        self.assertEqual(self.tx.BuyUsage(self.tx).spent,8)
        self.assertFalse(self.tx.ClearObserved(self.tx)[0])

    def test_missing_half_of_buy_usage_cannot_reset_spend_on_reload(self):
        p,before=self.runtime_buy();self.tx.PrepareRuntimeBuy(self.tx,p,before);self.tx.AuthorizeRuntimeBuy(self.tx,p)
        self.tx.RecordRuntimeReturn(self.tx,p.actionKey,p.intent.ownerGeneration,lua_table(self.h.lua,{'ok':False}))
        after=self.raw('buy',revision=5,server=1002)
        review=self.tx.RejectedRuntimeReview(self.tx,after)[0]
        self.assertTrue(self.tx.ReleaseRejectedRuntimeList(self.tx,review,after)[0])
        self.storage.data[self.tx.key].buySpent=None
        owner,reason=self.tab.NewTransactions(self.tab,self.storage,self.scope)
        self.assertIsNone(owner);self.assertIn('Corrupt',reason)

    def prepare(self, kind, tx=None):
        tx = tx if tx is not None else self.tx
        self.assertTrue(callable(tx.PrepareWithdraw if kind == "withdraw" else tx.PrepareBuy))
        before = self.raw(kind)
        proposal = self.first_proposal(kind, before)
        method = tx.PrepareWithdraw if kind == "withdraw" else tx.PrepareBuy
        ok, reason = method(tx, proposal, before)
        self.assertTrue(ok, reason)
        return proposal, before

    def observe(self, kind):
        self.prepare(kind)
        self.assertTrue(self.tx.MarkSending(self.tx)[0])
        self.tx = self.restart()
        after = self.raw(kind, "observed", revision=0, server=1002,
                         session="restart", captured=1)
        self.assertEqual(self.tx.Reconcile(self.tx, after)[0], "observed")
        self.tx = self.restart()
        return after

    def followup(self, kind, raw=None, now=2):
        if raw is None:
            raw = self.observe(kind)
        self.assertTrue(callable(self.tx.ListingContext))
        view, reason = self.tx.ListingContext(self.tx, raw, now)
        self.assertIsNone(reason)
        preflight = (self.tab.AssessSellAfterWithdraw if kind == "withdraw"
                     else self.tab.AssessFlipList)
        proposal, reason = preflight(self.tab, view,
            *self.views(raw, kind), now)
        self.assertIsNone(reason)
        return view, proposal, raw

    def test_withdraw_and_buy_complete_restart_lifecycle_without_transport(self):
        for kind in ("withdraw", "buy"):
            with self.subTest(kind=kind):
                view, proposal, raw = self.followup(kind)
                self.assertEqual(view.stage, "withdrawn" if kind == "withdraw" else "bought")
                self.assertFalse(self.tx.ClearObserved(self.tx)[0])
                ok, reason = self.tx.PrepareFollowupList(self.tx, proposal, raw, 2)
                self.assertTrue(ok, reason)
                record = self.tx.Active(self.tx)
                self.assertEqual(record.origin.kind, kind)
                self.assertEqual(record.listAttempts, 1)
                self.assertEqual(self.tx.Reconcile(self.tx, raw)[0], "prepared")
                self.assertTrue(self.tx.MarkSending(self.tx)[0])
                self.tx = self.restart()
                listed = self.raw(kind, "listed", revision=0, server=1004,
                                  session="second-restart", captured=0)
                self.assertEqual(self.tx.Reconcile(self.tx, listed)[0], "observed")
                self.assertTrue(self.tx.ClearObserved(self.tx)[0])
                self.tx = self.restart()
                self.assertIsNone(self.tx.Active(self.tx))
        self.assertEqual(len(self.h.transport.sent), 0)

    def test_prepared_uncertain_and_other_transactions_cannot_be_bypassed(self):
        proposal, before = self.prepare("buy")
        self.assertEqual(self.tx.Reconcile(self.tx,
            self.raw("buy", "observed", revision=5, server=1002))[0], "prepared")
        self.assertFalse(self.tx.PrepareBuy(self.tx, proposal, before)[0])
        self.assertFalse(self.tx.PrepareWithdraw(self.tx, proposal, before)[0])
        self.assertFalse(self.tx.PrepareOwnedList(self.tx, proposal, before)[0])
        self.assertFalse(self.tx.PrepareRent(self.tx, proposal, before)[0])
        self.assertTrue(self.tx.MarkSending(self.tx)[0])
        self.assertEqual(self.tx.Reconcile(self.tx, self.raw("buy", revision=5,
            server=1002))[0], "uncertain")
        self.assertIsNone(self.tx.ListingContext(self.tx, before, 11)[0])
        self.assertFalse(self.tx.PrepareFollowupList(self.tx, proposal, before, 11)[0])
        self.assertFalse(self.tx.ClearObserved(self.tx)[0])

    def test_changed_followup_identity_quantity_price_and_revision_stay_held(self):
        for kind in ("withdraw", "buy"):
            self.setUp()
            _, proposal, raw = self.followup(kind)
            changes = [("itemId", "w_other"), ("quantity", 2), ("ask", 14)]
            changes += ([("collectionWithdrawn", 1)] if kind == "withdraw" else
                        [("sourceListingId", "other"), ("buyPrice", 7)])
            for key, value in changes:
                old = proposal.intent[key]
                proposal.intent[key] = value
                self.assertFalse(self.tx.PrepareFollowupList(self.tx, proposal, raw, 2)[0], key)
                proposal.intent[key] = old
            for key, value in (("feature", "jobs"), ("preflightOnly", False),
                               ("revision", 99), ("session", "other")):
                old = proposal[key]
                proposal[key] = value
                self.assertFalse(self.tx.PrepareFollowupList(self.tx, proposal, raw, 2)[0], key)
                proposal[key] = old
            self.assertEqual(self.tx.Active(self.tx).stage, "observed")

    def test_listing_context_rejects_changed_custody_and_stale_full_sync(self):
        for kind in ("withdraw", "buy"):
            self.setUp()
            raw = self.observe(kind)
            for map_name, key, value in (("inventory", "w_baton", 9),
                    ("inventoryBound", "w_baton", 1),
                    ("inventory", "gold_bar", 11)):
                old = raw.native[map_name][key]
                raw.native[map_name][key] = value
                self.assertIsNone(self.tx.ListingContext(self.tx, raw, 2)[0])
                raw.native[map_name][key] = old
            if kind == "withdraw":
                raw.native.collection["w_baton@2"] = 2
                self.assertIsNone(self.tx.ListingContext(self.tx, raw, 2)[0])
                raw.native.collection["w_baton@2"] = 1
            for field, value in (("account", "other"), ("session", ""),
                                  ("capturedAt", -1), ("capturedAt", 4),
                                  ("capturedAt", float("nan"))):
                old = raw[field]
                raw[field] = value
                self.assertIsNone(self.tx.ListingContext(self.tx, raw, 2)[0])
                raw[field] = old
            self.assertIsNone(self.tx.ListingContext(self.tx, raw, 20)[0])
            raw.native.fullSync = False
            self.assertIsNone(self.tx.ListingContext(self.tx, raw, 2)[0])

    def test_server_age_does_not_renew_across_restarts_or_local_clock_reset(self):
        raw = self.observe("buy")
        view = self.tx.ListingContext(self.tx, raw, 2)[0]
        self.assertEqual(view.confirmedAt, 1)
        raw.native.serverNow = 1012
        raw.capturedAt = 20
        view = self.tx.ListingContext(self.tx, raw, 21)[0]
        self.assertEqual(view.confirmedAt, 10)
        self.tx = self.restart()
        raw.session, raw.revision = "again", 0
        raw.capturedAt = 0
        view, reason = self.tx.ListingContext(self.tx, raw, 1)
        self.assertIsNone(reason)
        self.assertEqual(view.confirmedAt, -10)
        listing, reason = self.tab.AssessFlipList(self.tab, view,
            *self.views(raw, "buy"), 1)
        self.assertIsNone(reason)
        self.assertIsNotNone(listing)
        raw.native.serverNow = 4603
        self.assertIsNone(self.tx.ListingContext(self.tx, raw, 100)[0])
        raw.native.serverNow = 1001
        self.assertIsNone(self.tx.ListingContext(self.tx, raw, 1)[0])

    def test_real_followup_preflights_keep_slots_expiry_margin_and_protection(self):
        for kind in ("withdraw", "buy"):
            self.setUp()
            raw = self.observe(kind)
            view = self.tx.ListingContext(self.tx, raw, 2)[0]
            assess = self.tab.AssessSellAfterWithdraw if kind == "withdraw" else self.tab.AssessFlipList
            for index, field, value in ((2, "shopUntil", 1010),
                    (1, "capturedAt", -100), (1, "quantity", 2),
                    (1, "net", 1), (0, "bound", 1)):
                values = self.views(raw, kind)
                values[index][field] = value
                self.assertIsNone(assess(self.tab, view, *values, 2)[0])
            values = self.views(raw, kind)
            values[2].listingCount = 5
            values[2].listings = lua_table(self.h.lua, {str(i): {} for i in range(5)})
            self.assertIsNone(assess(self.tab, view, *values, 2)[0])
            view.listAttempts = 1
            self.assertIsNone(assess(self.tab, view, *self.views(raw, kind), 2)[0])

    def test_persistence_failure_never_advances_each_transition(self):
        self.assertTrue(callable(self.tx.PrepareBuy))
        before = self.raw("buy")
        proposal = self.first_proposal("buy", before)
        self.storage.fail = True
        self.assertFalse(self.tx.PrepareBuy(self.tx, proposal, before)[0])
        self.assertIsNone(self.tx.Active(self.tx))
        self.storage.fail = False
        self.prepare("buy")
        self.storage.fail = True
        self.assertFalse(self.tx.MarkSending(self.tx)[0])
        self.assertEqual(self.tx.Active(self.tx).stage, "prepared")
        self.storage.fail = False
        self.tx.MarkSending(self.tx)
        raw = self.raw("buy", "observed", revision=5, server=1002)
        self.storage.fail = True
        self.assertEqual(self.tx.Reconcile(self.tx, raw)[0], "uncertain")
        self.assertEqual(self.tx.Active(self.tx).stage, "sent")
        self.storage.fail = False
        self.tx.Reconcile(self.tx, raw)
        _, listing, _ = self.followup("buy", raw, now=11)
        self.storage.fail = True
        self.assertFalse(self.tx.PrepareFollowupList(self.tx, listing, raw, 11)[0])
        self.assertEqual(self.tx.Active(self.tx).kind, "buy")
        self.storage.fail = False
        self.tx.PrepareFollowupList(self.tx, listing, raw, 11)
        self.storage.fail = True
        self.assertFalse(self.tx.MarkSending(self.tx)[0])
        self.storage.fail = False
        self.tx.MarkSending(self.tx)
        listed = self.raw("buy", "listed", revision=6, server=1004)
        self.storage.fail = True
        self.assertEqual(self.tx.Reconcile(self.tx, listed)[0], "uncertain")
        self.assertEqual(self.tx.Active(self.tx).stage, "sent")
        self.storage.fail = False
        self.tx.Reconcile(self.tx, listed)
        self.storage.fail = True
        self.assertFalse(self.tx.ClearObserved(self.tx)[0])
        self.assertEqual(self.tx.Active(self.tx).stage, "observed")

    def test_nested_maps_are_copied_on_prepare_active_write_and_recovery(self):
        self.prepare("withdraw")
        active = self.tx.Active(self.tx)
        active.baseline.looseVariants["w_baton@2"] = 99
        self.assertEqual(self.tx.Active(self.tx).baseline.looseVariants["w_baton@2"], 1)
        saved = self.storage.data[self.tx.key].transaction
        saved.baseline.looseVariants["w_baton@2"] = 2
        self.assertEqual(self.tx.Active(self.tx).baseline.looseVariants["w_baton@2"], 1)
        saved.baseline.looseVariants["w_baton@2"] = 1
        restarted = self.restart()
        saved.baseline.looseVariants["w_baton@2"] = 3
        self.assertEqual(restarted.Active(restarted).baseline.looseVariants["w_baton@2"], 1)

    def test_corrupt_baseline_maps_counts_scope_and_cycles_block_recovery(self):
        for corruption in ("variant", "total", "scope", "oversize", "cycle"):
            self.setUp()
            self.prepare("withdraw")
            saved = self.storage.data[self.tx.key].transaction
            if corruption == "variant":
                saved.baseline.looseVariants["w_baton@2"] = -1
            elif corruption == "total":
                saved.baseline.total = 99
            elif corruption == "scope":
                saved.baseline.account = "other"
            elif corruption == "oversize":
                saved.baseline.looseVariants = lua_table(self.h.lua,
                    {f"w_baton@{i}": 1 for i in range(10001)})
            else:
                saved.baseline.loop = saved
            tx, reason = self.tab.NewTransactions(self.tab, self.storage, self.scope)
            self.assertIsNone(tx, corruption)
            self.assertIn("Corrupt", reason)

    def test_missing_evidence_and_invalid_proposals_cannot_prepare_or_release(self):
        self.assertTrue(callable(self.tx.PrepareBuy))
        bare = self.module.new(self.storage, self.scope)[0]
        before = self.raw("buy")
        proposal = self.first_proposal("buy", before)
        self.assertFalse(bare.PrepareBuy(bare, proposal, before)[0])
        for field, value in (("account", "other"), ("feature", "jobs"),
                              ("preflightOnly", False)):
            old = proposal[field]
            proposal[field] = value
            self.assertFalse(self.tx.PrepareBuy(self.tx, proposal, before)[0])
            proposal[field] = old
        self.prepare("buy")
        self.tx.MarkSending(self.tx)
        bare = self.module.new(self.storage, self.scope)[0]
        raw = self.raw("buy", "observed", revision=5, server=1002)
        self.assertEqual(bare.Reconcile(bare, raw)[0], "uncertain")
        self.assertFalse(bare.ClearObserved(bare)[0])

    def test_delayed_preparation_needs_current_time_and_fresh_snapshot(self):
        _, proposal, raw = self.followup("buy")
        self.assertFalse(self.tx.PrepareFollowupList(self.tx, proposal, raw)[0])
        self.assertFalse(self.tx.PrepareFollowupList(self.tx, proposal, raw, 20)[0])
        self.assertEqual(self.tx.Active(self.tx).kind, "buy")
        # A recently captured Sync close to the one-hour boundary cannot
        # renew age by retaining the same native timestamp for fifteen seconds.
        raw.capturedAt, raw.native.serverNow = 4000, 4597
        raw.revision = 1
        view, reason = self.tx.ListingContext(self.tx, raw, 4001)
        self.assertIsNone(reason)
        proposal, reason = self.tab.AssessFlipList(self.tab, view,
            *self.views(raw, "buy"), 4001)
        self.assertIsNone(reason)
        self.assertFalse(self.tx.PrepareFollowupList(self.tx, proposal, raw, 4010)[0])

    def test_observation_idempotency_does_not_write_or_renew_server_age(self):
        raw = self.observe("withdraw")
        writes = self.storage.writes
        raw.native.serverNow = 1010
        self.assertEqual(self.tx.Reconcile(self.tx, raw)[0], "observed")
        self.assertEqual(self.storage.writes, writes)
        self.assertEqual(self.tx.Active(self.tx).confirmedServerNow, 1002)

    def test_both_first_stages_hold_ambiguous_newer_custody_after_restart(self):
        for kind in ("withdraw", "buy"):
            self.setUp()
            self.prepare(kind)
            self.tx.MarkSending(self.tx)
            self.tx = self.restart()
            raw = self.raw(kind, "observed", revision=0, server=1000,
                           session="restart", captured=1)
            self.assertEqual(self.tx.Reconcile(self.tx, raw)[0], "waiting")
            raw.native.serverNow = 1002
            raw.native.inventory.w_baton += 1
            self.assertEqual(self.tx.Reconcile(self.tx, raw)[0], "uncertain")
            self.assertFalse(self.tx.ClearObserved(self.tx)[0])

    def test_buy_owned_listing_maps_and_followup_origin_are_deep_copied(self):
        before = self.raw("buy")
        before.native.market.listings.old = self.raw("buy", "listed").native.market.listings.L2
        proposal = self.first_proposal("buy", before)
        self.assertTrue(self.tx.PrepareBuy(self.tx, proposal, before)[0])
        before.native.market.listings.old.price = 99
        active = self.tx.Active(self.tx)
        self.assertEqual(active.baseline.listings.old.price, 13)
        active.baseline.listings.old.price = 98
        self.assertEqual(self.tx.Active(self.tx).baseline.listings.old.price, 13)
        self.tx.MarkSending(self.tx)
        raw = self.raw("buy", "observed", revision=5, server=1002)
        raw.native.market.listings.old = self.raw("buy", "listed").native.market.listings.L2
        self.assertEqual(self.tx.Reconcile(self.tx, raw)[0], "observed")
        _, proposal, _ = self.followup("buy", raw, now=11)
        self.assertTrue(self.tx.PrepareFollowupList(self.tx, proposal, raw, 11)[0])
        active = self.tx.Active(self.tx)
        active.origin.baseline.listings.old.price = 97
        active.listings.old.price = 96
        self.assertEqual(self.tx.Active(self.tx).origin.baseline.listings.old.price, 13)
        self.assertEqual(self.tx.Active(self.tx).listings.old.price, 13)
        self.storage.data[self.tx.key].transaction.origin.baseline.listings.old.price = 95
        self.assertEqual(self.tx.Active(self.tx).origin.baseline.listings.old.price, 13)

    def test_store_recovery_rejects_corrupt_listing_maps_and_confirmation(self):
        for kind in ("withdraw", "buy"):
            for bad in ("session", "number", "map", "size"):
                self.setUp()
                raw = self.observe(kind)
                _, proposal, _ = self.followup(kind, raw)
                self.assertTrue(self.tx.PrepareFollowupList(self.tx, proposal, raw, 2)[0])
                record = self.storage.data[self.tx.key].transaction
                if bad == "session":
                    record.origin.confirmedSession = ""
                elif bad == "number":
                    record.ask = float("inf")
                elif bad == "map":
                    record.listings.bad = lua_table(self.h.lua, {"state": "live"})
                else:
                    record.size = 99
                tx, reason = self.tab.NewTransactions(self.tab, self.storage, self.scope)
                self.assertIsNone(tx)
                self.assertIn("Corrupt", reason)


if __name__ == "__main__":
    unittest.main()
