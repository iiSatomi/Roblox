"""Reviewed code upgrades preserve the original data lineage and unknown outcomes."""
import json
import unittest

from engine_harness import ROOT, lua_table
import test_redundant_store as disk_fixture


class StorageUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.f = disk_fixture.RedundantStoreTests(methodName='runTest'); self.f.setUp()
        self.h = self.f.h
        self.data_release, self.code_release = 'a' * 40, 'b' * 40
        self.identity = dict(self.h.session, release=self.code_release)
        self.directory = 'IdleMafiaEmber/state'
        self.files, self.codec, self.hash = self.f.store.files, self.f.store.codec, self.f.store.hash
        self.files.EnsureDirectory = self.h.lua.eval('function() return true end')
        self.h.lua.globals().upgradeList = lambda directory: lua_table(self.h.lua, sorted(
            p for p in self.f.disk if p.startswith(directory + '/')))
        self.files.ListFiles = self.h.lua.eval('function(self,directory) return upgradeList(directory) end')
        self.h.lua.globals().upgradeIsDirectory = lambda directory: any(p.startswith(directory + '/') for p in self.f.disk)
        self.files.IsDirectory = self.h.lua.eval('function(self,directory) return upgradeIsDirectory(directory) end')
        self.store = self.h.load('src/storage/RedundantStore.luau').new(self.files, self.codec,
            self.hash, self.directory + '/checkpoints', lua_table(self.h.lua, {'strictRecovery': True}))
        self.modules = {}
        for name, folder in [('Checkpoint', 'storage'), ('PendingAction', 'storage'),
            ('ResourceReservations', 'engine'), ('FamilyContributionUsage', 'tabs/family'),
            ('EventShopUsage', 'tabs/events'), ('MarketRentUsage', 'tabs/blackMarket'),
            ('CrewHireUsage', 'tabs/crew'), ('PlayerFightUsage', 'tabs/combat'),
            ('Chests', 'features'), ('ShopBuy', 'features')]:
            path = ROOT / 'src' / folder / (name + '.luau')
            if path.exists(): self.modules[name] = self.h.load(path.relative_to(ROOT).as_posix())
        tag = f'{len(self.identity["account"])}:{self.identity["account"]}{len(self.identity["place"])}:{self.identity["place"]}'
        self.owner_key = 'idle-mafia-ember:release-owner:v1:' + tag
        self.checkpoint_key = 'idle-mafia-ember:checkpoint:v1:' + tag + '40:' + self.data_release
        self.assertTrue(self.store.Write(self.store, self.owner_key, lua_table(self.h.lua, {
            'version': 1, 'account': self.identity['account'], 'place': self.identity['place'],
            'release': self.data_release})))
        m = self.modules
        self.cp = m['Checkpoint'].new(self.store, m['FamilyContributionUsage'], m['ResourceReservations'],
            m['PendingAction'], m['EventShopUsage'], m['MarketRentUsage'], m['CrewHireUsage'],
            m['PlayerFightUsage'], m.get('Chests'), m.get('ShopBuy'))
        self.assertIsNone(self.cp.Load(self.cp, self.identity['account'], self.identity['place'], self.data_release)[1])
        before = self.h.snapshot(native={'fullSync': True, 'serverNow': 1000, 'cash': 500,
            'operations': {'active': [{'slot': 1, 'opId': 'op_a', 'remaining': 20},
                                      {'slot': 2, 'opId': 'op_a', 'remaining': 30}]}},
            catalogKey='catalog-a', operationCatalog=[{'id': 'op_a', 'cost': 200}])
        before.release = self.data_release
        self.proposal = self.h.proposal('operations', 'operations:original')
        self.proposal.release, self.proposal.resources = self.data_release, lua_table(self.h.lua, {'cash': 200})
        self.proposal.intent = lua_table(self.h.lua, {'kind': 'operationStart', 'targetId': 'op_a',
            'expectedCost': 200, 'catalogKey': 'catalog-a'})
        self.evidence = self.h.load('src/features/OperationsEvidence.luau')
        baseline, reason = self.evidence.capture(self.proposal, before); self.assertIsNone(reason)
        self.assertTrue(self.cp.Save(self.cp, self.proposal, before, baseline)[0])
        self.assertTrue(self.cp.RecordReply(self.cp, self.proposal.actionKey, lua_table(self.h.lua, {'ok': True}))[0])
        self.before, self.baseline = before, baseline
        self.original = dict(self.f.disk)

    def engine(self, identity=None):
        path = ROOT / 'src/storage/StorageUpgrade.luau'
        self.assertTrue(path.is_file(), 'A reviewed nonempty storage upgrade owner is required')
        module = self.h.load('src/storage/StorageUpgrade.luau')
        owner, reason = module.new(lua_table(self.h.lua, {'store': self.store, 'files': self.files,
            'codec': self.codec, 'sha256': self.hash, 'directory': self.directory,
            'identity': identity or self.identity, 'modules': self.modules}))
        self.assertIsNotNone(owner, reason)
        return owner

    def preview(self):
        engine = self.engine()
        review, reason = engine.Preview(engine, self.data_release)
        self.assertIsNotNone(review, reason)
        return engine, review

    def test_preview_is_read_only_and_commit_preserves_v2_successful_reply_and_cash_custody(self):
        engine, review = self.preview()
        self.assertEqual(self.f.disk, self.original)
        result, reason = engine.Commit(engine, review); self.assertIsNotNone(result, reason)
        self.assertEqual((result.identity.release, result.sourceRelease), (self.data_release, self.code_release))
        self.assertIsNone(result.requestHighwaterFloor)
        self.assertIsNone(result.usageCarryGuard)
        self.assertEqual(result.identity.session, self.identity['session'])
        owner = self.store.Read(self.store, self.owner_key)
        self.assertEqual((owner.version, owner.release, owner.storageRelease), (2, self.code_release, self.data_release))
        recovered = self.cp.Recovery(self.cp, self.proposal.actionKey)[0]
        self.assertTrue(recovered.reply.ok)
        self.assertEqual(recovered.proposal.release, self.data_release)
        self.assertEqual(recovered.proposal.resources.cash, 200)
        self.assertIsNone(self.evidence.recoverSaved(recovered, self.before))
        self.assertEqual(self.store.Read(self.store, self.checkpoint_key).requestHighwater, 1)
        for path, content in self.original.items():
            if path not in self.store.Paths(self.store, self.owner_key): self.assertEqual(self.f.disk[path], content)
        self.assertIsNone(self.store.Read(self.store, self.checkpoint_key.replace(self.data_release, self.code_release)))

    def test_persistent_restart_uses_certificate_after_legitimate_current_checkpoint_writes(self):
        engine, review = self.preview(); self.assertIsNotNone(engine.Commit(engine, review)[0])
        p = self.h.proposal('jobs', 'jobs:next'); p.release = self.data_release
        self.assertTrue(self.cp.Save(self.cp, p, self.before, lua_table(self.h.lua, {'retained': True}))[0])
        before = dict(self.f.disk)
        opened, reason = self.engine().Open(self.engine())
        self.assertIsNotNone(opened, reason); self.assertEqual(self.f.disk, before)
        self.assertEqual(self.store.Read(self.store, self.checkpoint_key).requestHighwater, 2)
        self.assertIsNone(self.engine(dict(self.identity, release='c' * 40)).Open(
            self.engine(dict(self.identity, release='c' * 40)))[0])

    def test_second_code_upgrade_preserves_original_release_and_authenticates_prior_certificate_chain(self):
        engine, review = self.preview(); self.assertIsNotNone(engine.Commit(engine, review)[0])
        previous_certificate = self.store.Read(self.store, self.owner_key).receiptKey
        next_engine = self.engine(dict(self.identity, release='c' * 40))
        next_review, reason = next_engine.Preview(next_engine, self.data_release)
        self.assertIsNotNone(next_review, reason)
        result, reason = next_engine.Commit(next_engine, next_review); self.assertIsNotNone(result, reason)
        reopened, reason = next_engine.Open(next_engine); self.assertIsNotNone(reopened, reason)
        self.assertEqual(reopened.identity.release, self.data_release)
        self.assertEqual(reopened.sourceRelease, 'c' * 40)
        value = self.store.Read(self.store, previous_certificate); value.sources[1].payload = '{}'
        self.store.Write(self.store, previous_certificate, value)
        self.assertIsNone(next_engine.Open(next_engine)[0])

    def test_current_lineage_numbered_unsent_receipt_survives_restart_without_becoming_a_foreign_bypass(self):
        engine, review = self.preview(); self.assertIsNotNone(engine.Commit(engine, review)[0])
        p = self.h.proposal('jobs', 'jobs:unsent'); p.release = self.data_release
        baseline = lua_table(self.h.lua, {'retained': True})
        result = self.cp.Save(self.cp, p, self.before, baseline)
        self.assertTrue(result[0]); p.checkpointRequestId = self.cp.requestHighwater
        self.assertTrue(self.cp.RecordUnsent(self.cp, p, self.before, baseline)[0])
        opened, reason = self.engine().Open(self.engine()); self.assertIsNotNone(opened, reason)
        key = self.cp.UnsentKey(self.cp, p.checkpointRequestId)
        forged = self.store.Read(self.store, key); forged.release = 'c' * 40
        self.store.Write(self.store, key, forged)
        self.assertIsNone(self.engine().Open(self.engine())[0])

    def current_unsent(self):
        p = self.h.proposal('jobs', 'jobs:unsent'); p.release = self.data_release
        baseline = lua_table(self.h.lua, {'retained': True})
        self.assertTrue(self.cp.Save(self.cp, p, self.before, baseline)[0])
        p.checkpointRequestId = self.cp.requestHighwater
        self.assertTrue(self.cp.RecordUnsent(self.cp, p, self.before, baseline)[0])
        return self.cp.UnsentKey(self.cp, p.checkpointRequestId)

    def current_recall(self):
        import test_territory_recall as recall_fixture
        helper = recall_fixture.TerritoryRecallTests(methodName='runTest')
        helper.h = self.h
        self.h.session['release'] = self.data_release
        helper.scope = lua_table(self.h.lua, {**self.h.session, 'userId': 101})
        helper.terms = lua_table(self.h.lua, {'release': self.data_release, 'recallCooldownSeconds': 600})
        self.h.lua.globals().upgradeRecallIdentity = lua_table(self.h.lua, {
            'account': self.identity['account'], 'place': self.identity['place'], 'userId': 101,
            'nativeJob': 'recall-job', 'nativeEpoch': 'recall-epoch', 'nativeSourceKey': 'a' * 64})
        helper.identitySource = self.h.lua.execute("""local fence={owners={},writing={}};return {
            DurableFence=function()return fence end,Identity=function()return upgradeRecallIdentity end}""")
        helper.module = self.h.load('src/tabs/territory/RecallTransactions.luau')
        helper.storage = self.store
        helper.tx = helper.restart()
        helper.settle()
        self.assertEqual(helper.tx.Reconcile(helper.tx, helper.raw(5, 1700000005, home=True))[0], 'observed')
        return helper

    def next_upgrade(self):
        engine = self.engine(dict(self.identity, release='c' * 40))
        before = dict(self.f.disk)
        review, reason = engine.Preview(engine, self.data_release)
        self.assertIsNotNone(review, reason)
        self.assertEqual(self.f.disk, before, 'Preview must not write even with typed side ledgers')
        result, reason = engine.Commit(engine, review)
        self.assertIsNotNone(result, reason)
        self.assertIsNotNone(engine.Open(engine)[0])
        return engine

    def test_second_code_upgrade_archives_real_unsent_and_observed_recall_without_rewriting_originals(self):
        engine, review = self.preview(); self.assertIsNotNone(engine.Commit(engine, review)[0])
        unsent_key = self.current_unsent()
        helper = self.current_recall()
        originals = {key: self.store.Current(self.store, key)[0].payload
                     for key in (unsent_key, helper.tx.key, self.checkpoint_key)}
        next_engine = self.next_upgrade()
        for key, payload in originals.items():
            self.assertEqual(self.store.Current(self.store, key)[0].payload, payload)
        recovery = self.cp.Recovery(self.cp, self.proposal.actionKey)[0]
        self.assertTrue(recovery.reply.ok)
        self.assertEqual(recovery.proposal.resources.cash, 200)
        self.assertIsNone(self.evidence.recoverSaved(recovery, self.before))
        # The next authorized session must still be able to finish the same
        # producer's observed transaction instead of pinning it as foreign data.
        self.assertTrue(helper.tx.ClearObserved(helper.tx)[0])
        self.assertIsNotNone(next_engine.Open(next_engine)[0])

    def test_archived_mutable_ledger_requires_a_later_generation_for_changed_payload(self):
        for mutation in ('lower_generation', 'same_generation', 'missing'):
            with self.subTest(mutation=mutation):
                self.setUp(); engine, review = self.preview()
                self.assertIsNotNone(engine.Commit(engine, review)[0])
                helper = self.current_recall()
                archived_generation = self.store.Current(self.store, helper.tx.key)[0].generation
                next_engine = self.next_upgrade()
                self.assertTrue(helper.tx.ClearObserved(helper.tx)[0])
                self.assertIsNotNone(next_engine.Open(next_engine)[0])
                self.h.lua.globals().upgradeOriginalCurrent = self.store.Current
                self.h.lua.globals().upgradeMutableKey = helper.tx.key
                self.h.lua.globals().upgradeArchivedGeneration = archived_generation
                self.h.lua.globals().upgradeMutableMutation = mutation
                self.store.Current = self.h.lua.eval("""function(self,key)
                    local slot,reason=upgradeOriginalCurrent(self,key)
                    if key==upgradeMutableKey then
                        if upgradeMutableMutation=='missing' then return nil end
                        slot.generation=upgradeArchivedGeneration-(upgradeMutableMutation=='lower_generation' and 1 or 0)
                    end
                    return slot,reason
                end""")
                before = dict(self.f.disk)
                self.assertIsNone(next_engine.Open(next_engine)[0])
                third = self.engine(dict(self.identity, release='d' * 40))
                self.assertIsNone(third.Preview(third, self.data_release)[0])
                self.assertEqual(self.f.disk, before)

    def test_numbered_unsent_archive_remains_immutable_on_restart_and_next_code_review(self):
        engine, review = self.preview(); self.assertIsNotNone(engine.Commit(engine, review)[0])
        key = self.current_unsent()
        next_engine = self.next_upgrade()
        # Rewriting even a valid identical receipt changes its immutable generation.
        self.assertTrue(self.store.Write(self.store, key, self.store.Read(self.store, key)))
        before = dict(self.f.disk)
        self.assertIsNone(next_engine.Open(next_engine)[0])
        third = self.engine(dict(self.identity, release='d' * 40))
        self.assertIsNone(third.Preview(third, self.data_release)[0])
        self.assertEqual(self.f.disk, before)

    def test_changed_typed_side_ledger_after_preview_refuses_owner_adoption(self):
        engine, review = self.preview(); self.assertIsNotNone(engine.Commit(engine, review)[0])
        helper = self.current_recall()
        next_engine = self.engine(dict(self.identity, release='c' * 40))
        review, reason = next_engine.Preview(next_engine, self.data_release)
        self.assertIsNotNone(review, reason)
        self.assertTrue(helper.tx.ClearObserved(helper.tx)[0])
        owner = self.store.Current(self.store, self.owner_key)[0].payload
        self.assertIsNone(next_engine.Commit(next_engine, review)[0])
        self.assertEqual(self.store.Current(self.store, self.owner_key)[0].payload, owner)

    def test_cross_code_snapshot_refuses_malformed_typed_current_keys_without_writes(self):
        for mutation in ('unsent_scope', 'unsent_version', 'unsent_suffix', 'recall_version'):
            with self.subTest(mutation=mutation):
                self.setUp(); engine, review = self.preview()
                self.assertIsNotNone(engine.Commit(engine, review)[0])
                key = self.current_unsent()
                if mutation == 'recall_version':
                    key = self.current_recall().tx.key
                value = self.store.Read(self.store, key)
                if mutation == 'unsent_scope': value.release = 'c' * 40
                elif mutation == 'unsent_version': value.version = 999
                elif mutation == 'unsent_suffix': key += ':unreviewed-owner'
                else: value.version = 999
                self.assertTrue(self.store.Write(self.store, key, value))
                before = dict(self.f.disk)
                next_engine = self.engine(dict(self.identity, release='c' * 40))
                self.assertIsNone(next_engine.Preview(next_engine, self.data_release)[0])
                self.assertEqual(self.f.disk, before)

    def test_current_owner_retirement_during_certificate_write_blocks_adoption(self):
        alive = {'value': True}
        self.h.lua.globals().upgradeAlive = lambda: alive['value']
        engine = self.engine(); engine.deps.current = self.h.lua.eval('function() return upgradeAlive() end')
        review = engine.Preview(engine, self.data_release)[0]
        self.h.lua.globals().upgradeOriginalWrite = self.store.Write
        self.h.lua.globals().retireUpgrade = lambda: alive.update(value=False)
        self.store.Write = self.h.lua.eval('''function(self,key,value)
            local result=upgradeOriginalWrite(self,key,value)
            if key:find(':storage-upgrade:',1,true) then retireUpgrade() end
            return result
        end''')
        self.assertIsNone(engine.Commit(engine, review)[0])
        self.assertEqual(self.store.Read(self.store, self.owner_key).version, 1)

    def test_restart_rechecks_owner_after_reading_current_checkpoint(self):
        engine, review = self.preview(); self.assertIsNotNone(engine.Commit(engine, review)[0])
        self.h.lua.globals().upgradeOriginalRead = self.store.Read
        self.h.lua.globals().upgradeCheckpointKey = self.checkpoint_key
        self.h.lua.globals().upgradeOwnerKey = self.owner_key
        self.store.Read = self.h.lua.eval('''function(self,key)
            local value=upgradeOriginalRead(self,key)
            if key==upgradeCheckpointKey and not self.interrupted then
                self.interrupted=true
                local owner=upgradeOriginalRead(self,upgradeOwnerKey)
                owner.release=string.rep('c',40)
                self:Write(upgradeOwnerKey,owner)
            end
            return value
        end''')
        self.assertIsNone(self.engine().Open(self.engine())[0])

    def test_stale_preview_new_key_or_changed_payload_never_adopts_owner(self):
        for mutation in ('payload', 'key', 'owner', 'review'):
            with self.subTest(mutation=mutation):
                self.setUp(); engine, review = self.preview()
                if mutation == 'payload':
                    value = self.store.Read(self.store, self.checkpoint_key); value.requestHighwater = 3
                    self.store.Write(self.store, self.checkpoint_key, value)
                elif mutation == 'key': self.store.Write(self.store, 'unreviewed', lua_table(self.h.lua, {'held': 1}))
                elif mutation == 'owner':
                    self.store.Write(self.store, self.owner_key, self.store.Read(self.store, self.owner_key))
                else: review.owner.sha256 = '0' * 64
                original_owner = self.store.Current(self.store, self.owner_key)[0].payload
                self.assertIsNone(engine.Commit(engine, review)[0])
                self.assertEqual(self.store.Current(self.store, self.owner_key)[0].payload, original_owner)

    def test_nonzero_foreign_scope_and_unknown_owner_are_blocked_not_ignored(self):
        for value in ({'version': 1, 'records': [], 'stationAttempts': 1}, {'version': 999}):
            with self.subTest(value=value):
                self.setUp()
                foreign = self.checkpoint_key.replace(self.data_release, 'c' * 40)
                self.store.Write(self.store, foreign, lua_table(self.h.lua, value))
                engine = self.engine(); before = dict(self.f.disk)
                self.assertIsNone(engine.Preview(engine, self.data_release)[0]); self.assertEqual(self.f.disk, before)

    def test_typed_zero_family_usage_in_an_older_empty_scope_is_archived_without_reset_or_summing(self):
        foreign = self.checkpoint_key.replace(self.data_release, 'c' * 40)
        self.store.Write(self.store, foreign, lua_table(self.h.lua, {'version': 1, 'records': [],
            'requestHighwater': 1, 'familyClaimUsage': {'weeks': []},
            'familyContributionUsage': {'version': 1, 'lanes': {
                feature: {'attempted': 0, 'spent': 0} for feature in ('familyCash','familyGold','familyStamina')}}}))
        engine, review = self.preview()
        self.assertIsNotNone(engine.Commit(engine, review)[0])
        self.assertIsNotNone(self.engine().Open(self.engine())[0])

    def test_owner_write_unconfirmed_never_returns_activation_and_restarts_conservatively(self):
        engine, review = self.preview()
        self.h.lua.globals().originalUpgradeWrite = self.store.Write
        self.h.lua.globals().upgradeOwnerKey = self.owner_key
        self.store.Write = self.h.lua.eval('''function(self,key,value)
            if key==upgradeOwnerKey then originalUpgradeWrite(self,key,value);return nil end
            return originalUpgradeWrite(self,key,value) end''')
        self.assertIsNone(engine.Commit(engine, review)[0])
        self.store.Write = self.h.lua.globals().originalUpgradeWrite
        restarted = self.engine(); self.assertIsNotNone(restarted.Open(restarted)[0])

    def test_restart_refuses_new_foreign_state_and_changed_certificate(self):
        for mutation in ('foreign', 'unknown', 'certificate'):
            with self.subTest(mutation=mutation):
                self.setUp(); engine, review = self.preview()
                self.assertIsNotNone(engine.Commit(engine, review)[0])
                if mutation == 'certificate':
                    key = self.store.Read(self.store, self.owner_key).receiptKey
                    value = self.store.Read(self.store, key); value.sources[1].payload = '{}'
                else:
                    key = self.checkpoint_key.replace(self.data_release, 'c' * 40) if mutation == 'foreign' else 'unknown-new-owner'
                    value = lua_table(self.h.lua, {'version': 1, 'records': [], 'stationAttempts': 3})
                self.assertTrue(self.store.Write(self.store, key, value))
                self.assertIsNone(self.engine().Open(self.engine())[0])

    def test_unknown_suffix_version_and_malformed_canonical_producer_cannot_bypass_restart_inventory(self):
        for family, suffix, version in (('checkpoint', ':unreviewed-owner', 1),
                ('checkpoint', '', 999), ('payouts', ':arbitrary', 1),
                ('payouts', '', 1), ('market-rent', ':unsent:1', 1)):
            with self.subTest(family=family, suffix=suffix, version=version):
                self.setUp(); engine, review = self.preview()
                self.assertIsNotNone(engine.Commit(engine, review)[0])
                key = self.checkpoint_key.replace(':checkpoint:v1:', f':{family}:v{version}:') + suffix
                self.store.Write(self.store, key, lua_table(self.h.lua, {}))
                self.assertIsNone(self.engine().Open(self.engine())[0])

    def test_real_current_market_producer_and_exact_numbered_unsent_receipt_survive_restart(self):
        import test_market_transaction_flows as flows
        engine, review = self.preview(); self.assertIsNotNone(engine.Commit(engine, review)[0])
        self.h.session['release'] = self.data_release
        helper = flows.MarketTransactionFlowTests(methodName='runTest'); helper.h = self.h
        deps = {path.stem: self.h.load(path.relative_to(ROOT).as_posix())
            for path in (ROOT / 'src/tabs/blackMarket').glob('*.luau') if path.name != 'Module.luau'}
        for name, folder in (('MarketEarningsState', 'game'), ('MarketEarnings', 'features'),
                ('MarketEarningsEvidence', 'features'), ('MarketBrowse', 'features'), ('MarketPrices', 'features'),
                ('MarketRap', 'features'), ('MarketReadRuntime', 'features')):
            deps[name] = self.h.load(f'src/{folder}/{name}.luau')
        helper.tab = self.h.load('src/tabs/blackMarket/Module.luau').new(lua_table(self.h.lua, deps))
        helper.scope, helper.storage = lua_table(self.h.lua, self.h.session), self.store
        helper.tx = helper.restart()
        proposal, before = helper.runtime_buy()
        self.assertTrue(helper.tx.PrepareRuntimeBuy(helper.tx, proposal, before)[0])
        self.assertTrue(helper.tx.AuthorizeRuntimeBuy(helper.tx, proposal)[0])
        self.assertTrue(helper.tx.RecordRuntimeUnsent(helper.tx, proposal.actionKey, proposal.intent.ownerGeneration)[0])
        reopened, reason = self.engine().Open(self.engine()); self.assertIsNotNone(reopened, reason)
        self.assertEqual(helper.restart().BuyUsage(helper.restart()).spent, 8)
        next_engine = self.next_upgrade()
        self.assertIsNotNone(next_engine.Open(next_engine)[0])
        # A genuine producer transition may refund its exact known-unsent buy
        # after upgrade; the archived initial state remains in the certificate.
        unsent_review = helper.tx.RuntimeUnsentReview(helper.tx)[0]
        self.assertTrue(helper.tx.ReleaseRuntimeUnsent(helper.tx, unsent_review)[0])
        self.assertEqual(helper.tx.BuyUsage(helper.tx).spent, 0)
        self.assertIsNotNone(next_engine.Open(next_engine)[0])

    def test_known_external_store_cannot_be_omitted_from_an_upgrade_or_appear_after_adoption(self):
        for when in ('preview', 'restart'):
            with self.subTest(when=when):
                self.setUp(); engine = self.engine()
                if when == 'restart':
                    review = engine.Preview(engine, self.data_release)[0]
                    self.assertIsNotNone(engine.Commit(engine, review)[0])
                self.f.disk['IdleMafiaEmberCompletion655/checkpoints/unreviewed.json'] = '{}'
                before = dict(self.f.disk)
                result = engine.Preview(engine, self.data_release) if when == 'preview' else engine.Open(engine)
                self.assertIsNone(result[0]); self.assertEqual(self.f.disk, before)

    def test_typed_carry_is_verified_before_owner_adoption_and_returned_for_runtime_binding(self):
        engine = self.engine()
        carry = self.h.lua.execute('''return {valid=true,verified=0,
            Preview=function(self,target)
                return {version=1,sourceDirectory='IdleMafiaEmberCompletion655/checkpoints',sourceRelease=string.rep('c',40),
                    requestHighwaterFloor=19,preserveOriginalEvidence=true},{}
            end,
            Verify=function(self,review,target) self.verified=self.verified+1;return self.valid end,
            Adopt=function(self,review,sources,target)
                if not self.valid then return nil,'Carry changed' end
                return {requestHighwaterFloor=19,Check=function() return true end,BindCheckpoint=function()return true end}
            end}''')
        engine.deps.usageCarry = carry
        review, reason = engine.Preview(engine, self.data_release); self.assertIsNotNone(review, reason)
        self.assertIsNotNone(review.carryReview)
        result, reason = engine.Commit(engine, review); self.assertIsNotNone(result, reason)
        self.assertEqual(result.requestHighwaterFloor, 19)
        self.assertIsNotNone(result.usageCarryGuard)
        self.assertGreaterEqual(carry.verified, 2)
        carry.valid = False
        self.assertIsNone(engine.Open(engine)[0])

    def test_large_combined_sources_use_bounded_immutable_archives_without_raising_store_limits(self):
        engine = self.engine()
        self.h.lua.globals().largeCarryPayload = json.dumps({'proof': '"' * 220000})
        carry = self.h.lua.execute('''return {
            Preview=function(self,target) return {version=1,requestHighwaterFloor=19,
                sourceDirectory='IdleMafiaEmberCompletion655/checkpoints',sourceRelease=string.rep('c',40)},
                {{key='source-one',generation=1,payload=largeCarryPayload},
                 {key='source-two',generation=2,payload=largeCarryPayload}} end,
            Verify=function()return true end,
            Adopt=function(self,review,sources)
                assert(#sources==2 and sources[1].payload==largeCarryPayload and sources[2].payload==largeCarryPayload)
                return {requestHighwaterFloor=19,Check=function()return true end,BindCheckpoint=function()return true end}
            end}''')
        engine.deps.usageCarry = carry
        review, reason = engine.Preview(engine, self.data_release); self.assertIsNotNone(review, reason)
        result, reason = engine.Commit(engine, review); self.assertIsNotNone(result, reason)
        self.assertIsNotNone(engine.Open(engine)[0])
        for content in self.f.disk.values():
            if content.startswith('{'):
                parsed = json.loads(content)
                if 'payload' in parsed: self.assertLessEqual(len(parsed['payload'].encode()), 1048576)

    def test_unconfirmed_certificate_write_never_changes_original_owner(self):
        for mode in ('nil', 'false', 'throw', 'write_nil'):
            with self.subTest(mode=mode):
                self.setUp(); engine, review = self.preview()
                self.h.lua.globals().upgradeOriginalWrite = self.store.Write
                self.h.lua.globals().upgradeFailureMode = mode
                self.store.Write = self.h.lua.eval('''function(self,key,value)
                    if key:find(':storage-upgrade:',1,true) then
                        if upgradeFailureMode=='write_nil' then upgradeOriginalWrite(self,key,value) end
                        if upgradeFailureMode=='throw' then error('disk unavailable') end
                        if upgradeFailureMode=='false' then return false end
                        return nil
                    end
                    return upgradeOriginalWrite(self,key,value)
                end''')
                self.assertIsNone(engine.Commit(engine, review)[0])
                self.assertEqual(self.store.Read(self.store, self.owner_key).version, 1)
                self.store.Write = self.h.lua.globals().upgradeOriginalWrite
                self.assertIsNotNone(self.engine().Commit(self.engine(), review)[0])

    def test_legacy_bytes_and_original_owner_change_during_certificate_write_refuse_adoption(self):
        path = f'IdleMafiaFluent/{self.identity["place"]}/{self.identity["account"]}/settings.json'
        for mutation in ('legacy', 'owner'):
            with self.subTest(mutation=mutation):
                self.setUp(); self.f.disk[path] = '{}'; engine, review = self.preview()
                self.h.lua.globals().upgradeOriginalWrite = self.store.Write
                self.h.lua.globals().upgradeOwnerKey = self.owner_key
                def interrupt():
                    if mutation == 'legacy': self.f.disk[path] = '{"changed":true}'
                    else:
                        owner = self.store.Read(self.store, self.owner_key)
                        self.h.lua.globals().upgradeOriginalWrite(self.store, self.owner_key, owner)
                self.h.lua.globals().interruptUpgrade = interrupt
                self.store.Write = self.h.lua.eval('''function(self,key,value)
                    local result=upgradeOriginalWrite(self,key,value)
                    if key:find(':storage-upgrade:',1,true) then interruptUpgrade() end
                    return result
                end''')
                self.assertIsNone(engine.Commit(engine, review)[0])
                self.assertEqual(self.store.Read(self.store, self.owner_key).version, 1)

    def test_storage_assembly_consumes_exact_review_then_reopens_same_lineage_without_reapproval(self):
        _, review = self.preview()
        self.f.disk[self.directory + '/storage-upgrade-review.json'] = json.dumps(disk_fixture.plain(review))
        deps = dict(self.modules, StorageUpgrade=self.h.load('src/storage/StorageUpgrade.luau'),
            RedundantStore=self.h.load('src/storage/RedundantStore.luau'), identity=self.identity,
            directory=self.directory, files=self.files, codec=self.codec, sha256=self.hash, activateStorage=True)
        assembly = self.h.load('src/storage/StorageAssembly.luau')
        stores, reason = assembly.new(lua_table(self.h.lua, deps))
        self.assertIsNotNone(stores, reason)
        self.assertEqual((stores.identity.release, stores.sourceRelease), (self.data_release, self.code_release))
        before = dict(self.f.disk)
        self.assertIsNotNone(assembly.new(lua_table(self.h.lua, deps))[0]); self.assertEqual(self.f.disk, before)

    def test_assembly_refuses_changed_review_bytes_before_owner_adoption(self):
        _, review = self.preview()
        path = self.directory + '/storage-upgrade-review.json'
        self.f.disk[path] = json.dumps(disk_fixture.plain(review))
        deps = dict(self.modules, StorageUpgrade=self.h.load('src/storage/StorageUpgrade.luau'),
            RedundantStore=self.h.load('src/storage/RedundantStore.luau'), identity=self.identity,
            directory=self.directory, files=self.files, codec=self.codec, sha256=self.hash, activateStorage=True)
        count = 0
        original = self.h.lua.globals().py_read
        def changed(owner, name):
            nonlocal count
            if name == path:
                count += 1
                if count > 1: return '{}'
            return original(owner, name)
        self.h.lua.globals().py_read = changed
        self.assertIsNone(self.h.load('src/storage/StorageAssembly.luau').new(lua_table(self.h.lua, deps))[0])
        self.assertEqual(self.store.Read(self.store, self.owner_key).version, 1)


if __name__ == '__main__': unittest.main()
