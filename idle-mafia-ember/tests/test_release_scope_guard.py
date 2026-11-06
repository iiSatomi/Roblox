"""Durable account/place ownership refuses silent cross-release allowance resets."""
import unittest
import json
import test_redundant_store as fixture
import test_crew_replacement as crew_fixture
from engine_harness import lua_table

class ReleaseScopeGuardTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.RedundantStoreTests();self.f.setUp();self.h=self.f.h
        self.f.store.files.EnsureDirectory=self.h.lua.eval("function() return true end")
        self.identity={"account":"user-a","place":"place-a","release":"release-a"}
        self.h.lua.globals().guardList=lambda directory:lua_table(self.h.lua,sorted(p for p in self.f.disk if p.startswith(directory+"/")))
        self.f.store.files.ListFiles=self.h.lua.eval("function(self,directory) return guardList(directory) end")
    def start(self,identity=None):
        return self.h.load("src/storage/StorageAssembly.luau").new(lua_table(self.h.lua,{
            "RedundantStore":self.h.load("src/storage/RedundantStore.luau"),
            "FamilyContributionUsage":self.h.load("src/tabs/family/FamilyContributionUsage.luau"),
            "files":self.f.store.files,"codec":self.f.store.codec,"sha256":self.f.store.hash,
            "directory":"IdleMafiaEmber/state","activateStorage":True,
            "identity":self.identity if identity is None else identity}))
    def approve_review(self, legacy=None, checkpoints=None):
        self.f.disk['IdleMafiaEmber/state/migration-review.json']=json.dumps(dict(
            version=1,**self.identity,preserveLegacyHistory=True,
            legacy=legacy or {},checkpoints=checkpoints or {}))
    def test_exact_reviewed_legacy_bytes_allow_first_adoption_without_deleting_history(self):
        path='IdleMafiaFluent/place-a/user-a/settings.json';self.f.disk[path]='{"version":17}'
        self.approve_review({path:self.f.store.hash(self.f.disk[path])})
        stores,why=self.start();self.assertIsNotNone(stores,why)
        self.assertEqual(self.f.disk[path],'{"version":17}')
        self.f.disk[path]='{"version":17,"changed":true}'
        before=dict(self.f.disk);self.assertIsNone(self.start()[0]);self.assertEqual(self.f.disk,before)
    def test_reviewed_empty_old_checkpoint_can_be_retained_without_resetting_a_ledger(self):
        key='idle-mafia-ember:checkpoint:v1:6:user-a7:place-a9:release-b'
        store=self.seed(key,{'version':1,'records':[],'familyClaimUsage':{'weeks':[]}})
        encoded=store.Current(store,key)[0].payload
        self.approve_review(checkpoints={key:self.f.store.hash(encoded)})
        stores,why=self.start();self.assertIsNotNone(stores,why)
        self.assertIsNotNone(stores.storage.Read(stores.storage,key))
        self.seed(key,{'version':1,'records':[],'stationAttempts':7})
        self.assertIsNone(self.start()[0])
    def test_review_cannot_adopt_nonempty_usage_even_with_an_exact_digest(self):
        key='idle-mafia-ember:checkpoint:v1:6:user-a7:place-a9:release-b'
        store=self.seed(key,{'version':1,'records':[],'stationAttempts':7})
        encoded=store.Current(store,key)[0].payload
        self.approve_review(checkpoints={key:self.f.store.hash(encoded)})
        before=dict(self.f.disk);self.assertIsNone(self.start()[0]);self.assertEqual(self.f.disk,before)
    def test_review_scope_mismatch_and_new_legacy_file_remain_blocked(self):
        self.approve_review()
        value=json.loads(self.f.disk['IdleMafiaEmber/state/migration-review.json']);value['release']='another-release'
        self.f.disk['IdleMafiaEmber/state/migration-review.json']=json.dumps(value)
        before=dict(self.f.disk);self.assertIsNone(self.start()[0]);self.assertEqual(self.f.disk,before)
        self.approve_review();self.f.disk['IdleMafiaFluent/place-a/user-a/configs.json']='{}'
        before=dict(self.f.disk);self.assertIsNone(self.start()[0]);self.assertEqual(self.f.disk,before)
    def test_exact_review_digest_cannot_adopt_a_pending_action(self):
        key='idle-mafia-ember:checkpoint:v1:6:user-a7:place-a9:release-b'
        store=self.seed(key,{'version':1,'records':[{'feature':'jobs'}]})
        encoded=store.Current(store,key)[0].payload
        self.approve_review(checkpoints={key:self.f.store.hash(encoded)})
        before=dict(self.f.disk);self.assertIsNone(self.start()[0]);self.assertEqual(self.f.disk,before)
    def test_changed_reviewed_legacy_source_during_check_does_not_write_owner(self):
        path='IdleMafiaFluent/place-a/user-a/settings.json';self.f.disk[path]='{}'
        self.approve_review({path:self.f.store.hash('{}')})
        count=0
        original=self.h.lua.globals().py_read
        def read(owner,name):
            nonlocal count
            if name==path:
                count+=1
                if count==2:return '{"changed":true}'
            return original(owner,name)
        self.h.lua.globals().py_read=read
        before=dict(self.f.disk);self.assertIsNone(self.start()[0]);self.assertEqual(self.f.disk,before)
    def test_reviewed_release_upgrade_preserves_request_highwater_and_sources(self):
        first,_=self.start()
        old='idle-mafia-ember:checkpoint:v1:6:user-a7:place-a9:release-a'
        self.assertTrue(first.storage.Write(first.storage,old,lua_table(self.h.lua,{'version':1,'records':[],'requestHighwater':12})))
        owner=first.storage.Current(first.storage,self.key())[0]
        source=first.storage.Current(first.storage,old)[0]
        review=dict(version=1,**dict(self.identity,release='release-b'),preserveLegacyHistory=True,
            fromRelease='release-a',previousOwnerHash=self.f.store.hash(owner.payload),legacy={},checkpoints={old:self.f.store.hash(source.payload)})
        self.f.disk['IdleMafiaEmber/state/migration-review.json']=json.dumps(review)
        stores,why=self.start(dict(self.identity,release='release-b'));self.assertIsNotNone(stores,why)
        new='idle-mafia-ember:checkpoint:v1:6:user-a7:place-a9:release-b'
        self.assertEqual(stores.storage.Read(stores.storage,new).requestHighwater,12)
        self.assertEqual(stores.storage.Read(stores.storage,old).requestHighwater,12)
        self.assertEqual(stores.storage.Read(stores.storage,self.key()).release,'release-b')
        self.assertIsNotNone(self.start(dict(self.identity,release='release-b'))[0])
    def test_reviewed_upgrade_without_old_counter_source_cannot_change_owner(self):
        first,_=self.start();owner=first.storage.Current(first.storage,self.key())[0]
        self.f.disk['IdleMafiaEmber/state/migration-review.json']=json.dumps(dict(version=1,**dict(self.identity,release='release-b'),preserveLegacyHistory=True,fromRelease='release-a',previousOwnerHash=self.f.store.hash(owner.payload),legacy={},checkpoints={}))
        before=dict(self.f.disk);self.assertIsNone(self.start(dict(self.identity,release='release-b'))[0]);self.assertEqual(self.f.disk,before)
    def test_review_preserves_exact_zero_resource_ledgers_and_highwater(self):
        old='idle-mafia-ember:checkpoint:v1:6:user-a7:place-a9:release-b'
        usage={'version':1,'lanes':{f:{'attempted':0,'spent':0} for f in ('familyCash','familyGold','familyStamina')}}
        store=self.seed(old,{'version':1,'records':[],'requestHighwater':1,'stationAttempts':0,'prestigeAttempts':0,'residencyAttempts':0,'familyContributionUsage':usage})
        self.approve_review(checkpoints={old:self.f.store.hash(store.Current(store,old)[0].payload)})
        stores,why=self.start();self.assertIsNotNone(stores,why)
        key='idle-mafia-ember:checkpoint:v1:6:user-a7:place-a9:release-a'
        saved=stores.storage.Read(stores.storage,key)
        self.assertEqual(saved.requestHighwater,1);self.assertEqual(saved.stationAttempts,0)
        self.assertEqual(saved.familyContributionUsage.lanes.familyCash.spent,0)
    def test_review_cannot_reset_positive_family_exposure(self):
        old='idle-mafia-ember:checkpoint:v1:6:user-a7:place-a9:release-b'
        usage={'version':1,'lanes':{f:{'attempted':0,'spent':0} for f in ('familyCash','familyGold','familyStamina')}}
        usage['lanes']['familyCash']={'attempted':1,'spent':100}
        store=self.seed(old,{'version':1,'records':[],'familyContributionUsage':usage})
        self.approve_review(checkpoints={old:self.f.store.hash(store.Current(store,old)[0].payload)})
        before=dict(self.f.disk);self.assertIsNone(self.start()[0]);self.assertEqual(self.f.disk,before)
    def key(self):return "idle-mafia-ember:release-owner:v1:6:user-a7:place-a"
    def test_fresh_chunk_same_release_keeps_existing_checkpoint_and_does_not_rewrite_guard(self):
        first,reason=self.start();self.assertIsNone(reason)
        self.assertTrue(first.storage.Write(first.storage,"pending",lua_table(self.h.lua,{"held":7})))
        before=dict(self.f.disk);second,reason=self.start();self.assertIsNone(reason)
        self.assertEqual(second.storage.Read(second.storage,"pending").held,7)
        self.assertEqual(self.f.disk,before)
    def test_fresh_chunk_new_release_refuses_without_any_disk_change(self):
        self.start();before=dict(self.f.disk)
        second,reason=self.start(dict(self.identity,release="release-b"))
        self.assertIsNone(second);self.assertIn("migration",reason);self.assertEqual(self.f.disk,before)
    def test_account_and_place_have_independent_release_guards(self):
        self.start()
        self.assertIsNotNone(self.start(dict(self.identity,account="user-b",release="release-b"))[0])
        self.assertIsNotNone(self.start(dict(self.identity,place="place-b",release="release-b"))[0])
    def test_damaged_guard_cannot_be_treated_as_first_use(self):
        stores,_=self.start();a,b=stores.storage.Paths(stores.storage,self.key())
        self.f.disk[b]="partial"
        self.assertIsNone(self.start()[0])
    def test_well_formed_wrong_scope_guard_is_refused(self):
        stores,_=self.start()
        self.assertTrue(stores.storage.Write(stores.storage,self.key(),lua_table(self.h.lua,{
            "version":1,"account":"user-b","place":"place-a","release":"release-a"})))
        self.assertIsNone(self.start()[0])
    def test_unreadable_or_unconfirmed_guard_cannot_start_storage(self):
        self.f.short_write=True
        self.assertIsNone(self.start()[0])
    def test_activated_storage_requires_complete_identity(self):
        for field in ("account","place","release"):
            identity=dict(self.identity);identity[field]=""
            self.assertIsNone(self.start(identity)[0])
    def seed(self,key,value):
        store=self.h.load("src/storage/RedundantStore.luau").new(self.f.store.files,self.f.store.codec,self.f.store.hash,"IdleMafiaEmber/state/checkpoints",lua_table(self.h.lua,{"strictRecovery":True}))
        self.assertTrue(store.Write(store,key,lua_table(self.h.lua,value)))
        return store
    def test_first_adoption_detects_unindexed_other_release_without_writing_owner(self):
        for prefix in ("checkpoint","market-rent","payouts"):
            self.f.disk.clear();self.seed("idle-mafia-ember:"+prefix+":v1:6:user-a7:place-a9:release-b",{"version":1,"records":[],"stationAttempts":7})
            before=dict(self.f.disk);stores,reason=self.start()
            self.assertIsNone(stores);self.assertIn("migration",reason);self.assertEqual(self.f.disk,before)
    def test_missing_discovery_cannot_mean_no_older_checkpoint_exists(self):
        self.f.store.files.ListFiles=None
        stores,reason=self.start();self.assertIsNone(stores);self.assertIn("discovery",reason.lower())
        self.assertEqual(self.f.disk,{})
    def test_same_release_unindexed_checkpoint_is_preserved_on_adoption(self):
        key="idle-mafia-ember:checkpoint:v1:6:user-a7:place-a9:release-a"
        self.seed(key,{"version":1,"records":[],"stationAttempts":7})
        stores,reason=self.start();self.assertIsNone(reason)
        self.assertEqual(stores.storage.Read(stores.storage,key).stationAttempts,7)
    def test_known_legacy_records_hold_startup_even_after_release_adoption(self):
        self.start()
        for name in ("action-journal","market-flip","market-sell","market-memory","property-review","gear-plan"):
            path="IdleMafiaFluent/place-a/user-a/"+name+".json";self.f.disk[path]='{}'
            before=dict(self.f.disk);stores,reason=self.start()
            self.assertIsNone(stores);self.assertIn("legacy",reason.lower());self.assertEqual(self.f.disk,before)
            del self.f.disk[path]
    def test_standalone_high_value_evidence_and_config_backup_hold_without_writes(self):
        self.start()
        for name in ('high-value-targets.json','combat-evidence.json','configs.json.bak'):
            path='IdleMafiaFluent/place-a/user-a/'+name;self.f.disk[path]='{}';before=dict(self.f.disk)
            stores,why=self.start();self.assertIsNone(stores,name);self.assertIn('migration',why.lower());self.assertEqual(self.f.disk,before)
            del self.f.disk[path]
    def test_standalone_owned_mug_history_is_not_known_empty_after_release_adoption(self):
        self.start();path='IdleMafiaMugTracker/user-a/mugs.json';self.f.disk[path]='{}';before=dict(self.f.disk)
        stores,why=self.start();self.assertIsNone(stores);self.assertIn('mug',why.lower());self.assertEqual(self.f.disk,before)
    def test_other_account_legacy_memory_does_not_hold_this_account(self):
        self.start()
        self.f.disk['IdleMafiaMugTracker/user-b/mugs.json']='{}'
        self.f.disk['IdleMafiaFluent/place-a/user-b/high-value-targets.json']='{}'
        before=dict(self.f.disk);stores,why=self.start();self.assertIsNotNone(stores,why);self.assertEqual(self.f.disk,before)
    def test_actual_app_holds_standalone_legacy_mugs_before_ui_or_account_write(self):
        self.f.disk['IdleMafiaMugTracker/user-a/mugs.json']='{}';before=dict(self.f.disk)
        ember=self.h.load('tests/ember_double.lua')()
        deps=lua_table(self.h.lua,{'Ember':ember,'Catalog':self.h.load('src/ui/Catalog.luau'),'Settings':self.h.load('src/storage/Settings.luau'),
            'EmberAdapter':self.h.load('src/ui/EmberAdapter.luau'),'StorageAssembly':self.h.load('src/storage/StorageAssembly.luau'),
            'ProfileStore':self.h.load('src/storage/ProfileStore.luau'),'RedundantStore':self.h.load('src/storage/RedundantStore.luau'),
            'activateStorage':True,'identity':self.identity,'directory':'IdleMafiaEmber/state','files':self.f.store.files,'codec':self.f.store.codec,'sha256':self.f.store.hash})
        with self.assertRaisesRegex(Exception,'migration'):self.h.load('src/App.luau').start(deps)
        self.assertEqual(self.f.disk,before);self.assertEqual(len(ember.windows),0)
    def test_unscoped_adapter_receipt_from_other_release_is_also_held(self):
        self.seed("idle-mafia-ember:adapter-unsent:v1:opaque:1",dict(self.identity,release="release-b",version=1))
        self.assertIsNone(self.start()[0])
    def test_actual_app_blocks_before_ui_or_runtime_when_unindexed_state_needs_migration(self):
        self.seed("idle-mafia-ember:checkpoint:v1:6:user-a7:place-a9:release-b",{"version":1,"records":[],"stationAttempts":7})
        ember=self.h.load("tests/ember_double.lua")()
        deps=lua_table(self.h.lua,{"Ember":ember,"Catalog":self.h.load("src/ui/Catalog.luau"),"Settings":self.h.load("src/storage/Settings.luau"),
            "EmberAdapter":self.h.load("src/ui/EmberAdapter.luau"),"StorageAssembly":self.h.load("src/storage/StorageAssembly.luau"),
            "ProfileStore":self.h.load("src/storage/ProfileStore.luau"),"RedundantStore":self.h.load("src/storage/RedundantStore.luau"),
            "activateStorage":True,"identity":self.identity,"directory":"IdleMafiaEmber/state","files":self.f.store.files,"codec":self.f.store.codec,"sha256":self.f.store.hash})
        before=dict(self.f.disk)
        with self.assertRaisesRegex(Exception,"migration"):self.h.load("src/App.luau").start(deps)
        self.assertEqual(self.f.disk,before);self.assertEqual(len(ember.windows),0)
    def test_existing_owner_cannot_hide_later_other_release_checkpoint(self):
        self.start()
        self.seed("idle-mafia-ember:checkpoint:v1:6:user-a7:place-a9:release-b",
                  {"version": 1, "records": [], "stationAttempts": 7})
        before = dict(self.f.disk)
        stores, reason = self.start()
        self.assertIsNone(stores)
        self.assertIn("migration", reason)
        self.assertEqual(self.f.disk, before)

    def test_existing_owner_cannot_hide_later_unscoped_other_release_receipt(self):
        self.start()
        self.seed("idle-mafia-ember:adapter-unsent:v1:opaque:2",
                  dict(self.identity, release="release-b", version=1))
        before = dict(self.f.disk)
        stores, reason = self.start()
        self.assertIsNone(stores)
        self.assertIn("migration", reason)
        self.assertEqual(self.f.disk, before)

    def test_existing_owner_does_not_bypass_failed_or_damaged_discovery(self):
        self.start()
        self.f.store.files.ListFiles = None
        before = dict(self.f.disk)
        stores, reason = self.start()
        self.assertIsNone(stores)
        self.assertIn("discovery", reason.lower())
        self.assertEqual(self.f.disk, before)

    def test_later_same_release_and_other_account_state_remain_usable(self):
        self.start()
        self.seed("idle-mafia-ember:checkpoint:v1:6:user-a7:place-a9:release-a",
                  {"version": 1, "records": [], "stationAttempts": 7})
        self.seed("idle-mafia-ember:checkpoint:v1:6:user-b7:place-a9:release-b",
                  {"version": 1, "records": [], "stationAttempts": 8})
        before = dict(self.f.disk)
        stores, reason = self.start()
        self.assertIsNotNone(stores, reason)
        self.assertEqual(self.f.disk, before)

    def test_actual_app_holds_later_foreign_release_before_ui_or_account_write(self):
        self.start()
        self.seed("idle-mafia-ember:checkpoint:v1:6:user-a7:place-a9:release-b",
                  {"version": 1, "records": [], "stationAttempts": 7})
        before = dict(self.f.disk)
        ember = self.h.load("tests/ember_double.lua")()
        deps = lua_table(self.h.lua, {
            "Ember": ember, "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "StorageAssembly": self.h.load("src/storage/StorageAssembly.luau"),
            "ProfileStore": self.h.load("src/storage/ProfileStore.luau"),
            "RedundantStore": self.h.load("src/storage/RedundantStore.luau"),
            "activateStorage": True, "identity": self.identity,
            "directory": "IdleMafiaEmber/state", "files": self.f.store.files,
            "codec": self.f.store.codec, "sha256": self.f.store.hash})
        with self.assertRaisesRegex(Exception, "migration"):
            self.h.load("src/App.luau").start(deps)
        self.assertEqual(self.f.disk, before)
        self.assertEqual(len(ember.windows), 0)

    def seed_crew(self, identity=None, side_fact=False):
        identity = self.identity if identity is None else identity
        crew = crew_fixture.CrewReplacementTests()
        crew.h = self.h
        crew.load_components()
        previous = dict(self.h.session)
        self.h.session.update(identity)
        try:
            crew.source, reason = crew.module.new(crew.config, "a" * 64, identity["release"])
            self.assertIsNone(reason)
            crew.scope = lua_table(self.h.lua, {**identity, "ownerId": "replacement-a"})
            crew.storage = self.h.load("src/storage/RedundantStore.luau").new(
                self.f.store.files, self.f.store.codec, self.f.store.hash,
                "IdleMafiaEmber/state/checkpoints", lua_table(self.h.lua, {"strictRecovery": True}))
            crew.tx = crew.restart()
            proposal, before = crew.prepare()
            if side_fact:
                self.assertTrue(crew.tx.MarkSending(crew.tx, before, 1)[0])
                self.assertTrue(crew.tx.RecordAbandonedUnsent(crew.tx, proposal.actionKey))
                keys, reason = crew.storage.ListKeys(crew.storage)
                self.assertIsNone(reason)
                key = next(key for key in keys.values() if key.startswith(crew.tx.key + ":adapter-unsent:"))
            else:
                key = crew.tx.key
            return crew, key
        finally:
            self.h.session.clear()
            self.h.session.update(previous)

    def assert_crew_refused_without_write(self):
        before = dict(self.f.disk)
        stores, reason = self.start()
        self.assertIsNone(stores)
        self.assertIn("migration", reason.lower())
        self.assertEqual(self.f.disk, before)

    def test_actual_crew_old_release_before_first_adoption_is_held(self):
        self.seed_crew(dict(self.identity, release="release-b"))
        self.assert_crew_refused_without_write()

    def test_actual_crew_old_release_added_after_adoption_is_held(self):
        self.start()
        self.seed_crew(dict(self.identity, release="release-b"))
        self.assert_crew_refused_without_write()

    def test_actual_crew_same_release_custody_and_usage_are_preserved(self):
        self.start()
        crew, key = self.seed_crew()
        before = dict(self.f.disk)
        stores, reason = self.start()
        self.assertIsNotNone(stores, reason)
        self.assertEqual(self.f.disk, before)
        saved = stores.storage.Read(stores.storage, key)
        self.assertEqual(saved.usage.attempted, 1)
        self.assertEqual(saved.active.stage, "preparedDismiss")

    def test_actual_crew_other_account_and_place_do_not_hold_this_scope(self):
        self.start()
        for identity in (dict(self.identity, account="user-b", release="release-b"),
                         dict(self.identity, place="place-b", release="release-b")):
            self.seed_crew(identity)
        before = dict(self.f.disk)
        stores, reason = self.start()
        self.assertIsNotNone(stores, reason)
        self.assertEqual(self.f.disk, before)

    def test_actual_crew_malformed_nested_scope_and_unknown_schema_are_held(self):
        for field, value in (("scope", None), ("scope", "invalid"), ("schema", 2)):
            with self.subTest(field=field, value=value):
                self.f.disk.clear()
                crew, key = self.seed_crew()
                saved = crew.storage.Read(crew.storage, key)
                saved[field] = value
                self.assertTrue(crew.storage.Write(crew.storage, key, saved))
                self.assert_crew_refused_without_write()

    def test_actual_crew_malformed_envelope_and_unknown_scope_fields_are_held(self):
        for field, value in (("generation", 0), ("generation", 1.5), ("usage", None),
                             ("active", "invalid"), ("resolution", False), ("unknown", True)):
            with self.subTest(field=field):
                self.f.disk.clear()
                crew, key = self.seed_crew()
                saved = crew.storage.Read(crew.storage, key)
                saved[field] = value
                self.assertTrue(crew.storage.Write(crew.storage, key, saved))
                self.assert_crew_refused_without_write()
        self.f.disk.clear()
        crew, key = self.seed_crew()
        saved = crew.storage.Read(crew.storage, key)
        saved.scope.unknown = True
        self.assertTrue(crew.storage.Write(crew.storage, key, saved))
        self.assert_crew_refused_without_write()

    def test_actual_crew_unsent_fact_generation_and_shape_are_validated(self):
        for field, value in (("generation", 99), ("baseline", None), ("proposal", False)):
            with self.subTest(field=field):
                self.f.disk.clear()
                crew, key = self.seed_crew(side_fact=True)
                saved = crew.storage.Read(crew.storage, key)
                saved[field] = value
                self.assertTrue(crew.storage.Write(crew.storage, key, saved))
                self.assert_crew_refused_without_write()

    def test_actual_crew_key_and_nested_scope_mismatch_is_held(self):
        for field in ("account", "place", "release", "ownerId"):
            with self.subTest(field=field):
                self.f.disk.clear()
                crew, key = self.seed_crew()
                saved = crew.storage.Read(crew.storage, key)
                saved.scope[field] = "" if field == "ownerId" else "different"
                self.assertTrue(crew.storage.Write(crew.storage, key, saved))
                self.assert_crew_refused_without_write()

    def test_actual_crew_colon_scopes_are_matched_by_nested_identity(self):
        self.identity = dict(self.identity, account="user:a", place="place:a", release="release:a")
        self.start()
        self.seed_crew()
        before = dict(self.f.disk)
        stores, reason = self.start()
        self.assertIsNotNone(stores, reason)
        self.assertEqual(self.f.disk, before)
        self.seed_crew(dict(self.identity, release="release:b"))
        self.assert_crew_refused_without_write()

    def test_actual_crew_ambiguous_colon_scope_cannot_hide_current_account_custody(self):
        self.identity = dict(self.identity, account="user", place="a:place")
        self.start()
        self.seed_crew(dict(self.identity, account="user:a", place="place", release="release-b"))
        self.assert_crew_refused_without_write()

    def test_actual_crew_old_release_standalone_unsent_fact_is_held(self):
        crew, key = self.seed_crew(dict(self.identity, release="release-b"), side_fact=True)
        # Reproduce a surviving side fact without its original main envelope.
        for path in crew.storage.Paths(crew.storage, crew.tx.key):
            self.f.disk.pop(path, None)
        self.assertIn(":adapter-unsent:", key)
        self.assert_crew_refused_without_write()

    def test_actual_crew_same_release_unsent_fact_is_preserved(self):
        self.start()
        self.seed_crew(side_fact=True)
        before = dict(self.f.disk)
        stores, reason = self.start()
        self.assertIsNotNone(stores, reason)
        self.assertEqual(self.f.disk, before)

if __name__=="__main__":unittest.main()
