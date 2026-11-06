"""Current native event facts authorize free picks; historical boards do not."""
import unittest
import json
import test_pending_action_recovery as pending_fixture

from engine_harness import Harness, lua_table


class NativeBriefcaseSourceTests(unittest.TestCase):
    def setUp(self):
        self.h = h = Harness()
        self.rules = lua_table(h.lua, {"CASES": 12, "VERSION": 17})
        self.live = lua_table(h.lua, {"GlobalCaseEnd": 2000, "GlobalCaseSeason": 7,
                                     "serverNow": 1000, "briefcase": self.board()})
        h.lua.globals().briefcaseLive = self.live
        self.source, reason = h.load("src/tabs/events/NativeBriefcaseSource.luau").new(
            self.rules, h.lua.eval("function() return briefcaseLive end"),
            "a" * 64, "release-a", h.load("src/game/FreeBriefcasesState.luau"))
        self.assertIsNone(reason)
        self.context = h.load("src/game/Context.luau").new(h.contracts)
        self.planner = h.load("src/features/FreeBriefcases.luau")

    def board(self, free=1, number=3, opened=None):
        return {"season": 7, "free": free, "board": {"n": number, "cfg": 17,
                "opened": opened if opened is not None else {"c1": {"p": "cash2"}}}}

    def raw(self, revision=1):
        return self.h.snapshot(revision=revision, native={"fullSync": True,
            "serverNow": 1000, "briefcase": self.board()})

    def propose(self, raw=None):
        enriched, reason = self.source.Enrich(self.source, raw or self.raw())
        self.assertIsNone(reason)
        context, reason = self.context.Read(self.context, enriched,
            lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        view, reason = self.source.read(enriched, context)
        if view is None:
            return None, reason, enriched
        proposal, reason = self.planner.propose(view, lua_table(self.h.lua, {"enabled": True}))
        return proposal, reason, enriched

    def test_current_native_rules_attributes_and_matching_free_board_authorize_exact_open(self):
        proposal, reason, enriched = self.propose()
        self.assertIsNone(reason)
        self.assertEqual(proposal.intent.index, 2)
        self.assertEqual(enriched.caseEvent.endAt, 2000)
        self.assertEqual(enriched.briefcaseRules.version, 17)
        self.assertTrue(self.source.CanDispatch(self.source, proposal))
        call, reason = self.h.load("src/transport/NativeCallPlan.luau").describe(proposal)
        self.assertIsNone(reason)
        self.assertEqual((call.remote, call.arity, call.args[1], call.args[2]),
                         ("BriefcaseAction", 2, "open", 2))

    def test_absent_or_expired_attributes_report_inactive_despite_stored_free_pick(self):
        for end, season in ((None, None), (999, 7)):
            with self.subTest(end=end):
                self.live.GlobalCaseEnd, self.live.GlobalCaseSeason = end, season
                proposal, reason, _ = self.propose()
                self.assertIsNone(proposal)
                self.assertIn("inactive", reason)

    def test_expiry_season_config_or_consumed_free_pick_after_planning_cannot_use_a_key(self):
        mutations = ("expiry", "season", "version", "free", "opened", "board")
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.setUp()
                proposal, _, _ = self.propose()
                if mutation == "expiry": self.live.serverNow = 1996
                elif mutation == "season": self.live.GlobalCaseSeason = 8
                elif mutation == "version": self.rules.VERSION = 18
                elif mutation == "free": self.live.briefcase.free = 0
                elif mutation == "opened": self.live.briefcase.board.opened.c2 = lua_table(self.h.lua, {"p": "gold3"})
                else: self.live.briefcase.board.n = 4
                self.assertFalse(self.source.CanDispatch(self.source, proposal))

    def test_foreign_proof_partial_sync_and_changed_native_board_do_not_authorize(self):
        proposal, _, enriched = self.propose()
        enriched.briefcaseProof.sourceGeneration = 999
        context, _ = self.context.Read(self.context, enriched, lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(self.source.read(enriched, context)[0])
        raw = self.raw()
        raw.native.fullSync = False
        self.assertIsNone(self.source.Enrich(self.source, raw)[0])
        self.live.briefcase = lua_table(self.h.lua, self.board(free=0))
        self.assertIsNone(self.source.Enrich(self.source, self.raw())[0])
        self.source.Close(self.source)
        self.assertFalse(self.source.CanDispatch(self.source, proposal))

    def binding_fixture(self):
        h = self.h
        game, rules_module = h.lua.execute("""
            local function node(name,kind)
                local n={Name=name,ClassName=kind,children={}}
                function n:IsA(k) return k==self.ClassName end
                function n:FindFirstChild(k) return self.children[k] end
                function n:GetChildren() local out={} for _,v in pairs(self.children) do out[#out+1]=v end return out end
                function n:Add(c) self.children[c.Name]=c;c.Parent=self;return c end
                return n
            end
            local rs=node('ReplicatedStorage','ReplicatedStorage')
            local mw=rs:Add(node('MW','Folder'))
            function mw:GetAttribute(k) return briefcaseLive[k] end
            local remotes=mw:Add(node('Remotes','Folder'));remotes:Add(node('Sync','RemoteEvent'))
            mw:Add(node('Config','ModuleScript')).Value={COMBAT={}}
            mw:Add(node('GameData','ModuleScript')).Value={}
            mw:Add(node('GearSets','ModuleScript')).Value={slotBonus=function() return 0,0 end}
            mw:Add(node('ServerClock','ModuleScript')).Value={now=function() return briefcaseLive.serverNow end}
            local rules=mw:Add(node('BriefcaseRules','ModuleScript'));rules.Value={CASES=12,VERSION=17}
            local player=node('user-a','Player');player.UserId=123
            local scripts=player:Add(node('PlayerScripts','PlayerScripts'))
            local client=scripts:Add(node('MWClient','LocalScript'))
            client:Add(node('RemoteLink','ModuleScript')).Value={wrap=function() return remotes end}
            client:Add(node('State','ModuleScript')).Value={data={},lastSyncClock=0,
                latest=function() return {briefcase=briefcaseLive.briefcase} end,
                onChanged=function() return {Disconnect=function() end} end}
            local players={LocalPlayer=player}
            local game={PlaceId=73897506680154,PlaceVersion=654}
            function game:GetService(k)
                if k=='Players' then return players end
                if k=='ReplicatedStorage' then return rs end
            end
            return game,rules
        """)
        return game, rules_module

    def test_native_binding_reads_attributes_and_mutable_rules_but_rejects_replaced_source(self):
        h = self.h
        game, rules_module = self.binding_fixture()
        bindings, reason = h.load("src/transport/NativeClientBindings.luau").read(
            game, h.lua.eval("function(module) return module.Value end"))
        self.assertIsNone(reason)
        current = bindings.currentBriefcases
        self.assertIsNotNone(current)
        self.assertEqual(current.readCurrent().GlobalCaseSeason, 7)
        rules_module.Value.VERSION = 18
        self.assertEqual(current.definition.VERSION, 18)
        rules_module.Parent = None
        with self.assertRaisesRegex(Exception, "Briefcase source changed"):
            current.readCurrent()


    def test_briefcase_binding_never_adopts_a_build_changed_during_require(self):
        for initial,later in ((655,654),(654,655)):
            with self.subTest(initial=initial,later=later):
                self.setUp()
                game,_=self.binding_fixture();game.PlaceVersion=initial
                self.h.lua.globals().changingBuildGame=game
                self.h.lua.globals().laterBuild=later
                require=self.h.lua.eval("""function(module)
                    if module.Name=='State' then changingBuildGame.PlaceVersion=laterBuild end
                    return module.Value
                end""")
                bindings,reason=self.h.load('src/transport/NativeClientBindings.luau').read(game,require)
                self.assertIsNone(reason)
                self.assertIsNone(bindings.currentBriefcases)

    def test_briefcase_binding_retirement_is_sticky_after_build_returns(self):
        game,_=self.binding_fixture()
        bindings,reason=self.h.load('src/transport/NativeClientBindings.luau').read(
            game,self.h.lua.eval('function(module)return module.Value end'))
        self.assertIsNone(reason)
        source=bindings.currentBriefcases
        self.assertEqual(source.readCurrent().GlobalCaseSeason,7)
        game.PlaceVersion=655
        with self.assertRaisesRegex(Exception,'Briefcase source changed'):source.readCurrent()
        game.PlaceVersion=654
        with self.assertRaisesRegex(Exception,'Briefcase source changed'):source.readCurrent()

    def engine(self, attached=True):
        h = self.h
        deps = {"fingerprint": "a" * 64, "release": "release-a"}
        for name, folder in (("FreeBriefcasesState", "game"), ("FreeBriefcases", "features"),
                             ("FreeBriefcasesEvidence", "features"), ("EventShopBlocked", "tabs/events")):
            deps[name] = h.load("src/" + folder + "/" + name + ".luau")
        if attached: deps["briefcaseSource"] = self.source
        tab = h.load("src/tabs/events/Module.luau").new(lua_table(h.lua, deps))
        composed, reason = h.load("src/tabs/TabComposition.luau").build(
            lua_table(h.lua, [tab]), h.load("src/ui/Catalog.luau"),
            h.load("src/engine/FeatureRegistry.luau"), h.load("src/tabs/TabSnapshotAssembler.luau"))
        self.assertIsNone(reason)
        modules = {"Contracts": h.contracts}
        for name, folder in (("Broker", "engine"), ("Journal", "engine"), ("Context", "game"),
                             ("Scheduler", "engine"), ("Session", "engine"), ("Checkpoint", "storage"),
                             ("PendingAction", "storage"), ("CollectionProtection", "engine"),
                             ("ResourceReservations", "engine")):
            modules[name] = h.load("src/" + folder + "/" + name + ".luau")
        executor = h.lua.execute("""return {calls={},queued={},
            Schedule=function(self,fn) self.queued[#self.queued+1]=fn end,
            Invoke=function(self,remote,method,...)
                self.calls[#self.calls+1]={remote=remote,args=table.pack(...)}
                return {ok=true,source='free',prize='gold3',board=3}
            end,
            Drain=function(self) local q=self.queued;self.queued={};for _,fn in ipairs(q) do fn() end end}
        """)
        transport = h.load("src/transport/NativeDispatchAdapter.luau").new(
            h.load("src/transport/NativeCallPlan.luau"), executor)
        store = h.lua.execute("""return {strictRecovery=true,data={},
            Read=function(self,k) return self.data[k] end,
            Write=function(self,k,v) self.data[k]=v;return true end}
        """)
        runtime = h.load("src/engine/AutomationRuntime.luau").new(lua_table(h.lua, {
            "clock": h.clock, "transport": transport, "storage": store, "identity": h.session,
            "modules": modules, "features": composed.features, "featurePages": composed.featurePages,
            "snapshotAssembler": composed.snapshotAssembler}))
        runtime.Resume(runtime)
        return tab, runtime, executor

    def test_real_events_engine_sends_once_and_confirms_native_free_decrement_and_reveal(self):
        tab, runtime, executor = self.engine()
        settings = lua_table(self.h.lua, {"briefcases": {"enabled": True}})
        runtime.Step(runtime, self.raw(), settings)
        executor.Drain(executor)
        self.assertEqual(len(executor.calls), 1)
        self.assertEqual(executor.calls[1].remote, "BriefcaseAction")
        self.assertEqual(executor.calls[1].args[2], 2)
        after = self.raw(2)
        after.native.briefcase.free = 0
        after.native.briefcase.board.opened.c2 = lua_table(self.h.lua, {"p": "gold3"})
        self.live.briefcase = after.native.briefcase
        self.h.at(1)
        runtime.Step(runtime, after, settings)
        self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)), 0)
        self.assertEqual(runtime.outcomes.briefcases, "confirmed")
        tab.Close(tab)

    def test_sent_free_pick_confirms_from_newer_sync_after_native_event_attributes_expire(self):
        self.live.GlobalCaseEnd = 1010
        tab, runtime, executor = self.engine()
        settings = lua_table(self.h.lua, {"briefcases": {"enabled": True}})
        runtime.Step(runtime, self.raw(), settings)
        executor.Drain(executor)
        self.assertEqual(len(executor.calls), 1)
        after = self.raw(2)
        after.native.serverNow = 1015
        after.native.briefcase.free = 0
        after.native.briefcase.board.opened.c2 = lua_table(self.h.lua, {"p": "gold3"})
        self.live.briefcase, self.live.serverNow = after.native.briefcase, 1015
        self.live.GlobalCaseEnd, self.live.GlobalCaseSeason = None, None
        self.h.at(1)
        runtime.Step(runtime, after, settings)
        self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)), 0)
        self.assertEqual(runtime.outcomes.briefcases, "confirmed")
        executor.Drain(executor)
        self.assertEqual(len(executor.calls), 1)
        tab.Close(tab)

    def test_true_new_season_does_not_confirm_an_old_season_pick_after_expiry(self):
        self.live.GlobalCaseEnd = 1010
        tab, runtime, executor = self.engine()
        settings = lua_table(self.h.lua, {"briefcases": {"enabled": True}})
        runtime.Step(runtime, self.raw(), settings)
        executor.Drain(executor)
        after = self.raw(2)
        after.native.serverNow = 1015
        after.native.briefcase.free = 0
        after.native.briefcase.board.opened.c2 = lua_table(self.h.lua, {"p": "gold3"})
        self.live.briefcase, self.live.serverNow = after.native.briefcase, 1015
        self.live.GlobalCaseEnd, self.live.GlobalCaseSeason = 3000, 8
        self.h.at(1)
        runtime.Step(runtime, after, settings)
        self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)), 1)
        self.assertIsNone(runtime.outcomes.briefcases)
        tab.Close(tab)

    def test_expired_event_with_wrong_board_or_missing_source_proof_remains_unconfirmed(self):
        for change in ("board", "proof"):
            with self.subTest(change=change):
                self.setUp()
                before_raw = self.raw()
                before_raw = self.source.Enrich(self.source, before_raw)[0]
                # Re-plan against the source's latest capture generation.
                context, _ = self.context.Read(self.context, before_raw, lua_table(self.h.lua, self.h.session), 0, 2)
                proposal = self.planner.propose(self.source.read(before_raw, context)[0],
                    lua_table(self.h.lua, {"enabled": True}))[0]
                evidence = self.h.load("src/features/FreeBriefcasesEvidence.luau")
                baseline = evidence.capture(proposal, before_raw)[0]
                after = self.raw(2)
                after.native.serverNow = 2001
                after.native.briefcase.free = 0
                after.native.briefcase.board.opened.c2 = lua_table(self.h.lua, {"p": "gold3"})
                self.live.briefcase, self.live.serverNow = after.native.briefcase, 2001
                self.live.GlobalCaseEnd, self.live.GlobalCaseSeason = None, None
                after = self.source.Enrich(self.source, after)[0]
                if change == "board": after.native.briefcase.board.n = 4
                else: after.briefcaseProof = None
                self.assertEqual(evidence.evaluate(proposal, before_raw, after,
                    lua_table(self.h.lua, {"ok": True, "source": "free"}), baseline), "pending")


    def test_source_enriched_sent_pick_retains_exact_proof_after_v2_json_recapture_and_expiry(self):
        proposal,reason,before=self.propose()
        self.assertIsNone(reason)
        evidence=self.h.load('src/features/FreeBriefcasesEvidence.luau')
        baseline,reason=evidence.capture(proposal,before)
        self.assertIsNone(reason)
        pending=self.h.load('src/storage/PendingAction.luau')
        reply=lua_table(self.h.lua,{'ok':True,'source':'free','prize':'gold3','board':3})
        saved,reason=pending.Capture(proposal,before,baseline,reply)
        self.assertIsNone(reason)
        self.assertEqual(saved.version,2)
        saved=lua_table(self.h.lua,json.loads(json.dumps(pending_fixture.PendingActionRecoveryTests().plain(saved))))
        decoded=pending.Decode(saved)
        self.assertEqual(decoded.before.briefcaseProof.sourceKey,'a'*64)
        recaptured,reason=evidence.capture(decoded.proposal,decoded.before)
        self.assertIsNone(reason)
        # Rebuild persisted recovery from the exact original outcome inputs.
        saved,reason=pending.Capture(decoded.proposal,decoded.before,recaptured,decoded.reply)
        self.assertIsNone(reason)
        decoded=pending.Decode(lua_table(self.h.lua,json.loads(json.dumps(pending_fixture.PendingActionRecoveryTests().plain(saved)))))
        after=self.raw(2);after.native.serverNow=2001
        after.native.briefcase.free=0
        after.native.briefcase.board.opened.c2=lua_table(self.h.lua,{'p':'gold3'})
        self.live.briefcase,self.live.serverNow=after.native.briefcase,2001
        self.live.GlobalCaseEnd,self.live.GlobalCaseSeason=None,None
        after,reason=self.source.Enrich(self.source,after)
        self.assertIsNone(reason)
        self.assertEqual(evidence.evaluate(decoded.proposal,decoded.before,after,decoded.reply,decoded.baseline),'confirmed')

    def test_missing_adapter_cannot_use_caller_facts_and_consumed_free_pick_cancels_queued_send(self):
        tab, runtime, executor = self.engine(attached=False)
        forged = self.raw()
        forged.caseEvent = lua_table(self.h.lua, {"season": 7, "endAt": 2000})
        forged.briefcaseRules = lua_table(self.h.lua, {"cases": 12, "version": 17})
        forged.catalogKey = "a" * 64
        settings = lua_table(self.h.lua, {"briefcases": {"enabled": True}})
        runtime.Step(runtime, forged, settings)
        executor.Drain(executor)
        self.assertEqual(len(executor.calls), 0)
        runtime.Close(runtime)
        tab, runtime, executor = self.engine()
        runtime.Step(runtime, self.raw(), settings)
        self.live.briefcase.free = 0
        executor.Drain(executor)
        self.assertEqual(len(executor.calls), 0)


if __name__ == "__main__":
    unittest.main()
