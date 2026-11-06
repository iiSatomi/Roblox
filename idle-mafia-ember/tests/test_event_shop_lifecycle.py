"""Composed Event Shop acquisition uses the real broker, native adapter and custody."""
import unittest

from engine_harness import lua_table
import test_conditional_feature_contracts


class EventShopLifecycleTests(unittest.TestCase):
    setUp = test_conditional_feature_contracts.ConditionalContracts.setUp
    table = test_conditional_feature_contracts.ConditionalContracts.table
    header = test_conditional_feature_contracts.ConditionalContracts.header
    event = test_conditional_feature_contracts.ConditionalContracts.event
    event_raw = test_conditional_feature_contracts.ConditionalContracts.event_raw

    def engine(self, source, store=None):
        h = self.h
        deps = {"fingerprint":"a" * 64, "release":"release-a", "eventShopSource":source}
        for name, folder in (("FreeBriefcasesState","game"), ("FreeBriefcases","features"),
                ("FreeBriefcasesEvidence","features")):
            deps[name] = h.load(f"src/{folder}/{name}.luau")
        for name in ("EventShopBlocked", "EventShopBuyer"):
            deps[name] = h.load(f"src/tabs/events/{name}.luau")
        tab = h.load("src/tabs/events/Module.luau").new(self.table(deps))
        composed, reason = h.load("src/tabs/TabComposition.luau").build(self.table([tab]),
            h.load("src/ui/Catalog.luau"),h.load("src/engine/FeatureRegistry.luau"),
            h.load("src/tabs/TabSnapshotAssembler.luau"))
        self.assertIsNone(reason)
        modules = {"Contracts":h.contracts, "EventShopUsage":h.load("src/tabs/events/EventShopUsage.luau")}
        for name, folder in (("Broker","engine"),("Journal","engine"),("Scheduler","engine"),
                ("Session","engine"),("Context","game"),("Checkpoint","storage"),("PendingAction","storage")):
            modules[name] = h.load(f"src/{folder}/{name}.luau")
        if store is None:
            store = h.lua.execute("""return {strictRecovery=true,data={},
                Read=function(self,k) return self.data[k] end,
                Write=function(self,k,v) self.data[k]=v;return true end}""")
        executor = h.lua.execute("""return {queued={},calls={},reply={ok=true},
            Schedule=function(self,fn) self.queued[#self.queued+1]=fn;return true end,
            Invoke=function(self,remote,method,...)
                self.calls[#self.calls+1]={remote=remote,method=method,args=table.pack(...)}
                return self.reply
            end,
            Drain=function(self) local q=self.queued;self.queued={};for _,fn in ipairs(q) do fn() end end}""")
        plan = h.load("src/transport/NativeCallPlan.luau")
        transport = h.load("src/transport/NativeDispatchAdapter.luau").new(
            plan.withEvents(plan,deps["EventShopBuyer"]),executor)
        runtime = h.load("src/engine/AutomationRuntime.luau").new(self.table({
            "clock":h.clock,"transport":transport,"storage":store,"identity":h.session,
            "modules":modules,"features":composed.features,"featurePages":composed.featurePages,
            "snapshotAssembler":composed.snapshotAssembler,"tabInstances":composed.tabs}))
        runtime.Resume(runtime)
        return runtime,executor,store

    def raw(self, source, revision=1, medals=40, pills=0):
        self.h.at(revision)
        raw = self.event_raw(source,revision,medals=medals,pills=pills)
        raw.native.cash = 1000
        raw.native.pools = self.table({"energy":20})
        return raw

    def settings(self, **changes):
        return self.table({"eventShop":{"enabled":True,"offerKey":"healing",
            "medalReserve":30,"maxSpend":10,"maxAttempts":1,**changes}})

    def usage(self, runtime, raw):
        proof, reason = runtime.checkpoint.EventShopUsage(runtime.checkpoint,raw)
        self.assertIsNone(reason)
        return proof.attempted, proof.spent

    def test_one_exact_purchase_confirms_and_run_caps_survive_restart(self):
        source, _, attrs = self.event()
        runtime, executor, store = self.engine(source)
        before = self.raw(source)
        status = runtime.Step(runtime,before,self.settings())
        executor.Drain(executor)
        self.assertEqual(len(executor.calls),1,(status.globalReason,dict(status.reasons.items())))
        call = executor.calls[1]
        self.assertEqual((call.remote,call.method,call.args.n),("EventShopAction","InvokeServer",4))
        self.assertEqual([call.args[i] for i in (1,2,3,4)],["buy","healing",1,"medal"])
        self.assertEqual(self.usage(runtime,before),(1,10))
        after = self.raw(source,2,medals=30,pills=2)
        status = runtime.Step(runtime,after,self.settings())
        self.assertEqual(status.outcomes.eventShop,"confirmed")
        self.assertFalse(status.storageFault)
        self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)),0)
        executor.Drain(executor)
        self.assertEqual(len(executor.calls),1)
        runtime.Close(runtime)
        self.h.session["session"] = "run-b"
        next_source, _, _ = self.event()
        restarted, next_executor, _ = self.engine(next_source,store)
        status = restarted.Step(restarted,self.raw(next_source,3,medals=100,pills=2),
            self.settings(medalReserve=0))
        next_executor.Drain(next_executor)
        self.assertEqual(len(next_executor.calls),0)
        self.assertIn("cap",status.reasons.eventShop.lower())
        self.assertEqual(self.usage(restarted,self.raw(next_source,4,medals=100,pills=2)),(1,10))

    def test_source_retirement_or_changed_window_refuses_queued_native_send_and_refunds_only_unsent(self):
        for change in ("close","window","expiry"):
            with self.subTest(change=change):
                self.setUp()
                source, _, attrs = self.event()
                runtime, executor, _ = self.engine(source)
                before = self.raw(source)
                runtime.Step(runtime,before,self.settings())
                self.assertEqual(self.usage(runtime,before),(1,10))
                if change == "close": source.Close(source)
                elif change == "window": attrs.GlobalEventShop = False
                else: attrs.serverNow = attrs.GlobalEventShopEnd
                executor.Drain(executor)
                self.assertEqual(len(executor.calls),0)
                self.assertEqual(self.usage(runtime,before),(0,0))
                self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)),0)

    def test_saved_native_reply_reconciles_after_restart_without_resending(self):
        source, _, _ = self.event()
        runtime, executor, store = self.engine(source)
        runtime.Step(runtime,self.raw(source),self.settings())
        executor.Drain(executor)
        self.assertEqual(len(executor.calls),1)
        runtime.Close(runtime)
        self.h.session["session"] = "run-b"
        next_source, _, attrs = self.event()
        attrs.GlobalEventShop = False
        restarted, next_executor, _ = self.engine(next_source,store)
        after = self.raw(next_source,2,medals=30,pills=2)
        status = restarted.Step(restarted,after,self.settings())
        next_executor.Drain(next_executor)
        self.assertFalse(status.storageFault)
        self.assertEqual(len(next_executor.calls),0)
        self.assertEqual(len(restarted.checkpoint.Records(restarted.checkpoint)),0)
        self.assertEqual(self.usage(restarted,after),(1,10))

    def test_explicit_reserve_attempt_spend_and_paid_medals_gate_actual_admission(self):
        cases = [("reserve",{"medalReserve":31},None),
            ("attempt",{"maxAttempts":0},None),("spend",{"maxSpend":9},None),
            ("paid",{},1),("unknown offer",{"offerKey":"missing"},None)]
        for name, settings, paid in cases:
            with self.subTest(name=name):
                self.setUp()
                source, _, _ = self.event()
                runtime, executor, _ = self.engine(source)
                raw = self.raw(source)
                raw.native.paidMedals = paid
                runtime.Step(runtime,raw,self.settings(**settings))
                executor.Drain(executor)
                self.assertEqual(len(executor.calls),0)
                self.assertEqual(self.usage(runtime,raw),(0,0))

    def test_current_multicurrency_rows_select_only_explicit_earned_medal_currency(self):
        # Current654 EventShop has Candy/Corn-only rows before Medal rows;
        # EventShopTab.buyWith always supplies the explicit fourth currency key.
        definition = self.table({"MEDAL":"event_medal","MAX_ITEM_COUNT":99,
            "CURRENCIES":{"medal":{"item":"event_medal","paidField":"paidMedals"},
                "candy":{"item":"striped_candy"},"corn":{"item":"candy_corn","paidField":"paidCorn","tradable":True}},
            "ROWS":[{"key":"hw_crate","kind":"crate","item":"crate_halloween_2026","prices":{"candy":40}},
                {"key":"hw_crate_corn","kind":"crate","item":"crate_halloween_2026","prices":{"corn":2}},
                {"key":"gold","kind":"item","item":"gold_bar","count":1,"price":3,"prices":{"medal":3}}]})
        attrs = self.table({"GlobalEventShop":True,"GlobalEventShopEnd":1000,
            "MWPaidRandomRestricted":False,"serverNow":101})
        self.h.lua.globals().shopAttributes = attrs
        source, reason = self.h.load("src/tabs/events/NativeEventShopSource.luau").new(definition,
            self.h.lua.eval("function() return shopAttributes end"),"a"*64,"release-a")
        self.assertIsNone(reason)
        runtime, executor, _ = self.engine(source)
        raw = self.raw(source,medals=40)
        runtime.Step(runtime,raw,self.settings(offerKey="gold",medalReserve=37,maxSpend=3))
        executor.Drain(executor)
        self.assertEqual(len(executor.calls),1)
        call = executor.calls[1]
        self.assertEqual([call.args[i] for i in (1,2,3,4)],["buy","gold",1,"medal"])
        self.assertEqual(self.usage(runtime,raw),(1,3))
        after = self.raw(source,2,medals=37)
        after.native.inventoryBound.gold_bar = 1
        status = runtime.Step(runtime,after,self.settings(offerKey="gold",maxSpend=3))
        self.assertEqual(status.outcomes.eventShop,"confirmed")
        self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)),0)
        # Other currency rows are represented, but never become a Medal purchase.
        buyer = self.h.load("src/tabs/events/EventShopBuyer.luau").new(source)
        after, reason = source.Enrich(source,after)
        self.assertIsNone(reason)
        after.eventShopUsageProof = self.table({**self.header(2),"attempted":0,"spent":0})
        view, reason = buyer.read(after,after)
        self.assertIsNone(reason)
        for key in ("hw_crate","hw_crate_corn"):
            self.assertIsNone(buyer.propose(view,self.settings(offerKey=key).eventShop)[0])
        proposal, reason = buyer.propose(view,self.settings(offerKey="gold").eventShop)
        self.assertIsNone(reason)
        proposal.intent.currency = "candy"
        self.assertFalse(source.CanDispatch(source,proposal))
        self.assertIsNone(buyer.capture(proposal,after)[0])
        self.assertIsNone(self.h.load("src/tabs/events/EventShopBuyer.luau").describe(proposal)[0])
        definition.ROWS[3].prices.medal = 4
        self.assertFalse(source.CanDispatch(source,self.table({"feature":"eventShop",
            "intent":{"sourceKey":"a"*64,"sourceGeneration":view.sourceGeneration,"currency":"medal"}})))


if __name__ == "__main__": unittest.main()
