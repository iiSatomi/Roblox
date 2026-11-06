"""Free-charge Family Takedown attacks require personal native proof."""
import unittest

from engine_harness import Harness, lua_table


class FamilyTakedownAttackTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.takedown = self.h.load("src/game/FamilyTakedownState.luau")
        self.context = self.h.load("src/game/Context.luau").new(
            self.h.contracts, None, None, None, None, None, None,
            self.takedown)
        self.reader = self.h.load("src/game/FamilyBossAttackState.luau")
        self.planner = self.h.load("src/features/FamilyBossAttacks.luau")
        self.evidence = self.h.load(
            "src/features/FamilyBossAttacksEvidence.luau")

    def raw(self, revision=1, now=1050, tickets=0, free_used=1,
            damage=100, health=80, stamina=5, hit_back=20,
            hits=0, last=0, week=100, fam_id=9):
        captured = self.h.lua.globals().testNow
        return self.h.snapshot(revision=revision,
            native={"fullSync": True, "serverNow": now,
                "stats": {"maxHealth": 100},
                "pools": {"health": health, "stamina": stamina}},
            familyTakedownProof={"account": "user-a",
                "capturedAt": captured,
                "state": {"week": week, "famId": fam_id,
                    "inFamily": True, "stage": 2,
                    "resetAt": 2000, "freeMax": 3,
                    "freeUsed": free_used, "freeRegen": 60,
                    "tickets": tickets, "myDmg": damage,
                    "claims": [], "claimedStages": []}},
            familyAttackProof={"account": "user-a",
                "capturedAt": captured, "week": week,
                "famId": fam_id, "stage": 2,
                "staminaCost": 1,
                "hitBackMax": hit_back},
            familyAttackUsageProof={"account": "user-a",
                "capturedAt": captured, "week": week,
                "famId": fam_id, "hits": hits,
                "lastServerNow": last})

    def propose(self, raw):
        context = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session),
            self.h.lua.globals().testNow, 2)[0]
        view, reason = self.reader.read(raw, context)
        self.assertIsNone(reason)
        return self.planner.propose(view,
            lua_table(self.h.lua, {"enabled": True}),
            lua_table(self.h.lua, {"stamina": 0,
                "uncertainStamina": 0}))

    def test_newer_personal_damage_and_free_use_confirm(self):
        before = self.raw()
        proposal, reason = self.propose(before)
        self.assertIsNone(reason)
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        self.h.at(1)
        after = self.raw(revision=2, damage=150,
            free_used=2, hits=1, last=1050)
        reply = lua_table(self.h.lua, {"ok": True, "dmg": 50,
            "tickets": 0, "freeLeft": 1})
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, reply, baseline), "confirmed")
        after["familyTakedownProof"]["state"]["myDmg"] = 100
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, reply, baseline), "pending")
        after["familyTakedownProof"]["state"]["myDmg"] = 150
        after["familyTakedownProof"]["state"]["tickets"] = 1
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, reply, baseline), "pending")

    def test_ticket_health_stamina_cap_and_spacing_block(self):
        for changes in ({"tickets": 1}, {"free_used": 3},
                        {"hit_back": 0},
                        {"health": 60, "hit_back": 20},
                        {"stamina": 1}, {"hits": 25},
                        {"hits": 1, "last": 1048}):
            with self.subTest(changes=changes):
                self.assertIsNone(self.propose(
                    self.raw(**changes))[0])
        context = self.context.Read(self.context,
            self.raw(now=2000), lua_table(self.h.lua,
                self.h.session), 0, 2)[0]
        self.assertEqual(context["takedown"]["status"],
                         "unknown")

    def test_stage_clear_can_confirm_without_new_attack_quote(self):
        before = self.raw()
        proposal = self.propose(before)[0]
        baseline = self.evidence.capture(proposal, before)[0]
        self.h.at(1)
        after = self.raw(revision=2, damage=150,
            free_used=2, hits=1, last=1050)
        after["familyTakedownProof"]["state"]["stage"] = 3
        after["familyAttackProof"] = None
        reply = lua_table(self.h.lua, {"ok": True, "dmg": 50,
            "tickets": 0, "freeLeft": 1})
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, reply, baseline), "confirmed")

    def test_current_native_overtime_stage_six_keeps_free_attack_safety(self):
        before=self.raw()
        before.familyTakedownProof.state.stage=6
        before.familyAttackProof.stage=6
        proposal,reason=self.propose(before)
        self.assertIsNone(reason)
        self.assertEqual(proposal.intent.stage,6)
        baseline,reason=self.evidence.capture(proposal,before)
        self.assertIsNone(reason)
        after=self.raw(revision=2,damage=150,free_used=2,hits=1,last=1050)
        after.familyTakedownProof.state.stage=6
        after.familyAttackProof.stage=6
        reply=lua_table(self.h.lua,{'ok':True,'dmg':50,'freeLeft':1,'tickets':0})
        self.assertEqual(self.evidence.evaluate(proposal,before,after,reply,baseline),'confirmed')
        blocked=self.raw(tickets=1)
        blocked.familyTakedownProof.state.stage=6;blocked.familyAttackProof.stage=6
        self.assertIsNone(self.propose(blocked)[0])
        blocked.familyTakedownProof.state.stage=7;blocked.familyAttackProof.stage=7
        context=self.context.Read(self.context,blocked,lua_table(self.h.lua,self.h.session),0,2)[0]
        self.assertIsNone(self.reader.read(blocked,context)[0])

    def test_overtime_call_plans_and_durable_allowance_accept_exact_stage_six(self):
        proposal=self.propose(self.raw())[0]
        proposal.intent.stage=6
        for path in ('src/tabs/combat/CombatCallPlan.luau','src/transport/NativeCallPlan.luau'):
            with self.subTest(path=path):
                call,reason=self.h.load(path).describe(proposal)
                self.assertIsNone(reason)
                self.assertEqual((call.remote,call.arity,call.args[1]),('FamilyBossAction',1,'attack'))
        store=self.h.lua.execute('''return {data={},strictRecovery=true,
            Read=function(self,k) return self.data[k] end,
            Write=function(self,k,v) self.data[k]=v;return true end}''')
        checkpoint=self.h.load('src/storage/Checkpoint.luau').new(store)
        checkpoint.Load(checkpoint,self.h.session['account'],self.h.session['place'],self.h.session['release'])
        saved,reason=checkpoint.Save(checkpoint,proposal)
        self.assertTrue(saved,reason)
        self.assertEqual(checkpoint.FamilyAttackUsage(checkpoint,100,9,0).hits,1)

    def unknown_damage(self,**changes):
        raw=self.raw(health=100,**changes)
        proof=raw.familyAttackProof
        proof.hitBackMax=None;proof.hitBackKnown=False
        proof.nativePreflight=True;proof.controllersClear=True;proof.sourceKey='a'*64
        proof.header=lua_table(self.h.lua,{key:raw[key] for key in
            ('session','account','place','release','revision','capturedAt')})
        proof.hospitalHealth=20
        return raw

    def unknown_proposal(self,before):
        context=self.context.Read(self.context,before,lua_table(self.h.lua,self.h.session),0,2)[0]
        view,reason=self.reader.read(before,context);self.assertIsNone(reason)
        proposal,reason=self.planner.propose(view,lua_table(self.h.lua,{
            'enabled':True,'allowUncalculatedHitBack':True}),self.h.lua.table())
        self.assertIsNone(reason)
        return proposal

    def test_unknown_hit_back_needs_distinct_consent_full_health_and_first_weekly_attempt(self):
        before=self.unknown_damage()
        context=self.context.Read(self.context,before,lua_table(self.h.lua,self.h.session),0,2)[0]
        view,reason=self.reader.read(before,context);self.assertIsNone(reason)
        for permission in (None,False,'true'):
            with self.subTest(permission=permission):
                self.assertIsNone(self.planner.propose(view,lua_table(self.h.lua,{
                    'enabled':True,'allowUncalculatedHitBack':permission}),self.h.lua.table())[0])
        proposal,reason=self.planner.propose(view,lua_table(self.h.lua,{
            'enabled':True,'allowUncalculatedHitBack':True}),self.h.lua.table())
        self.assertIsNone(reason)
        self.assertTrue(proposal.intent.uncalculatedHitBack)
        self.assertIsNone(proposal.intent.expectedHitBackMax)
        baseline,reason=self.evidence.capture(proposal,before);self.assertIsNone(reason)
        for change in ('health','usage','controller'):
            with self.subTest(change=change):
                altered=self.unknown_damage(hits=1 if change=='usage' else 0)
                if change=='health':altered.native.pools.health=99
                if change=='controller':altered.familyAttackProof.controllersClear=False
                self.assertIsNone(self.evidence.capture(proposal,altered)[0])

    def test_pending_callback_never_confirms_or_rejects_a_free_hit(self):
        before=self.raw();proposal=self.propose(before)[0]
        baseline=self.evidence.capture(proposal,before)[0]
        after=self.raw(revision=2,damage=150,free_used=2,hits=1,last=1050)
        reply=lua_table(self.h.lua,{'ok':True,'pending':True,'dmg':50,'freeLeft':1,'tickets':0})
        self.assertEqual(self.evidence.evaluate(proposal,before,after,reply,baseline),'pending')
        for code in ('rate_limited','busy','presence'):
            with self.subTest(code=code):
                self.assertEqual(self.evidence.evaluate(proposal,before,self.raw(revision=2),
                    lua_table(self.h.lua,{'ok':False,'code':code}),baseline),'pending')

    def test_checkpoint_independently_caps_unknown_damage_at_one_attempt(self):
        before=self.unknown_damage();proposal=self.unknown_proposal(before)
        store=self.h.lua.execute('''return {data={},strictRecovery=true,
            Read=function(self,k) return self.data[k] end,
            Write=function(self,k,v) self.data[k]=v;return true end}''')
        cp=self.h.load('src/storage/Checkpoint.luau').new(store)
        cp.Load(cp,self.h.session['account'],self.h.session['place'],self.h.session['release'])
        self.assertTrue(cp.Save(cp,proposal)[0])
        self.assertTrue(cp.Resolve(cp,proposal.actionKey,'confirmed')[0])
        proposal.intent.hitsBefore=1;proposal.intent.lastServerNowBefore=1050;proposal.intent.serverNow=1055
        proposal.actionKey='familyBossAttacks:second'
        saved,reason=cp.Save(cp,proposal)
        self.assertFalse(saved)
        self.assertEqual(cp.FamilyAttackUsage(cp,100,9,0).hits,1)

    def test_unknown_damage_holds_all_health_and_respects_other_stamina_reservations(self):
        before=self.unknown_damage();proposal=self.unknown_proposal(before)
        module=self.h.load('src/engine/ResourceReservations.luau')
        claims,reason=module.ForProposal(proposal,before);self.assertIsNone(reason)
        self.assertEqual(claims.funds.health,100)
        record=lua_table(self.h.lua,{**self.h.session,'feature':'other','actionKey':'other',
            'resources':{'health':1}})
        owner=module.new(lua_table(self.h.lua,self.h.session),
            self.h.lua.eval('function(record) return function() return {record} end end')(record))
        self.assertIsNone(owner.Check(owner,proposal,before)[0])
        record.resources=lua_table(self.h.lua,{'stamina':4})
        self.assertIsNone(owner.Check(owner,proposal,before)[0])
        record.resources.stamina=3
        self.assertIsNotNone(owner.Check(owner,proposal,before)[0])


if __name__ == "__main__":
    unittest.main()
