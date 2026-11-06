"""Attack and own-Scout recovery for independent ordinary and war lanes."""
import unittest

from engine_harness import lua_table
from recovery_projection_harness import assert_projection
import test_war_combat


class CombatRecoveryProjectionTests(unittest.TestCase):
    def test_scout_and_attack_capture_survive_each_lane_projection(self):
        for feature in ("combat","warCombat"):
            with self.subTest(feature=feature):
                helper = test_war_combat.WarCombatFlowTests(methodName="runTest")
                helper.setUp()
                helper.quote_and_profile()
                h = helper.h
                settings = helper.settings.warCombat
                if feature=="combat":
                    helper.settings.combat = settings
                    spec = helper.tab.Descriptors(helper.tab)[1]
                    profiles = helper.tab.playerProfiles
                    query = helper.tab.hitListQuery
                    request,reason = query.Prepare(query,helper.raw)
                    self.assertIsNone(reason)
                    staged,reason = query.Accept(query,helper.raw,request,lua_table(h.lua,{
                        "ok":True,"warStatus":helper.status,"list":[{"userId":789,"name":"Other",
                            "level":10,"familyId":"other","stamina":1,"shielded":False}]}))
                    self.assertIsNone(reason)
                    self.assertTrue(query.Commit(query,staged))
                    request,reason = profiles.Prepare(profiles,helper.raw,30)
                    self.assertIsNone(reason)
                    staged,reason = profiles.Accept(profiles,helper.raw,request,lua_table(h.lua,{"ok":True,"profile":{
                        "userId":789,"name":"Other","level":10,"maxLevel":10,"familyId":"other",
                        "scoutCost":1,"statsHidden":True,"shieldLeft":0}}))
                    self.assertIsNone(reason)
                    self.assertTrue(profiles.Commit(profiles,staged))
                else:
                    spec = helper.spec
                context = h.load("src/game/Context.luau").new(h.contracts)
                def plan(raw):
                    before = helper.enrich(raw)
                    view,reason = context.Read(context,before,lua_table(h.lua,h.session),h.lua.globals().testNow,2)
                    self.assertIsNone(reason)
                    targets,reason = spec.reader.read(before,view)
                    self.assertIsNone(reason)
                    proposal,reason = spec.planner.propose(targets,settings,
                        lua_table(h.lua,{"stamina":0,"uncertainStamina":0}))
                    self.assertIsNone(reason)
                    return proposal,before
                scout,before = plan(helper.raw)
                self.assertEqual(scout.intent.kind,"playerScout")
                decoded = assert_projection(self,h,spec.evidence,scout,before)
                scout.requestId = 1
                reply = lua_table(h.lua,{"ok":True,"atk":100,"def":10,"crew":1})
                baseline = spec.evidence.capture(scout,before)[0]
                h.at(1)
                after = h.snapshot(revision=2,captured_at=1,native={"fullSync":True,"serverNow":101,"userId":123,
                    "level":10,"stats":{"maxHealth":100},"pools":{"health":100,"stamina":19},
                    "family":{"id":"own"},"derived":{"war":{"state":"active","enemyId":"enemy"}},
                    "attackDaily":{"day":0,"counts":{}}})
                enriched = helper.enrich(after)
                self.assertTrue(spec.recordOutcome(lua_table(h.lua,{
                    "proposal":scout,"before":before,"reply":reply,"baseline":baseline}),enriched)[0])
                attack,before = plan(after)
                self.assertEqual(attack.intent.kind,"playerAttack")
                self.assertEqual(attack.feature,feature)
                assert_projection(self,h,spec.evidence,attack,before)
                if feature=="combat":
                    # Exercise ordinary-only durable history, high-value membership,
                    # daily-only reset and a fresh public profile; war behavior is
                    # already covered by its separate exact-enemy flow tests.
                    attack.requestId = 2
                    baseline = spec.evidence.capture(attack,before)[0]
                    token,reason = helper.lane.TryAcquire(helper.lane,"mutation",attack.actionKey,45)
                    self.assertIsNone(reason)
                    receipts = helper.tab.fightReceipts
                    self.assertTrue(receipts.Begin(receipts,token,attack,789)[0])
                    first = {"ok":True,"won":True,"fightId":"ordinary-owned-1","cashStage":1,
                        "cashPending":True,"rewardsPending":True,"targetName":"Other",
                        "targetLevel":10,"targetShownLevel":10,"staminaCost":1,
                        "targetDaily":{"day":0,"count":1,"serverNow":101}}
                    initial = lua_table(h.lua,first)
                    self.assertTrue(receipts.Bind(receipts,token,initial)[0])
                    settled = lua_table(h.lua,{**first,"cashStage":4,"cashPending":False,
                        "rewardsPending":False,"cashConfirmed":1000000000,"stolen":1000000000,"xp":1,"respect":1})
                    helper.nativeSource.notify("fightcash",None,settled)
                    h.at(2)
                    after = h.lua.eval("function(raw) local function clone(v) if type(v)~='table' then return v end local out={} for k,x in pairs(v) do out[k]=clone(x) end return out end return clone(raw) end")(after)
                    after.revision,after.capturedAt,after.native.serverNow = 3,2,102
                    after.native.pools.stamina = 18
                    after.native.attackDaily.counts['789'] = 1
                    final = helper.enrich(after)
                    self.assertEqual(spec.evidence.evaluate(attack,before,final,initial,baseline),'confirmed')
                    data = lua_table(h.lua,{"proposal":attack,"before":before,"reply":initial,"baseline":baseline})
                    recorded,reason = spec.recordOutcome(data,final)
                    self.assertTrue(recorded,reason)
                    ledger = helper.tab.playerLedger
                    self.assertEqual(ledger.Summary(ledger).recent[1].feature,'combat')
                    saved = ledger.SavedTargets(ledger,final)
                    self.assertEqual((saved[1].userId,saved[1].name),(789,'Other'))
                    self.assertTrue(ledger.IsHighValue(ledger,final,789))
                    settings.dailyOnly = True
                    view = context.Read(context,final,lua_table(h.lua,h.session),2,2)[0]
                    targets = spec.reader.read(final,view)[0]
                    self.assertIsNone(spec.planner.propose(targets,settings,
                        lua_table(h.lua,{"stamina":0,"uncertainStamina":0}))[0])
                    # A new UTC day clears native daily count, but requires new
                    # target/profile reads; no old quote is promoted to current.
                    h.at(86401)
                    after.revision,after.capturedAt,after.native.serverNow = 4,86401,86401
                    after.native.attackDaily.day = 1
                    after.native.attackDaily.counts = h.lua.table()
                    after.native.derived.war = None
                    query = helper.tab.hitListQuery
                    request = query.Prepare(query,after)[0]
                    staged,reason = query.Accept(query,after,request,lua_table(h.lua,{
                        "ok":True,"warStatus":{"serverNow":86401,"day":1,"targets":[]},
                        "list":[{"userId":789,"name":"Other","level":10,"familyId":"other","stamina":1,"shielded":False}]}))
                    self.assertIsNone(reason)
                    self.assertTrue(query.Commit(query,staged))
                    profiles = helper.tab.playerProfiles
                    request = profiles.Prepare(profiles,after,30)[0]
                    staged,reason = profiles.Accept(profiles,after,request,lua_table(h.lua,{"ok":True,"profile":{
                        "userId":789,"name":"Other","level":10,"maxLevel":10,"familyId":"other",
                        "scoutCost":1,"statsHidden":False,"atk":100,"def":10,"crew":1,"shieldLeft":0}}))
                    self.assertIsNone(reason)
                    self.assertTrue(profiles.Commit(profiles,staged))
                    settings.targetSource,settings.allowScout = 'High value only',False
                    attack,before = plan(after)
                    self.assertEqual((attack.intent.kind,attack.intent.target),('playerAttack',789))
                    self.assertTrue(attack.intent.highValueOnly)
                    self.assertTrue(attack.intent.dailyOnly)
                    decoded = assert_projection(self,h,spec.evidence,attack,before)
                    self.assertEqual(list(decoded.before.playerFightHistoryProof.highValue.targets.keys()),['789'])
                    decoded.before.playerFightHistoryProof.highValue.targets['789'] = None
                    self.assertIsNone(spec.evidence.capture(decoded.proposal,decoded.before)[0])


if __name__ == "__main__":
    unittest.main()
