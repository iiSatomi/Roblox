"""Lossless compact recovery keeps ordinary composed snapshots within the same caps."""
import json
import unittest

import test_automation_runtime as runtime_fixture
import test_pending_action_recovery as recovery_fixture
from engine_harness import lua_table


class PendingActionCompactTests(unittest.TestCase):
    def setUp(self):
        self.f = recovery_fixture.PendingActionRecoveryTests()
        self.f.setUp()
        self.h, self.module = self.f.h, self.f.module

    def plain(self, value):
        return self.f.plain(value)

    def roundtrip(self, value):
        return lua_table(self.h.lua, json.loads(json.dumps(self.plain(value))))

    def capture(self, before=None, baseline=None):
        return self.module.Capture(self.h.proposal(), before or self.f.before(),
            baseline or self.f.baseline())

    def test_shared_tables_roundtrip_without_changing_original_baseline_or_key_types(self):
        before = self.f.before()
        before.data = before.native
        baseline = self.f.baseline()
        baseline.original = before.native.jobs
        saved, why = self.capture(before, baseline)
        self.assertIsNotNone(saved, why)
        self.assertEqual(saved.version, 2)
        decoded = self.module.Decode(self.roundtrip(saved))
        same = self.h.lua.eval("function(a,b) return rawequal(a,b) end")
        self.assertTrue(same(decoded.before.data, decoded.before.native))
        self.assertTrue(same(decoded.baseline.original, decoded.before.native.jobs))
        self.assertEqual(decoded.before.catalog[2].cost, 100)
        self.assertEqual(decoded.before.catalog['2'].cost, 999)
        before.native.jobs.j_a.completions = 999
        with_reply, why = self.module.WithReply(saved, None, lua_table(self.h.lua, {'ok': True}))
        self.assertIsNotNone(with_reply, why)
        restored = self.module.Decode(self.roundtrip(with_reply))
        self.assertEqual(restored.baseline.original.j_a.completions, 8)
        self.assertTrue(restored.reply.ok)
        self.assertIsNone(self.module.WithReply(with_reply, None,
            lua_table(self.h.lua, {'ok': False}))[0])
        self.assertTrue(self.module.Same(saved, self.module.Copy(saved)[0]))

    def test_version_one_json_records_remain_readable_and_copyable(self):
        def old(value):
            if isinstance(value, dict):
                return {'entries': {('n:' if isinstance(key, int) else 's:') + str(key): old(child)
                    for key, child in value.items()}}
            return value
        data = {'proposal': self.plain(self.h.proposal()), 'before': self.plain(self.f.before()),
            'baseline': self.plain(self.f.baseline()), 'reply': {'ok': False}}
        legacy = lua_table(self.h.lua, json.loads(json.dumps({'version': 1, 'payload': old(data)})))
        decoded = self.module.Decode(legacy)
        self.assertEqual(decoded.before.catalog[2].cost, 100)
        self.assertFalse(decoded.baseline.sparse[2])
        self.assertFalse(decoded.reply.ok)
        self.assertTrue(self.module.Same(legacy, self.module.Copy(legacy)[0]))
        legacy.payload.unexpected = True
        self.assertIsNone(self.module.Decode(legacy))

    def legacy_fractions(self, value=0.5):
        def old(item):
            if isinstance(item, list):
                item = {index: child for index, child in enumerate(item, 1)}
            if isinstance(item, dict):
                return {'entries': {('n:' if isinstance(key, int) else 's:') + str(key): old(child)
                    for key, child in item.items()}}
            return item
        data = {'proposal': self.plain(self.h.proposal()), 'before': self.plain(self.f.before()),
            'baseline': [value] * 8000}
        return {'version': 1, 'payload': old(data)}

    def test_fractional_heavy_version_one_copy_and_checkpoint_load_remain_supported(self):
        for value in (0.5, 0.1):
            with self.subTest(value=value):
                legacy = self.legacy_fractions(value)
                wire = lua_table(self.h.lua, legacy)
                self.assertIsNotNone(self.module.Decode(wire))
                copied, why = self.module.Copy(wire)
                self.assertIsNotNone(copied, why)
                record = {key: self.h.proposal()[key] for key in
                    ('account', 'place', 'release', 'feature', 'actionKey')}
                record.update(resources={'energy': 1}, recovery=legacy)
                scope = self.f.checkpoint.ScopeKey(self.f.checkpoint)
                self.f.storage.data[scope] = lua_table(self.h.lua,
                    json.loads(json.dumps({'version': 1, 'records': [record]})))
                restored = self.f.checkpoints.new(self.f.storage, None, None, self.module)
                self.assertIsNone(restored.Load(restored, 'user-a', self.h.session['place'], 'release-a')[1])
                recovered = restored.Recovery(restored, record['actionKey'])[0]
                self.assertEqual(recovered.baseline[8000], value)
                self.assertTrue(self.module.Same(wire, copied))
                returned, why = self.module.WithReply(wire, None, lua_table(self.h.lua, {'ok': False}))
                self.assertIsNotNone(returned, why)
                self.assertFalse(self.module.Decode(returned).reply.ok)
                if value == 0.1:
                    self.assertIsNone(self.module.WithReply(wire, None,
                        lua_table(self.h.lua, {'ok': True, 'padding': 'x' * 16000}))[0])
                    self.assertIsNone(self.module.Decode(wire).reply)

    def test_fresh_legacy_fallback_cannot_bypass_escaped_json_byte_limit(self):
        legacy = self.legacy_fractions()
        legacy['payload']['entries']['s:baseline'] = {'entries':
            {'s:field' + str(i): '\x01' * 8000 for i in range(6)}}
        wire = lua_table(self.h.lua, legacy)
        self.assertIsNotNone(self.module.Decode(wire))
        self.assertIsNone(self.module.Copy(wire)[0])

    def test_compact_wire_rejects_unknown_duplicate_unused_and_invalid_references(self):
        saved, _ = self.capture()
        self.assertEqual(saved.version, 2)
        original = self.plain(saved)
        before_key = str(original['payload']['keys'].index('s:before') + 1)
        cases = []
        def changed():
            return json.loads(json.dumps(original))
        value = changed(); value['payload']['unknown'] = True; cases.append(value)
        value = changed(); value['payload']['keys'].append(value['payload']['keys'][0]); cases.append(value)
        value = changed(); value['payload']['keys'].append('s:unused'); cases.append(value)
        value = changed(); value['payload']['tables'].append({}); cases.append(value)
        for reference in ([1], [0], [99999], [1.5], [True], [1, 2], {'ref': 1}):
            value = changed(); value['payload']['tables'][0][before_key] = reference; cases.append(value)
        value = changed(); value['payload']['tables'][0]['01'] = False; cases.append(value)
        value = changed(); value['payload']['keys'][0] = 'n:01'; cases.append(value)
        for value in cases:
            with self.subTest(value=value['payload'].get('unknown', 'malformed')):
                self.assertIsNone(self.module.Decode(lua_table(self.h.lua, value)))

    def test_equivalent_table_construction_and_copy_use_the_same_bounded_encoding(self):
        first, second = self.f.before(), self.f.before()
        first.details = self.h.lua.execute('local v={};for i=1,500 do v["field"..i]=i end;return v')
        second.details = self.h.lua.execute('local v={};for i=500,1,-1 do v["field"..i]=i end;return v')
        a, _ = self.capture(first)
        b, _ = self.capture(second)
        self.assertEqual(self.plain(a), self.plain(b))
        self.assertEqual(self.plain(a), self.plain(self.module.Copy(a)[0]))

    def test_version_tag_cannot_select_another_codec_after_decode_failure(self):
        saved, _ = self.capture()
        saved.version = 1
        self.assertIsNone(self.module.Decode(saved))

    def test_depth_limit_includes_primitive_leaves_after_cached_table_references(self):
        baseline = self.h.lua.execute('local v={leaf=false};for i=1,10 do v={next=v} end;return v')
        saved, why = self.capture(baseline=baseline)
        self.assertIsNotNone(saved, why)
        deeper = self.h.lua.execute('local v={leaf=false};for i=1,11 do v={next=v} end;return v')
        self.assertIsNone(self.capture(baseline=deeper)[0])
        wire = self.plain(saved)
        leaf_key = str(wire['payload']['keys'].index('s:leaf') + 1)
        tables = wire['payload']['tables']
        leaf = next(row for row in tables if leaf_key in row)
        tables.append({leaf_key: False})
        leaf[leaf_key] = [len(tables)]
        self.assertIsNone(self.module.Decode(lua_table(self.h.lua, wire)))

    def test_expanded_node_depth_and_unique_byte_caps_still_reject(self):
        for source in (
            "local v={leaf=false};for i=1,9 do v={a=v,b=v,c=v} end;return v",
            "local shared={tail={leaf=false}};local v=shared;for i=1,10 do v={next=v} end;return {shallow=shared,deep=v}",
            "local v={};v.self=v;return v",
            "return setmetatable({safe=true},{})",
            "return {capability=function() end}",
        ):
            with self.subTest(source=source):
                self.assertIsNone(self.capture(baseline=self.h.lua.execute(source))[0])
        unique = lua_table(self.h.lua, {str(i): str(i) + 'x' * 4090 for i in range(65)})
        self.assertIsNone(self.capture(baseline=unique)[0])

    def test_decoder_counts_expanded_alias_nodes_without_expanding_the_graph(self):
        baseline = self.h.lua.execute('local v={leaf=false};for i=1,9 do v={a=v,b=v} end;return v')
        saved, why = self.capture(baseline=baseline)
        self.assertIsNotNone(saved, why)
        wire = self.plain(saved)
        keys = wire['payload']['keys']
        a_key, b_key = str(keys.index('s:a') + 1), str(keys.index('s:b') + 1)
        keys.append('s:c'); c_key = str(len(keys))
        for row in wire['payload']['tables']:
            if a_key in row and b_key in row:
                row[c_key] = row[a_key]
        self.assertIsNone(self.module.Decode(lua_table(self.h.lua, wire)))

    def test_extreme_primitive_numbers_and_escaped_strings_keep_their_values(self):
        baseline = lua_table(self.h.lua, {9007199254740991: False, -3: 1e-300,
            '-3': 0.00000012345678901234567, 'text': '\\"/\n\u2603'})
        saved, why = self.capture(baseline=baseline)
        self.assertIsNotNone(saved, why)
        decoded = self.module.Decode(self.roundtrip(saved))
        self.assertFalse(decoded.baseline[9007199254740991])
        self.assertEqual(decoded.baseline[-3], 1e-300)
        self.assertEqual(decoded.baseline['-3'], baseline['-3'])
        self.assertEqual(decoded.baseline.text, baseline.text)
        self.assertLessEqual(len(json.dumps(self.plain(saved), ensure_ascii=True,
            separators=(',', ':')).encode()), 262144)

    def test_json_escaping_and_envelope_bytes_are_included_in_existing_budget(self):
        escaped = lua_table(self.h.lua, {str(i): '\x01' * 8000 for i in range(6)})
        self.assertIsNone(self.capture(baseline=escaped)[0])
        accepted, why = self.capture(baseline=lua_table(self.h.lua,
            {str(i): 'x' * 16384 for i in range(15)}))
        self.assertIsNotNone(accepted, why)
        self.assertLessEqual(len(json.dumps(self.plain(accepted), ensure_ascii=True,
            separators=(',', ':')).encode()), 262144)
        self.assertIsNone(self.capture(baseline=lua_table(self.h.lua,
            {str(i): 'x' * 16384 for i in range(16)}))[0])


class PendingActionComposedAppTests(unittest.TestCase):
    def test_native_reader_composed_job_snapshot_persists_before_one_send_and_recovers_exactly(self):
        self.composed_job_app()

    def test_large_mixed_job_snapshot_keeps_outcome_inputs_without_blocking_dispatch(self):
        self.composed_job_app(extra_history=True)

    def composed_job_app(self,extra_history=False):
        f = runtime_fixture.AutomationRuntimeTests(); f.setUp(); h = f.h
        f.runtime.Close(f.runtime)
        deps = f.runtime.modules
        for name, path in (('NativeJobCatalog', 'tabs/jobs/NativeJobCatalog'),
                ('JobsTab', 'tabs/jobs/Module'), ('JobsState', 'game/JobsState'),
                ('Jobs', 'features/Jobs'), ('JobsEvidence', 'features/JobsEvidence')):
            deps[name] = h.load('src/' + path + '.luau')
        deps.gameData = lua_table(h.lua, {'JOBS': [{'id': 'j_watch', 'level': 1,
            'energy': 1, 'cash': 60, 'xp': 2}]})
        deps.config = lua_table(h.lua, {'MASTERY': [{'completions': 25, 'energyDiscount': 0}]})
        deps.fingerprint, deps.release = 'a' * 64, 'release-a'
        tab = deps.JobsTab.new(deps)
        composed, why = h.load('src/tabs/TabComposition.luau').build(lua_table(h.lua, [tab]),
            h.load('src/ui/Catalog.luau'), h.load('src/engine/FeatureRegistry.luau'),
            h.load('src/tabs/TabSnapshotAssembler.luau'))
        self.assertIsNone(why)
        runtime = h.load('src/engine/AutomationRuntime.luau').new(lua_table(h.lua, {
            'clock': h.clock, 'transport': h.transport, 'storage': f.storage, 'identity': h.session,
            'modules': deps, 'features': composed.features, 'featurePages': composed.featurePages,
            'tabInstances': composed.tabs, 'snapshotAssembler': composed.snapshotAssembler}))
        app = h.load('src/App.luau').start(lua_table(h.lua, {'Ember': h.load('tests/ember_double.lua')(),
            'Catalog': h.load('src/ui/Catalog.luau'), 'Settings': h.load('src/storage/Settings.luau'),
            'EmberAdapter': h.load('src/ui/EmberAdapter.luau'), 'JobsTab': deps.JobsTab,
            'automationRuntimeInstance': runtime}))
        reader = h.load('src/transport/NativeSnapshotReader.luau').new(lua_table(h.lua, h.session), h.clock)
        native = f.raw().native
        native.heistLedger = lua_table(h.lua, [{'userId': i, 'name': 'Player ' + str(i),
            'lastAt': 1000, 'helped': i % 3, 'gotHelped': 0, 'helpedToday': 0,
            'lastHeistId': 'h_corner', 'friend': False} for i in range(1000)])
        if extra_history:
            native.heistResults=lua_table(h.lua,[{'id':'old-run-'+str(i),'heistId':'h_corner',
                'cash':35000,'xp':196,'collected':True,'completedAt':900} for i in range(1000)])
        try:
            self.assertTrue(reader.ObserveSync(reader, native))
            before = reader.Capture(reader)[0]
            if extra_history:
                before.territoryMap=lua_table(h.lua,{'header':{**h.session,'revision':before.revision,'capturedAt':before.capturedAt},
                    'cityId':'jade_harbor','districts':[{'id':'jade_harbor_'+str(i).zfill(3),'mine':True} for i in range(112)]})
            self.assertTrue(app.Set(app, 'jobs.enabled', True)[0]); app.Resume(app)
            app.Step(app, before)
            self.assertEqual(len(h.transport.sent), 1)
            records = runtime.checkpoint.Records(runtime.checkpoint, True)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[1].recovery.version, 2)
            saved = json.loads(json.dumps(recovery_fixture.PendingActionRecoveryTests().plain(
                records[1].recovery)))
            self.assertLessEqual(len(json.dumps(saved, separators=(',', ':')).encode()), 262144)
            scope = runtime.checkpoint.ScopeKey(runtime.checkpoint)
            f.storage.data[scope] = lua_table(h.lua, json.loads(json.dumps(
                recovery_fixture.PendingActionRecoveryTests().plain(f.storage.data[scope]))))
            restored = deps.Checkpoint.new(f.storage, deps.FamilyContributionUsage,
                deps.ResourceReservations, deps.PendingAction, deps.EventShopUsage,
                deps.MarketRentUsage, deps.CrewHireUsage, deps.PlayerFightUsage, deps.Chests)
            self.assertIsNone(restored.Load(restored, 'user-a', h.session['place'], 'release-a')[1])
            original = restored.Recovery(restored, records[1].actionKey)[0]
            self.assertEqual(before.native.heistLedger[1000].name, 'Player 999')
            recaptured,why=deps.JobsEvidence.capture(original.proposal,original.before)
            self.assertIsNotNone(recaptured,why)
            self.assertEqual(recaptured.completions,original.baseline.completions)
            self.assertEqual(recaptured.jobId,original.baseline.jobId)
            self.assertEqual(original.baseline.completions, 0)
            h.transport.callbacks[1](lua_table(h.lua, {'ok': True}))
            app.Set(app, 'jobs.enabled', False)
            h.at(1); native.jobs.j_watch.completions = 1
            self.assertTrue(reader.ObserveSync(reader, native)); app.Step(app, reader.Capture(reader)[0])
            self.assertEqual(runtime.Status(runtime).outcomes.jobs, 'confirmed')
            self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)), 0)
            self.assertEqual(len(h.transport.sent), 1)
        finally:
            app.Destroy(app); reader.Close(reader)


if __name__ == '__main__':
    unittest.main()
