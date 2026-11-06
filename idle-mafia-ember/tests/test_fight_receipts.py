"""Owned initial Attack reply binds native staged payouts; no send or replay."""
import copy
import json
from pathlib import Path
import unittest
from engine_harness import Harness, lua_table

LIVE = json.loads((Path(__file__).parents[1] / "docs/native-combat-live-2026-11-01.json").read_text())

class FightReceiptTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness()
        self.lane=self.h.load("src/engine/RequestLane.luau").new(self.h.clock)
        self.source=self.h.lua.execute("""return {callback=nil,disconnected=0,
            Subscribe=function(self,cb) self.callback=cb;return {Disconnect=function() self.disconnected=self.disconnected+1 end} end,
            CanAttack=function() return true end,Current=function() return true end}""")
        self.owner=self.h.load("src/tabs/combat/FightReceipts.luau").new(lua_table(self.h.lua,self.h.session),self.h.clock,self.lane,self.source,"a"*64)
        self.token=self.lane.TryAcquire(self.lane,"mutation","combat:42",45)[0]
        self.proposal=lua_table(self.h.lua,{**self.h.session,"feature":"combat","actionKey":"combat:42","resources":{"stamina":1},"intent":{"kind":"playerAttack","target":42}})
        self.initial=copy.deepcopy(LIVE["second"]["initial"])
        self.frames=copy.deepcopy(LIVE["second"]["notifications"])
    def begin(self):
        self.assertTrue(self.owner.Begin(self.owner,self.token,self.proposal,42)[0])
    def bind(self):
        return self.owner.Bind(self.owner,self.token,lua_table(self.h.lua,self.initial))
    def emit(self,frame):
        self.source.callback("fightcash","",lua_table(self.h.lua,frame))
    def read(self):
        return self.owner.Read(self.owner,self.h.snapshot())
    def test_live_stages_bind_only_to_owned_initial_reply_and_return_detached_proof(self):
        self.begin();self.assertTrue(self.bind()[0])
        for f in self.frames:
            self.emit(f);proof=self.read();row=proof.attempts[1]
            self.assertEqual(row.receipt.cashStage,f["cashStage"])
            self.assertEqual(row.target,42)
            self.assertEqual(row.status,"settled" if f["cashStage"]==4 else "pending")
        proof.attempts[1].receipt.cashConfirmed=0
        self.assertEqual(self.read().attempts[1].receipt.cashConfirmed,36274716)
        self.assertEqual(len(self.h.transport.sent),0)
    def test_notification_before_initial_reply_is_buffered_but_not_owned_until_bound(self):
        self.begin();self.emit(self.frames[-1]);self.assertEqual(len(self.read().attempts),0)
        self.assertTrue(self.bind()[0]);self.assertEqual(self.read().attempts[1].status,"settled")
    def test_foreign_manual_fight_is_never_promoted(self):
        self.begin();other=copy.deepcopy(self.frames[-1]);other["fightId"]="manual-fight"
        self.emit(other);self.assertTrue(self.bind()[0]);self.assertEqual(self.read().attempts[1].receipt.cashStage,1)
    def test_older_stage_cannot_replace_settled_receipt(self):
        self.begin();self.bind();self.emit(self.frames[-1]);self.emit(self.frames[0])
        self.assertEqual(self.read().attempts[1].status,"settled")
    def test_conflicting_same_stage_fences_success(self):
        self.begin();self.bind();self.emit(self.frames[-1]);bad=copy.deepcopy(self.frames[-1]);bad["cashConfirmed"]+=1
        self.emit(bad);self.assertEqual(self.read().attempts[1].status,"ambiguous")
    def test_stage_four_with_pending_flag_is_not_settled(self):
        self.begin();self.bind();bad=copy.deepcopy(self.frames[-1]);bad["rewardsPending"]=True;self.emit(bad)
        self.assertNotEqual(self.read().attempts[1].status,"settled")
    def test_canceled_or_failed_receipt_is_never_a_success(self):
        self.begin();self.bind();bad=copy.deepcopy(self.frames[-1]);bad["ok"]=False;bad["won"]=False;self.emit(bad)
        self.assertNotEqual(self.read().attempts[1].status,"settled")
    def test_changed_fight_identity_cannot_replace_bound_initial_reply(self):
        self.begin();self.bind();self.initial["fightId"]="different"
        self.assertFalse(self.bind()[0]);self.assertEqual(self.read().attempts[1].status,"ambiguous")
    def test_released_or_expired_lease_fences_late_callback(self):
        self.begin();self.bind();cb=self.source.callback
        self.lane.Release(self.lane,self.token,"disabled");cb("fightcash","",lua_table(self.h.lua,self.frames[-1]))
        self.assertEqual(len(self.read().attempts),0)
    def test_exact_45_second_deadline_cannot_promote_late_reply(self):
        self.begin();self.h.at(45);self.assertFalse(self.bind()[0]);self.assertEqual(len(self.read().attempts),0)
    def test_source_replacement_fences_packets_and_read(self):
        self.begin();self.bind();self.source.Current=self.h.lua.eval("function() return false end")
        self.emit(self.frames[-1]);self.assertIsNone(self.read())
    def test_close_disconnects_and_old_callback_cannot_write(self):
        self.begin();self.bind();cb=self.source.callback;self.owner.Close(self.owner)
        cb("fightcash","",lua_table(self.h.lua,self.frames[-1]))
        self.assertEqual(self.source.disconnected,1);self.assertIsNone(self.read())
    def test_wrong_scope_target_read_lease_and_non_player_action_do_not_admit(self):
        self.proposal.account="other";self.assertFalse(self.owner.Begin(self.owner,self.token,self.proposal,42)[0])
        self.proposal.account="user-a";self.assertFalse(self.owner.Begin(self.owner,self.token,self.proposal,43)[0])
        self.proposal.feature="bosses";self.assertFalse(self.owner.Begin(self.owner,self.token,self.proposal,42)[0])
    def test_bad_packets_do_not_become_settled(self):
        self.begin();self.bind()
        for changes in ({"fightId":""},{"cashStage":5},{"cashConfirmed":float("nan")},{"cashStage":4.5}):
            bad=copy.deepcopy(self.frames[-1]);bad.update(changes);self.emit(bad)
            self.assertEqual(self.read().attempts[1].receipt.cashStage,1)

    def test_changed_target_levels_or_stamina_charge_fence_the_same_fight(self):
        for field in ("targetLevel","targetShownLevel","staminaCost"):
            self.setUp();self.begin();self.bind();bad=copy.deepcopy(self.frames[-1]);bad[field]+=1
            self.emit(bad);self.assertEqual(self.read().attempts[1].status,"ambiguous")

    def test_absent_native_execution_guard_cannot_admit_a_new_attempt(self):
        self.source.CanAttack=None
        self.assertFalse(self.owner.Begin(self.owner,self.token,self.proposal,42)[0])
        self.assertIsNone(self.source.callback)

    def test_canceled_older_stage_cannot_leave_successful_proof(self):
        self.begin();self.bind();self.emit(self.frames[-1])
        canceled=copy.deepcopy(self.frames[0]);canceled['ok']=False;canceled['won']=False
        self.emit(canceled);self.assertEqual(self.read().attempts[1].status,'ambiguous')
    def test_release_disconnects_and_old_subscription_cannot_observe_new_attempt(self):
        self.begin();self.bind();old=self.source.callback
        self.owner.Release(self.owner,self.token)
        self.assertEqual(self.source.disconnected,1)
        self.lane.Release(self.lane,self.token,'confirmed')
        self.token=self.lane.TryAcquire(self.lane,'mutation','combat:42',45)[0]
        self.begin();old('fightcash','',lua_table(self.h.lua,self.frames[-1]));self.bind()
        self.assertEqual(self.read().attempts[1].receipt.cashStage,1)

    def test_initial_cost_different_from_reserved_stamina_never_settles(self):
        self.begin();self.initial['staminaCost']=2
        self.assertFalse(self.bind()[0])
        changed=copy.deepcopy(self.frames[-1]);changed['staminaCost']=2;self.emit(changed)
        self.assertEqual(self.read().attempts[1].status,'ambiguous')
    def test_missing_or_extra_resource_charge_cannot_start_a_fight(self):
        self.proposal.resources=None
        self.assertFalse(self.owner.Begin(self.owner,self.token,self.proposal,42)[0])
        self.proposal.resources=lua_table(self.h.lua,{'stamina':1,'cash':1})
        self.assertFalse(self.owner.Begin(self.owner,self.token,self.proposal,42)[0])
        self.assertIsNone(self.source.callback)

    def test_max_reservation_keeps_exact_lower_quoted_cost_receipt_binding(self):
        self.proposal.resources.stamina=5;self.proposal.intent.expectedStaminaCost=1;self.proposal.intent.maxStaminaExposure=5
        self.begin();self.assertTrue(self.bind()[0]);self.emit(self.frames[-1])
        self.assertEqual(self.read().attempts[1].status,'settled')
    def test_unquoted_or_inconsistent_larger_reservation_is_not_admitted(self):
        self.proposal.resources.stamina=5;self.proposal.intent.expectedStaminaCost=1
        self.assertFalse(self.owner.Begin(self.owner,self.token,self.proposal,42)[0])
        self.proposal.intent.maxStaminaExposure=4
        self.assertFalse(self.owner.Begin(self.owner,self.token,self.proposal,42)[0])

    def test_native_target_daily_times_may_be_fractional_without_changing_day_or_count(self):
        self.initial['targetDaily']['serverNow']+=.25;self.initial['targetDaily']['resetAt']=.5
        self.begin();self.assertTrue(self.bind()[0])

    def test_scout_preflight_requires_exact_lease_scope_and_guard_without_notification_subscription(self):
        self.proposal.intent.kind='playerScout'
        self.source.CanScout=self.h.lua.eval('function() return true end')
        self.assertTrue(self.owner.CheckScout(self.owner,self.token,self.proposal,42)[0])
        self.assertIsNone(self.source.callback)
        self.source.CanScout=self.h.lua.eval('function() return false end')
        self.assertFalse(self.owner.CheckScout(self.owner,self.token,self.proposal,42)[0])
        self.source.CanScout=self.h.lua.eval('function() return true end')
        self.proposal.intent.target=43
        self.assertFalse(self.owner.CheckScout(self.owner,self.token,self.proposal,42)[0])
        self.proposal.intent.target=42;self.h.at(45)
        self.assertFalse(self.owner.CheckScout(self.owner,self.token,self.proposal,42)[0])
