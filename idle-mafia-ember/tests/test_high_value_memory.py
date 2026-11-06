"""Default-rule high-value classification is atomic with exact owned fight history."""
import unittest
import test_player_fight_ledger as fixture
from engine_harness import lua_table

class HighValueMemoryTests(unittest.TestCase):
    def setUp(self):
        self.b=fixture.PlayerFightLedgerTests();self.b.setUp();self.h=self.b.h;self.f=self.b.f
        self.owner=self.b.owner;self.storage=self.b.storage;self.module=self.b.module
    def record(self,n,cash,target=42,estimate=None):
        name='Target B' if target==42 else 'Target_'+str(target)
        self.f.p.requestId=n;self.f.p.actionKey='combat:'+str(target)+':'+str(n)
        self.f.p.intent.target=target;self.f.p.intent.targetName=name;self.f.p.intent.serverNow=self.f.now+n
        self.f.before.native.serverNow=self.f.now+n;self.f.after.native.serverNow=self.f.now+n+1
        row=self.f.before.hitListProof.rows[1];row.userId=target;row.name=name
        self.f.after.native.attackDaily.counts=lua_table(self.h.lua,{str(target):1})
        for native in (self.f.initial,self.f.final):
            native['fightId']='high-value-fixture-'+str(n);native['targetName']=name
            if 'targetDaily' in native:native['targetDaily']['serverNow']=self.f.now+n
            native['cashEstimate']=cash if estimate is None else estimate
        self.f.final['cashConfirmed']=cash;self.f.final['stolen']=cash
        attempt=self.f.after.playerFightProof.attempts[1];attempt.target=target;attempt.actionKey=self.f.p.actionKey
        attempt.initial=lua_table(self.h.lua,self.f.initial);attempt.receipt=lua_table(self.h.lua,self.f.final)
        self.f.baseline=self.f.e.capture(self.f.p,self.f.before)[0]
        self.assertIsNotNone(self.f.baseline)
        return self.owner.Record(self.owner,self.f.data(),self.f.after)
    def status(self):return self.owner.HighValueStatus(self.owner,self.f.after)
    def new(self):
        owner,why=self.module.new(self.storage,lua_table(self.h.lua,self.h.session),self.f.e)
        self.assertIsNotNone(owner,why);return owner
    def test_exact_promotion_threshold_and_three_consecutive_low_payouts(self):
        self.assertTrue(self.record(1,999999999)[0]);self.assertEqual(self.status().count,0)
        self.assertTrue(self.record(2,1000000000)[0]);self.assertEqual(self.status().count,1)
        for n in (3,4):self.assertTrue(self.record(n,99999999)[0]);self.assertEqual(self.status().count,1)
        self.assertTrue(self.record(5,99999999)[0]);self.assertEqual(self.status().count,0)
    def test_mid_payout_resets_streak_and_repromotion_updates_known_high(self):
        for n,cash in enumerate((1000000000,0,100000000,0,0,2000000000),1):self.assertTrue(self.record(n,cash)[0])
        memory=self.owner.Summary(self.owner).highValue
        self.assertEqual((memory.targets['42'].lowStreak,memory.targets['42'].lastHighCash),(0,2000000000))
        self.assertEqual(self.status().count,1)
    def test_duplicate_terminal_cleanup_never_double_counts_a_low_payout(self):
        self.record(1,1000000000);self.record(2,0)
        self.assertTrue(self.owner.Record(self.owner,self.f.data(),self.f.after)[0])
        self.assertEqual(self.owner.Summary(self.owner).highValue.targets['42'].lowStreak,1)
    def test_promoted_identity_survives_global_receipt_compaction_and_reload(self):
        self.record(1,1000000000)
        for n in range(2,36):self.assertTrue(self.record(n,1,100+n)[0])
        self.owner=self.new();summary=self.owner.Summary(self.owner)
        self.assertNotIn(42,[r.target for r in summary.recent.values()])
        self.assertEqual(self.status().count,1)
        targets=self.owner.HighValueTargets(self.owner,self.f.after)
        self.assertEqual((targets[1].userId,targets[1].history[1].cash),(42,1000000000))
    def test_complete_old_ledger_can_derive_tags_but_truncated_old_ledger_stays_unknown(self):
        self.record(1,1000000000);self.storage.data[self.owner.key].highValue=None;self.owner=self.new()
        self.assertTrue(self.status().known);self.assertEqual(self.status().count,1)
        for n in range(2,36):self.assertTrue(self.record(n,1,100+n)[0])
        self.storage.data[self.owner.key].highValue=None;self.owner=self.new()
        self.assertFalse(self.status().known);self.assertIsNone(self.status().count)
        self.assertTrue(self.record(36,1)[0]);self.assertFalse(self.status().known)
        self.assertIsNone(self.owner.HighValueTargets(self.owner,self.f.after))
    def test_failed_or_ambiguous_write_never_advertises_uncommitted_memory(self):
        self.record(1,1000000000);self.storage.fail=True
        self.assertFalse(self.record(2,0)[0]);self.assertFalse(self.status().known)
        self.storage.fail=False;self.owner=self.new()
        self.assertEqual(self.owner.Summary(self.owner).highValue.targets['42'].lowStreak,0)
        self.storage.Write=self.h.lua.eval('function(self,k,v) self.data[k]=v;return false end')
        self.assertFalse(self.record(2,0)[0]);self.assertFalse(self.status().known)
        self.owner=self.new();self.assertEqual(self.owner.Summary(self.owner).highValue.targets['42'].lowStreak,1)
    def test_corrupt_memory_cannot_be_loaded_or_normalized_to_zero(self):
        self.record(1,1000000000);self.storage.data[self.owner.key].highValue.count=0
        self.assertIsNone(self.module.new(self.storage,lua_table(self.h.lua,self.h.session),self.f.e)[0])
    def test_recent_promotion_cannot_disappear_after_global_history_compaction(self):
        for n in range(1,33):self.record(n,1,100+n)
        self.record(33,1000000000)
        memory=self.storage.data[self.owner.key].highValue;memory.targets=self.h.lua.table();memory.count=0
        self.assertIsNone(self.module.new(self.storage,lua_table(self.h.lua,self.h.session),self.f.e)[0])
    def test_memory_cannot_skip_a_retained_low_settlement_after_compaction(self):
        for n in range(1,33):self.record(n,1,100+n)
        self.record(33,1000000000);self.record(34,0)
        target=self.storage.data[self.owner.key].highValue.targets['42']
        target.history[2]=None;target.requestId=33;target.lowStreak=0
        self.assertIsNone(self.module.new(self.storage,lua_table(self.h.lua,self.h.session),self.f.e)[0])
    def test_storage_safe_target_cap_preserves_history_and_marks_overflow_unknown(self):
        for n in range(1,129):self.assertTrue(self.record(n,1000000000,100+n)[0])
        self.assertEqual(self.status().count,128)
        self.assertTrue(self.record(129,1000000000,10000)[0])
        self.assertFalse(self.status().known);self.assertEqual(self.status().retained,128)
        self.assertEqual(sum(1 for _ in self.owner.Summary(self.owner).highValue.targets.keys()),128)
        self.owner=self.new();self.assertFalse(self.status().known)
    def test_full_target_history_envelope_fits_actual_redundant_store(self):
        import copy,json
        import test_redundant_store as disk_fixture
        for n in range(1,129):self.assertTrue(self.record(n,1000000000,100+n)[0])
        raw=disk_fixture.plain(self.owner.Summary(self.owner));cash=9007199254740991//4096
        name=chr(128)*32;session=chr(128)*100
        raw.update(fights=4096,wins=4096,stamina=4096,cash=4096*cash,lastRequestId=4096)
        memory=raw['highValue'];memory.update(lastRequestId=4096,count=128,overflow=False)
        for key,target in memory['targets'].items():
            index=target['userId']-100;last=3968+index
            target.update(name=name,requestId=last,lastHighCash=cash,promotedAt=self.f.now+last,lowStreak=0)
            target['history']=[{'requestId':index+128*r,'at':self.f.now+index+128*r,'cash':cash,'won':True} for r in range(32)]
        for row in raw['recent']:
            n=3968+row['target']-100;at=self.f.now+n
            row.update(requestId=n,actionKey=chr(128)*480+str(n),session=session,serverNow=at,day=int(at//86400),targetName=name)
            for packet in (row['initial'],row['receipt']):
                packet.update(fightId=chr(128)*70+str(n),targetName=name,cashEstimate=cash)
                if 'targetDaily' in packet:packet['targetDaily'].update(day=int(at//86400),serverNow=at)
            row['receipt'].update(cashConfirmed=cash,stolen=cash)
        self.storage.data[self.owner.key]=lua_table(self.h.lua,raw);owner=self.new()
        self.owner=owner
        payload=disk_fixture.plain(owner.Summary(owner))
        self.assertLess(len(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()),800000)
        disk=disk_fixture.RedundantStoreTests();disk.setUp()
        self.assertTrue(disk.store.Write(disk.store,'full-high-memory',lua_table(disk.h.lua,payload)))
        self.assertEqual(disk.store.Read(disk.store,'full-high-memory').highValue.count,128)
    def test_detached_memory_scope_and_close_do_not_leak_or_grant_tags(self):
        self.record(1,1000000000);targets=self.owner.HighValueTargets(self.owner,self.f.after)
        targets[1].name='forged';targets[1].history[1].cash=0
        self.assertEqual(self.owner.HighValueTargets(self.owner,self.f.after)[1].history[1].cash,1000000000)
        self.f.after.account='other';self.assertFalse(self.status().known)
        self.f.after.account=self.h.session['account'];self.owner.Close(self.owner);self.assertFalse(self.status().known)
    def test_native_estimate_never_promotes_without_confirmed_cash(self):
        self.assertTrue(self.record(1,1,estimate=1000000000)[0]);self.assertEqual(self.status().count,0)
    def test_war_outcomes_advance_ledger_marker_without_promoting_or_demoting(self):
        import test_war_fight_evidence as war_fixture
        import test_player_fight_evidence as ordinary_fixture
        war=war_fixture.WarFightEvidenceTests();war.setUp()
        self.h=war.h
        # Both lanes use their actual evidence contracts in one Lua/storage scope.
        self.f=ordinary_fixture.PlayerFightEvidenceTests();self.f.provided_h=self.h;self.f.setUp()
        self.storage=self.h.lua.execute("""return {strictRecovery=true,data={},Read=function(self,k) return self.data[k] end,
            Write=function(self,k,v) self.data[k]=v;return true end}""")
        self.module=self.h.load('src/tabs/combat/PlayerFightLedger.luau')
        self.owner,why=self.module.new(self.storage,lua_table(self.h.lua,self.h.session),war.e)
        self.assertIsNotNone(self.owner,why)
        def record_war(n,cash):
            war.p.requestId=n;war.p.actionKey='warCombat:attack:42:'+str(n)
            for packet in (war.initial,war.final):
                packet['fightId']='war-high-value-fixture-'+str(n);packet['cashEstimate']=cash
            war.final['cashConfirmed']=cash;war.final['stolen']=cash
            attempt=war.after.playerFightProof.attempts[1];attempt.actionKey=war.p.actionKey
            attempt.initial=lua_table(self.h.lua,war.initial);attempt.receipt=lua_table(self.h.lua,war.final)
            war.baseline,why=war.e.capture(war.p,war.before)
            self.assertIsNotNone(war.baseline,why)
            return self.owner.Record(self.owner,war.data(),war.after)
        self.assertTrue(record_war(1,1000000000)[0]);self.assertEqual(self.status().count,0)
        self.assertTrue(self.record(2,1000000000)[0]);self.assertEqual(self.status().count,1)
        for n in (3,4,5):self.assertTrue(record_war(n,0)[0])
        summary=self.owner.Summary(self.owner)
        self.assertEqual(summary.highValue.lastRequestId,5);self.assertEqual(summary.highValue.targets['42'].lowStreak,0)
        self.assertEqual([summary.recent[index].feature for index in range(1,6)],['warCombat','combat','warCombat','warCombat','warCombat'])
