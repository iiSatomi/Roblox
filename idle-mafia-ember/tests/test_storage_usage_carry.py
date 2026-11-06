"""Typed cross-directory allowances add a floor without rewriting old evidence."""
import unittest
import test_storage_upgrade as upgrade_fixture
from engine_harness import ROOT, lua_table


class StorageUsageCarryTests(unittest.TestCase):
    def setUp(self):
        self.f = upgrade_fixture.StorageUpgradeTests()
        self.f.setUp()
        self.h = self.f.h
        self.modules = self.f.modules
        self.source_release = "c" * 40
        self.identity = dict(self.h.session, release=self.f.data_release)
        self.source = self.h.load("src/storage/RedundantStore.luau").new(
            self.f.files, self.f.codec, self.f.hash, "PrivateReviewed/checkpoints",
            lua_table(self.h.lua, {"strictRecovery": True}))
        tag = f'{len(self.identity["account"])}:{self.identity["account"]}{len(self.identity["place"])}:{self.identity["place"]}'
        self.owner_key = 'idle-mafia-ember:release-owner:v1:' + tag
        self.cp_key = 'idle-mafia-ember:checkpoint:v1:' + tag + '40:' + self.source_release
        self.source.Write(self.source, self.owner_key, lua_table(self.h.lua, {
            'version': 1, 'account': self.identity['account'], 'place': self.identity['place'], 'release': self.source_release}))
        self.source_value = {'version': 1, 'records': [], 'requestHighwater': 19,
            'favorUsage': {'day': 20763, 'attempts': 1},
            'bossUsage': {'day': 2026310, 'hits': 1, 'stamina': 1, 'lastServerNow': 1793952348},
            'bossShopUsage': {'session': 'original-private-session', 'attempts': 1},
            'marketRentUsage': {'version': 1, 'attempted': 1, 'spent': 1},
            'stationAttempts': 1, 'prestigeAttempts': 0, 'residencyAttempts': 0,
            'familyContributionUsage': {'version': 1, 'lanes': {
                'familyCash': {'attempted': 1, 'spent': 100},
                'familyGold': {'attempted': 1, 'spent': 1},
                'familyStamina': {'attempted': 1, 'spent': 1}}}}
        self.source.Write(self.source, self.cp_key, lua_table(self.h.lua, self.source_value))
        self.before_disk = dict(self.f.f.disk)

    def engine(self):
        path = ROOT / 'src/storage/StorageUsageCarry.luau'
        self.assertTrue(path.exists(), 'Typed private allowance carry owner is missing')
        engine, reason = self.h.load(path.relative_to(ROOT).as_posix()).new(lua_table(self.h.lua, {
            'sourceStore': self.source, 'sourceDirectory': 'PrivateReviewed/checkpoints',
            'sourceRelease': self.source_release, 'identity': self.identity,
            'modules': self.modules, 'codec': self.f.codec, 'sha256': self.f.hash}))
        self.assertIsNotNone(engine, reason)
        return engine

    def review(self):
        engine = self.engine()
        review, sources = engine.Preview(engine, self.f.cp)
        self.assertIsNotNone(review, sources)
        return engine, review, sources

    def guard(self):
        engine, review, sources = self.review()
        guard, reason = engine.Adopt(engine, review, sources)
        self.assertIsNotNone(guard, reason)
        self.assertTrue(guard.BindCheckpoint(guard, self.f.cp)[0])
        return guard

    def proposal(self, feature='familyCash', amount=100, attempts=0, spent=0, cap=1, budget=100):
        p = self.h.proposal(feature, feature + ':carry')
        p.release = self.identity['release']
        resource = {'familyCash': 'cash', 'familyGold': 'gold_bar', 'familyStamina': 'stamina'}[feature]
        p.resources = lua_table(self.h.lua, {resource: amount})
        p.intent = lua_table(self.h.lua, {'kind': 'familyContribution', 'resource': resource,
            'amount': amount, 'attemptsBefore': attempts, 'spentBefore': spent,
            'actorId': 42, 'actorAccount': self.identity['account'], 'familyId': 7,
            'maxAttempts': cap, 'runBudget': budget})
        return p

    def raw(self):
        return self.h.snapshot(release=self.identity['release'], native={'fullSync': True, 'serverNow': 1793952354})

    def test_preview_and_adopt_are_read_only_and_detached(self):
        engine, review, sources = self.review()
        self.assertEqual(dict(self.f.f.disk), self.before_disk)
        self.assertEqual(review.requestHighwaterFloor, 19)
        self.assertEqual(review.floors.bossShopUsage.session, 'original-private-session')
        self.assertEqual(review.floors.familyContributionUsage.lanes.familyCash.spent, 100)
        self.assertEqual(len(sources), 2)
        self.assertTrue(engine.Verify(engine, review, self.f.cp)[0])
        guard, reason = engine.Adopt(engine, review, sources)
        self.assertIsNotNone(guard, reason)
        review.floors.familyContributionUsage.lanes.familyCash.attempted = 0
        self.assertTrue(guard.BindCheckpoint(guard, self.f.cp)[0])
        self.assertFalse(guard.Check(guard, self.proposal(), self.raw())[0])
        self.assertEqual(dict(self.f.f.disk), self.before_disk)

    def test_family_floor_enforces_attempt_and_spend_for_each_lane(self):
        guard = self.guard()
        for feature, amount in [('familyCash', 100), ('familyGold', 1), ('familyStamina', 1)]:
            with self.subTest(feature=feature):
                self.assertFalse(guard.Check(guard, self.proposal(feature, amount), self.raw())[0])
                self.assertTrue(guard.Check(guard, self.proposal(feature, amount, cap=2, budget=amount*2), self.raw())[0])
                self.assertFalse(guard.Check(guard, self.proposal(feature, amount, cap=2, budget=amount), self.raw())[0])

    def test_boss_shop_floor_survives_new_sessions(self):
        engine, review, sources = self.review()
        for session in ('new-a', 'new-b'):
            self.identity['session'] = session
            engine = self.engine()
            guard = engine.Adopt(engine, review, sources)[0]
            self.assertTrue(guard.BindCheckpoint(guard, self.f.cp)[0])
            raw = self.raw(); raw.session = session
            p = self.h.proposal('bossShop', 'boss-shop:carry')
            p.release, p.session = self.identity['release'], session
            p.intent = lua_table(self.h.lua, {'kind': 'bossShopBuy', 'attemptsBefore': 0, 'maxSends': 1})
            self.assertFalse(guard.Check(guard, p, raw)[0])
            p.intent.maxSends = 2
            self.assertTrue(guard.Check(guard, p, raw)[0])

    def test_initial_nonzero_target_is_blocked_instead_of_guessing_overlap(self):
        self.f.cp.familyContributionUsage.lanes.familyCash.attempted = 1
        self.f.cp.familyContributionUsage.lanes.familyCash.spent = 100
        engine, review, sources = self.review()
        self.assertIsNotNone(review.blockedFeatures.familyCash)
        guard = engine.Adopt(engine, review, sources)[0]
        guard.BindCheckpoint(guard, self.f.cp)
        self.assertFalse(guard.Check(guard, self.proposal(cap=20, budget=20000), self.raw())[0])
        self.assertTrue(guard.Check(guard, self.proposal('familyGold', 1, cap=2, budget=2), self.raw())[0])

    def test_prepared_own_charge_is_not_added_twice_and_replied_or_refunded_callback_is_refused(self):
        guard = self.guard()
        p = self.proposal(cap=2, budget=200)
        before = self.f.before
        before.native.family = lua_table(self.h.lua, {'id': 7})
        before.native.pools = lua_table(self.h.lua, {'stamina': 10})
        before.native.inventory = self.h.lua.table(); before.native.inventoryBound = self.h.lua.table()
        baseline = lua_table(self.h.lua, {'exact': True})
        self.assertTrue(guard.Check(guard, p, self.raw())[0])
        self.assertTrue(self.f.cp.Save(self.f.cp, p, before, baseline)[0])
        self.assertEqual(self.f.cp.familyContributionUsage.lanes.familyCash.attempted, 1)
        self.assertTrue(guard.Check(guard, p, self.raw())[0])
        self.assertTrue(self.f.cp.RecordUnsent(self.f.cp, p, before, baseline)[0])
        self.assertTrue(self.f.cp.Resolve(self.f.cp, p.actionKey, 'schedule_failed')[0])
        self.assertFalse(guard.Check(guard, p, self.raw())[0])
        p = self.proposal(cap=2, budget=200)
        self.assertTrue(self.f.cp.Save(self.f.cp, p, before, baseline)[0])
        self.assertTrue(self.f.cp.RecordReply(self.f.cp, p.actionKey, lua_table(self.h.lua, {'ok': True, 'pending': True}))[0])
        self.assertFalse(guard.Check(guard, p, self.raw())[0])

    def test_reviewed_zero_target_accepts_its_new_disjoint_usage_on_restart(self):
        engine, review, sources = self.review()
        guard = engine.Adopt(engine, review, sources)[0]
        guard.BindCheckpoint(guard, self.f.cp)
        p=self.proposal(cap=2,budget=200)
        before=self.f.before
        before.native.family=lua_table(self.h.lua,{'id':7})
        before.native.pools=lua_table(self.h.lua,{'stamina':10})
        before.native.inventory=self.h.lua.table();before.native.inventoryBound=self.h.lua.table()
        baseline=lua_table(self.h.lua,{'exact':True})
        self.assertTrue(self.f.cp.Save(self.f.cp,p,before,baseline)[0])
        self.assertTrue(self.f.cp.RecordReply(self.f.cp,p.actionKey,lua_table(self.h.lua,{'ok':True}))[0])
        self.assertTrue(self.f.cp.Resolve(self.f.cp,p.actionKey,'confirmed')[0])
        reopened,reason=self.engine().Adopt(self.engine(),review,sources,self.f.cp)
        self.assertIsNotNone(reopened,reason)
        self.assertTrue(reopened.BindCheckpoint(reopened,self.f.cp)[0])
        next_proposal=self.proposal(attempts=1,spent=100,cap=2,budget=200)
        self.assertFalse(reopened.Check(reopened,next_proposal,self.raw())[0])
        next_proposal.intent.maxAttempts=3;next_proposal.intent.runBudget=300
        self.assertTrue(reopened.Check(reopened,next_proposal,self.raw())[0])

    def test_bind_rejects_regressed_reviewed_canonical_usage(self):
        self.f.cp.familyContributionUsage.lanes.familyCash.attempted = 1
        self.f.cp.familyContributionUsage.lanes.familyCash.spent = 100
        engine, review, sources = self.review()
        guard = engine.Adopt(engine, review, sources)[0]
        self.f.cp.familyContributionUsage.lanes.familyCash.attempted = 0
        self.f.cp.familyContributionUsage.lanes.familyCash.spent = 0
        self.assertFalse(guard.BindCheckpoint(guard, self.f.cp)[0])

    def test_source_session_is_not_replaced_by_two_matching_forged_headers(self):
        guard = self.guard()
        p = self.proposal(cap=2, budget=200)
        raw = self.raw();p.session = raw.session = 'forged-new-session'
        self.assertFalse(guard.Check(guard, p, raw)[0])

    def test_current_recall_is_independent_of_station_deposit_floor(self):
        guard = self.guard()
        p = self.h.proposal('station', 'recall:own')
        p.release = self.identity['release']
        p.intent = lua_table(self.h.lua, {'kind': 'territoryRecall'})
        self.assertTrue(guard.Check(guard, p, self.raw())[0])

    def test_foreign_recall_blocks_only_its_intent_without_erasing_history(self):
        key = self.cp_key.replace(':checkpoint:', ':territory-recall:')
        value = lua_table(self.h.lua, {'version': 1, 'lastRequestId': 1,
                                     'receipt': {'outcome': 'confirmed', 'record': {'retained': True}}})
        self.source.Write(self.source, key, value)
        guard = self.guard()
        p = self.h.proposal('station', 'station:own');p.release = self.identity['release']
        p.intent = lua_table(self.h.lua, {'kind': 'territoryStation', 'attemptedBefore': 0, 'maxAttempts': 2})
        self.assertTrue(guard.Check(guard, p, self.raw())[0])
        p.intent.kind = 'territoryRecall'
        self.assertFalse(guard.Check(guard, p, self.raw())[0])
        self.assertEqual(self.source.Read(self.source, key).receipt.record.retained, True)

    def test_rent_station_favor_and_boss_caps_include_exact_imported_exposure(self):
        guard = self.guard();raw=self.raw()
        for feature, intent, capfield in (
            ('marketRent', {'kind':'marketRent','attemptedBefore':0,'spentBefore':0,'cost':1,'maxAttempts':1,'maxGoldSpend':2}, 'maxAttempts'),
            ('station', {'kind':'territoryStation','attemptedBefore':0,'maxAttempts':1}, 'maxAttempts'),
            ('favors', {'kind':'favorHelp','usageAttemptsBefore':0,'serverDay':20763,'maxDailyAttempts':1}, 'maxDailyAttempts')):
            with self.subTest(feature=feature):
                p=self.h.proposal(feature,feature+':cap');p.release=self.identity['release'];p.intent=lua_table(self.h.lua,intent)
                self.assertFalse(guard.Check(guard,p,raw)[0])
                p.intent[capfield]=2
                self.assertTrue(guard.Check(guard,p,raw)[0])
        p=self.h.proposal('bosses','boss:cap');p.release=self.identity['release']
        p.intent=lua_table(self.h.lua,{'kind':'bossStageAttack','dayStamp':2026310,'hitsBefore':0,'staminaBefore':0,
            'serverNow':1793952354,'expectedStaminaCost':1})
        self.assertTrue(guard.Check(guard,p,raw)[0])
        p.intent.serverNow=1793952352
        self.assertFalse(guard.Check(guard,p,raw)[0])
        p.intent.serverNow=1793952354
        self.f.cp.bossUsage=lua_table(self.h.lua,{'day':2026310,'hits':99,'stamina':99,'lastServerNow':1793952349})
        p.intent.hitsBefore=p.intent.staminaBefore=99
        self.assertFalse(guard.Check(guard,p,raw)[0])
        self.f.cp.bossUsage.hits=self.f.cp.bossUsage.stamina=98
        p.intent.hitsBefore=p.intent.staminaBefore=98
        self.assertTrue(guard.Check(guard,p,raw)[0])

    def test_periods_must_match_native_clock_and_cannot_launder_imported_limits(self):
        guard=self.guard();raw=self.raw()
        p=self.h.proposal('favors','favor:period');p.release=self.identity['release']
        p.intent=lua_table(self.h.lua,{'kind':'favorHelp','usageAttemptsBefore':0,'serverDay':20764,'maxDailyAttempts':1})
        self.assertFalse(guard.Check(guard,p,raw)[0])
        raw.native.serverNow=20764*86400+1
        self.assertTrue(guard.Check(guard,p,raw)[0])
        p.intent.serverDay=20762;raw.native.serverNow=20762*86400+1
        self.assertFalse(guard.Check(guard,p,raw)[0])

    def test_source_change_tampered_review_and_archived_payload_are_refused(self):
        engine, review, sources = self.review()
        sources[1].payload = '{}'
        self.assertIsNone(engine.Adopt(engine, review, sources)[0])
        engine, review, sources = self.review()
        review.floors.stationAttempts = 0
        self.assertIsNone(engine.Adopt(engine, review, sources)[0])
        engine, review, sources = self.review()
        self.source.Write(self.source, self.cp_key, lua_table(self.h.lua, self.source_value))
        self.assertFalse(engine.Verify(engine, review, self.f.cp)[0])

    def test_unbound_rebound_or_faulted_checkpoint_never_supplies_carry_permission(self):
        engine, review, sources = self.review()
        guard = engine.Adopt(engine, review, sources)[0]
        p = self.proposal(cap=2, budget=200)
        self.assertFalse(guard.Check(guard, p, self.raw())[0])
        self.assertTrue(guard.BindCheckpoint(guard, self.f.cp)[0])
        self.assertFalse(guard.BindCheckpoint(guard, self.h.lua.table())[0])
        self.f.cp.fault = 'unconfirmed storage'
        self.assertFalse(guard.Check(guard, p, self.raw())[0])

    def test_source_generation_change_during_capture_never_mixes_floors_and_archives(self):
        import copy
        changed=copy.deepcopy(self.source_value)
        changed['familyContributionUsage']['lanes']['familyCash']={'attempted':2,'spent':200}
        self.h.lua.globals().carryOriginalCurrent=self.source.Current
        self.h.lua.globals().carryOriginalWrite=self.source.Write
        self.h.lua.globals().carryRaceKey=self.cp_key
        self.h.lua.globals().carryRaceValue=lua_table(self.h.lua,changed)
        self.h.lua.globals().carryRaceDone=False
        self.h.lua.globals().carryRaceReads=0
        self.source.Current=self.h.lua.eval("""function(self,key)
            local current,path=carryOriginalCurrent(self,key)
            if key==carryRaceKey then
                carryRaceReads=carryRaceReads+1
                -- Discovery validates this key once; race its subsequent value capture.
                if carryRaceReads==2 and not carryRaceDone then
                    carryRaceDone=true;assert(carryOriginalWrite(self,key,carryRaceValue))
                end
            end
            return current,path
        end""")
        engine=self.engine()
        self.assertIsNone(engine.Preview(engine,self.f.cp)[0])

    def legacy_guard(self, kind):
        import test_legacy_completion_receipts as legacy_fixture
        f=legacy_fixture.LegacyCompletionReceiptTests();f.setUp()
        f.h.session.update(account=self.identity['account'],place=self.identity['place'],release=self.source_release)
        value=f.heist() if kind=='heist' else f.recall()
        family='heist-sequences' if kind=='heist' else 'territory-recall'
        key=self.cp_key.replace(':checkpoint:',':'+family+':')
        self.source.Write(self.source,key,lua_table(self.h.lua,legacy_fixture.plain(value)))
        self.modules['LegacyCompletionReceipts']=self.h.load('src/storage/LegacyCompletionReceipts.luau')
        self.modules['FavorHelpEvidence']=self.h.load('src/features/FavorHelpEvidence.luau')
        engine,review,sources=self.review()
        guard,why=engine.Adopt(engine,review,sources)
        self.assertIsNotNone(guard,why)
        self.assertTrue(guard.BindCheckpoint(guard,self.f.cp)[0])
        return guard,review,sources

    def native_source(self, kind):
        source=self.h.lua.execute("""return {valid=true,counter=7,
            account='user-a',place='73897506680154',userId=42,
            nativeJob='job-a',nativeEpoch='epoch-a',nativeSourceKey=string.rep('a',64),
            Inspect=function(s)
                if not s.valid then return nil end
                return {account=s.account,place=s.place,userId=s.userId,
                    controllerCounter=s.counter,counter=s.counter,nativeJob=s.nativeJob,
                    nativeEpoch=s.nativeEpoch,nativeSourceKey=s.nativeSourceKey}
            end,Owns=function(s,p)return s.owned==p end}""")
        if kind=='recall':source.counter=0
        return source

    def native_proposal(self,kind):
        p=self.h.proposal('heists' if kind=='heist' else 'station','native:carry')
        p.release=self.identity['release']
        p.intent=lua_table(self.h.lua,{'kind':'heistStart' if kind=='heist' else 'territoryRecall',
            'nativeJob':'job-a','nativeEpoch':'epoch-a','nativeSourceKey':'a'*64,
            'sequence':8,'nativeCounterBefore':0,'requestId':1000000,'userId':42})
        return p

    def test_typed_archives_require_bound_native_continuity_and_leave_review_unchanged(self):
        import test_legacy_completion_receipts as legacy_fixture
        for kind in ('heist','recall'):
            with self.subTest(kind=kind):
                self.setUp()
                guard,review,sources=self.legacy_guard(kind)
                original=legacy_fixture.plain(review)
                p=self.native_proposal(kind);raw=self.raw();native=self.native_source(kind)
                self.assertFalse(guard.Check(guard,p,raw)[0])
                self.assertIsNotNone(guard.BindNativeSources, 'Typed native continuity binding is missing')
                self.assertTrue(guard.BindNativeSources(guard,lua_table(self.h.lua,{kind:native}))[0])
                self.assertTrue(guard.Check(guard,p,raw)[0])
                self.assertFalse(guard.BindNativeSources(guard,lua_table(self.h.lua,{kind:self.native_source(kind)}))[0])
                native.owned=p;native.counter=8 if kind=='heist' else p.intent.requestId
                self.assertTrue(guard.Check(guard,p,raw)[0])
                native.owned=None
                self.assertFalse(guard.Check(guard,p,raw)[0])
                self.assertEqual(legacy_fixture.plain(review),original)
                engine=self.engine()
                self.assertIsNotNone(engine.Adopt(engine,review,sources,self.f.cp)[0])

    def test_typed_native_retirement_regression_epoch_or_method_swap_stays_blocked(self):
        for mode in ('retired','regression','epoch','method'):
            with self.subTest(mode=mode):
                self.setUp();guard,_,_=self.legacy_guard('heist')
                native=self.native_source('heist');p=self.native_proposal('heist');raw=self.raw()
                self.assertIsNotNone(guard.BindNativeSources, 'Typed native continuity binding is missing')
                self.assertTrue(guard.BindNativeSources(guard,lua_table(self.h.lua,{'heist':native}))[0])
                self.assertTrue(guard.Check(guard,p,raw)[0])
                original=native.Inspect
                if mode=='retired':native.valid=False
                elif mode=='regression':native.counter=6
                elif mode=='epoch':native.nativeEpoch='new-epoch'
                else:native.Inspect=self.h.lua.eval('function()return nil end')
                self.assertFalse(guard.Check(guard,p,raw)[0])
                native.valid=True;native.counter=7;native.nativeEpoch='epoch-a';native.Inspect=original
                self.assertFalse(guard.Check(guard,p,raw)[0])

    def fresh_heist_native(self):
        native=self.native_source('heist')
        native.counter=0;native.sequenceScope='nativeControllerEpoch';native.initialControllerCounter=0;native.controllerIdle=True
        self.h.lua.globals().freshCarryNative=native
        prior=native.Inspect;self.h.lua.globals().freshCarryPriorInspect=prior
        native.Inspect=self.h.lua.eval("""function(s)
            local value=freshCarryPriorInspect(s);if not value then return nil end
            value.sequenceScope=s.sequenceScope;value.initialControllerCounter=s.initialControllerCounter
            value.controllerIdle=s.controllerIdle;return value end""")
        return native

    def test_fresh_controller_epoch_preserves_legacy_receipt_but_uses_current_sequence(self):
        guard,review,sources=self.legacy_guard('heist');native=self.fresh_heist_native()
        self.assertTrue(guard.BindNativeSources(guard,lua_table(self.h.lua,{'heist':native}))[0])
        p=self.native_proposal('heist');p.intent.sequence=1;raw=self.raw()
        self.assertTrue(guard.Check(guard,p,raw)[0])
        native.owned=p;native.counter=1;native.controllerIdle=False
        self.assertTrue(guard.Check(guard,p,raw)[0])
        native.owned=None
        self.assertFalse(guard.Check(guard,p,raw)[0])
        native.controllerIdle=True;p.intent.sequence=2
        self.assertTrue(guard.Check(guard,p,raw)[0])
        self.assertEqual(guard.Summary(guard).floors.favorUsage.attempts,1)
        self.assertIsNotNone(review.blockedFeatures.favors)
        reopened=self.engine().Adopt(self.engine(),review,sources,self.f.cp)[0]
        self.assertTrue(reopened.BindCheckpoint(reopened,self.f.cp)[0])
        self.assertTrue(reopened.BindNativeSources(reopened,lua_table(self.h.lua,{'heist':native}))[0])
        self.assertTrue(reopened.Check(reopened,p,raw)[0])
        self.assertEqual(reopened.Summary(reopened).floors.favorUsage.attempts,1)

    def test_below_historical_counter_without_exact_fresh_idle_origin_is_refused(self):
        for mode in ('scope','origin','idle','missing_idle','missing_origin','sequence_zero','sequence_skip'):
            with self.subTest(mode=mode):
                self.setUp();guard,_,_=self.legacy_guard('heist');native=self.fresh_heist_native()
                p=self.native_proposal('heist');p.intent.sequence=1
                if mode=='scope':native.sequenceScope='accountLifetime'
                elif mode=='origin':native.initialControllerCounter=1
                elif mode=='idle':native.controllerIdle=False
                elif mode=='missing_idle':native.controllerIdle=None
                elif mode=='missing_origin':native.initialControllerCounter=None
                elif mode=='sequence_zero':p.intent.sequence=0
                else:p.intent.sequence=2
                self.assertTrue(guard.BindNativeSources(guard,lua_table(self.h.lua,{'heist':native}))[0])
                self.assertFalse(guard.Check(guard,p,self.raw())[0])

    def test_fresh_epoch_regression_origin_scope_or_methods_retire_stickily(self):
        for mode in ('regression','origin','epoch','method'):
            with self.subTest(mode=mode):
                self.setUp();guard,_,_=self.legacy_guard('heist');native=self.fresh_heist_native()
                p=self.native_proposal('heist');p.intent.sequence=1;raw=self.raw()
                self.assertTrue(guard.BindNativeSources(guard,lua_table(self.h.lua,{'heist':native}))[0])
                self.assertTrue(guard.Check(guard,p,raw)[0])
                native.counter=1;native.controllerIdle=False;native.owned=p
                self.assertTrue(guard.Check(guard,p,raw)[0])
                original=native.Inspect
                if mode=='regression':native.counter=0
                elif mode=='origin':native.initialControllerCounter=1
                elif mode=='epoch':native.nativeEpoch='changed'
                else:native.Inspect=self.h.lua.eval('function()return nil end')
                self.assertFalse(guard.Check(guard,p,raw)[0])
                native.counter=1;native.initialControllerCounter=0;native.nativeEpoch='epoch-a';native.Inspect=original
                self.assertFalse(guard.Check(guard,p,raw)[0])

    def test_real_recall_identity_survives_temporary_modal_without_sending(self):
        guard,_,_=self.legacy_guard('recall')
        port=self.h.lua.execute("""return {counter=0,ready=true,writes=0,
            Bound=function()return true end,Current=function(s)return s.ready end,
            Read=function(s)return {counter=s.counter,pending=s.pending}end,
            Write=function(s,k,v)s.writes=s.writes+1;s[k]=v end,
            Clock=function()return 1000 end}""")
        lease,why=self.h.load('src/tabs/territory/NativeRecallLease.luau').new(
            port,self.h.clock,lua_table(self.h.lua,{'account':self.identity['account'],
                'place':self.identity['place'],'userId':42,'jobId':'job-a','sourceKey':'a'*64}),
            lua_table(self.h.lua,{'id':'epoch-a','counterKnown':0,'proven':True}))
        self.assertIsNotNone(lease,why)
        self.assertTrue(guard.BindNativeSources(guard,lua_table(self.h.lua,{'recall':lease}))[0])
        p=self.native_proposal('recall');raw=self.raw()
        self.assertTrue(guard.Check(guard,p,raw)[0])
        port.ready=False
        # Identity inspection must not retire the source for a manual modal.
        guard.Check(guard,p,raw)
        self.assertFalse(lease.Acquire(lease,p,45)[0])
        self.assertEqual(port.writes,0)
        port.ready=True
        self.assertTrue(guard.Check(guard,p,raw)[0])
        self.assertTrue(lease.Acquire(lease,p,45)[0])
        self.assertTrue(guard.Check(guard,p,raw)[0])
        self.assertTrue(lease.Release(lease,p)[0])
        self.assertFalse(guard.Check(guard,p,raw)[0])

    def test_unknown_external_allowance_field_cannot_silently_disappear(self):
        value=dict(self.source_value, futureSpendUsage={'attempted':1})
        self.source.Write(self.source,self.cp_key,lua_table(self.h.lua,value))
        engine=self.engine()
        self.assertIsNone(engine.Preview(engine,self.f.cp)[0])

    def test_unrelated_feature_remains_eligible_and_source_active_custody_blocks_review(self):
        guard = self.guard()
        p = self.h.proposal('jobs', 'jobs:unrelated'); p.release = self.identity['release']
        self.assertTrue(guard.Check(guard, p, self.raw())[0])
        value = dict(self.source_value)
        value['records'] = [{'feature': 'operations'}]
        self.source.Write(self.source, self.cp_key, lua_table(self.h.lua, value))
        self.assertIsNone(self.engine().Preview(self.engine(), self.f.cp)[0])


if __name__ == '__main__':
    unittest.main()
