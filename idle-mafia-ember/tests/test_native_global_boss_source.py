"""Global Boss attributes use native private/public precedence and access rules."""
import unittest

from engine_harness import Harness, lua_table


class NativeGlobalBossSourceTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.module = self.h.load("src/tabs/combat/NativeGlobalBossSource.luau")
        self.reader = self.h.load("src/game/GlobalBossState.luau")
        self.h.lua.globals().attributes = lua_table(self.h.lua, {"GlobalBossState": "public"})
        self.h.lua.globals().events = lua_table(self.h.lua, {
            "public": {"id": "hellfire", "startAt": 2000000, "endAt": 2001000,
                "hp": 10000, "dmg": 100, "status": "live"},
            "private": {"id": "judge", "startAt": 2000000, "endAt": 2001000,
                "hp": 20000, "dmg": 200, "status": "live", "testUserId": 42}})
        self.rule = self.h.lua.execute("""return {ATTR='GlobalBossState',PRIVATE_ATTR='GlobalBossPrivateState',
            decode=function(encoded) return events[encoded] end,
            canAccess=function(event,user) return event.testUserId==nil or event.testUserId==user end}""")
        self.source, reason = self.module.new(self.rule,
            self.h.lua.eval("function() return attributes end"), self.reader, 42, "a" * 64, "release-a")
        self.assertIsNone(reason)

    def raw(self, revision=1):
        return self.h.snapshot(revision=revision, native={"fullSync": True,
            "serverNow": 2000100, "gb": {"run": "hellfire_2000000", "dmg": 50,
                "hits": 2, "claimed": False}})

    def test_reviewed_cooldown_is_freshly_bound_without_losing_event_evidence(self):
        self.rule.ATTACK_COOLDOWN=1.25
        enriched,reason=self.source.Enrich(self.source,self.raw());self.assertIsNone(reason)
        self.assertEqual(enriched.globalBossProof.attackCooldown,1.25)
        self.assertEqual(enriched.globalBossProof.attackCooldownStatus,'known')
        self.rule.ATTACK_COOLDOWN=7.5
        enriched,reason=self.source.Enrich(self.source,self.raw());self.assertIsNone(reason)
        self.assertEqual(enriched.globalBossProof.attackCooldown,7.5)
        self.assertEqual(enriched.globalBossProof.event.id,'hellfire')
    def test_invalid_cooldown_blocks_only_attack_proof_and_never_revives_fallback(self):
        for value in (0,-1,121,'1.25',float('nan')):
            self.rule.ATTACK_COOLDOWN=value
            source,reason=self.module.new(self.rule,self.h.lua.eval("function() return attributes end"),self.reader,42,'a'*64,'release-a')
            self.assertIsNone(reason)
            enriched,reason=source.Enrich(source,self.raw());self.assertIsNone(reason)
            self.assertTrue(enriched.globalBossProof.attackCooldownUnavailable)
            self.assertIsNone(enriched.globalBossProof.attackCooldown)
            self.assertEqual(enriched.globalBossProof.event.id,'hellfire')
            self.rule.ATTACK_COOLDOWN=None
            enriched,reason=source.Enrich(source,self.raw());self.assertIsNone(reason)
            self.assertEqual(enriched.globalBossProof.attackCooldownStatus,'unavailable')
        enriched,reason=self.source.Enrich(self.source,self.raw());self.assertIsNone(reason)
        self.assertEqual(enriched.globalBossProof.attackCooldownStatus,'legacy-absent')
    def test_cooldown_change_during_native_read_preserves_event_but_blocks_attack(self):
        self.rule.ATTACK_COOLDOWN=1.25;self.h.lua.globals().changingRule=self.rule
        source,reason=self.module.new(self.rule,self.h.lua.eval("function() changingRule.ATTACK_COOLDOWN=7.5;return attributes end"),self.reader,42,'a'*64,'release-a')
        self.assertIsNone(reason)
        enriched,reason=source.Enrich(source,self.raw());self.assertIsNone(reason)
        self.assertTrue(enriched.globalBossProof.attackCooldownUnavailable)
        self.assertEqual(enriched.globalBossProof.event.id,'hellfire')
        enriched,reason=source.Enrich(source,self.raw());self.assertIsNone(reason)
        self.assertFalse(enriched.globalBossProof.attackCooldownUnavailable)
        self.assertEqual(enriched.globalBossProof.attackCooldown,7.5)
    def test_observed_valid_then_missing_does_not_restore_legacy_fallback(self):
        self.rule.ATTACK_COOLDOWN=1.25
        self.source.Enrich(self.source,self.raw())
        self.rule.ATTACK_COOLDOWN=None
        enriched,reason=self.source.Enrich(self.source,self.raw());self.assertIsNone(reason)
        self.assertTrue(enriched.globalBossProof.attackCooldownUnavailable)
        self.assertEqual(enriched.globalBossProof.event.id,'hellfire')

    def test_public_event_produces_exact_identity_and_state_proofs(self):
        enriched, reason = self.source.Enrich(self.source, self.raw())
        self.assertIsNone(reason)
        self.assertEqual(enriched.globalBossProof.event.id, "hellfire")
        self.assertEqual(enriched.localUserIdProof.userId, 42)
        enriched.serverNow = enriched.native.serverNow
        view, reason = self.reader.read(enriched, enriched)
        self.assertIsNone(reason)
        self.assertEqual(view.remainingHp, 8900)
        self.assertEqual(len(self.h.transport.sent), 0)

    def test_private_event_precedes_public_and_inaccessible_is_hidden(self):
        self.h.lua.globals().attributes.GlobalBossPrivateState = "private"
        enriched, _ = self.source.Enrich(self.source, self.raw())
        self.assertEqual(enriched.globalBossProof.event.id, "judge")
        self.h.lua.globals().events.private.testUserId = 99
        enriched, _ = self.source.Enrich(self.source, self.raw())
        self.assertIsNone(enriched.globalBossProof.event)
        self.assertIsNone(enriched.globalBossProof.eventId)

    def test_empty_or_invalid_private_cannot_fall_back_to_public(self):
        for value in ("", "invalid"):
            self.h.lua.globals().attributes.GlobalBossPrivateState = value
            enriched, reason = self.source.Enrich(self.source, self.raw())
            if value == "":
                self.assertIsNone(reason)
                self.assertIsNone(enriched.globalBossProof.event)
            else:
                self.assertIsNone(enriched)
                self.assertIn("decode", reason)

    def test_no_event_replaces_forged_proof_and_returned_tables_are_copies(self):
        first, _ = self.source.Enrich(self.source, self.raw())
        first.globalBossProof.event.dmg = 999
        second, _ = self.source.Enrich(self.source, self.raw())
        self.assertEqual(second.globalBossProof.event.dmg, 100)
        self.h.lua.globals().attributes.GlobalBossState = None
        raw = self.raw()
        raw.globalBossProof = first.globalBossProof
        empty, reason = self.source.Enrich(self.source, raw)
        self.assertIsNone(reason)
        self.assertIsNone(empty.globalBossProof.event)

    def test_wrong_release_partial_sync_malformed_event_and_close_are_refused(self):
        raw = self.raw()
        raw.release = "other"
        self.assertIsNone(self.source.Enrich(self.source, raw)[0])
        raw = self.raw()
        raw.native.fullSync = False
        self.assertIsNone(self.source.Enrich(self.source, raw)[0])
        self.h.lua.globals().events.public.hp = 1
        self.assertIsNone(self.source.Enrich(self.source, self.raw())[0])
        self.source.Close(self.source)
        self.assertIsNone(self.source.Enrich(self.source, self.raw())[0])


if __name__ == "__main__":
    unittest.main()
