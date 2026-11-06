"""Historical receipts gate actual App/native owners without changing their scope."""
import hashlib
import copy
import json
import unittest

from engine_harness import lua_table
import test_heist_protocol_app as heist_fixture
import test_recall_runtime_app as recall_fixture
import test_legacy_completion_receipts as legacy_fixture


def make_carry(fixture, lease, kind, bind=True):
    h = fixture.h
    modules = fixture.base.runtime.modules if kind == 'heist' else fixture.modules
    target = fixture.base.runtime.checkpoint if kind == 'heist' else fixture.initial_checkpoint
    source_release = 'c' * 40
    old = legacy_fixture.LegacyCompletionReceiptTests(); old.setUp()
    old.h.session.update(account=h.session['account'], place=h.session['place'], release=source_release)
    receipt = legacy_fixture.plain(old.heist() if kind == 'heist' else old.recall())
    tag = f'{len(h.session["account"])}:{h.session["account"]}{len(h.session["place"])}:{h.session["place"]}'
    owner_key = 'idle-mafia-ember:release-owner:v1:' + tag
    cp_key = 'idle-mafia-ember:checkpoint:v1:' + tag + '40:' + source_release
    receipt_key = cp_key.replace(':checkpoint:', ':heist-sequences:' if kind == 'heist' else ':territory-recall:')
    values = {
        owner_key: {'version': 1, 'account': h.session['account'], 'place': h.session['place'], 'release': source_release},
        cp_key: {'version': 1, 'records': [], 'requestHighwater': 19,
                 **({'favorUsage': fixture.carry_favor_usage} if hasattr(fixture,'carry_favor_usage') else {})},
        receipt_key: receipt,
    }
    slots = {key: {'generation': 1, 'payload': json.dumps(value, sort_keys=True), 'value': value}
             for key, value in values.items()}
    h.lua.globals().carryAppSlots = lua_table(h.lua, slots)
    h.lua.globals().carryAppDecode = lambda value: lua_table(h.lua, json.loads(value))
    h.lua.globals().carryAppHash = lambda value: hashlib.sha256(value.encode()).hexdigest()
    store = h.lua.execute('''return {strictRecovery=true,
        Current=function(_,key)return carryAppSlots[key]end,
        Read=function(_,key)return carryAppSlots[key] and carryAppSlots[key].value end,
        ListKeys=function()local keys={}for key in pairs(carryAppSlots)do keys[#keys+1]=key end;return keys end}''')
    modules.LegacyCompletionReceipts = h.load('src/storage/LegacyCompletionReceipts.luau')
    modules.FavorHelpEvidence = h.load('src/features/FavorHelpEvidence.luau')
    engine, why = h.load('src/storage/StorageUsageCarry.luau').new(lua_table(h.lua, {
        'sourceStore': store, 'sourceDirectory': 'ImmutableLegacy/checkpoints', 'sourceRelease': source_release,
        'identity': h.session, 'modules': modules,
        'codec': h.lua.eval('{Decode=function(_,v)return carryAppDecode(v)end}'),
        'sha256': h.lua.eval('function(v)return carryAppHash(v)end')}))
    fixture.assertIsNotNone(engine, why)
    review, sources = engine.Preview(engine, target)
    fixture.assertIsNotNone(review, sources)
    guard, why = engine.Adopt(engine, review, sources)
    fixture.assertIsNotNone(guard, why)
    fixture.assertTrue(guard.BindNativeSources(guard, lua_table(h.lua, {kind: lease} if bind else {}))[0])
    fixture.carry = guard
    fixture.carry_engine = engine
    fixture.carry_review = legacy_fixture.plain(review)
    fixture.carry_archives = legacy_fixture.plain(sources)
    return guard


class StorageCarryNativeAppTests(unittest.TestCase):
    def heist(self, bind=True, counter=7, favor_floor=False):
        f = heist_fixture.HeistProtocolAppTests()
        def factory(current, lease):
            current.port.counter = counter
            if favor_floor:current.carry_favor_usage={'day':23,'attempts':1}
            return make_carry(current, lease, 'heist', bind)
        f.usage_carry_factory = factory
        f.setUp(); self.addCleanup(f.tearDown)
        return f

    def recall(self, bind=True):
        f = recall_fixture.RecallRuntimeAppTests()
        # The fixture closes its initial runtime before composing the new owner.
        # Capture the authoritative empty CP passed to the original constructor.
        original_start = f.start
        def start(*args, **kwargs):
            cp = f.modules.Checkpoint.new(f.storage, f.modules.FamilyContributionUsage,
                f.modules.ResourceReservations, f.modules.PendingAction, f.modules.EventShopUsage,
                f.modules.MarketRentUsage, f.modules.CrewHireUsage, f.modules.PlayerFightUsage,
                f.modules.Chests, f.modules.ShopBuy)
            cp.Load(cp, f.h.session['account'], f.h.session['place'], f.h.session['release'])
            f.initial_checkpoint = cp
            return original_start(*args, **kwargs)
        f.start = start
        f.usage_carry_factory = lambda current, lease: make_carry(current, lease, 'recall', bind)
        f.setUp(); self.addCleanup(f.tearDown)
        return f

    def test_heist_archived_sequence_allows_one_owned_send_and_durable_new_id(self):
        f = self.heist()
        f.start()
        self.assertEqual(len(f.executor.queued), 1, dict(f.runtime.Status(f.runtime).reasons.items()))
        self.assertEqual(f.port.counter, 8)
        f.executor.Drain(f.executor)
        self.assertEqual(len(f.executor.calls), 1)
        self.assertEqual((f.executor.calls[1].args[1], f.executor.calls[1].args[3]), ('start', 8))
        records = f.runtime.checkpoint.Records(f.runtime.checkpoint)
        self.assertEqual(records[1].requestId, 20)
        self.assertEqual(legacy_fixture.plain(f.carry.Summary(f.carry)), f.carry_review)
        f.later(46, False); f.app.Step(f.app, f.raw)
        self.assertEqual(len(f.executor.calls), 1)
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 1)

    def test_heist_queued_native_counter_replacement_never_invokes_or_relabels_history(self):
        f = self.heist(); f.start()
        f.port.counter = 9
        f.executor.Drain(f.executor)
        self.assertEqual(len(f.executor.calls), 0)
        self.assertEqual(legacy_fixture.plain(f.carry.Summary(f.carry)), f.carry_review)

    def test_fresh_zero_native_epoch_can_send_sequence_one_without_retagging_legacy_receipt(self):
        f=self.heist(counter=0)
        self.assertEqual(f.port.counter,0)
        archived=copy.deepcopy(f.carry_archives);review=copy.deepcopy(f.carry_review)
        f.start('favors')
        self.assertEqual(len(f.executor.queued),1,dict(f.runtime.Status(f.runtime).reasons.items()))
        self.assertEqual(f.port.counter,1)
        f.executor.Drain(f.executor)
        self.assertEqual(len(f.executor.calls),1)
        self.assertEqual((f.executor.calls[1].args[1],f.executor.calls[1].args[3]),('help',1))
        record=f.runtime.checkpoint.Records(f.runtime.checkpoint)[1]
        self.assertEqual(record.requestId,20)
        self.assertEqual(record.resources.energy,2)
        self.assertEqual(legacy_fixture.plain(f.carry.Summary(f.carry)),review)
        self.assertEqual(f.carry_archives,archived)
        f.later(46,False);f.app.Step(f.app,f.raw)
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)),1)
        self.assertEqual(len(f.executor.calls),1)

    def test_fresh_epoch_sequence_does_not_reset_imported_favor_attempt_floor(self):
        f=self.heist(counter=0,favor_floor=True)
        self.assertTrue(f.app.Set(f.app,'favors.custom.maxDailyAttempts',1)[0])
        f.start('favors')
        self.assertEqual(len(f.executor.queued),0)
        self.assertEqual(f.port.counter,0)
        self.assertTrue(f.app.Set(f.app,'favors.custom.maxDailyAttempts',2)[0])
        f.app.Step(f.app,f.raw)
        self.assertEqual(len(f.executor.queued),1,dict(f.runtime.Status(f.runtime).reasons.items()))
        self.assertEqual(f.port.counter,1)
        self.assertEqual(f.runtime.checkpoint.FavorUsage(f.runtime.checkpoint,23,0).attempts,1)
        self.assertEqual(f.carry.Summary(f.carry).floors.favorUsage.attempts,1)
        f.app.Set(f.app,'favors.enabled',False);f.executor.Drain(f.executor)
        self.assertEqual(len(f.executor.calls),0)
        self.assertEqual(f.port.counter,1,'Known-unsent cleanup must never refund native sequence')
        self.assertEqual(f.runtime.checkpoint.FavorUsage(f.runtime.checkpoint,23,0).attempts,1,
            'Existing conservative attempted quota remains charged even when native invocation is refused')
        self.assertEqual(f.carry.Summary(f.carry).floors.favorUsage.attempts,1)

    def test_new_controller_epoch_and_guard_do_not_erase_local_plus_imported_daily_usage(self):
        f=self.heist(counter=0,favor_floor=True)
        f.app.Set(f.app,'favors.custom.maxDailyAttempts',2)
        f.executor.reply=lua_table(f.h.lua,{'ok':False,'code':'not_available'})
        f.start('favors');f.executor.Drain(f.executor)
        self.assertEqual(len(f.executor.calls),1)
        f.later(1,False);f.app.Step(f.app,f.raw)
        self.assertEqual(f.runtime.Status(f.runtime).outcomes.favors,'rejected')
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)),0)
        self.assertEqual(f.runtime.checkpoint.FavorUsage(f.runtime.checkpoint,23,1).attempts,1)
        guard,why=f.carry_engine.Adopt(f.carry_engine,lua_table(f.h.lua,f.carry_review),
            lua_table(f.h.lua,f.carry_archives),f.runtime.checkpoint)
        self.assertIsNotNone(guard,why)
        self.assertTrue(guard.BindCheckpoint(guard,f.runtime.checkpoint)[0])
        port=f.h.lua.execute("""return {counter=0,running=false,writes=0,Current=function()return true end,
            Read=function(s)return {counter=s.counter,pending=s.pending,running=s.running}end,
            Write=function(s,k,v)s.writes=s.writes+1;s[k]=v end}""")
        lease,why=f.h.load('src/tabs/heists/NativeHeistLease.luau').new(port,f.h.clock,
            lua_table(f.h.lua,{'account':f.h.session['account'],'place':f.h.session['place'],'jobId':'new-job','sourceKey':'a'*64}),
            lua_table(f.h.lua,{'id':'new-epoch','counterSeen':0}))
        self.assertIsNotNone(lease,why)
        self.assertTrue(guard.BindNativeSources(guard,lua_table(f.h.lua,{'heist':lease}))[0])
        p=f.h.proposal('favors','new-epoch:favor',2)
        p.intent=lua_table(f.h.lua,{'kind':'favorHelp','sequence':1,'nativeJob':'new-job','nativeEpoch':'new-epoch',
            'nativeSourceKey':'a'*64,'serverDay':23,'usageAttemptsBefore':1,'maxDailyAttempts':2})
        self.assertFalse(guard.Check(guard,p,f.raw)[0])
        p.intent.maxDailyAttempts=3
        self.assertTrue(guard.Check(guard,p,f.raw)[0])
        self.assertEqual(port.writes,0);self.assertEqual(port.counter,0)
        self.assertEqual(legacy_fixture.plain(guard.Summary(guard)),f.carry_review)

    def test_fresh_epoch_queued_counter_drift_stays_unsent_with_archive_intact(self):
        f=self.heist(counter=0);f.start('favors')
        self.assertEqual(len(f.executor.queued),1,dict(f.runtime.Status(f.runtime).reasons.items()))
        f.port.counter=2
        f.executor.Drain(f.executor)
        self.assertEqual(len(f.executor.calls),0)
        self.assertEqual(f.port.counter,2)
        self.assertEqual(legacy_fixture.plain(f.carry.Summary(f.carry)),f.carry_review)

    def test_recall_original_floor_allows_new_owned_exact_target_then_confirms(self):
        f = self.recall()
        f.executor.reply = f.settled()
        f.begin(); f.send()
        self.assertGreater(f.executor.calls[1].id, 100001)
        self.assertEqual(f.runtime.checkpoint.Records(f.runtime.checkpoint)[1].requestId, 20)
        f.h.at(.25); f.step(f.raw(2, True, .25))
        self.assertEqual(f.runtime.Status(f.runtime).outcomes.station, 'confirmed')
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 0)
        self.assertEqual(f.recall.owner.Usage(f.recall.owner).attempted, 1)
        self.assertEqual(f.native.calls, 0)
        self.assertEqual(legacy_fixture.plain(f.carry.Summary(f.carry)), f.carry_review)

    def test_recall_queued_disable_records_unsent_without_native_invocation(self):
        f = self.recall(); f.begin()
        f.app.Set(f.app, 'station.enabled', False)
        f.executor.queued[1]()
        self.assertEqual(len(f.executor.calls), 0)
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 0)
        self.assertEqual(f.recall.owner.Usage(f.recall.owner).attempted, 0)
        self.assertEqual(f.native.calls, 0)

    def test_absent_native_sources_refuse_only_the_affected_routes(self):
        for kind in ('heist', 'recall'):
            with self.subTest(kind=kind):
                f = self.heist(False) if kind == 'heist' else self.recall(False)
                if kind == 'heist': f.start()
                else:
                    f.app.Set(f.app, 'station.enabled', True); f.app.Resume(f.app); f.step()
                self.assertEqual(len(f.executor.queued), 0)
                self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 0)
                p = f.h.proposal('jobs', 'unrelated:carry')
                self.assertTrue(f.carry.Check(f.carry, p, f.h.snapshot(native={'fullSync': True}))[0])


if __name__ == '__main__':
    unittest.main()
