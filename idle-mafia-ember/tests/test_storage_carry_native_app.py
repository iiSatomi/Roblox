"""Historical receipts gate actual App/native owners without changing their scope."""
import hashlib
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
        cp_key: {'version': 1, 'records': [], 'requestHighwater': 19},
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
    fixture.carry_review = legacy_fixture.plain(review)
    fixture.carry_archives = legacy_fixture.plain(sources)
    return guard


class StorageCarryNativeAppTests(unittest.TestCase):
    def heist(self, bind=True):
        f = heist_fixture.HeistProtocolAppTests()
        def factory(current, lease):
            current.port.counter = 7
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
