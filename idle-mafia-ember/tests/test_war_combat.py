"""War permissions require exact current enemy identity and independent limits."""
import unittest

from engine_harness import Harness, lua_table
import test_combat_tab_module as combat_fixture


class WarCombatPlannerTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.planner = self.h.load("src/tabs/combat/PlayerFightPlanner.luau").new(
            self.h.load("src/tabs/combat/TargetSelection.luau"), "warCombat")
        self.settings = lua_table(self.h.lua, {
            "enabled": True, "policy": "Custom", "targetSource": "Saved and new",
            "minimumPayout": 0, "staminaReserve": 0, "healthFloor": 20,
            "maxAttackSpend": 5, "maxScoutSpend": 5, "minSamples": 0,
            "minWinRate": 0, "minWinChance": 90, "minPowerRatio": 1.25,
            "scoutMaxAge": 30, "maxStaminaCost": 5, "minTargetLevel": 1,
            "maxTargetLevel": 1000, "allowScout": False,
        })
        self.held = lua_table(self.h.lua, {"stamina": 0, "uncertainStamina": 0})

    def view(self):
        return lua_table(self.h.lua, {**self.h.session, "revision": 1,
            "capturedAt": 0, "sourceKey": "a" * 64, "status": "known",
            "serverNow": 100, "ownUserId": 123, "ownFamilyId": "own",
            "health": 100, "maxHealth": 100, "stamina": 20, "attack": 1000,
            "hospitalHealth": 20, "scoutCost": 1, "maxNativeStaminaCost": 5,
            "fightVariance": 0.2, "fightVarianceCap": 5000,
            "attackAttempted": 0, "attackSpent": 0,
            "scoutAttempted": 0, "scoutSpent": 0,
            "war": {"active": True, "enemyFamilyId": "enemy", "canScore": True,
                    "ownRemaining": 10, "ownCap": 20, "statusServerNow": 100},
            "targets": [{"userId": 456, "name": "Enemy", "level": 10,
                "familyId": "enemy", "warFamilyId": "enemy", "friend": False,
                "staminaCost": 1, "remainingDaily": 5, "shieldUntil": 0,
                "cooldownUntil": 0, "history": [],
                "warStatus": {"day": 0, "remaining": 10, "cap": 40,
                              "attacksRemaining": 5, "attacksCap": 5,
                              "pairRemaining": 5, "canScore": True},
                "stats": {"at": 100, "kind": "scout", "level": 10, "defense": 10}}]})

    def test_exact_enemy_proposal_uses_independent_war_lane(self):
        proposal, reason = self.planner.propose(self.view(), self.settings, self.held)
        self.assertIsNone(reason)
        self.assertIsNotNone(proposal, "Verified scoring enemy must use its opted-in war lane")
        self.assertEqual(proposal.feature, "warCombat")
        self.assertEqual(proposal.intent.warEnemyFamilyId, "enemy")
        self.assertEqual(proposal.intent.warOwnFamilyId, "own")
        self.assertEqual(proposal.actionKey, "warCombat:attack:456:0")
        call, reason = self.h.load("src/tabs/combat/CombatCallPlan.luau").describe(proposal)
        self.assertIsNone(reason)
        self.assertEqual((call.remote, call.args[1]), ("Attack", 456))
        base = self.h.load("src/transport/NativeCallPlan.luau")
        composed = base.withCombat(base,self.h.load("src/tabs/combat/CombatCallPlan.luau"))
        self.assertEqual(composed.describe(proposal)[0].remote,"Attack")

    def test_war_never_accepts_foreign_family_or_unscouted_stats(self):
        for field, value in (("familyId", "foreign"), ("friend", True)):
            with self.subTest(field=field):
                view = self.view()
                view.targets[1][field] = value
                self.assertIsNone(self.planner.propose(view, self.settings, self.held)[0])
        view = self.view()
        view.targets[1].stats.kind = "public"
        self.assertIsNone(self.planner.propose(view, self.settings, self.held)[0])

    def test_exhausted_war_budget_cannot_borrow_ordinary_budget(self):
        view = self.view()
        view.attackAttempted, view.attackSpent = 1, 5
        self.assertIsNone(self.planner.propose(view, self.settings, self.held)[0])

    def test_scout_budget_is_separate_and_reserves_native_maximum(self):
        view = self.view()
        view.targets[1].stats = None
        self.settings.allowScout = True
        proposal, reason = self.planner.propose(view,self.settings,self.held)
        self.assertIsNone(reason)
        usage = self.h.load("src/tabs/combat/PlayerFightUsage.luau")
        charged, _, reason = usage.charge(None,proposal)
        self.assertIsNone(reason)
        self.assertEqual(charged.lanes.warCombat.scout.spent,5)
        self.assertEqual(charged.lanes.warCombat.attack.spent,0)
        self.assertEqual(charged.lanes.combat.scout.spent,0)
        view.scoutAttempted,view.scoutSpent = 1,5
        self.assertIsNone(self.planner.propose(view,self.settings,self.held)[0])

    def test_war_scoring_limits_and_switch_are_required(self):
        for field, value in (("remaining",0),("attacksRemaining",0),
                             ("pairRemaining",0),("canScore",False)):
            with self.subTest(field=field):
                view = self.view()
                view.targets[1].warStatus[field] = value
                self.assertIsNone(self.planner.propose(view,self.settings,self.held)[0])
        self.settings.enabled = False
        self.assertIsNone(self.planner.propose(self.view(),self.settings,self.held)[0])


class NativeWarGuardTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        base = self.h.load("tests/fixtures/prestige-client.lua")
        self.client = self.h.load("tests/fixtures/combat-client.lua")(base)
        self.client.data.family = lua_table(self.h.lua, {"id": "own"})
        self.client.data.derived.war = lua_table(self.h.lua,
            {"state": "active", "enemyId": "enemy"})
        self.status = lua_table(self.h.lua, {"serverNow": 100, "day": 0,
            "summary": {"enemyId": "enemy", "canScore": True, "ownRemaining": 10, "ownCap": 20},
            "targets": [{"userId": 456, "name": "Enemy", "level": 10,
                "familyId": "enemy", "warStatus": {"day": 0, "remaining": 10,
                    "cap": 40, "attacksRemaining": 5, "attacksCap": 5,
                    "pairRemaining": 5, "canScore": True}}]})
        self.h.lua.globals().warStatus = self.status
        self.client.attack[5].snapshot = self.h.lua.eval("function() return warStatus end")
        self.client.attack[5].targetOf = self.h.lua.eval(
            "function(id) if id == 456 then return warStatus.targets[1] end end")
        self.client.attack[5].accept = self.h.lua.eval(
            "function(status) warStatus = status; return true end")
        self.client.proposal.feature = "warCombat"
        intent = self.client.proposal.intent
        intent.familyId, intent.targetName, intent.targetLevel = "enemy", "Enemy", 10
        intent.warEnemyFamilyId, intent.warOwnFamilyId = "enemy", "own"
        intent.warDay, intent.warStatusServerNow = 0, 100
        self.source = self.h.load("src/transport/NativeClientBindings.luau").read(
            self.client.game, self.client.requireModule, self.client.readUpvalues)[0].currentFightNotifications

    def test_current_enemy_can_attack_without_bypassing_native_warning(self):
        self.assertTrue(self.source.CanAttack(self.source, self.client.proposal, 456)[0])
        self.client.attack[5].warning = self.h.lua.eval("function() return 'Scoring locked' end")
        self.assertFalse(self.source.CanAttack(self.source, self.client.proposal, 456)[0])

    def test_changed_enemy_or_scoring_allowance_refuses_dispatch(self):
        self.status.summary.enemyId = "changed"
        self.assertFalse(self.source.CanAttack(self.source, self.client.proposal, 456)[0])
        self.status.summary.enemyId = "enemy"
        self.status.targets[1].warStatus.pairRemaining = 0
        self.assertFalse(self.source.CanAttack(self.source, self.client.proposal, 456)[0])

    def test_stale_status_and_foreign_own_family_refuse_dispatch(self):
        self.client.data.serverNow = 111
        self.assertFalse(self.source.CanAttack(self.source,self.client.proposal,456)[0])
        self.client.data.serverNow = 100
        self.client.data.family.id = "another"
        self.assertFalse(self.source.CanAttack(self.source,self.client.proposal,456)[0])

    def test_owned_war_read_admits_native_cache_without_opening_ui(self):
        self.h.lua.globals().warStatus = None
        query = self.h.load("src/tabs/combat/HitListQuery.luau").new(
            lua_table(self.h.lua,self.h.session),"a"*64,self.source,"war")
        raw = self.h.snapshot(native=self.client.data)
        request,reason = query.Prepare(query,raw)
        self.assertIsNone(reason)
        staged,reason = query.Accept(query,raw,request,lua_table(self.h.lua,
            {"ok":True,"warStatus":self.status}))
        self.assertIsNone(reason)
        self.assertTrue(query.Commit(query,staged))
        self.assertIsNotNone(self.h.lua.globals().warStatus,
                             "Only an accepted owned roster read should populate the native cache")
        self.assertEqual(self.h.lua.globals().warStatus.summary.enemyId,"enemy")
        self.assertTrue(self.source.CanAttack(self.source,self.client.proposal,456)[0])

    def test_native_cache_admission_rejects_malformed_scoring_fields(self):
        self.status.targets[1].warStatus.remaining = "invalid"
        self.assertFalse(self.source.AcceptWarStatus(self.source,self.status,self.client.data))

    def test_no_war_read_can_clear_native_cache_without_an_active_enemy(self):
        self.client.data.derived.war = None
        status = lua_table(self.h.lua,{"serverNow":100,"day":0,"targets":[]})
        self.assertTrue(self.source.AcceptWarStatus(self.source,status,self.client.data))
        self.assertIsNone(self.h.lua.globals().warStatus.summary)
        self.assertEqual(len(self.h.lua.globals().warStatus.targets),0)

    def test_owned_cache_payload_is_bounded_before_it_is_copied(self):
        query = self.h.load("src/tabs/combat/HitListQuery.luau").new(
            lua_table(self.h.lua,self.h.session),"a"*64,self.source,"war")
        raw = self.h.snapshot(native=self.client.data)
        request,_ = query.Prepare(query,raw)
        self.status.extra = self.h.lua.eval("""(function()
            local root={};local current=root
            for i=1,12 do current.child={};current=current.child end
            return root
        end)()""")
        self.assertIsNone(query.Accept(query,raw,request,lua_table(self.h.lua,
            {"ok":True,"warStatus":self.status}))[0])


class WarCombatFlowTests(unittest.TestCase):
    def setUp(self):
        fixture = combat_fixture.CombatTabModuleTests()
        fixture.setUp()
        self.h, deps = fixture.h, fixture.deps
        for name in ("PlayerFightEvidence", "FightReceipts", "PlayerFightLedger",
                     "PlayerFightPlanner", "TargetSelection", "PlayerProfileQuery",
                     "PlayerScoutEvidence"):
            deps[name] = self.h.load(f"src/tabs/combat/{name}.luau")
        deps["fingerprint"] = "a" * 64
        deps["storage"] = self.h.lua.execute("""return {strictRecovery = true, data = {},
            Read = function(self,k) return self.data[k] end,
            Write = function(self,k,v) self.data[k]=v; return true end}""")
        deps["nativeReadSource"] = self.h.lua.execute("""return {
            Current = function() return true end,
            Friendship = function() return false end,
            CanAttack = function() return true end,
            Subscribe = function(self,callback)
                self.notify = callback
                return {Disconnect = function() end}
            end,
            CombatFrame = function(_, native, targets)
                local facts = {}
                for _,row in ipairs(targets) do facts[tostring(row.userId)] = {
                    remainingDaily=5,cooldownLeft=0,sameFamily=false,manualWarning=false} end
                return {ownUserId=123,ownFamilyId='own',attack=1000,maxHealth=100,
                    health=native.pools.health,stamina=native.pools.stamina,
                    hospitalHealth=20,staminaCost=1,scoutCost=1,maxStaminaCost=5,
                    dailyTargetCap=5,targetCooldown=30,fightVariance=0.2,fightVarianceCap=5000,
                    busy=false,shielded=false,globalCooldown=0,targets=facts}
            end}""")
        lane = self.h.load("src/engine/RequestLane.luau").new(self.h.clock)
        self.lane,self.nativeSource = lane,deps["nativeReadSource"]
        deps["fightReceipts"] = deps["FightReceipts"].new(
            lua_table(self.h.lua, self.h.session), self.h.clock, lane,
            deps["nativeReadSource"], "a" * 64)
        self.tab = fixture.entry.new(lua_table(self.h.lua, deps))
        self.spec = self.tab.Descriptors(self.tab)[2]
        self.raw = self.h.snapshot(native={"fullSync": True,"serverNow":100,"userId":123,
            "level":10,"stats":{"maxHealth":100},"pools":{"health":100,"stamina":20},
            "family":{"id":"own"},"derived":{"war":{"state":"active","enemyId":"enemy"}},
            "attackDaily":{"day":0,"counts":{}}})
        self.status = lua_table(self.h.lua, {"serverNow":100,"day":0,
            "summary":{"enemyId":"enemy","canScore":True,"ownRemaining":10,"ownCap":20},
            "targets":[{"userId":456,"name":"Enemy","level":10,"familyId":"enemy",
                "warStatus":{"day":0,"remaining":10,"cap":40,"attacksRemaining":5,
                    "attacksCap":5,"pairRemaining":5,"canScore":True}}]})
        for query, reply in ((self.tab.hitListQuery, {"ok":True,"list":[],"warStatus":self.status}),
                             (self.tab.warRosterQuery,{"ok":True,"warStatus":self.status})):
            request, reason = query.Prepare(query,self.raw)
            self.assertIsNone(reason)
            staged, reason = query.Accept(query,self.raw,request,lua_table(self.h.lua,reply))
            self.assertIsNone(reason)
            self.assertTrue(query.Commit(query,staged))
        self.settings = lua_table(self.h.lua, {"combat":{"enabled":False},"warCombat":{
            "enabled":True,"policy":"Custom","targetSource":"Saved and new","allowScout":True,
            "minimumPayout":0,"staminaReserve":0,"healthFloor":20,"maxAttackSpend":5,
            "maxScoutSpend":5,"minSamples":0,"minWinRate":0,"minWinChance":90,
            "minPowerRatio":1.25,"scoutMaxAge":30,"maxStaminaCost":5,
            "minTargetLevel":1,"maxTargetLevel":1000}})

    def enrich(self, raw):
        enriched, reason = self.tab.Enrich(self.tab,raw,self.settings)
        self.assertIsNone(reason)
        usage = self.h.load("src/tabs/combat/PlayerFightUsage.luau").copy(None)
        enriched.playerFightUsageProof = lua_table(self.h.lua,
            {"account":raw.account,"capturedAt":raw.capturedAt,"usage":usage})
        return enriched

    def quote_and_profile(self,quote_changes=None):
        sources = self.tab.ReadSources(self.tab,self.h.lua.table())
        quotes = next((source for source in sources.values()
                       if source.id == "combatWarQuote"),None)
        self.assertIsNotNone(quotes,"War must obtain an exact server quote without ordinary attack permission")
        self.assertTrue(quotes.enabled(self.settings,None,self.raw))
        request, reason = quotes.prepare(self.raw)
        self.assertIsNone(reason)
        self.assertEqual((request.remote,request.args[1]),("SearchTarget","Enemy"))
        row = {"userId":456,"name":"Enemy","level":10,"familyId":"enemy","stamina":1,"shielded":False}
        row.update(quote_changes or {})
        reply = lua_table(self.h.lua,{"ok":True,"search":"Enemy","list":[row]})
        staged, reason = quotes.accept(self.raw,request,reply)
        self.assertIsNone(reason)
        self.assertTrue(quotes.commit(staged))
        profiles = self.tab.warProfiles
        request, reason = profiles.Prepare(profiles,self.raw,30)
        self.assertIsNone(reason)
        staged, reason = profiles.Accept(profiles,self.raw,request,lua_table(self.h.lua,{"ok":True,"profile":{
            "userId":456,"name":"Enemy","level":10,"maxLevel":10,"familyId":"enemy",
            "scoutCost":1,"statsHidden":True,"shieldLeft":0}}))
        self.assertIsNone(reason)
        self.assertTrue(profiles.Commit(profiles,staged))

    def test_war_quote_profile_scout_then_attack_uses_only_war_permission(self):
        self.quote_and_profile()
        before = self.enrich(self.raw)
        context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        view = context.Read(context,before,lua_table(self.h.lua,self.h.session),0,2)[0]
        targets, reason = self.spec.reader.read(before,view)
        self.assertIsNone(reason)
        scout, reason = self.spec.planner.propose(targets,self.settings.warCombat,
            lua_table(self.h.lua,{"stamina":0,"uncertainStamina":0}))
        self.assertIsNone(reason)
        self.assertEqual((scout.feature,scout.intent.kind),("warCombat","playerScout"))
        self.assertTrue(self.spec.canDispatch(scout))
        baseline, reason = self.spec.evidence.capture(scout,before)
        self.assertIsNone(reason)
        scout.requestId = 1
        reply = lua_table(self.h.lua,{"ok":True,"atk":100,"def":10,"crew":1})
        self.h.at(1)
        self.raw = self.h.lua.eval("""function(raw)
            local function copy(value)
                if type(value) ~= 'table' then return value end
                local out = {}; for key,child in pairs(value) do out[key] = copy(child) end
                return out
            end
            return copy(raw)
        end""")(self.raw)
        self.raw.revision,self.raw.capturedAt,self.raw.native.serverNow = 2,1,101
        self.raw.native.pools.stamina = 19
        after = self.enrich(self.raw)
        self.assertEqual(self.spec.evidence.evaluate(scout,before,after,reply,baseline),"confirmed")
        self.assertTrue(self.spec.recordOutcome(lua_table(self.h.lua,
            {"proposal":scout,"before":before,"reply":reply,"baseline":baseline}),after)[0])
        refreshed = self.enrich(self.raw)
        view = context.Read(context,refreshed,lua_table(self.h.lua,self.h.session),1,2)[0]
        targets, reason = self.spec.reader.read(refreshed,view)
        self.assertIsNone(reason)
        attack, reason = self.spec.planner.propose(targets,self.settings.warCombat,
            lua_table(self.h.lua,{"stamina":0,"uncertainStamina":0}))
        self.assertIsNone(reason)
        self.assertEqual((attack.feature,attack.intent.kind),("warCombat","playerAttack"))
        self.assertTrue(self.spec.canDispatch(attack))
        attack_baseline,reason = self.spec.evidence.capture(attack,refreshed)
        self.assertIsNone(reason)
        attack.requestId = 2
        token,reason = self.lane.TryAcquire(self.lane,"mutation",attack.actionKey,45)
        self.assertIsNone(reason)
        receipts = self.tab.fightReceipts
        self.assertTrue(receipts.Begin(receipts,token,attack,456)[0])
        first = {"ok":True,"won":True,"fightId":"war-fight-1","cashStage":1,
            "cashPending":True,"rewardsPending":True,"targetName":"Enemy",
            "targetLevel":10,"targetShownLevel":10,"staminaCost":1,
            "targetDaily":{"day":0,"count":1,"serverNow":101}}
        initial = lua_table(self.h.lua,first)
        self.assertTrue(receipts.Bind(receipts,token,initial)[0])
        settled = lua_table(self.h.lua,{**first,"cashStage":4,"cashPending":False,
            "rewardsPending":False,"cashConfirmed":100,"stolen":100,"xp":1,"respect":1})
        self.nativeSource.notify("fightcash",None,settled)
        self.h.at(2)
        self.raw = self.h.lua.eval("""function(raw)
            local function copy(v)
                if type(v)~='table' then return v end
                local out={};for k,c in pairs(v) do out[k]=copy(c) end;return out
            end
            return copy(raw)
        end""")(self.raw)
        self.raw.revision,self.raw.capturedAt,self.raw.native.serverNow = 3,2,102
        self.raw.native.pools.stamina = 18
        self.raw.native.attackDaily.counts["456"] = 1
        final = self.enrich(self.raw)
        self.assertEqual(self.spec.evidence.evaluate(attack,refreshed,final,initial,attack_baseline),"confirmed")
        self.assertTrue(self.spec.recordOutcome(lua_table(self.h.lua,
            {"proposal":attack,"before":refreshed,"reply":initial,"baseline":attack_baseline}),final)[0])
        self.assertEqual(self.tab.playerLedger.Summary(self.tab.playerLedger).recent[1].feature,"warCombat")
        self.assertFalse(self.settings.combat.enabled)

    def test_foreign_quote_cannot_authorize_a_roster_enemy(self):
        self.quote_and_profile({"familyId":"foreign"})
        raw = self.enrich(self.raw)
        context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        view = context.Read(context,raw,lua_table(self.h.lua,self.h.session),0,2)[0]
        targets,reason = self.spec.reader.read(raw,view)
        self.assertIsNone(reason)
        self.assertEqual(len(targets.targets),0)
        self.assertIsNone(self.spec.planner.propose(targets,self.settings.warCombat,
            lua_table(self.h.lua,{"stamina":0,"uncertainStamina":0}))[0])

    def test_war_reader_cannot_fall_back_to_an_ordinary_hitlist(self):
        self.quote_and_profile()
        raw = self.enrich(self.raw)
        raw.warRosterProof = None
        context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        view = context.Read(context,raw,lua_table(self.h.lua,self.h.session),0,2)[0]
        self.assertIsNone(self.spec.reader.read(raw,view)[0])


if __name__ == "__main__":
    unittest.main()
