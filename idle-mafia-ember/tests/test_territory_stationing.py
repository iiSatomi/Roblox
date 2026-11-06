"""Own-member stationing never competes with training or a reserved member."""
import unittest, hashlib, json
import test_automation_runtime as runtime_fixture

from engine_harness import Harness, lua_table


class TerritoryStationingTests(unittest.TestCase):
    def setUp(self):
        base = runtime_fixture.AutomationRuntimeTests()
        base.setUp()
        self.h = base.h
        self.runtime_modules, self.storage = base.runtime.modules, base.storage
        base.runtime.Close(base.runtime)
        self.storage.Write = self.h.lua.eval("function(self,key,value) self.data[key]=value; return true end")
        self.h.lua.globals().stationHash = lambda value: hashlib.sha256(value.encode()).hexdigest()
        self.storage.hash = self.h.lua.eval("function(value) return stationHash(value) end")
        self.module = self.h.load("src/tabs/territory/Stationing.luau")
        self.state = self.module.new(lua_table(self.h.lua, {"TERRITORY": {"garrisonCap": 200}}),
            lua_table(self.h.lua, {"DISTRICTS_BY_ID": {"d1": {"city": "vespera"}}}),
            "a" * 64, "release-a")
        self.query = self.h.load("src/tabs/territory/DistrictQuery.luau").new()

    def raw(self, revision=1, stationed=False):
        crew = [{"name": "Player"}, {"name": "Ally", "rarity": 4, "healId": "ally"},
                {"name": "Guard", "rarity": 3, "healId": "guard"}, {"name": "Medic", "rarity": 2, "healId": "medic"}]
        if stationed:
            crew[1]["duty"] = "d1"
        return self.h.snapshot(revision=revision, native={"fullSync": True,
            "serverNow": 1000 + revision,
            "family": {"id": "fam-a"}, "crew": crew})

    def before(self):
        raw = self.raw()
        request, reason = self.query.Prepare(self.query, "d1", raw)
        self.assertIsNone(reason)
        result, reason = self.query.Accept(self.query, request, lua_table(self.h.lua, {
            "ok": True, "district": {"id": "d1", "mine": True, "holderId": "fam-a",
                "garrisonCount": 3, "garrisonCap": 200, "revision": 7}}))
        self.assertIsNone(reason)
        raw.territoryDistrict = result
        raw.territoryMap = lua_table(self.h.lua, {"header": {**self.h.session,
            "revision": 1, "capturedAt": 0}, "cityId": "vespera",
            "districts": [{"id": "d1", "mine": True}]})
        raw = self.state.Enrich(self.state, raw)[0]
        raw.stationReservationProof = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0, "members": {}, "attempted": 0})
        return raw

    def settings(self, **changes):
        value = {"enabled": True, "districtId": "d1", "memberSlot": 2,
                 "minHome": 2, "maxAttempts": 1}
        value.update(changes)
        return lua_table(self.h.lua, value)

    def test_full_saved_852_district_catalog_is_accepted(self):
        source = self.module.new(lua_table(self.h.lua, {"TERRITORY": {"garrisonCap": 200}}),
            lua_table(self.h.lua, {"DISTRICTS_BY_ID": {
                "d" + str(i): {"city": "city" + str(i % 8)} for i in range(852)}}),
            "a" * 64, "release-a")
        self.assertIsNotNone(source)

    def test_station_requires_unique_stable_native_member_ids(self):
        raw = self.before()
        raw.native.crew[2].healId = None
        view,reason=self.module.read(raw,raw)
        self.assertIsNotNone(view,reason)
        self.assertIsNone(self.module.propose(view,self.settings(minHome=0))[0])
        raw = self.before()
        raw.native.crew[3].healId = raw.native.crew[2].healId
        self.assertIsNone(self.module.read(raw, raw)[0])

    def test_same_named_distinct_member_ids_are_safe(self):
        raw = self.before()
        raw.native.crew[3].name, raw.native.crew[3].rarity = "Ally", 4
        self.assertIsNotNone(self.module.read(raw, raw)[0])

    def test_exact_station_call_and_newer_stable_member_duty(self):
        raw = self.before()
        view, reason = self.module.read(raw, raw)
        self.assertIsNone(reason)
        proposal, reason = self.module.propose(view, self.settings())
        self.assertIsNone(reason)
        calls = self.h.load("src/tabs/territory/TerritoryCallPlan.luau")
        call, reason = calls.describe(proposal)
        self.assertIsNone(reason)
        self.assertEqual((call.remote, call.arity, call.args[1], call.args[2], call.args[3]),
                         ("TerritoryAction", 4, "station", "d1", 2))
        baseline, reason = self.module.capture(proposal, raw)
        self.assertIsNone(reason)
        after = self.raw(2, True)
        self.assertEqual(self.module.evaluate(proposal, raw, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "confirmed")
        after.native.crew[2].name = "Replacement"
        self.assertEqual(self.module.evaluate(proposal, raw, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "pending")

    def test_reservations_home_training_injury_and_capacity_protect_crew(self):
        for change in ("reserved", "training", "injury", "full", "home", "family"):
            raw = self.before()
            settings = self.settings()
            if change == "reserved": raw.stationReservationProof.members["id:ally"] = True
            elif change == "training": raw.native.crew[2].training = lua_table(self.h.lua, {})
            elif change == "injury": raw.native.crew[2].injuredUntil = 2000
            elif change == "full": raw.territoryDistrict.district.garrisonCount = 200
            elif change == "home": settings.minHome = 3
            else: raw.native.family.id = "other"
            view = self.module.read(raw, raw)[0]
            if view is not None:
                self.assertIsNone(self.module.propose(view, settings)[0], change)

    def test_missing_ownership_and_duplicate_members_cannot_send(self):
        raw = self.before()
        raw.stationReservationProof = None
        view = self.module.read(raw, raw)[0]
        self.assertIsNone(self.module.propose(view, self.settings())[0])
        raw = self.before()
        raw.native.crew[3].healId = "ally"
        self.assertIsNone(self.module.read(raw, raw)[0])
        raw = self.before()
        view = self.module.read(raw, raw)[0]
        self.assertIsNone(self.module.propose(view, self.settings(maxAttempts=0))[0])

    def test_unbound_district_city_and_nil_reply_are_rejected(self):
        self.assertIsNone(self.module.read(self.raw(), self.raw())[0])
        raw = self.before()
        raw.territoryMap.cityId = "other"
        self.assertIsNone(self.module.read(raw, raw)[0])
        raw = self.before()
        raw.territoryMap.districts[2] = lua_table(self.h.lua, {"id": "d1", "mine": False})
        self.assertIsNone(self.module.read(raw, raw)[0])
        request = self.query.Prepare(self.query, "d1", self.raw())[0]
        self.assertIsNone(self.query.Accept(self.query, request, None)[0])

    def test_tier_eight_uses_reviewed_300_capacity_when_reply_omits_cap(self):
        source = self.module.new(lua_table(self.h.lua, {"TERRITORY": {
            "garrisonCap": 200, "garrisonCapByTier": {7: 250, 8: 300}}}),
            lua_table(self.h.lua, {"DISTRICTS_BY_ID": {"d1": {"city": "vespera", "tier": 8}}}),
            "a" * 64, "release-a")
        raw = self.before()
        raw = source.Enrich(source, raw)[0]
        raw.territoryDistrict.district.garrisonCap = None
        raw.territoryDistrict.district.garrisonCount = 299
        view, reason = self.module.read(raw, raw)
        self.assertIsNone(reason)
        self.assertEqual(view.cap, 300)
        self.assertIsNotNone(self.module.propose(view, self.settings())[0])
        raw.territoryDistrict.district.garrisonCount = 300
        self.assertIsNone(self.module.propose(self.module.read(raw, raw)[0], self.settings())[0])

    def test_send_time_member_reservation_and_limits_are_rechecked(self):
        raw = self.before()
        proposal = self.module.propose(self.module.read(raw, raw)[0], self.settings())[0]
        raw.stationReservationProof.members["id:ally"] = True
        self.assertIsNone(self.module.capture(proposal, raw)[0])
        raw.stationReservationProof.members["id:ally"] = None
        raw.stationReservationProof.attempted = 1
        self.assertIsNone(self.module.capture(proposal, raw)[0])
        raw.stationReservationProof.attempted = 0
        proposal.resources.stamina = 1
        self.assertIsNone(self.module.capture(proposal, raw)[0])

    def legacy_home(self, raw, slot=3):
        raw.native.crew[slot].healId=None
        raw.native.crew[slot].legacyDetails=lua_table(self.h.lua,{'rank':2,'cosmetic':{'hat':'plain'}})
        return raw

    def test_unidentified_home_bystander_has_no_identity_home_or_capacity_credit(self):
        raw=self.legacy_home(self.before())
        view,reason=self.module.read(raw,raw);self.assertIsNotNone(view,reason)
        self.assertTrue(view.members[3].unidentified)
        self.assertIsNone(view.members[3].key)
        proposal,reason=self.module.propose(view,self.settings(minHome=1,maxStationed=1))
        self.assertIsNotNone(proposal,reason)
        self.assertEqual(proposal.intent.memberKey,'id:ally')
        self.assertEqual(proposal.intent.homeSlots,'4')
        self.assertIsNone(proposal.intent.homeKey3)
        self.assertIsInstance(proposal.intent.unidentifiedHome3,str)
        self.assertLessEqual(len(proposal.intent.unidentifiedHome3.encode()),900)
        self.assertIsNone(self.module.propose(view,self.settings(minHome=2))[0])
        self.assertIsNone(self.module.propose(view,self.settings(memberSlot=3,minHome=0))[0])
        self.assertIsNotNone(self.module.capture(proposal,raw)[0])

    def test_unidentified_deployed_or_ambiguous_rows_still_block_whole_roster(self):
        for key,value in [('duty','d1'),('dutyToken','token'),('stationed',True),('recalling',True),
                ('dutyPending',True),('dutyRemapPending',True),('training',{}),('rolling',True)]:
            with self.subTest(key=key):
                raw=self.legacy_home(self.before());raw.native.crew[3][key]=lua_table(self.h.lua,value)
                self.assertIsNone(self.module.read(raw,raw)[0])

    def test_unidentified_full_baseline_changes_or_reorder_prevent_settlement(self):
        raw=self.legacy_home(self.before());view,reason=self.module.read(raw,raw)
        self.assertIsNotNone(view,reason)
        proposal=self.module.propose(view,self.settings(minHome=1))[0]
        baseline,reason=self.module.capture(proposal,raw);self.assertIsNotNone(baseline,reason)
        for change in ('none','nested','added','removed','identity','reorder'):
            with self.subTest(change=change):
                after=self.legacy_home(self.raw(2,True))
                if change=='nested':after.native.crew[3].legacyDetails.cosmetic.hat='changed'
                elif change=='added':after.native.crew[3].extra=True
                elif change=='removed':after.native.crew[3].legacyDetails=None
                elif change=='identity':after.native.crew[3].healId='new'
                elif change=='reorder':after.native.crew[3],after.native.crew[4]=after.native.crew[4],after.native.crew[3]
                self.assertEqual(self.module.evaluate(proposal,raw,after,lua_table(self.h.lua,{'ok':True}),baseline),
                    'confirmed' if change=='none' else 'pending')

    def test_unidentified_observation_is_bounded_and_rejects_cycles_or_unsupported_values(self):
        for change in ('oversize','cycle','function','depth'):
            with self.subTest(change=change):
                raw=self.legacy_home(self.before());row=raw.native.crew[3]
                if change=='oversize':row.extra='x'*1000
                elif change=='cycle':row.extra=row
                elif change=='function':row.extra=self.h.lua.eval('function()end')
                else:
                    row.extra=self.h.lua.table();at=row.extra
                    for _ in range(12):at.child=self.h.lua.table();at=at.child
                self.assertIsNone(self.module.read(raw,raw)[0])

    def test_actual_app_queued_unidentified_bystander_drift_refuses_before_native_send(self):
        app,runtime,executor=self.start_app()
        try:
            self.select(app,**{'station.custom.minHome':1})
            raw=self.legacy_home(self.before());app.Step(app,raw)
            self.assertIsNotNone(executor.callback,runtime.Status(runtime).reasons.station)
            raw.native.crew[3].legacyDetails.cosmetic.hat='changed'
            executor.callback()
            self.assertEqual(len(executor.calls),0)
            self.assertEqual(runtime.checkpoint.stationAttempts,0)
            self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)),0)
        finally:app.Destroy(app)

    def test_actual_app_transient_codes_never_settle_positive_or_negative_across_restart(self):
        for code in ('pending','busy'):
            for positive in (True,False):
                with self.subTest(code=code,positive=positive):
                    f=TerritoryStationingTests();f.setUp()
                    app,runtime,executor,raw=f.begin_app()
                    try:
                        executor.reply=lua_table(f.h.lua,{'ok':positive,'code':code});executor.callback()
                        f.h.at(1);app.Step(app,f.raw(2,positive))
                        self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)),1)
                        self.assertEqual(runtime.checkpoint.stationAttempts,1)
                        f.h.at(45);app.Step(app,f.raw(3,positive))
                        self.assertEqual(runtime.Status(runtime).outcomes.station,'skipped_unconfirmed')
                        app.Destroy(app);app,runtime,executor=f.start_app()
                        f.h.at(46);app.Step(app,f.raw(4,positive))
                        self.assertIsNone(runtime.Status(runtime).recoveries.station)
                        self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)),1)
                        self.assertEqual(runtime.checkpoint.stationAttempts,1)
                        self.assertEqual(len(executor.calls),0)
                    finally:app.Destroy(app)

    def test_maximum_roster_observations_fit_flat_intent_and_saved_codec(self):
        raw=self.before()
        for slot in range(3,47):
            raw.native.crew[slot]=lua_table(self.h.lua,{'name':'Legacy '+str(slot),'rarity':3})
        view,reason=self.module.read(raw,raw);self.assertIsNotNone(view,reason)
        proposal,reason=self.module.propose(view,self.settings(minHome=0));self.assertIsNotNone(proposal,reason)
        self.assertLessEqual(len(list(proposal.intent.keys())),64)
        self.assertFalse(any(str(key).startswith('homeKey') for key in proposal.intent.keys()))
        baseline,reason=self.module.capture(proposal,raw);self.assertIsNotNone(baseline,reason)
        pending=self.h.load('src/storage/PendingAction.luau')
        saved,reason=pending.Capture(proposal,raw,baseline);self.assertIsNotNone(saved,reason)
        decoded=pending.Decode(saved)
        if isinstance(decoded,tuple):decoded,reason=decoded
        self.assertIsNotNone(decoded,reason)
        self.assertEqual(decoded.proposal.intent.unidentifiedHome46,proposal.intent.unidentifiedHome46)
        self.assertIsNone(decoded.baseline.members[46].key)

    def test_actual_app_unidentified_bystander_roundtrips_v2_and_recovers_exactly(self):
        app,runtime,executor=self.start_app()
        try:
            self.select(app,**{'station.custom.minHome':1})
            before=self.legacy_home(self.before());app.Step(app,before)
            self.assertIsNotNone(executor.callback,runtime.Status(runtime).reasons.station)
            executor.callback();self.assertEqual(len(executor.calls),1)
            record=runtime.checkpoint.Records(runtime.checkpoint)[1]
            data=runtime.checkpoint.Recovery(runtime.checkpoint,record.actionKey)[0]
            self.assertTrue(data.baseline.members[3].unidentified)
            self.assertEqual(data.baseline.members[3].originalRow.legacyDetails.cosmetic.hat,'plain')
            self.assertEqual(data.proposal.intent.memberKey,'id:ally')
            held=runtime.reservationOwner.Held(runtime.reservationOwner,before)[0]
            self.assertEqual(set(held.members.keys()),{'id:ally','id:medic','slot:2','slot:4'})
            app.Destroy(app)
            def wire(value):
                if not hasattr(value,'items'):return value
                entries=dict(value.items())
                if entries and set(entries)==set(range(1,len(entries)+1)):
                    return [wire(entries[i]) for i in range(1,len(entries)+1)]
                return {key:wire(child) for key,child in entries.items()}
            for key,value in list(self.storage.data.items()):
                self.storage.data[key]=lua_table(self.h.lua,json.loads(json.dumps(wire(value),allow_nan=False)))
            self.h.session['session']='legacy-station-restart';self.h.at(1)
            app,owner,transport=self.start_app()
            app.Step(app,self.legacy_home(self.raw(2,True)))
            self.assertEqual(owner.Status(owner).recoveries.station,'confirmed')
            self.assertEqual(len(owner.checkpoint.Records(owner.checkpoint)),0)
            self.assertEqual(len(transport.calls),0)
        finally:app.Destroy(app)

    def start_app(self, with_residency=False):
        module = self.h.load("src/tabs/territory/Module.luau")
        deps = {name: self.h.load(path) for name, path in {
            "TerritoryMapQuery": "src/tabs/territory/TerritoryMapQuery.luau",
            "ResidencyQuery": "src/tabs/territory/ResidencyQuery.luau",
            "TerritoryState": "src/tabs/territory/TerritoryState.luau",
            "ReadAttachment": "src/tabs/territory/ReadAttachment.luau",
            "TerritoryBlocked": "src/tabs/territory/TerritoryBlocked.luau"}.items()}
        if with_residency: deps["Residency"] = self.h.load("src/tabs/territory/Residency.luau")
        deps.update({"Stationing": self.module, "config": {"TERRITORY": {"garrisonCap": 200}},
            "gameData": {"DISTRICTS_BY_ID": {"d1": {"city": "vespera"}}},
            "fingerprint": "a" * 64, "release": "release-a"})
        if hasattr(self,'station_city_source'):
            deps['territoryCitySource']=self.station_city_source
            deps['gameData']['DISTRICTS_BY_ID']['d1']['city']=self.station_catalog_city
        tab = module.new(lua_table(self.h.lua, deps))
        executor = self.h.lua.execute("""return {calls={},
            Schedule=function(self, cb) self.callback=cb; return true end,
            Invoke=function(self, remote, method, ...)
                self.calls[#self.calls+1]={remote=remote,args=table.pack(...)}
                return self.reply or {ok=true}
            end}""")
        native = self.h.load("src/transport/NativeCallPlan.luau")
        plan = native.withTerritory(native, self.h.load("src/tabs/territory/TerritoryCallPlan.luau"))
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(plan, executor)
        runtime = self.h.load("src/engine/AutomationRuntime.luau").new(lua_table(self.h.lua, {
            "clock": self.h.clock, "transport": adapter, "storage": self.storage,
            "identity": self.h.session, "modules": self.runtime_modules,
            "features": tab.Descriptors(tab), "tabInstances": [tab], "featurePages": {"station": "territory", "territoryWatch": "territory", "residency": "territory"},
            "snapshotAssembler": self.h.load("src/tabs/TabSnapshotAssembler.luau").new(lua_table(self.h.lua, [tab]))}))
        app = self.h.load("src/App.luau").start(lua_table(self.h.lua, {
            "Ember": self.h.load("tests/ember_double.lua")(),
            "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "TerritoryTab": module, "automationRuntimeInstance": runtime}))
        return app, runtime, executor

    def test_large_mixed_station_snapshot_persists_custody_and_recovers_without_replay(self):
        app,runtime,executor=self.start_app()
        self.select(app)
        before=self.before()
        before.native.heistLedger=lua_table(self.h.lua,[{'userId':i,'name':'Player '+str(i),
            'lastAt':900,'helped':1,'gotHelped':0,'helpedToday':0,'lastHeistId':'h_corner','friend':False} for i in range(1000)])
        before.native.heistResults=lua_table(self.h.lua,[{'id':'old-run-'+str(i),'heistId':'h_corner',
            'cash':35000,'xp':196,'collected':True,'completedAt':900} for i in range(1000)])
        before.data=before.native  # NativeSnapshotReader exposes this same native alias.
        try:
            app.Step(app,before)
            self.assertIsNotNone(executor.callback,runtime.Status(runtime).reasons.station)
            executor.callback();self.assertEqual(len(executor.calls),1)
            record=runtime.checkpoint.Records(runtime.checkpoint)[1]
            data=runtime.checkpoint.Recovery(runtime.checkpoint,record.actionKey)[0]
            baseline,why=self.module.capture(data.proposal,data.before)
            self.assertIsNotNone(baseline,why)
            self.assertEqual(baseline.memberKey,data.baseline.memberKey)
            self.assertEqual(before.native.heistLedger[1000].name,'Player 999')
            app.Set(app,'station.enabled',False);app.Destroy(app)
            self.h.session['session']='station-large-reload';self.h.at(1)
            resumed,owner,transport=self.start_app()
            try:
                resumed.Step(resumed,self.raw(2,True))
                self.assertEqual(owner.Status(owner).recoveries.station,'confirmed')
                self.assertEqual(len(owner.checkpoint.Records(owner.checkpoint)),0)
                self.assertEqual(len(transport.calls),0)
                self.assertFalse(resumed.model['values']['station.enabled'])
            finally:resumed.Destroy(resumed)
        finally:app.Destroy(app)

    def test_actual_app_maps_display_city_to_current_native_city_before_stationing(self):
        self.station_catalog_city='Jade Harbor'
        self.station_city_source=self.h.lua.execute("return {Current=function()return true end,Select=function(_,city,id)assert(id=='d1');return {cityId='jade_harbor'}end}")
        app,runtime,executor=self.start_app()
        try:
            self.select(app);before=self.before();before.territoryMap.cityId='jade_harbor'
            app.Step(app,before)
            self.assertIsNotNone(executor.callback,runtime.Status(runtime).reasons.station)
            executor.callback();self.assertEqual(len(executor.calls),1)
            app.Set(app,'station.enabled',False);self.h.at(1);app.Step(app,self.raw(2,True))
            self.assertEqual(runtime.Status(runtime).outcomes.station,'confirmed')
            self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)),0)
        finally:app.Destroy(app)

    def test_actual_app_keeps_verified_nil_city_global_map_scope(self):
        self.station_catalog_city='Jade Harbor'
        self.station_city_source=self.h.lua.execute("return {Current=function()return true end,Select=function()return {}end}")
        app,runtime,executor=self.start_app()
        try:
            self.select(app);before=self.before();before.territoryMap.cityId='all'
            app.Step(app,before)
            self.assertIsNotNone(executor.callback,runtime.Status(runtime).reasons.station)
            executor.callback();self.assertEqual(len(executor.calls),1)
        finally:app.Destroy(app)

    def test_unknown_native_city_mapping_does_not_fall_back_to_a_matching_label(self):
        self.station_catalog_city='vespera'
        self.station_city_source=self.h.lua.execute("return {Current=function()return true end,Select=function()return nil,'Unknown native city mapping'end}")
        app,runtime,executor=self.start_app()
        try:
            self.select(app);app.Step(app,self.before())
            self.assertIsNone(executor.callback)
            self.assertEqual(len(executor.calls),0)
            self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)),0)
        finally:app.Destroy(app)

    def test_queued_station_refuses_a_changed_native_city_source_and_refunds_unsent(self):
        self.station_catalog_city='vespera'
        self.station_city_source=self.h.lua.execute("return {valid=true,Current=function(self)return self.valid end,Select=function()return {cityId='vespera'}end}")
        app,runtime,executor=self.start_app()
        try:
            self.select(app);app.Step(app,self.before())
            self.assertIsNotNone(executor.callback)
            self.station_city_source.valid=False;executor.callback()
            self.assertEqual(len(executor.calls),0)
            self.assertEqual(runtime.checkpoint.stationAttempts,0)
            self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)),0)
        finally:app.Destroy(app)

    def test_app_broker_native_adapter_stationing_and_disable(self):
        app, runtime, executor = self.start_app()
        self.assertIsNone(app.ui.features.station.blockedReason)
        for key, value in (("station.enabled", True), ("station.custom.districtId", "d1"),
                           ("station.custom.maxAttempts", 1)):
            self.assertTrue(app.Set(app, key, value)[0])
        self.assertTrue(app.Resume(app)[0])
        self.assertTrue(app.Step(app, self.before())[0])
        executor.callback()
        self.assertEqual(len(executor.calls), 1)
        self.assertEqual(executor.calls[1].args.n, 4)
        self.assertEqual(executor.calls[1].args[1], "station")
        self.h.at(1)
        self.assertTrue(app.Step(app, self.raw(2, True))[0])
        self.assertEqual(runtime.Status(runtime).outcomes.station, "confirmed")
        self.assertTrue(app.Set(app, "station.enabled", False)[0])
        self.assertTrue(app.Step(app, self.raw(3, True))[0])
        self.assertEqual(len(executor.calls), 1)
        app.Destroy(app)

    def select(self, app, **settings):
        values = {"station.enabled": True, "station.custom.districtId": "d1",
                  "station.custom.maxAttempts": 1}
        values.update(settings)
        for key, value in values.items(): self.assertTrue(app.Set(app, key, value)[0])
        app.Resume(app)

    def test_app_uses_owned_attempt_count_not_forged_or_missing_proof(self):
        app, runtime, executor = self.start_app()
        self.select(app)
        raw = self.before()
        raw.stationReservationProof = None
        app.Step(app, raw)
        self.assertIsNotNone(executor.callback)
        executor.callback()
        self.h.at(1)
        app.Step(app, self.raw(2, True))
        self.assertEqual(runtime.Status(runtime).outcomes.station, "confirmed")
        self.assertEqual(runtime.checkpoint.stationAttempts, 1)
        app.Destroy(app)

    def test_pending_negative_and_unchanged_revision_cannot_reject(self):
        raw = self.before()
        proposal = self.module.propose(self.module.read(raw, raw)[0], self.settings())[0]
        baseline = self.module.capture(proposal, raw)[0]
        for after, reply in ((raw, {"ok": False}), (self.raw(2), {"ok": False, "pending": True}),
                             (self.raw(2), {"ok": False, "code": "presence"})):
            self.assertEqual(self.module.evaluate(proposal, raw, after,
                lua_table(self.h.lua, reply), baseline), "pending")

    def test_saved_exact_station_receipt_and_rejection(self):
        raw = self.before()
        proposal = self.module.propose(self.module.read(raw, raw)[0], self.settings())[0]
        baseline = self.module.capture(proposal, raw)[0]
        data = lua_table(self.h.lua, {"proposal": proposal, "before": raw, "baseline": baseline,
                                     "reply": {"ok": True}})
        self.assertEqual(self.module.recoverSaved(data, self.raw(2, True)), "confirmed")
        data.reply = lua_table(self.h.lua, {"ok": False})
        self.assertEqual(self.module.recoverSaved(data, self.raw(2)), "rejected")

    def begin_app(self, **settings):
        app, runtime, executor = self.start_app()
        self.select(app, **settings)
        raw = self.before()
        app.Step(app, raw)
        self.assertIsNotNone(executor.callback)
        return app, runtime, executor, raw

    def test_actual_app_disable_before_invoke_refunds_only_unsent_attempt(self):
        app,runtime,executor,raw = self.begin_app()
        self.assertEqual(runtime.checkpoint.stationAttempts, 1)
        app.Set(app, "station.enabled", False)
        executor.callback()
        self.assertEqual(len(executor.calls), 0)
        self.assertEqual(runtime.checkpoint.stationAttempts, 0)
        self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)), 0)
        app.Destroy(app)

    def test_queued_native_member_or_home_defense_drift_refuses_invocation(self):
        for field in ("healId", "training", "dutyPending", "home"):
            app,runtime,executor,raw = self.begin_app()
            if field == "healId": raw.native.crew[2].healId = "replacement"
            elif field == "training": raw.native.crew[2].training = self.h.lua.table()
            elif field == "dutyPending": raw.native.crew[2].dutyPending = True
            else: raw.native.crew[3].duty = "elsewhere"
            executor.callback()
            self.assertEqual(len(executor.calls), 0, field)
            self.assertEqual(runtime.checkpoint.stationAttempts, 0)
            app.Destroy(app)

    def test_sent_pending_45_seconds_keeps_roster_custody_and_attempt(self):
        app,runtime,executor,raw = self.begin_app()
        executor.reply = lua_table(self.h.lua, {"ok": True, "pending": True})
        executor.callback()
        self.h.at(45)
        app.Step(app, self.raw(2))
        self.assertEqual(runtime.Status(runtime).outcomes.station, "skipped_unconfirmed")
        self.assertEqual(runtime.checkpoint.stationAttempts, 1)
        held=runtime.reservationOwner.Held(runtime.reservationOwner,self.raw(2))[0]
        self.assertFalse(held.allCrew)
        self.assertTrue(held.members["id:ally"] and held.members["id:guard"] and held.members["id:medic"])
        app.Destroy(app)

    def test_saved_app_receipt_recovers_without_resending_or_refunding(self):
        app,runtime,executor,raw = self.begin_app()
        executor.callback()
        app.Destroy(app)
        app,runtime,executor = self.start_app()
        self.h.at(1)
        app.Step(app, self.raw(2, True))
        self.assertEqual(runtime.Status(runtime).recoveries.station, "confirmed")
        self.assertEqual(len(executor.calls), 0)
        self.assertEqual(runtime.checkpoint.stationAttempts, 1)
        self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)), 0)
        app.Destroy(app)

    def test_saved_app_rejection_consumes_attempt_and_caps_reload(self):
        app,runtime,executor,raw = self.begin_app()
        executor.reply = lua_table(self.h.lua, {"ok": False})
        executor.callback(); app.Destroy(app)
        app,runtime,executor = self.start_app()
        self.h.at(1); app.Step(app, self.raw(2))
        self.assertEqual(runtime.Status(runtime).recoveries.station, "rejected")
        self.select(app)
        app.Step(app, self.before())
        self.assertEqual(runtime.checkpoint.stationAttempts, 1)
        self.assertEqual(len(executor.calls), 0)
        app.Destroy(app)

    def test_unload_before_queued_invocation_records_exact_unsent_for_next_owner(self):
        app,runtime,executor,raw = self.begin_app()
        app.Destroy(app); executor.callback()
        self.assertEqual(len(executor.calls), 0)
        app,runtime,executor = self.start_app()
        self.h.at(1); app.Step(app, self.raw(2))
        self.assertEqual(runtime.Status(runtime).recoveries.station, "known_unsent")
        self.assertEqual(runtime.checkpoint.stationAttempts, 0)
        app.Destroy(app)

    def test_saved_station_count_corruption_refuses_load(self):
        app,runtime,executor,raw = self.begin_app()
        key = runtime.checkpoint.ScopeKey(runtime.checkpoint)
        app.Destroy(app)
        self.storage.data[key].stationAttempts = False
        app,runtime,executor = self.start_app()
        self.assertIsNotNone(runtime.session.storageFault)
        app.Destroy(app)

    def test_zero_attempt_budget_never_schedules(self):
        app,runtime,executor = self.start_app()
        self.select(app, **{"station.custom.maxAttempts": 0})
        app.Step(app, self.before())
        self.assertIsNone(executor.callback)
        self.assertEqual(runtime.checkpoint.stationAttempts, 0)
        app.Destroy(app)

    def test_station_allowance_reset_is_explicit_paused_and_durable(self):
        app,runtime,executor,raw = self.begin_app()
        executor.callback();self.h.at(1);app.Step(app,self.raw(2,True))
        self.assertIsNone(app.PreviewAllowance(app,"station")[0])
        app.Pause(app)
        preview,reason=app.PreviewAllowance(app,"station")
        self.assertIsNone(reason)
        self.assertEqual((preview.attempted,preview.spent),(1,0))
        self.assertTrue(app.ConfirmAllowance(app,"station")[0])
        self.assertEqual(runtime.checkpoint.stationAttempts,0)
        self.assertEqual(len(executor.calls),1)
        app.Destroy(app)
        app,runtime,executor=self.start_app()
        self.assertEqual(runtime.checkpoint.stationAttempts,0)
        app.Destroy(app)

    def test_station_uncertain_custody_prevents_allowance_reset(self):
        app,runtime,executor,raw=self.begin_app()
        executor.reply=lua_table(self.h.lua,{"ok":True,"pending":True});executor.callback()
        self.h.at(45);app.Step(app,self.raw(2));app.Pause(app)
        self.assertIsNone(app.PreviewAllowance(app,"station")[0])
        self.assertEqual(runtime.checkpoint.stationAttempts,1)
        app.Destroy(app)

    def test_unrelated_training_can_continue_while_selected_home_backup_is_reserved(self):
        app,runtime,executor=self.start_app()
        self.select(app, **{"station.custom.minHome":1})
        raw=self.before();raw.native.crew[4].training=lua_table(self.h.lua,{"to":1,"endsAt":1010})
        app.Step(app,raw)
        self.assertIsNotNone(executor.callback)
        executor.callback();self.assertEqual(len(executor.calls),1)
        held=runtime.reservationOwner.Held(runtime.reservationOwner,raw)[0]
        self.assertFalse(held.allCrew)
        self.assertTrue(held.members["id:ally"])
        self.assertTrue(held.members["id:guard"])
        self.assertIsNone(held.members["id:medic"])
        self.h.at(1);after=self.raw(2,True);after.native.crew[4].train=1
        app.Step(app,after)
        self.assertEqual(runtime.Status(runtime).outcomes.station,"confirmed")
        app.Destroy(app)

    def test_queued_home_backup_cannot_silently_switch_to_another_member(self):
        app,runtime,executor=self.start_app();self.select(app,**{"station.custom.minHome":1})
        raw=self.before();app.Step(app,raw)
        raw.native.crew[3].duty="elsewhere"
        executor.callback()
        self.assertEqual(len(executor.calls),0)
        self.assertEqual(runtime.checkpoint.stationAttempts,0)
        app.Destroy(app)


    def test_legacy_max_stationed_blocks_even_with_open_family_slots(self):
        raw=self.before();raw.native.crew[3].duty='other-district'
        view=self.module.read(raw,raw)[0]
        self.assertIsNone(self.module.propose(view,self.settings(minHome=0,maxStationed=1))[0])
    def test_station_cap_boundary_and_zero_are_independent_of_attempt_allowance(self):
        raw=self.before();view=self.module.read(raw,raw)[0]
        self.assertIsNone(self.module.propose(view,self.settings(minHome=0,maxStationed=0))[0])
        self.assertIsNotNone(self.module.propose(view,self.settings(minHome=0,maxStationed=1))[0])
    def test_actual_app_tightened_station_cap_cancels_only_unsent_attempt(self):
        app,runtime,executor=self.start_app()
        try:
            self.select(app,**{'station.custom.minHome':0})
            app.Step(app,self.before())
            self.assertTrue(app.Set(app,'station.custom.maxStationed',0)[0]);executor.callback()
            self.assertEqual(len(executor.calls),0);self.assertEqual(runtime.checkpoint.stationAttempts,0)
        finally:app.Destroy(app)
    def test_saved_unknown_station_counts_toward_cap_after_restart(self):
        app,runtime,executor=self.start_app()
        self.select(app,**{'station.custom.minHome':0,'station.custom.maxAttempts':3})
        app.Step(app,self.before());executor.reply=lua_table(self.h.lua,{'ok':True,'pending':True});executor.callback();app.Destroy(app)
        app,runtime,executor=self.start_app()
        try:
            self.select(app,**{'station.custom.minHome':0,'station.custom.memberSlot':3,'station.custom.maxAttempts':3,'station.custom.maxStationed':1})
            app.Step(app,self.before());self.assertEqual(len(executor.calls),0)
            self.assertIsNone(executor.callback);self.assertEqual(runtime.checkpoint.stationAttempts,1)
        finally:app.Destroy(app)
    def test_pending_and_replicated_same_member_are_not_double_counted(self):
        raw=self.before();raw.native.crew[3].duty='other';raw.stationReservationProof.pendingStation=lua_table(self.h.lua,{'id:guard':True})
        view=self.module.read(raw,raw)[0]
        self.assertIsNotNone(self.module.propose(view,self.settings(minHome=0,maxStationed=2))[0])
    def test_pending_unknown_station_identity_holds_new_deployment(self):
        raw=self.before();raw.stationReservationProof.stationUnknown=True
        view=self.module.read(raw,raw)[0]
        self.assertIsNone(self.module.propose(view,self.settings(minHome=0,maxStationed=45))[0])

    def test_cap_tightened_after_send_keeps_exact_confirmation(self):
        app,runtime,executor=self.start_app()
        try:
            self.select(app);app.Step(app,self.before());executor.callback()
            app.Set(app,'station.custom.maxStationed',0);self.h.at(1);app.Step(app,self.raw(2,True))
            self.assertEqual(runtime.Status(runtime).outcomes.station,'confirmed')
            self.assertEqual(runtime.checkpoint.stationAttempts,1)
        finally:app.Destroy(app)
    def test_native_deployed_count_blocks_next_member_after_confirmed_send(self):
        app,runtime,executor=self.start_app()
        try:
            self.select(app,**{'station.custom.minHome':0,'station.custom.maxAttempts':3,'station.custom.maxStationed':1})
            app.Step(app,self.before());executor.callback();self.h.at(1);app.Step(app,self.raw(2,True))
            app.Set(app,'station.custom.memberSlot',3)
            raw=self.before();raw.native.crew[2].duty='d1';self.h.at(0);app.Step(app,raw)
            self.assertEqual(runtime.checkpoint.stationAttempts,1);self.assertEqual(len(executor.calls),1)
        finally:app.Destroy(app)
    def test_caller_cannot_clear_saved_deployment_cap_ownership(self):
        app,runtime,executor=self.start_app()
        self.select(app,**{'station.custom.minHome':0,'station.custom.maxAttempts':3})
        app.Step(app,self.before());executor.reply=lua_table(self.h.lua,{'ok':True,'pending':True});executor.callback();app.Destroy(app)
        app,runtime,executor=self.start_app()
        try:
            self.select(app,**{'station.custom.minHome':0,'station.custom.memberSlot':3,'station.custom.maxAttempts':3,'station.custom.maxStationed':1})
            raw=self.before();raw.stationReservationProof.pendingStation=self.h.lua.table();raw.stationReservationProof.stationUnknown=False
            app.Step(app,raw);self.assertIsNone(executor.callback);self.assertEqual(runtime.checkpoint.stationAttempts,1)
        finally:app.Destroy(app)
    def test_station_cap_rejects_invalid_typed_values(self):
        app,runtime,executor=self.start_app()
        try:
            for value in (-1,1.5,46,True):self.assertFalse(app.Set(app,'station.custom.maxStationed',value)[0])
        finally:app.Destroy(app)

    def test_review_recalling_member_and_home_backup_are_unavailable(self):
        raw=self.before();raw.native.crew[2].recalling=True
        view=self.module.read(raw,raw)[0];self.assertIsNone(self.module.propose(view,self.settings(minHome=0))[0])
        raw=self.before();raw.native.crew[3].recalling=True
        view=self.module.read(raw,raw)[0];self.assertIsNone(self.module.propose(view,self.settings(minHome=2))[0])
    def test_review_stationed_flag_without_duty_blocks_redeployment_and_counts_cap(self):
        raw=self.before();raw.native.crew[2].stationed=True
        view=self.module.read(raw,raw)[0];self.assertIsNone(self.module.propose(view,self.settings(minHome=0))[0])
        raw=self.before();raw.native.crew[3].stationed=True
        view=self.module.read(raw,raw)[0];self.assertIsNone(self.module.propose(view,self.settings(minHome=0,maxStationed=1))[0])
    def test_review_dispatch_rechecks_other_pending_station_targets(self):
        raw=self.before();view=self.module.read(raw,raw)[0]
        proposal=self.module.propose(view,self.settings(minHome=0,maxStationed=1))[0]
        raw.stationReservationProof.pendingStation=lua_table(self.h.lua,{'id:guard':True})
        self.assertFalse(self.module.canDispatch(proposal,raw))
    def test_review_dispatch_excludes_its_own_pending_record_from_cap(self):
        raw=self.before();view=self.module.read(raw,raw)[0]
        proposal=self.module.propose(view,self.settings(minHome=0,maxStationed=1))[0]
        raw.stationReservationProof.pendingStation=lua_table(self.h.lua,{'id:ally':True})
        self.assertTrue(self.module.canDispatch(proposal,raw))
    def test_review_dispatch_does_not_erase_unknown_pending_identity(self):
        raw=self.before();view=self.module.read(raw,raw)[0]
        proposal=self.module.propose(view,self.settings(minHome=0,maxStationed=1))[0]
        raw.stationReservationProof.stationUnknown=True
        self.assertFalse(self.module.canDispatch(proposal,raw))
    def test_review_settling_and_shielded_districts_block_station(self):
        for field,value in [('settling',True),('shieldUntil',2000)]:
            raw=self.before();raw.territoryDistrict.district[field]=value
            view=self.module.read(raw,raw)[0]
            self.assertTrue(view is None or self.module.propose(view,self.settings())[0] is None)
    def test_review_stationed_flag_can_change_with_exact_confirmed_duty(self):
        raw=self.before();proposal=self.module.propose(self.module.read(raw,raw)[0],self.settings())[0]
        baseline=self.module.capture(proposal,raw)[0];after=self.raw(2,True);after.native.crew[2].stationed=True
        self.assertEqual(self.module.evaluate(proposal,raw,after,lua_table(self.h.lua,{'ok':True}),baseline),'confirmed')

    def district_reply(self,**changes):
        raw=self.raw();request=self.query.Prepare(self.query,'d1',raw)[0]
        row={'id':'d1','mine':True,'holderId':'fam-a','garrisonCount':3,'garrisonCap':200,'revision':7};row.update(changes)
        return self.query.Accept(self.query,request,lua_table(self.h.lua,{'ok':True,'district':row}))
    def test_review_query_preserves_guard_fields_without_aliasing_reply(self):
        result,reason=self.district_reply(settling=True,shieldUntil=2000)
        self.assertIsNone(reason);self.assertTrue(result.district.settling);self.assertEqual(result.district.shieldUntil,2000)
    def test_review_query_refuses_malformed_guard_fields(self):
        for field,value in [('settling',1),('shieldUntil','2000'),('shieldUntil',-1),('shieldUntil',float('nan')),('shieldUntil',float('inf'))]:
            self.assertIsNone(self.district_reply(**{field:value})[0])
    def test_review_actual_app_does_not_schedule_recalling_member(self):
        app,runtime,executor=self.start_app()
        try:
            self.select(app);raw=self.before();raw.native.crew[2].recalling=True;app.Step(app,raw)
            self.assertIsNone(executor.callback);self.assertEqual(runtime.checkpoint.stationAttempts,0)
        finally:app.Destroy(app)
    def test_review_queued_home_backup_recall_cancels_without_attempt_charge(self):
        app,runtime,executor=self.start_app()
        try:
            self.select(app);raw=self.before();app.Step(app,raw);raw.native.crew[3].recalling=True;executor.callback()
            self.assertEqual(len(executor.calls),0);self.assertEqual(runtime.checkpoint.stationAttempts,0)
        finally:app.Destroy(app)
    def test_review_shield_appearing_before_dispatch_cancels_without_attempt_charge(self):
        app,runtime,executor=self.start_app()
        try:
            self.select(app);raw=self.before();app.Step(app,raw);raw.territoryDistrict.district.shieldUntil=2000;executor.callback()
            self.assertEqual(len(executor.calls),0);self.assertEqual(runtime.checkpoint.stationAttempts,0)
        finally:app.Destroy(app)
    def test_review_negative_reply_with_changed_stationed_flag_remains_uncertain(self):
        raw=self.before();proposal=self.module.propose(self.module.read(raw,raw)[0],self.settings())[0]
        baseline=self.module.capture(proposal,raw)[0];after=self.raw(2);after.native.crew[2].stationed=True
        self.assertEqual(self.module.evaluate(proposal,raw,after,lua_table(self.h.lua,{'ok':False}),baseline),'pending')
    def test_review_malformed_member_flags_refuse_instead_of_becoming_available(self):
        for field in ('recalling','stationed'):
            raw=self.before();raw.native.crew[2][field]='true';self.assertIsNone(self.module.read(raw,raw)[0])
    def test_review_expired_shield_boundary_allows_stationing(self):
        raw=self.before();raw.territoryDistrict.district.shieldUntil=raw.native.serverNow
        view=self.module.read(raw,raw)[0];self.assertIsNotNone(self.module.propose(view,self.settings())[0])

if __name__ == "__main__":
    unittest.main()
